"""DuckDB queries over the price warehouse parquet. The Data MCP's data layer."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from lab_common.sql_safety import validate_select_only

ENV_VAR = "PRICES_PARQUET"
DEFAULT = Path("data/warehouse/prices.parquet")


def warehouse_path() -> Path:
    return Path(os.environ.get(ENV_VAR, str(DEFAULT)))


def get_prices(tickers: list[str], start: str, end: str, *, parquet: Path | None = None) -> list[dict[str, Any]]:
    parquet = parquet or warehouse_path()
    upper = [t.upper() for t in tickers]
    placeholders = ",".join("?" for _ in upper)
    q = (f"SELECT ticker, CAST(date AS VARCHAR) AS date, close FROM read_parquet(?) "
         f"WHERE ticker IN ({placeholders}) AND date BETWEEN ? AND ? ORDER BY ticker, date")
    df = duckdb.execute(q, [str(parquet), *upper, start, end]).df()
    return df.to_dict(orient="records")


def get_returns(tickers: list[str], start: str, end: str, *, parquet: Path | None = None) -> list[dict[str, Any]]:
    rows = get_prices(tickers, start, end, parquet=parquet)
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    df["ret"] = df.groupby("ticker")["close"].pct_change(fill_method=None)
    out = df.dropna(subset=["ret"])[["ticker", "date", "ret"]]
    return out.to_dict(orient="records")


def get_fundamentals(ticker: str, *, parquet: Path | None = None) -> dict[str, Any]:
    # Stub fundamentals (the warehouse has only prices); exists so the scope distinction
    # (fundamentals:read) is real and enforceable.
    return {"ticker": ticker.upper(), "sector": "Unknown", "note": "stub fundamentals"}


def run_query(query: str, *, parquet: Path | None = None) -> list[dict[str, Any]]:
    parquet = parquet or warehouse_path()
    q = validate_select_only(query)
    con = duckdb.connect()
    con.read_parquet(str(parquet)).create_view("prices")
    return con.execute(q).df().head(100).to_dict(orient="records")
