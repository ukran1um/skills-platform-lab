"""get_prices_auto routes by execution context: laptop (direct parquet) by default,
platform (Data MCP) when a platform context is active. The platform test stands up a real
Data MCP server in a thread — keyless, no agent."""

from __future__ import annotations

import socket
import threading
import time
from datetime import date
from pathlib import Path

import pytest
import uvicorn

from factor_correlation.tools.fetch import get_prices_auto
from lab_common.capability import mint
from lab_common.exec_context import use_platform_context

SECRET = "m5-fetch-auto-test-secret-32bytes!!"


def test_laptop_context_reads_parquet(fixtures_parquet: Path, monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    df = get_prices_auto(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 3, 31),
                         parquet=fixtures_parquet)
    assert not df.empty and set(df["ticker"].unique()) == {"AAPL", "MSFT"}


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


def test_platform_context_routes_via_mcp(live_data_mcp: str):
    tok = mint(sub="egor", skill="factor_correlation", scopes=["prices:read"],
               audience="data_mcp", secret=SECRET)
    with use_platform_context(live_data_mcp, tok):
        df = get_prices_auto(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 3, 31))
    assert not df.empty and set(df["ticker"].unique()) == {"AAPL", "MSFT"}
