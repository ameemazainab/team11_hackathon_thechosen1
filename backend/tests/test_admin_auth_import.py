"""FR-01, FR-06, FR-23 and set-up safety."""

from __future__ import annotations

import io
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select

from app import db as DB
from app import models as M
from app.api import auth as auth_api
from app.config import Settings, reset_settings_cache
from app.main import create_app, prepare_database
from app.services import importer


def test_demo_auth_refused_in_production(monkeypatch):
    monkeypatch.delenv("AUTH_MODE", raising=False)
    with pytest.raises(ValueError, match="AUTH_MODE=demo is not allowed in production"):
        Settings(app_env="production", auth_mode="demo", secret_key="x" * 20)
    s = Settings(app_env="production", secret_key="x" * 20)  # unset means Google in production
    assert s.auth_mode == "google"
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(app_env="production", auth_mode="google")
    assert Settings(app_env="local").auth_mode == "demo"
    assert Settings(database_url="postgres://u:p@h/db").database_url.startswith("postgresql+psycopg://")


def test_google_mode_has_no_demo_login(env, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "google")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    reset_settings_cache()
    with TestClient(create_app(prepare=False)) as c:
        assert c.get("/api/auth/config").json()["mode"] == "google"
        assert c.post("/api/auth/demo-login", json={"code": "CRO"}).status_code == 404
        assert c.get("/api/auth/demo-users").status_code == 404
        assert c.get("/api/forecast").status_code == 401


def test_fr01_only_provisioned_users_can_sign_in(env, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "google")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    reset_settings_cache()
    fake = MagicMock()
    monkeypatch.setattr(auth_api, "oauth", lambda settings: fake)
    with TestClient(create_app(prepare=False), follow_redirects=False) as c:
        fake.google.authorize_access_token = AsyncMock(return_value={"userinfo": {"email": "stranger@gmail.com", "email_verified": True}})
        r = c.get("/api/auth/callback")
        assert r.status_code in (302, 307) and r.headers["location"] == "/?signin=denied"
        assert c.get("/api/auth/me").status_code == 401
        fake.google.authorize_access_token = AsyncMock(return_value={"userinfo": {"email": "AVERY.CHEN@example.com", "email_verified": True}})
        r = c.get("/api/auth/callback")
        assert r.headers["location"] == "/"
        assert c.get("/api/auth/me").json()["user"]["name"] == "Avery Chen"
        fake.google.authorize_access_token = AsyncMock(return_value={"userinfo": {"email": "cro@example.com", "email_verified": False}})
        assert c.get("/api/auth/callback").headers["location"] == "/?signin=unverified"


def test_deactivated_user_loses_access(as_user):
    ac = as_user("AC")
    assert ac.get("/api/auth/me").status_code == 200
    adm = as_user("ADM")
    u = next(x for x in adm.get("/api/admin/users").json()["users"] if x["code"] == "AC")
    assert adm.patch("/api/admin/users/AC", json={**u, "active": False}).status_code == 200
    assert ac.get("/api/auth/me").status_code == 401


def test_admin_screens_are_admin_only(as_user):
    for path in ("/api/admin/users", "/api/admin/stages", "/api/admin/thresholds", "/api/admin/calendar", "/api/admin/jobs", "/api/ai-log"):
        assert as_user("CRO").get(path).status_code == 403, path
        assert as_user("ADM").get(path).status_code == 200, path


def test_admin_users_roles_and_guards(as_user):
    adm = as_user("ADM")
    r = adm.post("/api/admin/users", json={"name": "Nia Okoye", "email": "nia@example.com", "roles": ["Seller / AE"]})
    assert r.status_code == 201
    code = r.json()["code"]
    assert adm.post("/api/admin/users", json={"name": "Dup", "email": "NIA@example.com", "roles": ["Admin"]}).status_code == 409
    assert adm.post("/api/admin/users", json={"name": "X", "email": "x@example.com", "roles": ["Wizard"]}).status_code == 422
    me = next(x for x in adm.get("/api/admin/users").json()["users"] if x["code"] == "ADM")
    assert adm.patch("/api/admin/users/ADM", json={**me, "roles": ["Finance"]}).status_code == 422  # cannot lock yourself out
    assert as_user(code).get("/api/forecast").status_code == 200  # a newly provisioned seller can sign in
    # roles change what the person may do
    assert as_user(code).post("/api/projects", json={"customer": "Zed", "project": "One"}).status_code == 201


def test_admin_thresholds_calendar_reasons(as_user):
    adm = as_user("ADM")
    t = adm.get("/api/admin/thresholds").json()
    assert t["staleDays"] == 30
    assert adm.put("/api/admin/thresholds", json={**t, "staleDays": 10}).status_code == 200
    assert len([f for f in as_user("CRO").get("/api/checks").json()["findings"] if f["rule"] == "STALE"]) > 7
    assert adm.put("/api/admin/thresholds", json={**t, "reviewDue": "soon"}).status_code == 422
    assert adm.post("/api/admin/calendar", json={"country": "UK", "date": "2027-06-15", "name": "Boxing Day (observed)", "factor": 0}).status_code == 201
    assert adm.post("/api/admin/calendar", json={"country": "UK", "date": "2027-06-15", "name": "dup", "factor": 0}).status_code == 409
    reasons = as_user("CRO").get("/api/meta").json()["reasons"]
    assert adm.put("/api/admin/reasons", json=[{"code": r["code"], "label": r["label"], "use_when": r["use_when"]} for r in reasons if r["code"] != "OTHER"]).status_code == 422


