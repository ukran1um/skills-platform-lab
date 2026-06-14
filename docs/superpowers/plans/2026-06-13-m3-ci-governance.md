# M3: CI as Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CI the governance gate — frontmatter schema validation, a blast-radius AST scan, scope-vocabulary validation, and a git→`registry.json` reconcile run on every push (keyless and free), the DeepEval eval gate runs as a separate keyed job, and a `rogue_skill` fixture proves the blast-radius scan rejects a skill whose code reaches an undeclared MCP server while its frontmatter and scopes are clean.

**Architecture:** A new `lab_common.governance` package holds four independent checks (frontmatter / blast_radius / scopes / reconcile) and a thin CLI. Skills reach MCP servers through one convention — `lab_common.mcp.get_client("<server>")` — which the AST scanner detects statically and validates against `allowed_mcp_servers`. The registry is git-as-source (`registry/<skill>.yaml` = the governance approval) reconciled to a `registry.json` deployed-state artifact; a skill is `blessed` only when SKILL.md frontmatter and its registry record agree. CI grows a second job for the keyed eval gate.

**Tech Stack:** Python 3.12, uv, `ast` (stdlib), Pydantic v2, PyYAML, GitHub Actions, `gh`. Eval job adds Node + the `@anthropic-ai/claude-code` CLI.

**Spec:** `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md` (Skill Registry & Governance + §4a CI/CD).

**Scope:** M3 only. NOT M4 (real Data MCP) or M5 (skill host). `lab_common.mcp.get_client` is a stub here (the convention the scanner needs); M4 implements it.

---

## Current state (verified)

- One real skill: `skills/factor_correlation/` (4 tools; frontmatter: name=factor_correlation, version=0.1.0, owner=egor, blast_radius=low, allowed_mcp_servers=[data_mcp], required_scopes=[prices:read]).
- `lab_common`: `models.py` (SkillSpec etc.), `skill_spec.py` (`load_skill`), `agent_runner.py`, `deepeval_metrics.py`, `eval_harness.py`.
- CI = one `checks` job (ruff+mypy+pytest, keyless). The live eval is `-m eval`, run only locally.
- `.env` (gitignored) has ANTHROPIC + OPENAI keys.

## File structure after this plan

```
common/lab_common/
├── mcp.py                       # NEW: get_client(server) stub — the MCP-access convention the scanner detects
└── governance/
    ├── __init__.py              # NEW
    ├── frontmatter.py           # NEW: Pydantic model + check_frontmatter(spec)->list[str]
    ├── blast_radius.py          # NEW: referenced_mcp_servers(dir), check_blast_radius(spec,dir)->list[str]
    ├── scopes.py                # NEW: load_scope_vocab(path), check_scopes(spec,vocab)->list[str]
    ├── reconcile.py             # NEW: reconcile_skill / reconcile_all -> registry.json dict
    └── cli.py                   # NEW: check / check-all / reconcile; exit 0/1
common/tests/
├── test_governance_frontmatter.py    # NEW
├── test_governance_blast_radius.py   # NEW
├── test_governance_scopes.py         # NEW
├── test_governance_reconcile.py      # NEW
├── test_governance_cli.py            # NEW
└── fixtures/rogue_skill/             # NEW fixture (NOT under skills/, so check-all ignores it)
    ├── SKILL.md                      #   valid frontmatter, scopes ok
    └── rogue_skill/tools.py          #   calls get_client("notify_mcp") — undeclared
registry/
├── entitlements.yaml            # NEW: scope vocabulary (+ illustrative user->scopes)
└── factor_correlation.yaml      # NEW: governance approval record (status: blessed)
common/pyproject.toml            # MODIFY: + pydantic
.github/workflows/ci.yaml        # MODIFY: governance steps in free gate; new keyed eval job
README.md                        # MODIFY: rogue-PR demo + required secrets
```

---

## Task 1: MCP access convention stub + governance package + pydantic dep

**Files:** Create `common/lab_common/mcp.py`, `common/lab_common/governance/__init__.py`; Modify `common/pyproject.toml`.

- [ ] **Step 1: Create `common/lab_common/mcp.py`**

```python
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
```

- [ ] **Step 2: Create empty `common/lab_common/governance/__init__.py`**

(empty file)

- [ ] **Step 3: Add `"pydantic>=2"` to the `dependencies` list in `common/pyproject.toml`, then sync**

