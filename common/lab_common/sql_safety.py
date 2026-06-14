"""Shared SELECT-only guard for the flexible query path (used by the Data MCP run_query)."""

from __future__ import annotations

import re

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|export|install|load|set|call)\b",
    re.IGNORECASE,
)


def validate_select_only(query: str) -> str:
    """Return the normalized query if it is a single read-only SELECT/WITH; else raise."""
    q = query.strip().rstrip(";").strip()
    if not re.match(r"(?is)^\s*(select|with)\b", q):
        raise ValueError("only SELECT/WITH queries are allowed")
    if _FORBIDDEN.search(q):
        raise ValueError("query contains a forbidden (non-read) keyword")
    if ";" in q:
        raise ValueError("only a single statement is allowed")
    return q
