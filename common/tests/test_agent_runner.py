from types import SimpleNamespace

from lab_common.agent_runner import run_skill
from lab_common.models import SkillSpec

SPEC = SkillSpec(
    name="demo",
    version="0.1.0",
    owner="t",
    blast_radius="low",
    allowed_mcp_servers=[],
    required_scopes=[],
    golden_set="",
    threshold=0.0,
    system_prompt="You are a demo agent.",
)

TOOLS = [{"name": "echo", "description": "echo", "input_schema": {"type": "object", "properties": {}}}]


def _block(type_, **kw):
    return SimpleNamespace(type=type_, **kw)


class FakeClient:
    """Yields a scripted sequence of responses, one per create() call."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = self  # so client.messages.create works

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _dispatch(name, inputs, context):
    return '{"echoed": true}'


def test_runner_captures_tool_call_and_final_text():
    responses = [
        SimpleNamespace(
            stop_reason="tool_use",
            content=[_block("tool_use", name="echo", input={"x": 1}, id="tu_1")],
        ),
        SimpleNamespace(
            stop_reason="end_turn",
            content=[_block("text", text="all done")],
        ),
    ]
    client = FakeClient(responses)
    result = run_skill(SPEC, "do it", TOOLS, _dispatch, client=client, context={"parquet": None})
    assert result.final_text == "all done"
    assert result.called_tools() == ["echo"]
    assert result.trajectory[0].input == {"x": 1}
    assert result.trajectory[0].result == '{"echoed": true}'
    assert client.calls[0]["system"] == "You are a demo agent."
    assert client.calls[1]["messages"][-1]["content"][0]["type"] == "tool_result"


def test_runner_respects_max_turns():
    looping = [
        SimpleNamespace(
            stop_reason="tool_use",
            content=[_block("tool_use", name="echo", input={}, id=f"tu_{i}")],
        )
        for i in range(10)
    ]
    client = FakeClient(looping)
    result = run_skill(
        SPEC, "loop", TOOLS, _dispatch, client=client, context={}, max_turns=3
    )
    assert len(client.calls) == 3  # stopped at the cap
    assert len(result.trajectory) == 3
