from pathlib import Path
from types import SimpleNamespace

import yaml

from lab_common.eval_harness import run_evals

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR_SKILL = REPO_ROOT / "skills" / "factor_correlation"

TINY_GOLDEN = {
    "cases": [
        {
            "id": "t1",
            "input": "corr of AAPL and MSFT 2025-01-01..2025-06-30",
            "checks": [
                {"type": "trajectory", "must_call": ["compute_correlation"]},
            ],
        }
    ]
}


class FakeAgentClient:
    """One scripted agent run: call compute_correlation, then finish."""

    def __init__(self):
        self.messages = self
        self._step = 0

    def create(self, **kwargs):
        self._step += 1
        if self._step == 1:
            return SimpleNamespace(
                stop_reason="tool_use",
                content=[SimpleNamespace(
                    type="tool_use", name="compute_correlation",
                    input={"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
                    id="tu1")],
            )
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="AAPL and MSFT daily-return correlation over the window was moderate.")],
        )


def test_run_evals_trajectory_only(tmp_path: Path, fixtures_parquet: Path):
    golden = tmp_path / "golden.yaml"
    golden.write_text(yaml.safe_dump(TINY_GOLDEN))
    report = run_evals(
        FACTOR_SKILL,
        golden_path=golden,
        agent_client=FakeAgentClient(),
        judge_client=None,
        context={"parquet": fixtures_parquet},
    )
    assert report.skill == "factor_correlation"
    assert len(report.cases) == 1
    assert report.cases[0].checks[0].type == "trajectory"
    assert report.cases[0].checks[0].passed
    assert report.mean_score == 1.0
    assert report.passed


class RaisingAgentClient:
    """Always blows up — simulates a case that errors mid-run."""

    def __init__(self):
        self.messages = self

    def create(self, **kwargs):
        raise RuntimeError("boom")


def test_run_evals_errored_case_scores_zero_and_run_continues(tmp_path: Path, fixtures_parquet: Path):
    two_cases = {
        "cases": [
            {"id": "boom", "input": "x", "checks": [{"type": "trajectory", "must_call": ["compute_correlation"]}]},
            {"id": "ok", "input": "y", "checks": [{"type": "trajectory", "must_call": ["compute_correlation"]}]},
        ]
    }
    golden = tmp_path / "golden.yaml"
    golden.write_text(yaml.safe_dump(two_cases))
    report = run_evals(
        FACTOR_SKILL,
        golden_path=golden,
        agent_client=RaisingAgentClient(),  # every case errors
        judge_client=None,
        context={"parquet": fixtures_parquet},
    )
    # Both cases recorded (run did not abort); both scored 0 with an error check.
    assert len(report.cases) == 2
    assert all(c.score == 0.0 for c in report.cases)
    assert report.cases[0].checks[0].type == "error"
    assert not report.passed
