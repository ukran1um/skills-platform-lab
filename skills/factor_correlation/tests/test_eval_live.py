"""Live smoke test: runs the real harness against the fixtures parquet.

Marked `eval` so it is deselected by the default `pytest` run. Run explicitly with:
    uv run pytest -m eval
It is skipped if ANTHROPIC_API_KEY is not set.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.eval

REPO_ROOT = Path(__file__).resolve().parents[3]
FACTOR_SKILL = REPO_ROOT / "skills" / "factor_correlation"


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
def test_live_eval_runs_and_scores(fixtures_parquet: Path):
    import anthropic

    from lab_common.eval_harness import run_evals

    client = anthropic.Anthropic()
    report = run_evals(  # type: ignore[call-arg]
        FACTOR_SKILL,
        agent_client=client,
        judge_client=client,
        context={"parquet": fixtures_parquet},
        model="claude-haiku-4-5",
        judge_model="claude-haiku-4-5",  # keep the smoke test cheap
    )
    assert report.skill == "factor_correlation"
    assert len(report.cases) == 3
    two = next(c for c in report.cases if c.case_id == "corr_two_tickers")
    det = next(k for k in two.checks if k.type == "deterministic")
    assert det.passed, f"deterministic failed: {det.detail}"
