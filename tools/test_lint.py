#!/usr/bin/env python3
"""Source-only tests of tools/lint.py against throwaway repositories (no game data).

Covers docs/project-audit.md A03/A05/A11: the test manifest includes the nested suites,
timeouts and failures are results, tests never lose pre-existing edits, and the doc check
passes on a clean clone that lacks git-ignored generated/game paths.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

LINT = Path(__file__).resolve().parent / "lint.py"
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
           GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL="/dev/null")


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                          text=True, env=ENV).stdout


def load(root, sub):
    spec = importlib.util.spec_from_file_location("lint_under_test", LINT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ROOT, m.SUB = root, sub
    m.problems, m.notes, m.strict = [], [], False
    return m


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.sub = self.root / "external" / "ps3recomp"
        (self.root / "tools").mkdir(parents=True)
        (self.root / "docs").mkdir()
        self.sub.mkdir(parents=True)
        git(self.root, "init", "-q", "-b", "main")
        git(self.sub, "init", "-q", "-b", "main")
        (self.root / ".gitignore").write_text("/src/recomp/\n/game/\n/.cache/\n/external/\n")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, base, rel, text):
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p


class Docs(Base):
    def test_clean_clone_accepts_ignored_paths_but_not_missing_ones(self):
        self.write(self.root, "AGENTS.md", "index: [x](docs/x.md)\n")
        self.write(self.root, "docs/x.md", "lift output is `src/recomp/ppu.c`, boot data `game/EBOOT.elf`\n")
        lint = load(self.root, self.sub)
        lint.check_docs()
        self.assertEqual(lint.problems, [])
        self.write(self.root, "docs/x.md", "run `tools/missing.sh`\n")
        lint = load(self.root, self.sub)
        lint.check_docs()
        self.assertEqual(len(lint.problems), 1)
        self.assertIn("tools/missing.sh", lint.problems[0])

    def test_missing_submodule_is_a_note_not_a_failure(self):
        (self.sub / ".git").unlink() if (self.sub / ".git").is_file() else None
        import shutil
        shutil.rmtree(self.sub / ".git")
        self.write(self.root, "AGENTS.md", "index: [x](docs/x.md)\n")
        self.write(self.root, "docs/x.md", "see `libs/video/foo.c`\n")
        lint = load(self.root, self.sub)
        lint.check_docs()
        self.assertEqual(lint.problems, [])
        self.assertTrue(any("not checked out" in n for n in lint.notes))
        lint.strict = True
        lint.check_docs()
        self.assertTrue(any("--strict" in p for p in lint.problems))


class Manifest(Base):
    def test_nested_suites_are_included_and_missing_ones_reported(self):
        lint = load(self.root, self.sub)
        self.write(self.root, "tools/test_a.py", "")
        self.write(self.sub, "tools/test_b.py", "")
        for n in lint.NESTED_TESTS[:2]:
            self.write(self.sub, n, "")
        found = [str(t.relative_to(self.root)) for t, _ in lint.test_manifest()]
        self.assertIn("tools/test_a.py", found)
        self.assertIn("external/ps3recomp/tools/test_b.py", found)
        self.assertIn("external/ps3recomp/" + lint.NESTED_TESTS[0], found)
        self.assertEqual(len(lint.problems), 1)
        self.assertIn(lint.NESTED_TESTS[2], lint.problems[0])


class RunTests(Base):
    def run_lint_tests(self, **scripts):
        lint = load(self.root, self.sub)
        lint.NESTED_TESTS = ()
        lint.TEST_TIMEOUT = 1
        for name, body in scripts.items():
            self.write(self.root, f"tools/{name}.py", body)
        lint.run_tests()
        return lint

    def test_failure_and_timeout_are_results_with_saved_output(self):
        lint = self.run_lint_tests(
            test_fail="import sys; print('boom'); sys.exit(3)",
            test_slow="import time; print('started', flush=True); time.sleep(30)",
            test_ok="print('fine')",
            test_skip="print('OK (skipped=2)')")
        text = "\n".join(lint.problems)
        self.assertEqual(len(lint.problems), 2, text)
        self.assertIn("failed", text)
        self.assertIn("timeout", text)
        self.assertTrue(any("1 passed, 1 skipped, 1 failed, 1 timeout" in n for n in lint.notes), lint.notes)
        log = self.root / ".cache" / "lint-tests"
        self.assertIn("boom", (log / "tools__test_fail.py.log").read_text())

    def test_strict_makes_skips_problems(self):
        lint = load(self.root, self.sub)
        lint.NESTED_TESTS = ()
        lint.strict = True
        self.write(self.root, "tools/test_skip.py", "print('skipped=1')")
        lint.run_tests()
        self.assertEqual(len(lint.problems), 1)

    def test_pre_existing_edits_to_a_rewritten_fixture_survive(self):
        fixture = self.write(self.sub, "scratch/ppu_conformance.cpp", "committed\n")
        git(self.sub, "add", "-A")
        git(self.sub, "commit", "-qm", "base")
        fixture.write_text("my uncommitted edit\n")
        self.write(self.sub, "tools/test_rewrite.py",
                   "from pathlib import Path\nPath('scratch/ppu_conformance.cpp').write_text('generated\\n')\n")
        lint = load(self.root, self.sub)
        lint.NESTED_TESTS = ()
        lint.run_tests()
        self.assertEqual(lint.problems, [])
        self.assertEqual(fixture.read_text(), "my uncommitted edit\n")

    def test_unknown_files_changed_by_tests_are_reported_not_reverted(self):
        other = self.write(self.sub, "other.txt", "orig\n")
        git(self.sub, "add", "-A")
        git(self.sub, "commit", "-qm", "base")
        self.write(self.sub, "tools/test_touch.py", "from pathlib import Path\nPath('other.txt').write_text('changed\\n')\n")
        lint = load(self.root, self.sub)
        lint.NESTED_TESTS = ()
        lint.run_tests()
        self.assertEqual(other.read_text(), "changed\n")
        self.assertTrue(any("other.txt" in p for p in lint.problems), lint.problems)


if __name__ == "__main__":
    unittest.main()
