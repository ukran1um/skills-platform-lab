# M5: Skill Host + Promotion Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the skill host — a service that runs a *blessed* skill server-side through the Claude Agent SDK, injecting a scoped capability token so the skill's tools fetch through the governed Data MCP (platform context) — and author a second skill, `market_brief`, through the full promotion path to make path-filtering and two-scope-sets real.

**Architecture:** The host is the governance wrapper around the already-built `run_skill` runtime. On a request it (1) **loads** the skill only if `reconcile` reports it `blessed`, (2) **mints** a least-privilege capability token for `(user, skill)` — the user must hold every scope the skill declares, and the token carries exactly those, (3) **injects the platform context** (the Data MCP base URL + token) via two env vars the skill's in-process tools read at call time — the proven `$PRICES_PARQUET` mechanism, serialized by a host lock so the process-global env is never shared across concurrent runs — and (4) runs the async Agent-SDK loop, returning `final_text` + trajectory. The agent run is injectable so the host's governance logic is unit-tested offline without the SDK; one eval-marked live test proves the full HTTP→host→agent→Data-MCP round-trip. A skill becomes context-portable by routing its data fetch through a tiny `platform_context()` check: platform → Data MCP (capability-scoped), else laptop → direct parquet. `market_brief` (prices:read + fundamentals:read) is the second skill that makes the scope distinction and blast-radius declaration genuinely load-bearing for more than one skill.

**Tech Stack:** Python 3.12, uv workspace, **FastAPI** + **uvicorn** (the host service), **httpx** (TestClient), Claude Agent SDK (reused `run_skill`), `lab_common.capability` (HS256 tokens), `lab_common.mcp` (Data MCP client), DuckDB/pandas, DeepEval (the `market_brief` golden), pytest. All host *logic* tests are keyless (free `checks` gate); the live agent tests are `eval`-marked (PR-only, need the `claude` CLI + `ANTHROPIC_API_KEY`).

**Spec:** `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md` (§ skill host / two execution contexts / promotion path). Out of scope: M6/M7 knowledge-base.

**Current-state facts the implementer must rely on (verified before writing this plan):**
- `lab_common.agent_runner.run_skill(spec, user_input, *, server, allowed_tools, model=…, max_turns=…)` is **async**; the host `await`s it directly. It hardcodes the MCP key `"factor"` (`mcp_servers={"factor": server}`) — Task 1 generalizes this to a `server_name` param so `market_brief`'s tools aren't cosmetically prefixed `mcp__factor__`. `build_runresult` already strips any `mcp__<server>__` prefix.
- `lab_common.governance.reconcile.reconcile_skill(skill_dir, registry_path, source_commit) -> dict` returns `{"status": "blessed"|"candidate"|"deprecated", "agreement_errors": [...], ...}`. `blessed` only when SKILL.md frontmatter and `registry/<skill>.yaml` agree on `(name, version, blast_radius, allowed_mcp_servers, required_scopes)`.
- `lab_common.skill_spec.load_skill(skill_dir) -> SkillSpec` (fields: `name, version, owner, blast_radius, allowed_mcp_servers, required_scopes, golden_set, threshold, system_prompt`).
- `lab_common.capability.mint(*, sub, skill, scopes, audience, secret, ttl_seconds=900) -> str` and `verify(token, *, audience, secret) -> Claims`. HS256, secret must be **≥32 bytes**. `Claims.has_scope(s)`.
- `registry/entitlements.yaml` → `users:` maps a user to granted scopes (`egor` has all five). Scope vocab includes `prices:read`, `fundamentals:read`, `query:run`.
- A skill's `agent_tools` module exports `SERVER` (a config dict from `create_sdk_mcp_server`) and `ALLOWED_TOOLS` (e.g. `["mcp__factor__compute_correlation", …]`). Imported offline without a key (no CLI spawn at import).
- `golden_set` is a **path relative to the skill dir**; `factor_correlation` uses `evals/golden.yaml`. `run_evals(skill_dir, *, runner, judge, parquet, golden_path=None)`; `make_judge(provider=None, env=None) -> (judge, name)`.
- Workspace members glob: `["data", "skills/*", "common", "services/*"]` — new dirs under `skills/` and `services/` are picked up automatically by `uv sync --all-packages`.
- Live-server test pattern (uvicorn in a daemon thread + a free port) lives in `services/data_mcp/tests/test_integration_http.py`; reuse it for keyless platform-path tests.
- **Branch + PR is mandatory** (main is protected; direct-to-main blocked). Work is on branch `m5-skill-host`.

---

## File Structure

**New — the skill host (`services/skill_host/`):**
- `pyproject.toml` — package `skill-host`; deps `fastapi`, `uvicorn`, `httpx`, `pyyaml`, `lab-common`.
- `skill_host/__init__.py`
- `skill_host/errors.py` — host exceptions mapped to HTTP status (404/403).
- `skill_host/loader.py` — `load_blessed_skill` (reconcile gate + importlib the tool surface).
- `skill_host/scoping.py` — `mint_scoped_token` (entitlement check + least-privilege token).
- `skill_host/host.py` — `run_skill_request` orchestration (load → mint → inject context → run), injectable runner, host lock.
- `skill_host/app.py` — FastAPI `POST /run` + `GET /healthz`; error→HTTP mapping; `create_app(...)` factory; `main()`.
- `tests/test_loader.py`, `tests/test_scoping.py`, `tests/test_host.py`, `tests/test_app.py` — keyless.
- `tests/test_host_live.py` — `eval`-marked end-to-end (real agent + live Data MCP).

**New — `lab_common.exec_context` (the platform-context contract):**
- `common/lab_common/exec_context.py` + `common/tests/test_exec_context.py`.

**New — the second skill (`skills/market_brief/`):**
- `pyproject.toml`, `market_brief/__init__.py`, `SKILL.md`, `market_brief/tools/__init__.py`, `market_brief/tools/fetch.py`, `market_brief/agent_tools.py`, `evals/golden.yaml`.
- `tests/test_fetch.py` (keyless: laptop + live-MCP platform), `tests/test_governance.py` (keyless: reconciles to blessed), `tests/test_eval_live.py` (`eval`-marked).
- `registry/market_brief.yaml` — the governance approval record (`status: blessed`).

**Modified:**
- `common/lab_common/agent_runner.py` — `server_name` param on `run_skill`/`make_sdk_runner`.
- `common/lab_common/eval_harness.py` — CLI passes `server_name=getattr(mod, "SERVER_NAME", "factor")`.
- `skills/factor_correlation/factor_correlation/agent_tools.py` — add `SERVER_NAME = "factor"`; route impls through context-aware fetch.
- `skills/factor_correlation/factor_correlation/tools/fetch.py` — add `get_prices_auto`.
- `skills/factor_correlation/factor_correlation/cli.py` — `run()` uses `get_prices_auto`.
- `README.md`, `LEARNINGS.md`, the design spec — M5 docs.

---

## Task 1: Generalize the runtime for a per-skill MCP server name

So a second skill's tools aren't forced under the `mcp__factor__` prefix. Backward-compatible: `server_name` defaults to `"factor"`.

**Files:**
- Modify: `common/lab_common/agent_runner.py`
- Modify: `common/lab_common/eval_harness.py:113-115`
- Modify: `skills/factor_correlation/factor_correlation/agent_tools.py` (add `SERVER_NAME`)
- Test: `common/tests/test_agent_runner.py`

- [ ] **Step 1: Write the failing tests** — append to `common/tests/test_agent_runner.py`:

