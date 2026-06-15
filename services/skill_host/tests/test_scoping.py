"""Least-privilege token minting: the user must hold EVERY scope the skill declares; the
token then carries exactly those (required ⊆ granted)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab_common.capability import verify
from lab_common.models import SkillSpec
from skill_host.errors import EntitlementError
from skill_host.scoping import mint_scoped_token

REPO = Path(__file__).resolve().parents[3]
ENTITLEMENTS = REPO / "registry" / "entitlements.yaml"
SECRET = "skill-host-scoping-test-secret-32!"


def _spec(scopes):
    return SkillSpec(name="s", version="0", owner="", blast_radius="", allowed_mcp_servers=[],
                     required_scopes=scopes, golden_set="", threshold=0.0, system_prompt="p")


def test_mints_least_privilege_token_for_entitled_user():
    token, scopes = mint_scoped_token(_spec(["prices:read"]), "egor",
                                      entitlements_path=ENTITLEMENTS, secret=SECRET)
    assert scopes == ["prices:read"]
    claims = verify(token, audience="data_mcp", secret=SECRET)
    assert claims.sub == "egor" and claims.has_scope("prices:read")


def test_unknown_user_is_denied():
    with pytest.raises(EntitlementError):
        mint_scoped_token(_spec(["prices:read"]), "nobody",
                          entitlements_path=ENTITLEMENTS, secret=SECRET)


def test_missing_required_scope_is_denied(tmp_path: Path):
    ent = tmp_path / "entitlements.yaml"
    ent.write_text("users:\n  bob: [prices:read]\n")
    with pytest.raises(EntitlementError):
        mint_scoped_token(_spec(["prices:read", "fundamentals:read"]), "bob",
                          entitlements_path=ent, secret=SECRET)
