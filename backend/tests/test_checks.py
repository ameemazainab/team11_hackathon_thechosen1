"""FR-17, FR-18, FR-20, FR-24: quality checks never edit data; people accept or dismiss with a reason."""

from __future__ import annotations

import httpx
from sqlalchemy import select

from app import models as M
from app.config import get_settings
from app.jobs import nightly_checks  # noqa: F401  (module must import)
from app.services import ai
from app.services import state as ST


def dump(db):
    rows = db.execute(select(M.Project.id, M.Project.customer, M.Project.project, M.Project.status, M.Project.last_updated, M.Project.last_updated_by,
                             M.Project.client_partner, M.Project.deal_id).order_by(M.Project.id)).all()
    rev = db.execute(select(M.Revenue.project_id, M.Revenue.month, M.Revenue.amount).order_by(M.Revenue.project_id, M.Revenue.month)).all()
    log = db.scalar(select(M.ChangeLog.seq).order_by(M.ChangeLog.seq.desc()))
    deals = db.execute(select(M.Deal.deal_id, M.Deal.amount, M.Deal.stage)).all()
    return [tuple(r) for r in rows], [tuple(r) for r in rev], log, [tuple(r) for r in deals]


def test_checks_never_change_project_data(as_user, db):
    before = dump(db)
    cro = as_user("CRO")
    assert cro.post("/api/checks/run").status_code == 200
    fid = cro.get("/api/checks").json()["findings"][0]["id"]
    assert cro.post(f"/api/checks/{fid}/resolve", json={"status": "accepted", "reason": "Will fix"}).status_code == 200
    from app.api.checks import run_and_log

    run_and_log(db, get_settings(), "Nightly run", job="nightly_checks")
    db.expire_all()
    assert dump(db) == before  # not a single project, month, deal or audit entry changed


def test_every_finding_has_rule_evidence_fix_and_owner(as_user):
    r = as_user("CRO").get("/api/checks").json()
    assert len(r["findings"]) == 43 and r["summary"]["open"] == 43
    for f in r["findings"]:
        assert f["rule"] and f["evidence"] and f["fix"] and f["owner"] and f["owner_name"] and f["severity"] in ("high", "medium", "low")
    dup = next(f for f in r["findings"] if f["rule"] == "DUPLICATE")
    assert [x["id"] for x in dup["rows"]] == ["R1009", "R1010"] and dup["owner_name"] == "Taylor Brooks"


def test_findings_routed_to_owner(as_user):
    tb = as_user("TB").get("/api/checks", params={"mine": True}).json()["findings"]
    assert tb and all(f["owner"] == "TB" for f in tb)
    assert {"DUPLICATE", "HOLIDAY"} <= {f["rule"] for f in tb}
    cro_mine = as_user("CRO").get("/api/checks", params={"mine": True}).json()["findings"]
    assert all(f["owner"] in ("CRO",) for f in cro_mine)


def test_accept_dismiss_need_reason_and_are_persisted_by_stable_id(as_user):
    tb, cro = as_user("TB"), as_user("CRO")
    f = next(x for x in tb.get("/api/checks", params={"mine": True}).json()["findings"] if x["rule"] == "DUPLICATE")
    assert tb.post(f"/api/checks/{f['id']}/resolve", json={"status": "dismissed", "reason": "  "}).status_code == 422
    assert tb.post(f"/api/checks/{f['id']}/resolve", json={"status": "bogus", "reason": "x"}).status_code == 422
    r = tb.post(f"/api/checks/{f['id']}/resolve", json={"status": "dismissed", "reason": "Two different workstreams"})
    assert r.status_code == 200 and r.json()["status"] == "dismissed" and r.json()["resolution"]["by_name"] == "Taylor Brooks"
    cro.post("/api/checks/run")  # a new run keeps the decision: same finding id
    again = next(x for x in cro.get("/api/checks").json()["findings"] if x["id"] == f["id"])
    assert again["status"] == "dismissed" and again["resolution"]["reason"] == "Two different workstreams"
    assert cro.get("/api/checks").json()["summary"]["dismissed"] == 1
    assert tb.post(f"/api/checks/{f['id']}/resolve", json={"status": "open"}).status_code == 200  # reopen


def test_only_owner_or_leadership_can_resolve(as_user):
    f = next(x for x in as_user("CRO").get("/api/checks").json()["findings"] if x["rule"] == "DUPLICATE")
    r = as_user("AC").post(f"/api/checks/{f['id']}/resolve", json={"status": "accepted", "reason": "ok"})
    assert r.status_code == 403 and "Taylor Brooks" in r.json()["detail"]["message"]
    assert as_user("CRO").post(f"/api/checks/{f['id']}/resolve", json={"status": "accepted", "reason": "ok"}).status_code == 200


