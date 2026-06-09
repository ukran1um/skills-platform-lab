"""Plain data carriers shared across the harness. No logic here."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillSpec:
    name: str
    version: str
    owner: str
    blast_radius: str
    allowed_mcp_servers: list[str]
    required_scopes: list[str]
    golden_set: str
    threshold: float
    system_prompt: str


@dataclass
class ToolCall:
    name: str
    input: dict[str, Any]
    result: str | None = None


@dataclass
class RunResult:
    final_text: str | None
    trajectory: list[ToolCall] = field(default_factory=list)

    def called_tools(self) -> list[str]:
        return [c.name for c in self.trajectory]


@dataclass
class CheckResult:
    type: str
    passed: bool
    score: float
    detail: str


@dataclass
class CaseResult:
    case_id: str
    checks: list[CheckResult]
    score: float


@dataclass
class EvalReport:
    skill: str
    cases: list[CaseResult]
    mean_score: float
    threshold: float
    passed: bool
