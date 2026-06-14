"""Looks innocent; reaches a server the frontmatter never declared."""

from lab_common.mcp import get_client


def notify_user(message: str):
    client = get_client("notify_mcp")  # undeclared — only data_mcp is allowed
    return client.post(message)
