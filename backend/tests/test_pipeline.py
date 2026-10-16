"""FR-07 to FR-11, FR-21: HubSpot pipeline, weighting, Closed Won conversion, no double counting."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app import models as M
from app.integrations.hubspot import HubSpotClient, HubSpotData
from app.services.hubspot_sync import run_sync, sync_banner

MONTHS = ["2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04"]
DEAL = {"deal_id": "TEST-1", "name": "Testco - Platform Build", "company": "Testco", "company_id": "900", "amount": 120000, "owner": "Dev Patel",
        "stage": "Negotiation/Review", "close_date": "2026-11-15 10:00", "tech": "PEGA", "region": "NA", "expected_start": "2026-11-01", "duration_months": 6}  # fmt: skip


class FakeClient:
    def __init__(self, deals):
        self.deals = deals

    def fetch(self):
        return HubSpotData(deals=self.deals, stages=[], source="test")


def base_deals(db):
    rows = db.scalars(select(M.Deal).order_by(M.Deal.sort)).all()
    return [{k: getattr(d, k) for k in ("deal_id", "name", "company", "company_id", "amount", "owner", "stage", "close_date", "tech", "region",
                                         "expected_start", "duration_months")} for d in rows]  # fmt: skip


def totals(client):
    return client.get("/api/forecast").json()["totals"]


def set_probability(as_user, stage="Negotiation/Review", p=0.5):
    adm = as_user("ADM")
    stages = adm.get("/api/admin/stages").json()
    for s in stages:
        if s["stage"] == stage:
            s["probability"] = p
    assert adm.put("/api/admin/stages", json=stages).status_code == 200


def test_fr08_weighted_example_exact(as_user, db, env):
    set_probability(as_user, p=0.5)
    cro = as_user("CRO")
    before = totals(cro)["weighted"]
    assert run_sync(db, env, client=FakeClient([*base_deals(db), DEAL]))["ok"]
    after = totals(cro)["weighted"]
    for m in MONTHS:  # $120,000 x 50% = $60,000 over 6 months = $10,000 a month, Nov to Apr, exact
        assert round(after[m] - before[m], 6) == 10000, m
    assert after["2026-10"] == before["2026-10"] and after["2027-05"] == before["2027-05"]
    line = next(x for x in cro.get("/api/forecast").json()["pipeline"] if x["deal_id"] == "TEST-1")
    assert line["probability"] == 0.5 and line["weighted"] == 60000 and line["months"] == {m: 10000 for m in MONTHS}


def test_fr09_fr11_closed_won_counts_once(as_user, db, env):
    set_probability(as_user, p=0.5)
    cro = as_user("CRO")
    run_sync(db, env, client=FakeClient([*base_deals(db), DEAL]))
    mid = totals(cro)
    deal_won = {**DEAL, "stage": "Closed Won", "close_date": "2026-10-01 08:00"}
    r = run_sync(db, env, client=FakeClient([*base_deals(db), deal_won]))
    assert r["ok"] and r["created_drafts"] == 1
    draft = next(x for x in cro.get("/api/forecast").json()["rows"] if x["deal_id"] == "TEST-1")
    assert draft["status"] == "Draft" and draft["customer"] == "Testco"
    after = totals(cro)
    for m in MONTHS:
        # weighted line gone, committed carries the full deal (120,000 / 6 = 20,000), so the deal counts once, never 30,000
        assert round(after["weighted"][m] - (mid["weighted"][m] - 10000), 6) == 0
        assert after["committed"][m] - mid["committed"][m] == 20000
        assert round(after["total"][m] - mid["total"][m], 6) == 10000  # 20,000 committed replaces 10,000 weighted
    pipeline = cro.get("/api/pipeline").json()
    assert "TEST-1" not in [x["deal_id"] for x in pipeline["lines"]]
    # owner confirms the draft: still counted once, now Active
    assert as_user("Patel").post(f"/api/projects/{draft['id']}/confirm-draft").status_code == 200
    again = totals(cro)
    assert again["committed"]["2026-12"] == after["committed"]["2026-12"] and again["weighted"]["2026-12"] == after["weighted"]["2026-12"]
    # a second sync never creates a second draft
    assert run_sync(db, env, client=FakeClient([*base_deals(db), deal_won]))["created_drafts"] == 0
    assert sum(1 for x in cro.get("/api/forecast").json()["rows"] if x["deal_id"] == "TEST-1") == 1


def test_no_deal_is_in_committed_and_weighted_at_once(as_user):
    f = as_user("CRO").get("/api/forecast").json()
    linked = {r["deal_id"] for r in f["rows"] if r["deal_id"]}
    weighted = {x["deal_id"] for x in f["pipeline"]}
    assert linked and not (linked & weighted)
    assert {"57018801551", "64360839985"} <= linked  # Granitepeak and Cedarfall were entered by owners already


def test_deal_links_to_one_row_only(as_user):
    cro = as_user("CRO")
    assert cro.post("/api/pipeline/deals/57018801551/link", json={"row_id": "R1004"}).status_code == 422
    assert cro.post("/api/pipeline/deals/57018801551/link", json={"row_id": None}).status_code == 200
    assert cro.post("/api/pipeline/deals/57018801551/link", json={"row_id": "R1007"}).status_code == 200


def test_fr10_closed_lost_removes_line_and_logs(as_user, db, env):
    deals = base_deals(db)
    victim = next(d for d in deals if d["stage"] == "Negotiation/Review")
    cro = as_user("CRO")
    assert victim["deal_id"] in [x["deal_id"] for x in cro.get("/api/pipeline").json()["lines"] if x["status"] == "ok"]
    deals = [{**d, "stage": "Closed Lost"} if d["deal_id"] == victim["deal_id"] else d for d in deals]
    assert run_sync(db, env, client=FakeClient(deals))["ok"]
    p = cro.get("/api/pipeline").json()
    assert victim["deal_id"] not in [x["deal_id"] for x in p["lines"]]
    assert any(e["kind"] == "closed_lost_removed" and e["deal_id"] == victim["deal_id"] for e in p["events"])


def test_deal_moving_below_forecast_stage_is_removed_and_logged(as_user, db, env):
    deals = base_deals(db)
    victim = next(d for d in deals if d["stage"] == "Negotiation/Review" and d["expected_start"])
    deals = [{**d, "stage": "Presentation"} if d["deal_id"] == victim["deal_id"] else d for d in deals]
    adm = as_user("ADM")
    stages = adm.get("/api/admin/stages").json()
    for s in stages:
        if s["stage"] == "Presentation":
            s["in_forecast"] = "No"
    adm.put("/api/admin/stages", json=stages)
    run_sync(db, env, client=FakeClient(deals))
    p = as_user("CRO").get("/api/pipeline").json()
    assert next(x for x in p["lines"] if x["deal_id"] == victim["deal_id"])["status"] == "below"
    assert any(e["kind"] == "below_stage" for e in p["events"])


def test_sync_failure_keeps_last_good_data_and_shows_banner(as_user, db, env):
    class Boom:
        def fetch(self):
            raise RuntimeError("HubSpot is down")

    cro = as_user("CRO")
    before = cro.get("/api/forecast").json()["totals"]
    r = run_sync(db, env, client=Boom())
    assert r["ok"] is False
    assert cro.get("/api/forecast").json()["totals"] == before  # last good data stays
    banner = cro.get("/api/meta").json()["sync"]
    assert banner["stale"] is True and "HubSpot" in banner["message"] and banner["since"]
    assert db.scalar(select(M.JobRun).where(M.JobRun.status == "failed"))
    run_sync(db, env, client=FakeClient(base_deals(db)))
    assert cro.get("/api/meta").json()["sync"]["stale"] is False


def test_stale_banner_by_age(db, env):
    from app.services import state as ST

    ST.set_setting(db, "synced_at", "2026-09-01T00:00:00")  # a month before the "as of" date
    db.commit()
    b = sync_banner(db, env)
    assert b["stale"] is True and b["since"] == "2026-09-01T00:00:00"


def test_fr21_owner_phasing_keeps_weighted_total(as_user):
    deal = "55403950381"  # Kestrel Phase 3, owner Avery Chen
    cro = as_user("CRO")
    line = next(x for x in cro.get("/api/pipeline").json()["lines"] if x["deal_id"] == deal)
    total = sum(line["months"].values())
    assert as_user("JM").put(f"/api/pipeline/deals/{deal}/phasing", json={"shares": {"2027-01": 1}}).status_code == 403
    r = as_user("AC").put(f"/api/pipeline/deals/{deal}/phasing", json={"shares": {"2027-01": 1, "2027-02": 3}})
    assert r.status_code == 200
    line2 = next(x for x in cro.get("/api/pipeline").json()["lines"] if x["deal_id"] == deal)
    assert round(sum(line2["months"].values()), 4) == round(total, 4)  # timing changes, the weighted total does not
    assert line2["amount"] == line["amount"] and line2["probability"] == line["probability"] and line2["has_override"]
    assert round(line2["months"]["2027-02"] / line2["months"]["2027-01"], 6) == 3


def test_stage_probabilities_admin_only_and_applied(as_user):
    assert as_user("CRO").put("/api/admin/stages", json=[]).status_code == 403
    cro = as_user("CRO")
    before = cro.get("/api/forecast").json()["totals"]["weighted"]["2026-12"]
    adm = as_user("ADM")
    stages = adm.get("/api/admin/stages").json()
    for s in stages:
        if s["stage"] == "Contracting":
            s["probability"] = 0.9
    assert adm.put("/api/admin/stages", json=stages).status_code == 200
    assert cro.get("/api/forecast").json()["totals"]["weighted"]["2026-12"] > before


def test_hubspot_client_is_read_only_and_maps_fields(env):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        p = request.url.path
        if p == "/crm/v3/pipelines/deals":
            return httpx.Response(200, json={"results": [{"id": "default", "stages": [
                {"id": "s1", "label": "Proposal/Price Quote", "metadata": {"probability": "0.4"}},
                {"id": "closedwon", "label": "Closed won", "metadata": {"probability": "1.0"}}]}]})
        if p == "/crm/v3/owners":
            return httpx.Response(200, json={"results": [{"id": 7, "firstName": "Dev", "lastName": "Patel"}]})
        if p == "/crm/v3/objects/deals":
            return httpx.Response(200, json={"results": [{"id": "55", "properties": {
                "dealname": "Acme - Build", "amount": "50000", "dealstage": "closedwon", "closedate": "2026-09-30T12:00:00Z", "hubspot_owner_id": "7",
                "pipeline": "default", "expected_start_date": "2026-11-01", "duration_months": "5", "practice": "PEGA"},
                "associations": {"companies": {"results": [{"id": "9"}]}}}]})
        if p == "/crm/v3/objects/companies/batch/read":
            return httpx.Response(200, json={"results": [{"id": "9", "properties": {"name": "Acme Corp"}}]})
        return httpx.Response(404)

    env.hubspot_token = "pat-test"
    data = HubSpotClient(env, transport=httpx.MockTransport(handler)).fetch()
    d = data.deals[0]
    assert (d["company"], d["owner"], d["stage"], d["amount"], d["duration_months"], d["expected_start"]) == ("Acme Corp", "Dev Patel", "Closed Won", 50000.0, 5, "2026-11-01")
    assert {s["stage"] for s in data.stages} == {"Proposal/Price Quote", "Closed Won"}
    assert {m for m, _ in calls} <= {"GET", "POST"} and all(p.endswith("batch/read") for m, p in calls if m == "POST")  # read-only
    env.hubspot_token = ""


def test_sync_requires_role(as_user):
    assert as_user("AC").post("/api/pipeline/sync").status_code == 403
    r = as_user("FIN").post("/api/pipeline/sync")
    assert r.status_code == 200 and r.json()["ok"] and r.json()["source"] == "sample"


@pytest.mark.parametrize("code", ["AC", "RES"])
def test_pipeline_visible_to_everyone(as_user, code):
    r = as_user(code).get("/api/pipeline")
    assert r.status_code == 200 and r.json()["lines"]
