"""Deterministic synthetic price fixtures for tests and evals."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "SPY"]
SEED = 42


def make_prices(
    tickers: list[str] | None = None,
    start: date = date(2024, 1, 1),
    end: date = date(2025, 12, 31),
    seed: int = SEED,
) -> pd.DataFrame:
    """Geometric random walk, weekdays only. Same seed -> identical frame.

    Note: per-ticker values depend on position in `tickers` (one RNG drawn
    sequentially across the list), so changing the list changes downstream values.
    """
    tickers = tickers or DEFAULT_TICKERS
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end)
    frames = []
    for ticker in tickers:
        log_returns = rng.normal(loc=0.0003, scale=0.02, size=len(days))
        close = 100.0 * np.exp(np.cumsum(log_returns))
        frames.append(pd.DataFrame({"ticker": ticker, "date": days.date, "close": close}))
    return pd.concat(frames, ignore_index=True)


def write_parquet(out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    make_prices().to_parquet(out_path, index=False)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/fixtures/prices.parquet"))
    args = parser.parse_args()
    print(f"wrote {write_parquet(args.out)}")


if __name__ == "__main__":
    main()
