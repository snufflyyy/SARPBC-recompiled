#!/usr/bin/env python3
"""Source-only tests of tools/task.sh in a throwaway git repository (no game data).

Covers the board hazards from docs/project-audit.md A10: unique IDs under concurrent
`new`, exactly one winner per `claim`, and owner checks on note/done/release.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent / "task.sh"


class TaskBoard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "tools").mkdir()
        shutil.copy(SCRIPT, self.root / "tools" / "task.sh")

    def tearDown(self):
        self.tmp.cleanup()

    def task(self, *args, env=None):
        return subprocess.run([str(self.root / "tools" / "task.sh"), *args],
                              capture_output=True, text=True, env=env)

    def names(self, state):
        return sorted(p.name for p in (self.root / "docs/tasks" / state).glob("*.md"))

    def test_concurrent_new_allocates_unique_ids(self):
        with ThreadPoolExecutor(8) as ex:
            results = list(ex.map(lambda i: self.task("new", f"t{i}", "title"), range(16)))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results])
        ids = [n[:4] for n in self.names("open")]
        self.assertEqual(len(ids), 16)
        self.assertEqual(len(set(ids)), 16)

    def test_new_rejects_bad_slug(self):
        self.assertNotEqual(self.task("new", "../evil", "x").returncode, 0)
        self.assertEqual(self.names("open"), [])

    def test_single_claim_winner(self):
        self.task("new", "a", "A")
        with ThreadPoolExecutor(6) as ex:
            results = list(ex.map(lambda i: self.task("claim", "T001", f"agent{i}"), range(6)))
        self.assertEqual(sum(r.returncode == 0 for r in results), 1)
        self.assertEqual(len(self.names("claimed")), 1)

    def test_owner_checks(self):
        self.task("new", "a", "A")
        self.assertEqual(self.task("claim", "T001", "alice").returncode, 0)
        for cmd in (("note", "T001", "bob", "hi"), ("done", "T001", "bob", "x"),
                    ("release", "T001", "bob", "x")):
            r = self.task(*cmd)
            self.assertNotEqual(r.returncode, 0, cmd)
            self.assertIn("owned by 'alice'", r.stderr)
        self.assertEqual(len(self.names("claimed")), 1)
        self.assertEqual(self.task("note", "T001", "alice", "ok").returncode, 0)
        import os
        env = dict(os.environ, TASK_FORCE="1")
        self.assertEqual(self.task("release", "T001", "bob", "gone", env=env).returncode, 0)
        self.assertEqual(len(self.names("open")), 1)
        self.task("claim", "T001", "alice")
        self.assertEqual(self.task("done", "T001", "alice", "fin").returncode, 0)
        self.assertEqual(len(self.names("done")), 1)


if __name__ == "__main__":
    unittest.main()
