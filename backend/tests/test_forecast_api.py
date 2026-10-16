from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app import models as M


def cell(c, row, month, value, **kw):
    return c.patch(f"/api/projects/{row}/months/{month}", json={"value": value, **kw})


def test_requires_sign_in(client):
    assert client.get("/api/forecast").status_code == 401
    assert client.get("/api/overview").status_code == 401


def test_fr02_unauthorized_edit_blocked_and_owner_named(as_user, db):
    ac = as_user("AC")  # Avery Chen (Client Partner) does not own R1002 (Jordan Malik)
    before = db.scalar(select(M.Revenue.amount).where(M.Revenue.project_id == "R1002", M.Revenue.month == "2026-11"))
    r = cell(ac, "R1002", "2026-11", "1")
    assert r.status_code == 403
    msg = r.json()["detail"]["message"]
    assert "Jordan Malik" in msg and "Client Partner" in msg and "Ask them to make this change" in msg
    after = db.scalar(select(M.Revenue.amount).where(M.Revenue.project_id == "R1002", M.Revenue.month == "2026-11"))
    assert before == after
    # a project row says who owns it and that Avery cannot edit it
    row = next(x for x in ac.get("/api/forecast").json()["rows"] if x["id"] == "R1002")
    assert row["can_edit"] is False and "Jordan Malik" in row["edit_reason"]


def test_owner_can_edit_and_leadership_can_edit_all(as_user):
    assert cell(as_user("JM"), "R1002", "2026-11", "70,000", reason="DATA_FIX").status_code == 200
    assert cell(as_user("CRO"), "R1001", "2026-11", 81000).status_code == 200
    assert cell(as_user("ADM"), "R1001", "2026-11", 82000).status_code == 200


def test_read_only_roles_cannot_edit(as_user):
    for code in ("RES", "FIN"):  # Resourcing is view-only; Finance does not edit forecast rows
        assert cell(as_user(code), "R1001", "2026-11", 1).status_code == 403


@pytest.mark.parametrize("bad", ["=90000-55000", "abc", "-5", "12k", "1/2", "NaN", "1e3"])
def test_fr05_rejects_formulas_text_negatives(as_user, db, bad):
    r = cell(as_user("AC"), "R1001", "2026-11", bad)
    assert r.status_code == 422
    assert r.json()["detail"]["message"]
    assert db.scalar(select(M.Revenue.amount).where(M.Revenue.project_id == "R1001", M.Revenue.month == "2026-11")) == 80000


def test_fr05_messages(as_user):
    ac = as_user("AC")
    assert "Formulas are not accepted" in cell(ac, "R1001", "2026-11", "=90000-55000").json()["detail"]["message"]
    assert "Revenue cannot be negative" in cell(ac, "R1001", "2026-11", "-5").json()["detail"]["message"]
    assert "Please enter a number" in cell(ac, "R1001", "2026-11", "text").json()["detail"]["message"]


def test_closed_month_edit_refused(as_user, db):
    r = cell(as_user("AC"), "R1001", "2026-09", "5")
    assert r.status_code == 409 and "Sep 26 is closed" in r.json()["detail"]["message"]


def test_other_reason_needs_note(as_user):
    r = cell(as_user("AC"), "R1001", "2026-11", 70000, reason="OTHER")
    assert r.status_code == 422 and "note" in r.json()["detail"]["message"].lower()
    assert cell(as_user("AC"), "R1001", "2026-11", 70000, reason="OTHER", note="Client call").status_code == 200


def test_batch_save_one_reason_many_cells(as_user):
    ac = as_user("AC")
    r = ac.post("/api/forecast/changes", json={"reason": "RATE_CHANGE", "note": "uplift",
                                                "changes": [{"row_id": "R1001", "month": "2026-11", "value": "81000"},
                                                            {"row_id": "R1001", "month": "2026-12", "value": "70000"},
                                                            {"row_id": "R1002", "month": "2026-11", "value": "5"}]})  # fmt: skip
    body = r.json()
    assert r.status_code == 200 and body["applied"] == 2  # the row Avery does not own is refused, the rest saved
    assert len(body["errors"]) == 1 and "Jordan Malik" in body["errors"][0]


def test_fr13_every_edit_logged_with_user_time_old_new(as_user):
    ac = as_user("AC")
    cell(ac, "R1001", "2026-11", "81,500", reason="RATE_CHANGE", note="uplift")
    cell(ac, "R1001", "2026-10", "")  # clearing a month is an edit too
    hist = ac.get("/api/history", params={"row_id": "R1001"}).json()["entries"]
    e = next(x for x in hist if x["field"] == "2026-11")
    assert (e["user"], e["user_name"], e["old"], e["new"], e["reason"], e["note"]) == ("AC", "Avery Chen", 80000, 81500, "RATE_CHANGE", "uplift")
    assert e["ts"].startswith("2026-10-01T") and e["field_label"] == "Nov 26"
    e2 = hist[0]  # newest first
    assert (e2["field"], e2["old"], e2["new"]) == ("2026-10", 80000, None)
    detail = ac.get("/api/projects/R1001").json()
    assert detail["history"][0]["id"] == e2["id"] and detail["history"][0]["id"] > "#2274"
    assert detail["last_updated_by"] == "AC" and detail["last_updated"] == "2026-10-01"


