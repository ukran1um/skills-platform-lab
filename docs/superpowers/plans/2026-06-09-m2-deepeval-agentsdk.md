# M2 Rebuild: Agent-SDK Runtime + DeepEval, Multi-Tool Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the skill through the **Claude Agent SDK** (the real runtime, isolated via `setting_sources=[]` + string `system_prompt`) in the eval harness — the same substrate the M5 host will use — and score the resulting multi-step agentic trace with **DeepEval** (GEval / ToolCorrectnessMetric / a custom deterministic metric). Expand `factor_correlation` to a 4-tool skill so the trace is genuinely multi-step.

**Architecture:** The skill's tools become in-process Agent-SDK MCP tools (`@tool` + `create_sdk_mcp_server`). `run_skill` becomes an async Agent-SDK adapter: it runs `query()` headless (API key via `options.env`), isolated from local config (`setting_sources=[]`, `system_prompt` = SKILL.md string), and a **pure** `build_runresult` filters harness-internal tools (ToolSearch) and strips the `mcp__factor__` prefix into our `RunResult`. The harness turns each `RunResult` into a DeepEval `LLMTestCase` and scores it. The agent run is injected into `run_evals` as a `runner` callable, so the orchestration stays unit-testable offline while the live runner spawns the SDK.

**Tech Stack:** Python 3.12, uv, **claude-agent-sdk 0.2.94** (`query`, `tool`, `create_sdk_mcp_server`, `ClaudeAgentOptions`), **deepeval 4.0.5** (`GEval`, `ToolCorrectnessMetric`, `BaseMetric`, `LLMTestCase`, `ToolCall`, `AnthropicModel`/`GPTModel`), anthropic, duckdb, pandas, pytest. Runtime needs the `claude` CLI + Node present (here already; CI adds an install step in M3).

**Spec:** `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md` (Eval section — this plan updates it).

---

## Verified API (spiked live — use exactly this)

**Agent SDK (claude-agent-sdk 0.2.94):**
- `from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions, query, AssistantMessage, UserMessage, ResultMessage, TextBlock, ToolUseBlock, ToolResultBlock`
- `@tool(name: str, description: str, input_schema: dict)` decorates `async def fn(args: dict) -> dict` returning `{"content": [{"type": "text", "text": <str>}]}`.
- `create_sdk_mcp_server(name, version="1.0.0", tools=[...]) -> McpSdkServerConfig` (runs **in-process** — tools execute in this Python process and read its `os.environ`).
- `ClaudeAgentOptions(mcp_servers={"factor": server}, allowed_tools=["mcp__factor__<tool>", ...], system_prompt=<str replaces CC default>, model="claude-haiku-4-5", permission_mode="bypassPermissions", setting_sources=[], max_turns=8, env={"ANTHROPIC_API_KEY": ...})`. `system_prompt` as a `str` **replaces** the default Claude Code prompt. `setting_sources=[]` loads **no** local `~/.claude`/project/local config.
- `async for msg in query(prompt=<str>, options=opts): ...` — `AssistantMessage.content` holds `ToolUseBlock(id, name, input)` / `TextBlock(text)`; `UserMessage.content` holds `ToolResultBlock(tool_use_id, content)`; `ResultMessage.result` is the final text (also `.total_cost_usd`, `.num_turns`).
- **Harness behavior to filter:** the agent emits a `ToolSearch` tool call (deferred tool loading) before the real `mcp__factor__*` call. Drop any tool whose name does not start with `mcp__`.

**DeepEval (4.0.5):** `AnthropicModel(model, api_key)` / `GPTModel()`; `LLMTestCase(input, actual_output, tools_called=[ToolCall(name, input_parameters, output)], expected_tools=[ToolCall(name)])`; `GEval(name, criteria, evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT], model, threshold)`; `ToolCorrectnessMetric(threshold, should_consider_ordering, should_exact_match)`; custom `BaseMetric.measure()`. All `.measure(tc)` → `.score`/`.is_successful()`/`.reason`. GEval needs the LLM (live); ToolCorrectness + custom metric are offline.

---

## File structure after this plan

```
common/
├── pyproject.toml                      # MODIFY: + claude-agent-sdk, deepeval
└── lab_common/
    ├── agent_runner.py                 # REWRITE: SDK adapter (build_runresult pure + async run + make_sdk_runner)
    ├── deepeval_metrics.py             # NEW: judge factory + DeterministicCorrelationMetric + builders + to_test_case
    ├── eval_harness.py                 # REWRITE: injectable runner; DeepEval scoring; SDK runner in main()
    ├── scorers.py                      # DELETE
    ├── models.py                       # unchanged
    └── skill_spec.py                   # unchanged
common/tests/
├── test_agent_runner.py               # REWRITE: build_runresult (offline) + live SDK run (marked eval)
├── test_deepeval_metrics.py           # NEW (offline)
├── test_eval_harness.py               # REWRITE (offline, fake runner)
└── test_scorers.py                    # DELETE
skills/factor_correlation/
├── factor_correlation/
│   ├── tools/fetch.py                  # MODIFY: + list_tickers(), run_sql()
│   ├── tools/compute.py               # MODIFY: + returns_stats()
│   └── agent_tools.py                 # REWRITE: impl fns + @tool wrappers + SERVER + ALLOWED_TOOLS
│   └── cli.py                          # unchanged
├── tests/{test_fetch,test_compute,test_agent_tools}.py   # MODIFY/REWRITE
├── tests/test_eval_live.py            # REWRITE (4 cases, live)
├── SKILL.md                            # REWRITE body: execution-agnostic (capability + tools + reporting rules)
└── evals/golden.yaml                  # REWRITE: 4 cases incl. multi-step
docs/superpowers/specs/...             # MODIFY: eval section -> Agent SDK + DeepEval
```

---

## Task 1: New skill tool implementations (fetch + compute)

**Files:** Modify `skills/factor_correlation/factor_correlation/tools/fetch.py`, `.../tools/compute.py`; Test `.../tests/test_fetch.py`, `.../tests/test_compute.py`.

