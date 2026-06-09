from datetime import date

import pandas as pd
import pytest

from factor_correlation.tools.compute import correlation_matrix, daily_returns

DATES = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6), date(2025, 1, 7)]


def _prices(ticker: str, closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"ticker": ticker, "date": DATES, "close": closes})


def _closes_from_returns(start: float, returns: list[float]) -> list[float]:
    closes = [start]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    return closes


def test_daily_returns_shape():
    prices = _prices("AAA", [100.0, 110.0, 104.5, 112.86])
    returns = daily_returns(prices)
    assert list(returns.columns) == ["AAA"]
    assert len(returns) == 3  # n-1 return rows
    assert returns["AAA"].iloc[0] == pytest.approx(0.10)


def test_perfectly_correlated_pair():
    a = _closes_from_returns(100.0, [0.10, -0.05, 0.08])
    b = [x * 2 for x in a]  # scaled prices -> identical returns
    prices = pd.concat([_prices("AAA", a), _prices("BBB", b)], ignore_index=True)
    corr = correlation_matrix(prices)
    assert corr.loc["AAA", "BBB"] == pytest.approx(1.0)


def test_inversely_correlated_pair():
    a = _closes_from_returns(100.0, [0.10, -0.05, 0.08])
    c = _closes_from_returns(100.0, [-0.10, 0.05, -0.08])  # negated returns
    prices = pd.concat([_prices("AAA", a), _prices("CCC", c)], ignore_index=True)
    corr = correlation_matrix(prices)
    assert corr.loc["AAA", "CCC"] == pytest.approx(-1.0, abs=1e-3)


def test_returns_stats():
    from factor_correlation.tools.compute import returns_stats
    prices = _prices("AAA", _closes_from_returns(100.0, [0.10, -0.05, 0.08]))
    stats = returns_stats(prices)
    assert stats["ticker"] == "AAA"
    assert stats["n_days"] == 3
    assert stats["mean_daily_return"] == pytest.approx((0.10 - 0.05 + 0.08) / 3, abs=1e-6)
    assert stats["daily_vol"] > 0
