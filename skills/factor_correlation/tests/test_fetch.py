from datetime import date
from pathlib import Path

import pytest

from factor_correlation.tools.fetch import get_prices
from lab_data.fixtures import write_parquet


@pytest.fixture()
def warehouse(tmp_path: Path) -> Path:
    return write_parquet(tmp_path / "prices.parquet")


def test_get_prices_filters_tickers_and_dates(warehouse: Path):
    df = get_prices(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 3, 31), parquet=warehouse)
    assert set(df["ticker"]) == {"AAPL", "MSFT"}
    assert df["date"].min() >= date(2025, 1, 1)
    assert df["date"].max() <= date(2025, 3, 31)
    assert list(df.columns) == ["ticker", "date", "close"]


def test_get_prices_is_case_insensitive(warehouse: Path):
    df = get_prices(["aapl"], date(2025, 1, 1), date(2025, 1, 31), parquet=warehouse)
    assert set(df["ticker"]) == {"AAPL"}


def test_get_prices_missing_warehouse_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="warehouse parquet not found"):
        get_prices(["AAPL"], date(2025, 1, 1), date(2025, 1, 31), parquet=tmp_path / "nope.parquet")
