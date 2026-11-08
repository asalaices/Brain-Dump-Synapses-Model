#!/usr/bin/env python3
"""Regression checks for the public synthetic Synapses-Model starter.

Standard library only. Exits nonzero with explicit findings on any violation.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
HOST_PATH = re.compile(r"(/Users/[^/\s]+|/home/[^/\s]+|[A-Za-z]:\\Users\\)")
SECRET = re.compile(
    r"(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})"
)
NUMERIC_REPO_ID = re.compile(r"(repository_id|repo_id|installation_id)\"?\s*[:=]\s*\"?\d+")
FORBIDDEN_DIRS = {"records", "ledger", "grants", "receipts", "cache", "logs"}
LINK = re.compile(r"\]\((?!https?://|#|mailto:)([^)#\s]+)")


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split("\n")
    return [ROOT / p for p in out if p and (ROOT / p).is_file()]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def check_templates(errors):
    inst = load("model/instance.template.json")
    for key in ("instance_id", "source_alias", "repository"):
        if inst.get(key) is not None:
            errors.append(f"instance.template.json: {key} must be null")
    if inst.get("status") != "uninitialized":
        errors.append("instance.template.json: status must be 'uninitialized'")
    extra = set(inst) - {"template_version", "status", "instance_id", "source_alias", "repository", "note"}
    if extra:
        errors.append(f"instance.template.json: unexpected keys {sorted(extra)}")

    grants = load("model/grants.template.json")
    if grants.get("default") != "deny":
        errors.append("grants.template.json: default must be 'deny'")
    for key in ("readers", "writers"):
        if grants.get(key) != []:
            errors.append(f"grants.template.json: {key} must be an empty list")
    extra = set(grants) - {"template_version", "default", "readers", "writers", "note"}
    if extra:
        errors.append(f"grants.template.json: unexpected keys {sorted(extra)}")

    example = load("examples/synthetic-record.example.json")
    if example.get("synthetic") is not True:
        errors.append("synthetic example must declare synthetic: true")


def check_content(errors, files):
    for path in files:
        rel = path.relative_to(ROOT)
        if rel.parts[0] in FORBIDDEN_DIRS:
            errors.append(f"{rel}: operational directory '{rel.parts[0]}' is not allowed in the public model")
        if rel.as_posix() == "scripts/check_model.py" or rel.parts[0] == "tests":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{rel}: binary file not allowed")
            continue
        for label, pattern in (
            ("UUID-shaped identifier", UUID),
            ("host-specific path", HOST_PATH),
            ("credential-like value", SECRET),
            ("numeric repository binding", NUMERIC_REPO_ID),
        ):
            if pattern.search(text):
                errors.append(f"{rel}: contains {label}")


def check_links(errors, files):
    for path in files:
        if path.suffix != ".md":
            continue
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            if not (path.parent / target).resolve().exists():
                errors.append(f"{path.relative_to(ROOT)}: broken relative link {target}")


def run_checks():
    errors = []
    files = tracked_files()
    check_templates(errors)
    check_content(errors, files)
    check_links(errors, files)
    return errors


def main():
    errors = run_checks()
    for err in errors:
        print(f"FAIL: {err}", file=sys.stderr)
    if errors:
        return 1
    print("OK: public model checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