Run: `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv sync --all-packages`
Expected: resolves (pydantic likely already present transitively; this pins it). `uv.lock` updates if needed.

- [ ] **Step 4: Verify imports**

Run: `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv run python -c "import lab_common.mcp, lab_common.governance, pydantic; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add common/lab_common/mcp.py common/lab_common/governance/__init__.py common/pyproject.toml uv.lock
git commit -m "feat: MCP get_client convention stub + governance package + pydantic dep"
```

---

## Task 2: Frontmatter schema validation

**Files:** Create `common/lab_common/governance/frontmatter.py`; Test `common/tests/test_governance_frontmatter.py`.

- [ ] **Step 1: Write the failing test `common/tests/test_governance_frontmatter.py`**

```python
from lab_common.governance.frontmatter import check_frontmatter
from lab_common.models import SkillSpec


def _spec(**over) -> SkillSpec:
    base = dict(
        name="x", version="0.1.0", owner="egor", blast_radius="low",
        allowed_mcp_servers=["data_mcp"], required_scopes=["prices:read"],
        golden_set="evals/golden.yaml", threshold=0.8, system_prompt="body",
    )
    base.update(over)
    return SkillSpec(**base)


def test_valid_frontmatter_has_no_errors():
    assert check_frontmatter(_spec()) == []


def test_bad_blast_radius_is_rejected():
    errs = check_frontmatter(_spec(blast_radius="catastrophic"))
    assert any("blast_radius" in e for e in errs)


def test_threshold_out_of_range_is_rejected():
    assert any("threshold" in e for e in check_frontmatter(_spec(threshold=1.5)))


def test_empty_owner_is_rejected():
    assert any("owner" in e for e in check_frontmatter(_spec(owner="")))
```

- [ ] **Step 2: Run** — `uv run pytest common/tests/test_governance_frontmatter.py -v` → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write `common/lab_common/governance/frontmatter.py`**

```python
"""Validate a skill's frontmatter contract with a Pydantic schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from lab_common.models import SkillSpec


class Frontmatter(BaseModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    blast_radius: Literal["negligible", "low", "medium", "high"]
    allowed_mcp_servers: list[str]
    required_scopes: list[str]
    golden_set: str = Field(min_length=1)
    threshold: float

    @field_validator("threshold")
    @classmethod
    def _threshold_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")
        return v


def check_frontmatter(spec: SkillSpec) -> list[str]:
    """Return a list of human-readable validation errors ([] if valid)."""
    try:
        Frontmatter(
            name=spec.name, version=spec.version, owner=spec.owner,
            blast_radius=spec.blast_radius, allowed_mcp_servers=spec.allowed_mcp_servers,
            required_scopes=spec.required_scopes, golden_set=spec.golden_set,
            threshold=spec.threshold,
        )
    except ValidationError as exc:
        return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
    return []
```

- [ ] **Step 4: Run** — `uv run pytest common/tests/test_governance_frontmatter.py -v` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add common/lab_common/governance/frontmatter.py common/tests/test_governance_frontmatter.py
git commit -m "feat: frontmatter schema validation (governance gate 1)"
```

---

## Task 3: Blast-radius AST scanner + rogue fixture

**Files:** Create `common/lab_common/governance/blast_radius.py`, `common/tests/fixtures/rogue_skill/SKILL.md`, `common/tests/fixtures/rogue_skill/rogue_skill/tools.py`; Test `common/tests/test_governance_blast_radius.py`.

- [ ] **Step 1: Create the rogue fixture — `common/tests/fixtures/rogue_skill/SKILL.md`** (valid frontmatter; the violation is in the code, not here)

```markdown
---
name: rogue_skill
version: 0.1.0
owner: egor
blast_radius: low
allowed_mcp_servers: [data_mcp]
required_scopes: [prices:read]
eval:
  golden_set: evals/golden.yaml
  threshold: 0.8
---

# Rogue Skill

Its frontmatter declares only data_mcp, but its code reaches an undeclared MCP server.
```

- [ ] **Step 2: Create `common/tests/fixtures/rogue_skill/rogue_skill/tools.py`**

```python
"""Looks innocent; reaches a server the frontmatter never declared."""

from lab_common.mcp import get_client


def notify_user(message: str):
    client = get_client("notify_mcp")  # undeclared — only data_mcp is allowed
    return client.post(message)
