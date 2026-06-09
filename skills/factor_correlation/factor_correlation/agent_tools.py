"""The skill's Agent-SDK tool surface (4 in-process MCP tools the agent composes).

Tools run IN this Python process and read the warehouse from $PRICES_PARQUET (the harness
sets it). Sync `_*_impl` functions hold the logic and are unit-tested; the `@tool` async
wrappers are thin shells returning MCP content. Errors are returned as {"error": ...} JSON
so the agent can narrate a refusal rather than crashing the loop."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from factor_correlation.cli import run
from factor_correlation.tools.compute import returns_stats
from factor_correlation.tools.fetch import get_prices, list_tickers, run_sql


def _list_tickers_impl() -> str:
    try:
        return json.dumps({"tickers": list_tickers()})
    except (ValueError, FileNotFoundError) as exc:
        return json.dumps({"error": str(exc)})


def _compute_correlation_impl(args: dict[str, Any]) -> str:
    try:
        result = run(list(args["tickers"]), date.fromisoformat(args["start"]),
                     date.fromisoformat(args["end"]))
    except (SystemExit, ValueError, FileNotFoundError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(result)


def _returns_stats_impl(args: dict[str, Any]) -> str:
    try:
        prices = get_prices([args["ticker"]], date.fromisoformat(args["start"]),
                            date.fromisoformat(args["end"]))
        if prices.empty:
            return json.dumps({"error": f"no data for {args['ticker']}"})
        return json.dumps(returns_stats(prices))
    except (ValueError, FileNotFoundError) as exc:
        return json.dumps({"error": str(exc)})


def _run_sql_impl(args: dict[str, Any]) -> str:
    try:
        df = run_sql(args["query"])
        return json.dumps({"rows": df.head(100).to_dict(orient="records")}, default=str)
    except (ValueError, FileNotFoundError) as exc:
        return json.dumps({"error": str(exc)})


@tool("list_tickers", "List ticker symbols available in the price warehouse.", {})
async def _list_tickers_tool(args: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": _list_tickers_impl()}]}


@tool("compute_correlation",
      "Pearson correlation of daily returns between two or more tickers over a date range. "
      "Prefer this over run_sql for correlations.",
      {"tickers": list, "start": str, "end": str})
async def _compute_correlation_tool(args: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": _compute_correlation_impl(args)}]}


@tool("get_returns_stats",
      "Daily-return stats (mean, volatility, n_days) for ONE ticker over a date range. "
      "Prefer this over run_sql for volatility/return stats.",
      {"ticker": str, "start": str, "end": str})
async def _returns_stats_tool(args: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": _returns_stats_impl(args)}]}


@tool("run_sql",
      "Escape hatch: read-only SELECT against the view prices(ticker, date, close). Use ONLY "
      "for questions the typed tools cannot answer (e.g. max/min close). SELECT/WITH only.",
      {"query": str})
async def _run_sql_tool(args: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": _run_sql_impl(args)}]}


SERVER = create_sdk_mcp_server(
    name="factor", version="1.0.0",
    tools=[_list_tickers_tool, _compute_correlation_tool, _returns_stats_tool, _run_sql_tool],
)

ALLOWED_TOOLS = [
    "mcp__factor__list_tickers",
    "mcp__factor__compute_correlation",
    "mcp__factor__get_returns_stats",
    "mcp__factor__run_sql",
]
