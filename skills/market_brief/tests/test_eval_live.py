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
