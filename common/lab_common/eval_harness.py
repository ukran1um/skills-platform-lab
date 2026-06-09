"""Drive a skill's golden set: run the agent once per case, apply each check, aggregate.

CLI: `python -m lab_common.eval_harness <skill_dir> [--haiku] [--report out.json]`
Default backend is laptop mode against the fixtures parquet.
"""

from __future__ import annotations

import argparse
import importlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import yaml

from lab_common.agent_runner import run_skill
from lab_common.models import CaseResult, CheckResult, EvalReport, SkillSpec
from lab_common.scorers import score_deterministic, score_judge, score_trajectory
from lab_common.skill_spec import load_skill


def load_golden(path: str | Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return list(data.get("cases", []))


def _load_agent_tools(spec: SkillSpec):
    try:
        module = importlib.import_module(f"{spec.name}.agent_tools")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            f"Could not import '{spec.name}.agent_tools'. "
            f"The skill's package name must match its SKILL.md name (got: {spec.name!r})."
        ) from exc
    return module.TOOLS, module.dispatch


def _score_case(
    case: dict[str, Any],
    run: Any,
    *,
    judge_client: Any,
    judge_model: str,
    context: dict[str, Any],
) -> CaseResult:
    results: list[CheckResult] = []
    for check in case["checks"]:
        ctype = check["type"]
        if ctype == "trajectory":
            results.append(score_trajectory(run, check))
        elif ctype == "deterministic":
            results.append(score_deterministic(run, check, context=context))
        elif ctype == "judge":
            results.append(
                score_judge(run.final_text, check, client=judge_client, judge_model=judge_model)
            )
        else:
            results.append(CheckResult(ctype, False, 0.0, f"unknown check type {ctype}"))
    case_score = statistics.mean(r.score for r in results) if results else 0.0
    return CaseResult(case_id=case["id"], checks=results, score=case_score)


def run_evals(
    skill_dir: str | Path,
    *,
    golden_path: str | Path | None = None,
    agent_client: Any,
    judge_client: Any,
    context: dict[str, Any],
    model: str = "claude-sonnet-4-6",
    judge_model: str = "claude-sonnet-4-6",
) -> EvalReport:
    spec = load_skill(skill_dir)
    golden_path = golden_path or (Path(skill_dir) / spec.golden_set)
    cases = load_golden(golden_path)
    tools, dispatch = _load_agent_tools(spec)

    has_judge = any(c["type"] == "judge" for case in cases for c in case["checks"])
    if has_judge and judge_client is None:
        raise ValueError("golden set contains judge checks but judge_client is None")

    case_results: list[CaseResult] = []
    for case in cases:
        # One erroring case must not abort the whole run — record it as a 0-score
        # case (with the error in the detail) and keep going.
        try:
            run = run_skill(
                spec, case["input"], tools, dispatch,
                client=agent_client, context=context, model=model,
            )
            case_results.append(
                _score_case(
                    case, run, judge_client=judge_client, judge_model=judge_model, context=context
                )
            )
        except Exception as exc:  # noqa: BLE001 — resilience is the point here
            case_results.append(
                CaseResult(
                    case_id=case["id"],
                    checks=[CheckResult("error", False, 0.0, str(exc))],
                    score=0.0,
                )
            )

    mean = statistics.mean(c.score for c in case_results) if case_results else 0.0
    return EvalReport(
        skill=spec.name,
        cases=case_results,
        mean_score=mean,
        threshold=spec.threshold,
        passed=mean >= spec.threshold,
    )


def _print_report(report: EvalReport) -> None:
    print(f"\n=== eval: {report.skill} ===")
    for case in report.cases:
        print(f"  {case.case_id}: score={case.score:.3f}")
        for chk in case.checks:
            mark = "PASS" if chk.passed else "FAIL"
            print(f"    [{mark}] {chk.type} ({chk.score:.3f}) {chk.detail}")
    verdict = "PASS" if report.passed else "FAIL"
    print(f"  MEAN {report.mean_score:.3f} vs threshold {report.threshold} -> {verdict}\n")


def _report_to_dict(report: EvalReport) -> dict[str, Any]:
    return {
        "skill": report.skill,
        "mean_score": report.mean_score,
        "threshold": report.threshold,
        "passed": report.passed,
        "cases": [
            {
                "case_id": c.case_id,
                "score": c.score,
                "checks": [
                    {"type": k.type, "passed": k.passed, "score": k.score, "detail": k.detail}
                    for k in c.checks
                ],
            }
            for c in report.cases
        ],
    }


def main() -> None:
    import anthropic
    from dotenv import load_dotenv

    from lab_data.fixtures import write_parquet

    load_dotenv()  # pick up ANTHROPIC_API_KEY from a project-root .env if present

    parser = argparse.ArgumentParser(description="Run a skill's golden-set evals (laptop mode).")
    parser.add_argument("skill_dir")
    parser.add_argument("--haiku", action="store_true", help="Use the cheaper model for the agent + judge")
    parser.add_argument("--report", type=Path, help="Write the JSON report to this path")
    parser.add_argument("--parquet", type=Path, help="Warehouse parquet (default: a fresh fixtures parquet)")
    args = parser.parse_args()

    # --haiku is a true cheap mode: both the agent loops AND the judge use Haiku.
    model = "claude-haiku-4-5" if args.haiku else "claude-sonnet-4-6"
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env
    parquet = args.parquet or write_parquet(Path(".eval_fixtures/prices.parquet"))

    report = run_evals(
        args.skill_dir,
        agent_client=client,
        judge_client=client,
        context={"parquet": parquet},
        model=model,
        judge_model=model,
    )
    _print_report(report)
    if args.report:
        args.report.write_text(json.dumps(_report_to_dict(report), indent=2))
        print(f"wrote {args.report}")
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
