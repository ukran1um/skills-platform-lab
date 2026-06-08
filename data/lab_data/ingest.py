"""Download daily adjusted closes from Yahoo Finance into the warehouse parquet."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf


def normalize_closes(close_wide: pd.DataFrame) -> pd.DataFrame:
    """Wide (index=date, columns=ticker) closes -> long (ticker, date, close).

    Drops missing closes, sorts by (ticker, date).
    """
    long = close_wide.stack().rename("close").reset_index()
    long.columns = ["date", "ticker", "close"]
    long["date"] = pd.to_datetime(long["date"]).dt.date
    long["close"] = long["close"].astype(float)
    long = long.dropna(subset=["close"])
    long = long[["ticker", "date", "close"]].sort_values(["ticker", "date"])
    return long.reset_index(drop=True)


def download_prices(tickers: list[str], start: str, end: str | None) -> pd.DataFrame:
    """Batch-download adjusted closes for all tickers in one call."""
    raw = yf.download(
        tickers, start=start, end=end, auto_adjust=True, progress=False
    )
    close = raw["Close"]
    if isinstance(close, pd.Series):  # single-ticker shape
        close = close.to_frame(tickers[0])
    return normalize_closes(close)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers-file", type=Path, default=Path("data/tickers.txt"))
    parser.add_argument("--out", type=Path, default=Path("data/warehouse/prices.parquet"))
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default=None)
    args = parser.parse_args()
    tickers = [t.strip() for t in args.tickers_file.read_text().splitlines() if t.strip()]
    df = download_prices(tickers, args.start, args.end)
    if df.empty:
        raise SystemExit("no price data downloaded")
    got = sorted(df["ticker"].unique())
    missing = sorted(set(t.upper() for t in tickers) - set(got))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"wrote {len(df)} rows / {len(got)} tickers to {args.out}")
    if missing:
        print(f"missing tickers (no data returned): {missing}")


if __name__ == "__main__":
    main()
