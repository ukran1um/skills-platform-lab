# M2: Eval Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a faithful eval harness that runs the `factor_correlation` skill as a real agent loop and scores each golden case with three check types — deterministic recompute, trajectory assertions, and an LLM judge — so the operational texture of eval gates (judge flakiness, threshold calibration, cost, trajectory-vs-outcome) becomes hands-on.

**Architecture:** A new `lab_common` workspace package holds the reusable pieces the later skill-host (M5) will also use: a `SkillSpec` loader, a generic `agent_runner` (manual Anthropic Messages API tool-use loop with full trajectory capture), three `scorers`, and an `eval_harness` that drives golden cases and emits a JSON report. The skill declares its own agent tool surface (`agent_tools.py`). Evals run in **laptop mode** against the deterministic fixtures parquet (not the live warehouse). Real API calls are isolated to the agent loop and the judge; all loop/scorer logic is unit-tested offline with injected fake clients, and the live calibration run is a user-run checkpoint.

**Tech Stack:** Python 3.12, uv workspace, `anthropic` SDK (Messages API tool-use loop + judge), PyYAML, pandas/pyarrow (independent recompute oracle), pytest. Models: `claude-sonnet-4-6` (agent + judge), `claude-haiku-4-5` as the cheap toggle.

**Spec:** `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md` (Eval harness and CI gates section).

---

## Key design decisions (locked in here; react at the execution-handoff gate if any is wrong)

1. **Substrate = `anthropic` Messages API manual tool-use loop**, not a separate agent SDK. Research (June 2026) found no clean headless `claude-agent-sdk`; the manual loop is pure-Python, CI-safe with only `ANTHROPIC_API_KEY`, and gives full trajectory (tool name + input + result per turn). This runner is the reusable core M5's skill-host wraps with governance — not throwaway.
2. **One agent run per case feeds all three checks.** The agent receives the natural-language case input, calls the skill's `compute_correlation` tool, and narrates following SKILL.md rules. Deterministic extracts the number from the captured tool *result* and recomputes independently; trajectory inspects the tool-call log; judge scores the final narration.
3. **Eval is a separate, paid gate — excluded from the default `pytest` run.** Root pytest config defaults to `-m "not eval"`, so the free M0 CI (`uv run pytest -q`, no API key) stays fast and key-less. Live evals run via the harness CLI or `pytest -m eval`. (This is the M3 story made concrete.)
4. **"pytest plugin" is realized as a library + CLI runner + a marked live test**, the pragmatic and useful interpretation. M3 CI will call the CLI.
5. **Judge robustness via `tool_choice` force-call** (force a `submit_score` tool returning `{score, reasoning}`), the version-stable structured-output pattern — not the newer `messages.parse`/`output_config` APIs.
6. **Live calibration (≥5 runs) is a user-run checkpoint** (Task 9), because implementer subagents won't have `ANTHROPIC_API_KEY`. All non-API logic is fully unit-tested before then.
7. **Carryover A (lab_data test dependency)** is fixed by introducing a workspace-root `conftest.py` that owns the fixtures-parquet fixture, decoupling skill tests from a direct `lab_data` import (standalone-ready for M4). **Carryover B (golden.yaml)** is created in Task 7 when its schema is settled, resolving the dangling `SKILL.md` `eval.golden_set` reference.

---

## File structure after this plan

```
skills-platform-lab/
├── pyproject.toml                       # MODIFY: add "common" to workspace members; add pytest eval marker + addopts
├── conftest.py                          # NEW: root fixtures_parquet session fixture (carryover A)
├── common/
│   ├── pyproject.toml                   # NEW: package lab-common
│   └── lab_common/
│       ├── __init__.py                  # NEW
│       ├── models.py                    # NEW: dataclasses (SkillSpec, ToolCall, RunResult, CheckResult, CaseResult, EvalReport)
│       ├── skill_spec.py                # NEW: load_skill(path) -> SkillSpec
│       ├── agent_runner.py              # NEW: run_skill(...) manual tool-use loop + trajectory
│       ├── scorers.py                   # NEW: score_deterministic / score_trajectory / score_judge
│       └── eval_harness.py              # NEW: load_golden, run_evals, main() CLI
│   └── tests/
│       ├── test_skill_spec.py           # NEW
│       ├── test_agent_runner.py         # NEW (fake client)
│       ├── test_scorers.py              # NEW (fake client for judge)
│       └── test_eval_harness.py         # NEW (fake client, tiny golden)
├── skills/factor_correlation/
│   ├── factor_correlation/agent_tools.py  # NEW: TOOLS + dispatch (the skill's agent tool surface)
│   ├── tests/
│   │   ├── test_agent_tools.py          # NEW
│   │   ├── test_cli.py                  # MODIFY: use root fixtures_parquet fixture (carryover A)
│   │   ├── test_compute.py              # unchanged
│   │   └── test_fetch.py                # MODIFY: use root fixtures_parquet fixture (carryover A)
│   ├── evals/golden.yaml                # NEW (carryover B)
│   └── tests/test_eval_live.py          # NEW: @pytest.mark.eval live smoke (skipped without key)
└── docs/superpowers/plans/...           # this plan
```

Responsibilities: `skill_spec` = parse only; `agent_runner` = the loop + trajectory only (skill-agnostic); `scorers` = scoring only (each check type isolated); `eval_harness` = orchestration + report; `agent_tools` = the skill's tool surface only. No module does two of these.

---

## Task 1: `lab_common` package + workspace wiring

**Files:**
- Create: `common/pyproject.toml`, `common/lab_common/__init__.py`
- Modify: `pyproject.toml` (root)

- [ ] **Step 1: Create `common/pyproject.toml`**

```toml
[project]
name = "lab-common"
version = "0.1.0"
description = "Shared platform lib: skill loader, agent runner, eval harness"
requires-python = ">=3.12"
dependencies = [
    "anthropic>=0.40",
    "pyyaml>=6.0",
    "pandas>=2.2",
    "pyarrow>=16",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["lab_common"]
```

- [ ] **Step 2: Create empty `common/lab_common/__init__.py`**

