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

# Matched by function NAME (so get_client(...) and x.get_client(...) both match). This is
# deliberately broad: a skill that defines its own unrelated get_client() gets flagged, which
# is the conservative (over-block) outcome — a CI gate must not have false negatives.
_MCP_CLIENT_FUNCS = {"get_client", "get_mcp_client", "mcp_client"}


def _func_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _literal_server(node: ast.Call) -> str | None:
    """Extract the server name from get_client('x') or get_client(server_name='x')."""
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    for kw in node.keywords:
        if kw.arg == "server_name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def referenced_mcp_servers(skill_dir: str | Path) -> tuple[set[str], list[str]]:
    """Return (servers referenced via get_client('literal'), warnings for dynamic refs).

    Scans every .py under skill_dir except a tests/ subtree."""
    servers: set[str] = set()
    warnings: list[str] = []
    root = Path(skill_dir).resolve()
    for py in sorted(root.rglob("*.py")):
        rel = py.relative_to(root)
        if "tests" in rel.parts:
            continue
        try:
            tree = ast.parse(py.read_text(), filename=str(py))
        except SyntaxError as exc:
            # A malformed skill file is a clean governance failure, not a runner crash.
            warnings.append(f"{rel}:{exc.lineno}: SyntaxError: {exc.msg}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _func_name(node.func) not in _MCP_CLIENT_FUNCS:
                continue
            server = _literal_server(node)
            if server is not None:
                servers.add(server)
            else:
                warnings.append(
                    f"{rel}:{node.lineno}: get_client() called with a non-literal "
                    "server name (cannot verify statically)"
                )
    return servers, warnings


def check_blast_radius(spec: SkillSpec, skill_dir: str | Path) -> list[str]:
    """Errors if the code reaches a server not in allowed_mcp_servers, or if any
    get_client call uses a non-literal server name / a file fails to parse."""
    referenced, warnings = referenced_mcp_servers(skill_dir)
    allowed = set(spec.allowed_mcp_servers)
    undeclared = referenced - allowed
    errors = [
        f"reaches undeclared MCP server '{s}' (allowed_mcp_servers: {sorted(allowed)})"
        for s in sorted(undeclared)
    ]
    errors.extend(warnings)
    return errors
