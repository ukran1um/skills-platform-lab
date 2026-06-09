import json
from datetime import date
from pathlib import Path

import pytest

from factor_correlation.cli import run


def test_run_accepts_parquet_kwarg(fixtures_parquet: Path):
    result = run(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)
    assert result["tickers"] == ["AAPL", "MSFT"]
    assert "correlation_value" in result


def test_run_two_tickers_has_correlation_value(fixtures_parquet: Path):
    result = run(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)
    assert result["tickers"] == ["AAPL", "MSFT"]
    assert "correlation_value" in result
    assert -1.0 <= result["correlation_value"] <= 1.0
    assert result["matrix"]["AAPL"]["MSFT"] == result["correlation_value"]
    json.dumps(result)  # JSON-serializable


def test_run_three_tickers_matrix_only(fixtures_parquet: Path):
    result = run(["AAPL", "MSFT", "NVDA"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)
    assert "correlation_value" not in result
    assert set(result["matrix"].keys()) == {"AAPL", "MSFT", "NVDA"}
    assert result["matrix"]["AAPL"]["AAPL"] == pytest.approx(1.0)


def test_run_unknown_ticker_exits(fixtures_parquet: Path):
    with pytest.raises(SystemExit, match="no price data"):
        run(["ZZZTOP"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)


def test_run_partial_unknown_exits(fixtures_parquet: Path):
    with pytest.raises(SystemExit, match="ZZZTOP"):
        run(["AAPL", "ZZZTOP"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)
