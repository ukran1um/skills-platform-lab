"""market_brief data access. Platform context (set by the skill host) -> the governed Data MCP
(capability-scoped get_prices + get_fundamentals); laptop context -> direct parquet for prices
(fundamentals only exist on the platform). The get_client('data_mcp') calls are what the
blast-radius scanner detects and checks against allowed_mcp_servers."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from lab_common.exec_context import platform_context

DEFAULT_WAREHOUSE = Path("data/warehouse/prices.parquet")


def _warehouse() -> Path:
    return Path(os.environ.get("PRICES_PARQUET", str(DEFAULT_WAREHOUSE)))


def get_prices(ticker: str, start: date, end: date) -> list[dict[str, Any]]:
    ctx = platform_context()
    if ctx is not None:
        base_url, token = ctx
        from lab_common.mcp import get_client
        client = get_client("data_mcp", token=token, base_url=base_url)
        return client.call_tool("get_prices", {"tickers": [ticker.upper()],
                                "start": start.isoformat(), "end": end.isoformat()})
    parquet = _warehouse()
    if not parquet.exists():
        raise FileNotFoundError(f"warehouse parquet not found at {parquet}")
    q = ("SELECT ticker, CAST(date AS VARCHAR) AS date, close FROM read_parquet(?) "
         "WHERE ticker = ? AND date BETWEEN ? AND ? ORDER BY date")
    rows = duckdb.execute(q, [str(parquet), ticker.upper(), start.isoformat(),
                              end.isoformat()]).df()
    return rows.to_dict(orient="records")


def get_fundamentals(ticker: str) -> dict[str, Any]:
    ctx = platform_context()
    if ctx is not None:
        base_url, token = ctx
        from lab_common.mcp import get_client
        client = get_client("data_mcp", token=token, base_url=base_url)
        return client.call_tool("get_fundamentals", {"ticker": ticker.upper()})
    return {"ticker": ticker.upper(), "note": "fundamentals unavailable in laptop context"}