def test_edit_after_snapshot_is_flagged_and_snapshot_unchanged(as_user):
    ac = as_user("AC")
    cell(ac, "R1001", "2026-11", 1234)
    e = ac.get("/api/history", params={"row_id": "R1001", "limit": 1}).json()["entries"][0]
    assert e["after_snapshot"] is True  # month was in the Sep 1 snapshot


def test_fr19_duplicate_warning_and_confirm(as_user):
    ac = as_user("AC")
    body = {"customer": "Alberta Blue Cross", "project": "SRH Go Get", "tech": "PEGA", "region": "NA", "industry": "Insurance", "category": "EE"}
    assert ac.post("/api/projects", json=body).status_code == 201  # first one is fine
    near = {**body, "project": "SRH Go-Get"}
    r = ac.post("/api/projects", json=near)
    assert r.status_code == 409
    dups = r.json()["detail"]["duplicates"]
    assert dups[0]["customer"] == "Alberta Blue Cross" and dups[0]["similarity"] >= 70 and dups[0]["owner_label"]
    assert ac.post("/api/projects/check-duplicate", json=near).json()["duplicates"]
    assert ac.post("/api/projects", json={**near, "confirm_duplicate": True}).status_code == 201  # user confirmed


def test_new_project_owner_defaults_to_creator_and_seeded_duplicate(as_user):
    r = as_user("JM").post("/api/projects", json={"customer": "Newco", "project": "Phase 1", "tech": "PEGA", "region": "NA"})
    assert r.status_code == 201 and r.json()["client_partner"]["code"] == "JM" and r.json()["can_edit"] is True
    assert as_user("RES").post("/api/projects", json={"customer": "X", "project": "Y"}).status_code == 403
    dup = as_user("AC").post("/api/projects", json={"customer": "Lakemoor Pharma", "project": "Clinical Workflows"})
    assert dup.status_code == 409


def test_non_leaders_cannot_assign_owners(as_user):
    ac = as_user("AC")
    assert ac.patch("/api/projects/R1001", json={"client_partner": "JM"}).status_code == 403
    assert as_user("CRO").patch("/api/projects/R1001", json={"client_partner": "JM"}).status_code == 200
    h = as_user("CRO").get("/api/history", params={"row_id": "R1001", "kind": "field"}).json()["entries"][0]
    assert h["field"] == "Field: Client Partner" and (h["old"], h["new"]) == ("AC", "JM")


def test_month_close_and_reopen_by_finance(as_user):
    ac, fin = as_user("AC"), as_user("FIN")
    assert ac.post("/api/months/close", json={"closed_through": "2026-10", "reason": "x"}).status_code == 403
    assert fin.post("/api/months/close", json={"closed_through": "2026-10", "reason": ""}).status_code == 422
    assert fin.post("/api/months/close", json={"closed_through": "2026-10", "reason": "October books closed"}).status_code == 200
    assert cell(ac, "R1001", "2026-10", 1).status_code == 409
    assert fin.post("/api/months/close", json={"closed_through": "2026-09", "reason": "Late invoice found"}).status_code == 200
    assert cell(ac, "R1001", "2026-10", 79000).status_code == 200
    log = fin.get("/api/months/close-log").json()["log"]
    assert [x["to"] for x in log] == ["2026-09", "2026-10"]


def test_filters_and_subtotals(as_user):
    c = as_user("RES")
    all_ = c.get("/api/forecast").json()
    pega = c.get("/api/forecast", params={"tech": "PEGA"}).json()
    assert pega["count"] < all_["count"] and all(r["tech"] == "PEGA" for r in pega["rows"])
    assert pega["totals"]["committed"]["2026-10"] == sum(r["revenue"].get("2026-10", 0) for r in pega["rows"])
    tot = all_["totals"]
    for m in ("2026-10", "2027-03"):
        assert round(tot["total"][m]) == round(tot["committed"][m] + tot["weighted"][m])


def test_confirm_draft_requires_owner(as_user, db):
    assert as_user("AC").post("/api/projects/R1112/confirm-draft").status_code == 403
    assert as_user("Lowe").post("/api/projects/R1112/confirm-draft").status_code == 200
    assert db.get(M.Project, "R1112") and db.scalar(select(func.count()).select_from(M.Project)) == 112
