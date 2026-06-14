from pathlib import Path

from lab_common.governance.cli import check_all_results, check_skill

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR = REPO_ROOT / "skills" / "factor_correlation"
ROGUE = Path(__file__).resolve().parent / "fixtures" / "rogue_skill"
ENTITLEMENTS = REPO_ROOT / "registry" / "entitlements.yaml"

_VALID_SKILL_MD = (
    "---\nname: good\nversion: 0.1.0\nowner: egor\nblast_radius: low\n"
    "allowed_mcp_servers: [data_mcp]\nrequired_scopes: [prices:read]\n"
    "eval:\n  golden_set: evals/golden.yaml\n  threshold: 0.8\n---\n# Good\n"
)


def test_factor_passes_all_gates():
    results = check_skill(FACTOR, ENTITLEMENTS)
    assert results["frontmatter"] == []
    assert results["blast_radius"] == []
    assert results["scopes"] == []


def test_rogue_passes_frontmatter_and_scopes_but_fails_blast_radius():
    results = check_skill(ROGUE, ENTITLEMENTS)
    assert results["frontmatter"] == []
    assert results["scopes"] == []
    assert any("notify_mcp" in e for e in results["blast_radius"])


def test_check_all_reports_malformed_skill_without_crashing(tmp_path: Path):
    good = tmp_path / "good"
    good.mkdir()
    (good / "SKILL.md").write_text(_VALID_SKILL_MD)
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "SKILL.md").write_text("no frontmatter here")  # load_skill will raise
    results = check_all_results(tmp_path, ENTITLEMENTS)  # must NOT raise
    by_name = {name: (res, err) for name, res, err in results}
    assert set(by_name) == {"good", "bad"}
    assert by_name["good"][1] is None  # good skill: no error
    assert by_name["bad"][1] is not None  # bad skill: error captured, not raised