(empty file)

- [ ] **Step 3: Add `common` to the workspace members in root `pyproject.toml`**

Change the `[tool.uv.workspace]` block from:

```toml
[tool.uv.workspace]
members = ["data", "skills/*"]
```

to:

```toml
[tool.uv.workspace]
members = ["data", "skills/*", "common"]
```

- [ ] **Step 4: Sync the workspace**

Run: `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv sync --all-packages`
Expected: resolves; `lab-common` and `anthropic`/`pyyaml` installed; `uv.lock` updated.

- [ ] **Step 5: Verify import works**

Run: `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv run python -c "import lab_common, anthropic, yaml; print('ok')"`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add common pyproject.toml uv.lock
git commit -m "feat: lab_common workspace package (anthropic, pyyaml, pandas)"
```

---

## Task 2: shared dataclasses (`models.py`)

**Files:**
- Create: `common/lab_common/models.py`
- Test: `common/tests/test_models.py`

- [ ] **Step 1: Write the failing test `common/tests/test_models.py`**

```python
from lab_common.models import (
    CaseResult,
    CheckResult,
    EvalReport,
    RunResult,
    SkillSpec,
    ToolCall,
)


def test_skillspec_fields():
    spec = SkillSpec(
        name="x",
        version="0.1.0",
        owner="egor",
        blast_radius="low",
        allowed_mcp_servers=["data_mcp"],
        required_scopes=["prices:read"],
        golden_set="evals/golden.yaml",
        threshold=0.8,
        system_prompt="do the thing",
    )
    assert spec.name == "x"
    assert spec.threshold == 0.8


def test_runresult_holds_trajectory():
    call = ToolCall(name="t", input={"a": 1}, result='{"r": 2}')
    run = RunResult(final_text="done", trajectory=[call])
    assert run.trajectory[0].name == "t"
    assert run.final_text == "done"


def test_report_aggregates_case_scores():
    cr = CheckResult(type="trajectory", passed=True, score=1.0, detail="")
    case = CaseResult(case_id="c1", checks=[cr], score=1.0)
    report = EvalReport(skill="x", cases=[case], mean_score=1.0, threshold=0.8, passed=True)
    assert report.passed is True
    assert report.cases[0].case_id == "c1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest common/tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lab_common.models'`

- [ ] **Step 3: Write `common/lab_common/models.py`**

```python
"""Plain data carriers shared across the harness. No logic here."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillSpec:
    name: str
    version: str
    owner: str
    blast_radius: str
    allowed_mcp_servers: list[str]
    required_scopes: list[str]
    golden_set: str
    threshold: float
    system_prompt: str


@dataclass
class ToolCall:
    name: str
    input: dict[str, Any]
    result: str | None = None


@dataclass
class RunResult:
    final_text: str | None
    trajectory: list[ToolCall] = field(default_factory=list)

    def called_tools(self) -> list[str]:
        return [c.name for c in self.trajectory]


@dataclass
class CheckResult:
    type: str
    passed: bool
    score: float
    detail: str


@dataclass
class CaseResult:
    case_id: str
    checks: list[CheckResult]
    score: float


@dataclass
class EvalReport:
    skill: str
    cases: list[CaseResult]
    mean_score: float
    threshold: float
    passed: bool
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest common/tests/test_models.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add common/lab_common/models.py common/tests/test_models.py
git commit -m "feat: shared dataclasses for the eval harness"
```

---

## Task 3: SkillSpec loader (`skill_spec.py`)

**Files:**
- Create: `common/lab_common/skill_spec.py`
- Test: `common/tests/test_skill_spec.py`

- [ ] **Step 1: Write the failing test `common/tests/test_skill_spec.py`**

```python
from pathlib import Path

import pytest

from lab_common.skill_spec import load_skill

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR_SKILL = REPO_ROOT / "skills" / "factor_correlation"

SAMPLE = """---
name: demo
version: 1.2.3
owner: tester
blast_radius: medium
allowed_mcp_servers: [data_mcp, research_mcp]
required_scopes: [prices:read]
eval:
  golden_set: evals/golden.yaml
  threshold: 0.7
---

# Demo

System prompt body here.
"""


def test_load_real_factor_skill():
    spec = load_skill(FACTOR_SKILL)
    assert spec.name == "factor_correlation"
    assert spec.blast_radius == "low"
    assert spec.allowed_mcp_servers == ["data_mcp"]
    assert spec.required_scopes == ["prices:read"]
    assert spec.threshold == 0.8
    assert spec.golden_set == "evals/golden.yaml"
    assert "Factor Correlation" in spec.system_prompt  # body captured


def test_load_from_sample(tmp_path: Path):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(SAMPLE)
    spec = load_skill(skill_dir)
    assert spec.version == "1.2.3"
    assert spec.allowed_mcp_servers == ["data_mcp", "research_mcp"]
    assert spec.threshold == 0.7
    assert spec.system_prompt.strip().startswith("# Demo")


def test_missing_frontmatter_raises(tmp_path: Path):
    skill_dir = tmp_path / "broken"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("no frontmatter here")
    with pytest.raises(ValueError, match="frontmatter"):
        load_skill(skill_dir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest common/tests/test_skill_spec.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lab_common.skill_spec'`

- [ ] **Step 3: Write `common/lab_common/skill_spec.py`**

```python
"""Parse a skill's SKILL.md (YAML frontmatter + markdown body) into a SkillSpec."""

from __future__ import annotations

from pathlib import Path

import yaml

from lab_common.models import SkillSpec


def load_skill(skill_dir: str | Path) -> SkillSpec:
    skill_dir = Path(skill_dir)
    text = (skill_dir / "SKILL.md").read_text()
    if not text.startswith("---"):
        raise ValueError(f"{skill_dir}/SKILL.md has no YAML frontmatter")
    # Split on the first two '---' fences.
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{skill_dir}/SKILL.md frontmatter is malformed")
    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].lstrip("\n")
    eval_cfg = meta.get("eval", {}) or {}
    return SkillSpec(
        name=meta["name"],
        version=str(meta["version"]),
        owner=meta.get("owner", ""),
        blast_radius=meta.get("blast_radius", ""),
        allowed_mcp_servers=list(meta.get("allowed_mcp_servers", [])),
        required_scopes=list(meta.get("required_scopes", [])),
        golden_set=eval_cfg.get("golden_set", ""),
        threshold=float(eval_cfg.get("threshold", 0.0)),
        system_prompt=body,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest common/tests/test_skill_spec.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add common/lab_common/skill_spec.py common/tests/test_skill_spec.py
git commit -m "feat: SKILL.md loader (frontmatter contract + system prompt body)"
```

