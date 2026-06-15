"""The host loads ONLY blessed skills. Uses the real repo skills/ + registry/ for the happy
path; a tmp candidate skill for the rejection path (status checked before any import)."""

from __future__ import annotations

from pathlib import Path

import pytest

from skill_host.errors import SkillNotBlessedError, SkillNotFoundError
from skill_host.loader import load_blessed_skill

REPO = Path(__file__).resolve().parents[3]
SKILLS, REGISTRY = REPO / "skills", REPO / "registry"


def test_loads_blessed_skill():
    loaded = load_blessed_skill("factor_correlation", skills_dir=SKILLS, registry_dir=REGISTRY)
    assert loaded.status == "blessed"
    assert loaded.server_name == "factor"
    assert "mcp__factor__compute_correlation" in loaded.allowed_tools
    assert loaded.spec.required_scopes == ["prices:read"]


def test_unknown_skill_raises_not_found():
    with pytest.raises(SkillNotFoundError):
        load_blessed_skill("does_not_exist", skills_dir=SKILLS, registry_dir=REGISTRY)


def test_candidate_skill_is_refused(tmp_path: Path):
    skills = tmp_path / "skills"
    registry = tmp_path / "registry"
    (skills / "tmpskill").mkdir(parents=True)
    registry.mkdir()
    (skills / "tmpskill" / "SKILL.md").write_text(
        "---\nname: tmpskill\nversion: 0.1.0\nblast_radius: low\n"
        "allowed_mcp_servers: []\nrequired_scopes: []\n---\nbody\n")
    (registry / "tmpskill.yaml").write_text(
        "name: tmpskill\nversion: 0.1.0\nblast_radius: low\n"
        "allowed_mcp_servers: []\nrequired_scopes: []\nstatus: candidate\n")
    with pytest.raises(SkillNotBlessedError):
        load_blessed_skill("tmpskill", skills_dir=skills, registry_dir=registry)