```python
def test_build_runresult_strips_any_server_prefix():
    # Trajectory parsing must be server-name-agnostic (works for mcp__brief__ too).
    from lab_common.agent_runner import build_runresult
    rr = build_runresult(
        tool_uses=[("t1", "mcp__brief__get_market_data", {"ticker": "AAPL"})],
        tool_results={"t1": "{}"},
        final_text="ok",
    )
    assert rr.trajectory[0].name == "get_market_data"


def test_make_sdk_runner_accepts_server_name():
    # The closure must accept the server_name kwarg without constructing the SDK.
    from lab_common.agent_runner import make_sdk_runner
    from lab_common.models import SkillSpec
    spec = SkillSpec(name="x", version="0", owner="", blast_radius="", allowed_mcp_servers=[],
                     required_scopes=[], golden_set="", threshold=0.0, system_prompt="p")
    runner = make_sdk_runner(spec, {"type": "sdk"}, ["mcp__brief__x"], server_name="brief")
    assert callable(runner)
```

- [ ] **Step 2: Run them to confirm they fail**

Run: `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv run pytest common/tests/test_agent_runner.py -k "server" -v`
Expected: FAIL — `make_sdk_runner() got an unexpected keyword argument 'server_name'`.

- [ ] **Step 3: Add `server_name` to `run_skill` and `make_sdk_runner`**

In `common/lab_common/agent_runner.py`, change the `run_skill` signature and the `mcp_servers` line:

```python
async def run_skill(
    spec: SkillSpec,
    user_input: str,
    *,
    server: Any,
    allowed_tools: list[str],
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    server_name: str = "factor",
) -> RunResult:
```

```python
    opts = ClaudeAgentOptions(
        mcp_servers={server_name: server},
        allowed_tools=allowed_tools,
```

And `make_sdk_runner`:

```python
def make_sdk_runner(
    spec: SkillSpec, server: Any, allowed_tools: list[str], model: str = DEFAULT_MODEL,
    *, server_name: str = "factor",
) -> Callable[[str], RunResult]:
    def runner(user_input: str) -> RunResult:
        return asyncio.run(run_skill(spec, user_input, server=server,
                                     allowed_tools=allowed_tools, model=model,
                                     server_name=server_name))
    return runner
```

- [ ] **Step 4: Add `SERVER_NAME` to factor_correlation and thread it through the eval CLI**

In `skills/factor_correlation/factor_correlation/agent_tools.py`, just above `SERVER = create_sdk_mcp_server(`:

```python
SERVER_NAME = "factor"
```

In `common/lab_common/eval_harness.py` (the CLI `main`, around line 114-115), pass the skill's server name:

```python
    mod = importlib.import_module(f"{spec.name}.agent_tools")
    runner = make_sdk_runner(spec, mod.SERVER, mod.ALLOWED_TOOLS, model,
                             server_name=getattr(mod, "SERVER_NAME", "factor"))
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest common/tests/test_agent_runner.py -v`
Expected: PASS (all, including the two new ones).

- [ ] **Step 6: Commit**

```bash
git add common/lab_common/agent_runner.py common/lab_common/eval_harness.py \
        skills/factor_correlation/factor_correlation/agent_tools.py common/tests/test_agent_runner.py
git commit -m "feat(runtime): per-skill MCP server_name (default factor); enables a second skill"
```

---

## Task 2: The platform-context contract (`lab_common.exec_context`)

The single source of truth for how the host tells a skill "fetch through the Data MCP with this token."

**Files:**
- Create: `common/lab_common/exec_context.py`
- Test: `common/tests/test_exec_context.py`

- [ ] **Step 1: Write the failing test** — `common/tests/test_exec_context.py`:

```python
import os

from lab_common.exec_context import platform_context, use_platform_context


def test_no_context_by_default(monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    assert platform_context() is None


def test_context_active_inside_block(monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    with use_platform_context("http://h/mcp", "tok"):
        assert platform_context() == ("http://h/mcp", "tok")
    assert platform_context() is None  # restored after the block


def test_context_restores_prior_value(monkeypatch):
    monkeypatch.setenv("DATA_MCP_URL", "http://old/mcp")
    monkeypatch.setenv("DATA_MCP_TOKEN", "old")
    with use_platform_context("http://new/mcp", "new"):
        assert platform_context() == ("http://new/mcp", "new")
    assert os.environ["DATA_MCP_URL"] == "http://old/mcp"
    assert os.environ["DATA_MCP_TOKEN"] == "old"


def test_partial_env_is_not_a_context(monkeypatch):
    monkeypatch.setenv("DATA_MCP_URL", "http://h/mcp")
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    assert platform_context() is None  # need BOTH url and token
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `uv run pytest common/tests/test_exec_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lab_common.exec_context'`.

- [ ] **Step 3: Implement** — `common/lab_common/exec_context.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest common/tests/test_exec_context.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add common/lab_common/exec_context.py common/tests/test_exec_context.py
git commit -m "feat(exec_context): platform-context env contract (DATA_MCP_URL/TOKEN)"
```

---

## Task 3: Make factor_correlation context-portable (`get_prices_auto`)

The same skill, two execution contexts: platform → Data MCP, laptop → direct parquet. Laptop behavior is unchanged when no context is active.

**Files:**
- Modify: `skills/factor_correlation/factor_correlation/tools/fetch.py` (add `get_prices_auto`)
- Modify: `skills/factor_correlation/factor_correlation/cli.py:20` (use `get_prices_auto`)
- Modify: `skills/factor_correlation/factor_correlation/agent_tools.py` (`_returns_stats_impl` uses `get_prices_auto`)
- Test: `skills/factor_correlation/tests/test_fetch_auto.py`

- [ ] **Step 1: Write the failing tests** — `skills/factor_correlation/tests/test_fetch_auto.py`:

```python
"""get_prices_auto routes by execution context: laptop (direct parquet) by default,
platform (Data MCP) when a platform context is active. The platform test stands up a real
Data MCP server in a thread — keyless, no agent."""

from __future__ import annotations

import socket
import threading
import time
from datetime import date
from pathlib import Path

import pytest
import uvicorn

from factor_correlation.tools.fetch import get_prices_auto
from lab_common.capability import mint
from lab_common.exec_context import use_platform_context

SECRET = "m5-fetch-auto-test-secret-32bytes!!"


def test_laptop_context_reads_parquet(fixtures_parquet: Path, monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    df = get_prices_auto(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 3, 31),
                         parquet=fixtures_parquet)
    assert not df.empty and set(df["ticker"].unique()) == {"AAPL", "MSFT"}


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def live_data_mcp(fixtures_parquet: Path, monkeypatch):
    from data_mcp.server import build_app
    monkeypatch.setenv("CAPABILITY_SECRET", SECRET)
    port = _free_port()
    config = uvicorn.Config(build_app(parquet=fixtures_parquet), host="127.0.0.1",
                            port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    thread.join(timeout=5)


def test_platform_context_routes_via_mcp(live_data_mcp: str):
    tok = mint(sub="egor", skill="factor_correlation", scopes=["prices:read"],
               audience="data_mcp", secret=SECRET)
    with use_platform_context(live_data_mcp, tok):
        df = get_prices_auto(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 3, 31))
    assert not df.empty and set(df["ticker"].unique()) == {"AAPL", "MSFT"}
```

- [ ] **Step 2: Run them to confirm they fail**

Run: `uv run pytest skills/factor_correlation/tests/test_fetch_auto.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_prices_auto'`.

- [ ] **Step 3: Add `get_prices_auto`** to `skills/factor_correlation/factor_correlation/tools/fetch.py` (after `get_prices_via_mcp`):

```python
def get_prices_auto(
    tickers: list[str], start: date, end: date, parquet: Path | None = None
) -> pd.DataFrame:
    """Route the price fetch by execution context. Platform context (set by the skill host) ->
    the governed Data MCP, capability-scoped. Laptop context -> direct parquet. Same row shape."""
    from lab_common.exec_context import platform_context

    ctx = platform_context()
    if ctx is not None:
        base_url, token = ctx
        return get_prices_via_mcp(tickers, start, end, token=token, base_url=base_url)
    return get_prices(tickers, start, end, parquet=parquet)
```

