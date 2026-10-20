#!/usr/bin/env python3
"""Source-only tests of tools/apply_patches.sh and build.sh in throwaway git repositories.

A fake "ps3recomp" upstream with two commits stands in for the submodule and a fake
`cmake` records its calls, so no game data, network or compiler is needed. Covers
docs/project-audit.md A04: dirty refusal leaves the checkout unchanged, a wrong patch
history with the same commit count is replaced, a failing patch changes nothing, and
concurrent builds of one checkout never overlap.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parent
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
           GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL="/dev/null")


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                          text=True, env=ENV).stdout.strip()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.sub = self.root / "external" / "ps3recomp"
        self.sub.mkdir(parents=True)
        git(self.sub, "init", "-q", "-b", "main")
        (self.sub / "a.txt").write_text("one\n")
        git(self.sub, "add", "-A")
        git(self.sub, "commit", "-qm", "pin")
        self.pin = git(self.sub, "rev-parse", "HEAD")
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "update-index", "--add", "--cacheinfo", f"160000,{self.pin},external/ps3recomp")
        (self.root / "tools").mkdir()
        for name in ("apply_patches.sh", "task.sh"):
            shutil.copy(TOOLS / name, self.root / "tools" / name)
        shutil.copy(TOOLS.parent / "build.sh", self.root / "build.sh")
        (self.root / "patches" / "ps3recomp").mkdir(parents=True)
        (self.root / "src" / "recomp").mkdir(parents=True)
        (self.root / "src" / "spu_gen").mkdir(parents=True)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "root")
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.tmp.name) / "cmake.log"
        fake = self.bin / "cmake"
        fake.write_text(f'''#!/usr/bin/env bash
echo "start $$ $(date +%s.%N)" >> {self.log}
sleep 0.2
if [ "$1" = -S ]; then mkdir -p "$4" && touch "$4/build.ninja"; fi
echo "end $$ $(date +%s.%N)" >> {self.log}
''')
        fake.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def make_patch(self, name, filename, content):
        """Write patches/ps3recomp/<name> adding/replacing filename, made against the pin."""
        work = Path(self.tmp.name) / ("w_" + name)
        subprocess.run(["git", "clone", "-q", str(self.sub), str(work)], check=True, env=ENV)
        git(work, "checkout", "-q", self.pin)
        (work / filename).write_text(content)
        git(work, "add", "-A")
        git(work, "commit", "-qm", f"patch {name}")
        out = git(work, "format-patch", "-1", "--stdout")
        (self.root / "patches" / "ps3recomp" / name).write_text(out + "\n")

    def apply(self, *args, env=None):
        return subprocess.run([str(self.root / "tools" / "apply_patches.sh"), *args],
                              capture_output=True, text=True, env=dict(ENV, **(env or {})))

    def build(self, *args):
        env = dict(ENV, PATH=f"{self.bin}:{os.environ['PATH']}")
        return subprocess.run([str(self.root / "build.sh"), "--version", "0102", *args],
                              capture_output=True, text=True, env=env)

    def head(self):
        return git(self.sub, "rev-parse", "HEAD")


class ApplyPatches(Fixture):
    def test_applies_stack_and_ensure_is_a_noop(self):
        self.make_patch("0001-a.patch", "b.txt", "b\n")
        r = self.apply()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.sub / "b.txt").read_text(), "b\n")
        before = self.head()
        mtime = (self.sub / "b.txt").stat().st_mtime_ns
        self.assertEqual(self.apply("--ensure").returncode, 0)
        self.assertEqual(self.head(), before)
        self.assertEqual((self.sub / "b.txt").stat().st_mtime_ns, mtime)

    def test_unstamped_correct_checkout_is_trusted_without_rewrite(self):
        self.make_patch("0001-a.patch", "b.txt", "b\n")
        self.apply()
        stamp = Path(git(self.sub, "rev-parse", "--absolute-git-dir")) / "sarpbc-patches.stamp"
        stamp.unlink()
        mtime = (self.sub / "b.txt").stat().st_mtime_ns
        self.assertEqual(self.apply("--ensure").returncode, 0)
        self.assertTrue(stamp.exists())
        self.assertEqual((self.sub / "b.txt").stat().st_mtime_ns, mtime)

    def test_wrong_history_with_same_commit_count_is_replaced(self):
        self.make_patch("0001-a.patch", "b.txt", "right\n")
        self.apply()
        # Same number of commits on top of the pin, different content, no stamp.
        git(self.sub, "reset", "-q", "--hard", self.pin)
        (self.sub / "b.txt").write_text("wrong\n")
        git(self.sub, "add", "-A")
        git(self.sub, "commit", "-qm", "wrong")
        git(self.sub, "checkout", "-q", "-B", "sarpbc-patches")
        stamp = Path(git(self.sub, "rev-parse", "--absolute-git-dir")) / "sarpbc-patches.stamp"
        stamp.unlink(missing_ok=True)
        r = self.apply("--ensure")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.sub / "b.txt").read_text(), "right\n")
        self.assertIn("sarpbc-backup", r.stderr)

    def test_dirty_checkout_is_refused_and_unchanged(self):
        self.make_patch("0001-a.patch", "b.txt", "b\n")
        self.apply()
        self.make_patch("0002-c.patch", "c.txt", "c\n")
        (self.sub / "a.txt").write_text("edited\n")
        before = self.head()
        for args in ((), ("--ensure",)):
            r = self.apply(*args)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("uncommitted", r.stderr)
            self.assertEqual(self.head(), before)
            self.assertEqual((self.sub / "a.txt").read_text(), "edited\n")
            self.assertFalse((self.sub / "c.txt").exists())

    def test_dirty_override_builds_as_is(self):
        self.make_patch("0001-a.patch", "b.txt", "b\n")
        self.apply()
        self.make_patch("0002-c.patch", "c.txt", "c\n")
        (self.sub / "a.txt").write_text("edited\n")
        r = self.apply("--ensure", env={"SARPBC_ALLOW_DIRTY_RUNTIME": "1"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("warning", r.stderr)
        self.assertEqual((self.sub / "a.txt").read_text(), "edited\n")

    def test_failing_patch_leaves_checkout_untouched(self):
        self.make_patch("0001-a.patch", "b.txt", "b\n")
        self.apply()
        before = self.head()
        (self.root / "patches" / "ps3recomp" / "0002-bad.patch").write_text("not a patch\n")
        r = self.apply()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.head(), before)
        self.assertEqual(git(self.sub, "status", "--porcelain"), "")
        self.assertEqual(git(self.sub, "branch", "--show-current"), "sarpbc-patches")


class BuildSh(Fixture):
    def test_build_runs_and_dirty_runtime_fails_closed(self):
        self.make_patch("0001-a.patch", "b.txt", "b\n")
        r = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.sub / "b.txt").exists())
        (self.sub / "a.txt").write_text("edited\n")
        self.log.unlink()
        r = self.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.log.exists(), "must not compile an unexpected runtime")

    def test_concurrent_builds_do_not_overlap(self):
        self.make_patch("0001-a.patch", "b.txt", "b\n")
        with ThreadPoolExecutor(4) as ex:
            results = list(ex.map(lambda _: self.build("--clean"), range(4)))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results])
        events = [l.split() for l in self.log.read_text().splitlines()]
        self.assertEqual(len(events), 16)   # configure + compile per build
        # Strictly alternating start/end means no two steps ran at once, so --clean,
        # configure and compile of one checkout are one transaction.
        self.assertEqual([e[0] for e in events], ["start", "end"] * 8)


if __name__ == "__main__":
    unittest.main()
