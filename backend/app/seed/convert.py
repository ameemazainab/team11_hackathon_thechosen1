"""Convert the camelCase seed.json (exported from the original Google Sheet and HubSpot samples)
into the snake_case structures used by the application."""

from __future__ import annotations

import json
from pathlib import Path

SEED_PATH = Path(__file__).with_name("seed.json")


def load_seed() -> dict:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def convert_project(p: dict) -> dict:
    return {
        "id": p["id"], "customer": p["customer"], "project": p["project"],
        "client_partner": p.get("clientPartner"), "ae": p.get("ae"), "commercial_owner": p.get("commercialOwner"),
        "tech": p.get("tech"), "region": p.get("region"), "industry": p.get("industry"), "category": p.get("category"),
        "country": p.get("country"), "billing_type": p.get("billingType") or "T&M", "currency": "CAD",
        "status": p["status"], "last_updated": p["lastUpdated"], "last_updated_by": p["lastUpdatedBy"],
        "revenue": dict(p["revenue"]), "deal_id": None,
    }  # fmt: skip


def convert_log(e: dict) -> dict:
    return {
        "entry_no": int(e["id"].lstrip("#")), "ts": e["ts"], "user": e["user"], "user_name": e["userName"],
        "row_id": e["rowId"], "customer": e.get("customer"), "project": e.get("project"), "month": e["month"],
        "old": e.get("old"), "new": e.get("new"), "reason": e.get("reason"), "note": e.get("note"),
    }  # fmt: skip


def convert_deal(d: dict) -> dict:
    return {
        "deal_id": d["dealId"], "name": d["name"], "company": d["company"], "company_id": d.get("companyId"),
        "amount": d["amount"], "owner": d["owner"], "stage": d["stage"], "close_date": d["closeDate"],
        "tech": d.get("tech"), "region": d.get("region"), "expected_start": d.get("expectedStart"),
        "duration_months": d.get("durationMonths"),
    }  # fmt: skip


def convert_stage(s: dict) -> dict:
    return {"stage": s["stage"], "probability": s["probability"], "in_forecast": s["inForecast"], "note": s.get("note")}
