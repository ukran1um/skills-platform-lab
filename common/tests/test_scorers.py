import json
from pathlib import Path
from types import SimpleNamespace

from lab_common.models import RunResult, ToolCall
from lab_common.scorers import score_deterministic, score_judge, score_trajectory


def test_trajectory_must_call_and_must_not_call():
    run = RunResult(final_text="x", trajectory=[ToolCall("compute_correlation", {}, "{}")])
    ok = score_trajectory(run, {"must_call": ["compute_correlation"], "must_not_call": ["run_query"]})
    assert ok.passed and ok.score == 1.0

    bad = score_trajectory(run, {"must_call": ["get_prices"]})
    assert not bad.passed and bad.score == 0.0


def test_deterministic_recompute_matches(fixtures_parquet: Path):
    from factor_correlation.cli import run as skill_run

    out = skill_run(["AAPL", "MSFT"], _d("2025-01-01"), _d("2025-06-30"), parquet=fixtures_parquet)
    run = RunResult(
        final_text="...",
        trajectory=[
            ToolCall(
                "compute_correlation",
                {"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
                json.dumps(out),
            )
        ],
    )
    res = score_deterministic(
        run,
        {"tool": "compute_correlation", "field": "correlation_value", "tolerance": 0.01},
        context={"parquet": fixtures_parquet},
    )
    assert res.passed and res.score == 1.0


def test_deterministic_catches_wrong_number(fixtures_parquet: Path):
    run = RunResult(
        final_text="...",
        trajectory=[
            ToolCall(
                "compute_correlation",
                {"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
                json.dumps({"correlation_value": 0.999}),
            )
        ],
    )
    res = score_deterministic(
        run,
        {"tool": "compute_correlation", "field": "correlation_value", "tolerance": 0.01},
        context={"parquet": fixtures_parquet},
    )
    assert not res.passed


def test_judge_takes_median_of_runs():
    class FakeJudge:
        def __init__(self, scores):
            self._scores = list(scores)
            self.messages = self

        def create(self, **kwargs):
            score = self._scores.pop(0)
            return SimpleNamespace(
                content=[SimpleNamespace(type="tool_use", name="submit_score",
                                         input={"score": score, "reasoning": "r"})]
            )

    client = FakeJudge([0.9, 0.4, 0.8])  # median 0.8
    res = score_judge("some narration", {"rubric": "is it good", "min_score": 0.7},
                      client=client, runs=3)
    assert res.score == 0.8
    assert res.passed


def test_deterministic_rejects_non_pair_call(fixtures_parquet: Path):
    import pytest

    run = RunResult(
        final_text="...",
        trajectory=[
            ToolCall(
                "compute_correlation",
                {"tickers": ["AAPL", "MSFT", "NVDA"], "start": "2025-01-01", "end": "2025-06-30"},
                json.dumps({"correlation_value": 0.5}),
            )
        ],
    )
    # The independent oracle is 2-ticker-only; a 3-ticker deterministic check is a
    # misconfiguration and must fail loudly rather than silently score a wrong pair.
    with pytest.raises(ValueError, match="exactly 2 tickers"):
        score_deterministic(
            run,
            {"tool": "compute_correlation", "field": "correlation_value", "tolerance": 0.01},
            context={"parquet": fixtures_parquet},
        )


def _d(s: str):
    from datetime import date
    return date.fromisoformat(s)
