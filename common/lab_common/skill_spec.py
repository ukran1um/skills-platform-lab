"""Parse a skill's SKILL.md (YAML frontmatter + markdown body) into a SkillSpec."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from lab_common.models import SkillSpec

# Line-boundary-aware frontmatter match: opening '---' line, YAML block, closing
# '---' line, then the body. Anchored at start-of-file and matched on whole lines
# so a '---' inside a YAML value or the markdown body never confuses the split.
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)", re.DOTALL)


def load_skill(skill_dir: str | Path) -> SkillSpec:
    skill_dir = Path(skill_dir)
    text = (skill_dir / "SKILL.md").read_text()
    match = _FRONTMATTER.match(text)
    if not match:
        raise ValueError(f"{skill_dir}/SKILL.md has no YAML frontmatter")
    meta = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).lstrip("\n")
    for key in ("name", "version"):
        if key not in meta:
            raise ValueError(f"{skill_dir}/SKILL.md: required frontmatter field '{key}' missing")
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
