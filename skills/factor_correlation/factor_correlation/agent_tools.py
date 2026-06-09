"""The skill's agent-facing tool surface.

The agent runner exposes these tools to Claude; in laptop/eval mode they read the
fixtures parquet via the `parquet` context. Tool results are JSON strings (the
Messages API requires tool_result content to be a string).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from factor_correlation.cli import run

TOOLS: list[dict[str, Any]] = [
    {
        "name": "compute_correlation",
        "description": (
            "Compute the Pearson correlation of daily returns between two or more "
            "tickers over a date range. Returns a correlation matrix, and for exactly "
            "two tickers a top-level correlation_value."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ticker symbols, e.g. ['AAPL', 'MSFT']",
                },
                "start": {"type": "string", "description": "Start date ISO YYYY-MM-DD"},
                "end": {"type": "string", "description": "End date ISO YYYY-MM-DD"},
            },
            "required": ["tickers", "start", "end"],
        },
    }
]


def _compute_correlation(inputs: dict[str, Any], context: dict[str, Any]) -> str:
    parquet = context.get("parquet")
    parquet = Path(parquet) if parquet else None
    try:
        result = run(
            list(inputs["tickers"]),
            date.fromisoformat(inputs["start"]),
            date.fromisoformat(inputs["end"]),
            parquet=parquet,
        )
    except SystemExit as exc:  # missing/partial tickers, empty range
        return json.dumps({"error": str(exc)})
    return json.dumps(result)


def dispatch(name: str, inputs: dict[str, Any], context: dict[str, Any]) -> str:
    if name == "compute_correlation":
        return _compute_correlation(inputs, context)
    return json.dumps({"error": f"unknown tool: {name}"})
