"""Download daily closes from Stooq into the warehouse parquet."""

from __future__ import annotations

import argparse
import io
import time
from pathlib import Path

import pandas as pd
import requests

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"


def stooq_symbol(ticker: str) -> str:
    return f"{ticker.lower()}.us"


def parse_stooq_csv(ticker: str, csv_text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(csv_text))
    if "Close" not in df.columns:
        raise ValueError(f"unexpected response for {ticker}: {csv_text[:80]!r}")
    return pd.DataFrame(
        {
            "ticker": ticker.upper(),
            "date": pd.to_datetime(df["Date"]).dt.date,
            "close": df["Close"].astype(float),
        }
    )


def fetch_ticker(ticker: str, session: requests.Session) -> pd.DataFrame:
    resp = session.get(STOOQ_URL.format(symbol=stooq_symbol(ticker)), timeout=30)
    resp.raise_for_status()
    return parse_stooq_csv(ticker, resp.text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers-file", type=Path, default=Path("data/tickers.txt"))
    parser.add_argument("--out", type=Path, default=Path("data/warehouse/prices.parquet"))
    args = parser.parse_args()
    tickers = [t.strip() for t in args.tickers_file.read_text().splitlines() if t.strip()]
    session = requests.Session()
    frames = []
    for i, ticker in enumerate(tickers):
        try:
            frames.append(fetch_ticker(ticker, session))
            print(f"[{i + 1}/{len(tickers)}] {ticker} ok")
        except Exception as exc:  # noqa: BLE001 — skip-and-report is correct ingest behavior
            print(f"[{i + 1}/{len(tickers)}] {ticker} FAILED: {exc}")
        time.sleep(0.5)  # be polite to stooq
    if not frames:
        raise SystemExit("no tickers downloaded")
    df = pd.concat(frames, ignore_index=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"wrote {len(df)} rows / {df['ticker'].nunique()} tickers to {args.out}")


if __name__ == "__main__":
    main()
