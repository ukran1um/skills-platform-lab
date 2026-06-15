"""The host orchestration, with the agent run replaced by a fake runner so we can assert the
governance + context-injection behavior offline (no SDK, no key)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from lab_common.models import RunResult, ToolCall
from skill_host.errors import EntitlementError, SkillNotBlessedError
from skill_host.host import HostConfig, run_skill_request

REPO = Path(__file__).resolve().parents[3]
SECRET = "skill-host-orchestration-secret-32!"


def _config(**overrides: Any) -> HostConfig:
    base: dict[str, Any] = dict(
        skills_dir=REPO / "skills", registry_dir=REPO / "registry",
        entitlements_path=REPO / "registry" / "entitlements.yaml",
        data_mcp_base_url="http://data-mcp.test/mcp", secret=SECRET)
    base.update(overrides)
    return HostConfig(**base)


def test_runs_blessed_skill_in_platform_context():
    seen = {}

    async def fake_runner(loaded, message):
        from lab_common.exec_context import platform_context
        seen["ctx"] = platform_context()
        seen["message"] = message
        return RunResult(final_text="done",
                         trajectory=[ToolCall("compute_correlation", {"x": 1}, "{}")])

    resp = asyncio.run(run_skill_request(
        "factor_correlation", "How correlated were AAPL and MSFT?", "egor",
        config=_config(), runner=fake_runner))

    # The host set the platform context for the skill's tools (data_mcp is declared).
    assert seen["ctx"] is not None and seen["ctx"][0] == "http://data-mcp.test/mcp"
    assert seen["message"].startswith("How correlated")
    assert resp.scopes == ["prices:read"]
    assert resp.final_text == "done"
    assert resp.trajectory[0]["name"] == "compute_correlation"
    # Context is torn down after the run.
    from lab_common.exec_context import platform_context
    assert platform_context() is None


def test_not_blessed_propagates(tmp_path: Path):
    skills, registry = tmp_path / "skills", tmp_path / "registry"
    (skills / "tmpskill").mkdir(parents=True)
    registry.mkdir()
    (skills / "tmpskill" / "SKILL.md").write_text(
        "---\nname: tmpskill\nversion: 0.1.0\nblast_radius: low\n"
        "allowed_mcp_servers: []\nrequired_scopes: []\n---\nbody\n")
    (registry / "tmpskill.yaml").write_text(
        "name: tmpskill\nversion: 0.1.0\nblast_radius: low\n"
        "allowed_mcp_servers: []\nrequired_scopes: []\nstatus: candidate\n")

    async def fake_runner(loaded, message):  # never reached
        raise AssertionError("runner should not be called for an unblessed skill")

    with pytest.raises(SkillNotBlessedError):
        asyncio.run(run_skill_request("tmpskill", "hi", "egor",
                    config=_config(skills_dir=skills, registry_dir=registry),
                    runner=fake_runner))


def test_unentitled_user_propagates():
    async def fake_runner(loaded, message):  # never reached
        raise AssertionError("runner should not be called when entitlement fails")

    with pytest.raises(EntitlementError):
        asyncio.run(run_skill_request("factor_correlation", "hi", "nobody",
                    config=_config(), runner=fake_runner))
