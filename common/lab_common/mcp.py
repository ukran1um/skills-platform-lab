"""The convention by which a skill reaches a platform MCP server.

A skill calls `get_client("<server>")` to obtain a client for a declared MCP server.
The blast-radius scanner (lab_common.governance.blast_radius) detects these calls
statically and checks the server name against the skill's allowed_mcp_servers. The real
client is wired in M4 (Data MCP); for now this is a stub so the convention exists and is
detectable.
"""

from __future__ import annotations

from typing import Any


def get_client(server_name: str) -> Any:
    raise NotImplementedError(
        f"MCP client for {server_name!r} is not available yet (wired in M4). "
        "Skills reference it via this convention so governance can verify "
        "allowed_mcp_servers statically."
    )
