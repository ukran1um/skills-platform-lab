"""DeepEval scoring: configurable cross-family judge, a custom deterministic metric, and
builders turning golden-set checks into DeepEval metrics + a RunResult into an LLMTestCase."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
from deepeval.metrics import BaseMetric, GEval, ToolCorrectnessMetric
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.test_case import ToolCall as DEToolCall

from lab_common.models import RunResult

DEFAULT_ANTHROPIC_JUDGE = "claude-sonnet-4-6"


class _NoModel(DeepEvalBaseLLM):
    """Placeholder LLM for deterministic metrics that don't use one.

    deepeval's built-in metrics call initialize_model(None), which defaults to
    GPTModel() and raises if OPENAI_API_KEY is unset — even for ToolCorrectnessMetric,
    which never calls an LLM. Passing this keeps construction keyless (the offline gate
    has no API keys). It is never invoked; generate() raising is the safety net.
    """

    def load_model(self):
        return None

    def generate(self, *args: Any, **kwargs: Any) -> str:
        raise NotImplementedError("_NoModel is for metrics that do not use an LLM")

    async def a_generate(self, *args: Any, **kwargs: Any) -> str:
        raise NotImplementedError("_NoModel is for metrics that do not use an LLM")

    def get_model_name(self) -> str:
        return "none"


def choose_judge_provider(env: dict[str, str]) -> str:
    """Prefer a judge family DIFFERENT from the Claude generator. OpenAI > Gemini > Claude."""
    if env.get("OPENAI_API_KEY"):
        return "openai"
    if env.get("GOOGLE_API_KEY"):
        return "gemini"
    return "anthropic"


def make_judge(provider: str | None = None, env: dict[str, str] | None = None):
    env = env if env is not None else dict(os.environ)
    provider = provider or choose_judge_provider(env)
    if provider == "openai":
        from deepeval.models import GPTModel
        judge: Any = GPTModel()
        return judge, f"openai:{judge.get_model_name()}"
    if provider == "gemini":
        from deepeval.models import GeminiModel
        judge = GeminiModel()
        return judge, f"gemini:{judge.get_model_name()}"
    from deepeval.models import AnthropicModel
    judge = AnthropicModel(model=DEFAULT_ANTHROPIC_JUDGE, api_key=env["ANTHROPIC_API_KEY"])
    return judge, f"anthropic:{DEFAULT_ANTHROPIC_JUDGE}"


def _recompute_matrix(parquet: Path, tickers: list[str], start: str, end: str) -> dict:
    df = pd.read_parquet(parquet)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    mask = (df["ticker"].isin([t.upper() for t in tickers])
            & (df["date"] >= pd.to_datetime(start).date())
            & (df["date"] <= pd.to_datetime(end).date()))
    corr = df[mask].pivot(index="date", columns="ticker", values="close").sort_index() \
        .pct_change(fill_method=None).dropna(how="all").corr(method="pearson")
    return {a: {b: float(corr.loc[a, b]) for b in corr.columns} for a in corr.columns}


class DeterministicCorrelationMetric(BaseMetric):
    """Independent oracle: recompute every compute_correlation matrix from the parquet and
    require all reported cells within tolerance. No LLM."""

    def __init__(self, parquet: Path, tolerance: float = 0.01):
        self.parquet = Path(parquet)
        self.tolerance = tolerance
        self.threshold = 1.0
        self.async_mode = False
        self.include_reason = True

    def measure(self, test_case: LLMTestCase) -> float:
        calls = [c for c in (test_case.tools_called or []) if c.name == "compute_correlation"]
        if not calls:
            self.score, self.success, self.reason = 0.0, False, "compute_correlation not called"
            return self.score
        bad = []
        for call in calls:
            output: str = call.output or ""
            try:
                parsed = json.loads(output)
            except json.JSONDecodeError:
                bad.append(f"unparseable tool output: {output[:80]!r}")
                continue
            if "matrix" not in parsed:
                # e.g. the tool returned {"error": ...} (missing ticker, bad range)
                bad.append(f"tool returned no matrix: {parsed.get('error', output[:80])}")
                continue
            reported = parsed["matrix"]
            params: dict[str, Any] = call.input_parameters or {}
            expected = _recompute_matrix(self.parquet, params["tickers"],
                                         params["start"], params["end"])
            for a in expected:
                for b in expected:
                    if abs(reported[a][b] - expected[a][b]) > self.tolerance:
                        bad.append(f"{a}/{b}: {reported[a][b]:.4f} vs {expected[a][b]:.4f}")
        self.success = not bad
        self.score = 1.0 if self.success else 0.0
        self.reason = "all cells within tolerance" if self.success else "; ".join(bad)
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):
        return "DeterministicCorrelation"


def to_test_case(input_text: str, run: RunResult, expected_tools: list[str] | None) -> LLMTestCase:
    return LLMTestCase(
        input=input_text,
        actual_output=run.final_text or "",
        tools_called=[DEToolCall(name=c.name, input_parameters=c.input, output=c.result)
                      for c in run.trajectory],
        expected_tools=[DEToolCall(name=n) for n in (expected_tools or [])],  # type: ignore[call-arg]
    )


def build_metric(check: dict[str, Any], *, judge: Any, parquet: Path):
    """Return (metric, type_label) for a golden check."""
    t = check["type"]
    if t == "deterministic":
        return DeterministicCorrelationMetric(parquet=parquet, tolerance=check.get("tolerance", 0.01)), "deterministic"
    if t == "tool_correctness":
        return ToolCorrectnessMetric(
            threshold=check.get("threshold", 1.0),
            should_consider_ordering=check.get("ordered", False),
            should_exact_match=check.get("exact_match", False),
            model=_NoModel(),  # deterministic metric — avoid the GPT default + key demand
        ), "tool_correctness"
    if t == "geval":
        return GEval(
            name=check.get("name", "criteria"), criteria=check["criteria"],
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
            model=judge, threshold=check.get("threshold", 0.7),
        ), "geval"
    raise ValueError(f"unknown check type: {t}")
