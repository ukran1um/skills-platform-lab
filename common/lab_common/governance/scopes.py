"""Validate a skill's required_scopes against the platform scope vocabulary."""

from __future__ import annotations

from pathlib import Path

import yaml

from lab_common.models import SkillSpec


def load_scope_vocab(entitlements_path: str | Path) -> set[str]:
    data = yaml.safe_load(Path(entitlements_path).read_text()) or {}
    return set(data.get("scopes", []))


def check_scopes(spec: SkillSpec, vocab: set[str]) -> list[str]:
    return [
        f"unknown scope '{s}' (not in the entitlements vocabulary)"
        for s in spec.required_scopes
        if s not in vocab
    ]
