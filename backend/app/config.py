"""Application settings, loaded with pydantic-settings.

Locally these come from ``backend/.env`` (git-ignored). On Railway they come from the service's Variables.
Secrets never go into React, Git or the Docker image.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "development", "production"] = "local"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'chosen_one.db'}"
    secret_key: str = "dev-only-change-me"
    base_url: str = "http://localhost:8000"
    frontend_dir: str = ""  # folder holding the built React app; empty = auto-detect

    # --- sign-in ---
    auth_mode: Literal["demo", "google"] | None = None  # None = demo locally, google elsewhere
    allow_demo_auth_in_production: bool = False
    google_client_id: str = ""
    google_client_secret: str = ""
    google_hosted_domain: str = ""  # e.g. bitsinglass.com; empty = any Google account that is provisioned
    session_hours: int = 12
    demo_default_user: str = "CRO"

    # --- the "as of" date. Empty = today. The sample data is dated 2026-10-01. ---
    as_of_date: str = ""
    seed_on_startup: bool = True  # load the sample data when the database is empty
    bootstrap_admin_email: str = ""  # creates this Google user as an Admin if it does not exist

    # --- HubSpot (read-only) ---
    hubspot_token: str = ""
    hubspot_pipeline_id: str = ""  # empty = all deal pipelines
    hubspot_prop_expected_start: str = "expected_start_date"
    hubspot_prop_duration: str = "duration_months"
    hubspot_prop_tech: str = "practice"
    hubspot_prop_region: str = "region"
    sync_stale_minutes: int = 120

    # --- Claude (optional) ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    ai_monthly_cost_ceiling_usd: float = 250.0
    ai_input_usd_per_mtok: float = 3.0
    ai_output_usd_per_mtok: float = 15.0

    @model_validator(mode="after")
    def _resolve(self):
        if self.auth_mode is None:
            self.auth_mode = "demo" if self.app_env == "local" else "google"
        if self.app_env == "production":
            if self.auth_mode == "demo" and not self.allow_demo_auth_in_production:
                raise ValueError("AUTH_MODE=demo is not allowed in production. Use AUTH_MODE=google.")
            if self.secret_key == "dev-only-change-me":
                raise ValueError("SECRET_KEY must be set in production.")
        if self.auth_mode == "google" and not (self.google_client_id and self.google_client_secret):
            # allowed to boot (so health checks pass) but sign-in will report a clear message
            pass
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self

    @property
    def is_demo_auth(self) -> bool:
        return self.auth_mode == "demo"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()

