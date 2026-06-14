from lab_common.governance.frontmatter import check_frontmatter
from lab_common.models import SkillSpec


def _spec(**over) -> SkillSpec:
    base = dict(
        name="x", version="0.1.0", owner="egor", blast_radius="low",
        allowed_mcp_servers=["data_mcp"], required_scopes=["prices:read"],
        golden_set="evals/golden.yaml", threshold=0.8, system_prompt="body",
    )
    base.update(over)
    return SkillSpec(**base)  # type: ignore[arg-type]


def test_valid_frontmatter_has_no_errors():
    assert check_frontmatter(_spec()) == []


def test_bad_blast_radius_is_rejected():
    errs = check_frontmatter(_spec(blast_radius="catastrophic"))
    assert any("blast_radius" in e for e in errs)


def test_threshold_out_of_range_is_rejected():
    assert any("threshold" in e for e in check_frontmatter(_spec(threshold=1.5)))


def test_empty_owner_is_rejected():
    assert any("owner" in e for e in check_frontmatter(_spec(owner="")))