```

- [ ] **Step 3: Write the failing test `common/tests/test_governance_blast_radius.py`**

```python
from pathlib import Path

from lab_common.governance.blast_radius import check_blast_radius, referenced_mcp_servers
from lab_common.skill_spec import load_skill

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR = REPO_ROOT / "skills" / "factor_correlation"
ROGUE = Path(__file__).resolve().parent / "fixtures" / "rogue_skill"


def test_factor_correlation_references_no_servers():
    # Laptop-context skill: tools read parquet directly, no get_client calls.
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
        "def f(name):\n    return get_client(name)\n"  # non-literal arg
    )
    _, warnings = referenced_mcp_servers(pkg)
    assert any("non-literal" in w for w in warnings)
```

- [ ] **Step 4: Run** — `uv run pytest common/tests/test_governance_blast_radius.py -v` → FAIL (ModuleNotFoundError).

- [ ] **Step 5: Write `common/lab_common/governance/blast_radius.py`**

```python
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
    for py in sorted(Path(skill_dir).rglob("*.py")):
        if "tests" in py.parts:
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
```

- [ ] **Step 6: Run** — `uv run pytest common/tests/test_governance_blast_radius.py -v` → 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add common/lab_common/governance/blast_radius.py common/tests/fixtures/rogue_skill common/tests/test_governance_blast_radius.py
git commit -m "feat: blast-radius AST scan (governance gate 2) + rogue_skill fixture"
```

---

## Task 4: Scope-vocabulary validation + entitlements.yaml

**Files:** Create `registry/entitlements.yaml`, `common/lab_common/governance/scopes.py`; Test `common/tests/test_governance_scopes.py`.

- [ ] **Step 1: Create `registry/entitlements.yaml`**

```yaml
# The scope vocabulary the platform recognizes — the ceiling skills draw required_scopes
# from. (The user->scopes map is illustrative; M5 uses it to mint capability tokens.)
scopes:
  - prices:read
  - fundamentals:read
  - query:run
  - kb:read
  - kb:write

users:
  egor: [prices:read, fundamentals:read, query:run, kb:read, kb:write]
```

- [ ] **Step 2: Write the failing test `common/tests/test_governance_scopes.py`**

```python
from pathlib import Path

from lab_common.governance.scopes import check_scopes, load_scope_vocab
from lab_common.models import SkillSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTITLEMENTS = REPO_ROOT / "registry" / "entitlements.yaml"


def _spec(scopes):
    return SkillSpec("x", "0.1.0", "e", "low", ["data_mcp"], scopes, "evals/golden.yaml", 0.8, "b")


def test_vocab_loads():
    vocab = load_scope_vocab(ENTITLEMENTS)
    assert "prices:read" in vocab and "kb:write" in vocab


def test_known_scopes_pass():
    vocab = load_scope_vocab(ENTITLEMENTS)
    assert check_scopes(_spec(["prices:read"]), vocab) == []


def test_unknown_scope_is_rejected():
    vocab = load_scope_vocab(ENTITLEMENTS)
    errs = check_scopes(_spec(["prices:read", "trading:write"]), vocab)
    assert any("trading:write" in e for e in errs)
```

- [ ] **Step 3: Run** — FAIL (ModuleNotFoundError). **Step 4: Write `common/lab_common/governance/scopes.py`**

```python
"""Validate a skill's required_scopes against the platform scope vocabulary."""

from __future__ import annotations

from pathlib import Path

import yaml

from lab_common.models import SkillSpec


def load_scope_vocab(entitlements_path: str | Path) -> set[str]:
    data = yaml.safe_load(Path(entitlements_path).read_text()) or {}
    return set(data.get("scopes", []))


def check_scopes(spec: SkillSpec, vocab: set[str]) -> list[str]:
    return [
        f"unknown scope '{s}' (not in the entitlements vocabulary)"
        for s in spec.required_scopes
        if s not in vocab
    ]
```

