from datetime import date
from pathlib import Path

import pytest

from factor_correlation.tools.fetch import get_prices


def test_get_prices_filters_tickers_and_dates(fixtures_parquet: Path):
    df = get_prices(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 3, 31), parquet=fixtures_parquet)
    assert set(df["ticker"]) == {"AAPL", "MSFT"}
    assert df["date"].min() >= date(2025, 1, 1)
    assert df["date"].max() <= date(2025, 3, 31)
    assert list(df.columns) == ["ticker", "date", "close"]


def test_get_prices_is_case_insensitive(fixtures_parquet: Path):
    df = get_prices(["aapl"], date(2025, 1, 1), date(2025, 1, 31), parquet=fixtures_parquet)
    assert set(df["ticker"]) == {"AAPL"}


def test_get_prices_missing_warehouse_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="warehouse parquet not found"):
        get_prices(["AAPL"], date(2025, 1, 1), date(2025, 1, 31), parquet=tmp_path / "nope.parquet")


def test_list_tickers(fixtures_parquet: Path):
    from factor_correlation.tools.fetch import list_tickers
    tickers = list_tickers(parquet=fixtures_parquet)
    assert tickers == sorted(tickers)
    assert "AAPL" in tickers and "MSFT" in tickers


def test_run_sql_select_ok(fixtures_parquet: Path):
    from factor_correlation.tools.fetch import run_sql
    df = run_sql("SELECT count(*) AS n FROM prices WHERE ticker='AAPL'", parquet=fixtures_parquet)
    assert int(df.iloc[0]["n"]) > 0


def test_run_sql_rejects_non_select(fixtures_parquet: Path):
    from factor_correlation.tools.fetch import run_sql
    with pytest.raises(ValueError, match="SELECT"):
        run_sql("DROP TABLE prices", parquet=fixtures_parquet)


def test_run_sql_rejects_multiple_statements(fixtures_parquet: Path):
    from factor_correlation.tools.fetch import run_sql
    with pytest.raises(ValueError, match="single statement"):
        run_sql("SELECT 1; SELECT 2", parquet=fixtures_parquet)