- [ ] **Step 4: Route the skill's compute paths through it**

In `skills/factor_correlation/factor_correlation/cli.py`, change the import and the fetch line in `run()`:

```python
from factor_correlation.tools.fetch import get_prices_auto
```
```python
    prices = get_prices_auto(tickers, start, end, parquet=parquet)
```

(Remove the now-unused `get_prices` import from `cli.py` if ruff flags it.)

In `skills/factor_correlation/factor_correlation/agent_tools.py`, update `_returns_stats_impl` to use the auto router and update the import line `from factor_correlation.tools.fetch import get_prices, list_tickers, run_sql`:

```python
from factor_correlation.tools.fetch import get_prices_auto, list_tickers, run_sql
```
```python
def _returns_stats_impl(args: dict[str, Any]) -> str:
    try:
        prices = get_prices_auto([args["ticker"]], date.fromisoformat(args["start"]),
                                 date.fromisoformat(args["end"]))
        if prices.empty:
            return json.dumps({"error": f"no data for {args['ticker']}"})
        return json.dumps(returns_stats(prices))
    except Exception as exc:  # noqa: BLE001 — tool boundary: never crash the loop
        return json.dumps({"error": str(exc)})
```

(`_compute_correlation_impl` calls `cli.run`, which now uses `get_prices_auto`, so correlation auto-routes too. `_run_sql_impl` stays laptop — `run_sql` is the escape hatch and `factor_correlation` does not declare `query:run`.)

- [ ] **Step 5: Run the new test + the existing factor_correlation suite (no regressions)**

Run: `uv run pytest skills/factor_correlation -q`
Expected: PASS (existing tests + the 2 new ones; the platform test stands up the Data MCP server).

- [ ] **Step 6: Commit**

```bash
git add skills/factor_correlation/factor_correlation/tools/fetch.py \
        skills/factor_correlation/factor_correlation/cli.py \
        skills/factor_correlation/factor_correlation/agent_tools.py \
        skills/factor_correlation/tests/test_fetch_auto.py
git commit -m "feat(factor_correlation): context-portable fetch (laptop|platform via get_prices_auto)"
```

---

## Task 4: Host governance core — loader + scoping

The two gates the host enforces before any agent runs: **only blessed skills** load, and **the user must hold every scope the skill declares**.

**Files:**
- Create: `services/skill_host/pyproject.toml`
- Create: `services/skill_host/skill_host/__init__.py`
- Create: `services/skill_host/skill_host/errors.py`
- Create: `services/skill_host/skill_host/loader.py`
- Create: `services/skill_host/skill_host/scoping.py`
- Test: `services/skill_host/tests/test_loader.py`, `services/skill_host/tests/test_scoping.py`

- [ ] **Step 1: Create the package scaffold**

`services/skill_host/pyproject.toml`:

```toml
[project]
name = "skill-host"
version = "0.1.0"
description = "Runs blessed skills server-side with scoped, governed MCP access"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "httpx>=0.27",
    "pyyaml>=6",
    "lab-common",
]

[tool.uv.sources]
lab-common = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["skill_host"]
```

`services/skill_host/skill_host/__init__.py`: empty file.

- [ ] **Step 2: Write the failing tests** — `services/skill_host/tests/test_loader.py`:

```python
"""The host loads ONLY blessed skills. Uses the real repo skills/ + registry/ for the happy
path; a tmp candidate skill for the rejection path (status checked before any import)."""

from __future__ import annotations

from pathlib import Path

import pytest

from skill_host.errors import SkillNotBlessedError, SkillNotFoundError
from skill_host.loader import load_blessed_skill

REPO = Path(__file__).resolve().parents[3]
SKILLS, REGISTRY = REPO / "skills", REPO / "registry"


def test_loads_blessed_skill():
    loaded = load_blessed_skill("factor_correlation", skills_dir=SKILLS, registry_dir=REGISTRY)
    assert loaded.status == "blessed"
    assert loaded.server_name == "factor"
    assert "mcp__factor__compute_correlation" in loaded.allowed_tools
    assert loaded.spec.required_scopes == ["prices:read"]


def test_unknown_skill_raises_not_found():
    with pytest.raises(SkillNotFoundError):
        load_blessed_skill("does_not_exist", skills_dir=SKILLS, registry_dir=REGISTRY)


def test_candidate_skill_is_refused(tmp_path: Path):
    skills = tmp_path / "skills"
    registry = tmp_path / "registry"
    (skills / "tmpskill").mkdir(parents=True)
    registry.mkdir()
    (skills / "tmpskill" / "SKILL.md").write_text(
        "---\nname: tmpskill\nversion: 0.1.0\nblast_radius: low\n"
        "allowed_mcp_servers: []\nrequired_scopes: []\n---\nbody\n")
    (registry / "tmpskill.yaml").write_text(
        "name: tmpskill\nversion: 0.1.0\nblast_radius: low\n"
        "allowed_mcp_servers: []\nrequired_scopes: []\nstatus: candidate\n")
    with pytest.raises(SkillNotBlessedError):
        load_blessed_skill("tmpskill", skills_dir=skills, registry_dir=registry)
```

`services/skill_host/tests/test_scoping.py`:

```python
"""Least-privilege token minting: the user must hold EVERY scope the skill declares; the
token then carries exactly those (required ⊆ granted)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab_common.capability import verify
from lab_common.models import SkillSpec
from skill_host.errors import EntitlementError
from skill_host.scoping import mint_scoped_token

REPO = Path(__file__).resolve().parents[3]
ENTITLEMENTS = REPO / "registry" / "entitlements.yaml"
SECRET = "skill-host-scoping-test-secret-32!"


def _spec(scopes):
    return SkillSpec(name="s", version="0", owner="", blast_radius="", allowed_mcp_servers=[],
                     required_scopes=scopes, golden_set="", threshold=0.0, system_prompt="p")


def test_mints_least_privilege_token_for_entitled_user():
    token, scopes = mint_scoped_token(_spec(["prices:read"]), "egor",
                                      entitlements_path=ENTITLEMENTS, secret=SECRET)
    assert scopes == ["prices:read"]
    claims = verify(token, audience="data_mcp", secret=SECRET)
    assert claims.sub == "egor" and claims.has_scope("prices:read")


def test_unknown_user_is_denied():
    with pytest.raises(EntitlementError):
        mint_scoped_token(_spec(["prices:read"]), "nobody",
                          entitlements_path=ENTITLEMENTS, secret=SECRET)


def test_missing_required_scope_is_denied(tmp_path: Path):
    ent = tmp_path / "entitlements.yaml"
    ent.write_text("users:\n  bob: [prices:read]\n")
    with pytest.raises(EntitlementError):
        mint_scoped_token(_spec(["prices:read", "fundamentals:read"]), "bob",
                          entitlements_path=ent, secret=SECRET)
```

- [ ] **Step 3: Run them to confirm they fail**

Run: `uv run pytest services/skill_host -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skill_host'` (sync the workspace in Step 4 first if collection errors).

- [ ] **Step 4: Implement errors, loader, scoping**

`services/skill_host/skill_host/errors.py`:

```python
"""Host errors, mapped to HTTP by the API layer."""

from __future__ import annotations


class HostError(Exception):
    """Base for all skill-host errors."""


class SkillNotFoundError(HostError):
    """No skill directory / registry record by that name (-> 404)."""


class SkillNotBlessedError(HostError):
    """The skill exists but reconcile did not bless it (-> 403)."""


class EntitlementError(HostError):
    """The user is unknown or lacks a scope the skill requires (-> 403)."""
```

