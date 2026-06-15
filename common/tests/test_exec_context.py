import os

from lab_common.exec_context import platform_context, use_platform_context


def test_no_context_by_default(monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    assert platform_context() is None


def test_context_active_inside_block(monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    with use_platform_context("http://h/mcp", "tok"):
        assert platform_context() == ("http://h/mcp", "tok")
    assert platform_context() is None  # restored after the block


def test_context_restores_prior_value(monkeypatch):
    monkeypatch.setenv("DATA_MCP_URL", "http://old/mcp")
    monkeypatch.setenv("DATA_MCP_TOKEN", "old")
    with use_platform_context("http://new/mcp", "new"):
        assert platform_context() == ("http://new/mcp", "new")
    assert os.environ["DATA_MCP_URL"] == "http://old/mcp"
    assert os.environ["DATA_MCP_TOKEN"] == "old"


def test_partial_env_is_not_a_context(monkeypatch):
    monkeypatch.setenv("DATA_MCP_URL", "http://h/mcp")
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    assert platform_context() is None  # need BOTH url and token