- [ ] **Step 1: Append failing tests to `skills/factor_correlation/tests/test_fetch.py`**

```python
def test_list_tickers(fixtures_parquet: Path):
    from factor_correlation.tools.fetch import list_tickers
    tickers = list_tickers(parquet=fixtures_parquet)
    assert tickers == sorted(tickers)
    assert "AAPL" in tickers and "MSFT" in tickers


def test_run_sql_select_ok(fixtures_parquet: Path):
    from factor_correlation.tools.fetch import run_sql
    df = run_sql("SELECT count(*) AS n FROM prices WHERE ticker='AAPL'", parquet=fixtures_parquet)
    assert int(df.iloc[0]["n"]) > 0


def test_run_sql_rejects_non_select(fixtures_parquet: Path):
    from factor_correlation.tools.fetch import run_sql
    with pytest.raises(ValueError, match="SELECT"):
        run_sql("DROP TABLE prices", parquet=fixtures_parquet)


def test_run_sql_rejects_multiple_statements(fixtures_parquet: Path):
    from factor_correlation.tools.fetch import run_sql
    with pytest.raises(ValueError, match="single statement"):
        run_sql("SELECT 1; SELECT 2", parquet=fixtures_parquet)
```

- [ ] **Step 2: Run** — `uv run pytest skills/factor_correlation/tests/test_fetch.py -v` → FAIL (ImportError).

- [ ] **Step 3: Append to `skills/factor_correlation/factor_correlation/tools/fetch.py`**

```python
import re

_FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|export|install|load|set)\b",
    re.IGNORECASE,
)


def list_tickers(parquet: Path | None = None) -> list[str]:
    """Distinct tickers in the warehouse, sorted."""
    parquet = parquet or warehouse_path()
    if not parquet.exists():
        raise FileNotFoundError(f"warehouse parquet not found at {parquet}")
    rows = duckdb.execute(
        "SELECT DISTINCT ticker FROM read_parquet(?) ORDER BY ticker", [str(parquet)]
    ).fetchall()
    return [r[0] for r in rows]


def run_sql(query: str, parquet: Path | None = None) -> pd.DataFrame:
    """Read-only SELECT against a view prices(ticker, date, close). SELECT/WITH only,
    single statement, no DDL/DML — the security boundary, enforced here not by the agent."""
    parquet = parquet or warehouse_path()
    if not parquet.exists():
        raise FileNotFoundError(f"warehouse parquet not found at {parquet}")
    q = query.strip().rstrip(";").strip()
    if ";" in q:
        raise ValueError("only a single statement is allowed")
    if not re.match(r"(?is)^\s*(select|with)\b", q):
        raise ValueError("only SELECT/WITH queries are allowed")
    if _FORBIDDEN_SQL.search(q):
        raise ValueError("query contains a forbidden (non-read) keyword")
    con = duckdb.connect()
    con.execute(f"CREATE VIEW prices AS SELECT * FROM read_parquet('{parquet}')")
    return con.execute(q).df()
```

- [ ] **Step 4: Run** — `uv run pytest skills/factor_correlation/tests/test_fetch.py -v` → all PASS.

- [ ] **Step 5: Append failing test to `skills/factor_correlation/tests/test_compute.py`**

```python
def test_returns_stats():
    from factor_correlation.tools.compute import returns_stats
    prices = _prices("AAA", _closes_from_returns(100.0, [0.10, -0.05, 0.08]))
    stats = returns_stats(prices)
    assert stats["ticker"] == "AAA"
    assert stats["n_days"] == 3
    assert stats["mean_daily_return"] == pytest.approx((0.10 - 0.05 + 0.08) / 3, abs=1e-6)
    assert stats["daily_vol"] > 0
```

- [ ] **Step 6: Run** → FAIL. **Step 7: Append to `compute.py`:**

```python
def returns_stats(prices: pd.DataFrame) -> dict:
    """Per-ticker daily-return stats from one ticker's price rows."""
    ticker = str(prices["ticker"].iloc[0])
    rets = prices.sort_values("date")["close"].pct_change(fill_method=None).dropna()
    return {
        "ticker": ticker,
        "n_days": int(len(rets)),
        "mean_daily_return": float(rets.mean()),
        "daily_vol": float(rets.std()),
    }
```

- [ ] **Step 8: Run** — `uv run pytest skills/factor_correlation/tests/test_compute.py -v` → all PASS.

- [ ] **Step 9: Commit**

```bash
git add skills/factor_correlation/factor_correlation/tools/ skills/factor_correlation/tests/test_fetch.py skills/factor_correlation/tests/test_compute.py
git commit -m "feat: list_tickers, run_sql (SELECT-only), returns_stats for the multi-tool skill"
```

---

## Task 2: Agent-SDK tool surface (`agent_tools.py`) + dep

**Files:** Modify `common/pyproject.toml`; Rewrite `skills/factor_correlation/factor_correlation/agent_tools.py`, `.../tests/test_agent_tools.py`.

- [ ] **Step 1: Add `claude-agent-sdk` to `common/pyproject.toml`** dependencies (`"claude-agent-sdk>=0.2"`), then `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv sync --all-packages`.

- [ ] **Step 2: Rewrite `skills/factor_correlation/tests/test_agent_tools.py`** (tests the sync impl functions, which read PRICES_PARQUET — no SDK, no API)

