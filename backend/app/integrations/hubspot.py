"""HubSpot access. READ-ONLY: this module only issues GET requests and the search/batch-read POSTs,
never creates, updates or deletes anything in HubSpot.

With HUBSPOT_TOKEN set (a private-app token with read scopes) the live account is used. Without a
token the sample deals shipped in seed.json are used, so the app works offline and in demos.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from ..config import Settings
from ..seed.convert import convert_deal, convert_stage, load_seed

log = logging.getLogger(__name__)
API = "https://api.hubapi.com"


@dataclass
class HubSpotData:
    deals: list[dict]
    stages: list[dict] = field(default_factory=list)  # {stage, probability} defaults from HubSpot
    source: str = "sample"


class SampleClient:
    """Fallback used when no HubSpot token is configured."""

    def fetch(self) -> HubSpotData:
        seed = load_seed()
        deals = [convert_deal(d) for d in seed["onDeck"] + seed["recentClosed"]]
        stages = [{"stage": s["stage"], "probability": s["probability"]} for s in map(convert_stage, seed["stageProbabilities"])]
        return HubSpotData(deals=deals, stages=stages, source="sample")


class HubSpotClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.s = settings
        self.http = httpx.Client(
            base_url=API, timeout=30, transport=transport,
            headers={"Authorization": f"Bearer {settings.hubspot_token}", "Content-Type": "application/json"},
        )  # fmt: skip

    def _get(self, path: str, **params):
        r = self.http.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def _stages(self) -> tuple[dict[str, str], list[dict]]:
        labels: dict[str, str] = {}
        probs: list[dict] = []
        for pl in self._get("/crm/v3/pipelines/deals").get("results", []):
            if self.s.hubspot_pipeline_id and pl["id"] != self.s.hubspot_pipeline_id:
                continue
            for st in pl.get("stages", []):
                name = _stage_name(st["id"], st["label"])
                labels[st["id"]] = name
                try:
                    probs.append({"stage": name, "probability": float(st.get("metadata", {}).get("probability", 0))})
                except (TypeError, ValueError):
                    probs.append({"stage": name, "probability": 0.0})
        return labels, probs

    def _owners(self) -> dict[str, str]:
        out: dict[str, str] = {}
        after = None
        while True:
            params = {"limit": 100, **({"after": after} if after else {})}
            data = self._get("/crm/v3/owners", **params)
            for o in data.get("results", []):
                out[str(o["id"])] = (f"{o.get('firstName') or ''} {o.get('lastName') or ''}").strip() or o.get("email", "")
            after = data.get("paging", {}).get("next", {}).get("after")
            if not after:
                return out

    def _companies(self, ids: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for i in range(0, len(ids), 100):
            chunk = ids[i : i + 100]
            r = self.http.post("/crm/v3/objects/companies/batch/read", json={"properties": ["name"], "inputs": [{"id": c} for c in chunk]})
            r.raise_for_status()
            for c in r.json().get("results", []):
                out[str(c["id"])] = c.get("properties", {}).get("name") or str(c["id"])
        return out

    def fetch(self) -> HubSpotData:
        s = self.s
        labels, probs = self._stages()
        owners = self._owners()
        props = ["dealname", "amount", "dealstage", "closedate", "hubspot_owner_id", "pipeline",
                 s.hubspot_prop_expected_start, s.hubspot_prop_duration, s.hubspot_prop_tech, s.hubspot_prop_region]  # fmt: skip
        raw: list[dict] = []
        after = None
        while True:
            params = {"limit": 100, "properties": ",".join(props), "associations": "companies", **({"after": after} if after else {})}
            data = self._get("/crm/v3/objects/deals", **params)
            raw.extend(data.get("results", []))
            after = data.get("paging", {}).get("next", {}).get("after")
            if not after:
                break
        company_of: dict[str, str] = {}
        for d in raw:
            assoc = d.get("associations", {}).get("companies", {}).get("results", [])
            if assoc:
                company_of[d["id"]] = str(assoc[0]["id"])
        names = self._companies(sorted(set(company_of.values())))
        deals = []
        for d in raw:
            p = d.get("properties", {})
            if s.hubspot_pipeline_id and p.get("pipeline") != s.hubspot_pipeline_id:
                continue
            stage = labels.get(p.get("dealstage"), _stage_name(p.get("dealstage") or "", p.get("dealstage") or "Unknown"))
            cid = company_of.get(d["id"])
            dur = p.get(s.hubspot_prop_duration)
            deals.append(
                {
                    "deal_id": str(d["id"]), "name": p.get("dealname") or "(no name)",
                    "company": names.get(cid, cid or "Unknown company"), "company_id": cid,
                    "amount": float(p.get("amount") or 0), "owner": owners.get(str(p.get("hubspot_owner_id") or ""), ""),
                    "stage": stage, "close_date": (p.get("closedate") or "")[:16].replace("T", " ") or "1970-01-01",
                    "tech": p.get(s.hubspot_prop_tech) or None, "region": p.get(s.hubspot_prop_region) or None,
                    "expected_start": (p.get(s.hubspot_prop_expected_start) or "")[:10] or None,
                    "duration_months": int(float(dur)) if dur not in (None, "") else None,
                }
            )  # fmt: skip
        return HubSpotData(deals=deals, stages=probs, source="hubspot")


def _stage_name(stage_id: str, label: str) -> str:
    key = f"{stage_id} {label}".lower().replace(" ", "")
    if "closedwon" in key:
        return "Closed Won"
    if "closedlost" in key:
        return "Closed Lost"
    return label


def get_client(settings: Settings):
    return HubSpotClient(settings) if settings.hubspot_token else SampleClient()
