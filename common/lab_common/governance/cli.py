"""Governance CLI: run the gates over a skill (or all skills), and reconcile the registry.

  python -m lab_common.governance.cli check <skill_dir>
  python -m lab_common.governance.cli check-all [--skills skills]
  python -m lab_common.governance.cli reconcile [--out registry.json]

Exits non-zero on any violation / disagreement, so CI can gate on it."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from lab_common.governance.blast_radius import check_blast_radius
from lab_common.governance.frontmatter import check_frontmatter
from lab_common.governance.reconcile import reconcile_all
from lab_common.governance.scopes import check_scopes, load_scope_vocab
from lab_common.skill_spec import load_skill

DEFAULT_ENTITLEMENTS = "registry/entitlements.yaml"


def check_skill(skill_dir: str | Path, entitlements: str | Path) -> dict[str, list[str]]:
    spec = load_skill(skill_dir)
    vocab = load_scope_vocab(entitlements)
    return {
        "frontmatter": check_frontmatter(spec),
        "blast_radius": check_blast_radius(spec, skill_dir),
        "scopes": check_scopes(spec, vocab),
    }


def _print_skill(name: str, results: dict[str, list[str]]) -> bool:
    ok = True
    for gate, errs in results.items():
        if errs:
            ok = False
            for e in errs:
                print(f"  [FAIL] {name} / {gate}: {e}")
        else:
            print(f"  [pass] {name} / {gate}")
    return ok


def _source_commit() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Skill governance gates")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check")
    c.add_argument("skill_dir")
    c.add_argument("--entitlements", default=DEFAULT_ENTITLEMENTS)

    ca = sub.add_parser("check-all")
    ca.add_argument("--skills", default="skills")
    ca.add_argument("--entitlements", default=DEFAULT_ENTITLEMENTS)

    r = sub.add_parser("reconcile")
    r.add_argument("--skills", default="skills")
    r.add_argument("--registry", default="registry")
    r.add_argument("--out", type=Path)

    args = parser.parse_args()

    if args.cmd == "check":
        ok = _print_skill(Path(args.skill_dir).name, check_skill(args.skill_dir, args.entitlements))
        sys.exit(0 if ok else 1)

    if args.cmd == "check-all":
        all_ok = True
        for skill in sorted(d for d in Path(args.skills).iterdir() if (d / "SKILL.md").exists()):
            all_ok = _print_skill(skill.name, check_skill(skill, args.entitlements)) and all_ok
        sys.exit(0 if all_ok else 1)

    if args.cmd == "reconcile":
        report = reconcile_all(args.skills, args.registry, _source_commit())
        bad = False
        for rec in report["skills"]:
            errs = rec.get("agreement_errors") or []
            bad = bad or bool(errs)
            tail = (" ERRORS: " + "; ".join(errs)) if errs else ""
            print(f"  {rec['name']}: status={rec.get('status')}{tail}")
        if args.out:
            args.out.write_text(json.dumps(report, indent=2))
            print(f"wrote {args.out}")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
