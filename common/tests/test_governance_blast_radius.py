from pathlib import Path

from lab_common.governance.blast_radius import check_blast_radius, referenced_mcp_servers
from lab_common.skill_spec import load_skill

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR = REPO_ROOT / "skills" / "factor_correlation"
ROGUE = Path(__file__).resolve().parent / "fixtures" / "rogue_skill"


def test_factor_correlation_references_no_servers():
    servers, warnings = referenced_mcp_servers(FACTOR)
    assert servers == set() and warnings == []
    assert check_blast_radius(load_skill(FACTOR), FACTOR) == []


def test_rogue_is_rejected_for_undeclared_server():
    servers, _ = referenced_mcp_servers(ROGUE)
    assert servers == {"notify_mcp"}
    errors = check_blast_radius(load_skill(ROGUE), ROGUE)
    assert any("notify_mcp" in e for e in errors)


def test_dynamic_server_name_is_flagged(tmp_path: Path):
    pkg = tmp_path / "dyn"
    pkg.mkdir()
    (pkg / "SKILL.md").write_text(
        "---\nname: dyn\nversion: 0.1.0\nowner: e\nblast_radius: low\n"
        "allowed_mcp_servers: [data_mcp]\nrequired_scopes: [prices:read]\n"
        "eval:\n  golden_set: evals/golden.yaml\n  threshold: 0.8\n---\n# dyn\n"
    )
    (pkg / "code.py").write_text(
        "from lab_common.mcp import get_client\n"
        "def f(name):\n    return get_client(name)\n"
    )
    _, warnings = referenced_mcp_servers(pkg)
    assert any("non-literal" in w for w in warnings)


def test_keyword_arg_server_name_is_extracted(tmp_path: Path):
    pkg = tmp_path / "kw"
    pkg.mkdir()
    (pkg / "code.py").write_text(
        "from lab_common.mcp import get_client\n"
        "def f():\n    return get_client(server_name='notify_mcp')\n"
    )
    servers, warnings = referenced_mcp_servers(pkg)
    assert servers == {"notify_mcp"} and warnings == []  # keyword form must resolve, not warn


def test_syntax_error_is_a_clean_failure_not_a_crash(tmp_path: Path):
    pkg = tmp_path / "broken"
    pkg.mkdir()
    (pkg / "code.py").write_text("def f(:\n    pass\n")  # invalid syntax
    servers, warnings = referenced_mcp_servers(pkg)  # must not raise
    assert servers == set()
    assert any("SyntaxError" in w for w in warnings)