def test_holiday_ack_clears_finding_when_owner_records_reason(as_user):
    tb = as_user("TB")
    before = [f for f in as_user("CRO").get("/api/checks").json()["findings"] if f["rule"] == "HOLIDAY" and f["owner"] == "TB"]
    assert before
    r = tb.post("/api/forecast/changes", json={"reason": "HOLIDAY", "note": "Christmas week",
                                                "changes": [{"row_id": "R1009", "month": "2026-12", "value": "21000"}]})  # fmt: skip
    assert r.status_code == 200
    tb_dec = [f for f in as_user("CRO").get("/api/checks").json()["findings"] if f["rule"] == "HOLIDAY" and f["owner"] == "TB"]
    assert "R1009" not in [x["id"] for x in tb_dec[0]["rows"]]


def test_ask_about_forecast_cites_rows_and_audit_entries(as_user, db):
    r = as_user("CRO").post("/api/ask", json={"question": "Why did December drop?"})
    body = r.json()
    assert r.status_code == 200 and body["used_ai"] is False and body["title"].startswith("Why December 2026")
    text = " ".join(body["answer"])
    assert "Kestrel Life & Annuity" in text and "#2243" in text
    assert any(c["row_id"] == "R1001" and c["entry_id"] == "#2228" for c in body["cites"])
    assert all(c["label"] for c in body["cites"])
    assert db.scalar(select(M.AiLog).where(M.AiLog.kind == "ask"))  # logged
    cust = as_user("CRO").post("/api/ask", json={"question": "What is going on with Kestrel?"}).json()
    assert cust["title"] == "Kestrel Life & Annuity" and cust["cites"]
    who = as_user("CRO").post("/api/ask", json={"question": "Who has not updated their rows?"}).json()
    assert "Taylor Brooks" in " ".join(who["answer"])
    assert as_user("CRO").post("/api/ask", json={"question": "  "}).status_code == 422


def test_ask_with_claude_logs_prompt_output_and_respects_cost_ceiling(db, env):
    S = ST.load_state(db, env)
    user = {"code": "CRO", "name": "Demo CRO", "roles": ["Sales leadership"]}
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["body"] = request.read().decode()
        sent["key"] = request.headers["x-api-key"]
        return httpx.Response(200, json={"content": [{"type": "text", "text": "December is lower mainly because of R1001 (#2228)."}],
                                         "usage": {"input_tokens": 1000, "output_tokens": 100}})  # fmt: skip

    env.anthropic_api_key = "sk-test"
    try:
        r = ai.ask(db, env, S, user, "Why did December drop?", transport=httpx.MockTransport(handler))
        assert r["used_ai"] is True and r["answer"] == ["December is lower mainly because of R1001 (#2228)."] and r["cites"]
        assert "Kestrel" in sent["body"] and "Policy Admin" in sent["body"] and sent["key"] == "sk-test"
        assert len(sent["body"]) < 6000  # only the summarised facts go out, never the whole data set
        log = db.scalars(select(M.AiLog).where(M.AiLog.used_ai.is_(True))).one()
        assert log.prompt.startswith("Question: Why did December drop?") and "R1001" in log.output and log.cost_usd > 0
        env.ai_monthly_cost_ceiling_usd = 0.0001
        r2 = ai.ask(db, env, S, user, "Why did December drop?", transport=httpx.MockTransport(handler))
        assert r2["used_ai"] is False and "limit" in r2["notice"]
        env.ai_monthly_cost_ceiling_usd = 250
        r3 = ai.ask(db, env, S, user, "Why did December drop?", transport=httpx.MockTransport(lambda req: httpx.Response(500)))
        assert r3["used_ai"] is False and r3["notice"] and r3["answer"]
    finally:
        env.anthropic_api_key = ""


def test_fr20_attestation_by_owner_and_status(as_user):
    ac = as_user("AC")
    rv = ac.get("/api/review").json()
    mine = [r["id"] for r in rv["mine"]]
    assert mine and all(r["attested"] is False for r in rv["mine"])
    r = ac.post("/api/review/attest", json={"row_ids": mine[:2]})
    assert r.json()["attested"] == 2
    assert ac.post("/api/review/attest", json={"row_ids": ["R1002"]}).status_code == 403  # not Avery's row
    rv2 = ac.get("/api/review").json()
    assert sum(1 for x in rv2["mine"] if x["attested"]) == 2
    row = next(x for x in rv2["status"] if x["owner"] == "AC")
    assert row["attested"] == 2 and row["total"] >= 2
    assert rv2["overall"]["attested"] == 2 and rv2["window"] == ["2026-11", "2026-12", "2027-01"]
    assert as_user("CRO").get("/api/review").json()["overall"]["attested"] == 2
    detail = ac.get(f"/api/projects/{mine[0]}").json()
    assert detail["attested"]["by"] == "Avery Chen"


def test_overview_has_headline_numbers(as_user):
    o = as_user("AC").get("/api/overview").json()
    assert o["kpis"]["committed"] + o["kpis"]["weighted"] == o["kpis"]["total"]
    assert o["checks"]["open"] == 43 and o["review"]["my_rows"] >= 1 and o["series"][0]["month"] == "2026-10"
    drafts = as_user("Lowe").get("/api/overview").json()["drafts"]
    assert drafts and drafts[0]["id"] == "R1112"
