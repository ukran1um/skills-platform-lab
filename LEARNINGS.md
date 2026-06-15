# Learnings

Running log of operational gotchas found while building this. Format:

## YYYY-MM-DD — <area>: <one-line finding>
What happened, why it matters, what we changed.

## 2026-06-08 — data ingest: Stooq added a JS proof-of-work wall; switched to yfinance
Stooq's CSV download endpoint now returns a JavaScript SHA-256 proof-of-work challenge
to all non-browser HTTP clients (requests/curl get an HTML wall, 0 rows). Swapped the
ingest to yfinance (Yahoo), which works headless with no API key and returns adjusted
closes. Lesson: a "no-API-key public data source" is a standing liability — the resilient
move is one batched download through a maintained library, plus deterministic synthetic
fixtures (lab_data.fixtures) for tests/CI so the build never depends on a live scrape.

## 2026-06-08 — M1 acceptance: project-level symlinked skills are discovered by Claude Code
Verified in a fresh Claude Code session at the repo root: asking "how correlated were AAPL
and MSFT daily returns in 2025?" caused Claude Code to discover and invoke the
factor_correlation skill (exposed via .claude/skills/factor_correlation -> ../../skills/...)
and run its CLI. The committed relative symlink works as the skill-wiring mechanism — no
need for the fallback of a checked-in SKILL.md copy. This confirms the laptop-context path
the promotion pipeline (M5) graduates skills out of.

## 2026-06-09 — M2 eval calibration: the rubric is the product, not the model temperature
First live eval runs of factor_correlation (3 cases, judge median-of-3). The two-ticker and
missing-ticker cases passed cleanly. The three-ticker case FAILED the judge 0/0/0 with a
Haiku judge — and it was NOT flakiness (flakiness scatters; this was systematic). The agent's
answer was actually excellent (full correlation matrix, labeled daily-returns, window named).

Root cause: the rubric said "No fabricated tickers or numbers." The Haiku judge read that as
"the numbers must be independently verifiable; I can't verify 2025 H1 correlations, therefore
they're fabricated" → 0.0. It conflated "I can't verify this" with "this is made up." Crucially,
the judge only sees the agent's final TEXT, not the tool's structured result — so number
faithfulness is not something the judge can assess at all. A Sonnet judge read the rubric better
(0.6-0.7) but still hovered at/below the 0.7 floor.

Fix: re-scope every judge rubric to PRESENTATION ONLY (all pairs present, labeled daily-returns,
window named) with an explicit "do NOT verify the numeric values, do NOT treat unverifiable
figures as fabricated." Number correctness is the DETERMINISTIC check's job (independent
recompute), not the judge's. After the rubric fix: both Sonnet AND Haiku judges score the same
answer 1.0, stable across runs. Mean 0.833 -> 1.000.

Lessons for talking about eval gates:
1. The dominant source of a failing/"flaky" eval was the RUBRIC wording, not model randomness.
   Writing rubrics is the real skill; ambiguity is where evals rot.
2. Give the judge only what it can actually observe. Correctness -> deterministic oracle;
   presentation/faithfulness -> judge. Don't ask the judge to police numbers it never sees.
3. Judge model matters: a weak judge (Haiku) amplifies rubric ambiguity into confident wrong
   scores. Use a capable judge for trustworthy gating; `--haiku` is for cheap agent iteration.
4. median-of-N smooths RANDOM noise, not a SYSTEMATICALLY wrong judge — it did nothing for the
   0/0/0 case. Repetition is not a substitute for a well-scoped rubric.

