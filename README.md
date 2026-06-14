# skills-platform-lab

A working prototype of a governed skills platform: skill registry monorepo with
eval-gated CI, CI/CD-as-governance, a capability-token-validated MCP server, and
a skill-host runtime. Learning project; public data only.

Design: `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md`

## Quickstart

    uv sync --all-packages
    uv run python -m lab_data.ingest          # build the price warehouse (network)
    uv run pytest -q

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
