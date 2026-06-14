from pathlib import Path

import yaml

from lab_common.governance.reconcile import _agreement_errors, reconcile_all, reconcile_skill
from lab_common.models import SkillSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR = REPO_ROOT / "skills" / "factor_correlation"
FACTOR_REG = REPO_ROOT / "registry" / "factor_correlation.yaml"


def test_agreement_ignores_list_order():
    spec = SkillSpec("x", "0.1.0", "e", "low", ["data_mcp", "audit_mcp"],
                     ["prices:read", "kb:read"], "g", 0.8, "b")
    record = {"name": "x", "version": "0.1.0", "blast_radius": "low",
              "allowed_mcp_servers": ["audit_mcp", "data_mcp"],
              "required_scopes": ["kb:read", "prices:read"]}
    assert _agreement_errors(spec, record) == []  # reordered lists still agree


def test_unknown_status_is_rejected(tmp_path: Path):
    reg = tmp_path / "factor_correlation.yaml"
    reg.write_text(yaml.safe_dump({
        "name": "factor_correlation", "version": "0.1.0", "owner": "egor",
        "blast_radius": "low", "allowed_mcp_servers": ["data_mcp"],
        "required_scopes": ["prices:read"], "status": "blesed",  # typo
    }))
    rec = reconcile_skill(FACTOR, reg, source_commit="x")
    assert rec["status"] == "candidate"
    assert any("status" in e for e in rec["agreement_errors"])


def test_agreeing_skill_is_blessed():
    rec = reconcile_skill(FACTOR, FACTOR_REG, source_commit="abc123")
    assert rec["status"] == "blessed"
    assert rec["agreement_errors"] == []
    assert rec["source_commit"] == "abc123"


def test_disagreeing_registry_downgrades_to_candidate(tmp_path: Path):
    bad = tmp_path / "factor_correlation.yaml"
    bad.write_text(yaml.safe_dump({
        "name": "factor_correlation", "version": "0.1.0", "owner": "egor",
        "blast_radius": "high",
        "allowed_mcp_servers": ["data_mcp"], "required_scopes": ["prices:read"],
        "status": "blessed",
    }))
    rec = reconcile_skill(FACTOR, bad, source_commit="x")
    assert rec["status"] == "candidate"
    assert any("blast_radius" in e for e in rec["agreement_errors"])


def test_reconcile_all_emits_records():
    report = reconcile_all(REPO_ROOT / "skills", REPO_ROOT / "registry", "sha")
    names = {r["name"] for r in report["skills"]}
    assert "factor_correlation" in names
