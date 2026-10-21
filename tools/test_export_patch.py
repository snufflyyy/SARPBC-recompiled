#!/usr/bin/env python3
"""tools/export_patch.sh in a scratch superproject with a scratch submodule."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('export_patch.sh')
README = """# patches
| File | What | Upstream |
|---|---|---|
| `0001-first.patch` | first | generic |

Making a new one: see above.
"""


def git(cwd, *args):
    return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


class ExportPatchTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='sarpbc-export-test-')
        self.root = Path(self._tmp.name)
        sub = self.root / 'external' / 'ps3recomp'
        sub.mkdir(parents=True)
        git(sub, 'init', '-q', '-b', 'main')
        (sub / 'a.txt').write_text('base\n')
        git(sub, 'add', '.')
        git(sub, 'commit', '-qm', 'pin')
        self.pin = git(sub, 'rev-parse', 'HEAD').strip()
        git(sub, 'checkout', '-qb', 'sarpbc-patches')
        (sub / 'a.txt').write_text('one\n')
        git(sub, 'commit', '-qam', 'first')
        out = self.root / 'patches' / 'ps3recomp'
        out.mkdir(parents=True)
        (out / '0001-first.patch').write_text(git(sub, 'format-patch', '-1', '--stdout'))
        (out / 'README.md').write_text(README)
        (self.root / 'tools').mkdir()
        shutil.copy(SCRIPT, self.root / 'tools' / 'export_patch.sh')
        git(self.root, 'init', '-q', '-b', 'main')
        git(self.root, 'update-index', '--add', '--cacheinfo', f'160000,{self.pin},external/ps3recomp')
        git(self.root, 'add', 'patches', 'tools')
        git(self.root, 'commit', '-qm', 'root')
        self.sub = sub

    def tearDown(self):
        self._tmp.cleanup()

    def run_export(self, *args):
        return subprocess.run([str(self.root / 'tools' / 'export_patch.sh'), *args],
                              capture_output=True, text=True)

    def commit(self, text):
        (self.sub / 'a.txt').write_text(text)
        git(self.sub, 'commit', '-qam', 'second: ' + text.strip())

    def test_exports_next_number_and_readme_row(self):
        self.commit('two\n')
        r = self.run_export('second-change', 'T1: why', 'generic')
        self.assertEqual(r.returncode, 0, r.stderr)
        patch = self.root / 'patches/ps3recomp/0002-second-change.patch'
        self.assertIn('second: two', patch.read_text())
        rows = (self.root / 'patches/ps3recomp/README.md').read_text().split('\n')
        i = rows.index('| `0001-first.patch` | first | generic |')
        self.assertEqual(rows[i + 1], '| `0002-second-change.patch` | T1: why | generic |')

    def test_refuses_dirty_checkout_and_wrong_count(self):
        self.commit('two\n')
        (self.sub / 'a.txt').write_text('dirty\n')
        self.assertEqual(self.run_export('x', 'd').returncode, 1)
        git(self.sub, 'checkout', 'a.txt')
        r = self.run_export('x', 'd', '--count', '2')
        self.assertEqual(r.returncode, 1)
        self.assertIn('expected exactly 2 new', r.stderr)

    def test_refuses_nothing_new_and_bad_slug(self):
        self.assertEqual(self.run_export('x', 'd').returncode, 1)
        self.commit('two\n')
        self.assertEqual(self.run_export('Bad_Slug', 'd').returncode, 2)
        self.assertEqual(self.run_export('x', 'a | b').returncode, 2)


if __name__ == '__main__':
    unittest.main()
