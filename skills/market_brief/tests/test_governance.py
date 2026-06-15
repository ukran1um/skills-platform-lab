"""market_brief passes the governance gates and reconciles to blessed."""

from __future__ import annotations

from pathlib import Path

from lab_common.governance.reconcile import reconcile_skill

REPO = Path(__file__).resolve().parents[3]


def test_market_brief_reconciles_to_blessed():
    rec = reconcile_skill(REPO / "skills" / "market_brief",
                          REPO / "registry" / "market_brief.yaml", "local")
    assert rec["status"] == "blessed", rec["agreement_errors"]
    assert sorted(rec["required_scopes"]) == ["fundamentals:read", "prices:read"]
