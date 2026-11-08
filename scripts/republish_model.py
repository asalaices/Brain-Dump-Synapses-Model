#!/usr/bin/env python3
"""Consumer for the Synapses-owned sanitized export (synapses-model-export/v1).

Standard library only. Consumes only a producer-built artifact directory
(manifest.json, manifest.sha256, files/). It never reads a private repository.

  verify --artifact DIR            validate the artifact; write nothing
  plan   --artifact DIR            verify and report create/update/unchanged
  apply  --artifact DIR            same as plan unless --execute is given
  apply  --artifact DIR --execute  all-or-nothing write into the destination root

Authenticity limit: source_commit and source_tree_clean are producer
assertions. The consumer can check only internal consistency (digest, hashes,
sizes), conformance to its own approved policy, and the commit string shape.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_model  # noqa: E402

POLICY_PATH = ROOT / "model" / "republish-policy.json"
PROVENANCE = "model/PROVENANCE.json"
MANIFEST_KEYS = {"format", "source_repo", "source_commit", "source_tree_clean",
                 "allowlist_version", "allowlist_sha256", "generated_by", "files"}
ENTRY_KEYS = {"path", "sha256", "size", "mode"}
MODES = {"0644": 0o644, "0755": 0o755}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
GENERATED_BY = re.compile(r"^[A-Za-z0-9._-]+ [0-9A-Za-z.+-]+$")
NIL_UUID = "-".join("0" * n for n in (8, 4, 4, 4, 12))
EXTRA_LEAKS = (
    ("private temp path", re.compile(r"/private/tmp")),
    ("private host identifier", re.compile(r"master-01")),
    ("numeric repository binding", re.compile(r"github_repository_id\"?\s*[:=]\s*\"?\d+")),
)


class Refusal(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def fold(path):
    return unicodedata.normalize("NFC", path).casefold()


def load_policy(path=POLICY_PATH):
    try:
        policy = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refusal(f"policy unreadable: {exc}")
    for key in ("format", "source_repo", "dest_root", "max_files", "max_file_bytes", "approved_allowlists"):
        if key not in policy:
            raise Refusal(f"policy missing '{key}'")
    check_path(policy["dest_root"], "policy dest_root")
    return policy


def check_path(path, what="path"):
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        raise Refusal(f"{what} {path!r}: must be a relative POSIX path")
    for seg in path.split("/"):
        if seg in ("", ".", ".."):
            raise Refusal(f"{what} {path!r}: empty, '.' or '..' segment")
        if not SEGMENT.match(seg):
            raise Refusal(f"{what} {path!r}: unsupported characters")


def read_manifest(artifact):
    mpath, dpath = artifact / "manifest.json", artifact / "manifest.sha256"
    for p in (mpath, dpath):
        if p.is_symlink() or not p.is_file():
            raise Refusal(f"{p.name}: missing or not a regular file")
    raw = mpath.read_bytes()
    declared = dpath.read_text(encoding="ascii", errors="replace").strip()
    if not HEX64.match(declared):
        raise Refusal("manifest.sha256: not a lowercase hex SHA-256")
    if sha256(raw) != declared:
        raise Refusal("manifest.json digest does not match manifest.sha256")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise Refusal(f"manifest.json: invalid JSON: {exc}")
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if canonical != raw:
        raise Refusal("manifest.json is not canonical JSON")
    return manifest, declared


def check_manifest(manifest, policy):
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        extra = sorted(set(manifest) - MANIFEST_KEYS) if isinstance(manifest, dict) else []
        raise Refusal(f"manifest keys must match exactly (unexpected: {extra})")
    if manifest["format"] != policy["format"]:
        raise Refusal(f"format {manifest['format']!r} is not approved")
    if manifest["source_repo"] != policy["source_repo"]:
        raise Refusal(f"source_repo {manifest['source_repo']!r} is not approved")
    if not isinstance(manifest["source_commit"], str) or not COMMIT.match(manifest["source_commit"]):
        raise Refusal("source_commit must be a 40-hex string")
    if manifest["source_tree_clean"] is not True:
        raise Refusal("source_tree_clean must be true")
    if not isinstance(manifest["generated_by"], str) or not GENERATED_BY.match(manifest["generated_by"]):
        raise Refusal("generated_by must be 'name version'")
    pair = (manifest["allowlist_version"], manifest["allowlist_sha256"])
    if pair not in {(a["version"], a["sha256"]) for a in policy["approved_allowlists"]}:
        raise Refusal("allowlist version/digest pair is not approved by the consumer policy")
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise Refusal("files must be a non-empty list")
    if len(files) > policy["max_files"]:
        raise Refusal("too many files")
    seen, prev = {}, None
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != ENTRY_KEYS:
            raise Refusal("file entry keys must be path, sha256, size, mode")
        path = entry["path"]
        check_path(path)
        if prev is not None and path.encode() <= prev.encode():
            raise Refusal(f"files not strictly sorted bytewise at {path!r} (duplicate or order)")
        prev = path
        key = fold(path)
        if key in seen:
            raise Refusal(f"case/normalization collision: {path!r} vs {seen[key]!r}")
        seen[key] = path
        if not isinstance(entry["sha256"], str) or not HEX64.match(entry["sha256"]):
            raise Refusal(f"{path}: bad sha256")
        size = entry["size"]
        if type(size) is not int or size < 0 or size > policy["max_file_bytes"]:
            raise Refusal(f"{path}: bad size")
        if entry["mode"] not in MODES:
            raise Refusal(f"{path}: mode must be 0644 or 0755")


def scan_text(path, text):
    if "\r" in text:
        raise Refusal(f"{path}: contains CR (LF-only payload required)")
    for label, pattern in (("host-specific path", check_model.HOST_PATH),
                           ("credential-like value", check_model.SECRET),
                           ("numeric repository binding", check_model.NUMERIC_REPO_ID)) + EXTRA_LEAKS:
        if pattern.search(text):
            raise Refusal(f"{path}: contains {label}")
    for match in check_model.UUID.findall(text):
        if match != NIL_UUID:
            raise Refusal(f"{path}: contains UUID-shaped identifier")


def verify_artifact(artifact, policy):
    artifact = Path(artifact)
    if artifact.is_symlink() or not artifact.is_dir():
        raise Refusal("artifact must be a real directory")
    if {p.name for p in artifact.iterdir()} != {"manifest.json", "manifest.sha256", "files"}:
        raise Refusal("artifact must contain exactly manifest.json, manifest.sha256 and files/")
    manifest, manifest_digest = read_manifest(artifact)
    check_manifest(manifest, policy)
    base = artifact / "files"
    if base.is_symlink() or not base.is_dir():
        raise Refusal("files/ must be a real directory")
    present = set()
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        for name in dirnames + filenames:
            full = Path(dirpath) / name
            if full.is_symlink():
                raise Refusal(f"symlink in payload: {full.relative_to(base).as_posix()}")
        for name in filenames:
            present.add((Path(dirpath) / name).relative_to(base).as_posix())
    declared = {e["path"] for e in manifest["files"]}
    if present != declared:
        raise Refusal(f"payload differs from manifest (unlisted: {sorted(present - declared)}, "
                      f"missing: {sorted(declared - present)})")
    payload = {}
    for entry in manifest["files"]:
        data = (base / entry["path"]).read_bytes()
        if len(data) != entry["size"] or sha256(data) != entry["sha256"]:
            raise Refusal(f"{entry['path']}: size or sha256 mismatch")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise Refusal(f"{entry['path']}: not UTF-8 text")
        scan_text(entry["path"], text)
        payload[entry["path"]] = data
    return manifest, manifest_digest, payload


def provenance_for(manifest, manifest_digest, policy):
    return {
        "format": manifest["format"],
        "source_repo": manifest["source_repo"],
        "source_commit": manifest["source_commit"],
        "allowlist_version": manifest["allowlist_version"],
        "allowlist_sha256": manifest["allowlist_sha256"],
        "manifest_sha256": manifest_digest,
        "dest_root": policy["dest_root"],
        "files": [{"path": e["path"], "sha256": e["sha256"], "size": e["size"], "mode": e["mode"]}
                  for e in manifest["files"]],
        "note": "Producer assertions are not independently verified by this consumer.",
    }


def render(obj):
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


def check_destination(repo, rel):
    """Refuse symlinked parents/targets and case/normalization aliases."""
    cur = repo
    parts = rel.split("/")
    for i, part in enumerate(parts):
        if cur.is_symlink():
            raise Refusal(f"{rel}: parent is a symlink")
        if cur.exists():
            for name in os.listdir(cur):
                if name != part and fold(name) == fold(part):
                    raise Refusal(f"{rel}: collides with existing '{name}'")
        cur = cur / part
        if cur.is_symlink():
            raise Refusal(f"{rel}: path component is a symlink")
        if i < len(parts) - 1 and cur.exists() and not cur.is_dir():
            raise Refusal(f"{rel}: parent is not a directory")
    if cur.exists() and not cur.is_file():
        raise Refusal(f"{rel}: destination is not a regular file")
    return cur


def read_existing_provenance(repo):
    path = repo / PROVENANCE
    if path.is_symlink():
        raise Refusal("PROVENANCE.json is a symlink")
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {f["path"]: f for f in data["files"]}, data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise Refusal(f"existing PROVENANCE.json is invalid: {exc}")


def build_plan(repo, manifest, manifest_digest, payload, policy):
    repo = Path(repo)
    dest_root = policy["dest_root"]
    existing = read_existing_provenance(repo)
    managed = existing[0] if existing else {}
    actions = []
    for entry in manifest["files"]:
        rel = f"{dest_root}/{entry['path']}"
        target = check_destination(repo, rel)
        if not target.exists():
            action = "create"
        else:
            same = target.read_bytes() == payload[entry["path"]] and \
                (target.stat().st_mode & 0o777) == MODES[entry["mode"]]
            if entry["path"] not in managed and not same:
                raise Refusal(f"{rel}: exists and is not managed by a previous republish")
            action = "unchanged" if same else "update"
        actions.append({"path": rel, "action": action})
    stale = sorted(p for p in managed if p not in payload)
    if stale:
        raise Refusal(f"previously provided files absent from artifact (no deletions in this scope): {stale}")
    prov = render(provenance_for(manifest, manifest_digest, policy))
    check_destination(repo, PROVENANCE)
    prov_path = repo / PROVENANCE
    prov_same = prov_path.exists() and prov_path.read_bytes() == prov
    noop = prov_same and all(a["action"] == "unchanged" for a in actions)
    return {"actions": actions, "provenance_changed": not prov_same, "noop": noop,
            "source_commit": manifest["source_commit"], "provenance_bytes": prov}


def apply_plan(repo, plan, manifest, payload, policy):
    repo = Path(repo)
    stage = Path(tempfile.mkdtemp(prefix=".republish-", dir=repo))
    created_dirs, done = [], []
    try:
        writes = []
        for entry in manifest["files"]:
            rel = f"{policy['dest_root']}/{entry['path']}"
            writes.append((rel, payload[entry["path"]], MODES[entry["mode"]]))
        writes.append((PROVENANCE, plan["provenance_bytes"], 0o644))
        staged = []
        for i, (rel, data, mode) in enumerate(writes):
            src = stage / f"new-{i}"
            src.write_bytes(data)
            os.chmod(src, mode)
            staged.append((rel, src))
        for i, (rel, src) in enumerate(staged):
            target = repo / rel
            missing = []
            parent = target.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for d in reversed(missing):
                d.mkdir()
                created_dirs.append(d)
            backup = None
            if target.exists():
                backup = stage / f"old-{i}"
                os.replace(target, backup)
            done.append((target, backup))
            os.replace(src, target)
    except BaseException:
        for target, backup in reversed(done):
            if target.exists():
                target.unlink()
            if backup is not None:
                os.replace(backup, target)
        for d in reversed(created_dirs):
            try:
                d.rmdir()
            except OSError:
                pass
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def run(args):
    policy = load_policy(args.policy)
    manifest, digest, payload = verify_artifact(args.artifact, policy)
    result = {"status": "verified", "source_commit": manifest["source_commit"],
              "allowlist_version": manifest["allowlist_version"], "files": len(manifest["files"])}
    if args.command == "verify":
        return result
    plan = build_plan(args.repo, manifest, digest, payload, policy)
    result.update(status="noop" if plan["noop"] else "planned", actions=plan["actions"],
                  provenance_changed=plan["provenance_changed"])
    if args.command == "apply" and args.execute and not plan["noop"]:
        apply_plan(args.repo, plan, manifest, payload, policy)
        result["status"] = "applied"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["verify", "plan", "apply"])
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument("--policy", default=str(POLICY_PATH))
    parser.add_argument("--execute", action="store_true", help="required for apply to write")
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except Refusal as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
