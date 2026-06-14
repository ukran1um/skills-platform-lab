from pathlib import Path

from starlette.testclient import TestClient

from data_mcp.server import build_app
from lab_common.capability import mint


def test_missing_token_gets_401_challenge(fixtures_parquet: Path, monkeypatch):
    monkeypatch.setenv("CAPABILITY_SECRET", "test-secret")
    c = TestClient(build_app(parquet=fixtures_parquet))
    r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401
    assert "Bearer" in r.headers.get("WWW-Authenticate", "")


def test_invalid_token_gets_401(fixtures_parquet: Path, monkeypatch):
    monkeypatch.setenv("CAPABILITY_SECRET", "test-secret")
    c = TestClient(build_app(parquet=fixtures_parquet))
    r = c.post("/mcp", headers={"Authorization": "Bearer not-a-jwt"},
               json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401


def test_valid_token_passes_the_auth_layer(fixtures_parquet: Path, monkeypatch):
    monkeypatch.setenv("CAPABILITY_SECRET", "test-secret")
    tok = mint(sub="u", skill="s", scopes=["prices:read"], audience="data_mcp", secret="test-secret")
    with TestClient(build_app(parquet=fixtures_parquet)) as c:
        r = c.post("/mcp", headers={"Authorization": f"Bearer {tok}"},
                   json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code != 401   # past the auth layer (may be 200/400/406 from MCP handshake)