`services/skill_host/skill_host/loader.py`:

```python
"""Load a BLESSED skill for execution: reconcile its declared state, refuse anything not
blessed, then import its Agent-SDK tool surface. The host runs only what governance blessed."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lab_common.governance.reconcile import reconcile_skill
from lab_common.models import SkillSpec
from lab_common.skill_spec import load_skill

from skill_host.errors import SkillNotBlessedError, SkillNotFoundError


@dataclass
class LoadedSkill:
    spec: SkillSpec
    server: Any
    allowed_tools: list[str]
    server_name: str
    status: str


def load_blessed_skill(
    skill_name: str, *, skills_dir: str | Path, registry_dir: str | Path,
    source_commit: str = "local",
) -> LoadedSkill:
    skills_dir, registry_dir = Path(skills_dir), Path(registry_dir)
    skill_dir = skills_dir / skill_name
    registry_path = registry_dir / f"{skill_name}.yaml"
    if not (skill_dir / "SKILL.md").exists() or not registry_path.exists():
        raise SkillNotFoundError(f"no skill named {skill_name!r}")
    record = reconcile_skill(skill_dir, registry_path, source_commit)
    if record["status"] != "blessed":
        raise SkillNotBlessedError(
            f"{skill_name} is {record['status']} "
            f"(agreement errors: {record['agreement_errors']})")
    spec = load_skill(skill_dir)
    mod = importlib.import_module(f"{spec.name}.agent_tools")
    return LoadedSkill(
        spec=spec, server=mod.SERVER, allowed_tools=list(mod.ALLOWED_TOOLS),
        server_name=getattr(mod, "SERVER_NAME", "factor"), status=record["status"])
```

`services/skill_host/skill_host/scoping.py`:

```python
"""Mint a least-privilege capability token for a (user, skill): the user must hold every
scope the skill declares; the token then carries exactly those (required ⊆ granted)."""

from __future__ import annotations

from pathlib import Path

import yaml

from lab_common.capability import mint
from lab_common.models import SkillSpec

from skill_host.errors import EntitlementError

AUDIENCE = "data_mcp"


def _entitlements(path: str | Path) -> dict[str, list[str]]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return data.get("users", {})


def mint_scoped_token(
    spec: SkillSpec, user: str, *, entitlements_path: str | Path, secret: str,
    ttl_seconds: int = 900,
) -> tuple[str, list[str]]:
    users = _entitlements(entitlements_path)
    if user not in users:
        raise EntitlementError(f"unknown user {user!r}")
    granted = set(users[user])
    required = set(spec.required_scopes)
    missing = sorted(required - granted)
    if missing:
        raise EntitlementError(f"{user} lacks required scope(s) for {spec.name}: {missing}")
    scopes = sorted(required)  # required ⊆ granted -> least privilege
    token = mint(sub=user, skill=spec.name, scopes=scopes, audience=AUDIENCE,
                 secret=secret, ttl_seconds=ttl_seconds)
    return token, scopes
```

- [ ] **Step 5: Sync the workspace and run the tests**

Run: `uv sync --all-packages >/dev/null && uv run pytest services/skill_host/tests/test_loader.py services/skill_host/tests/test_scoping.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add services/skill_host/pyproject.toml services/skill_host/skill_host/__init__.py \
        services/skill_host/skill_host/errors.py services/skill_host/skill_host/loader.py \
        services/skill_host/skill_host/scoping.py services/skill_host/tests/
git commit -m "feat(skill_host): governance core — blessed-only loader + least-privilege scoping"
```

---

## Task 5: Host orchestration + FastAPI surface

Wire load → mint → inject platform context → run; expose `POST /run`. The agent run is injectable, so this is fully testable offline.

**Files:**
- Create: `services/skill_host/skill_host/host.py`
- Create: `services/skill_host/skill_host/app.py`
- Test: `services/skill_host/tests/test_host.py`, `services/skill_host/tests/test_app.py`

- [ ] **Step 1: Write the failing host tests** — `services/skill_host/tests/test_host.py`:

```python
"""The host orchestration, with the agent run replaced by a fake runner so we can assert the
governance + context-injection behavior offline (no SDK, no key)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from lab_common.models import RunResult, ToolCall
from skill_host.errors import EntitlementError, SkillNotBlessedError
from skill_host.host import HostConfig, run_skill_request

REPO = Path(__file__).resolve().parents[3]
SECRET = "skill-host-orchestration-secret-32!"


def _config(**overrides) -> HostConfig:
    base = dict(skills_dir=REPO / "skills", registry_dir=REPO / "registry",
                entitlements_path=REPO / "registry" / "entitlements.yaml",
                data_mcp_base_url="http://data-mcp.test/mcp", secret=SECRET)
    base.update(overrides)
    return HostConfig(**base)


def test_runs_blessed_skill_in_platform_context():
    seen = {}

    async def fake_runner(loaded, message):
        from lab_common.exec_context import platform_context
        seen["ctx"] = platform_context()
        seen["message"] = message
        return RunResult(final_text="done",
                         trajectory=[ToolCall("compute_correlation", {"x": 1}, "{}")])

    resp = asyncio.run(run_skill_request(
        "factor_correlation", "How correlated were AAPL and MSFT?", "egor",
        config=_config(), runner=fake_runner))

    # The host set the platform context for the skill's tools (data_mcp is declared).
    assert seen["ctx"] is not None and seen["ctx"][0] == "http://data-mcp.test/mcp"
    assert seen["message"].startswith("How correlated")
    assert resp.scopes == ["prices:read"]
    assert resp.final_text == "done"
    assert resp.trajectory[0]["name"] == "compute_correlation"
    # Context is torn down after the run.
    from lab_common.exec_context import platform_context
    assert platform_context() is None


def test_not_blessed_propagates(tmp_path: Path):
    skills, registry = tmp_path / "skills", tmp_path / "registry"
    (skills / "tmpskill").mkdir(parents=True)
    registry.mkdir()
    (skills / "tmpskill" / "SKILL.md").write_text(
        "---\nname: tmpskill\nversion: 0.1.0\nblast_radius: low\n"
        "allowed_mcp_servers: []\nrequired_scopes: []\n---\nbody\n")
    (registry / "tmpskill.yaml").write_text(
        "name: tmpskill\nversion: 0.1.0\nblast_radius: low\n"
        "allowed_mcp_servers: []\nrequired_scopes: []\nstatus: candidate\n")

    async def fake_runner(loaded, message):  # never reached
        raise AssertionError("runner should not be called for an unblessed skill")

    with pytest.raises(SkillNotBlessedError):
        asyncio.run(run_skill_request("tmpskill", "hi", "egor",
                    config=_config(skills_dir=skills, registry_dir=registry),
                    runner=fake_runner))


def test_unentitled_user_propagates():
    async def fake_runner(loaded, message):  # never reached
        raise AssertionError("runner should not be called when entitlement fails")

    with pytest.raises(EntitlementError):
        asyncio.run(run_skill_request("factor_correlation", "hi", "nobody",
                    config=_config(), runner=fake_runner))
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest services/skill_host/tests/test_host.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skill_host.host'`.

- [ ] **Step 3: Implement `host.py`**

