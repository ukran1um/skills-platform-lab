"""Generic agent loop over the Anthropic Messages API with full trajectory capture.

Skill-agnostic: the caller supplies the tool catalog (JSON-schema dicts) and a
`dispatch(name, inputs, context) -> str` function. This is the runner the M5
skill-host will reuse (swapping local dispatch for MCP-client dispatch + tokens).
"""

from __future__ import annotations

from typing import Any, Callable

from lab_common.models import RunResult, SkillSpec, ToolCall

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TURNS = 8

DispatchFn = Callable[[str, dict[str, Any], dict[str, Any]], str]


def run_skill(
    spec: SkillSpec,
    user_input: str,
    tools: list[dict[str, Any]],
    dispatch: DispatchFn,
    *,
    client: Any,
    context: dict[str, Any] | None = None,
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_tokens: int = 2048,
) -> RunResult:
    context = context or {}
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_input}]
    trajectory: list[ToolCall] = []
    final_text: str | None = None

    for _ in range(max_turns):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=spec.system_prompt,
            tools=tools,
            messages=messages,
        )
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        texts = [b for b in response.content if b.type == "text"]
        turn_text = texts[-1].text if texts else None

        if response.stop_reason != "tool_use" or not tool_uses:
            # Only the terminal turn's text is the agent's answer; never carry
            # forward mid-loop narration (it would be judged as the answer).
            final_text = turn_text
            break

        tool_results = []
        for block in tool_uses:
            out = dispatch(block.name, dict(block.input), context)
            trajectory.append(ToolCall(name=block.name, input=dict(block.input), result=out))
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": out}
            )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return RunResult(final_text=final_text, trajectory=trajectory)
