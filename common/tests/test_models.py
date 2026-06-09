from lab_common.models import (
    CaseResult,
    CheckResult,
    EvalReport,
    RunResult,
    SkillSpec,
    ToolCall,
)


def test_skillspec_fields():
    spec = SkillSpec(
        name="x",
        version="0.1.0",
        owner="egor",
        blast_radius="low",
        allowed_mcp_servers=["data_mcp"],
        required_scopes=["prices:read"],
        golden_set="evals/golden.yaml",
        threshold=0.8,
        system_prompt="do the thing",
    )
    assert spec.name == "x"
    assert spec.threshold == 0.8


def test_runresult_holds_trajectory():
    call = ToolCall(name="t", input={"a": 1}, result='{"r": 2}')
    run = RunResult(final_text="done", trajectory=[call])
    assert run.trajectory[0].name == "t"
    assert run.final_text == "done"
    assert run.called_tools() == ["t"]


def test_report_aggregates_case_scores():
    cr = CheckResult(type="trajectory", passed=True, score=1.0, detail="")
    case = CaseResult(case_id="c1", checks=[cr], score=1.0)
    report = EvalReport(skill="x", cases=[case], mean_score=1.0, threshold=0.8, passed=True)
    assert report.passed is True
    assert report.cases[0].case_id == "c1"
