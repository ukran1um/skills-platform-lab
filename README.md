# skills-platform-lab

A working prototype of a governed skills platform: skill registry monorepo with
eval-gated CI, CI/CD-as-governance, a capability-token-validated MCP server, and
a skill-host runtime. Learning project; public data only.

Design: `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md`

## Quickstart

    uv sync --all-packages
    uv run python -m lab_data.ingest          # build the price warehouse (network)
    uv run pytest -q
