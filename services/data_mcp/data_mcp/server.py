"""The Data MCP server: FastMCP tools over the warehouse, capability-token validated.

build_server() registers tools (each reads the verified claims from the request and enforces
its scope). build_app() wraps the streamable-HTTP ASGI app with the auth middleware (401
challenge). Run with: python -m data_mcp.server  (uvicorn on 127.0.0.1:8081)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from starlette.applications import Starlette

from lab_common.capability import Claims, ScopeError

from data_mcp import tools
from data_mcp.auth import CapabilityAuthMiddleware


def _claims_from(ctx: Context) -> Claims:
    request = ctx.request_context.request
    claims = getattr(request.state, "capability_claims", None) if request else None
    if claims is None:
        raise ScopeError("no capability claims on request (auth middleware not applied)")
    return claims


def build_server(parquet: Path | None = None) -> FastMCP:
    server = FastMCP(name="data_mcp", stateless_http=True, json_response=True)

    def _run(name: str, args: dict[str, Any], ctx: Context) -> str:
        claims = _claims_from(ctx)
        try:
            return tools.call_tool_impl(name, args, claims=claims, parquet=parquet)
        except ScopeError as exc:
            raise ValueError(f"scope denied: {exc}") from exc

    @server.tool()
    async def get_prices(tickers: list[str], start: str, end: str, ctx: Context) -> str:
        """Daily closes for tickers over a date range (requires prices:read)."""
        return _run("get_prices", {"tickers": tickers, "start": start, "end": end}, ctx)

    @server.tool()
    async def get_returns(tickers: list[str], start: str, end: str, ctx: Context) -> str:
        """Daily returns for tickers over a date range (requires prices:read)."""
        return _run("get_returns", {"tickers": tickers, "start": start, "end": end}, ctx)

    @server.tool()
    async def get_fundamentals(ticker: str, ctx: Context) -> str:
        """Fundamentals for one ticker (requires fundamentals:read)."""
        return _run("get_fundamentals", {"ticker": ticker}, ctx)

    @server.tool()
    async def run_query(query: str, ctx: Context) -> str:
        """Read-only SELECT over the prices view (requires query:run)."""
        return _run("run_query", {"query": query}, ctx)

    return server


def build_app(parquet: Path | None = None) -> Starlette:
    app = build_server(parquet).streamable_http_app()
    app.add_middleware(CapabilityAuthMiddleware)
    return app


def main() -> None:
    import uvicorn

    uvicorn.run(build_app(), host="127.0.0.1", port=8081)


if __name__ == "__main__":
    main()
