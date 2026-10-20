#!/usr/bin/env python3
"""Check the title's SPURS completion default without running game code."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SpursConfigTests(unittest.TestCase):
    def test_default_and_environment_override(self):
        cxx = os.environ.get('CXX', 'clang++')
        if not shutil.which(cxx):
            self.skipTest(f'{cxx} unavailable')
        with tempfile.TemporaryDirectory(prefix='sarpbc-spurs-config-') as name:
            root = Path(name)
            src = root / 'main.cpp'
            src.write_text('#include <cstdlib>\n#include <cstdio>\n'
                           'int main() { const char* s=getenv("SPURS_JC_DONE_EVENTS"); '
                           'if (!s) return 1; puts(s); }\n')
            exe = root / 'config'
            subprocess.run([cxx, '-std=c++20', str(src),
                            str(ROOT / 'src/overrides/spurs_config.cpp'), '-o', str(exe)], check=True)
            for supplied, expected in ((None, '0'), ('1', '1'), ('0', '0')):
                with self.subTest(supplied=supplied):
                    env = dict(os.environ)
                    env.pop('SPURS_JC_DONE_EVENTS', None)
                    if supplied is not None:
                        env['SPURS_JC_DONE_EVENTS'] = supplied
                    result = subprocess.run([str(exe)], env=env, capture_output=True,
                                            text=True, timeout=5)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), expected)


if __name__ == '__main__':
    unittest.main()