```python
import json
from pathlib import Path

import pytest

from factor_correlation import agent_tools as at


@pytest.fixture()
def env_parquet(fixtures_parquet: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PRICES_PARQUET", str(fixtures_parquet))
    return fixtures_parquet


def test_allowed_tools_and_server(env_parquet):
    assert set(at.ALLOWED_TOOLS) == {
        "mcp__factor__list_tickers", "mcp__factor__compute_correlation",
        "mcp__factor__get_returns_stats", "mcp__factor__run_sql",
    }
    assert at.SERVER is not None


def test_impl_list_tickers(env_parquet):
    assert "AAPL" in json.loads(at._list_tickers_impl())["tickers"]


def test_impl_compute_correlation(env_parquet):
    out = json.loads(at._compute_correlation_impl({"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"}))
    assert -1.0 <= out["correlation_value"] <= 1.0


def test_impl_returns_stats(env_parquet):
    out = json.loads(at._returns_stats_impl({"ticker": "AAPL", "start": "2025-01-01", "end": "2025-06-30"}))
    assert out["ticker"] == "AAPL" and out["daily_vol"] > 0


def test_impl_run_sql_ok(env_parquet):
    out = json.loads(at._run_sql_impl({"query": "SELECT max(close) AS hi FROM prices WHERE ticker='AAPL'"}))
    assert out["rows"]


def test_impl_run_sql_rejected_is_error(env_parquet):
    assert "error" in json.loads(at._run_sql_impl({"query": "DELETE FROM prices"}))


def test_impl_missing_ticker_is_error(env_parquet):
    assert "error" in json.loads(at._compute_correlation_impl({"tickers": ["ZZZTOP"], "start": "2025-01-01", "end": "2025-06-30"}))
```

- [ ] **Step 3: Run** → FAIL (no `agent_tools._*_impl`). **Step 4: Rewrite `skills/factor_correlation/factor_correlation/agent_tools.py`**

```python
"""The skill's Agent-SDK tool surface (4 in-process MCP tools the agent composes).

Tools run IN this Python process (in-process SDK MCP server) and read the warehouse
from $PRICES_PARQUET (the harness sets it). Sync `_*_impl` functions hold the logic and
are unit-tested; the `@tool` async wrappers are thin shells returning MCP content.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from factor_correlation.cli import run
from factor_correlation.tools.compute import returns_stats
from factor_correlation.tools.fetch import get_prices, list_tickers, run_sql


def _list_tickers_impl() -> str:
    try:
        return json.dumps({"tickers": list_tickers()})
    except (ValueError, FileNotFoundError) as exc:
        return json.dumps({"error": str(exc)})


def _compute_correlation_impl(args: dict[str, Any]) -> str:
    try:
        result = run(list(args["tickers"]), date.fromisoformat(args["start"]),
                     date.fromisoformat(args["end"]))
    except (SystemExit, ValueError, FileNotFoundError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(result)


def _returns_stats_impl(args: dict[str, Any]) -> str:
    try:
        prices = get_prices([args["ticker"]], date.fromisoformat(args["start"]),
                            date.fromisoformat(args["end"]))
        if prices.empty:
            return json.dumps({"error": f"no data for {args['ticker']}"})
        return json.dumps(returns_stats(prices))
    except (ValueError, FileNotFoundError) as exc:
        return json.dumps({"error": str(exc)})


def _run_sql_impl(args: dict[str, Any]) -> str:
    try:
        df = run_sql(args["query"])
        return json.dumps({"rows": df.head(100).to_dict(orient="records")}, default=str)
    except (ValueError, FileNotFoundError) as exc:
        return json.dumps({"error": str(exc)})


@tool("list_tickers", "List ticker symbols available in the price warehouse.", {})
async def _list_tickers_tool(args):
    return {"content": [{"type": "text", "text": _list_tickers_impl()}]}


@tool("compute_correlation",
      "Pearson correlation of daily returns between two or more tickers over a date range. "
      "Prefer this over run_sql for correlations.",
      {"tickers": list, "start": str, "end": str})
async def _compute_correlation_tool(args):
    return {"content": [{"type": "text", "text": _compute_correlation_impl(args)}]}


@tool("get_returns_stats",
      "Daily-return stats (mean, volatility, n_days) for ONE ticker over a date range. "
      "Prefer this over run_sql for volatility/return stats.",
      {"ticker": str, "start": str, "end": str})
async def _returns_stats_tool(args):
    return {"content": [{"type": "text", "text": _returns_stats_impl(args)}]}


@tool("run_sql",
      "Escape hatch: read-only SELECT against the view prices(ticker, date, close). Use ONLY "
      "for questions the typed tools cannot answer (e.g. max/min close). SELECT/WITH only.",
      {"query": str})
async def _run_sql_tool(args):
    return {"content": [{"type": "text", "text": _run_sql_impl(args)}]}


SERVER = create_sdk_mcp_server(
    name="factor", version="1.0.0",
    tools=[_list_tickers_tool, _compute_correlation_tool, _returns_stats_tool, _run_sql_tool],
)

ALLOWED_TOOLS = [
    "mcp__factor__list_tickers",
    "mcp__factor__compute_correlation",
    "mcp__factor__get_returns_stats",
    "mcp__factor__run_sql",
]
```

- [ ] **Step 5: Run** — `uv run pytest skills/factor_correlation/tests/test_agent_tools.py -v` → all PASS.

- [ ] **Step 6: Commit**

```bash
git add common/pyproject.toml uv.lock skills/factor_correlation/factor_correlation/agent_tools.py skills/factor_correlation/tests/test_agent_tools.py
git commit -m "feat: Agent-SDK in-process tool surface (4 tools) + claude-agent-sdk dep"
```

---

## Task 3: Rewrite `agent_runner.py` as the Agent-SDK adapter

**Files:** Rewrite `common/lab_common/agent_runner.py`, `common/tests/test_agent_runner.py`.

- [ ] **Step 1: Rewrite `common/tests/test_agent_runner.py`** (offline test of the pure `build_runresult`; the live SDK run is in the eval-marked live test, Task 6)

```python
from lab_common.agent_runner import build_runresult


def test_build_runresult_filters_harness_tools_and_strips_prefix():
    # ToolSearch (harness-internal) must be dropped; mcp__factor__ prefix stripped.
    tool_uses = [
        ("id0", "ToolSearch", {"query": "select:..."}),
        ("id1", "mcp__factor__compute_correlation", {"tickers": ["AAPL", "MSFT"]}),
    ]
    tool_results = {"id0": "[ref]", "id1": '{"correlation_value": -0.05}'}
    run = build_runresult(tool_uses, tool_results, final_text="the answer")
    assert run.called_tools() == ["compute_correlation"]   # ToolSearch dropped
    assert run.trajectory[0].input == {"tickers": ["AAPL", "MSFT"]}
    assert run.trajectory[0].result == '{"correlation_value": -0.05}'
    assert run.final_text == "the answer"


def test_build_runresult_handles_missing_result():
    run = build_runresult([("id1", "mcp__factor__list_tickers", {})], {}, final_text=None)
    assert run.called_tools() == ["list_tickers"]
    assert run.trajectory[0].result is None
    assert run.final_text is None
```

