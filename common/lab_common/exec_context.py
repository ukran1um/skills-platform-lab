"""Platform execution context: how the skill host tells a skill's in-process tools to route
data access through the Data MCP (with a capability token) instead of the laptop warehouse.

Carried in two env vars the tools read at call time. This is the proven mechanism: the Agent
SDK runs in-process tools in THIS process, so env set before the run is visible to them — the
same way $PRICES_PARQUET already is. The host serializes runs (one at a time) so this
process-global env is never shared across concurrent invocations; a production runtime would
isolate per call (a container/worker per invocation, or request-scoped DI)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

URL_ENV = "DATA_MCP_URL"
TOKEN_ENV = "DATA_MCP_TOKEN"


def platform_context() -> tuple[str, str] | None:
    """(base_url, token) if a platform context is active, else None (laptop context)."""
    url = os.environ.get(URL_ENV)
    token = os.environ.get(TOKEN_ENV)
    if url and token:
        return url, token
    return None


@contextmanager
def use_platform_context(base_url: str, token: str) -> Iterator[None]:
    """Activate the platform context for the block, restoring prior env afterwards so nothing
    leaks into the next run."""
    prev = {URL_ENV: os.environ.get(URL_ENV), TOKEN_ENV: os.environ.get(TOKEN_ENV)}
    os.environ[URL_ENV], os.environ[TOKEN_ENV] = base_url, token
    try:
        yield
    finally:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
