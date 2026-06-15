"""Load a BLESSED skill for execution: reconcile its declared state, refuse anything not
blessed, then import its Agent-SDK tool surface. The host runs only what governance blessed."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lab_common.governance.reconcile import reconcile_skill
from lab_common.models import SkillSpec
from lab_common.skill_spec import load_skill

from skill_host.errors import SkillNotBlessedError, SkillNotFoundError


@dataclass
class LoadedSkill:
    spec: SkillSpec
    server: Any
    allowed_tools: list[str]
    server_name: str
    status: str


def load_blessed_skill(
    skill_name: str, *, skills_dir: str | Path, registry_dir: str | Path,
    source_commit: str = "local",
) -> LoadedSkill:
    skills_dir, registry_dir = Path(skills_dir), Path(registry_dir)
    skill_dir = skills_dir / skill_name
    registry_path = registry_dir / f"{skill_name}.yaml"
    if not (skill_dir / "SKILL.md").exists() or not registry_path.exists():
        raise SkillNotFoundError(f"no skill named {skill_name!r}")
    record = reconcile_skill(skill_dir, registry_path, source_commit)
    if record["status"] != "blessed":
        raise SkillNotBlessedError(
            f"{skill_name} is {record['status']} "
            f"(agreement errors: {record['agreement_errors']})")
    spec = load_skill(skill_dir)
    mod = importlib.import_module(f"{spec.name}.agent_tools")
    return LoadedSkill(
        spec=spec, server=mod.SERVER, allowed_tools=list(mod.ALLOWED_TOOLS),
        server_name=getattr(mod, "SERVER_NAME", "factor"), status=record["status"])
