import json
from pathlib import Path

import pytest

from data_mcp.tools import TOOL_SCOPES, call_tool_impl
from lab_common.capability import Claims, ScopeError


def _claims(scopes):
    return Claims(sub="u", skill="factor_correlation", scopes=scopes, audience="data_mcp")


def test_scope_map():
    assert TOOL_SCOPES["get_prices"] == "prices:read"
    assert TOOL_SCOPES["run_query"] == "query:run"
    assert TOOL_SCOPES["get_fundamentals"] == "fundamentals:read"


def test_get_prices_with_scope(fixtures_parquet: Path):
    out = call_tool_impl("get_prices", {"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-03-31"},
                         claims=_claims(["prices:read"]), parquet=fixtures_parquet)
    rows = json.loads(out)
    assert rows and {r["ticker"] for r in rows} == {"AAPL", "MSFT"}


def test_get_prices_without_scope_is_denied(fixtures_parquet: Path):
    with pytest.raises(ScopeError):
        call_tool_impl("get_prices", {"tickers": ["AAPL"], "start": "2025-01-01", "end": "2025-03-31"},
                       claims=_claims(["fundamentals:read"]), parquet=fixtures_parquet)


def test_run_query_requires_query_scope(fixtures_parquet: Path):
    with pytest.raises(ScopeError):
        call_tool_impl("run_query", {"query": "SELECT max(close) FROM prices"},
                       claims=_claims(["prices:read"]), parquet=fixtures_parquet)
    out = call_tool_impl("run_query", {"query": "SELECT count(*) AS n FROM prices WHERE ticker='AAPL'"},
                         claims=_claims(["query:run"]), parquet=fixtures_parquet)
    assert json.loads(out)[0]["n"] > 0
