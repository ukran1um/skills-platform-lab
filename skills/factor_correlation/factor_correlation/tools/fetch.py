"""Load prices from the warehouse parquet (laptop context: direct file access)."""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

_FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|export|install|load|set)\b",
    re.IGNORECASE,
)

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


def list_tickers(parquet: Path | None = None) -> list[str]:
    """Distinct tickers in the warehouse, sorted."""
    parquet = parquet or warehouse_path()
    if not parquet.exists():
        raise FileNotFoundError(f"warehouse parquet not found at {parquet}")
    rows = duckdb.execute(
        "SELECT DISTINCT ticker FROM read_parquet(?) ORDER BY ticker", [str(parquet)]
    ).fetchall()
    return [r[0] for r in rows]


def run_sql(query: str, parquet: Path | None = None) -> pd.DataFrame:
    """Read-only SELECT against a view prices(ticker, date, close). SELECT/WITH only,
    single statement, no DDL/DML — enforced here, not trusted to the agent."""
    parquet = parquet or warehouse_path()
    if not parquet.exists():
        raise FileNotFoundError(f"warehouse parquet not found at {parquet}")
    q = query.strip().rstrip(";").strip()
    if ";" in q:
        raise ValueError("only a single statement is allowed")
    if not re.match(r"(?is)^\s*(select|with)\b", q):
        raise ValueError("only SELECT/WITH queries are allowed")
    if _FORBIDDEN_SQL.search(q):
        raise ValueError("query contains a forbidden (non-read) keyword")
    con = duckdb.connect()
    con.execute(f"CREATE VIEW prices AS SELECT * FROM read_parquet('{parquet}')")
    return con.execute(q).df()
