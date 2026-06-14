from pathlib import Path

from lab_common.governance.scopes import check_scopes, load_scope_vocab
from lab_common.models import SkillSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTITLEMENTS = REPO_ROOT / "registry" / "entitlements.yaml"


def _spec(scopes):
    return SkillSpec("x", "0.1.0", "e", "low", ["data_mcp"], scopes, "evals/golden.yaml", 0.8, "b")


def test_vocab_loads():
    vocab = load_scope_vocab(ENTITLEMENTS)
    assert "prices:read" in vocab and "kb:write" in vocab


def test_known_scopes_pass():
    vocab = load_scope_vocab(ENTITLEMENTS)
    assert check_scopes(_spec(["prices:read"]), vocab) == []


def test_unknown_scope_is_rejected():
    vocab = load_scope_vocab(ENTITLEMENTS)
    errs = check_scopes(_spec(["prices:read", "trading:write"]), vocab)
    assert any("trading:write" in e for e in errs)