def test_amount_mismatch_rule_is_available_and_off_by_default(as_user):
    adm, cro = as_user("ADM"), as_user("CRO")
    assert not [f for f in cro.get("/api/checks").json()["findings"] if f["rule"] == "AMOUNT_MISMATCH"]
    t = adm.get("/api/admin/thresholds").json()
    adm.put("/api/admin/thresholds", json={**t, "amountMismatchCheck": True})
    hits = [f for f in cro.get("/api/checks").json()["findings"] if f["rule"] == "AMOUNT_MISMATCH"]
    assert hits and "differs" in hits[0]["title"].lower()


def sheet(rows, months=("2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03")):
    import datetime as dt

    wb = Workbook()
    ws = wb.active
    ws.title = "Forecast"
    ws.append(["subtotals"])
    ws.append(["Customer", "Project", "Client Partner", "AE", "TECH", "Region", "Industry", "CATG",
               *[dt.datetime(int(m[:4]), int(m[5:]), 1) for m in months], "Row ID"])  # fmt: skip
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_fr06_import_reports_every_bad_row_and_totals(tmp_path, monkeypatch):
    path = tmp_path / "fresh.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("SEED_ON_STARTUP", "false")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "boss@example.com")
    reset_settings_cache()
    from app.config import get_settings

    DB.init_engine(f"sqlite:///{path}")
    prepare_database(get_settings(), migrate=True)
    with DB.session_factory()() as db:
        db.add(M.User(code="AC", name="Avery Chen", email="ac@example.com", roles=["Client Partner"]))
        db.commit()
        admin = db.scalar(select(M.User).where(M.User.email == "boss@example.com"))
        assert admin.roles == ["Admin"]
        content = sheet([
            ["Acme", "Build", "AC", "N/A", "PEGA", "NA", "Insurance", "EE", 100, 200, 300, 400, 500, 600, "R2001"],
            ["Beta", "Run", "AC", None, "CRM", "UK", "Banking", "EN", 10, "=90000-55000", 30, None, None, None, "R2002"],
            ["Gamma", "Run", "ZZ", None, "CRM", "UK", "Banking", "EN", 10, 20, 30, None, None, None, "R2003"],
            ["Delta", "Run", "AC", None, "CRM", "UK", "Banking", "EN", 10, "n/a", -5, "text", None, None, "R2004"],
            ["Echo", "Run", "AC", None, "CRM", "NA", "GCC", "EE", 7, None, 9, None, None, None, "R2005"],
        ])  # fmt: skip
        admin_u = {"code": admin.code, "name": admin.name, "roles": admin.roles}
        dry = importer.import_workbook(db, get_settings(), admin_u, content, commit=False)
        assert dry["rows_found"] == 5 and dry["rows_accepted"] == 2 and dry["rows_rejected"] == 3 and dry["committed"] is False
        bad = {r["customer"]: r["problems"] for r in dry["rejects"]}
        assert "formula" in bad["Beta"][0] and "Unknown client partner" in bad["Gamma"][0]
        assert len(bad["Delta"]) == 2  # negative and text both reported (n/a is a blank)
        assert dry["totals_by_month"]["2026-10"] == 107 and dry["totals_by_month"]["2026-12"] == 309  # accepted rows only: to the dollar
        assert db.query(M.Project).count() == 0
        done = importer.import_workbook(db, get_settings(), admin_u, content, commit=True)
        assert done["committed"] and db.query(M.Project).count() == 2
        assert db.query(M.Revenue).count() == 6 + 2
        assert db.query(M.ChangeLog).count() == 2
        again = importer.import_workbook(db, get_settings(), admin_u, content, commit=True)
        assert again["ok"] is False  # one-time only
    DB.get_engine().dispose()
    os.environ.pop("SEED_ON_STARTUP", None)
    os.environ.pop("BOOTSTRAP_ADMIN_EMAIL", None)
    reset_settings_cache()


def test_import_endpoint_is_admin_only_and_dry_run_by_default(as_user):
    content = sheet([["Acme", "Build", "AC", None, "PEGA", "NA", "Insurance", "EE", 1, 2, 3, 4, 5, 6, "R9001"]])
    assert as_user("CRO").post("/api/admin/import", files={"file": ("x.xlsx", content)}).status_code == 403
    r = as_user("ADM").post("/api/admin/import", files={"file": ("x.xlsx", content)})
    assert r.status_code == 200 and r.json()["committed"] is False
    assert as_user("ADM").post("/api/admin/import", params={"commit": True}, files={"file": ("x.xlsx", content)}).status_code == 422  # not empty


def test_alembic_schema_matches_models(template_db):
    from sqlalchemy import create_engine, inspect

    insp = inspect(create_engine(f"sqlite:///{template_db}"))
    assert set(insp.get_table_names()) >= set(DB.Base.metadata.tables) | {"alembic_version"}
    for name, table in DB.Base.metadata.tables.items():
        assert {c["name"] for c in insp.get_columns(name)} == {c.name for c in table.columns}, name


def test_health_and_security_headers(client):
    r = client.get("/api/health")
    assert r.json()["status"] == "ok" and r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert client.get("/api/health").headers["cache-control"] == "no-store"
