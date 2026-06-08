import json
from datetime import date
from pathlib import Path

import pytest

from factor_correlation.cli import run
from lab_data.fixtures import write_parquet


@pytest.fixture()
def warehouse_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = write_parquet(tmp_path / "prices.parquet")
    monkeypatch.setenv("PRICES_PARQUET", str(path))
    return path


def test_run_two_tickers_has_correlation_value(warehouse_env: Path):
    result = run(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 6, 30))
    assert result["tickers"] == ["AAPL", "MSFT"]
    assert "correlation_value" in result
    assert -1.0 <= result["correlation_value"] <= 1.0
    assert result["matrix"]["AAPL"]["MSFT"] == result["correlation_value"]
    json.dumps(result)  # must be JSON-serializable


def test_run_three_tickers_matrix_only(warehouse_env: Path):
    result = run(["AAPL", "MSFT", "NVDA"], date(2025, 1, 1), date(2025, 6, 30))
    assert "correlation_value" not in result
    assert set(result["matrix"].keys()) == {"AAPL", "MSFT", "NVDA"}
    assert result["matrix"]["AAPL"]["AAPL"] == pytest.approx(1.0)


def test_run_unknown_ticker_exits(warehouse_env: Path):
    with pytest.raises(SystemExit, match="no price data"):
        run(["ZZZTOP"], date(2025, 1, 1), date(2025, 6, 30))


def test_run_partial_unknown_exits(warehouse_env: Path):
    # Some tickers present, some absent: must fail loudly, naming the missing one.
    with pytest.raises(SystemExit, match="ZZZTOP"):
        run(["AAPL", "ZZZTOP"], date(2025, 1, 1), date(2025, 6, 30))
