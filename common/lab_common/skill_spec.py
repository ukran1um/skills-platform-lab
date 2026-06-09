"""Parse a skill's SKILL.md (YAML frontmatter + markdown body) into a SkillSpec."""

from __future__ import annotations

from pathlib import Path

import yaml

from lab_common.models import SkillSpec


def load_skill(skill_dir: str | Path) -> SkillSpec:
    skill_dir = Path(skill_dir)
    text = (skill_dir / "SKILL.md").read_text()
    if not text.startswith("---"):
        raise ValueError(f"{skill_dir}/SKILL.md has no YAML frontmatter")
    # Split on the first two '---' fences.
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{skill_dir}/SKILL.md frontmatter is malformed")
    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].lstrip("\n")
    eval_cfg = meta.get("eval", {}) or {}
    return SkillSpec(
        name=meta["name"],
        version=str(meta["version"]),
        owner=meta.get("owner", ""),
        blast_radius=meta.get("blast_radius", ""),
        allowed_mcp_servers=list(meta.get("allowed_mcp_servers", [])),
        required_scopes=list(meta.get("required_scopes", [])),
        golden_set=eval_cfg.get("golden_set", ""),
        threshold=float(eval_cfg.get("threshold", 0.0)),
        system_prompt=body,
    )