---

## Task 4: Carryover A — root conftest fixtures-parquet + decouple skill tests

**Files:**
- Create: `conftest.py` (repo root)
- Modify: `skills/factor_correlation/tests/test_fetch.py`, `skills/factor_correlation/tests/test_cli.py`

- [ ] **Step 1: Create `conftest.py` at the repo root**

```python
"""Workspace-wide pytest fixtures.

`fixtures_parquet` owns the deterministic synthetic warehouse so individual skill
tests don't import lab_data directly (keeps skills standalone-extractable for M4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lab_data.fixtures import write_parquet


@pytest.fixture(scope="session")
def fixtures_parquet(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("warehouse") / "prices.parquet"
    return write_parquet(path)
```

- [ ] **Step 2: Refactor `skills/factor_correlation/tests/test_fetch.py` to use the fixture**

Replace the entire file with:

```python
from datetime import date
from pathlib import Path

import pytest

from factor_correlation.tools.fetch import get_prices


def test_get_prices_filters_tickers_and_dates(fixtures_parquet: Path):
    df = get_prices(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 3, 31), parquet=fixtures_parquet)
    assert set(df["ticker"]) == {"AAPL", "MSFT"}
    assert df["date"].min() >= date(2025, 1, 1)
    assert df["date"].max() <= date(2025, 3, 31)
    assert list(df.columns) == ["ticker", "date", "close"]


def test_get_prices_is_case_insensitive(fixtures_parquet: Path):
    df = get_prices(["aapl"], date(2025, 1, 1), date(2025, 1, 31), parquet=fixtures_parquet)
    assert set(df["ticker"]) == {"AAPL"}


def test_get_prices_missing_warehouse_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="warehouse parquet not found"):
        get_prices(["AAPL"], date(2025, 1, 1), date(2025, 1, 31), parquet=tmp_path / "nope.parquet")
```

- [ ] **Step 3: Refactor `skills/factor_correlation/tests/test_cli.py` to use the fixture**

Replace the entire file with:

```python
import json
from datetime import date
from pathlib import Path

import pytest

from factor_correlation.cli import run


def test_run_accepts_parquet_kwarg(fixtures_parquet: Path):
    result = run(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)
    assert result["tickers"] == ["AAPL", "MSFT"]
    assert "correlation_value" in result


def test_run_two_tickers_has_correlation_value(fixtures_parquet: Path):
    result = run(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)
    assert result["tickers"] == ["AAPL", "MSFT"]
    assert "correlation_value" in result
    assert -1.0 <= result["correlation_value"] <= 1.0
    assert result["matrix"]["AAPL"]["MSFT"] == result["correlation_value"]
    json.dumps(result)  # JSON-serializable


def test_run_three_tickers_matrix_only(fixtures_parquet: Path):
    result = run(["AAPL", "MSFT", "NVDA"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)
    assert "correlation_value" not in result
    assert set(result["matrix"].keys()) == {"AAPL", "MSFT", "NVDA"}
    assert result["matrix"]["AAPL"]["AAPL"] == pytest.approx(1.0)


def test_run_unknown_ticker_exits(fixtures_parquet: Path):
    with pytest.raises(SystemExit, match="no price data"):
        run(["ZZZTOP"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)


def test_run_partial_unknown_exits(fixtures_parquet: Path):
    with pytest.raises(SystemExit, match="ZZZTOP"):
        run(["AAPL", "ZZZTOP"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)
```

Note: these now pass `parquet=fixtures_parquet` explicitly (no env monkeypatching), which exercises the `parquet=` seam added at the end of M1.

- [ ] **Step 4: Run the affected tests + full suite**

Run: `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv run pytest skills/factor_correlation/tests/test_fetch.py skills/factor_correlation/tests/test_cli.py -v`
Expected: all PASS (5 cli + 3 fetch). Then `uv run pytest -q` → all green (no `lab_data` import remains in the skill test files: confirm with `grep -rn "import lab_data" skills/` returning nothing).

- [ ] **Step 5: Commit**

```bash
git add conftest.py skills/factor_correlation/tests/test_fetch.py skills/factor_correlation/tests/test_cli.py
git commit -m "refactor: root fixtures_parquet fixture; decouple skill tests from lab_data (carryover A)"
```

---

## Task 5: skill agent tool surface (`agent_tools.py`)

**Files:**
- Create: `skills/factor_correlation/factor_correlation/agent_tools.py`
- Test: `skills/factor_correlation/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing test `skills/factor_correlation/tests/test_agent_tools.py`**

```python
import json
from pathlib import Path

from factor_correlation.agent_tools import TOOLS, dispatch


def test_tools_catalog_shape():
    assert len(TOOLS) == 1
    tool = TOOLS[0]
    assert tool["name"] == "compute_correlation"
    assert "tickers" in tool["input_schema"]["properties"]
    assert tool["input_schema"]["required"] == ["tickers", "start", "end"]