- [ ] **Step 5: Run** — `uv run pytest common/tests/test_governance_scopes.py -v` → 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add registry/entitlements.yaml common/lab_common/governance/scopes.py common/tests/test_governance_scopes.py
git commit -m "feat: scope-vocabulary validation (governance gate 3) + entitlements.yaml"
```

---

## Task 5: Registry reconcile (git → registry.json deployed state)

**Files:** Create `registry/factor_correlation.yaml`, `common/lab_common/governance/reconcile.py`; Test `common/tests/test_governance_reconcile.py`.

- [ ] **Step 1: Create `registry/factor_correlation.yaml`** (must AGREE with the SKILL.md frontmatter)

```yaml
# Governance approval record (the stand-in for a council sign-off). git is the source of
# truth; reconcile.py emits registry.json (deployed state). A skill is `blessed` only when
# this record and the SKILL.md frontmatter agree.
name: factor_correlation
version: 0.1.0
owner: egor
blast_radius: low
allowed_mcp_servers: [data_mcp]
required_scopes: [prices:read]
status: blessed
```

- [ ] **Step 2: Write the failing test `common/tests/test_governance_reconcile.py`**

```python
from pathlib import Path

import yaml

from lab_common.governance.reconcile import reconcile_all, reconcile_skill

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR = REPO_ROOT / "skills" / "factor_correlation"
FACTOR_REG = REPO_ROOT / "registry" / "factor_correlation.yaml"


def test_agreeing_skill_is_blessed():
    rec = reconcile_skill(FACTOR, FACTOR_REG, source_commit="abc123")
    assert rec["status"] == "blessed"
    assert rec["agreement_errors"] == []
    assert rec["source_commit"] == "abc123"


def test_disagreeing_registry_downgrades_to_candidate(tmp_path: Path):
    bad = tmp_path / "factor_correlation.yaml"
    bad.write_text(yaml.safe_dump({
        "name": "factor_correlation", "version": "0.1.0", "owner": "egor",
        "blast_radius": "high",  # disagrees with SKILL.md (low)
        "allowed_mcp_servers": ["data_mcp"], "required_scopes": ["prices:read"],
        "status": "blessed",
    }))
    rec = reconcile_skill(FACTOR, bad, source_commit="x")
    assert rec["status"] == "candidate"
    assert any("blast_radius" in e for e in rec["agreement_errors"])


def test_reconcile_all_emits_records():
    report = reconcile_all(REPO_ROOT / "skills", REPO_ROOT / "registry", "sha")
    names = {r["name"] for r in report["skills"]}
    assert "factor_correlation" in names
```

- [ ] **Step 3: Run** — FAIL (ModuleNotFoundError). **Step 4: Write `common/lab_common/governance/reconcile.py`**

```python
"""Reconcile git-declared state (SKILL.md frontmatter + registry/<skill>.yaml) into a
deployed-state record. A skill is `blessed` only when the two agree."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from lab_common.models import SkillSpec
from lab_common.skill_spec import load_skill

_AGREE_FIELDS = ("name", "version", "blast_radius", "allowed_mcp_servers", "required_scopes")


def _agreement_errors(spec: SkillSpec, record: dict[str, Any]) -> list[str]:
    errors = []
    for field in _AGREE_FIELDS:
        sv = getattr(spec, field)
        rv = record.get(field)
        sv_n = list(sv) if isinstance(sv, list) else sv
        rv_n = list(rv) if isinstance(rv, list) else rv
        if sv_n != rv_n:
            errors.append(f"{field}: SKILL.md={sv_n!r} != registry={rv_n!r}")
    return errors


def reconcile_skill(skill_dir: str | Path, registry_path: str | Path, source_commit: str) -> dict[str, Any]:
    spec = load_skill(skill_dir)
    record = yaml.safe_load(Path(registry_path).read_text()) or {}
    errors = _agreement_errors(spec, record)
    declared = record.get("status", "candidate")
    # blessed requires agreement; any disagreement forces candidate.
    status = declared if not errors else "candidate"
    return {
        "name": spec.name, "version": spec.version, "owner": spec.owner,
        "blast_radius": spec.blast_radius, "allowed_mcp_servers": spec.allowed_mcp_servers,
        "required_scopes": spec.required_scopes, "source_commit": source_commit,
        "status": status, "agreement_errors": errors,
    }


def reconcile_all(skills_dir: str | Path, registry_dir: str | Path, source_commit: str) -> dict[str, Any]:
    skills_dir, registry_dir = Path(skills_dir), Path(registry_dir)
    records: list[dict[str, Any]] = []
    for skill_path in sorted(p for p in skills_dir.iterdir() if (p / "SKILL.md").exists()):
        reg = registry_dir / f"{skill_path.name}.yaml"
        if not reg.exists():
            records.append({"name": skill_path.name, "status": "candidate",
                            "agreement_errors": [f"no registry record at {reg}"]})
        else:
            records.append(reconcile_skill(skill_path, reg, source_commit))
    return {"skills": records}
```

- [ ] **Step 5: Run** — `uv run pytest common/tests/test_governance_reconcile.py -v` → 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add registry/factor_correlation.yaml common/lab_common/governance/reconcile.py common/tests/test_governance_reconcile.py
git commit -m "feat: registry reconcile (governance gate 4) + factor_correlation approval record"
```

---

## Task 6: Governance CLI + the rogue rejection demo

**Files:** Create `common/lab_common/governance/cli.py`; Test `common/tests/test_governance_cli.py`.

- [ ] **Step 1: Write the failing test `common/tests/test_governance_cli.py`**

```python
from pathlib import Path

from lab_common.governance.cli import check_skill

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR = REPO_ROOT / "skills" / "factor_correlation"
ROGUE = Path(__file__).resolve().parent / "fixtures" / "rogue_skill"
ENTITLEMENTS = REPO_ROOT / "registry" / "entitlements.yaml"


def test_factor_passes_all_gates():
    results = check_skill(FACTOR, ENTITLEMENTS)
    assert results["frontmatter"] == []
    assert results["blast_radius"] == []
    assert results["scopes"] == []


def test_rogue_passes_frontmatter_and_scopes_but_fails_blast_radius():
    # The demo: gates 1 (frontmatter) and 3 (scopes) pass; gate 2 (blast_radius) fails.
    results = check_skill(ROGUE, ENTITLEMENTS)
    assert results["frontmatter"] == []
    assert results["scopes"] == []
    assert any("notify_mcp" in e for e in results["blast_radius"])
```

- [ ] **Step 2: Run** — FAIL (ModuleNotFoundError). **Step 3: Write `common/lab_common/governance/cli.py`**

```python
"""Governance CLI: run the gates over a skill (or all skills), and reconcile the registry.

  python -m lab_common.governance.cli check <skill_dir>
  python -m lab_common.governance.cli check-all [--skills skills]
  python -m lab_common.governance.cli reconcile [--out registry.json]

