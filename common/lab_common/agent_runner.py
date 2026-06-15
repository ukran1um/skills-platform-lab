"""Run a skill through the Claude Agent SDK (the real runtime) and capture its trace.

`build_runresult` is pure (filter harness tools, strip mcp prefix, match results) and
unit-tested offline. `run_skill` is the async live adapter that spawns the SDK headless,
isolated from local config. `make_sdk_runner` returns a sync `runner(input)->RunResult`."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Callable

from lab_common.models import RunResult, SkillSpec, ToolCall

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TURNS = 8


def _text_of(content: Any) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return None


def build_runresult(
    tool_uses: list[tuple[str, str, dict]],
    tool_results: dict[str, Any],
    final_text: str | None,
) -> RunResult:
    """tool_uses: [(id, name, input)]; tool_results: {id: content}. Drops harness-internal
    tools (anything not mcp__*), strips the mcp__<server>__ prefix, matches results by id."""
    trajectory: list[ToolCall] = []
    for tool_id, name, inp in tool_uses:
        if not name.startswith("mcp__"):
            continue  # harness-internal (e.g. ToolSearch) — not part of the skill's trace
        short = name.split("__")[-1]
        trajectory.append(ToolCall(name=short, input=dict(inp), result=_text_of(tool_results.get(tool_id))))
    return RunResult(final_text=final_text, trajectory=trajectory)


async def run_skill(
    spec: SkillSpec,
    user_input: str,
    *,
    server: Any,
    allowed_tools: list[str],
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    server_name: str = "factor",
) -> RunResult:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
        query,
    )

    opts = ClaudeAgentOptions(
        mcp_servers={server_name: server},
        allowed_tools=allowed_tools,
        system_prompt=spec.system_prompt,      # str => REPLACES the default Claude Code prompt
        model=model,
        permission_mode="bypassPermissions",
        setting_sources=[],                     # load NO local ~/.claude / project / local config
        max_turns=max_turns,
        env={"ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"]},
    )
    tool_uses: list[tuple[str, str, dict]] = []
    tool_results: dict[str, Any] = {}
    final_text: str | None = None
    async for msg in query(prompt=user_input, options=opts):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, ToolUseBlock):
                    tool_uses.append((b.id, b.name, b.input))
                elif isinstance(b, TextBlock):
                    final_text = b.text
        elif isinstance(msg, UserMessage):
            content = msg.content if isinstance(msg.content, list) else []
            for b in content:
                if isinstance(b, ToolResultBlock):
                    tool_results[b.tool_use_id] = b.content
        elif isinstance(msg, ResultMessage):
            if getattr(msg, "result", None):
                final_text = msg.result
    return build_runresult(tool_uses, tool_results, final_text)


def make_sdk_runner(
    spec: SkillSpec, server: Any, allowed_tools: list[str], model: str = DEFAULT_MODEL,
    *, server_name: str = "factor",
) -> Callable[[str], RunResult]:
    """A sync runner(input)->RunResult that runs the async SDK query per call.

    NOTE: uses asyncio.run, so it is NOT safe to call from within a running event loop
    (e.g. an async M5 host) — call the async `run_skill` directly there instead.
    """
    def runner(user_input: str) -> RunResult:
        return asyncio.run(run_skill(spec, user_input, server=server,
                                     allowed_tools=allowed_tools, model=model,
                                     server_name=server_name))
    return runner
