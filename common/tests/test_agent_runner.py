from lab_common.agent_runner import build_runresult


def test_build_runresult_filters_harness_tools_and_strips_prefix():
    tool_uses = [
        ("id0", "ToolSearch", {"query": "select:..."}),
        ("id1", "mcp__factor__compute_correlation", {"tickers": ["AAPL", "MSFT"]}),
    ]
    tool_results = {"id0": "[ref]", "id1": '{"correlation_value": -0.05}'}
    run = build_runresult(tool_uses, tool_results, final_text="the answer")
    assert run.called_tools() == ["compute_correlation"]
    assert run.trajectory[0].input == {"tickers": ["AAPL", "MSFT"]}
    assert run.trajectory[0].result == '{"correlation_value": -0.05}'
    assert run.final_text == "the answer"


def test_build_runresult_handles_missing_result():
    run = build_runresult([("id1", "mcp__factor__list_tickers", {})], {}, final_text=None)
    assert run.called_tools() == ["list_tickers"]
    assert run.trajectory[0].result is None
    assert run.final_text is None


def test_build_runresult_extracts_text_from_list_content():
    # tool_results values may be a list of content blocks (SDK shape) or a plain string.
    tool_uses = [("id1", "mcp__factor__run_sql", {"query": "SELECT 1"})]
    tool_results = {"id1": [{"type": "text", "text": '{"rows": []}'}]}
    run = build_runresult(tool_uses, tool_results, final_text="x")
    assert run.trajectory[0].result == '{"rows": []}'


def test_build_runresult_strips_any_server_prefix():
    # Trajectory parsing must be server-name-agnostic (works for mcp__brief__ too).
    from lab_common.agent_runner import build_runresult
    rr = build_runresult(
        tool_uses=[("t1", "mcp__brief__get_market_data", {"ticker": "AAPL"})],
        tool_results={"t1": "{}"},
        final_text="ok",
    )
    assert rr.trajectory[0].name == "get_market_data"


def test_make_sdk_runner_accepts_server_name():
    # The closure must accept the server_name kwarg without constructing the SDK.
    from lab_common.agent_runner import make_sdk_runner
    from lab_common.models import SkillSpec
    spec = SkillSpec(name="x", version="0", owner="", blast_radius="", allowed_mcp_servers=[],
                     required_scopes=[], golden_set="", threshold=0.0, system_prompt="p")
    runner = make_sdk_runner(spec, {"type": "sdk"}, ["mcp__brief__x"], server_name="brief")
    assert callable(runner)
