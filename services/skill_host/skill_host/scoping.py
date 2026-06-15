"""Mint a least-privilege capability token for a (user, skill): the user must hold every
scope the skill declares; the token then carries exactly those (required ⊆ granted)."""

from __future__ import annotations

from pathlib import Path

import yaml

from lab_common.capability import mint
from lab_common.models import SkillSpec

from skill_host.errors import EntitlementError

AUDIENCE = "data_mcp"


def _entitlements(path: str | Path) -> dict[str, list[str]]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return data.get("users", {})


def mint_scoped_token(
    spec: SkillSpec, user: str, *, entitlements_path: str | Path, secret: str,
    ttl_seconds: int = 900,
) -> tuple[str, list[str]]:
    users = _entitlements(entitlements_path)
    if user not in users:
        raise EntitlementError(f"unknown user {user!r}")
    granted = set(users[user])
    required = set(spec.required_scopes)
    missing = sorted(required - granted)
    if missing:
        raise EntitlementError(f"{user} lacks required scope(s) for {spec.name}: {missing}")
    scopes = sorted(required)  # required ⊆ granted -> least privilege
    token = mint(sub=user, skill=spec.name, scopes=scopes, audience=AUDIENCE,
                 secret=secret, ttl_seconds=ttl_seconds)
    return token, scopes