Exits non-zero on any violation / disagreement, so CI can gate on it."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from lab_common.governance.blast_radius import check_blast_radius
from lab_common.governance.frontmatter import check_frontmatter
from lab_common.governance.reconcile import reconcile_all
from lab_common.governance.scopes import check_scopes, load_scope_vocab
from lab_common.skill_spec import load_skill

DEFAULT_ENTITLEMENTS = "registry/entitlements.yaml"


def check_skill(skill_dir: str | Path, entitlements: str | Path) -> dict[str, list[str]]:
    spec = load_skill(skill_dir)
    vocab = load_scope_vocab(entitlements)
    return {
        "frontmatter": check_frontmatter(spec),
        "blast_radius": check_blast_radius(spec, skill_dir),
        "scopes": check_scopes(spec, vocab),
    }


def _print_skill(name: str, results: dict[str, list[str]]) -> bool:
    ok = True
    for gate, errs in results.items():
        if errs:
            ok = False
            for e in errs:
                print(f"  [FAIL] {name} / {gate}: {e}")
        else:
            print(f"  [pass] {name} / {gate}")
    return ok


def _source_commit() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Skill governance gates")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check")
    c.add_argument("skill_dir")
    c.add_argument("--entitlements", default=DEFAULT_ENTITLEMENTS)

    ca = sub.add_parser("check-all")
    ca.add_argument("--skills", default="skills")
    ca.add_argument("--entitlements", default=DEFAULT_ENTITLEMENTS)

    r = sub.add_parser("reconcile")
    r.add_argument("--skills", default="skills")
    r.add_argument("--registry", default="registry")
    r.add_argument("--out", type=Path)

    args = parser.parse_args()

    if args.cmd == "check":
        ok = _print_skill(Path(args.skill_dir).name, check_skill(args.skill_dir, args.entitlements))
        sys.exit(0 if ok else 1)

    if args.cmd == "check-all":
        all_ok = True
        for skill in sorted(d for d in Path(args.skills).iterdir() if (d / "SKILL.md").exists()):
            all_ok = _print_skill(skill.name, check_skill(skill, args.entitlements)) and all_ok
        sys.exit(0 if all_ok else 1)

    if args.cmd == "reconcile":
        report = reconcile_all(args.skills, args.registry, _source_commit())
        bad = False
        for rec in report["skills"]:
            errs = rec.get("agreement_errors") or []
            bad = bad or bool(errs)
            tail = (" ERRORS: " + "; ".join(errs)) if errs else ""
            print(f"  {rec['name']}: status={rec.get('status')}{tail}")
        if args.out:
            args.out.write_text(json.dumps(report, indent=2))
            print(f"wrote {args.out}")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run** — `uv run pytest common/tests/test_governance_cli.py -v` → 2 PASS.