```python
"""The skill host: run a BLESSED skill in PLATFORM context. Load (governance gate) -> mint a
scoped capability token -> inject the platform context (the skill's tools then route through
the Data MCP with that token) -> run the Agent-SDK loop -> return final text + trajectory.

The agent run is injectable (`runner`) so the host's governance logic is testable offline
without the SDK. A process-wide lock serializes runs because the platform context is global
env (see lab_common.exec_context)."""

from __future__ import annotations

import asyncio
import os
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from lab_common.exec_context import use_platform_context
from lab_common.models import RunResult

from skill_host.loader import LoadedSkill, load_blessed_skill
from skill_host.scoping import mint_scoped_token

DEFAULT_DATA_MCP_BASE_URL = "http://127.0.0.1:8081/mcp"
SECRET_ENV = "CAPABILITY_SECRET"
DEFAULT_SECRET = "dev-secret-not-for-production-pad32"  # >=32 bytes; matches the Data MCP default

Runner = Callable[[LoadedSkill, str], Awaitable[RunResult]]


async def _default_runner(loaded: LoadedSkill, message: str) -> RunResult:
    from lab_common.agent_runner import run_skill
    return await run_skill(loaded.spec, message, server=loaded.server,
                           allowed_tools=loaded.allowed_tools, server_name=loaded.server_name)


@dataclass
class HostConfig:
    skills_dir: Path
    registry_dir: Path
    entitlements_path: Path
    data_mcp_base_url: str = DEFAULT_DATA_MCP_BASE_URL
    secret: str = field(default_factory=lambda: os.environ.get(SECRET_ENV, DEFAULT_SECRET))


@dataclass
class RunResponse:
    skill: str
    status: str
    user: str
    scopes: list[str]
    final_text: str | None
    trajectory: list[dict]


_run_lock = asyncio.Lock()


async def run_skill_request(
    skill: str, message: str, user: str, *, config: HostConfig,
    runner: Runner = _default_runner,
) -> RunResponse:
    loaded = load_blessed_skill(skill, skills_dir=config.skills_dir,
                                registry_dir=config.registry_dir)
    token, scopes = mint_scoped_token(loaded.spec, user,
                                      entitlements_path=config.entitlements_path,
                                      secret=config.secret)
    uses_mcp = "data_mcp" in loaded.spec.allowed_mcp_servers
    ctx = use_platform_context(config.data_mcp_base_url, token) if uses_mcp else nullcontext()
    async with _run_lock:  # platform context is process-global env; serialize runs
        with ctx:
            result = await runner(loaded, message)
    return RunResponse(
        skill=loaded.spec.name, status=loaded.status, user=user, scopes=scopes,
        final_text=result.final_text,
        trajectory=[{"name": c.name, "input": c.input, "result": c.result}
                    for c in result.trajectory])
```

- [ ] **Step 4: Run the host tests**

Run: `uv run pytest services/skill_host/tests/test_host.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the failing API tests** — `services/skill_host/tests/test_app.py`:

```python
"""The FastAPI surface: governance failures map to HTTP status; the happy path returns the
run result. The agent run is faked via create_app(runner=...)."""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from lab_common.models import RunResult, ToolCall
from skill_host.app import create_app
from skill_host.host import HostConfig

REPO = Path(__file__).resolve().parents[3]
SECRET = "skill-host-api-test-secret-32bytes!"


def _cfg() -> HostConfig:
    return HostConfig(skills_dir=REPO / "skills", registry_dir=REPO / "registry",
                      entitlements_path=REPO / "registry" / "entitlements.yaml",
                      data_mcp_base_url="http://data-mcp.test/mcp", secret=SECRET)


async def _fake_runner(loaded, message):
    return RunResult(final_text="brief done",
                     trajectory=[ToolCall("compute_correlation", {"x": 1}, "{}")])


def test_healthz():
    client = TestClient(create_app(config=_cfg(), runner=_fake_runner))
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_run_blessed_skill_returns_result():
    client = TestClient(create_app(config=_cfg(), runner=_fake_runner))
    r = client.post("/run", json={"skill": "factor_correlation",
                                  "message": "corr AAPL MSFT", "user": "egor"})
    assert r.status_code == 200
    body = r.json()
    assert body["scopes"] == ["prices:read"]
    assert body["final_text"] == "brief done"
    assert body["trajectory"][0]["name"] == "compute_correlation"


def test_unknown_skill_is_404():
    client = TestClient(create_app(config=_cfg(), runner=_fake_runner))
    r = client.post("/run", json={"skill": "nope", "message": "x", "user": "egor"})
    assert r.status_code == 404


def test_unentitled_user_is_403():
    client = TestClient(create_app(config=_cfg(), runner=_fake_runner))
    r = client.post("/run", json={"skill": "factor_correlation", "message": "x", "user": "nobody"})
    assert r.status_code == 403
