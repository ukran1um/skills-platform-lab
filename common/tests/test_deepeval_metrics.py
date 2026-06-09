import json
from pathlib import Path

from deepeval.test_case import LLMTestCase, ToolCall

from lab_common.deepeval_metrics import DeterministicCorrelationMetric, choose_judge_provider


def test_chooser_prefers_openai():
    assert choose_judge_provider({"OPENAI_API_KEY": "x", "ANTHROPIC_API_KEY": "y"}) == "openai"


def test_chooser_falls_back_to_anthropic():
    assert choose_judge_provider({"ANTHROPIC_API_KEY": "y"}) == "anthropic"


def test_chooser_gemini_when_only_google():
    assert choose_judge_provider({"GOOGLE_API_KEY": "g", "ANTHROPIC_API_KEY": "y"}) == "gemini"


def _tc(output: dict) -> LLMTestCase:
    return LLMTestCase(input="x", actual_output="...", tools_called=[ToolCall(
        name="compute_correlation",
        input_parameters={"tickers": ["AAPL", "MSFT"], "start": "2025-01-01", "end": "2025-06-30"},
        output=json.dumps(output))])


def test_deterministic_passes_on_correct_matrix(fixtures_parquet: Path):
    from datetime import date
    from factor_correlation.cli import run as skill_run
    truth = skill_run(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 6, 30), parquet=fixtures_parquet)
    m = DeterministicCorrelationMetric(parquet=fixtures_parquet, tolerance=0.01)
    m.measure(_tc(truth))
    assert m.is_successful() and m.score == 1.0


def test_deterministic_fails_on_wrong_matrix(fixtures_parquet: Path):
    bad = {"matrix": {"AAPL": {"AAPL": 1.0, "MSFT": 0.99}, "MSFT": {"AAPL": 0.99, "MSFT": 1.0}}}
    m = DeterministicCorrelationMetric(parquet=fixtures_parquet, tolerance=0.01)
    m.measure(_tc(bad))
    assert not m.is_successful()
