"""Tests for the read-only audit/plan report."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def audit(mutate=None):
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "m"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        subprocess.run(["git", "init", "-q"], cwd=work, check=True)
        if mutate:
            mutate(work)
        before = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=work,
                                capture_output=True, text=True).stdout
        r = subprocess.run([sys.executable, str(work / "scripts/audit_plan.py")],
                           cwd=work, capture_output=True, text=True)
        after = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=work,
                               capture_output=True, text=True).stdout
        return r, json.loads(r.stdout), before == after


class AuditPlan(unittest.TestCase):
    def test_clean_report(self):
        r, rep, unchanged = audit()
        self.assertEqual(r.returncode, 0)
        self.assertEqual(rep["findings"], [])
        self.assertTrue(rep["read_only"])
        self.assertTrue(unchanged)

    def test_leak_reported_as_blocker_without_mutation(self):
        def m(w):
            (w / "docs/leak.md").write_text("see /Users/someone/repo\n")
        r, rep, unchanged = audit(m)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("host-specific path" in f["message"] for f in rep["findings"]))
        self.assertFalse(rep["ready_for_release_review"])
        self.assertTrue(unchanged)

    def test_out_of_scope_declared(self):
        _, rep, _ = audit()
        self.assertTrue(any("grants" in s for s in rep["out_of_scope"]))


if __name__ == "__main__":
    unittest.main()
