import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from data_mcp.server import build_app
from lab_common.capability import mint
from lab_common.mcp import get_client

SECRET = "m4-integration-test-secret-32byte!"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def live_server(fixtures_parquet: Path, monkeypatch):
    monkeypatch.setenv("CAPABILITY_SECRET", SECRET)
    port = _free_port()
    config = uvicorn.Config(build_app(parquet=fixtures_parquet), host="127.0.0.1", port=port, log_level="warning")
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


def test_get_prices_via_mcp_with_valid_token(live_server: str):
    tok = mint(sub="user:egor", skill="factor_correlation", scopes=["prices:read"],
               audience="data_mcp", secret=SECRET)
    client = get_client("data_mcp", token=tok, base_url=live_server)
    rows = client.call_tool("get_prices", {"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-03-31"})
    assert rows and {r["ticker"] for r in rows} == {"AAPL", "MSFT"}


def test_insufficient_scope_is_an_error(live_server: str):
    tok = mint(sub="u", skill="s", scopes=["fundamentals:read"], audience="data_mcp", secret=SECRET)
    client = get_client("data_mcp", token=tok, base_url=live_server)
    with pytest.raises(RuntimeError, match="scope denied"):
        client.call_tool("get_prices", {"tickers": ["AAPL"], "start": "2025-01-01", "end": "2025-03-31"})


def test_no_token_is_unauthorized(live_server: str):
    client = get_client("data_mcp", token="not-a-jwt", base_url=live_server)
    with pytest.raises(Exception):
        client.call_tool("get_prices", {"tickers": ["AAPL"], "start": "2025-01-01", "end": "2025-03-31"})
