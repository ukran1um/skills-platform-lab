"""The FastAPI surface: governance failures map to HTTP status; the happy path returns the
run result. The agent run is faked via create_app(runner=...)."""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from lab_common.models import RunResult, ToolCall
from skill_host.app import create_app
from skill_host.host import HostConfig

REPO = Path(__file__).resolve().parents[3]
SECRET = "skill-host-api-test-secret-32bytes!"


def _cfg() -> HostConfig:
    return HostConfig(skills_dir=REPO / "skills", registry_dir=REPO / "registry",
                      entitlements_path=REPO / "registry" / "entitlements.yaml",
                      data_mcp_base_url="http://data-mcp.test/mcp", secret=SECRET)


async def _fake_runner(loaded, message):
    return RunResult(final_text="brief done",
                     trajectory=[ToolCall("compute_correlation", {"x": 1}, "{}")])


def test_healthz():
    client = TestClient(create_app(config=_cfg(), runner=_fake_runner))
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_run_blessed_skill_returns_result():
    client = TestClient(create_app(config=_cfg(), runner=_fake_runner))
    r = client.post("/run", json={"skill": "factor_correlation",
                                  "message": "corr AAPL MSFT", "user": "egor"})
    assert r.status_code == 200
    body = r.json()
    assert body["scopes"] == ["prices:read"]
    assert body["final_text"] == "brief done"
    assert body["trajectory"][0]["name"] == "compute_correlation"


def test_unknown_skill_is_404():
    client = TestClient(create_app(config=_cfg(), runner=_fake_runner))
    r = client.post("/run", json={"skill": "nope", "message": "x", "user": "egor"})
    assert r.status_code == 404


def test_unentitled_user_is_403():
    client = TestClient(create_app(config=_cfg(), runner=_fake_runner))
    r = client.post("/run", json={"skill": "factor_correlation", "message": "x", "user": "nobody"})
    assert r.status_code == 403


def test_default_config_reads_data_mcp_base_url_env(monkeypatch):
    from skill_host.app import default_config
    from skill_host.host import DEFAULT_DATA_MCP_BASE_URL

    monkeypatch.delenv("DATA_MCP_BASE_URL", raising=False)
    assert default_config().data_mcp_base_url == DEFAULT_DATA_MCP_BASE_URL
    monkeypatch.setenv("DATA_MCP_BASE_URL", "http://data-mcp.example:9000/mcp")
    assert default_config().data_mcp_base_url == "http://data-mcp.example:9000/mcp"
