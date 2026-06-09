"""The three check types. Deterministic + trajectory are pure; judge calls the API.

The deterministic scorer is an INDEPENDENT oracle: it recomputes the correlation
straight from the fixtures parquet with its own pandas math (not the skill's code),
so a regression in the skill's compute path is actually caught.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

import pandas as pd

from lab_common.models import CheckResult, RunResult

JUDGE_MODEL = "claude-sonnet-4-6"

_SUBMIT_SCORE_TOOL = {
    "name": "submit_score",
    "description": "Submit your evaluation score (0.0-1.0) and a one-line reasoning.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "number", "description": "0.0 (fails rubric) to 1.0 (fully meets it)"},
            "reasoning": {"type": "string"},
        },
        "required": ["score", "reasoning"],
    },
}


def _find_call(run: RunResult, tool: str):
    for call in run.trajectory:
        if call.name == tool:
            return call
    return None


def _independent_pearson(parquet: Path, tickers: list[str], start: str, end: str) -> float:
    if len(tickers) != 2:
        raise ValueError(
            f"deterministic recompute requires exactly 2 tickers, got {tickers!r}"
        )
    df = pd.read_parquet(parquet)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    mask = (
        df["ticker"].isin([t.upper() for t in tickers])
        & (df["date"] >= pd.to_datetime(start).date())
        & (df["date"] <= pd.to_datetime(end).date())
    )
    wide = df[mask].pivot(index="date", columns="ticker", values="close").sort_index()
    returns = wide.pct_change(fill_method=None).dropna(how="all")
    corr = returns.corr(method="pearson")
    cols = sorted(corr.columns.tolist())
    return float(corr.loc[cols[0], cols[1]])


def score_trajectory(run: RunResult, check: dict[str, Any]) -> CheckResult:
    called = set(run.called_tools())
    must_call = set(check.get("must_call", []))
    must_not = set(check.get("must_not_call", []))
    missing = must_call - called
    forbidden = must_not & called
    passed = not missing and not forbidden
    detail = ""
    if missing:
        detail += f"missing calls: {sorted(missing)}; "
    if forbidden:
        detail += f"forbidden calls present: {sorted(forbidden)}"
    return CheckResult("trajectory", passed, 1.0 if passed else 0.0, detail.strip())


def score_deterministic(
    run: RunResult, check: dict[str, Any], *, context: dict[str, Any]
) -> CheckResult:
    call = _find_call(run, check["tool"])
    if call is None or call.result is None:
        return CheckResult("deterministic", False, 0.0, f"tool {check['tool']} not called")
    data = json.loads(call.result)
    if check["field"] not in data:
        return CheckResult("deterministic", False, 0.0, f"no field {check['field']} ({data})")
    reported = float(data[check["field"]])
    expected = _independent_pearson(
        Path(context["parquet"]), call.input["tickers"], call.input["start"], call.input["end"]
    )
    diff = abs(reported - expected)
    passed = diff <= float(check.get("tolerance", 0.01))
    return CheckResult(
        "deterministic", passed, 1.0 if passed else 0.0,
        f"reported={reported:.6f} expected={expected:.6f} diff={diff:.6f}",
    )


def _judge_once(client: Any, rubric: str, candidate: str) -> float:
    prompt = (
        f"Rubric: {rubric}\n\n"
        f"Candidate response to evaluate:\n\"\"\"\n{candidate}\n\"\"\"\n\n"
        "Score how well the candidate meets the rubric from 0.0 to 1.0 and submit it."
    )
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=300,
        tools=[_SUBMIT_SCORE_TOOL],
        tool_choice={"type": "tool", "name": "submit_score"},
        messages=[{"role": "user", "content": prompt}],
    )
    block = next(b for b in response.content if b.type == "tool_use")
    return float(block.input["score"])


def score_judge(
    candidate: str | None, check: dict[str, Any], *, client: Any, runs: int = 3
) -> CheckResult:
    if not candidate:
        return CheckResult("judge", False, 0.0, "no candidate text to judge")
    scores = [_judge_once(client, check["rubric"], candidate) for _ in range(runs)]
    median = statistics.median(scores)
    min_score = float(check.get("min_score", 0.7))
    passed = median >= min_score
    return CheckResult(
        "judge", passed, median, f"scores={scores} median={median:.3f} min={min_score}"
    )
