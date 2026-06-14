import pytest

from lab_common.capability import (
    CapabilityError,
    ScopeError,
    mint,
    require_scope,
    verify,
)

SECRET = "test-secret"


def test_mint_then_verify_roundtrip():
    tok = mint(sub="user:egor", skill="factor_correlation",
               scopes=["prices:read"], audience="data_mcp", secret=SECRET, ttl_seconds=900)
    claims = verify(tok, audience="data_mcp", secret=SECRET)
    assert claims.sub == "user:egor"
    assert claims.skill == "factor_correlation"
    assert claims.scopes == ["prices:read"]
    assert claims.has_scope("prices:read") and not claims.has_scope("query:run")


def test_wrong_secret_is_rejected():
    tok = mint(sub="u", skill="s", scopes=["prices:read"], audience="data_mcp", secret=SECRET)
    with pytest.raises(CapabilityError):
        verify(tok, audience="data_mcp", secret="other-secret")


def test_wrong_audience_is_rejected():
    tok = mint(sub="u", skill="s", scopes=["prices:read"], audience="research_mcp", secret=SECRET)
    with pytest.raises(CapabilityError):
        verify(tok, audience="data_mcp", secret=SECRET)


def test_expired_token_is_rejected():
    tok = mint(sub="u", skill="s", scopes=["prices:read"], audience="data_mcp",
               secret=SECRET, ttl_seconds=-1)
    with pytest.raises(CapabilityError):
        verify(tok, audience="data_mcp", secret=SECRET)


def test_require_scope_raises_on_missing():
    claims = verify(
        mint(sub="u", skill="s", scopes=["prices:read"], audience="data_mcp", secret=SECRET),
        audience="data_mcp", secret=SECRET,
    )
    require_scope(claims, "prices:read")
    with pytest.raises(ScopeError):
        require_scope(claims, "query:run")
