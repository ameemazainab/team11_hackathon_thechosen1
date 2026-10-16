"""Test set-up: one seeded template database (built through the real Alembic migration), copied for each test."""

from __future__ import annotations

import os
import shutil
import warnings

warnings.filterwarnings("ignore")
os.environ.update({"APP_ENV": "local", "AUTH_MODE": "demo", "AS_OF_DATE": "2026-10-01", "ANTHROPIC_API_KEY": "", "HUBSPOT_TOKEN": "",
                   "SEED_ON_STARTUP": "true", "BOOTSTRAP_ADMIN_EMAIL": ""})  # fmt: skip

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as DB  # noqa: E402
from app.config import get_settings, reset_settings_cache  # noqa: E402
from app.main import create_app, prepare_database  # noqa: E402


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("tpl") / "template.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    reset_settings_cache()
    DB.init_engine(os.environ["DATABASE_URL"])
    prepare_database(get_settings(), migrate=True)  # alembic upgrade head + seed from seed.json
    DB.get_engine().dispose()
    return path


@pytest.fixture()
def env(template_db, tmp_path):
    path = tmp_path / "test.db"
    shutil.copy(template_db, path)
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    reset_settings_cache()
    DB.init_engine(os.environ["DATABASE_URL"])
    yield get_settings()
    DB.get_engine().dispose()


@pytest.fixture()
def app(env):
    return create_app(prepare=False)


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


def login(app, code: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/demo-login", json={"code": code})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture()
def as_user(app):
    def _as(code: str) -> TestClient:
        return login(app, code)

    return _as


@pytest.fixture()
def db(env):
    with DB.session_factory()() as s:
        yield s
