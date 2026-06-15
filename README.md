# skills-platform-lab

A working prototype of a governed skills platform: skill registry monorepo with
eval-gated CI, CI/CD-as-governance, a capability-token-validated MCP server, and
a skill-host runtime. Learning project; public data only.

Design: `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md`

## Quickstart

    uv sync --all-packages
    uv run python -m lab_data.ingest          # build the price warehouse (network)
    uv run pytest -q

## Data MCP (the governed tool/data boundary)

`services/data_mcp` is a FastMCP Streamable-HTTP server over the price warehouse. Every call
carries a capability token (HS256 JWT: sub, skill, scopes, aud=data_mcp, 15-min exp). A
missing/invalid token gets a `401` + `WWW-Authenticate: Bearer …` challenge at the transport;
a valid token with the wrong scope gets an in-protocol error. Tools map to scopes:
get_prices/get_returns → `prices:read`, get_fundamentals → `fundamentals:read`, run_query →
`query:run`.

Run it:  `CAPABILITY_SECRET=dev uv run python -m data_mcp.server`  (127.0.0.1:8081)

Skills reach it via `get_client("data_mcp", token=…, base_url=…)`. `factor_correlation` keeps
its laptop path (direct parquet) and adds a platform path (`get_prices_via_mcp`) that fetches
through the governed server — the same skill, two execution contexts.

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

## Governance (CI as the gate)

Every push runs four keyless governance gates (`lab_common.governance.cli check-all` +
`reconcile`): frontmatter schema validation, a blast-radius AST scan, scope-vocabulary
validation, and a registry reconcile (git → `registry.json`; a skill is `blessed` only when
its `SKILL.md` frontmatter and `registry/<skill>.yaml` agree). A separate keyed `eval` job
runs the live Agent-SDK + DeepEval gate — it installs the `claude` CLI and needs the
`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` Actions secrets (until they're set, the eval test
skips, so the job stays green).

Run the gates locally:

    uv run python -m lab_common.governance.cli check-all
    uv run python -m lab_common.governance.cli reconcile --out registry.json

### The rogue-skill demo
`common/tests/fixtures/rogue_skill/` has clean frontmatter and valid scopes, but its code
calls `get_client("notify_mcp")` — a server it never declared in `allowed_mcp_servers`. The
governance check passes gates 1 (frontmatter) and 3 (scopes) and fails gate 2 (blast radius):

    uv run python -m lab_common.governance.cli check common/tests/fixtures/rogue_skill

To see CI reject it as a PR: copy the fixture into `skills/rogue_skill/` on a branch and open
a PR — the `checks` job goes red on the blast-radius gate while the skill's evals would pass.
