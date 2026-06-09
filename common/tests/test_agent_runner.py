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