```

- [ ] **Step 6: Implement `app.py`**

```python
"""FastAPI surface for the skill host. POST /run {skill, message, user} runs a blessed skill
in platform context. Governance failures map to HTTP: unknown skill -> 404; not blessed or
missing entitlement -> 403."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from skill_host.errors import EntitlementError, SkillNotBlessedError, SkillNotFoundError
from skill_host.host import HostConfig, Runner, _default_runner, run_skill_request


class RunBody(BaseModel):
    skill: str
    message: str
    user: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def create_app(*, config: HostConfig | None = None, runner: Runner = _default_runner) -> FastAPI:
    root = _repo_root()
    cfg = config or HostConfig(
        skills_dir=root / "skills", registry_dir=root / "registry",
        entitlements_path=root / "registry" / "entitlements.yaml")
    app = FastAPI(title="skills-platform-lab skill host")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/run")
    async def run(body: RunBody) -> dict[str, Any]:
        try:
            resp = await run_skill_request(body.skill, body.message, body.user,
                                           config=cfg, runner=runner)
        except SkillNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (SkillNotBlessedError, EntitlementError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {"skill": resp.skill, "status": resp.status, "user": resp.user,
                "scopes": resp.scopes, "final_text": resp.final_text,
                "trajectory": resp.trajectory}

    return app


def main() -> None:
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8082)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run the API tests**

Run: `uv run pytest services/skill_host/tests/test_app.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Commit**

```bash
git add services/skill_host/skill_host/host.py services/skill_host/skill_host/app.py \
        services/skill_host/tests/test_host.py services/skill_host/tests/test_app.py
git commit -m "feat(skill_host): run orchestration + FastAPI /run (load->mint->inject->run)"
```

---

## Task 6: The `market_brief` skill (code + governance)

The second blessed skill. Two scopes (`prices:read` + `fundamentals:read`) and a real `get_client("data_mcp")` call make the scope distinction and the blast-radius declaration load-bearing for more than one skill.

**Files:**
- Create: `skills/market_brief/pyproject.toml`, `skills/market_brief/market_brief/__init__.py`, `skills/market_brief/market_brief/tools/__init__.py`
- Create: `skills/market_brief/SKILL.md`
- Create: `skills/market_brief/market_brief/tools/fetch.py`
- Create: `skills/market_brief/market_brief/agent_tools.py`
- Create: `registry/market_brief.yaml`
- Test: `skills/market_brief/tests/test_fetch.py`, `skills/market_brief/tests/test_governance.py`

- [ ] **Step 1: Scaffold the package**

`skills/market_brief/pyproject.toml`:

```toml
[project]
name = "market-brief"
version = "0.1.0"
description = "Short factual brief on a single ticker over a date window"
requires-python = ">=3.12"
dependencies = [
    "duckdb>=1.0",
    "pandas>=2.2",
    "pyarrow>=16",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["market_brief"]
```

`skills/market_brief/market_brief/__init__.py` and `skills/market_brief/market_brief/tools/__init__.py`: empty files.

`skills/market_brief/SKILL.md`:

```markdown
---
name: market_brief
version: 0.1.0
owner: egor
description: Write a short factual brief on one stock/ETF ticker over a date window — its price move and fundamentals. Use when asked for a brief, summary, or overview of a ticker.
blast_radius: low
allowed_mcp_servers: [data_mcp]
required_scopes: [prices:read, fundamentals:read]
eval:
  golden_set: evals/golden.yaml
  threshold: 0.7
---

# Market Brief

Write a short, factual brief on ONE ticker over a date window.

## How to answer
1. Call `get_market_data(ticker, start, end)` exactly once.
2. From its output, write 2–4 sentences: name the ticker and the date window; describe the
   price move over the period (direction and rough magnitude, using first vs last close); and
   mention the fundamentals note.
3. Be factual. Do not invent any figure that is not in the tool output. If the tool returns an
   error (e.g. no data), say so plainly and name the ticker — do not fabricate a brief.

## Available tools
- `get_market_data(ticker, start, end)` — returns first/last close, number of trading days,
  and fundamentals for the ticker over the window.
```

`registry/market_brief.yaml`:

```yaml
# Governance approval record for market_brief (see registry/factor_correlation.yaml).
name: market_brief
version: 0.1.0
owner: egor
blast_radius: low
allowed_mcp_servers: [data_mcp]
required_scopes: [prices:read, fundamentals:read]
status: blessed
```

- [ ] **Step 2: Write the failing tests** — `skills/market_brief/tests/test_fetch.py`:

```python
"""market_brief data access routes by execution context, exactly like factor_correlation.
Laptop reads the parquet for prices (fundamentals only exist on the platform); platform routes
both through the Data MCP. The platform test stands up a real server — keyless, no agent."""

from __future__ import annotations

import json
import socket
import threading
import time
from datetime import date
from pathlib import Path

import pytest
import uvicorn

from lab_common.capability import mint
from lab_common.exec_context import use_platform_context
from market_brief.agent_tools import _get_market_data_impl
from market_brief.tools.fetch import get_fundamentals, get_prices

SECRET = "m5-market-brief-test-secret-32byte!"


def test_laptop_prices_from_parquet(fixtures_parquet: Path, monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    monkeypatch.setenv("PRICES_PARQUET", str(fixtures_parquet))
    rows = get_prices("AAPL", date(2025, 1, 1), date(2025, 3, 31))
    assert rows and all(r["ticker"] == "AAPL" for r in rows)


def test_laptop_fundamentals_note(monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    assert "unavailable" in get_fundamentals("AAPL")["note"].lower()


def test_impl_builds_brief_inputs(fixtures_parquet: Path, monkeypatch):
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("DATA_MCP_TOKEN", raising=False)
    monkeypatch.setenv("PRICES_PARQUET", str(fixtures_parquet))
    out = json.loads(_get_market_data_impl(
        {"ticker": "AAPL", "start": "2025-01-01", "end": "2025-03-31"}))
    assert out["ticker"] == "AAPL"
    assert "first_close" in out and "last_close" in out and out["n_days"] > 0


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def live_data_mcp(fixtures_parquet: Path, monkeypatch):
    from data_mcp.server import build_app
    monkeypatch.setenv("CAPABILITY_SECRET", SECRET)
    port = _free_port()
    config = uvicorn.Config(build_app(parquet=fixtures_parquet), host="127.0.0.1",
                            port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    thread.join(timeout=5)


def test_platform_routes_prices_and_fundamentals(live_data_mcp: str):
    tok = mint(sub="egor", skill="market_brief", scopes=["prices:read", "fundamentals:read"],
               audience="data_mcp", secret=SECRET)
    with use_platform_context(live_data_mcp, tok):
        rows = get_prices("AAPL", date(2025, 1, 1), date(2025, 3, 31))
        fundamentals = get_fundamentals("AAPL")
    assert rows and rows[0]["ticker"] == "AAPL"
    assert fundamentals["ticker"] == "AAPL"  # came from the Data MCP get_fundamentals stub
```

`skills/market_brief/tests/test_governance.py`:

```python
"""market_brief passes the governance gates and reconciles to blessed."""

from __future__ import annotations

from pathlib import Path

from lab_common.governance.reconcile import reconcile_skill

REPO = Path(__file__).resolve().parents[3]


def test_market_brief_reconciles_to_blessed():
    rec = reconcile_skill(REPO / "skills" / "market_brief",
                          REPO / "registry" / "market_brief.yaml", "local")
    assert rec["status"] == "blessed", rec["agreement_errors"]
    assert sorted(rec["required_scopes"]) == ["fundamentals:read", "prices:read"]
```

- [ ] **Step 3: Run to confirm failure**

Run: `uv run pytest skills/market_brief -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'market_brief'`.

- [ ] **Step 4: Implement `tools/fetch.py`**

```python
"""market_brief data access. Platform context (set by the skill host) -> the governed Data MCP
(capability-scoped get_prices + get_fundamentals); laptop context -> direct parquet for prices
(fundamentals only exist on the platform). The get_client('data_mcp') calls are what the
blast-radius scanner detects and checks against allowed_mcp_servers."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from lab_common.exec_context import platform_context

DEFAULT_WAREHOUSE = Path("data/warehouse/prices.parquet")


def _warehouse() -> Path:
    return Path(os.environ.get("PRICES_PARQUET", str(DEFAULT_WAREHOUSE)))


def get_prices(ticker: str, start: date, end: date) -> list[dict[str, Any]]:
    ctx = platform_context()
    if ctx is not None:
        base_url, token = ctx
        from lab_common.mcp import get_client
        client = get_client("data_mcp", token=token, base_url=base_url)
        return client.call_tool("get_prices", {"tickers": [ticker.upper()],
                                "start": start.isoformat(), "end": end.isoformat()})
    parquet = _warehouse()
    if not parquet.exists():
        raise FileNotFoundError(f"warehouse parquet not found at {parquet}")
    q = ("SELECT ticker, CAST(date AS VARCHAR) AS date, close FROM read_parquet(?) "
         "WHERE ticker = ? AND date BETWEEN ? AND ? ORDER BY date")
    rows = duckdb.execute(q, [str(parquet), ticker.upper(), start.isoformat(),
                              end.isoformat()]).df()
    return rows.to_dict(orient="records")


def get_fundamentals(ticker: str) -> dict[str, Any]:
    ctx = platform_context()
    if ctx is not None:
        base_url, token = ctx
        from lab_common.mcp import get_client
        client = get_client("data_mcp", token=token, base_url=base_url)
        return client.call_tool("get_fundamentals", {"ticker": ticker.upper()})
    return {"ticker": ticker.upper(), "note": "fundamentals unavailable in laptop context"}
