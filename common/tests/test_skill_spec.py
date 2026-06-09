from pathlib import Path

import pytest

from lab_common.skill_spec import load_skill

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR_SKILL = REPO_ROOT / "skills" / "factor_correlation"

SAMPLE = """---
name: demo
version: 1.2.3
owner: tester
blast_radius: medium
allowed_mcp_servers: [data_mcp, research_mcp]
required_scopes: [prices:read]
eval:
  golden_set: evals/golden.yaml
  threshold: 0.7
---

# Demo

System prompt body here.
"""


def test_load_real_factor_skill():
    spec = load_skill(FACTOR_SKILL)
    assert spec.name == "factor_correlation"
    assert spec.blast_radius == "low"
    assert spec.allowed_mcp_servers == ["data_mcp"]
    assert spec.required_scopes == ["prices:read"]
    assert spec.threshold == 0.8
    assert spec.golden_set == "evals/golden.yaml"
    assert "Factor Correlation" in spec.system_prompt  # body captured


def test_load_from_sample(tmp_path: Path):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(SAMPLE)
    spec = load_skill(skill_dir)
    assert spec.version == "1.2.3"
    assert spec.allowed_mcp_servers == ["data_mcp", "research_mcp"]
    assert spec.threshold == 0.7
    assert spec.system_prompt.strip().startswith("# Demo")


def test_missing_frontmatter_raises(tmp_path: Path):
    skill_dir = tmp_path / "broken"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("no frontmatter here")
    with pytest.raises(ValueError, match="frontmatter"):
        load_skill(skill_dir)


def test_inline_dashes_in_value_not_truncated(tmp_path: Path):
    # A '---' inside a YAML value must not be treated as a fence boundary.
    skill_dir = tmp_path / "dashes"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: dash\n"
        "version: 0.1.0\n"
        "description: compute foo --- bar baz\n"
        "---\n\n"
        "# Body\n"
        "Some text with a --- horizontal rule.\n"
    )
    spec = load_skill(skill_dir)
    assert spec.name == "dash"
    assert "# Body" in spec.system_prompt
    assert "horizontal rule" in spec.system_prompt


def test_missing_required_key_raises_clear_error(tmp_path: Path):
    skill_dir = tmp_path / "noname"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nversion: 0.1.0\n---\n\n# Body\n")
    with pytest.raises(ValueError, match="required frontmatter field 'name'"):
        load_skill(skill_dir)
