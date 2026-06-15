# skills-platform-lab — Design

**Date:** 2026-06-06
**Status:** Approved
**Purpose:** A working prototype of a governed skills platform: a skill registry monorepo with eval-gated CI, CI/CD-as-governance, a capability-token-validated MCP server, and a skill-host runtime. Built as a learning project to get hands-on depth on three mechanisms: (1) the repo-skills pattern with evals wired into specific skills, (2) CI/CD as the governance path from ungoverned local skill to blessed platform skill, (3) MCP from the server side.

This is a sanitized, generic-named, public-data-only project. It may become a public portfolio artifact.

## Goals

1. Verify the skills-to-agents promotion path works end to end: local skill → PR → CI gates → blessed registry status → runs server-side with injected, governed tool access.
2. Learn the operational texture of eval gates in CI: judge flakiness, threshold calibration, cost, trajectory-vs-outcome scoring. Record findings in `LEARNINGS.md`.
3. Build and operate a real MCP server: Streamable HTTP, tools/list + tools/call, JWT capability-token validation per call, 401 challenge behavior, OTel spans.
4. Demonstrate governance catching a misbehaving skill (blast-radius AST scan rejecting a skill whose code calls an undeclared MCP server).

## Non-goals (deliberately out of scope)

- AWS AgentCore or any cloud deployment (the skill host simulates the server-side runtime locally)
- Neo4j / semantic layer
- Chat, notebook, or marketplace surfaces
- Router / intent classification (skill host takes an explicit skill name)
- Session manager / event sourcing
- Async job handles
- Asymmetric JWKS key distribution, OAuth dynamic client registration (HS256 shared secret suffices for the lesson)
- Vector store / embeddings for the knowledge base (BM25 over markdown, per the Karpathy small-scale observation)
- Synthetic data generation / fine-tuning over the KB (Karpathy's "further explorations" — noted, not built)

## Decisions log

| Decision | Choice |
|---|---|
| Location | `~/Projects/learning/skills-platform-lab` |
| GitHub remote | Private first; flip public after review |
| Eval billing in CI | Anthropic API key (Console + prepaid credits) as repo secret |
| Models | Sonnet for skill agent and judge; Haiku as cheap CI fallback if cost annoys |
| Stack | Python 3.12, uv workspace, Claude Agent SDK, MCP Python SDK (FastMCP), DuckDB + Parquet, GitHub Actions, PyJWT (HS256), pytest |
| Demo skills | `factor_correlation` (numeric, deterministic evals) and `market_brief` (free text, judge evals), plus `rogue_skill` as a rejected PR; `kb_compile` and `kb_qa` in the KB extension |
| Knowledge base | Separate private repo `agents-kb` (AI-agents research topic), Karpathy raw/ + wiki/ pattern, Obsidian as human frontend, distributed by git clone/pull |
| KB placement | M6–M7, after the governance core lands; replaces prior M6 stretch ideas |

## Architecture

One uv-workspace monorepo:

```
skills-platform-lab/
├── skills/
│   ├── factor_correlation/
│   │   ├── SKILL.md              # frontmatter (contract) + system prompt
│   │   ├── tools/                # fetch.py, compute.py — plain Python functions
│   │   ├── evals/golden.yaml     # golden cases: deterministic + trajectory + judge
│   │   └── pyproject.toml        # independent version
│   └── market_brief/             # authored in M5 via the full promotion path
├── registry/
│   ├── factor_correlation.yaml   # governance approval record (declared state)
│   └── reconcile.py              # git → registry.json "deployed state" artifact
├── common/                       # shared lib: MCP client factory, JWT mint/verify,
│                                 # eval harness (pytest plugin), skill loader
├── services/
│   ├── data_mcp/                 # FastMCP Streamable HTTP over DuckDB; JWT-checked; OTel
│   └── skill_host/               # FastAPI: load blessed skill → inject declared MCP
│                                 # clients → Agent SDK loop
├── data/                         # ingest.py → parquet (~50 tickers, daily closes);
│                                 # DuckDB views; small fixtures set for staging/evals
├── .github/workflows/ci.yaml     # path-filtered per-skill gates
├── .claude/skills/               # symlinks into skills/ for local Claude Code
├── docs/superpowers/specs/       # this document
└── LEARNINGS.md                  # running log of gotchas — the primary learning artifact
```

### Two execution contexts, same skill definition

1. **Laptop context (M1).** `skills/<name>/` symlinked into `.claude/skills/` so local Claude Code discovers and runs the skill directly against local parquet. Ungoverned, local credentials. This is the deliberate "Phase 1" starting state.
2. **Platform context (M5).** The skill host importlib-loads the same package, uses the same `SKILL.md` as the system prompt, but tools reach data only through the Data MCP with a capability token. Same definition, different execution context and governance wrapper.

In platform context the Data MCP is the only path to the warehouse. In laptop context the skill reads parquet directly, on purpose, so the promotion diff is visible.

> **M5 status (built):** `services/skill_host` is a FastAPI service (`POST /run {skill, message, user}`). It loads a skill only if `reconcile` reports it `blessed`, mints a least-privilege capability token (the user must hold every scope the skill declares; token carries exactly those), injects the platform context (`DATA_MCP_URL`/`DATA_MCP_TOKEN` via `lab_common.exec_context`, serialized by a host lock), and runs the async Agent-SDK loop. Skills are context-portable: `platform_context()` routes data access through the governed Data MCP (platform) or direct parquet (laptop). `market_brief` (prices:read + fundamentals:read) is the second blessed skill — the two-scope set and the `get_client("data_mcp")` declaration are now load-bearing for more than one skill. Host *logic* tests are keyless; the full HTTP→host→agent→Data-MCP round-trip is one eval-marked live test.

### The skills

| | `factor_correlation` | `market_brief` | `rogue_skill` (PR only, never merged) |
|---|---|---|---|
| Output shape | Numeric (correlation matrix) | Free text (markdown brief on a ticker) | — |
| Eval type | Deterministic (recompute, tolerance) | LLM-judge (rubric) | Has passing evals (that is the point) |
| `blast_radius` | low | low | declared `low`, code calls undeclared server |
| `allowed_mcp_servers` | `data_mcp` | `data_mcp` | declares `data_mcp`, also imports `notify_mcp` |
| `required_scopes` | `prices:read` | `prices:read`, `fundamentals:read` | — |
| Built in | M1 | M5 (via full promotion path) | M3 (the CI-goes-red demo) |

Two blessed skills plus one rejected PR exercise: path-filtered CI visibly skipping the unchanged skill, two scope sets making token scoping falsifiable, both eval modes in one harness, and a concrete governance rejection.

## Contracts

### SKILL.md frontmatter

Consumed by CI (schema validation, AST scan, eval gate), the reconciler, and the skill host.

```yaml
---
name: factor_correlation
version: 0.1.0
owner: egor
description: Compute return correlations between tickers over a window
blast_radius: low            # negligible | low | medium | high
allowed_mcp_servers: [data_mcp]
required_scopes: [prices:read]
eval:
  golden_set: evals/golden.yaml
  threshold: 0.8             # mean score across cases; calibrated in M2
---
<system prompt for the agent loop follows>
```

### Registry record

`reconcile.py` emits one record per skill-version into `registry.json` (the build artifact / "deployed state"):

```json
{
  "name": "factor_correlation", "version": "0.1.0",
  "owner": "egor", "blast_radius": "low",
  "allowed_mcp_servers": ["data_mcp"], "required_scopes": ["prices:read"],
  "source_commit": "<sha>", "eval_score": 0.91,
  "status": "blessed"
}
```

`status` lifecycle: `candidate | blessed | deprecated`.

**Reconciliation rule:** a skill is `blessed` only if frontmatter (authored intent), `registry/<skill>.yaml` (governance approval — the stand-in for a council sign-off), and CI results (evidence) agree. Disagreement fails the build.

### Capability token

Minted by a `common/` helper at skill activation; validated by the Data MCP on every `tools/call`.

```json
{
  "sub": "user:egor", "skill": "factor_correlation",
  "scopes": ["prices:read"], "iat": "...", "exp": "+15min",
  "aud": ["data_mcp"]
}
```

- Scope = (skill's `required_scopes` ∩ user's entitlements). A static `entitlements.yaml` (user → allowed scopes) plays the role of the authz service.
- The skill host mints; HS256 with a shared secret.
- 15-minute TTL; expiry produces a visible 401, never a silent re-mint.

### Data MCP tool surface

> **M4 status (built):** `services/data_mcp` implements this as a FastMCP Streamable-HTTP server over the warehouse. The capability token is validated at the boundary by a Starlette middleware (missing/invalid → `401 + WWW-Authenticate: Bearer …`, verified live); per-tool scope is enforced in the tool impls as an in-protocol error ("scope denied"). `run_query` uses the shared `lab_common.sql_safety.validate_select_only` guard (regex, not sqlglot). `lab_common.mcp.get_client` is real; `factor_correlation` gained a platform path (`get_prices_via_mcp`) alongside its laptop path. (Non-goal still deferred: asymmetric JWKS — HS256 shared secret here.)

All read-only, all token-checked:

| Tool | Scope | Notes |
|---|---|---|
| `get_prices(tickers, start, end)` | `prices:read` | |
| `get_returns(tickers, window)` | `prices:read` | |
| `get_fundamentals(ticker)` | `fundamentals:read` | May serve stub data; exists so the scope distinction between skills is enforceable |
| `run_query(sql)` | `query:run` | Single-SELECT-only, validated by a regex guard (`lab_common.sql_safety`). Neither blessed skill declares it — demonstrates an undeclared tool being invisible to the agent even though the server offers it |

Wire behavior (modeled on live-probed public servers, June 2026): Streamable HTTP transport, SSE-framed JSON-RPC responses, `401 + WWW-Authenticate: Bearer resource_metadata=...` challenge on missing/invalid token (the Stripe pattern), scope denial as an in-protocol JSON-RPC error. Both failure styles intentionally observable.

## Knowledge-base extension (M6–M7)

The Karpathy LLM-knowledge-base pattern (raw sources → LLM-compiled markdown wiki → Obsidian as viewer → agent Q&A → outputs filed back), integrated as a platform extension. This is also the "knowledge base track" pattern referenced in the source research.

### `agents-kb`: a separate, private companion repo

```
agents-kb/                        # own git repo, cloned to ~/Projects/learning/agents-kb
├── raw/                          # source documents: clipped articles (Obsidian Web Clipper),
│                                 # papers, images — never edited after ingest
├── wiki/                         # LLM-compiled: concept articles, summaries, backlinks,
│                                 # index files. Maintained by skills, rarely by hand
│   └── _index.md                 # the auto-maintained map the agent reads first
└── .obsidian/                    # vault config (gitignored except essentials)
```

Topic: AI-agents research. Seed corpus: existing notes (`agentic-ai-landscape-march-2026.md`) plus clipped public sources (Anthropic engineering posts, MCP spec, runtime docs). The KB stays private — it is personal research, decoupled from the platform repo's later flip to public.

**Distribution is git.** "Download the knowledge" = clone; "sync" = pull. One repo, three consumers:

1. **Obsidian** (human frontend): open the clone as a vault. Backlinks/graph view come free since the wiki is markdown-with-wikilinks.
2. **Local Claude Code**: reads files directly — index files + summaries instead of RAG, per Karpathy's small-scale observation.
3. **The platform**: `research_mcp` (below) over a configured clone path.

### Research MCP

Same FastMCP/JWT skeleton as the Data MCP, over the KB clone:

| Tool | Scope | Notes |
|---|---|---|
| `search_kb(query)` | `kb:read` | BM25 over markdown (rank-bm25), Karpathy's "naive search engine" as an MCP tool. No vector store |
| `read_doc(path)` | `kb:read` | Returns a wiki or raw document |
| `list_index()` | `kb:read` | Returns `_index.md` |
| `file_note(path, content)` | `kb:write` | Writes into `wiki/` only (never `raw/`); commits to a branch, never to main |

`entitlements.yaml` vocabulary gains `kb:read`, `kb:write`.

### Two new skills

| | `kb_compile` | `kb_qa` v0.1.0 → v0.2.0 |
|---|---|---|
| Purpose | Compile `raw/` items into wiki articles with backlinks; update `_index.md` | Answer questions citing wiki articles; v0.2.0 files its answers back into the wiki (Karpathy's "outputs add up" loop) |
| `blast_radius` | medium (writes) | v0.1.0: low (read-only) → v0.2.0: medium (write-back) |
| `allowed_mcp_servers` | `research_mcp` | `research_mcp` |
| `required_scopes` | `kb:read`, `kb:write` | v0.1.0: `kb:read` → v0.2.0: + `kb:write` |
| Eval type | Judge: article faithful to raw source, links resolve, index updated (an open eval-design problem — that's the point) | Judge: answer cites real wiki docs; trajectory: `must_call: [search_kb]`; citation paths verified to exist deterministically |

**The escalation demo (replaces the earlier market_brief v0.2.0 idea):** `kb_qa` v0.1.0 is blessed as a low/read-only skill. v0.2.0 requests `kb:write` and `blast_radius: medium` — the diff triggers the heavier review tier in CI (medium+ requires explicit registry YAML sign-off before reconcile passes). Blast-radius escalation through the governance pipeline, end to end. `market_brief` stays `data_mcp`-only.

### KB safety rails

- `file_note` writes are branch-only; a human merges KB changes (the KB has its own lighter governance: review-on-merge, no eval gate)
- `raw/` is append-only by convention; CI on the KB repo (single check) fails if a PR modifies existing `raw/` files
- Wiki lint (`kb_compile`'s health-check mode): dangling wikilinks, raw items missing from the index — Karpathy's "linting" pass as a skill invocation rather than a hand-run script

## Eval harness and CI gates

### Golden set format (`evals/golden.yaml`)

```yaml
cases:
  - id: corr_basic
    input: "Correlation between AAPL and MSFT daily returns, 2025"
    checks:
      - type: deterministic
        extract: correlation_value      # harness pulls the number from the result
        expect: {recompute: pearson, tolerance: 0.02}
      - type: trajectory
        expect: {must_call: [compute_correlation], must_not_call: [run_query]}
        # tool names are the skill's local tools/ functions; in platform context
        # those functions wrap MCP calls, so the assertion holds in both contexts
  - id: brief_quality                   # market_brief style
    input: "One-paragraph brief on NVDA"
    checks:
      - type: judge
        rubric: "States current price level, names a recent driver, no fabricated numbers"
        min_score: 0.7
```

Three check types:

1. **deterministic** — recompute the answer in plain Python, compare within tolerance. Strongest gate; use wherever possible.
2. **trajectory** — assert on the tool-call sequence reported by the Agent SDK (`must_call` / `must_not_call`). Catches right-answer-wrong-way.
3. **judge** — Sonnet scores against a rubric. Run 3 times per case, take the median. Residual variance is itself a finding for `LEARNINGS.md`.

### Harness mechanics

- `lab_common.eval_harness.run_evals(skill_dir, *, runner, judge, parquet, golden_path=None)` — DeepEval-native harness.
- Runs each golden-set case through the **Claude Agent SDK** (the same runtime the M5 skill-host uses), isolated via `setting_sources=[]` and a string `system_prompt` derived from the SKILL.md body.
- The runner is constructed with `lab_common.agent_runner.make_sdk_runner(spec, server, allowed_tools, model)`, where `server` and `allowed_tools` come from the skill's `agent_tools` module. The skill exposes four tools (`list_tickers`, `compute_correlation`, `get_returns_stats`, `run_sql`), so traces are naturally multi-step.
- Scoring uses **DeepEval**: `GEval` for rubric/judge checks (configurable cross-family judge model: OpenAI/Gemini/Claude), `ToolCorrectnessMetric` for trajectory/tool-correctness checks, and a custom `BaseMetric` as a deterministic recompute oracle (Pearson within tolerance, no LLM).
- Evals never depend on live ingested data; the fixtures parquet is injected via the `parquet` argument and `$PRICES_PARQUET`.
- Output: per-case scores, mean compared to the frontmatter `threshold`, JSON report.
- Wiring the eval gate into CI (M3) requires the `claude` CLI and Node in the runner environment in addition to the `ANTHROPIC_API_KEY` repo secret.

### CI pipeline (GitHub Actions, path-filtered per skill)

1. **Static gates** (free, fast): ruff, mypy, pytest unit tests, frontmatter schema validation (Pydantic), secrets scan.
2. **Blast-radius AST scan:** walk the skill's imports and calls; any MCP client reference not in `allowed_mcp_servers` → fail. This catches `rogue_skill`.
3. **Scope validation:** `required_scopes` ⊆ vocabulary defined in `entitlements.yaml`.
4. **Eval gate:** the harness, `ANTHROPIC_API_KEY` from repo secrets, capped at roughly $1/run via case count and `max_tokens`.
5. **Reconcile check:** frontmatter ↔ registry YAML agreement; on main, emits `registry.json` as a build artifact.

Static gates run before the eval gate so a lint failure never burns API spend. Branch protection on `main`: PRs only, CI green required.

**M3 demo moment:** the `rogue_skill` PR passes the static gates and dies on gate 2 (fail-fast: gates 3–5 never run, so no eval spend). Its evals pass when run locally — which is the point: governance catches a skill that lies about its tool surface even when its outputs are good.

## Error handling

| Component | Behavior |
|---|---|
| Skill host | Unknown skill or `status != blessed` → 403 with registry status in body. Expired token → 401, no silent re-mint. Agent-loop exception → structured error with partial trajectory attached. |
| Data MCP | Missing/bad token → 401 + `WWW-Authenticate` challenge. Insufficient scope → JSON-RPC error naming the missing scope. `run_query` rejects anything that is not a single SELECT (regex guard, `lab_common.sql_safety`). |
| Eval harness | Per-case timeout (120s), one retry on API 5xx. An errored case scores 0 rather than aborting the run. |
| CI | Eval gate always uploads the per-case JSON report as an artifact, pass or fail. |

## Testing strategy

1. **Unit (pytest, no LLM):** `tools/` functions, JWT mint/verify helpers.
2. **Contract:** frontmatter schema, reconciler agreement rules, AST scanner against fixture skills that should pass/fail (`rogue_skill` starts life as a scanner test fixture).
3. **Integration:** staging Data MCP subprocess end-to-end with a real token.
4. **System:** the golden evals themselves.

Implementation follows TDD discipline (superpowers). The AST scanner is the highest-value TDD target.

## Milestones and acceptance criteria

| Milestone | Scope | Acceptance |
|---|---|---|
| **M0** | Repo scaffold + GitHub remote (private) + data ingest + CI skeleton | `uv sync` clean; ingest produces parquet; CI green on push |
| **M1** | `factor_correlation` skill, laptop context | Skill answers correctly in local Claude Code from local parquet |
| **M2** | Eval harness + golden set | Harness runs locally; threshold calibrated over ≥5 runs; first `LEARNINGS.md` entries |
| **M3** | Full CI governance | PR gates live; `rogue_skill` PR rejected by AST gate; `registry.json` artifact on main |
| **M4** | Data MCP server | Live locally; wired into Claude Code via `claude mcp add`; 401 and scope-denial curl-verifiable |
| **M5** | Skill host + promotion demo | `market_brief` authored through full promotion path; both skills runnable via skill host with scoped tokens; end-to-end demo in README |
| **M6** | `agents-kb` repo + Research MCP + Obsidian | KB repo seeded (≥10 raw items; ≥5 bootstrap wiki pages compiled via local Claude Code — the ungoverned phase, formalized by `kb_compile` in M7); Obsidian vault opens it; `research_mcp` live with `search_kb`/`read_doc`/`list_index`/`file_note`; curl-verifiable kb:read vs kb:write scope denial |
| **M7** | KB skills + escalation demo | `kb_compile` blessed (medium, write) and compiling new raw items; `kb_qa` v0.1.0 blessed read-only; v0.2.0 escalation to kb:write demonstrated through the heavier review tier |

Estimated effort: roughly two weekends plus a few evenings for the core (M0–M5); two to three more evenings for the KB extension (M6–M7).

## Risks / known open questions

- **Judge flakiness vs threshold:** the 0.8 threshold is a placeholder until M2 calibration. If median-of-3 still straddles, options are larger rubrics, more cases, or per-case rather than mean thresholds. Whatever happens is a `LEARNINGS.md` entry, which is the point.
- **CI eval cost discipline:** $1/run cap is a design intent; M3 verifies it holds in practice.
- **Agent SDK trajectory introspection:** the trajectory check assumes the SDK exposes the tool-call log cleanly; if not, the harness falls back to instrumenting the injected MCP clients.
