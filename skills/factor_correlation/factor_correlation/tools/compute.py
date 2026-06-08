"""Pure correlation math. No I/O here."""

from __future__ import annotations

import pandas as pd


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Long (ticker, date, close) -> wide frame of daily pct-change returns."""
    wide = prices.pivot(index="date", columns="ticker", values="close").sort_index()
    return wide.pct_change(fill_method=None).dropna(how="all")


def correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of daily returns, pairwise over shared dates."""
    return daily_returns(prices).corr(method="pearson")
