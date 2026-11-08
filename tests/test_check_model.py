"""Negative tests: the checker must reject leaked or permissive content."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "scripts" / "check_model.py"


def run_in_copy(mutate):
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "m"
        shutil.copytree(
            ROOT, work,
            ignore=shutil.ignore_patterns(".git", "__pycache__"),
        )
        subprocess.run(["git", "init", "-q"], cwd=work, check=True)
        mutate(work)
        return subprocess.run(
            [sys.executable, str(work / "scripts" / "check_model.py")],
            cwd=work, capture_output=True, text=True,
        )


def edit_json(path, fn):
    data = json.loads(path.read_text())
    fn(data)
    path.write_text(json.dumps(data))


class ModelChecks(unittest.TestCase):
    def test_clean_passes(self):
        self.assertEqual(run_in_copy(lambda w: None).returncode, 0)

    def test_inherited_reader_rejected(self):
        r = run_in_copy(lambda w: edit_json(
            w / "model/grants.template.json", lambda d: d["readers"].append("someone")))
        self.assertNotEqual(r.returncode, 0)

    def test_default_allow_rejected(self):
        r = run_in_copy(lambda w: edit_json(
            w / "model/grants.template.json", lambda d: d.update(default="allow")))
        self.assertNotEqual(r.returncode, 0)

    def test_preset_instance_identity_rejected(self):
        r = run_in_copy(lambda w: edit_json(
            w / "model/instance.template.json", lambda d: d.update(instance_id="x")))
        self.assertNotEqual(r.returncode, 0)

    def test_uuid_rejected(self):
        def m(w):
            (w / "docs/leak.md").write_text("id 123e4567-e89b-42d3-a456-426614174000\n")
        self.assertNotEqual(run_in_copy(m).returncode, 0)

    def test_host_path_rejected(self):
        def m(w):
            (w / "docs/leak.md").write_text("see /Users/someone/repo\n")
        self.assertNotEqual(run_in_copy(m).returncode, 0)

    def test_credential_rejected(self):
        def m(w):
            (w / "docs/leak.md").write_text("token ghp_" + "a" * 30 + "\n")
        self.assertNotEqual(run_in_copy(m).returncode, 0)

    def test_records_directory_rejected(self):
        def m(w):
            (w / "records").mkdir()
            (w / "records/x.json").write_text("{}")
        self.assertNotEqual(run_in_copy(m).returncode, 0)

    def test_broken_link_rejected(self):
        def m(w):
            (w / "docs/leak.md").write_text("[x](missing.md)\n")
        self.assertNotEqual(run_in_copy(m).returncode, 0)


if __name__ == "__main__":
    unittest.main()
