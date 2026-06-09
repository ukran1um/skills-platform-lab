import json
from pathlib import Path

from factor_correlation.agent_tools import TOOLS, dispatch


def test_tools_catalog_shape():
    assert len(TOOLS) == 1
    tool = TOOLS[0]
    assert tool["name"] == "compute_correlation"
    assert "tickers" in tool["input_schema"]["properties"]
    assert tool["input_schema"]["required"] == ["tickers", "start", "end"]


def test_dispatch_returns_correlation_json(fixtures_parquet: Path):
    out = dispatch(
        "compute_correlation",
        {"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
        {"parquet": fixtures_parquet},
    )
    data = json.loads(out)
    assert data["tickers"] == ["AAPL", "MSFT"]
    assert -1.0 <= data["correlation_value"] <= 1.0


def test_dispatch_unknown_ticker_returns_error_not_raises(fixtures_parquet: Path):
    out = dispatch(
        "compute_correlation",
        {"tickers": ["ZZZTOP"], "start": "2025-01-01", "end": "2025-06-30"},
        {"parquet": fixtures_parquet},
    )
    data = json.loads(out)
    assert "error" in data  # the agent must be able to narrate the refusal


def test_dispatch_unknown_tool_returns_error(fixtures_parquet: Path):
    out = dispatch("nope", {}, {"parquet": fixtures_parquet})
    assert "error" in json.loads(out)