- [ ] **Step 5: Exercise the CLI end to end locally**

```bash
cd /Users/ukran1um/Projects/learning/skills-platform-lab
uv run python -m lab_common.governance.cli check-all          # expect all [pass], exit 0
uv run python -m lab_common.governance.cli check common/tests/fixtures/rogue_skill ; echo "exit=$?"   # expect blast_radius FAIL, exit=1
uv run python -m lab_common.governance.cli reconcile --out /tmp/registry.json   # factor_correlation: status=blessed, exit 0
```
Expected: `check-all` green; the rogue check prints `[FAIL] rogue_skill / blast_radius: reaches undeclared MCP server 'notify_mcp' …` and exits 1; reconcile prints `factor_correlation: status=blessed`.

- [ ] **Step 6: Run the full gate + commit**

Run: `uv run ruff check . && uv run mypy . && uv run pytest -q` → all green.

```bash
git add common/lab_common/governance/cli.py common/tests/test_governance_cli.py
git commit -m "feat: governance CLI (check/check-all/reconcile) + rogue rejection demo test"
```

---

## Task 7: Wire governance into the free CI gate

**Files:** Modify `.github/workflows/ci.yaml`.

- [ ] **Step 1: Add governance + reconcile steps to the existing `checks` job** — after the `Unit tests` step, append:

```yaml
      - name: Governance gates
        run: uv run python -m lab_common.governance.cli check-all
      - name: Registry reconcile
        run: uv run python -m lab_common.governance.cli reconcile --out registry.json
      - name: Upload registry.json
        uses: actions/upload-artifact@v4
        with:
          name: registry
          path: registry.json
```

These are keyless and deterministic — they stay in the free gate.

- [ ] **Step 2: Verify locally exactly as CI runs**

Run: `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv run ruff check . && uv run mypy . && uv run pytest -q && uv run python -m lab_common.governance.cli check-all && uv run python -m lab_common.governance.cli reconcile --out registry.json && echo OK`
Expected: `OK`. (`registry.json` is generated; add it to `.gitignore`.)

- [ ] **Step 3: Gitignore the generated artifact** — append `registry.json` to `.gitignore`.

- [ ] **Step 4: Commit, push, watch CI**

```bash
git add .github/workflows/ci.yaml .gitignore
git commit -m "ci: run governance gates + registry reconcile in the free gate"
git push && gh run watch "$(gh run list --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status --interval 10
```
Expected: green.

---

## Task 8: Keyed eval CI job + secrets + branch protection + README demo

**Files:** Modify `.github/workflows/ci.yaml`, `README.md`. Some steps are user-run (outward-facing).

- [ ] **Step 1: Add a second job to `.github/workflows/ci.yaml`** (the keyed eval gate; runs after `checks`)

```yaml
  eval:
    runs-on: ubuntu-latest
    needs: checks
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - name: Install Claude CLI (the Agent SDK spawns it)
        run: npm install -g @anthropic-ai/claude-code
      - name: Sync workspace
        run: uv sync --all-packages
      - name: Eval gate (live Agent SDK + DeepEval)
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: uv run pytest -m eval -q
```

Note: the live eval test `skipif`s when `ANTHROPIC_API_KEY` is absent, so this job is green-by-skip until secrets are set — it won't block before you configure them.

- [ ] **Step 2: Verify the workflow YAML parses + push**

Run: `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yaml')); print('yaml ok')"`
Expected: `yaml ok`.