```

- [ ] **Step 5: Implement `agent_tools.py`**

```python
"""market_brief Agent-SDK tool surface: one tool returning the brief inputs (prices +
fundamentals) for a ticker; the agent narrates the brief from it. The sync `_*_impl` holds the
logic and is unit-tested; the `@tool` wrapper is a thin shell. The impl catches broadly on
purpose — a tool boundary turns ANY failure into {"error": ...} JSON, never an exception."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from market_brief.tools.fetch import get_fundamentals, get_prices


def _get_market_data_impl(args: dict[str, Any]) -> str:
    try:
        ticker = str(args["ticker"]).upper()
        prices = get_prices(ticker, date.fromisoformat(args["start"]),
                            date.fromisoformat(args["end"]))
        if not prices:
            return json.dumps({"error": f"no price data for {ticker}"})
        first, last = prices[0], prices[-1]
        return json.dumps({
            "ticker": ticker,
            "start": args["start"], "end": args["end"],
            "first_close": first["close"], "last_close": last["close"],
            "n_days": len(prices),
            "fundamentals": get_fundamentals(ticker),
        })
    except Exception as exc:  # noqa: BLE001 — tool boundary: never crash the loop
        return json.dumps({"error": str(exc)})


@tool("get_market_data",
      "Fetch the inputs for a brief on ONE ticker over a date range: first/last close, number "
      "of trading days, and fundamentals. Call once, then write the brief.",
      {"ticker": str, "start": str, "end": str})
async def _get_market_data_tool(args: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": _get_market_data_impl(args)}]}


SERVER_NAME = "brief"
SERVER = create_sdk_mcp_server(name="brief", version="1.0.0", tools=[_get_market_data_tool])
ALLOWED_TOOLS = ["mcp__brief__get_market_data"]
```

- [ ] **Step 6: Sync and run the market_brief keyless tests**

Run: `uv sync --all-packages >/dev/null && uv run pytest skills/market_brief/tests/test_fetch.py skills/market_brief/tests/test_governance.py -v`
Expected: PASS (5 tests).

- [ ] **Step 7: Confirm the governance gates accept it (blast radius is satisfied by the get_client calls)**

Run: `uv run python -m lab_common.governance.cli check skills/market_brief && uv run python -m lab_common.governance.cli check-all`
Expected: market_brief passes all gates (frontmatter, blast radius — it declares `data_mcp` and only calls `get_client("data_mcp")`, scopes). `check-all` exits 0.

- [ ] **Step 8: Commit**

```bash
git add skills/market_brief/ registry/market_brief.yaml
git commit -m "feat(market_brief): second blessed skill (prices+fundamentals via Data MCP)"
```

---

## Task 7: `market_brief` golden + eval

The judge-evaluated golden set — the eval half of the promotion path.

**Files:**
- Create: `skills/market_brief/evals/golden.yaml`
- Create: `skills/market_brief/tests/test_eval_live.py` (`eval`-marked)

- [ ] **Step 1: Write the golden set** — `skills/market_brief/evals/golden.yaml`:

```yaml
cases:
  - id: brief_aapl
    input: "Give me a short brief on AAPL from 2025-01-01 to 2025-03-31."
    checks:
      - type: tool_correctness
        expected_tools: [get_market_data]
        exact_match: true
      - type: geval
        name: brief_quality
        criteria: >
          The answer is a short brief on AAPL that names the ticker and the date window and
          describes the price move over the period (direction and rough magnitude). Judge
          presentation and completeness only; do NOT verify any numeric value or treat
          unverifiable figures as fabricated.
        threshold: 0.7
      - type: answer_relevancy
        threshold: 0.7

  - id: brief_msft
    input: "Brief me on MSFT's price action between 2025-01-01 and 2025-03-31."
    checks:
      - type: tool_correctness
        expected_tools: [get_market_data]
        exact_match: true
      - type: geval
        name: brief_quality
        criteria: >
          The answer is a short brief on MSFT that names the ticker and the date window and
          describes the period's price move. Judge presentation and completeness only; do NOT
          verify numbers.
        threshold: 0.7
      - type: task_completion
        threshold: 0.7
```

- [ ] **Step 2: Write the eval-marked live test** — `skills/market_brief/tests/test_eval_live.py`:

```python
"""Live smoke: real Agent-SDK run of market_brief + DeepEval scoring against the fixtures
parquet (laptop context — no Data MCP server needed for the eval). Marked `eval` (deselected
by default). Run: uv run pytest -m eval. Needs the claude CLI + ANTHROPIC_API_KEY."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.eval

REPO_ROOT = Path(__file__).resolve().parents[3]
BRIEF_SKILL = REPO_ROOT / "skills" / "market_brief"


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
def test_market_brief_eval(fixtures_parquet: Path):
    from lab_common.agent_runner import make_sdk_runner
    from lab_common.deepeval_metrics import make_judge
    from lab_common.eval_harness import run_evals
    from lab_common.skill_spec import load_skill

    os.environ["PRICES_PARQUET"] = str(fixtures_parquet)
    os.environ.pop("DATA_MCP_URL", None)   # force laptop context for the eval
    os.environ.pop("DATA_MCP_TOKEN", None)
    spec = load_skill(BRIEF_SKILL)
    mod = importlib.import_module("market_brief.agent_tools")
    runner = make_sdk_runner(spec, mod.SERVER, mod.ALLOWED_TOOLS, "claude-haiku-4-5",
                             server_name=mod.SERVER_NAME)
    judge, _ = make_judge()
    report = run_evals(BRIEF_SKILL, runner=runner, judge=judge, parquet=fixtures_parquet)
    assert len(report.cases) == 2
    assert report.passed, [(c.case_id, round(c.score, 3)) for c in report.cases]
```

- [ ] **Step 3: Verify the golden parses (collection works) without running the live agent**

Run: `uv run pytest skills/market_brief/tests/test_eval_live.py --collect-only -q`
Expected: 1 test collected (deselected under the default `-m "not eval"`), no collection error.

- [ ] **Step 4 (optional, needs the key locally): run the live eval once to calibrate**

Run: `uv run pytest skills/market_brief/tests/test_eval_live.py -m eval -v`
Expected: PASS (mean score ≥ 0.7). If a `geval` case flakes, fix the *rubric* (presentation-only), not the model — see LEARNINGS 2026-06-09. If `ANTHROPIC_API_KEY` is unset, the test skips (green) — that's fine for the keyless gate.

- [ ] **Step 5: Commit**

```bash
git add skills/market_brief/evals/golden.yaml skills/market_brief/tests/test_eval_live.py
git commit -m "feat(market_brief): judge-evaluated golden + eval-marked live smoke"
```

---

## Task 8: End-to-end live test, docs, CI, PR

The full M5 demo and the merge.

**Files:**
- Create: `services/skill_host/tests/test_host_live.py` (`eval`-marked)
- Modify: `README.md`, `LEARNINGS.md`, `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md`

- [ ] **Step 1: Write the end-to-end live test** — `services/skill_host/tests/test_host_live.py`:

```python
"""End-to-end M5: the host runs a blessed skill through the REAL Agent SDK, and the skill's
tools fetch through the capability-gated Data MCP (platform context). Marked `eval` — needs the
claude CLI + ANTHROPIC_API_KEY and stands up a live Data MCP server. Run: uv run pytest -m eval."""

from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from skill_host.host import HostConfig, run_skill_request

pytestmark = pytest.mark.eval

