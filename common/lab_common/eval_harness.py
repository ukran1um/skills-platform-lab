"""Drive a skill's golden set with DeepEval. The agent run is injected as `runner` so the
orchestration is unit-testable offline; the live runner spawns the Agent SDK.

CLI: python -m lab_common.eval_harness <skill_dir> [--haiku] [--report out.json]"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Callable

import yaml

from lab_common.deepeval_metrics import build_metric, make_judge, to_test_case
from lab_common.models import CaseResult, CheckResult, EvalReport, RunResult
from lab_common.skill_spec import load_skill


def load_golden(path: str | Path) -> list[dict[str, Any]]:
    return list((yaml.safe_load(Path(path).read_text()) or {}).get("cases", []))


def _expected_tools(case: dict[str, Any]) -> list[str] | None:
    for chk in case["checks"]:
        if chk["type"] == "tool_correctness":
            return list(chk.get("expected_tools", []))
    return None


def _score_case(case: dict[str, Any], run: RunResult, *, judge: Any, parquet: Path) -> CaseResult:
    tc = to_test_case(case["input"], run, _expected_tools(case))
    results: list[CheckResult] = []
    for check in case["checks"]:
        metric, label = build_metric(check, judge=judge, parquet=parquet)
        metric.measure(tc)
        results.append(CheckResult(type=label, passed=bool(metric.is_successful()),
                                   score=float(metric.score), detail=str(metric.reason or "")))
    score = statistics.mean(r.score for r in results) if results else 0.0
    return CaseResult(case_id=case["id"], checks=results, score=score)


def run_evals(
    skill_dir: str | Path,
    *,
    runner: Callable[[str], RunResult],
    judge: Any,
    parquet: Path,
    golden_path: str | Path | None = None,
) -> EvalReport:
    spec = load_skill(skill_dir)
    cases = load_golden(golden_path or (Path(skill_dir) / spec.golden_set))
    if any(c["type"] == "geval" for case in cases for c in case["checks"]) and judge is None:
        raise ValueError("golden set has geval checks but no judge model")
    case_results: list[CaseResult] = []
    for case in cases:
        try:
            run = runner(case["input"])
            case_results.append(_score_case(case, run, judge=judge, parquet=parquet))
        except Exception as exc:  # noqa: BLE001 — one bad case must not abort the run
            case_results.append(CaseResult(case_id=case["id"],
                                checks=[CheckResult("error", False, 0.0, str(exc))], score=0.0))
    mean = statistics.mean(c.score for c in case_results) if case_results else 0.0
    return EvalReport(skill=spec.name, cases=case_results, mean_score=mean,
                      threshold=spec.threshold, passed=mean >= spec.threshold)


def _report_to_dict(r: EvalReport) -> dict[str, Any]:
    return {"skill": r.skill, "mean_score": r.mean_score, "threshold": r.threshold, "passed": r.passed,
            "cases": [{"case_id": c.case_id, "score": c.score,
                       "checks": [{"type": k.type, "passed": k.passed, "score": k.score, "detail": k.detail}
                                  for k in c.checks]} for c in r.cases]}


def _print_report(r: EvalReport, judge_label: str) -> None:
    print(f"\n=== eval: {r.skill}  (judge: {judge_label}) ===")
    for c in r.cases:
        print(f"  {c.case_id}: score={c.score:.3f}")
        for k in c.checks:
            print(f"    [{'PASS' if k.passed else 'FAIL'}] {k.type} ({k.score:.3f}) {k.detail[:110]}")
    print(f"  MEAN {r.mean_score:.3f} vs {r.threshold} -> {'PASS' if r.passed else 'FAIL'}\n")


def main() -> None:
    from dotenv import load_dotenv

    from lab_common.agent_runner import make_sdk_runner
    from lab_data.fixtures import write_parquet

    load_dotenv()
    parser = argparse.ArgumentParser(description="Run a skill's golden-set evals (Agent SDK + DeepEval).")
    parser.add_argument("skill_dir")
    parser.add_argument("--haiku", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--parquet", type=Path)
    args = parser.parse_args()

    model = "claude-haiku-4-5" if args.haiku else "claude-sonnet-4-6"
    parquet = args.parquet or write_parquet(Path(".eval_fixtures/prices.parquet"))
    os.environ["PRICES_PARQUET"] = str(parquet)   # in-process tools read this

    spec = load_skill(args.skill_dir)
    mod = importlib.import_module(f"{spec.name}.agent_tools")
    runner = make_sdk_runner(spec, mod.SERVER, mod.ALLOWED_TOOLS, model)
    judge, judge_label = make_judge()

    report = run_evals(args.skill_dir, runner=runner, judge=judge, parquet=parquet)
    _print_report(report, judge_label)
    if args.report:
        args.report.write_text(json.dumps(_report_to_dict(report), indent=2))
        print(f"wrote {args.report}")
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