def test_dispatch_returns_correlation_json(fixtures_parquet: Path):
    out = dispatch(
        "compute_correlation",
        {"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
        {"parquet": fixtures_parquet},
    )
    data = json.loads(out)
    assert data["tickers"] == ["AAPL", "MSFT"]
    assert -1.0 <= data["correlation_value"] <= 1.0


def test_dispatch_unknown_ticker_returns_error_not_raises(fixtures_parquet: Path):
    out = dispatch(
        "compute_correlation",
        {"tickers": ["ZZZTOP"], "start": "2025-01-01", "end": "2025-06-30"},
        {"parquet": fixtures_parquet},
    )
    data = json.loads(out)
    assert "error" in data  # the agent must be able to narrate the refusal


def test_dispatch_unknown_tool_returns_error(fixtures_parquet: Path):
    out = dispatch("nope", {}, {"parquet": fixtures_parquet})
    assert "error" in json.loads(out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest skills/factor_correlation/tests/test_agent_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'factor_correlation.agent_tools'`

- [ ] **Step 3: Write `skills/factor_correlation/factor_correlation/agent_tools.py`**

```python
"""The skill's agent-facing tool surface.

The agent runner exposes these tools to Claude; in laptop/eval mode they read the
fixtures parquet via the `parquet` context. Tool results are JSON strings (the
Messages API requires tool_result content to be a string).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from factor_correlation.cli import run

TOOLS: list[dict[str, Any]] = [
    {
        "name": "compute_correlation",
        "description": (
            "Compute the Pearson correlation of daily returns between two or more "
            "tickers over a date range. Returns a correlation matrix, and for exactly "
            "two tickers a top-level correlation_value."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ticker symbols, e.g. ['AAPL', 'MSFT']",
                },
                "start": {"type": "string", "description": "Start date ISO YYYY-MM-DD"},
                "end": {"type": "string", "description": "End date ISO YYYY-MM-DD"},
            },
            "required": ["tickers", "start", "end"],
        },
    }
]


def _compute_correlation(inputs: dict[str, Any], context: dict[str, Any]) -> str:
    parquet = context.get("parquet")
    parquet = Path(parquet) if parquet else None
    try:
        result = run(
            list(inputs["tickers"]),
            date.fromisoformat(inputs["start"]),
            date.fromisoformat(inputs["end"]),
            parquet=parquet,
        )
    except SystemExit as exc:  # missing/partial tickers, empty range
        return json.dumps({"error": str(exc)})
    return json.dumps(result)


def dispatch(name: str, inputs: dict[str, Any], context: dict[str, Any]) -> str:
    if name == "compute_correlation":
        return _compute_correlation(inputs, context)
    return json.dumps({"error": f"unknown tool: {name}"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest skills/factor_correlation/tests/test_agent_tools.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add skills/factor_correlation/factor_correlation/agent_tools.py skills/factor_correlation/tests/test_agent_tools.py
git commit -m "feat: factor_correlation agent tool surface (compute_correlation)"
```

---

## Task 6: agent runner (`agent_runner.py`)

**Files:**
- Create: `common/lab_common/agent_runner.py`
- Test: `common/tests/test_agent_runner.py`

- [ ] **Step 1: Write the failing test `common/tests/test_agent_runner.py`** (fake client — no API)

```python
from types import SimpleNamespace

from lab_common.agent_runner import run_skill
from lab_common.models import SkillSpec

SPEC = SkillSpec(
    name="demo",
    version="0.1.0",
    owner="t",
    blast_radius="low",
    allowed_mcp_servers=[],
    required_scopes=[],
    golden_set="",
    threshold=0.0,
    system_prompt="You are a demo agent.",
)

TOOLS = [{"name": "echo", "description": "echo", "input_schema": {"type": "object", "properties": {}}}]


def _block(type_, **kw):
    return SimpleNamespace(type=type_, **kw)


class FakeClient:
    """Yields a scripted sequence of responses, one per create() call."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = self  # so client.messages.create works

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _dispatch(name, inputs, context):
    return '{"echoed": true}'


def test_runner_captures_tool_call_and_final_text():
    responses = [
        SimpleNamespace(
            stop_reason="tool_use",
            content=[_block("tool_use", name="echo", input={"x": 1}, id="tu_1")],
        ),
        SimpleNamespace(
            stop_reason="end_turn",
            content=[_block("text", text="all done")],
        ),
    ]
    client = FakeClient(responses)
    result = run_skill(SPEC, "do it", TOOLS, _dispatch, client=client, context={"parquet": None})
    assert result.final_text == "all done"
    assert result.called_tools() == ["echo"]
    assert result.trajectory[0].input == {"x": 1}
    assert result.trajectory[0].result == '{"echoed": true}'
    # system prompt threaded through
    assert client.calls[0]["system"] == "You are a demo agent."
    # tool_result message appended before the second create call
    assert client.calls[1]["messages"][-1]["content"][0]["type"] == "tool_result"


def test_runner_respects_max_turns():
    # Always returns tool_use -> would loop forever without the cap.
    looping = [
        SimpleNamespace(
            stop_reason="tool_use",
            content=[_block("tool_use", name="echo", input={}, id=f"tu_{i}")],
        )
        for i in range(10)
    ]
    client = FakeClient(looping)
    result = run_skill(
        SPEC, "loop", TOOLS, _dispatch, client=client, context={}, max_turns=3
    )
    assert len(client.calls) == 3  # stopped at the cap
    assert len(result.trajectory) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest common/tests/test_agent_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lab_common.agent_runner'`

- [ ] **Step 3: Write `common/lab_common/agent_runner.py`**

```python
"""Generic agent loop over the Anthropic Messages API with full trajectory capture.

Skill-agnostic: the caller supplies the tool catalog (JSON-schema dicts) and a
`dispatch(name, inputs, context) -> str` function. This is the runner the M5
skill-host will reuse (swapping local dispatch for MCP-client dispatch + tokens).
"""

from __future__ import annotations

from typing import Any, Callable

from lab_common.models import RunResult, SkillSpec, ToolCall

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TURNS = 8

DispatchFn = Callable[[str, dict[str, Any], dict[str, Any]], str]


def run_skill(
    spec: SkillSpec,
    user_input: str,
    tools: list[dict[str, Any]],
    dispatch: DispatchFn,
    *,
    client: Any,
    context: dict[str, Any] | None = None,
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_tokens: int = 2048,
) -> RunResult:
    context = context or {}
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_input}]
    trajectory: list[ToolCall] = []
    final_text: str | None = None

    for _ in range(max_turns):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=spec.system_prompt,
            tools=tools,
            messages=messages,
        )
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        texts = [b for b in response.content if b.type == "text"]
        if texts:
            final_text = texts[-1].text

        if response.stop_reason != "tool_use" or not tool_uses:
            break

        tool_results = []
        for block in tool_uses:
            out = dispatch(block.name, dict(block.input), context)
            trajectory.append(ToolCall(name=block.name, input=dict(block.input), result=out))
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": out}
            )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return RunResult(final_text=final_text, trajectory=trajectory)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest common/tests/test_agent_runner.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add common/lab_common/agent_runner.py common/tests/test_agent_runner.py
git commit -m "feat: generic agent runner (Messages API tool-use loop + trajectory)"
```

---

## Task 7: scorers (`scorers.py`)

**Files:**
- Create: `common/lab_common/scorers.py`
- Test: `common/tests/test_scorers.py`

- [ ] **Step 1: Write the failing test `common/tests/test_scorers.py`**

```python
import json
from pathlib import Path
from types import SimpleNamespace

from lab_common.models import RunResult, ToolCall
from lab_common.scorers import score_deterministic, score_judge, score_trajectory


def test_trajectory_must_call_and_must_not_call():
    run = RunResult(final_text="x", trajectory=[ToolCall("compute_correlation", {}, "{}")])
    ok = score_trajectory(run, {"must_call": ["compute_correlation"], "must_not_call": ["run_query"]})
    assert ok.passed and ok.score == 1.0

    bad = score_trajectory(run, {"must_call": ["get_prices"]})
    assert not bad.passed and bad.score == 0.0


def test_deterministic_recompute_matches(fixtures_parquet: Path):
    # Build a trajectory whose tool result is the skill's real output for AAPL/MSFT.
    from factor_correlation.cli import run as skill_run

    out = skill_run(["AAPL", "MSFT"], _d("2025-01-01"), _d("2025-06-30"), parquet=fixtures_parquet)
    run = RunResult(
        final_text="...",
        trajectory=[
            ToolCall(
                "compute_correlation",
                {"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
                json.dumps(out),
            )
        ],
    )
    res = score_deterministic(
        run,
        {"tool": "compute_correlation", "field": "correlation_value", "tolerance": 0.01},
        context={"parquet": fixtures_parquet},
    )
    assert res.passed and res.score == 1.0


def test_deterministic_catches_wrong_number(fixtures_parquet: Path):
    run = RunResult(
        final_text="...",
        trajectory=[
            ToolCall(
                "compute_correlation",
                {"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
                json.dumps({"correlation_value": 0.999}),  # fabricated
            )
        ],
    )
    res = score_deterministic(
        run,
        {"tool": "compute_correlation", "field": "correlation_value", "tolerance": 0.01},
        context={"parquet": fixtures_parquet},
    )
    assert not res.passed


def test_judge_takes_median_of_runs():
    class FakeJudge:
        def __init__(self, scores):
            self._scores = list(scores)
            self.messages = self

        def create(self, **kwargs):
            score = self._scores.pop(0)
            return SimpleNamespace(
                content=[SimpleNamespace(type="tool_use", name="submit_score",
                                         input={"score": score, "reasoning": "r"})]
            )

    client = FakeJudge([0.9, 0.4, 0.8])  # median 0.8
    res = score_judge("some narration", {"rubric": "is it good", "min_score": 0.7},
                      client=client, runs=3)
    assert res.score == 0.8
    assert res.passed  # 0.8 >= 0.7


def _d(s: str):
    from datetime import date
    return date.fromisoformat(s)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest common/tests/test_scorers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lab_common.scorers'`

- [ ] **Step 3: Write `common/lab_common/scorers.py`**

```python
"""The three check types. Deterministic + trajectory are pure; judge calls the API.

The deterministic scorer is an INDEPENDENT oracle: it recomputes the correlation
straight from the fixtures parquet with its own pandas math (not the skill's code),
so a regression in the skill's compute path is actually caught.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

import pandas as pd

from lab_common.models import CheckResult, RunResult

JUDGE_MODEL = "claude-sonnet-4-6"

_SUBMIT_SCORE_TOOL = {
    "name": "submit_score",
    "description": "Submit your evaluation score (0.0-1.0) and a one-line reasoning.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "number", "description": "0.0 (fails rubric) to 1.0 (fully meets it)"},
            "reasoning": {"type": "string"},
        },
        "required": ["score", "reasoning"],
    },
}


def _find_call(run: RunResult, tool: str):
    for call in run.trajectory:
        if call.name == tool:
            return call
    return None


def _independent_pearson(parquet: Path, tickers: list[str], start: str, end: str) -> float:
    df = pd.read_parquet(parquet)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    mask = (
        df["ticker"].isin([t.upper() for t in tickers])
        & (df["date"] >= pd.to_datetime(start).date())
        & (df["date"] <= pd.to_datetime(end).date())
    )
    wide = df[mask].pivot(index="date", columns="ticker", values="close").sort_index()
    returns = wide.pct_change(fill_method=None).dropna(how="all")
    corr = returns.corr(method="pearson")
    cols = sorted(corr.columns.tolist())
    return float(corr.loc[cols[0], cols[1]])


def score_trajectory(run: RunResult, check: dict[str, Any]) -> CheckResult:
    called = set(run.called_tools())
    must_call = set(check.get("must_call", []))
    must_not = set(check.get("must_not_call", []))
    missing = must_call - called
    forbidden = must_not & called
    passed = not missing and not forbidden
    detail = ""
    if missing:
        detail += f"missing calls: {sorted(missing)}; "
    if forbidden:
        detail += f"forbidden calls present: {sorted(forbidden)}"
    return CheckResult("trajectory", passed, 1.0 if passed else 0.0, detail.strip())


def score_deterministic(
    run: RunResult, check: dict[str, Any], *, context: dict[str, Any]
) -> CheckResult:
    call = _find_call(run, check["tool"])
    if call is None or call.result is None:
        return CheckResult("deterministic", False, 0.0, f"tool {check['tool']} not called")
    data = json.loads(call.result)
    if check["field"] not in data:
        return CheckResult("deterministic", False, 0.0, f"no field {check['field']} ({data})")
    reported = float(data[check["field"]])
    expected = _independent_pearson(
        Path(context["parquet"]), call.input["tickers"], call.input["start"], call.input["end"]
    )
    diff = abs(reported - expected)
    passed = diff <= float(check.get("tolerance", 0.01))
    return CheckResult(
        "deterministic", passed, 1.0 if passed else 0.0,
        f"reported={reported:.6f} expected={expected:.6f} diff={diff:.6f}",
    )


def _judge_once(client: Any, rubric: str, candidate: str) -> float:
    prompt = (
        f"Rubric: {rubric}\n\n"
        f"Candidate response to evaluate:\n\"\"\"\n{candidate}\n\"\"\"\n\n"
        "Score how well the candidate meets the rubric from 0.0 to 1.0 and submit it."
    )
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=300,
        tools=[_SUBMIT_SCORE_TOOL],
        tool_choice={"type": "tool", "name": "submit_score"},
        messages=[{"role": "user", "content": prompt}],
    )
    block = next(b for b in response.content if b.type == "tool_use")
    return float(block.input["score"])


def score_judge(
    candidate: str | None, check: dict[str, Any], *, client: Any, runs: int = 3
) -> CheckResult:
    if not candidate:
        return CheckResult("judge", False, 0.0, "no candidate text to judge")
    scores = [_judge_once(client, check["rubric"], candidate) for _ in range(runs)]
    median = statistics.median(scores)
    min_score = float(check.get("min_score", 0.7))
    passed = median >= min_score
    return CheckResult(
        "judge", passed, median, f"scores={scores} median={median:.3f} min={min_score}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest common/tests/test_scorers.py -v`
Expected: 5 PASS (no API hit — judge test uses the fake client; deterministic uses fixtures parquet)

- [ ] **Step 5: Commit**

```bash
git add common/lab_common/scorers.py common/tests/test_scorers.py
git commit -m "feat: deterministic/trajectory/judge scorers (judge median-of-N)"
```

---

## Task 8: golden.yaml + eval harness orchestrator (`eval_harness.py`)

**Files:**
- Create: `skills/factor_correlation/evals/golden.yaml`, `common/lab_common/eval_harness.py`
- Test: `common/tests/test_eval_harness.py`

- [ ] **Step 1: Create `skills/factor_correlation/evals/golden.yaml`** (resolves the SKILL.md dangling reference — carryover B)

```yaml
cases:
  - id: corr_two_tickers
    input: "How correlated were AAPL and MSFT daily returns from 2025-01-01 to 2025-06-30?"
    checks:
      - type: deterministic
        tool: compute_correlation
        field: correlation_value
        tolerance: 0.01
      - type: trajectory
        must_call: [compute_correlation]
        must_not_call: [run_query]
      - type: judge
        rubric: >
          The answer states a single correlation number, says explicitly that it is a
          correlation of DAILY RETURNS (not price levels), and names the date window.
          It must not invent extra figures.
        min_score: 0.7

  - id: corr_three_tickers
    input: "Give me the correlation matrix of AAPL, MSFT and NVDA daily returns over the first half of 2025 (2025-01-01 to 2025-06-30)."
    checks:
      - type: trajectory
        must_call: [compute_correlation]
        must_not_call: [run_query]
      - type: judge
        rubric: >
          The answer reports pairwise correlations among all three of AAPL, MSFT, NVDA
          (a matrix or the set of pairs), describes them as daily-return correlations,
          and names the window. No fabricated tickers or numbers.
        min_score: 0.7

  - id: refuses_missing_ticker
    input: "How correlated were AAPL and ZZZTOP daily returns in the first half of 2025 (2025-01-01 to 2025-06-30)?"
    checks:
      - type: trajectory
        must_call: [compute_correlation]
      - type: judge
        rubric: >
          The answer makes clear it could NOT compute the correlation because ZZZTOP is
          not in the warehouse, and names ZZZTOP as the problem. It must NOT fabricate a
          correlation value for the missing ticker.
        min_score: 0.7
```

- [ ] **Step 2: Write the failing test `common/tests/test_eval_harness.py`** (fake client; tiny inline golden)

```python
from pathlib import Path
from types import SimpleNamespace

import yaml

from lab_common.eval_harness import run_evals

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR_SKILL = REPO_ROOT / "skills" / "factor_correlation"

TINY_GOLDEN = {
    "cases": [
        {
            "id": "t1",
            "input": "corr of AAPL and MSFT 2025-01-01..2025-06-30",
            "checks": [
                {"type": "trajectory", "must_call": ["compute_correlation"]},
            ],
        }
    ]
}


class FakeAgentClient:
    """One scripted agent run: call compute_correlation, then finish."""

    def __init__(self):
        self.messages = self
        self._step = 0

    def create(self, **kwargs):
        self._step += 1
        if self._step == 1:
            return SimpleNamespace(
                stop_reason="tool_use",
                content=[SimpleNamespace(
                    type="tool_use", name="compute_correlation",
                    input={"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
                    id="tu1")],
            )
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="AAPL and MSFT daily-return correlation over the window was moderate.")],
        )


def test_run_evals_trajectory_only(tmp_path: Path, fixtures_parquet: Path):
    golden = tmp_path / "golden.yaml"
    golden.write_text(yaml.safe_dump(TINY_GOLDEN))
    report = run_evals(
        FACTOR_SKILL,
        golden_path=golden,
        agent_client=FakeAgentClient(),
        judge_client=None,  # no judge checks in TINY_GOLDEN
        context={"parquet": fixtures_parquet},
    )
    assert report.skill == "factor_correlation"
    assert len(report.cases) == 1
    assert report.cases[0].checks[0].type == "trajectory"
    assert report.cases[0].checks[0].passed
    assert report.mean_score == 1.0
    assert report.passed  # 1.0 >= threshold 0.8
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest common/tests/test_eval_harness.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lab_common.eval_harness'`

- [ ] **Step 4: Write `common/lab_common/eval_harness.py`**

```python
"""Drive a skill's golden set: run the agent once per case, apply each check, aggregate.

CLI: `python -m lab_common.eval_harness <skill_dir> [--haiku] [--report out.json]`
Default backend is laptop mode against the fixtures parquet.
"""

from __future__ import annotations

import argparse
import importlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import yaml

from lab_common.agent_runner import run_skill
from lab_common.models import CaseResult, CheckResult, EvalReport, SkillSpec
from lab_common.scorers import score_deterministic, score_judge, score_trajectory
from lab_common.skill_spec import load_skill


def load_golden(path: str | Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return list(data.get("cases", []))


def _load_agent_tools(spec: SkillSpec):
    module = importlib.import_module(f"{spec.name}.agent_tools")
    return module.TOOLS, module.dispatch


def _score_case(case, run, *, judge_client, context) -> CaseResult:
    results: list[CheckResult] = []
    for check in case["checks"]:
        ctype = check["type"]
        if ctype == "trajectory":
            results.append(score_trajectory(run, check))
        elif ctype == "deterministic":
            results.append(score_deterministic(run, check, context=context))
        elif ctype == "judge":
            results.append(score_judge(run.final_text, check, client=judge_client))
        else:
            results.append(CheckResult(ctype, False, 0.0, f"unknown check type {ctype}"))
    case_score = statistics.mean(r.score for r in results) if results else 0.0
    return CaseResult(case_id=case["id"], checks=results, score=case_score)


def run_evals(
    skill_dir: str | Path,
    *,
    golden_path: str | Path | None = None,
    agent_client: Any,
    judge_client: Any,
    context: dict[str, Any],
    model: str = "claude-sonnet-4-6",
) -> EvalReport:
    spec = load_skill(skill_dir)
    golden_path = golden_path or (Path(skill_dir) / spec.golden_set)
    cases = load_golden(golden_path)
    tools, dispatch = _load_agent_tools(spec)

    case_results: list[CaseResult] = []
    for case in cases:
        run = run_skill(
            spec, case["input"], tools, dispatch,
            client=agent_client, context=context, model=model,
        )
        case_results.append(_score_case(case, run, judge_client=judge_client, context=context))

    mean = statistics.mean(c.score for c in case_results) if case_results else 0.0
    return EvalReport(
        skill=spec.name,
        cases=case_results,
        mean_score=mean,
        threshold=spec.threshold,
        passed=mean >= spec.threshold,
    )


def _print_report(report: EvalReport) -> None:
    print(f"\n=== eval: {report.skill} ===")
    for case in report.cases:
        print(f"  {case.case_id}: score={case.score:.3f}")
        for chk in case.checks:
            mark = "PASS" if chk.passed else "FAIL"
            print(f"    [{mark}] {chk.type} ({chk.score:.3f}) {chk.detail}")
    verdict = "PASS" if report.passed else "FAIL"
    print(f"  MEAN {report.mean_score:.3f} vs threshold {report.threshold} -> {verdict}\n")


def main() -> None:
    import anthropic

    from lab_data.fixtures import write_parquet

    parser = argparse.ArgumentParser(description="Run a skill's golden-set evals (laptop mode).")
    parser.add_argument("skill_dir")
    parser.add_argument("--haiku", action="store_true", help="Use the cheaper model for the agent + judge")
    parser.add_argument("--report", type=Path, help="Write the JSON report to this path")
    parser.add_argument("--parquet", type=Path, help="Warehouse parquet (default: a fresh fixtures parquet)")
    args = parser.parse_args()

    model = "claude-haiku-4-5" if args.haiku else "claude-sonnet-4-6"
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env
    parquet = args.parquet or write_parquet(Path(".eval_fixtures/prices.parquet"))

    report = run_evals(
        args.skill_dir,
        agent_client=client,
        judge_client=client,
        context={"parquet": parquet},
        model=model,
    )
    _print_report(report)
    if args.report:
        args.report.write_text(json.dumps(_report_to_dict(report), indent=2))
        print(f"wrote {args.report}")
    sys.exit(0 if report.passed else 1)


def _report_to_dict(report: EvalReport) -> dict[str, Any]:
    return {
        "skill": report.skill,
        "mean_score": report.mean_score,
        "threshold": report.threshold,
        "passed": report.passed,
        "cases": [
            {
                "case_id": c.case_id,
                "score": c.score,
                "checks": [
                    {"type": k.type, "passed": k.passed, "score": k.score, "detail": k.detail}
                    for k in c.checks
                ],
            }
            for c in report.cases
        ],
    }


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest common/tests/test_eval_harness.py -v`
Expected: 1 PASS

- [ ] **Step 6: Add `.eval_fixtures/` and report output to `.gitignore`**

Append these lines to `.gitignore`:

```
.eval_fixtures/
eval_report.json
```

- [ ] **Step 7: Commit**

```bash
git add skills/factor_correlation/evals/golden.yaml common/lab_common/eval_harness.py common/tests/test_eval_harness.py .gitignore
git commit -m "feat: eval harness orchestrator + factor_correlation golden set (carryover B)"
```

---

## Task 9: pytest marker config + live smoke test + verify the free gate stays free

**Files:**
- Modify: `pyproject.toml` (root)
- Create: `skills/factor_correlation/tests/test_eval_live.py`

- [ ] **Step 1: Add the eval marker + default deselect to root `pyproject.toml`**

Append this block to the root `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-m 'not eval'"
markers = [
    "eval: live evals that call the Anthropic API (needs ANTHROPIC_API_KEY); deselected by default",
]
```

- [ ] **Step 2: Create `skills/factor_correlation/tests/test_eval_live.py`**

```python
"""Live smoke test: runs the real harness against the fixtures parquet.

Marked `eval` so it is deselected by the default `pytest` run. Run explicitly with:
    uv run pytest -m eval
It is skipped if ANTHROPIC_API_KEY is not set.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.eval

REPO_ROOT = Path(__file__).resolve().parents[3]
FACTOR_SKILL = REPO_ROOT / "skills" / "factor_correlation"


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
def test_live_eval_runs_and_scores(fixtures_parquet: Path):
    import anthropic

    from lab_common.eval_harness import run_evals

    client = anthropic.Anthropic()
    report = run_evals(
        FACTOR_SKILL,
        agent_client=client,
        judge_client=client,
        context={"parquet": fixtures_parquet},
        model="claude-haiku-4-5",  # cheap for the smoke test
    )
    assert report.skill == "factor_correlation"
    assert len(report.cases) == 3
    # The deterministic check on corr_two_tickers should pass (real math, real data).
    two = next(c for c in report.cases if c.case_id == "corr_two_tickers")
    det = next(k for k in two.checks if k.type == "deterministic")
    assert det.passed, f"deterministic failed: {det.detail}"
```

- [ ] **Step 3: Verify the default (free) gate excludes eval and stays green WITHOUT a key**

Run: `cd /Users/ukran1um/Projects/learning/skills-platform-lab && env -u ANTHROPIC_API_KEY uv run pytest -q`
Expected: all green, and the live test is **deselected** (not just skipped) — the summary shows `deselected` and no API call happens. Total selected should be the full offline suite (data + skill + common), with the eval-marked test deselected.

- [ ] **Step 4: Verify ruff + mypy stay clean**

Run: `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv run ruff check . && uv run mypy .`
Expected: both clean. Fix minimally if anything flags (e.g. an unused import or a missing annotation). Note any fix in your report.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml skills/factor_correlation/tests/test_eval_live.py
git commit -m "test: eval marker (free gate excludes evals) + live harness smoke test"
```

- [ ] **Step 6: Push and confirm CI is green**

```bash
git push && gh run watch "$(gh run list --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status --interval 10
```

Expected: green. (CI runs `uv run pytest -q`, which excludes the eval-marked test — so CI needs no API key, as intended.)

---

## Task 10: Manual checkpoint — live calibration + LEARNINGS (user-run)

**Files:** `LEARNINGS.md` (and possibly `skills/factor_correlation/SKILL.md` threshold)

This is the headline M2 deliverable: the operational texture you can only get by running it for real. It is user-run because it needs `ANTHROPIC_API_KEY`.

- [ ] **Step 1: Run the live harness once and read the report**

```bash
cd /Users/ukran1um/Projects/learning/skills-platform-lab
export ANTHROPIC_API_KEY=sk-ant-...        # your key
uv run python -m lab_common.eval_harness skills/factor_correlation --haiku --report eval_report.json
```

Expected: the agent runs each of the 3 cases, the report prints per-case/per-check scores, and a mean-vs-threshold verdict. The `corr_two_tickers` deterministic check should PASS (real math vs real data).

- [ ] **Step 2: Run it ≥5 times and observe judge variance**

```bash
for i in 1 2 3 4 5; do uv run python -m lab_common.eval_harness skills/factor_correlation --haiku; done
```

Watch the judge `scores=[...]` lines across runs. Note: do the medians swing across runs? Does any case straddle its `min_score`? Try `--haiku` vs the default Sonnet judge — is Sonnet steadier? This is the calibration data.

- [ ] **Step 3: Calibrate.** Based on what you saw, decide whether the skill's `threshold: 0.8` (in `skills/factor_correlation/SKILL.md`) and the per-case `min_score: 0.7` values are right. If the judge is noisy and good answers straddle the line, options are: raise `runs` (more judge samples → steadier median), loosen `min_score`, or sharpen the rubric wording. Make at most one change, re-run, and see if it stabilizes.

- [ ] **Step 4: Record LEARNINGS.** Add entries to `LEARNINGS.md` for what you found, e.g.:
  - Judge flakiness: the actual score spread you saw and median-of-N's effect.
  - Haiku-vs-Sonnet judge stability.
  - Whether deterministic/trajectory (cheap, stable) carried the signal while judge added noise — the "use the strongest gate you can" lesson.
  - Rough cost per eval run (from your Anthropic console).

```bash
git add LEARNINGS.md skills/factor_correlation/SKILL.md
git commit -m "docs: M2 eval calibration learnings (judge variance, threshold tuning)"
git push
```

**M2 acceptance met when:** the harness runs locally, the threshold is calibrated over ≥5 runs, and the first eval LEARNINGS entries are written.

---

## Self-review notes (run after drafting; issues found and fixed inline)

- **Spec coverage (Eval harness section):** golden.yaml format → Task 8; three check types (deterministic/trajectory/judge) → Task 7 + scorers; harness instantiates the skill via the same loader the host will use → `skill_spec` + `agent_runner` (Tasks 3, 6), reused by M5; staging vs laptop backend → laptop mode (fixtures parquet) implemented, staging-MCP mode deferred to M4 per spec; per-case scores + mean-vs-threshold + JSON report → Task 8; judge median-of-3 → Task 7; eval excluded from free CI → Task 9. Carryover A → Task 4; Carryover B → Task 8.
- **Deferred from the spec, on purpose:** the spec's harness section mentions an M4 "staging Data MCP" backend — not built here (M2 is laptop mode only, explicitly). The spec golden example used `compute_correlation`/`run_query`; `run_query` is a Data-MCP tool that arrives in M4, so `must_not_call: [run_query]` is satisfied vacuously now and becomes load-bearing at M4. Noted, not silently dropped.
- **Type consistency:** `run_skill(spec, user_input, tools, dispatch, *, client, context, model, max_turns, max_tokens)` is called consistently in Task 8. `dispatch(name, inputs, context)` signature matches `agent_tools.dispatch` (Task 5) and the runner's call (Task 6). `score_*` signatures match their calls in `_score_case` (Task 8). `CheckResult`/`CaseResult`/`EvalReport` fields used in Tasks 7-9 match `models.py` (Task 2).
- **Placeholder scan:** clean — every code step has complete code; every run step has a command + expected output.
- **Known risks:** (1) `anthropic` response-block attribute access (`b.type`, `b.input`, `b.id`) is verified against the Messages API tool-use shape; if the installed SDK differs, the live test (Task 9/10) surfaces it and the runner is the single place to adjust. (2) Judge cost: ~3 judge calls × 3 judge-cases + 3 agent runs per harness invocation — cents on Haiku, well under the spec's $1/run cap; the ≥5-run calibration is still a few dollars at most.
