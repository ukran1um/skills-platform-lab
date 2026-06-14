"""MCP client access: the convention a skill uses to reach a platform MCP server.

get_client("<server>", token=..., base_url=...) returns a sync DataMCPClient that connects
to the server over Streamable HTTP carrying the capability token. The blast-radius scanner
(M3) detects get_client("literal") and checks the name against allowed_mcp_servers."""

from __future__ import annotations

import asyncio
import json
from typing import Any


def _unwrap_exception_group(eg: BaseException) -> BaseException | None:
    """Recursively extract a single leaf exception from a (possibly nested) ExceptionGroup.

    anyio wraps exceptions raised inside task groups in one or more ExceptionGroup layers.
    This returns the innermost non-group exception when there is exactly one, so callers
    can `raise` it directly and `pytest.raises` / user code can match it normally."""
    if isinstance(eg, BaseExceptionGroup):
        if len(eg.exceptions) == 1:
            return _unwrap_exception_group(eg.exceptions[0])
        return None
    return eg


class DataMCPClient:
    def __init__(self, server_name: str, token: str, base_url: str) -> None:
        self.server_name = server_name
        self._token = token
        self._base_url = base_url

    async def _call_async(self, tool: str, arguments: dict[str, Any]) -> Any:
        from mcp import ClientSession
        # streamablehttp_client (with the headers kwarg) is the working API here; the newer
        # streamable_http_client has a different signature (no headers). The deprecation is cosmetic.
        from mcp.client.streamable_http import streamablehttp_client

        headers = {"Authorization": f"Bearer {self._token}"}
        async with streamablehttp_client(self._base_url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments=arguments)
                if result.isError:
                    first = result.content[0] if result.content else None
                    text = first.text if hasattr(first, "text") else "tool error"  # type: ignore[union-attr]
                    raise RuntimeError(f"{tool} failed: {text}")
                first = result.content[0] if result.content else None
                text = first.text if hasattr(first, "text") else "null"  # type: ignore[union-attr]
                return json.loads(text)

    def call_tool(self, tool: str, arguments: dict[str, Any]) -> Any:
        """Sync wrapper: run the async MCP call. (Not for use inside a running event loop.)"""
        try:
            return asyncio.run(self._call_async(tool, arguments))
        except BaseExceptionGroup as eg:
            # anyio task groups wrap exceptions (possibly nested); unwrap so callers
            # can catch RuntimeError("scope denied" / "failed") without ExceptionGroup.
            cause = _unwrap_exception_group(eg)
            if cause is not None:
                raise cause from eg
            raise


def get_client(server_name: str, *, token: str | None = None, base_url: str | None = None) -> DataMCPClient:
    if not token:
        raise ValueError("get_client requires a capability token")
    if not base_url:
        raise ValueError("get_client requires a base_url for the MCP server")
    return DataMCPClient(server_name, token, base_url)
