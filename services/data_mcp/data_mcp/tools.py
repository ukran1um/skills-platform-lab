"""Scope-checked tool implementations. Pure (claims + args + parquet -> JSON string),
so scope enforcement and data access are unit-testable without a server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lab_common.capability import Claims, require_scope

from data_mcp import warehouse

TOOL_SCOPES = {
    "get_prices": "prices:read",
    "get_returns": "prices:read",
    "get_fundamentals": "fundamentals:read",
    "run_query": "query:run",
}


def call_tool_impl(name: str, args: dict[str, Any], *, claims: Claims, parquet: Path | None = None) -> str:
    """Enforce the tool's scope against the caller's claims, then run it. Returns a JSON
    string. Raises ScopeError on insufficient scope (the caller maps it to an MCP error)."""
    if name not in TOOL_SCOPES:
        raise ValueError(f"unknown tool: {name}")
    require_scope(claims, TOOL_SCOPES[name])
    if name == "get_prices":
        return json.dumps(warehouse.get_prices(args["tickers"], args["start"], args["end"], parquet=parquet))
    if name == "get_returns":
        return json.dumps(warehouse.get_returns(args["tickers"], args["start"], args["end"], parquet=parquet))
    if name == "get_fundamentals":
        return json.dumps(warehouse.get_fundamentals(args["ticker"], parquet=parquet))
    return json.dumps(warehouse.run_query(args["query"], parquet=parquet))
