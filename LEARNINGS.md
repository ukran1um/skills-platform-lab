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
