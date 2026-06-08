from datetime import date

import pandas as pd

from lab_data.fixtures import make_prices


def test_fixture_prices_deterministic():
    a = make_prices()
    b = make_prices()
    pd.testing.assert_frame_equal(a, b)


def test_fixture_prices_schema_and_bounds():
    df = make_prices(tickers=["AAPL"], start=date(2025, 1, 1), end=date(2025, 1, 31))
    assert list(df.columns) == ["ticker", "date", "close"]
    assert set(df["ticker"]) == {"AAPL"}
    assert (df["close"] > 0).all()
    assert all(d.weekday() < 5 for d in df["date"])  # weekdays only
    assert df["date"].min() >= date(2025, 1, 1)
    assert df["date"].max() <= date(2025, 1, 31)