- [ ] **Step 2: Run** → FAIL (no `build_runresult`). **Step 3: Rewrite `common/lab_common/agent_runner.py`**

```python
"""Run a skill through the Claude Agent SDK (the real runtime) and capture its trace.

`build_runresult` is pure (filter harness tools, strip mcp prefix, match results) and
unit-tested offline. `run_skill` is the async live adapter that spawns the SDK headless,
isolated from local config. `make_sdk_runner` returns a sync `runner(input)->RunResult`.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Callable

from lab_common.models import RunResult, SkillSpec, ToolCall

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TURNS = 8


def _text_of(content: Any) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return None


def build_runresult(
    tool_uses: list[tuple[str, str, dict]],
    tool_results: dict[str, Any],
    final_text: str | None,
) -> RunResult:
    """tool_uses: [(id, name, input)]; tool_results: {id: content}. Drops harness-internal
    tools (anything not mcp__*), strips the mcp__<server>__ prefix, matches results by id."""
    trajectory: list[ToolCall] = []
    for tool_id, name, inp in tool_uses:
        if not name.startswith("mcp__"):
            continue  # harness-internal (e.g. ToolSearch) — not part of the skill's trace
        short = name.split("__")[-1]
        trajectory.append(ToolCall(name=short, input=dict(inp), result=_text_of(tool_results.get(tool_id))))
    return RunResult(final_text=final_text, trajectory=trajectory)


async def run_skill(
    spec: SkillSpec,
    user_input: str,
    *,
    server: Any,
    allowed_tools: list[str],
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> RunResult:
    from claude_agent_sdk import (
        AssistantMessage, ResultMessage, TextBlock, ToolResultBlock, ToolUseBlock,
        UserMessage, ClaudeAgentOptions, query,
    )

    opts = ClaudeAgentOptions(
        mcp_servers={"factor": server},
        allowed_tools=allowed_tools,
        system_prompt=spec.system_prompt,      # str => REPLACES the default CC prompt
        model=model,
        permission_mode="bypassPermissions",
        setting_sources=[],                     # load NO local ~/.claude / project / local config
        max_turns=max_turns,
        env={"ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"]},
    )
    tool_uses: list[tuple[str, str, dict]] = []
    tool_results: dict[str, Any] = {}
    final_text: str | None = None
    async for msg in query(prompt=user_input, options=opts):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, ToolUseBlock):
                    tool_uses.append((b.id, b.name, b.input))
                elif isinstance(b, TextBlock):
                    final_text = b.text
        elif isinstance(msg, UserMessage):
            content = msg.content if isinstance(msg.content, list) else []
            for b in content:
                if isinstance(b, ToolResultBlock):
                    tool_results[b.tool_use_id] = b.content
        elif isinstance(msg, ResultMessage):
            if getattr(msg, "result", None):
                final_text = msg.result
    return build_runresult(tool_uses, tool_results, final_text)


def make_sdk_runner(
    spec: SkillSpec, server: Any, allowed_tools: list[str], model: str = DEFAULT_MODEL
) -> Callable[[str], RunResult]:
    """A sync runner(input)->RunResult that runs the async SDK query per call."""
    def runner(user_input: str) -> RunResult:
        return asyncio.run(run_skill(spec, user_input, server=server,
                                     allowed_tools=allowed_tools, model=model))
    return runner
```

- [ ] **Step 4: Run** — `uv run pytest common/tests/test_agent_runner.py -v` → 2 PASS (offline, no SDK).

- [ ] **Step 5: Commit**

```bash
git add common/lab_common/agent_runner.py common/tests/test_agent_runner.py
git commit -m "feat: Agent-SDK runner adapter (isolated headless run + pure trajectory parse)"
```

---

## Task 4: DeepEval dep + judge factory + deterministic metric

**Files:** Modify `common/pyproject.toml`; Create `common/lab_common/deepeval_metrics.py`; Test `common/tests/test_deepeval_metrics.py`.

- [ ] **Step 1: Add `"deepeval>=4.0"` to `common/pyproject.toml` dependencies; `uv sync --all-packages`.**

- [ ] **Step 2: Write failing test `common/tests/test_deepeval_metrics.py`**

```python
import json
from pathlib import Path

from deepeval.test_case import LLMTestCase, ToolCall

from lab_common.deepeval_metrics import DeterministicCorrelationMetric, choose_judge_provider


def test_chooser_prefers_openai():
    assert choose_judge_provider({"OPENAI_API_KEY": "x", "ANTHROPIC_API_KEY": "y"}) == "openai"


def test_chooser_falls_back_to_anthropic():
    assert choose_judge_provider({"ANTHROPIC_API_KEY": "y"}) == "anthropic"


def test_chooser_gemini_when_only_google():
    assert choose_judge_provider({"GOOGLE_API_KEY": "g", "ANTHROPIC_API_KEY": "y"}) == "gemini"


def _tc(output: dict) -> LLMTestCase:
    return LLMTestCase(input="x", actual_output="...", tools_called=[ToolCall(
        name="compute_correlation",
        input_parameters={"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
        output=json.dumps(output))])


def test_deterministic_passes_on_correct_matrix(fixtures_parquet: Path):
    from datetime import date
    from factor_correlation.cli import run as skill_run
    truth = skill_run(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)
    m = DeterministicCorrelationMetric(parquet=fixtures_parquet, tolerance=0.01)
    m.measure(_tc(truth))
    assert m.is_successful() and m.score == 1.0


def test_deterministic_fails_on_wrong_matrix(fixtures_parquet: Path):
    bad = {"matrix": {"AAPL": {"AAPL": 1.0, "MSFT": 0.99}, "MSFT": {"AAPL": 0.99, "MSFT": 1.0}}}
    m = DeterministicCorrelationMetric(parquet=fixtures_parquet, tolerance=0.01)
    m.measure(_tc(bad))
    assert not m.is_successful()
```

