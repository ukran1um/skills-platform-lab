"""Pure correlation math. No I/O here."""

from __future__ import annotations

from typing import Any

import pandas as pd


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Long (ticker, date, close) -> wide frame of daily pct-change returns."""
    wide = prices.pivot(index="date", columns="ticker", values="close").sort_index()
    return wide.pct_change(fill_method=None).dropna(how="all")


def correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of daily returns, pairwise over shared dates."""
    return daily_returns(prices).corr(method="pearson")


def returns_stats(prices: pd.DataFrame) -> dict[str, Any]:
    """Per-ticker daily-return stats from one ticker's price rows.

    daily_vol is the sample std (ddof=1) of daily returns. With a single return row
    (n_days=1) std is NaN, which serializes to JSON null — acceptable for the lab.
    """
    ticker = str(prices["ticker"].iloc[0])
    rets = prices.sort_values("date")["close"].pct_change(fill_method=None).dropna()
    return {
        "ticker": ticker,
        "n_days": int(len(rets)),
        "mean_daily_return": float(rets.mean()),
        "daily_vol": float(rets.std()),
    }
