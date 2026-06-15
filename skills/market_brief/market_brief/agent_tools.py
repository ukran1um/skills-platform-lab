"""market_brief Agent-SDK tool surface: one tool returning the brief inputs (prices +
fundamentals) for a ticker; the agent narrates the brief from it. The sync `_*_impl` holds the
logic and is unit-tested; the `@tool` wrapper is a thin shell. The impl catches broadly on
purpose — a tool boundary turns ANY failure into {"error": ...} JSON, never an exception."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from market_brief.tools.fetch import get_fundamentals, get_prices


def _get_market_data_impl(args: dict[str, Any]) -> str:
    try:
        ticker = str(args["ticker"]).upper()
        prices = get_prices(ticker, date.fromisoformat(args["start"]),
                            date.fromisoformat(args["end"]))
        if not prices:
            return json.dumps({"error": f"no price data for {ticker}"})
        first, last = prices[0], prices[-1]
        return json.dumps({
            "ticker": ticker,
            "start": args["start"], "end": args["end"],
            "first_close": first["close"], "last_close": last["close"],
            "n_days": len(prices),
            "fundamentals": get_fundamentals(ticker),
        })
    except Exception as exc:  # noqa: BLE001 — tool boundary: never crash the loop
        return json.dumps({"error": str(exc)})


@tool("get_market_data",
      "Fetch the inputs for a brief on ONE ticker over a date range: first/last close, number "
      "of trading days, and fundamentals. Call once, then write the brief.",
      {"ticker": str, "start": str, "end": str})
async def _get_market_data_tool(args: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": _get_market_data_impl(args)}]}


SERVER_NAME = "brief"
SERVER = create_sdk_mcp_server(name="brief", version="1.0.0", tools=[_get_market_data_tool])
ALLOWED_TOOLS = ["mcp__brief__get_market_data"]
