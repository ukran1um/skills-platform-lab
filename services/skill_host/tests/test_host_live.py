"""End-to-end M5: the host runs a blessed skill through the REAL Agent SDK, and the skill's
tools fetch through the capability-gated Data MCP (platform context). Marked `eval` — needs the
claude CLI + ANTHROPIC_API_KEY and stands up a live Data MCP server. Run: uv run pytest -m eval."""

from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from skill_host.host import HostConfig, run_skill_request

pytestmark = pytest.mark.eval

REPO = Path(__file__).resolve().parents[3]
SECRET = "m5-host-live-test-secret-32-bytes!!"


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
    monkeypatch.setenv("PRICES_PARQUET", str(fixtures_parquet))
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


def _cfg(base_url: str) -> HostConfig:
    return HostConfig(skills_dir=REPO / "skills", registry_dir=REPO / "registry",
                      entitlements_path=REPO / "registry" / "entitlements.yaml",
                      data_mcp_base_url=base_url, secret=SECRET)


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
def test_host_runs_factor_correlation_through_data_mcp(live_data_mcp: str):
    resp = asyncio.run(run_skill_request(
        "factor_correlation",
        "How correlated were AAPL and MSFT daily returns from 2025-01-01 to 2025-03-31?",
        "egor", config=_cfg(live_data_mcp)))
    assert resp.status == "blessed" and resp.scopes == ["prices:read"]
    assert resp.final_text and "compute_correlation" in [c["name"] for c in resp.trajectory]


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
def test_host_runs_market_brief_through_data_mcp(live_data_mcp: str):
    resp = asyncio.run(run_skill_request(
        "market_brief", "Give me a short brief on AAPL from 2025-01-01 to 2025-03-31.",
        "egor", config=_cfg(live_data_mcp)))
    assert resp.status == "blessed"
    assert sorted(resp.scopes) == ["fundamentals:read", "prices:read"]
    assert resp.final_text and "get_market_data" in [c["name"] for c in resp.trajectory]
