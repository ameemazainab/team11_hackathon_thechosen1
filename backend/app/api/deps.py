from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..domain import engine as E
from ..models import User
from ..services import state as ST


def current_user(request: Request, db: Session = Depends(get_db)) -> dict:
    code = request.session.get("uid")
    u = db.get(User, code) if code else None
    if u is None or not u.active:
        request.session.clear()
        raise HTTPException(401, "Please sign in.")
    return ST.user_dict(u)


def read_state(db: Session = Depends(get_db), settings: Settings = Depends(get_settings), _u: dict = Depends(current_user)) -> E.State:
    return ST.load_state(db, settings)


def capabilities(u: dict) -> dict:
    return {
        "can_create": E.can_create(u),
        "can_assign_owner": E.can_assign_owner(u),
        "can_snapshot": E.can_snapshot(u),
        "can_close_months": E.can_close_months(u),
        "can_admin": E.can_admin(u),
        "can_sync": E.has_role(u, "Finance", "Admin", "Sales leadership"),
        "can_edit_any": E.has_role(u, *E.EDITABLE_ROLES, "Sales leadership", "Admin"),
        "read_only": not E.has_role(u, *E.EDITABLE_ROLES, "Sales leadership", "Admin", "Finance"),
    }


def need(ok: bool, msg: str) -> None:
    if not ok:
        raise HTTPException(403, msg)


def filters_from(q: dict) -> dict:
    f = E.empty_filter()
    for k in f:
        if q.get(k):
            f[k] = q[k]
    return f
