"""MCP client access: the convention a skill uses to reach a platform MCP server.

get_client("<server>", token=..., base_url=...) returns a sync DataMCPClient that connects
to the server over Streamable HTTP carrying the capability token. The blast-radius scanner
(M3) detects get_client("literal") and checks the name against allowed_mcp_servers."""

from __future__ import annotations

import asyncio
import json
from typing import Any


class DataMCPClient:
    def __init__(self, server_name: str, token: str, base_url: str) -> None:
        self.server_name = server_name
        self._token = token
        self._base_url = base_url

    async def _call_async(self, tool: str, arguments: dict[str, Any]) -> Any:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        headers = {"Authorization": f"Bearer {self._token}"}
        async with streamablehttp_client(self._base_url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments=arguments)
                if result.isError:
                    text = result.content[0].text if result.content else "tool error"
                    raise RuntimeError(f"{tool} failed: {text}")
                text = result.content[0].text if result.content else "null"
                return json.loads(text)

    def call_tool(self, tool: str, arguments: dict[str, Any]) -> Any:
        """Sync wrapper: run the async MCP call. (Not for use inside a running event loop.)"""
        return asyncio.run(self._call_async(tool, arguments))


def get_client(server_name: str, *, token: str | None = None, base_url: str | None = None) -> DataMCPClient:
    if not token:
        raise ValueError("get_client requires a capability token")
    if not base_url:
        raise ValueError("get_client requires a base_url for the MCP server")
    return DataMCPClient(server_name, token, base_url)
