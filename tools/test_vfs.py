#!/usr/bin/env python3
"""Exercise the real runner's VFS setup with synthetic paths and mocked SFO I/O."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <string>

/* Refuse the old fixed-buffer call instead of deliberately overflowing it.
 * Successful canonicalization still comes from the real host filesystem. */
static char* checked_realpath(const char* path, char* out) {
    char* resolved = realpath(path, nullptr);
    if (!resolved || !out) return resolved;
    if (strlen(resolved) >= 1024) { free(resolved); errno = ENAMETOOLONG; return nullptr; }
    strcpy(out, resolved); free(resolved); return out;
}
static int checked_setenv(const char* name, const char* value, int overwrite) {
    if (getenv("TEST_VFS_ENV_FAILURE")) { errno = ENOMEM; return -1; }
    return setenv(name, value, overwrite);
}
#define realpath checked_realpath
#define setenv checked_setenv
#define main sarpbc_runner_main
#include "main.cpp"
#undef main
#undef realpath
#undef setenv

static std::string seen_sfo;
extern "C" {
const char* ppu_vfs_root;
void cellGame_init_from_paramsfo(const char* path) { seen_sfo = path; }
}
int main(int argc, char** argv) {
    if (argc != 3) return 2;
    const bool ok = setup_vfs(argv[1]);
    if (!strcmp(argv[2], "missing")) return ok || !seen_sfo.empty() ? 1 : 0;
    if (!ok) return 1;
    char* resolved = realpath(argv[1], nullptr);
    if (!resolved) return 3;
    const std::string hdd0 = std::string(resolved) + "/dev_hdd0";
    const std::string game = hdd0 + "/game/NPUB30035";
    free(resolved);
    const char* expected = getenv("TEST_VFS_OVERRIDE");
    if (!expected) expected = hdd0.c_str();
    if (!ppu_vfs_root || expected != std::string(ppu_vfs_root)) return 4;
    if (game != getenv("PS3_USRDIR_BASE")) return 5;
    if (game + "/PARAM.SFO" != seen_sfo) return 6;
    if (strcmp(getenv("PS3_BOOT_PATH"), "/dev_hdd0/game/NPUB30035/USRDIR/EBOOT.BIN")) return 7;
    return 0;
}
'''


class VfsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name != 'posix':
            raise unittest.SkipTest('fixture currently uses POSIX linker dead-section collection')
        compiler = os.environ.get('CXX', 'clang++')
        if not shutil.which(compiler):
            raise unittest.SkipTest(f'{compiler} unavailable')
        cls.tmp = tempfile.TemporaryDirectory(prefix='sarpbc-vfs-test-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.path = Path(cls.tmp.name)
        (cls.path / 'ppu_recomp.h').write_text('#include <stdint.h>\nstruct ppu_context { uint64_t gpr[32]; };\n')
        (cls.path / 'harness.cpp').write_text(HARNESS)
        cls.exe = cls.path / 'test'
        subprocess.run([compiler, '-std=c++20', '-O2', '-ffunction-sections', '-fdata-sections',
                        '-I' + str(cls.path), '-I' + str(ROOT / 'src'),
                        '-I' + str(ROOT / 'external/ps3recomp/runtime/platform'),
                        str(cls.path / 'harness.cpp'), '-Wl,--gc-sections', '-pthread',
                        '-o', str(cls.exe)], check=True)
        cls.long = cls.path / 'vfs'
        for i in range(9):
            cls.long = cls.long / (str(i) + 'a' * 120)
        cls.long.mkdir(parents=True)

    def run_case(self, path, mode='valid', override=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('PS3_', 'TEST_VFS_'))}
        if override is not None:
            env['PS3_VFS_ROOT'] = env['TEST_VFS_OVERRIDE'] = override
        if mode == 'env-failure':
            env['TEST_VFS_ENV_FAILURE'] = '1'
            mode = 'missing'
        result = subprocess.run([str(self.exe), str(path), mode], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_long_existing_root(self):
        self.assertGreater(len(str(self.long)), 1024)
        self.run_case(self.long)

    def test_short_root(self):
        self.run_case(self.path)

    def test_missing_root_fails(self):
        self.run_case(self.path / 'missing', 'missing')

    def test_environment_failure_stops_before_sfo_load(self):
        self.run_case(self.path, mode='env-failure')

    def test_environment_root_is_not_truncated(self):
        self.run_case(self.path, override=str(self.long) + '/dev_hdd0')


if __name__ == '__main__':
    unittest.main()
