import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from lab_common.eval_harness import run_evals
from lab_common.models import RunResult, ToolCall

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTOR_SKILL = REPO_ROOT / "skills" / "factor_correlation"


def _good_runner(fixtures_parquet: Path):
    from factor_correlation.cli import run as skill_run
    truth = skill_run(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)

    def runner(_input: str) -> RunResult:
        return RunResult(final_text="done", trajectory=[ToolCall(
            "compute_correlation",
            {"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
            json.dumps(truth))])
    return runner


def test_offline_deterministic_and_tool_correctness(tmp_path: Path, fixtures_parquet: Path):
    golden = {"cases": [{"id": "c1", "input": "x", "checks": [
        {"type": "deterministic", "tolerance": 0.01},
        {"type": "tool_correctness", "expected_tools": ["compute_correlation"], "exact_match": True},
    ]}]}
    gp = tmp_path / "g.yaml"
    gp.write_text(yaml.safe_dump(golden))
    report = run_evals(FACTOR_SKILL, runner=_good_runner(fixtures_parquet), judge=None,
                       parquet=fixtures_parquet, golden_path=gp)
    assert {c.type for c in report.cases[0].checks} == {"deterministic", "tool_correctness"}
    assert report.cases[0].checks[0].passed and report.passed


def test_errored_case_scores_zero(tmp_path: Path, fixtures_parquet: Path):
    def boom(_): raise RuntimeError("boom")
    golden = {"cases": [{"id": "b", "input": "x",
                         "checks": [{"type": "tool_correctness", "expected_tools": ["compute_correlation"]}]}]}
    gp = tmp_path / "g.yaml"
    gp.write_text(yaml.safe_dump(golden))
    report = run_evals(FACTOR_SKILL, runner=boom, judge=None, parquet=fixtures_parquet, golden_path=gp)
    assert report.cases[0].checks[0].type == "error" and not report.passed


@pytest.mark.parametrize("check", [
    {"type": "geval", "criteria": "good?"},
    {"type": "answer_relevancy"},
    {"type": "task_completion"},
])
def test_judge_backed_check_without_judge_raises(check, tmp_path: Path, fixtures_parquet: Path):
    golden = {"cases": [{"id": "g", "input": "x", "checks": [check]}]}
    gp = tmp_path / "g.yaml"
    gp.write_text(yaml.safe_dump(golden))
    with pytest.raises(ValueError, match="no judge"):
        run_evals(FACTOR_SKILL, runner=lambda s: RunResult("x", []), judge=None,
                  parquet=fixtures_parquet, golden_path=gp)
