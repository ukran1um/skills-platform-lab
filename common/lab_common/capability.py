"""Capability tokens: mint + verify HS256 JWTs scoped to a skill activation.

HS256 with a shared secret is deliberately the prototype's choice; a real platform uses
asymmetric keys + a JWKS endpoint (spec non-goal). The token is the artifact validated at
the MCP boundary: signature + expiry + audience at the transport (401), scope per tool
(in-protocol error)."""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt


class CapabilityError(Exception):
    """Token missing/invalid/expired/wrong-audience — a 401-level failure."""


class ScopeError(Exception):
    """Valid token, but it lacks the scope a tool requires — an in-protocol failure."""


@dataclass
class Claims:
    sub: str
    skill: str
    scopes: list[str]
    audience: str

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


def mint(*, sub: str, skill: str, scopes: list[str], audience: str, secret: str,
         ttl_seconds: int = 900) -> str:
    now = int(time.time())
    payload = {
        "sub": sub, "skill": skill, "scopes": list(scopes),
        "aud": audience, "iat": now, "exp": now + ttl_seconds,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify(token: str, *, audience: str, secret: str) -> Claims:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], audience=audience)
    except jwt.PyJWTError as exc:
        raise CapabilityError(str(exc)) from exc
    return Claims(
        sub=payload.get("sub", ""), skill=payload.get("skill", ""),
        scopes=list(payload.get("scopes", [])), audience=payload.get("aud", ""),
    )


def require_scope(claims: Claims, scope: str) -> None:
    if not claims.has_scope(scope):
        raise ScopeError(f"token for skill {claims.skill!r} lacks required scope {scope!r}")