## 2026-06-09 — M2 rebuilt on the real runtime: Claude Agent SDK + DeepEval, multi-tool skill
Rebuilt the eval harness to run the skill through the **Claude Agent SDK** (the same runtime
the M5 host will use) and score with **DeepEval** — the bespoke Messages-API loop + hand-rolled
scorers are gone. Why: evaluating a skill in a look-alike harness is apples-to-oranges; running
it in the deployment substrate is apples-to-apples. The runner uses `setting_sources=[]` (loads
no local ~/.claude) and a string `system_prompt` (replaces Claude Code's default), so the eval
can't absorb laptop config — the same isolation a containerized CI would enforce.

Substrate facts learned:
- The Python `claude-agent-sdk` is a wrapper that spawns the `claude` CLI subprocess, so it needs
  Node + the CLI present (not pure-Python). It DOES run headless on just an API key (passed via
  `options.env`). M3 CI must install the CLI + Node in the runner.
- The real runtime shows through: every run emits a harness-internal `ToolSearch` tool call
  (deferred tool loading) before the skill's tools. We filter anything not prefixed `mcp__` and
  strip the `mcp__factor__` prefix when building the trajectory for scoring.
- Three DeepEval check types map cleanly: `GEval` = judge, `ToolCorrectnessMetric` = trajectory,
  a custom `BaseMetric` = the deterministic recompute oracle.

Live-run calibration findings (the headline lessons):
1. **Cross-family judge, live.** With OPENAI_API_KEY in the env, the judge auto-selected
   `openai:gpt-5.4` to grade Claude-haiku output — the whiteboard's "different family for review"
   running for real. Generator and judge are independently configurable; nothing forces a weak
   judge on strong output (the failure direction we hit earlier).
2. **`exact_match` tool-correctness is too brittle for live agents.** The multi-step case had the
   agent call `get_returns_stats` TWICE (it checked both candidates) — a correct answer, but
   `exact_match=True` (expected exactly [compute_correlation, get_returns_stats]) FAILED it.
   Relaxed to subset/recall (assert the two typed tools were composed). Lesson: "assert no extra
   tools" and "tolerate reasonable agent variation" conflict; a gate must tolerate the variation
   or it false-fails correct work. Forbidding a specific tool (run_sql) needs its own assertion,
   not exact_match.
3. **Verification-seeking recurs even with a STRONG judge.** GPT-5.4 docked the run_sql case to
   0.5 because it "could not verify $121.39 is actually the highest close." Same failure mode as
   the earlier Haiku judge on the 3-ticker case — the judge tried to verify a number it can't see.
   Fix was again the RUBRIC ("judge only the format; do not verify the value; do not penalize
   inability to verify"), not the model. Reinforces: rubric scoping is model-independent; even a
   frontier judge defaults to verification-seeking unless explicitly told not to. Keep the judge
   on what it can observe; let deterministic checks own correctness.

After calibration: 4/4 cases, mean 1.000. Cost per run ≈ 4 Agent-SDK loops (CLI subprocess) +
GEval judge calls — cents on Haiku agent + GPT judge.

## 2026-06-09 — the keyless CI gate caught a hidden dependency the local run masked
First CI run of the DeepEval harness FAILED on an offline test that passed locally. Cause:
`ToolCorrectnessMetric()` (a deterministic, no-LLM metric) calls deepeval's
`initialize_model(None)`, which DEFAULTS to `GPTModel()` and raises if `OPENAI_API_KEY` is
unset — at construction, before any scoring. It passed on my laptop only because my shell
has OPENAI_API_KEY (the same key that made the judge auto-pick gpt-5.4). CI's free gate is
keyless, so construction blew up. Fix: pass a no-op `_NoModel(DeepEvalBaseLLM)` so the metric
never defaults to GPT. Reproduced locally by unsetting the keys (`env -u OPENAI_API_KEY ...`).

This is the containerization/parity lesson in miniature: a dependency that "works on my
laptop" because of ambient env state (an exported API key) silently breaks in a clean
environment. The keyless CI gate is the cheap proxy for the hermetic container — it fails
fast on exactly the leak that would otherwise surface only after deploy. Lesson: run the gate
in the cleanest environment you can (no ambient keys, no local config) so local convenience
state can't mask a real dependency.

## 2026-06-14 — M3: CI as governance (four keyless gates + a keyed eval job)
Governance now runs in CI on every push: frontmatter schema, a blast-radius AST scan,
scope-vocabulary validation, and a git→registry.json reconcile (a skill is `blessed` only
when SKILL.md and registry/<skill>.yaml agree). These are model-free and keyless on purpose
— cheap, deterministic, always-on. The live Agent-SDK+DeepEval eval is a SEPARATE keyed job
scoped to pull_request only (bounds API cost; secrets ANTHROPIC/OPENAI in Actions; the job
installs the `claude` CLI via npm so the SDK can spawn it).

Blast-radius convention: a skill reaches a server via `lab_common.mcp.get_client("<server>")`;
the AST scanner extracts the string-literal name and checks it against allowed_mcp_servers.
factor_correlation references none (laptop context) so it's vacuously clean; the rogue_skill
fixture calls get_client("notify_mcp") and is rejected while its frontmatter + scopes pass —
the "passes gates 1 & 3, dies on gate 2" demo. Static analysis is best-effort: a non-literal
get_client(var) is flagged, a syntax-error file fails cleanly (not a crash), and the runtime
token + tool-injection layers (M4/M5) are the real backstop.

Gotchas worth knowing:
- Branch protection requires GitHub Pro on a PRIVATE repo (API 403: "Upgrade to Pro or make
  this repository public"). The free path to enforced protection is to make the repo public.
- ToolCorrectnessMetric (and other deepeval built-ins) instantiate a judge model at
  construction and default to GPTModel() → they demand OPENAI_API_KEY even when deterministic.
  Pass a no-op model for the keyless ones (handled in M2's _NoModel).

## 2026-06-14 — M4: capability-token Data MCP server (the governed tool/data boundary)
Built services/data_mcp: a FastMCP Streamable-HTTP server over the warehouse. Capability
tokens (lab_common.capability, HS256 JWT: sub/skill/scopes/aud/15-min exp) are validated at
the boundary. The two failure modes are deliberately distinct: a missing/invalid token is a
TRANSPORT 401 + `WWW-Authenticate: Bearer resource_metadata=...` (Starlette middleware, the
Stripe/RFC9728 pattern — verified live: `HTTP 401`, detail "missing bearer token"); an
insufficient SCOPE on a valid token is an IN-PROTOCOL tool error ("scope denied: ..."). Tools
map to scopes: get_prices/get_returns→prices:read, get_fundamentals→fundamentals:read,
run_query→query:run. `get_client("data_mcp", token=, base_url=)` is now real (Streamable HTTP
+ bearer token). factor_correlation keeps its laptop path (direct parquet) and adds a platform
path (get_prices_via_mcp) through the server — same skill, two execution contexts.

Governance is now LOAD-BEARING: factor_correlation actually calls get_client("data_mcp"), so
the M3 blast-radius scanner returns {data_mcp}, which IS declared in its allowed_mcp_servers →
passes. If it reached an undeclared server, CI would reject it. The declaration finally bites.

Gotchas:
- `streamablehttp_client` (with the `headers=` kwarg) is the working client API; the
  non-deprecated `streamable_http_client` has a DIFFERENT signature (no headers) — NOT a
  drop-in. The deprecation warning is cosmetic; correctness > silencing it.
- anyio wraps an exception raised inside a task group in nested ExceptionGroups on teardown of
  streamablehttp_client; the sync DataMCPClient unwraps the single leaf so callers see the real
  RuntimeError ("scope denied"), not an ExceptionGroup.
- FastMCP's streamable_http_app has a Host-header check: TestClient (host "testserver") gets
  421, but a real client to 127.0.0.1 is fine — so unit-test the 401 via the middleware
  (TestClient asserts !=401) and prove the round-trip with a live uvicorn integration test.
- All M4 tests are keyless (no LLM) — they run in the free `checks` gate, including the live
  uvicorn integration tests (server in a daemon thread, readiness-polled, ephemeral port).

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
