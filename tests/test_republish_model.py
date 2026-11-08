"""Behavioral tests for the Synapses-export consumer (synthetic fixtures only)."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "republish_model.py"
COMMIT = "a" * 40
ALLOW_SHA = "b" * 64
FILES = {
    "schemas/record.stub.json": b'{"id": "<UUIDv4>", "date": "YYYY-MM-DD"}\n',
    "examples/demo.json": b'{"label": "BD-DEMO", "note": "example-only"}\n',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_policy(path):
    path.write_text(json.dumps({
        "policy_version": 1, "format": "synapses-model-export/v1",
        "source_repo": "example/synthetic-source", "dest_root": "upstream",
        "max_files": 8, "max_file_bytes": 4096,
        "approved_allowlists": [{"version": "v1", "sha256": ALLOW_SHA}],
    }))


def build(artifact, files=None, **override):
    files = dict(FILES if files is None else files)
    (artifact / "files").mkdir(parents=True)
    entries = []
    for rel in sorted(files, key=lambda p: p.encode()):
        target = artifact / "files" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(files[rel])
        entries.append({"mode": "0644", "path": rel, "sha256": digest(files[rel]), "size": len(files[rel])})
    manifest = {
        "allowlist_sha256": ALLOW_SHA, "allowlist_version": "v1", "files": entries,
        "format": "synapses-model-export/v1", "generated_by": "fixture 1.0.0",
        "source_commit": COMMIT, "source_repo": "example/synthetic-source", "source_tree_clean": True,
    }
    manifest.update(override)
    seal(artifact, manifest)


def seal(artifact, manifest):
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    (artifact / "manifest.json").write_bytes(raw)
    (artifact / "manifest.sha256").write_text(digest(raw) + "\n")


def load_manifest(artifact):
    return json.loads((artifact / "manifest.json").read_text())


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        (self.repo / "model").mkdir()
        self.policy = self.tmp / "policy.json"
        write_policy(self.policy)
        self.artifact = self.tmp / "artifact"

    def run_cli(self, command, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), command, "--artifact", str(self.artifact),
             "--repo", str(self.repo), "--policy", str(self.policy), *extra],
            capture_output=True, text=True)

    def snapshot(self):
        return {p.relative_to(self.repo).as_posix(): p.read_bytes()
                for p in sorted(self.repo.rglob("*")) if p.is_file()}

    def assertRefused(self, result, text=""):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("refused", result.stderr)
        self.assertIn(text, result.stderr)


class Apply(Base):
    def test_apply_writes_files_and_provenance(self):
        build(self.artifact)
        r = self.run_cli("apply", "--execute")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["status"], "applied")
        for rel, data in FILES.items():
            self.assertEqual((self.repo / "upstream" / rel).read_bytes(), data)
        prov = json.loads((self.repo / "model/PROVENANCE.json").read_text())
        self.assertEqual(prov["source_commit"], COMMIT)
        self.assertEqual(len(prov["files"]), 2)
        self.assertFalse([p for p in self.repo.iterdir() if p.name.startswith(".republish-")])

    def test_apply_without_execute_is_plan_only(self):
        build(self.artifact)
        r = self.run_cli("apply")
        self.assertEqual(json.loads(r.stdout)["status"], "planned")
        self.assertEqual(self.snapshot(), {})

    def test_republish_same_artifact_is_noop(self):
        build(self.artifact)
        self.run_cli("apply", "--execute")
        before = self.snapshot()
        r = self.run_cli("apply", "--execute")
        self.assertEqual(json.loads(r.stdout)["status"], "noop")
        self.assertEqual(self.snapshot(), before)

    def test_update_changes_only_modified_file(self):
        build(self.artifact)
        self.run_cli("apply", "--execute")
        shutil.rmtree(self.artifact)
        changed = dict(FILES, **{"examples/demo.json": b'{"label": "BD-DEMO"}\n'})
        build(self.artifact, changed, source_commit="c" * 40)
        r = self.run_cli("apply", "--execute")
        actions = {a["path"]: a["action"] for a in json.loads(r.stdout)["actions"]}
        self.assertEqual(actions["upstream/examples/demo.json"], "update")
        self.assertEqual(actions["upstream/schemas/record.stub.json"], "unchanged")
        prov = json.loads((self.repo / "model/PROVENANCE.json").read_text())
        self.assertEqual(prov["source_commit"], "c" * 40)

    def test_executable_mode_applied_exactly(self):
        build(self.artifact)
        manifest = load_manifest(self.artifact)
        manifest["files"][0]["mode"] = "0755"
        seal(self.artifact, manifest)
        self.run_cli("apply", "--execute")
        first = self.repo / "upstream" / manifest["files"][0]["path"]
        self.assertEqual(first.stat().st_mode & 0o777, 0o755)

    def test_failed_apply_rolls_back_and_leaves_no_partial_writes(self):
        build(self.artifact)
        self.run_cli("apply", "--execute")
        shutil.rmtree(self.artifact)
        build(self.artifact, dict(FILES, **{"examples/demo.json": b'{"x": 1}\n'}), source_commit="d" * 40)
        before = self.snapshot()
        mod = {}
        sys.path.insert(0, str(ROOT / "scripts"))
        import republish_model as rm
        policy = rm.load_policy(self.policy)
        manifest, dig, payload = rm.verify_artifact(self.artifact, policy)
        plan = rm.build_plan(self.repo, manifest, dig, payload, policy)
        real = os.replace
        calls = {"n": 0}

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] == 4:
                raise OSError("injected")
            return real(src, dst)
        rm.os.replace = flaky
        try:
            with self.assertRaises(OSError):
                rm.apply_plan(self.repo, plan, manifest, payload, policy)
        finally:
            rm.os.replace = real
        self.assertEqual(self.snapshot(), before)


class Refusals(Base):
    def refuse_unchanged(self, text, command="apply"):
        extra = ("--execute",) if command == "apply" else ()
        r = self.run_cli(command, *extra)
        self.assertRefused(r, text)
        self.assertEqual(self.snapshot(), {})

    def test_digest_mismatch(self):
        build(self.artifact)
        (self.artifact / "manifest.sha256").write_text("0" * 64 + "\n")
        self.refuse_unchanged("digest does not match")

    def test_tampered_payload(self):
        build(self.artifact)
        (self.artifact / "files/examples/demo.json").write_bytes(b'{"label": "x"}\n')
        self.refuse_unchanged("mismatch")

    def test_unlisted_payload_file(self):
        build(self.artifact)
        (self.artifact / "files/extra.json").write_text("{}\n")
        self.refuse_unchanged("unlisted")

    def test_unknown_manifest_key(self):
        build(self.artifact, bonus="x")
        self.refuse_unchanged("manifest keys")

    def test_non_canonical_manifest(self):
        build(self.artifact)
        raw = json.dumps(load_manifest(self.artifact), indent=1).encode()
        (self.artifact / "manifest.json").write_bytes(raw)
        (self.artifact / "manifest.sha256").write_text(digest(raw) + "\n")
        self.refuse_unchanged("canonical")

    def test_unapproved_allowlist_digest(self):
        build(self.artifact, allowlist_sha256="c" * 64)
        self.refuse_unchanged("not approved")

    def test_unapproved_format_and_source(self):
        build(self.artifact, source_repo="someone/else")
        self.refuse_unchanged("source_repo")

    def test_dirty_source_flag(self):
        build(self.artifact, source_tree_clean=False)
        self.refuse_unchanged("source_tree_clean")

    def test_bad_commit(self):
        build(self.artifact, source_commit="abc")
        self.refuse_unchanged("40-hex")

    def test_path_rules(self):
        for bad in ("../x.json", "a/./b.json", "/abs.json", "a//b.json", "a\\b.json", "sp ace.json"):
            with self.subTest(bad=bad):
                shutil.rmtree(self.artifact, ignore_errors=True)
                build(self.artifact, {"ok.json": b"{}\n"})
                manifest = load_manifest(self.artifact)
                manifest["files"][0]["path"] = bad
                seal(self.artifact, manifest)
                self.assertRefused(self.run_cli("verify"))

    def test_case_fold_collision(self):
        build(self.artifact, {"A.json": b"{}\n", "a.json": b"{}\n"})
        self.assertRefused(self.run_cli("verify"), "collision")

    def test_unicode_normalization_collision(self):
        build(self.artifact, {"caf\u00e9.json": b"{}\n"})
        manifest = load_manifest(self.artifact)
        manifest["files"].append(dict(manifest["files"][0], path="cafe\u0301.json"))
        seal(self.artifact, manifest)
        self.assertRefused(self.run_cli("verify"))

    def test_duplicate_or_unsorted(self):
        build(self.artifact)
        manifest = load_manifest(self.artifact)
        manifest["files"].append(manifest["files"][0])
        seal(self.artifact, manifest)
        self.assertRefused(self.run_cli("verify"), "sorted")

    def test_bad_mode(self):
        build(self.artifact)
        manifest = load_manifest(self.artifact)
        manifest["files"][0]["mode"] = "0777"
        seal(self.artifact, manifest)
        self.assertRefused(self.run_cli("verify"), "mode")

    def test_symlink_in_payload(self):
        build(self.artifact)
        link = self.artifact / "files" / "link.json"
        os.symlink(self.artifact / "files/examples/demo.json", link)
        self.refuse_unchanged("symlink")

    def test_leaks_rejected(self):
        leaks = {
            "uuid": b'{"id": "3f2b8c1e-9a4d-4e6b-8c1f-2a7d9e0b5c43"}\n',
            "host path": b'{"p": "/Users/someone/repo"}\n',
            "credential": b'{"t": "ghp_' + b"A" * 24 + b'"}\n',
            "private host": b'{"h": "master-01"}\n',
            "repo id": b'{"github_repository_id": 123456}\n',
            "crlf": b'{"a": 1}\r\n',
        }
        for name, data in leaks.items():
            with self.subTest(name):
                shutil.rmtree(self.artifact, ignore_errors=True)
                build(self.artifact, {"leak.json": data})
                self.assertRefused(self.run_cli("verify"))

    def test_placeholders_and_nil_uuid_are_not_leaks(self):
        build(self.artifact, {"ok.json": b'{"id": "<UUIDv4>", "nil": "00000000-0000-0000-0000-000000000000"}\n'})
        self.assertEqual(self.run_cli("verify").returncode, 0)

    def test_symlinked_destination_parent(self):
        build(self.artifact)
        outside = self.tmp / "outside"
        outside.mkdir()
        os.symlink(outside, self.repo / "upstream")
        self.assertRefused(self.run_cli("apply", "--execute"), "symlink")
        self.assertEqual(list(outside.iterdir()), [])

    def test_unmanaged_existing_file_is_not_overwritten(self):
        build(self.artifact)
        target = self.repo / "upstream/examples/demo.json"
        target.parent.mkdir(parents=True)
        target.write_text("mine\n")
        self.assertRefused(self.run_cli("apply", "--execute"), "not managed")
        self.assertEqual(target.read_text(), "mine\n")
        self.assertFalse((self.repo / "model/PROVENANCE.json").exists())

    def test_stale_previous_file_is_not_deleted(self):
        build(self.artifact)
        self.run_cli("apply", "--execute")
        shutil.rmtree(self.artifact)
        build(self.artifact, {"schemas/record.stub.json": FILES["schemas/record.stub.json"]})
        before = self.snapshot()
        self.assertRefused(self.run_cli("apply", "--execute"), "no deletions")
        self.assertEqual(self.snapshot(), before)

    def test_extra_artifact_root_entry(self):
        build(self.artifact)
        (self.artifact / "notes.txt").write_text("x")
        self.assertRefused(self.run_cli("verify"), "exactly")


class Shipped(unittest.TestCase):
    def test_shipped_policy_is_well_formed(self):
        policy = json.loads((ROOT / "model/republish-policy.json").read_text())
        self.assertEqual(policy["format"], "synapses-model-export/v1")
        self.assertTrue(all(len(a["sha256"]) == 64 for a in policy["approved_allowlists"]))


if __name__ == "__main__":
    unittest.main()
