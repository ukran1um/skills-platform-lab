from pathlib import Path

from lab_common.governance.cli import check_skill

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR = REPO_ROOT / "skills" / "factor_correlation"
ROGUE = Path(__file__).resolve().parent / "fixtures" / "rogue_skill"
ENTITLEMENTS = REPO_ROOT / "registry" / "entitlements.yaml"


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
