"""Reconcile git-declared state (SKILL.md frontmatter + registry/<skill>.yaml) into a
deployed-state record. A skill is `blessed` only when the two agree."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from lab_common.models import SkillSpec
from lab_common.skill_spec import load_skill

_AGREE_FIELDS = ("name", "version", "blast_radius", "allowed_mcp_servers", "required_scopes")


def _agreement_errors(spec: SkillSpec, record: dict[str, Any]) -> list[str]:
    errors = []
    for field in _AGREE_FIELDS:
        sv = getattr(spec, field)
        rv = record.get(field)
        sv_n = list(sv) if isinstance(sv, list) else sv
        rv_n = list(rv) if isinstance(rv, list) else rv
        if sv_n != rv_n:
            errors.append(f"{field}: SKILL.md={sv_n!r} != registry={rv_n!r}")
    return errors


def reconcile_skill(skill_dir: str | Path, registry_path: str | Path, source_commit: str) -> dict[str, Any]:
    spec = load_skill(skill_dir)
    record = yaml.safe_load(Path(registry_path).read_text()) or {}
    errors = _agreement_errors(spec, record)
    declared = record.get("status", "candidate")
    status = declared if not errors else "candidate"
    return {
        "name": spec.name, "version": spec.version, "owner": spec.owner,
        "blast_radius": spec.blast_radius, "allowed_mcp_servers": spec.allowed_mcp_servers,
        "required_scopes": spec.required_scopes, "source_commit": source_commit,
        "status": status, "agreement_errors": errors,
    }


def reconcile_all(skills_dir: str | Path, registry_dir: str | Path, source_commit: str) -> dict[str, Any]:
    skills_dir, registry_dir = Path(skills_dir), Path(registry_dir)
    records: list[dict[str, Any]] = []
    for skill_path in sorted(p for p in skills_dir.iterdir() if (p / "SKILL.md").exists()):
        reg = registry_dir / f"{skill_path.name}.yaml"
        if not reg.exists():
            records.append({"name": skill_path.name, "status": "candidate",
                            "agreement_errors": [f"no registry record at {reg}"]})
        else:
            records.append(reconcile_skill(skill_path, reg, source_commit))
    return {"skills": records}