- [ ] **Step 3: Run** → FAIL. **Step 4: Create `common/lab_common/deepeval_metrics.py`**

```python
"""DeepEval scoring: configurable cross-family judge, a custom deterministic metric, and
builders turning golden-set checks into DeepEval metrics + a RunResult into an LLMTestCase."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
from deepeval.metrics import BaseMetric, GEval, ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.test_case import ToolCall as DEToolCall

from lab_common.models import RunResult

DEFAULT_ANTHROPIC_JUDGE = "claude-sonnet-4-6"


def choose_judge_provider(env: dict[str, str]) -> str:
    """Prefer a judge family DIFFERENT from the Claude generator (breaks correlated
    failure modes). OpenAI > Gemini > Claude."""
    if env.get("OPENAI_API_KEY"):
        return "openai"
    if env.get("GOOGLE_API_KEY"):
        return "gemini"
    return "anthropic"


def make_judge(provider: str | None = None, env: dict[str, str] | None = None):
    env = env if env is not None else dict(os.environ)
    provider = provider or choose_judge_provider(env)
    if provider == "openai":
        from deepeval.models import GPTModel
        m = GPTModel()
        return m, f"openai:{m.get_model_name()}"
    if provider == "gemini":
        from deepeval.models import GeminiModel
        m = GeminiModel()
        return m, f"gemini:{m.get_model_name()}"
    from deepeval.models import AnthropicModel
    m = AnthropicModel(model=DEFAULT_ANTHROPIC_JUDGE, api_key=env["ANTHROPIC_API_KEY"])
    return m, f"anthropic:{DEFAULT_ANTHROPIC_JUDGE}"


def _recompute_matrix(parquet: Path, tickers: list[str], start: str, end: str) -> dict:
    df = pd.read_parquet(parquet)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    mask = (df["ticker"].isin([t.upper() for t in tickers])
            & (df["date"] >= pd.to_datetime(start).date())
            & (df["date"] <= pd.to_datetime(end).date()))
    corr = df[mask].pivot(index="date", columns="ticker", values="close").sort_index() \
        .pct_change(fill_method=None).dropna(how="all").corr(method="pearson")
    return {a: {b: float(corr.loc[a, b]) for b in corr.columns} for a in corr.columns}


class DeterministicCorrelationMetric(BaseMetric):
    """Independent oracle: recompute every compute_correlation matrix from the parquet and
    require all reported cells within tolerance. No LLM."""

    def __init__(self, parquet: Path, tolerance: float = 0.01):
        self.parquet = Path(parquet)
        self.tolerance = tolerance
        self.threshold = 1.0
        self.async_mode = False
        self.include_reason = True

    def measure(self, test_case: LLMTestCase) -> float:
        calls = [c for c in (test_case.tools_called or []) if c.name == "compute_correlation"]
        if not calls:
            self.score, self.success, self.reason = 0.0, False, "compute_correlation not called"
            return self.score
        bad = []
        for call in calls:
            reported = json.loads(call.output)["matrix"]
            expected = _recompute_matrix(self.parquet, call.input_parameters["tickers"],
                                         call.input_parameters["start"], call.input_parameters["end"])
            for a in expected:
                for b in expected:
                    if abs(reported[a][b] - expected[a][b]) > self.tolerance:
                        bad.append(f"{a}/{b}: {reported[a][b]:.4f} vs {expected[a][b]:.4f}")
        self.success = not bad
        self.score = 1.0 if self.success else 0.0
        self.reason = "all cells within tolerance" if self.success else "; ".join(bad)
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):
        return "DeterministicCorrelation"
```

- [ ] **Step 5: Run** — `uv run pytest common/tests/test_deepeval_metrics.py -v` → all PASS (no API).

- [ ] **Step 6: Commit**

```bash
git add common/pyproject.toml uv.lock common/lab_common/deepeval_metrics.py common/tests/test_deepeval_metrics.py
git commit -m "feat: deepeval dep, cross-family judge factory, DeterministicCorrelationMetric"
```

---

## Task 5: Builders + rebuild `eval_harness` (injectable runner)

**Files:** Modify `common/lab_common/deepeval_metrics.py`; Rewrite `common/lab_common/eval_harness.py`; Delete `scorers.py`/`test_scorers.py`; Rewrite `common/tests/test_eval_harness.py`.

- [ ] **Step 1: Append builders to `common/lab_common/deepeval_metrics.py`**

```python
def to_test_case(input_text: str, run: RunResult, expected_tools: list[str] | None) -> LLMTestCase:
    return LLMTestCase(
        input=input_text,
        actual_output=run.final_text or "",
        tools_called=[DEToolCall(name=c.name, input_parameters=c.input, output=c.result)
                      for c in run.trajectory],
        expected_tools=[DEToolCall(name=n) for n in (expected_tools or [])],
    )


def build_metric(check: dict[str, Any], *, judge: Any, parquet: Path):
    """Return (metric, type_label) for a golden check."""
    t = check["type"]
    if t == "deterministic":
        return DeterministicCorrelationMetric(parquet=parquet, tolerance=check.get("tolerance", 0.01)), "deterministic"
    if t == "tool_correctness":
        return ToolCorrectnessMetric(
            threshold=check.get("threshold", 1.0),
            should_consider_ordering=check.get("ordered", False),
            should_exact_match=check.get("exact_match", False),
        ), "tool_correctness"
    if t == "geval":
        return GEval(
            name=check.get("name", "criteria"), criteria=check["criteria"],
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
            model=judge, threshold=check.get("threshold", 0.7),
        ), "geval"
    raise ValueError(f"unknown check type: {t}")
```

- [ ] **Step 2: Rewrite `common/lab_common/eval_harness.py`**

