from __future__ import annotations

import logging

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..models import User
from ..services import state as ST
from .deps import capabilities, current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger(__name__)
_oauth: OAuth | None = None


def oauth(settings: Settings) -> OAuth:
    global _oauth
    if _oauth is None:
        _oauth = OAuth()
        _oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    return _oauth


@router.get("/config")
def auth_config(settings: Settings = Depends(get_settings)):
    return {"mode": settings.auth_mode, "google_configured": bool(settings.google_client_id and settings.google_client_secret),
            "demo_default_user": settings.demo_default_user, "env": settings.app_env}  # fmt: skip


@router.get("/demo-users")
def demo_users(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)):
    if not settings.is_demo_auth:
        raise HTTPException(404, "Not available")
    return [{"code": u.code, "name": u.name, "roles": u.roles, "notes": u.notes}
            for u in db.scalars(select(User).where(User.active.is_(True)).order_by(User.name))]  # fmt: skip


class DemoLogin(BaseModel):
    code: str


@router.post("/demo-login")
def demo_login(body: DemoLogin, request: Request, settings: Settings = Depends(get_settings), db: Session = Depends(get_db)):
    if not settings.is_demo_auth:
        raise HTTPException(404, "Not available")
    u = db.get(User, body.code)
    if not u or not u.active:
        raise HTTPException(404, "No such user")
    request.session.clear()
    request.session["uid"] = u.code
    return me_payload(ST.user_dict(u), settings)


def me_payload(u: dict, settings: Settings) -> dict:
    return {"user": {k: u[k] for k in ("code", "name", "email", "roles")}, "capabilities": capabilities(u),
            "auth_mode": settings.auth_mode, "ai_enabled": settings.ai_enabled}  # fmt: skip


@router.get("/me")
def me(u: dict = Depends(current_user), settings: Settings = Depends(get_settings)):
    return me_payload(u, settings)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/login")
async def google_login(request: Request, settings: Settings = Depends(get_settings)):
    if settings.auth_mode != "google":
        raise HTTPException(404, "Google sign-in is not enabled")
    if not (settings.google_client_id and settings.google_client_secret):
        raise HTTPException(503, "Google sign-in is not set up yet. Ask an administrator.")
    redirect_uri = settings.base_url.rstrip("/") + "/api/auth/callback"
    params = {"hd": settings.google_hosted_domain} if settings.google_hosted_domain else {}
    return await oauth(settings).google.authorize_redirect(request, redirect_uri, **params)


@router.get("/callback")
async def google_callback(request: Request, settings: Settings = Depends(get_settings), db: Session = Depends(get_db)):
    if settings.auth_mode != "google":
        raise HTTPException(404, "Google sign-in is not enabled")
    try:
        token = await oauth(settings).google.authorize_access_token(request)
    except OAuthError as exc:
        log.warning("Google sign-in failed: %s", exc)
        return RedirectResponse("/?signin=failed")
    info = token.get("userinfo") or {}
    email = (info.get("email") or "").lower()
    if not email or not info.get("email_verified", False):
        return RedirectResponse("/?signin=unverified")
    if settings.google_hosted_domain and info.get("hd") != settings.google_hosted_domain:
        return RedirectResponse("/?signin=domain")
    u = db.scalar(select(User).where(func.lower(User.email) == email, User.active.is_(True)))
    if u is None:  # FR-01: only provisioned users may enter
        log.warning("Sign-in refused for unprovisioned account %s", email)
        return RedirectResponse("/?signin=denied")
    request.session.clear()
    request.session["uid"] = u.code
    return RedirectResponse("/")
