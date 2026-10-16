"""Reconciliation of the Python port against the reference implementation (core.js) numbers."""

from __future__ import annotations

from collections import Counter

from app.domain import engine as E
from app.services import state as ST

COMMITTED = {"2026-10": 2_677_000, "2026-11": 2_813_000, "2026-12": 2_385_000, "2027-03": 2_780_000, "2027-04": 2_192_250}
WEIGHTED = {"2026-10": 68_833, "2026-11": 164_713, "2026-12": 234_940, "2027-03": 362_033, "2027-04": 453_977}
FINDINGS = {"DUPLICATE": 1, "DRAFT_OVERDUE": 1, "STALE": 7, "RUN_RATE": 9, "MISSING_FIELDS": 2, "LOST_DEAL_SPIKE": 1, "CLOSE_DATE_PAST": 6,
            "MISSING_PHASING": 2, "RENEWAL_OVERLAP": 2, "HOLIDAY": 3, "LOOKALIKE": 1, "NO_REASON": 2, "FY_END": 6}  # fmt: skip


def test_reconciles_to_reference_numbers(db, env):
    S = ST.load_state(db, env)
    c, w = E.monthly_committed(S), E.monthly_weighted(S)
    for m, v in COMMITTED.items():
        assert c[m] == v, m
    for m, v in WEIGHTED.items():
        assert round(w[m]) == v, m
    assert round(E.unphased_total(S)) == 645_512
    assert len(S.projects) == 112  # 111 + Brightharbor draft R1112 created on first sync
    assert S.project("R1112")["status"] == "Draft"


def test_findings_by_rule_match_reference(db, env):
    S = ST.load_state(db, env)
    F = E.run_checks(S, stamp=False)
    assert dict(Counter(f["rule"] for f in F)) == FINDINGS
    hol = {(f["owner"], tuple(f["rows"])) for f in F if f["rule"] == "HOLIDAY" and f["title"].startswith("December")}
    assert hol == {("MR", ("R1008", "R1019", "R1020", "R1045", "R1046", "R1085")), ("TB", ("R1009", "R1010", "R1022", "R1051"))}


def test_evidence_wording_and_owner_routing(db, env):
    S = ST.load_state(db, env)
    F = {f["id"]: f for f in E.run_checks(S, stamp=False)}
    dup = F["DUPLICATE:R1009+R1010"]
    assert dup["evidence"][0] == 'Two rows for Lakemoor Pharma have near-identical names: "Clinical Workflow" and "Clinical Workflows" (name match 100%).'
    assert dup["owner"] == "TB" and dup["fix"].startswith("Open both rows and merge them into one.")
    assert F["DRAFT_OVERDUE:R1112"]["owner"] == "Lowe"
    assert F["RUN_RATE:R1002"]["evidence"][1].startswith("No reason was recorded for this change (#2243, Jordan Malik")
    assert F["RUN_RATE:R1001"]["explained"] is True and F["RUN_RATE:R1001"]["severity"] == "low"
    assert F["STALE:R1011"]["title"] == "Not updated in 65 days: Bluewater Utilities"


def test_value_parsing_rules():
    assert E.parse_value("=90000-55000")["ok"] is False
    assert E.parse_value("abc")["ok"] is False
    assert E.parse_value("-5") == {"ok": False, "error": "Revenue cannot be negative."}
    assert E.parse_value("$1,250.555") == {"ok": True, "value": 1250.56}
    assert E.parse_value("") == {"ok": True, "value": None}
    assert E.parse_value("1e5")["ok"] is False
    assert E.parse_value(" 42000 ")["value"] == 42000


def test_weighted_example_fr08_pure():
    first = E.spread_even(120000, "2026-11-01", 6)
    assert first == {"2026-11": 20000, "2026-12": 20000, "2027-01": 20000, "2027-02": 20000, "2027-03": 20000, "2027-04": 20000}
