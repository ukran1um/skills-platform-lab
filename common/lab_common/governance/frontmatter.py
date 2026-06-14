"""Validate a skill's frontmatter contract with a Pydantic schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from lab_common.models import SkillSpec


class Frontmatter(BaseModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    blast_radius: Literal["negligible", "low", "medium", "high"]
    allowed_mcp_servers: list[str]
    required_scopes: list[str]
    golden_set: str = Field(min_length=1)
    threshold: float

    @field_validator("threshold")
    @classmethod
    def _threshold_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")
        return v


def check_frontmatter(spec: SkillSpec) -> list[str]:
    """Return a list of human-readable validation errors ([] if valid)."""
    try:
        Frontmatter(
            name=spec.name, version=spec.version, owner=spec.owner,
            blast_radius=spec.blast_radius,  # type: ignore[arg-type]
            allowed_mcp_servers=spec.allowed_mcp_servers,
            required_scopes=spec.required_scopes, golden_set=spec.golden_set,
            threshold=spec.threshold,
        )
    except ValidationError as exc:
        return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
    return []
