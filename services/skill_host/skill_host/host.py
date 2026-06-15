"""The skill host: run a BLESSED skill in PLATFORM context. Load (governance gate) -> mint a
scoped capability token -> inject the platform context (the skill's tools then route through
the Data MCP with that token) -> run the Agent-SDK loop -> return final text + trajectory.

The agent run is injectable (`runner`) so the host's governance logic is testable offline
without the SDK. A process-wide lock serializes runs because the platform context is global
env (see lab_common.exec_context)."""

from __future__ import annotations

import asyncio
import os
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from lab_common.exec_context import use_platform_context
from lab_common.models import RunResult

from skill_host.loader import LoadedSkill, load_blessed_skill
from skill_host.scoping import mint_scoped_token

DEFAULT_DATA_MCP_BASE_URL = "http://127.0.0.1:8081/mcp"
SECRET_ENV = "CAPABILITY_SECRET"
DEFAULT_SECRET = "dev-secret-not-for-production-pad32"  # >=32 bytes; matches the Data MCP default

Runner = Callable[[LoadedSkill, str], Awaitable[RunResult]]


async def _default_runner(loaded: LoadedSkill, message: str) -> RunResult:
    from lab_common.agent_runner import run_skill
    return await run_skill(loaded.spec, message, server=loaded.server,
                           allowed_tools=loaded.allowed_tools, server_name=loaded.server_name)


@dataclass
class HostConfig:
    skills_dir: Path
    registry_dir: Path
    entitlements_path: Path
    data_mcp_base_url: str = DEFAULT_DATA_MCP_BASE_URL
    secret: str = field(default_factory=lambda: os.environ.get(SECRET_ENV, DEFAULT_SECRET))


@dataclass
class RunResponse:
    skill: str
    status: str
    user: str
    scopes: list[str]
    final_text: str | None
    trajectory: list[dict]


_run_lock = asyncio.Lock()


async def run_skill_request(
    skill: str, message: str, user: str, *, config: HostConfig,
    runner: Runner = _default_runner,
) -> RunResponse:
    loaded = load_blessed_skill(skill, skills_dir=config.skills_dir,
                                registry_dir=config.registry_dir)
    token, scopes = mint_scoped_token(loaded.spec, user,
                                      entitlements_path=config.entitlements_path,
                                      secret=config.secret)
    uses_mcp = "data_mcp" in loaded.spec.allowed_mcp_servers
    ctx = use_platform_context(config.data_mcp_base_url, token) if uses_mcp else nullcontext()
    async with _run_lock:  # platform context is process-global env; serialize runs
        with ctx:
            result = await runner(loaded, message)
    return RunResponse(
        skill=loaded.spec.name, status=loaded.status, user=user, scopes=scopes,
        final_text=result.final_text,
        trajectory=[{"name": c.name, "input": c.input, "result": c.result}
                    for c in result.trajectory])
