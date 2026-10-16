"""Relational data model (FR-03, FR-13, FR-14). Snapshots and the audit log are append-only."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

NJSON = JSON(none_as_null=True)


class User(Base):
    __tablename__ = "users"
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    roles: Mapped[list] = mapped_column(JSON, default=list)
    location: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    customer: Mapped[str] = mapped_column(String(200), index=True)
    project: Mapped[str] = mapped_column(String(300))
    client_partner: Mapped[str | None] = mapped_column(ForeignKey("users.code"), nullable=True)
    ae: Mapped[str | None] = mapped_column(ForeignKey("users.code"), nullable=True)
    commercial_owner: Mapped[str | None] = mapped_column(ForeignKey("users.code"), nullable=True)
    tech: Mapped[str | None] = mapped_column(String(40), nullable=True)
    region: Mapped[str | None] = mapped_column(String(20), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(60), nullable=True)
    category: Mapped[str | None] = mapped_column(String(10), nullable=True)
    country: Mapped[str | None] = mapped_column(String(60), nullable=True)
    billing_type: Mapped[str] = mapped_column(String(30), default="T&M")
    currency: Mapped[str] = mapped_column(String(8), default="CAD")
    status: Mapped[str] = mapped_column(String(20), default="Active")
    # A HubSpot deal can be linked to one row only: this is what prevents double counting (FR-11).
    deal_id: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)
    last_updated: Mapped[str] = mapped_column(String(10))
    last_updated_by: Mapped[str | None] = mapped_column(String(60), nullable=True)
    draft_closed_at: Mapped[str | None] = mapped_column(String(10), nullable=True)
    draft_amount: Mapped[float | None] = mapped_column(Float, nullable=True)


class Revenue(Base):
    __tablename__ = "revenue"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    amount: Mapped[float] = mapped_column(Float)


class ChangeLog(Base):
    """The audit log: one row per changed cell or field. Never updated or deleted."""

    __tablename__ = "change_log"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_no: Mapped[int] = mapped_column(Integer, unique=True)
    ts: Mapped[str] = mapped_column(String(19), index=True)
    user_code: Mapped[str] = mapped_column(String(60))
    user_name: Mapped[str] = mapped_column(String(120))
    row_id: Mapped[str] = mapped_column(String(16), index=True)
    customer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    project: Mapped[str | None] = mapped_column(String(300), nullable=True)
    month: Mapped[str] = mapped_column(String(60))  # a month "2026-11" or a label such as "Field: Region"
    old: Mapped[object | None] = mapped_column(NJSON, nullable=True)
    new: Mapped[object | None] = mapped_column(NJSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_snapshot: Mapped[bool] = mapped_column(Boolean, default=False)


class Snapshot(Base):
    """An immutable forecast snapshot (FR-14). See the guards at the bottom of this file."""

    __tablename__ = "snapshots"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(60), unique=True)
    date: Mapped[str] = mapped_column(String(10))
    label: Mapped[str] = mapped_column(String(200))
    taken_by: Mapped[str] = mapped_column(String(120))
    created: Mapped[str] = mapped_column(String(19))
    auto: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict] = mapped_column(JSON)
    committed: Mapped[dict | None] = mapped_column(NJSON, nullable=True)
    weighted: Mapped[dict | None] = mapped_column(NJSON, nullable=True)


class Deal(Base):
    __tablename__ = "deals"
    deal_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200))
    company_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stage: Mapped[str] = mapped_column(String(60))
    close_date: Mapped[str] = mapped_column(String(20))
    tech: Mapped[str | None] = mapped_column(String(40), nullable=True)
    region: Mapped[str | None] = mapped_column(String(20), nullable=True)
    expected_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phasing: Mapped[dict | None] = mapped_column(NJSON, nullable=True)  # FR-21 owner override (month -> share)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class StageProbability(Base):
    __tablename__ = "stage_probabilities"
    stage: Mapped[str] = mapped_column(String(60), primary_key=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    probability: Mapped[float] = mapped_column(Float)
    in_forecast: Mapped[str] = mapped_column(String(12))  # Yes | Committed | No
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SyncEvent(Base):
    __tablename__ = "sync_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(String(19), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    deal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message: Mapped[str] = mapped_column(Text)


class FindingState(Base):
    __tablename__ = "finding_state"
    finding_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    status: Mapped[str] = mapped_column(String(12))  # open | accepted | dismissed
    reason: Mapped[str] = mapped_column(Text, default="")
    by_code: Mapped[str] = mapped_column(String(60))
    by_name: Mapped[str] = mapped_column(String(120))
    at: Mapped[str] = mapped_column(String(19))


class Attestation(Base):
    __tablename__ = "attestations"
    cycle: Mapped[str] = mapped_column(String(7), primary_key=True)
    row_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    by_code: Mapped[str] = mapped_column(String(60))
    at: Mapped[str] = mapped_column(String(19))


class MonthClose(Base):
    __tablename__ = "month_close_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[str] = mapped_column(String(19))
    by: Mapped[str] = mapped_column(String(120))
    from_month: Mapped[str] = mapped_column(String(7))
    to_month: Mapped[str] = mapped_column(String(7))
    reason: Mapped[str] = mapped_column(Text)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[object | None] = mapped_column(NJSON, nullable=True)


class ReasonCode(Base):
    __tablename__ = "reason_codes"
    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(120))
    use_when: Mapped[str | None] = mapped_column(Text, nullable=True)


class CalendarDay(Base):
    __tablename__ = "billing_calendar"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(60))
    date: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(40))
    factor: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("country", "date", name="uq_calendar_country_date"),)


class Actual(Base):
    __tablename__ = "actuals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch: Mapped[str] = mapped_column(String(40), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    customer: Mapped[str] = mapped_column(String(200))
    project: Mapped[str | None] = mapped_column(String(300), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    row_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(120))
    uploaded_at: Mapped[str] = mapped_column(String(19))


class AiLog(Base):
    __tablename__ = "ai_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(String(19))
    user_code: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(30))
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    used_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt: Mapped[str] = mapped_column(Text)
    output: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job: Mapped[str] = mapped_column(String(40), index=True)
    started: Mapped[str] = mapped_column(String(19))
    finished: Mapped[str | None] = mapped_column(String(19), nullable=True)
    status: Mapped[str] = mapped_column(String(12))  # ok | failed
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


Index("ix_attestations_row", Attestation.row_id)


# --- immutability guards -------------------------------------------------------------
class ImmutableRecordError(RuntimeError):
    pass


@event.listens_for(Snapshot, "before_update")
def _snapshot_no_update(*_):
    raise ImmutableRecordError("Snapshots cannot be changed after they are taken.")


@event.listens_for(Snapshot, "before_delete")
def _snapshot_no_delete(*_):
    raise ImmutableRecordError("Snapshots cannot be deleted.")


@event.listens_for(ChangeLog, "before_update")
def _log_no_update(*_):
    raise ImmutableRecordError("Audit log entries cannot be changed.")


@event.listens_for(ChangeLog, "before_delete")
def _log_no_delete(*_):
    raise ImmutableRecordError("Audit log entries cannot be deleted.")
