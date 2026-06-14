import pytest

from lab_common.mcp import DataMCPClient, get_client


def test_get_client_returns_data_mcp_client():
    client = get_client("data_mcp", token="tok", base_url="http://127.0.0.1:9/mcp")
    assert isinstance(client, DataMCPClient)
    assert client.server_name == "data_mcp"


def test_get_client_requires_token_and_base_url():
    with pytest.raises(ValueError, match="token"):
        get_client("data_mcp", base_url="http://x/mcp")
    with pytest.raises(ValueError, match="base_url"):
        get_client("data_mcp", token="tok")
