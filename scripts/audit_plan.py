#!/usr/bin/env python3
"""Read-only audit/plan report for the public Synapses-Model starter.

Reuses scripts/check_model.py. Writes nothing to the repository and publishes,
grants or imports nothing. Prints a structured JSON report; exits 1 when
blocking findings exist.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep the audit read-only
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_model  # noqa: E402

ROOT = check_model.ROOT

OUT_OF_SCOPE = [
    "release publication or destination selection",
    "reader/writer grants or enrollment",
    "private ledger records or history import",
    "git history audit or rewriting (working tree only)",
]


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def build_report():
    findings = check_model.run_checks()
    dirty = git("status", "--porcelain")
    return {
        "schema_version": 1,
        "mode": "audit-plan",
        "read_only": True,
        "head": git("rev-parse", "HEAD"),
        "working_tree_clean": dirty == "",
        "checked": ["templates", "content", "links"],
        "findings": [{"severity": "blocker", "message": m} for m in findings],
        "plan": [
            {"step": "resolve-blockers", "needed": bool(findings)},
            {"step": "commit-clean-tree", "needed": dirty != ""},
            {"step": "authorize-release-separately", "needed": True},
        ],
        "out_of_scope": OUT_OF_SCOPE,
        "ready_for_release_review": not findings and dirty == "",
    }


def main():
    report = build_report()
    print(json.dumps(report, indent=2))
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
