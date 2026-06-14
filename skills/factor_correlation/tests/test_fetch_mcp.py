import socket
import threading
import time
from datetime import date
from pathlib import Path

import pytest
import uvicorn

from data_mcp.server import build_app
from factor_correlation.tools.fetch import get_prices, get_prices_via_mcp
from lab_common.capability import mint

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
    server = uvicorn.Server(uvicorn.Config(build_app(parquet=fixtures_parquet),
                                           host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield fixtures_parquet, f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    t.join(timeout=5)


def test_platform_path_matches_laptop_path(live_server):
    fixtures_parquet, url = live_server
    tok = mint(sub="u", skill="factor_correlation", scopes=["prices:read"],
               audience="data_mcp", secret=SECRET)
    laptop = get_prices(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 3, 31), parquet=fixtures_parquet)
    platform = get_prices_via_mcp(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 3, 31), token=tok, base_url=url)
    assert set(platform["ticker"]) == set(laptop["ticker"]) == {"AAPL", "MSFT"}
    assert len(platform) == len(laptop)
