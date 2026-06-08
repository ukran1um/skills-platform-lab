from datetime import date

import pandas as pd

from lab_data.ingest import normalize_closes


def _wide() -> pd.DataFrame:
    wide = pd.DataFrame(
        {"AAPL": [100.0, 101.0], "MSFT": [200.0, 202.0]},
        index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
    )
    wide.index.name = "Date"
    wide.columns.name = "Ticker"
    return wide


def test_normalize_closes_wide_to_long():
    long = normalize_closes(_wide())
    assert list(long.columns) == ["ticker", "date", "close"]
    assert set(long["ticker"]) == {"AAPL", "MSFT"}
    assert len(long) == 4
    aapl = long[long["ticker"] == "AAPL"].sort_values("date")
    assert aapl["close"].tolist() == [100.0, 101.0]
    assert long["date"].iloc[0] == date(2025, 1, 2)


def test_normalize_closes_drops_nan():
    wide = _wide()
    wide.loc[wide.index[1], "AAPL"] = None  # one missing close
    long = normalize_closes(wide)
    assert len(long) == 3  # the NaN AAPL row is dropped


def test_normalize_closes_sorted():
    long = normalize_closes(_wide())
    by_ticker = long.groupby("ticker")["date"]
    for _, dates in by_ticker:
        assert list(dates) == sorted(dates)


def test_normalize_closes_single_ticker_no_column_name():
    # Mirrors download_prices' single-ticker path: yf returns a Series, which
    # download_prices converts via close.to_frame(ticker) — a frame whose
    # columns.name is None. The positional rename must still land correctly.
    wide = pd.DataFrame(
        {"AAPL": [100.0, 101.0]},
        index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
    )
    wide.index.name = "Date"  # columns.name intentionally left as None
    long = normalize_closes(wide)
    assert list(long.columns) == ["ticker", "date", "close"]
    assert set(long["ticker"]) == {"AAPL"}
    assert long["close"].tolist() == [100.0, 101.0]