REPO = Path(__file__).resolve().parents[3]
SECRET = "m5-host-live-test-secret-32-bytes!!"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def live_data_mcp(fixtures_parquet: Path, monkeypatch):
    from data_mcp.server import build_app
    monkeypatch.setenv("CAPABILITY_SECRET", SECRET)
    monkeypatch.setenv("PRICES_PARQUET", str(fixtures_parquet))
    port = _free_port()
    config = uvicorn.Config(build_app(parquet=fixtures_parquet), host="127.0.0.1",
                            port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    thread.join(timeout=5)


def _cfg(base_url: str) -> HostConfig:
    return HostConfig(skills_dir=REPO / "skills", registry_dir=REPO / "registry",
                      entitlements_path=REPO / "registry" / "entitlements.yaml",
                      data_mcp_base_url=base_url, secret=SECRET)


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
def test_host_runs_factor_correlation_through_data_mcp(live_data_mcp: str):
    resp = asyncio.run(run_skill_request(
        "factor_correlation",
        "How correlated were AAPL and MSFT daily returns from 2025-01-01 to 2025-03-31?",
        "egor", config=_cfg(live_data_mcp)))
    assert resp.status == "blessed" and resp.scopes == ["prices:read"]
    assert resp.final_text and "compute_correlation" in [c["name"] for c in resp.trajectory]


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
def test_host_runs_market_brief_through_data_mcp(live_data_mcp: str):
    resp = asyncio.run(run_skill_request(
        "market_brief", "Give me a short brief on AAPL from 2025-01-01 to 2025-03-31.",
        "egor", config=_cfg(live_data_mcp)))
    assert resp.status == "blessed"
    assert sorted(resp.scopes) == ["fundamentals:read", "prices:read"]
    assert resp.final_text and "get_market_data" in [c["name"] for c in resp.trajectory]
```

- [ ] **Step 2: Confirm collection (no live run needed in the gate)**

Run: `uv run pytest services/skill_host/tests/test_host_live.py --collect-only -q`
Expected: 2 tests collected (deselected by default), no error.

- [ ] **Step 3: Run the full keyless gate**

Run: `uv run ruff check . && uv run mypy . && uv run pytest -q`
Expected: ruff clean, mypy clean, all keyless tests PASS (factor_correlation + exec_context + skill_host loader/scoping/host/app + market_brief fetch/governance + the prior 97). The `eval`-marked tests are deselected.

- [ ] **Step 4: Update the design spec** — add an "M5 status (built)" note to the skill-host / promotion-path section of `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md` (mirror the M4 note's style):

```markdown
> **M5 status (built):** `services/skill_host` is a FastAPI service (`POST /run {skill, message, user}`). It loads a skill only if `reconcile` reports it `blessed`, mints a least-privilege capability token (the user must hold every scope the skill declares; token carries exactly those), injects the platform context (`DATA_MCP_URL`/`DATA_MCP_TOKEN` via `lab_common.exec_context`, serialized by a host lock), and runs the async Agent-SDK loop. Skills are context-portable: `platform_context()` routes data access through the governed Data MCP (platform) or direct parquet (laptop). `market_brief` (prices:read + fundamentals:read) is the second blessed skill — the two-scope set and the `get_client("data_mcp")` declaration are now load-bearing for more than one skill. Host *logic* tests are keyless; the full HTTP→host→agent→Data-MCP round-trip is one eval-marked live test.
```

- [ ] **Step 5: Update the README** — add a "Skill host (the platform runtime)" section after the Data MCP section:

```markdown
## Skill host (the platform runtime)

`services/skill_host` runs a *blessed* skill server-side. `POST /run {skill, message, user}`:
loads the skill only if `reconcile` reports it `blessed`, mints a least-privilege capability
token (the user must hold every scope the skill declares), injects the Data MCP URL + token so
the skill's tools fetch through the governed server (platform context), runs the Agent-SDK
loop, and returns the final text + trajectory. Unknown skill → 404; not blessed or missing
entitlement → 403.

Run it:  `uv run python -m skill_host.app`  (127.0.0.1:8082; point it at the Data MCP via
`DATA_MCP_BASE_URL`, share `CAPABILITY_SECRET` with the server).

The same skill runs in two contexts: a laptop reads the parquet directly; the host routes the
same skill through the Data MCP. `market_brief` is a second blessed skill (prices + fundamentals)
authored through the full promotion path — local code → PR → governance gates + evals → blessed
→ runnable in the host.
```

- [ ] **Step 6: Append a LEARNINGS entry** — add an M5 section to `LEARNINGS.md`:

```markdown
## M5 — skill host + promotion demo (2026-06-14)

- **The host is a governance wrapper around the runtime, not new runtime.** It reuses `run_skill`
  unchanged; its value is the gates: blessed-only load (`reconcile`), least-privilege token mint
  (user must hold every declared scope), and platform-context injection. Made the orchestration
  testable offline by injecting the runner — the agent loop is faked in the keyless gate and run
  for real only in the eval gate.
- **Platform context via env vars, not contextvars.** The Agent SDK runs in-process tools in the
  host process, so env set before the run is visible to them — the proven `$PRICES_PARQUET`
  mechanism. contextvar propagation across the SDK's tool execution was the riskier bet; env is
  process-global and certain. Cost: it's global, so the host serializes runs with a lock. A
  production runtime would isolate per call (worker/container per invocation).
- **A second skill made the abstractions load-bearing.** With only `factor_correlation`, the
  scope set and `allowed_mcp_servers` were a sample size of one. `market_brief` (prices:read +
  fundamentals:read) forced the token mint to actually intersect scopes and proved the blast-radius
  declaration generalizes. `get_prices_auto` / `platform_context()` is the seam that makes one
  skill definition run in two execution contexts — the whole point of the design.
- **Generalized the hardcoded `mcp__factor__` key** to a per-skill `SERVER_NAME` so the second
  skill's tools read as `mcp__brief__…`; `build_runresult` already stripped any prefix.
```

- [ ] **Step 7: Commit, push, open the PR**

```bash
git add services/skill_host/tests/test_host_live.py README.md LEARNINGS.md \
        docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md
git commit -m "test(skill_host): e2e live demo (host->agent->Data MCP); M5 docs"
git push -u origin m5-skill-host
gh pr create --title "M5: skill host + promotion demo (market_brief)" \
  --body "Skill host runs blessed skills server-side with a scoped capability token; skills are context-portable (laptop|platform via Data MCP); market_brief is a second blessed skill (prices+fundamentals) through the full promotion path. Host logic keyless; full HTTP->host->agent->Data-MCP is one eval-marked live test."
```

- [ ] **Step 8: Watch CI and merge after green**

```bash
gh run watch "$(gh run list --branch m5-skill-host --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status
```
Expected: `checks` green (keyless gate incl. all new host/skill/exec_context tests) and `eval` green (PR-only; runs both skill evals + the live host test). Then:

```bash
gh pr merge --merge --delete-branch
git checkout main && git pull
```

---

## Self-Review

**1. Spec coverage:**
- Skill host service `POST /run` that loads a blessed skill, mints a scoped token, injects MCP access, runs via the Agent SDK, returns final_text + trajectory, 403 on not-blessed/unentitled → **Tasks 4, 5**.
- Platform-context tool wiring; both contexts kept working (laptop direct + platform via MCP) → **Tasks 2, 3** (factor_correlation), **Task 6** (market_brief).
- `market_brief` authored through the full promotion path (code → governance gates → blessed → judge golden) → **Tasks 6, 7**.
- End-to-end promotion demo (host runs market_brief AND factor_correlation through the Data MCP) → **Task 8**.
- Out of scope (M6/M7 KB) → not present. ✓

**2. Placeholder scan:** No TBD/TODO/"handle errors"/"similar to" — every code and test step has complete content. ✓

**3. Type consistency:** `LoadedSkill(spec, server, allowed_tools, server_name, status)`, `HostConfig(skills_dir, registry_dir, entitlements_path, data_mcp_base_url, secret)`, `RunResponse(skill, status, user, scopes, final_text, trajectory)`, `run_skill_request(skill, message, user, *, config, runner)`, `mint_scoped_token(spec, user, *, entitlements_path, secret, ttl_seconds) -> (token, scopes)`, `load_blessed_skill(skill_name, *, skills_dir, registry_dir, source_commit)`, `get_prices_auto(tickers, start, end, parquet)`, `platform_context() -> (url, token)|None`, `use_platform_context(base_url, token)`, `SERVER_NAME`/`SERVER`/`ALLOWED_TOOLS`, `_get_market_data_impl(args) -> str`. Names are consistent across tasks. The Data MCP `get_prices` tool args are `{tickers, start, end}` (list) and `get_fundamentals` is `{ticker}` — matched in `fetch.py`. ✓

**Risk notes for the executor:**
- The two `eval`-marked tests (market_brief eval, host live e2e) need the `claude` CLI + `ANTHROPIC_API_KEY`; they skip cleanly when the key is absent, so the keyless gate stays green. The eval CI job (PR-only) runs them.
- `mypy` must pass for FastAPI/pydantic — both ship types. If `mod.SERVER`/`mod.ALLOWED_TOOLS`/`mod.SERVER_NAME` trip `mypy` (dynamic import), a targeted `# type: ignore[attr-defined]` on those attribute accesses in `loader.py` is acceptable.
- `asyncio.Lock()` at module scope is bound to the running loop on first `await`; the tests call `run_skill_request` via `asyncio.run` (fresh loop each call), which is fine in 3.12 (no loop captured at construction). If a "bound to a different event loop" error ever appears, construct the lock lazily inside `run_skill_request`.
```

