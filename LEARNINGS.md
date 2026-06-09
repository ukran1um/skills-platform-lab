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