```python
"""Drive a skill's golden set with DeepEval. The agent run is injected as `runner` so
the orchestration is unit-testable offline; the live runner spawns the Agent SDK.

CLI: python -m lab_common.eval_harness <skill_dir> [--haiku] [--report out.json]"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Callable

import yaml

from lab_common.deepeval_metrics import build_metric, make_judge, to_test_case
from lab_common.models import CaseResult, CheckResult, EvalReport, RunResult
from lab_common.skill_spec import load_skill


def load_golden(path: str | Path) -> list[dict[str, Any]]:
    return list((yaml.safe_load(Path(path).read_text()) or {}).get("cases", []))


def _expected_tools(case: dict[str, Any]) -> list[str] | None:
    for chk in case["checks"]:
        if chk["type"] == "tool_correctness":
            return list(chk.get("expected_tools", []))
    return None


def _score_case(case: dict[str, Any], run: RunResult, *, judge: Any, parquet: Path) -> CaseResult:
    tc = to_test_case(case["input"], run, _expected_tools(case))
    results: list[CheckResult] = []
    for check in case["checks"]:
        metric, label = build_metric(check, judge=judge, parquet=parquet)
        metric.measure(tc)
        results.append(CheckResult(type=label, passed=bool(metric.is_successful()),
                                   score=float(metric.score), detail=str(metric.reason or "")))
    score = statistics.mean(r.score for r in results) if results else 0.0
    return CaseResult(case_id=case["id"], checks=results, score=score)


def run_evals(
    skill_dir: str | Path,
    *,
    runner: Callable[[str], RunResult],
    judge: Any,
    parquet: Path,
    golden_path: str | Path | None = None,
) -> EvalReport:
    spec = load_skill(skill_dir)
    cases = load_golden(golden_path or (Path(skill_dir) / spec.golden_set))
    if any(c["type"] == "geval" for case in cases for c in case["checks"]) and judge is None:
        raise ValueError("golden set has geval checks but no judge model")
    case_results: list[CaseResult] = []
    for case in cases:
        try:
            run = runner(case["input"])
            case_results.append(_score_case(case, run, judge=judge, parquet=parquet))
        except Exception as exc:  # noqa: BLE001 — one bad case must not abort the run
            case_results.append(CaseResult(case_id=case["id"],
                                checks=[CheckResult("error", False, 0.0, str(exc))], score=0.0))
    mean = statistics.mean(c.score for c in case_results) if case_results else 0.0
    return EvalReport(skill=spec.name, cases=case_results, mean_score=mean,
                      threshold=spec.threshold, passed=mean >= spec.threshold)


def _report_to_dict(r: EvalReport) -> dict[str, Any]:
    return {"skill": r.skill, "mean_score": r.mean_score, "threshold": r.threshold, "passed": r.passed,
            "cases": [{"case_id": c.case_id, "score": c.score,
                       "checks": [{"type": k.type, "passed": k.passed, "score": k.score, "detail": k.detail}
                                  for k in c.checks]} for c in r.cases]}


def _print_report(r: EvalReport, judge_label: str) -> None:
    print(f"\n=== eval: {r.skill}  (judge: {judge_label}) ===")
    for c in r.cases:
        print(f"  {c.case_id}: score={c.score:.3f}")
        for k in c.checks:
            print(f"    [{'PASS' if k.passed else 'FAIL'}] {k.type} ({k.score:.3f}) {k.detail[:110]}")
    print(f"  MEAN {r.mean_score:.3f} vs {r.threshold} -> {'PASS' if r.passed else 'FAIL'}\n")


def main() -> None:
    from dotenv import load_dotenv

    from lab_common.agent_runner import make_sdk_runner
    from lab_data.fixtures import write_parquet

    load_dotenv()
    parser = argparse.ArgumentParser(description="Run a skill's golden-set evals (Agent SDK + DeepEval).")
    parser.add_argument("skill_dir")
    parser.add_argument("--haiku", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--parquet", type=Path)
    args = parser.parse_args()

    model = "claude-haiku-4-5" if args.haiku else "claude-sonnet-4-6"
    parquet = args.parquet or write_parquet(Path(".eval_fixtures/prices.parquet"))
    os.environ["PRICES_PARQUET"] = str(parquet)   # in-process tools read this

    spec = load_skill(args.skill_dir)
    mod = importlib.import_module(f"{spec.name}.agent_tools")
    runner = make_sdk_runner(spec, mod.SERVER, mod.ALLOWED_TOOLS, model)
    judge, judge_label = make_judge()

    report = run_evals(args.skill_dir, runner=runner, judge=judge, parquet=parquet)
    _print_report(report, judge_label)
    if args.report:
        args.report.write_text(json.dumps(_report_to_dict(report), indent=2))
        print(f"wrote {args.report}")
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Delete old scorers** — `git rm common/lab_common/scorers.py common/tests/test_scorers.py`

- [ ] **Step 4: Rewrite `common/tests/test_eval_harness.py`** (offline: fake runner, no SDK/API)

```python
import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from lab_common.eval_harness import run_evals
from lab_common.models import RunResult, ToolCall

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR_SKILL = REPO_ROOT / "skills" / "factor_correlation"


