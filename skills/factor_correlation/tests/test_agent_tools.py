import json
from pathlib import Path

import pytest

from factor_correlation import agent_tools as at


@pytest.fixture()
def env_parquet(fixtures_parquet: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PRICES_PARQUET", str(fixtures_parquet))
    return fixtures_parquet


def test_allowed_tools_and_server(env_parquet):
    assert set(at.ALLOWED_TOOLS) == {
        "mcp__factor__list_tickers", "mcp__factor__compute_correlation",
        "mcp__factor__get_returns_stats", "mcp__factor__run_sql",
    }
    assert at.SERVER is not None


def test_impl_list_tickers(env_parquet):
    assert "AAPL" in json.loads(at._list_tickers_impl())["tickers"]


def test_impl_compute_correlation(env_parquet):
    out = json.loads(at._compute_correlation_impl({"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"}))
    assert -1.0 <= out["correlation_value"] <= 1.0


def test_impl_returns_stats(env_parquet):
    out = json.loads(at._returns_stats_impl({"ticker": "AAPL", "start": "2025-01-01", "end": "2025-06-30"}))
    assert out["ticker"] == "AAPL" and out["daily_vol"] > 0


def test_impl_run_sql_ok(env_parquet):
    out = json.loads(at._run_sql_impl({"query": "SELECT max(close) AS hi FROM prices WHERE ticker='AAPL'"}))
    assert out["rows"]


def test_impl_run_sql_rejected_is_error(env_parquet):
    assert "error" in json.loads(at._run_sql_impl({"query": "DELETE FROM prices"}))


def test_impl_missing_ticker_is_error(env_parquet):
    assert "error" in json.loads(at._compute_correlation_impl({"tickers": ["ZZZTOP"], "start": "2025-01-01", "end": "2025-06-30"}))
