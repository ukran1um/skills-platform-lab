"""Load prices from the warehouse parquet (laptop context: direct file access)."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

DEFAULT_WAREHOUSE = Path("data/warehouse/prices.parquet")
ENV_VAR = "PRICES_PARQUET"


def warehouse_path() -> Path:
    return Path(os.environ.get(ENV_VAR, str(DEFAULT_WAREHOUSE)))


def get_prices(
    tickers: list[str],
    start: date,
    end: date,
    parquet: Path | None = None,
) -> pd.DataFrame:
    parquet = parquet or warehouse_path()
    if not parquet.exists():
        raise FileNotFoundError(
            f"warehouse parquet not found at {parquet}; "
            f"run `uv run python -m lab_data.ingest` or set ${ENV_VAR}"
        )
    upper = [t.upper() for t in tickers]
    placeholders = ",".join("?" for _ in upper)
    query = f"""
        SELECT ticker, date, close
        FROM read_parquet(?)
        WHERE ticker IN ({placeholders}) AND date BETWEEN ? AND ?
        ORDER BY ticker, date
    """
    df = duckdb.execute(query, [str(parquet), *upper, start, end]).df()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df