```bash
git add .github/workflows/ci.yaml
git commit -m "ci: keyed eval job (Node + claude CLI + secrets) running the live DeepEval gate"
git push && gh run watch "$(gh run list --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status --interval 10
```
Expected: `checks` green; `eval` green (the live test skips without secrets, or runs if you've set them).

- [ ] **Step 3 (user-run, outward-facing): set the Actions secrets from `.env`** so the eval job actually runs the gate. Confirm before running.

```bash
cd /Users/ukran1um/Projects/learning/skills-platform-lab
gh secret set ANTHROPIC_API_KEY --body "$(grep '^ANTHROPIC_API_KEY=' .env | cut -d= -f2-)"
gh secret set OPENAI_API_KEY    --body "$(grep '^OPENAI_API_KEY=' .env | cut -d= -f2-)"
gh secret list
```

- [ ] **Step 4 (user-run, outward-facing): branch protection** — require the `checks` status and PRs on `main`. Confirm before running.

```bash
gh api -X PUT repos/ukran1um/skills-platform-lab/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[contexts][]=checks' \
  -f 'enforce_admins=false' \
  -f 'required_pull_request_reviews[required_approving_review_count]=0' \
  -f 'restrictions='
```
(Solo repo: `required_approving_review_count=0` keeps you unblocked while still requiring green `checks`. Raise it later if you want mandatory review.)

- [ ] **Step 5: Document the rogue-PR demo + secrets in `README.md`** — add a "Governance (M3)" section:

```markdown
## Governance (CI as the gate)

Every push runs four keyless gates (`lab_common.governance.cli check-all` + `reconcile`):
frontmatter schema, blast-radius AST scan, scope vocabulary, and registry reconcile
(git → `registry.json`; a skill is `blessed` only when SKILL.md and `registry/<skill>.yaml`
agree). A separate keyed `eval` job runs the live Agent-SDK + DeepEval gate (needs the
`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` Actions secrets and installs the `claude` CLI).

### The rogue-skill demo
`common/tests/fixtures/rogue_skill/` has clean frontmatter and valid scopes but its code
calls `get_client("notify_mcp")`, a server it never declared. `governance.cli check` passes
gates 1 and 3 and fails gate 2:

    uv run python -m lab_common.governance.cli check common/tests/fixtures/rogue_skill

To see CI reject it as a PR: copy the fixture into `skills/rogue_skill/` on a branch and
open a PR — the `checks` job goes red on the blast-radius gate while its evals would pass.
```

- [ ] **Step 6: Commit + push**

```bash
git add README.md
git commit -m "docs: governance + rogue-PR demo + required secrets"
git push && gh run watch "$(gh run list --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status --interval 10
```
Expected: green.

**M3 acceptance:** every push runs the four governance gates + reconcile (keyless) and the keyed eval job; `governance.cli check` rejects the rogue fixture on blast-radius while passing frontmatter + scopes; `registry.json` is emitted as an artifact with `factor_correlation: blessed`; branch protection requires green `checks` on main.

---

## Self-review notes (issues found and fixed inline)

- **Spec coverage:** frontmatter validation → Task 2; blast-radius AST scan → Task 3 (+ rogue fixture); scope validation → Task 4 (+ entitlements.yaml); registry reconcile (git→registry.json, candidate/blessed/deprecated, blessed-only-on-agreement) → Task 5; eval gate in CI → Task 8; rogue rejection demo (passes 1&3, fails 2) → Tasks 3+6; path-filtering — partially: `check-all` runs over all skills (cheap, keyless) and the eval job runs the whole `-m eval` suite; true per-skill path-filtering of the eval job is noted as a later refinement (only one real skill today). Branch protection → Task 8.
- **Type/contract consistency:** `check_frontmatter(spec)`, `check_blast_radius(spec, dir)`, `check_scopes(spec, vocab)`, `referenced_mcp_servers(dir)->(set,list)`, `reconcile_skill(dir, registry_path, source_commit)`, `reconcile_all(skills, registry, sha)`, `check_skill(dir, entitlements)->{gate:[errors]}` are used consistently across modules, the CLI, and tests. The MCP convention `get_client("literal")` is what both `mcp.py` defines and `blast_radius.py` detects and the rogue fixture uses.
- **Placeholder scan:** clean — complete code in every step.
- **Known risks/limits:** (1) Static AST scan is best-effort — a dynamic `get_client(var)` is flagged as a warning/violation, not silently passed; the runtime token + tool-injection layers (M4/M5) are the real backstop, as the spec states. (2) The eval job is green-by-skip until secrets are set, so Task 8 Steps 1–2 don't block before Step 3. (3) `factor_correlation` references no MCP servers yet (laptop context), so its blast-radius check is vacuously clean; it becomes load-bearing when M4 swaps its data access to `get_client("data_mcp")`. (4) Branch protection + secret-setting are outward-facing — flagged user-run/confirm.
