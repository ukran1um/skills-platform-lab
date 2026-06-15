"""market_brief data access routes by execution context, exactly like factor_correlation.
Laptop reads the parquet for prices (fundamentals only exist on the platform); platform routes
both through the Data MCP. The platform test stands up a real server — keyless, no agent."""

from __future__ import annotations

import json
import socket
import threading
import time
from datetime import date
from pathlib import Path

import pytest
import uvicorn

from lab_common.capability import mint
from lab_common.exec_context import use_platform_context
from market_brief.agent_tools import _get_market_data_impl
from market_brief.tools.fetch import get_fundamentals, get_prices

SECRET = "m5-market-brief-test-secret-32byte!"


def test_laptop_prices_from_parquet(fixtures_parquet: Path, monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    monkeypatch.setenv("PRICES_PARQUET", str(fixtures_parquet))
    rows = get_prices("AAPL", date(2025, 1, 1), date(2025, 3, 31))
    assert rows and all(r["ticker"] == "AAPL" for r in rows)


def test_laptop_fundamentals_note(monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    assert "unavailable" in get_fundamentals("AAPL")["note"].lower()


def test_impl_builds_brief_inputs(fixtures_parquet: Path, monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    monkeypatch.setenv("PRICES_PARQUET", str(fixtures_parquet))
    out = json.loads(_get_market_data_impl(
        {"ticker": "AAPL", "start": "2025-01-01", "end": "2025-03-31"}))
    assert out["ticker"] == "AAPL"
    assert "first_close" in out and "last_close" in out and out["n_days"] > 0


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def live_data_mcp(fixtures_parquet: Path, monkeypatch):
    from data_mcp.server import build_app
    monkeypatch.setenv("CAPABILITY_SECRET", SECRET)
    port = _free_port()
    config = uvicorn.Config(build_app(parquet=fixtures_parquet), host="127.0.0.1",
                            port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    thread.join(timeout=5)


def test_platform_routes_prices_and_fundamentals(live_data_mcp: str):
    tok = mint(sub="egor", skill="market_brief", scopes=["prices:read", "fundamentals:read"],
               audience="data_mcp", secret=SECRET)
    with use_platform_context(live_data_mcp, tok):
        rows = get_prices("AAPL", date(2025, 1, 1), date(2025, 3, 31))
        fundamentals = get_fundamentals("AAPL")
    assert rows and rows[0]["ticker"] == "AAPL"
    assert fundamentals["ticker"] == "AAPL"  # came from the Data MCP get_fundamentals stub
