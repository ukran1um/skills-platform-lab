"""Starlette middleware: validate the capability token at the transport boundary.

Missing/invalid/expired/wrong-audience token -> 401 + WWW-Authenticate (the Stripe/RFC9728
pattern). On success, the verified Claims are stashed on request.state for the tools to read
(per-tool SCOPE is enforced in the tools as an in-protocol error, not here)."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lab_common.capability import CapabilityError, verify

AUDIENCE = "data_mcp"
SECRET_ENV = "CAPABILITY_SECRET"
DEFAULT_SECRET = "dev-secret-not-for-production"

_CHALLENGE = 'Bearer resource_metadata="/.well-known/oauth-protected-resource"'


def _secret() -> str:
    return os.environ.get(SECRET_ENV, DEFAULT_SECRET)


class CapabilityAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else ""
        detail: str | None = "missing bearer token" if not token else None
        if token:
            try:
                request.state.capability_claims = verify(token, audience=AUDIENCE, secret=_secret())
            except CapabilityError as exc:
                detail = str(exc)
        if detail:
            return JSONResponse(
                {"error": "unauthorized", "detail": detail},
                status_code=401,
                headers={"WWW-Authenticate": _CHALLENGE},
            )
        return await call_next(request)
