from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from alembic import command

from .api import admin, auth, checks, forecast, insights, overview, pipeline, snapshots
from .config import BACKEND_DIR, Settings, get_settings
from .db import Base, get_engine, session_factory
from .services import seeding

log = logging.getLogger("chosen_one")


def run_migrations() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


def prepare_database(settings: Settings, migrate: bool = True) -> None:
    if migrate:
        run_migrations()
    else:
        Base.metadata.create_all(get_engine())
    with session_factory()() as db:
        if settings.seed_on_startup:
            seeding.seed_database(db, settings)
        else:
            seeding.ensure_reference_data(db, settings)
        if settings.bootstrap_admin_email:
            seeding.ensure_bootstrap_admin(db, settings.bootstrap_admin_email)


def find_frontend(settings: Settings) -> Path | None:
    candidates = [settings.frontend_dir] if settings.frontend_dir else []
    candidates += [str(BACKEND_DIR / "static"), str(BACKEND_DIR.parent / "frontend" / "dist")]
    for c in candidates:
        if c and (Path(c) / "index.html").exists():
            return Path(c)
    return None


def create_app(migrate: bool = True, prepare: bool = True) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if prepare:
            prepare_database(settings, migrate=migrate)
        yield

    app = FastAPI(title="The Chosen One", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(
        SessionMiddleware, secret_key=settings.secret_key, max_age=settings.session_hours * 3600, same_site="lax",
        https_only=settings.app_env != "local", session_cookie="chosen_one_session",
    )  # fmt: skip

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if request.url.path.startswith("/api/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    for r in (auth, forecast, checks, pipeline, snapshots, insights, admin, overview):
        app.include_router(r.router)

    @app.get("/api/health")
    def health():
        with get_engine().connect() as c:
            c.execute(text("select 1"))
        return {"status": "ok", "env": settings.app_env, "auth_mode": settings.auth_mode}

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = [".".join(str(x) for x in e["loc"][1:]) for e in exc.errors()]
        return JSONResponse({"detail": {"message": "Some of the information is missing or not valid: " + ", ".join(f for f in fields if f), "errors": jsonable_encoder(exc.errors(), custom_encoder={Exception: str})}}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse({"detail": {"message": "Something went wrong on our side. Please try again."}}, status_code=500)

    dist = find_frontend(settings)
    if dist:
        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            f = (dist / path).resolve()
            if path and f.is_file() and dist.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
