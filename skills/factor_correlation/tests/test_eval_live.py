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
