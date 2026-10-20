#!/usr/bin/env python3
"""src/overrides/input_config.cpp: [input] upper-case keys become environment variables,
but only the supported prefixes; the environment still wins. Needs a C++ compiler."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <cstdio>
#include <initializer_list>
#include <cstdlib>
extern "C" void sarpbc_input_config(void);
int main() {
    sarpbc_input_config();
    for (const char* k : {"KEY_CROSS", "PAD_TRACE", "PATH_EVIL", "LD_PRELOAD", "KEY_L1", "SARPBC_KBM_LOG"}) {
        const char* v = getenv(k);
        printf("%s=%s\n", k, v ? v : "<unset>");
    }
}
'''


@unittest.skipUnless(shutil.which("clang++") or shutil.which("g++"), "no C++ compiler")
class InputConfig(unittest.TestCase):
    def test_whitelist_and_precedence(self):
        cxx = shutil.which("clang++") or shutil.which("g++")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "h.cpp").write_text(HARNESS)
            (d / "config.toml").write_text(
                '[input]\nKEY_CROSS = "Z"\nPAD_TRACE = true\nLD_PRELOAD = "/tmp/x.so"\n'
                'PATH_EVIL = "1"\nKEY_L1 = "Q"\nSARPBC_KBM_LOG = 1\n[graphics]\nKEY_L1 = "NO"\n')
            subprocess.run([cxx, "-std=c++17", "-o", str(d / "h"), str(d / "h.cpp"),
                            str(ROOT / "src/overrides/input_config.cpp")], check=True)
            env = {k: v for k, v in os.environ.items() if k not in ("LD_PRELOAD", "KEY_CROSS")}
            env.update(SARPBC_CONFIG=str(d / "config.toml"), KEY_L1="FROM_ENV")
            out = subprocess.run([str(d / "h")], env=env, capture_output=True, text=True, check=True)
            got = dict(l.split("=", 1) for l in out.stdout.splitlines() if "=" in l and not l.startswith("["))
            self.assertEqual(got["KEY_CROSS"], "Z")
            self.assertEqual(got["PAD_TRACE"], "1")
            self.assertEqual(got["KEY_L1"], "FROM_ENV")
            self.assertEqual(got["SARPBC_KBM_LOG"], "1")
            self.assertEqual(got["LD_PRELOAD"], "<unset>")
            self.assertEqual(got["PATH_EVIL"], "<unset>")
            self.assertIn("ignoring unsupported key LD_PRELOAD", out.stderr)


if __name__ == "__main__":
    unittest.main()
