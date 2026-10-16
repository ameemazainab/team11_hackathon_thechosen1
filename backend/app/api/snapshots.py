from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as M
from ..config import Settings, get_settings
from ..db import get_db
from ..domain import engine as E
from ..domain.util import m_label, tidy
from ..services import actuals as AC
from ..services import state as ST
from ..services.exports import to_xlsx
from .deps import current_user, need, read_state
from .forecast import filter_params

router = APIRouter(prefix="/api", tags=["snapshots"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def snap_out(S: E.State, s: dict, detail: bool = False) -> dict:
    ms = E.snap_months(S, s)
    tot = E.snapshot_totals(S, s)
    out = {"id": s["id"], "date": s["date"], "label": s["label"], "taken_by": s["taken_by"], "created": s.get("created"),
           "auto": s.get("auto", False), "rows": len(s["data"]), "months": ms,
           "committed": {m: tidy(v) for m, v in tot.items()},
           "weighted": {m: tidy(round(v)) for m, v in (s.get("weighted") or {}).items() if m in ms} if s.get("weighted") else None}  # fmt: skip
    if detail:
        out["table"] = [
            {"id": rid, "customer": (S.project(rid) or {}).get("customer", ""), "project": (S.project(rid) or {}).get("project", ""),
             "client_partner": E.user_name(S, (S.project(rid) or {}).get("client_partner")), "values": {m: r.get(m) for m in ms if r.get(m) is not None}}
            for rid, r in s["data"].items()
        ]  # fmt: skip
    return out


@router.get("/snapshots")
def list_snapshots(S: E.State = Depends(read_state)):
    return [snap_out(S, s) for s in reversed(S.snapshots)]


class NewSnapshot(BaseModel):
    label: str | None = None


def create_snapshot(db: Session, settings: Settings, who: str, label: str | None, auto: bool) -> dict:
    S = ST.load_state(db, settings, for_write=True)
    snap = E.take_snapshot(S, who, label, auto=auto, snap_id=f"snap-{S.as_of}-{uuid.uuid4().hex[:6]}")
    db.add(M.Snapshot(id=snap["id"], date=snap["date"], label=snap["label"], taken_by=snap["taken_by"], created=snap["created"],
                      auto=auto, data=snap["data"], committed=snap["committed"], weighted=snap["weighted"]))  # fmt: skip
    db.commit()
    return snap_out(S, snap)


@router.post("/snapshots", status_code=201)
def take_snapshot(body: NewSnapshot, db: Session = Depends(get_db), settings: Settings = Depends(get_settings), u: dict = Depends(current_user)):
    need(E.can_snapshot(u), "Only Finance or an Admin can take a snapshot.")
    return create_snapshot(db, settings, u["name"], (body.label or "").strip() or None, auto=False)


def _snap(S: E.State, sid: str) -> dict:
    s = next((x for x in S.snapshots if x["id"] == sid), None)
    if not s:
        raise HTTPException(404, "Snapshot not found")
    return s


@router.get("/snapshots/{sid}")
def snapshot_detail(sid: str, S: E.State = Depends(read_state)):
    return snap_out(S, _snap(S, sid), detail=True)


def _file(content: bytes | str, name: str, media: str) -> Response:
    return Response(content=content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/export/forecast")
def export_current(format: str = "xlsx", S: E.State = Depends(read_state), u: dict = Depends(current_user), f: dict = Depends(filter_params)):
    t = E.export_forecast(S, u, f)
    stem = f"chosen-one-forecast-{S.as_of}"
    if format == "csv":
        return _file(E.to_csv(t), stem + ".csv", "text/csv; charset=utf-8")
    if format != "xlsx":
        raise HTTPException(422, "Format must be xlsx or csv.")
    return _file(to_xlsx(t, "Forecast"), stem + ".xlsx", XLSX)


@router.get("/snapshots/{sid}/export")
def export_snapshot(sid: str, format: str = "xlsx", S: E.State = Depends(read_state), u: dict = Depends(current_user)):
    s = _snap(S, sid)
    t = E.export_snapshot(S, u, s)
    stem = f"chosen-one-{s['id']}"
    if format == "csv":
        return _file(E.to_csv(t), stem + ".csv", "text/csv; charset=utf-8")
    if format != "xlsx":
        raise HTTPException(422, "Format must be xlsx or csv.")
    return _file(to_xlsx(t, "Snapshot"), stem + ".xlsx", XLSX)


# ---------------------------------------------------------------- actuals and accuracy (FR-16)
@router.post("/actuals/upload")
async def upload_actuals(file: UploadFile = File(...), db: Session = Depends(get_db), settings: Settings = Depends(get_settings), u: dict = Depends(current_user)):
    need(E.can_snapshot(u), "Only Finance or an Admin can load actuals.")
    content = await file.read()
    if len(content) > 5_000_000:
        raise HTTPException(413, "That file is too large (limit 5 MB).")
    if not (file.filename or "").lower().endswith((".csv", ".xlsx", ".xlsm")):
        raise HTTPException(422, "Please upload a .csv or .xlsx file.")
    S = ST.load_state(db, settings)
    try:
        r = AC.load_actuals(db, S, u, file.filename or "actuals.csv", content)
    except Exception as exc:
        raise HTTPException(422, f"That file could not be read: {exc}") from exc
    if not r["ok"]:
        raise HTTPException(422, detail={"message": r["error"], "rejects": r.get("rejects", [])})
    return r


@router.get("/actuals/template")
def actuals_template():
    csv = "Customer,Project,Amount,Month\nKestrel Life & Annuity,Policy Admin Modernization,80000,2026-10\n"
    return _file(csv, "actuals-template.csv", "text/csv; charset=utf-8")


@router.get("/actuals")
def list_actuals(db: Session = Depends(get_db)):
    from sqlalchemy import func

    rows = db.execute(select(M.Actual.month, func.sum(M.Actual.amount), func.count(), func.max(M.Actual.uploaded_at), func.max(M.Actual.uploaded_by))
                      .group_by(M.Actual.month).order_by(M.Actual.month)).all()  # fmt: skip
    return [{"month": m, "label": m_label(m), "total": tidy(a), "lines": n, "uploaded_at": t, "uploaded_by": b} for m, a, n, t, b in rows]


@router.get("/insights/accuracy")
def accuracy(db: Session = Depends(get_db), S: E.State = Depends(read_state)):
    return AC.accuracy_report(db, S)


# ---------------------------------------------------------------- month close
class Close(BaseModel):
    closed_through: str
    reason: str


@router.get("/months/close-log")
def close_log(S: E.State = Depends(read_state)):
    return {"closed_through": S.closed_through, "log": list(reversed(S.close_log))}


@router.post("/months/close")
def close_months(body: Close, db: Session = Depends(get_db), settings: Settings = Depends(get_settings), u: dict = Depends(current_user)):
    S = ST.load_state(db, settings, for_write=True)
    r = E.commit_month_close(S, u, body.closed_through, body.reason)
    if not r["ok"]:
        raise HTTPException(403 if "Only" in r["error"] else 422, r["error"])
    e = r["entry"]
    db.add(M.MonthClose(at=e["at"], by=e["by"], from_month=e["from"], to_month=e["to"], reason=e["reason"]))
    ST.set_setting(db, "closed_through", S.closed_through)
    db.commit()
    return {"ok": True, "closed_through": S.closed_through}