def _good_runner(fixtures_parquet: Path):
    from factor_correlation.cli import run as skill_run
    truth = skill_run(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)

    def runner(_input: str) -> RunResult:
        return RunResult(final_text="done", trajectory=[ToolCall(
            "compute_correlation",
            {"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
            json.dumps(truth))])
    return runner


def test_offline_deterministic_and_tool_correctness(tmp_path: Path, fixtures_parquet: Path):
    golden = {"cases": [{"id": "c1", "input": "x", "checks": [
        {"type": "deterministic", "tolerance": 0.01},
        {"type": "tool_correctness", "expected_tools": ["compute_correlation"], "exact_match": True},
    ]}]}
    gp = tmp_path / "g.yaml"; gp.write_text(yaml.safe_dump(golden))
    report = run_evals(FACTOR_SKILL, runner=_good_runner(fixtures_parquet), judge=None,
                       parquet=fixtures_parquet, golden_path=gp)
    assert {c.type for c in report.cases[0].checks} == {"deterministic", "tool_correctness"}
    assert report.cases[0].checks[0].passed and report.passed


def test_errored_case_scores_zero(tmp_path: Path, fixtures_parquet: Path):
    def boom(_): raise RuntimeError("boom")
    golden = {"cases": [{"id": "b", "input": "x",
                         "checks": [{"type": "tool_correctness", "expected_tools": ["compute_correlation"]}]}]}
    gp = tmp_path / "g.yaml"; gp.write_text(yaml.safe_dump(golden))
    report = run_evals(FACTOR_SKILL, runner=boom, judge=None, parquet=fixtures_parquet, golden_path=gp)
    assert report.cases[0].checks[0].type == "error" and not report.passed


def test_geval_without_judge_raises(tmp_path: Path, fixtures_parquet: Path):
    golden = {"cases": [{"id": "g", "input": "x", "checks": [{"type": "geval", "criteria": "good?"}]}]}
    gp = tmp_path / "g.yaml"; gp.write_text(yaml.safe_dump(golden))
    with pytest.raises(ValueError, match="no judge"):
        run_evals(FACTOR_SKILL, runner=lambda s: RunResult("x", []), judge=None,
                  parquet=fixtures_parquet, golden_path=gp)
```

- [ ] **Step 5: Run** — `uv run pytest common/tests/ -v` → all PASS (offline). **Step 6: Commit**

```bash
git add common/lab_common/eval_harness.py common/lab_common/deepeval_metrics.py common/tests/test_eval_harness.py
git rm common/lab_common/scorers.py common/tests/test_scorers.py
git commit -m "feat: rebuild run_evals on DeepEval with an injectable Agent-SDK runner; drop bespoke scorers"
```

---

## Task 6: Execution-agnostic SKILL.md + new golden set + live test + spec

**Files:** Rewrite `skills/factor_correlation/SKILL.md` (body), `skills/factor_correlation/evals/golden.yaml`, `skills/factor_correlation/tests/test_eval_live.py`; Modify the spec.

- [ ] **Step 1: Rewrite the SKILL.md body** (keep the frontmatter unchanged; replace the `# Factor Correlation` body with an execution-agnostic version — capability + tools + reporting rules, NOT a Bash CLI). Replace everything after the closing `---` with:

```markdown
# Factor Correlation

Answer questions about how stock/ETF returns relate over a date window, using the tools provided.

## Available tools
- `list_tickers` — which tickers exist in the warehouse.
- `compute_correlation(tickers, start, end)` — Pearson correlation of daily returns; returns a matrix (and a correlation_value for two tickers). Use for correlations.
- `get_returns_stats(ticker, start, end)` — mean daily return, volatility, n_days for one ticker. Use for volatility/return stats.
- `run_sql(query)` — read-only SELECT over `prices(ticker, date, close)`. Use ONLY for questions the typed tools cannot answer (e.g. max/min close).

## How to work
- Prefer the typed tools over `run_sql` whenever they cover the question.
- For "which is more correlated" questions, call `compute_correlation` once for all tickers, then compare.

## Reporting rules
- Report correlations to two decimal places and name the date window used.
- These are correlations of DAILY RETURNS, not price levels — say so explicitly.
- If a requested ticker is missing from the warehouse, name it and stop; never guess values.
```

- [ ] **Step 2: Rewrite `skills/factor_correlation/evals/golden.yaml`**

```yaml
cases:
  - id: corr_two_tickers
    input: "How correlated were AAPL and MSFT daily returns from 2025-01-01 to 2025-06-30?"
    checks:
      - type: deterministic
        tolerance: 0.01
      - type: tool_correctness
        expected_tools: [compute_correlation]
        exact_match: true        # asserts it did NOT also reach for run_sql
      - type: geval
        name: presentation
        criteria: >
          The answer states a correlation number, explicitly calls it a correlation of
          DAILY RETURNS (not price levels), and names the date window. Judge presentation
          only; do NOT verify the numeric value or treat unverifiable figures as fabricated.
        threshold: 0.7

  - id: winner_and_volatility            # the multi-step agentic case
    input: >
      Of MSFT and NVDA, which was more correlated with AAPL's daily returns from
      2025-01-01 to 2025-06-30, and how volatile was that winner over the same window?
    checks:
      - type: deterministic
        tolerance: 0.01
      - type: tool_correctness
        expected_tools: [compute_correlation, get_returns_stats]
        ordered: true            # correlation first, then stats on the winner
        exact_match: true        # and NOT run_sql / nothing extraneous
      - type: geval
        name: conclusion
        criteria: >
          The answer identifies NVDA (not MSFT) as more correlated with AAPL, and reports
          NVDA's daily-return volatility over the window, described as daily-return based.
          Judge the stated conclusion and completeness only.
        threshold: 0.7

  - id: flexible_query_uses_sql          # long-tail query the typed tools can't answer
    input: "What was AAPL's single highest daily closing price between 2025-01-01 and 2025-06-30?"
    checks:
      - type: tool_correctness
        expected_tools: [run_sql]
        exact_match: true
      - type: geval
        name: answered
        criteria: >
          The answer gives a single highest closing price for AAPL in the window as a
          concrete dollar figure. Judge only that it answered with a max close.
        threshold: 0.7

  - id: refuses_missing_ticker
    input: "How correlated were AAPL and ZZZTOP daily returns from 2025-01-01 to 2025-06-30?"
    checks:
      - type: geval
        name: refusal
        criteria: >
          The answer makes clear it could NOT compute the correlation because ZZZTOP is
          not in the warehouse, and names ZZZTOP. It must NOT invent a correlation value.
        threshold: 0.7
```

- [ ] **Step 3: Rewrite `skills/factor_correlation/tests/test_eval_live.py`** (live: real Agent SDK + DeepEval; marked `eval`)

```python
"""Live smoke: real Agent-SDK run + DeepEval scoring against the fixtures parquet.
Marked `eval` (deselected by default). Run: uv run pytest -m eval. Needs the claude CLI + key."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.eval

REPO_ROOT = Path(__file__).resolve().parents[3]
FACTOR_SKILL = REPO_ROOT / "skills" / "factor_correlation"


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
def test_live_eval_runs(fixtures_parquet: Path):
    from lab_common.agent_runner import make_sdk_runner
    from lab_common.deepeval_metrics import make_judge
    from lab_common.eval_harness import run_evals
    from lab_common.skill_spec import load_skill

    os.environ["PRICES_PARQUET"] = str(fixtures_parquet)
    spec = load_skill(FACTOR_SKILL)
    mod = importlib.import_module("factor_correlation.agent_tools")
    runner = make_sdk_runner(spec, mod.SERVER, mod.ALLOWED_TOOLS, "claude-haiku-4-5")
    judge, _ = make_judge()
    report = run_evals(FACTOR_SKILL, runner=runner, judge=judge, parquet=fixtures_parquet)
    assert len(report.cases) == 4
    det = next(k for c in report.cases if c.case_id == "corr_two_tickers"
               for k in c.checks if k.type == "deterministic")
    assert det.passed, det.detail
```

- [ ] **Step 4: Update the spec** — in `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md`, in the "Eval harness and CI gates" section, replace the DeepEval-deferral / bespoke-harness wording with: the harness runs the skill through the **Claude Agent SDK** (the same runtime the M5 host uses), isolated via `setting_sources=[]` + a string `system_prompt`, and scores with **DeepEval** (GEval judge with a configurable cross-family model, ToolCorrectnessMetric for the trajectory, a custom BaseMetric for the deterministic recompute). Note the skill exposes four tools so traces are multi-step, and that running this in CI (M3) requires the `claude` CLI + Node in the runner.

- [ ] **Step 5: Run the offline gate** — `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv run ruff check . && uv run mypy . && uv run pytest -q` → green, the live test deselected. **Step 6: Commit**

```bash
git add skills/factor_correlation/SKILL.md skills/factor_correlation/evals/golden.yaml skills/factor_correlation/tests/test_eval_live.py docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md
git commit -m "feat: execution-agnostic SKILL.md, 4-case DeepEval golden set, live Agent-SDK eval; spec updated"
```

---

## Task 7: Live run + calibrate + LEARNINGS

The `.env` key and `claude` CLI are present, so this runs now.

- [ ] **Step 1: Run** — `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv run python -m lab_common.eval_harness skills/factor_correlation --haiku --report eval_report.json`. Expected: 4 cases scored; report prints the judge family; deterministic on `corr_two_tickers` passes; `winner_and_volatility` trace shows `compute_correlation` then `get_returns_stats` (the ToolSearch call is filtered out).

- [ ] **Step 2: Inspect the multi-step + SQL cases.** If `winner_and_volatility` fails `tool_correctness`, read why (did the agent add a `list_tickers` discovery call, skip `get_returns_stats`, use `run_sql`, or get the order wrong?). Decide: tighten/loosen `ordered`/`exact_match`, or it's a real agent misstep (a finding). Same for `flexible_query_uses_sql` (did it actually use `run_sql`?).

- [ ] **Step 3: Calibrate** any geval that straddles `min_score` across 3+ runs (one change, re-run).

- [ ] **Step 4: Append a LEARNINGS entry** covering: the Agent-SDK switch (real-runtime parity; ToolSearch filtering; `setting_sources=[]`/string-`system_prompt` isolation), what `ToolCorrectness` with `ordered`+`exact_match` caught on the multi-step trace, cross-family vs Claude judge (if an OpenAI/Gemini key was added), and that CI (M3) will need the `claude` CLI + Node in the runner image. Commit + push.

```bash
git add LEARNINGS.md skills/factor_correlation/evals/golden.yaml
git commit -m "docs: Agent-SDK + DeepEval multi-tool eval learnings + calibration"
git push
```

**Acceptance:** harness runs the skill through the Agent SDK and scores with DeepEval; the 4-tool skill yields a real multi-step trace; offline suite green + free CI keyless; live run passes with LEARNINGS recorded.

---

## Self-review notes (issues found and fixed inline)

- **Spec coverage:** Agent-SDK substrate for eval+host → Task 3 (`run_skill`/`make_sdk_runner`, reused by M5); isolation (`setting_sources=[]`, string `system_prompt`) → Task 3; 4-tool skill → Tasks 1-2; in-process MCP tools → Task 2; DeepEval (GEval/ToolCorrectness/custom) → Tasks 4-5; cross-family judge → Task 4; multi-step golden case asserting order + no-run_sql → Task 6; deterministic oracle as BaseMetric → Task 4; harness-tool filtering (ToolSearch) → Task 3 `build_runresult`; execution-agnostic SKILL.md (parity for the system prompt) → Task 6. M3 CI wiring + container explicitly out of scope (noted for M3).
- **Type consistency:** `make_sdk_runner(spec, server, allowed_tools, model) -> Callable[[str], RunResult]`; `run_evals(skill_dir, *, runner, judge, parquet, golden_path=None)`; `build_runresult(tool_uses, tool_results, final_text)`; `build_metric(check, *, judge, parquet)`; `to_test_case(input_text, run, expected_tools)`; `DeterministicCorrelationMetric(parquet, tolerance)` — all consistent across tasks. `agent_tools` exports `SERVER`, `ALLOWED_TOOLS`, and `_*_impl` functions used by the tests and `main`.
- **Placeholder scan:** clean; complete code in every step.
- **Known risks:** (1) Tools run **in-process** and read `$PRICES_PARQUET`; `main`/live-test set it before running — if unset, tools error (caught → error JSON). (2) The `claude` CLI + Node must be present to run the live path (here yes; CI is M3). (3) `should_exact_match`/`ordered` on the multi-step case may be too strict if a valid agent adds a discovery call — Task 7 Step 2 checks and adjusts. (4) `system_prompt` as a string replaces the CC default (verified via the field type `str | preset | file`); the execution-agnostic SKILL.md (Task 6) keeps that prompt aligned with the tool-based runtime.
```
