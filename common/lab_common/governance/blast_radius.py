"""Static (AST) blast-radius scan: which MCP servers does a skill's code reach, and are
they all declared in allowed_mcp_servers?

Convention: skills reach a server via lab_common.mcp.get_client("<server>"). The scanner
finds those calls and extracts the string-literal server name. A non-literal argument
can't be verified statically and is reported as a warning (the runtime token + injection
layers are the real backstop — this is a fast first gate, not a proof)."""

from __future__ import annotations

import ast
from pathlib import Path

from lab_common.models import SkillSpec

_MCP_CLIENT_FUNCS = {"get_client", "get_mcp_client", "mcp_client"}


def _func_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def referenced_mcp_servers(skill_dir: str | Path) -> tuple[set[str], list[str]]:
    """Return (servers referenced via get_client('literal'), warnings for dynamic refs).

    Scans every .py under skill_dir except a tests/ subtree."""
    servers: set[str] = set()
    warnings: list[str] = []
    root = Path(skill_dir).resolve()
    for py in sorted(root.rglob("*.py")):
        rel_parts = py.relative_to(root).parts
        if "tests" in rel_parts:
            continue
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _func_name(node.func) not in _MCP_CLIENT_FUNCS:
                continue
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                servers.add(node.args[0].value)
            else:
                warnings.append(
                    f"{py.name}:{node.lineno}: get_client() called with a non-literal "
                    "server name (cannot verify statically)"
                )
    return servers, warnings


def check_blast_radius(spec: SkillSpec, skill_dir: str | Path) -> list[str]:
    """Errors if the code reaches a server not in allowed_mcp_servers."""
    referenced, warnings = referenced_mcp_servers(skill_dir)
    allowed = set(spec.allowed_mcp_servers)
    undeclared = referenced - allowed
    errors = [
        f"reaches undeclared MCP server '{s}' (allowed_mcp_servers: {sorted(allowed)})"
        for s in sorted(undeclared)
    ]
    errors.extend(warnings)
    return errors
