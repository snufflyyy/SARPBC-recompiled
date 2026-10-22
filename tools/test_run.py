#!/usr/bin/env python3
"""Test the real ./run.sh -> tools/run.sh chain without game data or a display."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RunLauncher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sarpbc-launch-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "checkout with spaces"
        (self.root / "tools").mkdir(parents=True)
        for name in ("run.sh", "tools/run.sh", "tools/overlay.sh"):
            shutil.copy2(ROOT / name, self.root / name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.bd = self.root / "versions/0109/build"
        self.make_build(self.bd)
        for name in ("versions/0109/game", "versions/0109/vfs", "game", "vfs"):
            (self.root / name).mkdir(parents=True)
        for name in ("versions/0109/game/EBOOT.elf", "game/EBOOT.elf"):
            (self.root / name).write_text("launcher fixture, not a guest executable\n")
        self.env = dict(os.environ)
        for key in ("BUILD_DIR", "GAME_DIR", "VFS_DIR", "PS3RECOMP_VK_WINDOW",
                    "PS3RECOMP_VK_GUEST_PROGRAMS", "PS3_TITLE", "SARPBC_CONFIG",
                    "SDL_VIDEODRIVER", "FAKE_EXIT"):
            self.env.pop(key, None)

    def make_build(self, directory, vulkan="ON"):
        directory.mkdir(parents=True, exist_ok=True)
        binary = directory / "sarpbc"
        binary.write_text(f'''#!{sys.executable}
import json, os, sys
keys = ("PS3RECOMP_VK_WINDOW", "PS3RECOMP_VK_GUEST_PROGRAMS", "PS3_TITLE", "SARPBC_CONFIG", "SDL_VIDEODRIVER")
print(json.dumps({{"argv": sys.argv[1:], "env": {{k: os.environ.get(k) for k in keys}}}}))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
''')
        binary.chmod(0o755)
        (directory / "CMakeCache.txt").write_text(f"PS3RECOMP_RSX_VULKAN:BOOL={vulkan}\n")

    def launch(self, *args, env=None):
        # Deliberately launch outside the checkout, as a desktop shortcut can.
        return subprocess.run([str(self.root / "run.sh"), *args], cwd=self.tmp.name,
                              env=self.env | (env or {}), capture_output=True, text=True)

    def data(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_desktop_defaults_and_empty_defaults(self):
        for value in (None, ""):
            overrides = {} if value is None else {"PS3RECOMP_VK_WINDOW": value,
                                                   "PS3RECOMP_VK_GUEST_PROGRAMS": value,
                                                   "PS3_TITLE": value, "SARPBC_CONFIG": value}
            with self.subTest(value=value):
                data = self.data(self.launch(env=overrides))
                self.assertEqual(data["argv"], [str(self.root / "versions/0109/game/EBOOT.elf"),
                                                str(self.root / "versions/0109/vfs")])
                self.assertEqual(data["env"]["PS3RECOMP_VK_WINDOW"], "1")
                self.assertEqual(data["env"]["PS3RECOMP_VK_GUEST_PROGRAMS"], "1")
                self.assertEqual(data["env"]["PS3_TITLE"], "SARPBC")
                self.assertEqual(data["env"]["SARPBC_CONFIG"], str(self.root / "config.toml"))

    def test_base_version(self):
        self.make_build(self.root / "build")
        data = self.data(self.launch("--version", "0102"))
        self.assertEqual(data["argv"], [str(self.root / "game/EBOOT.elf"), str(self.root / "vfs")])
        self.assertEqual(data["env"]["PS3RECOMP_VK_WINDOW"], "1")

    def test_explicit_headless_and_custom_values(self):
        data = self.data(self.launch(env={"PS3RECOMP_VK_WINDOW": "0",
                                         "PS3RECOMP_VK_GUEST_PROGRAMS": "0",
                                         "PS3_TITLE": "Custom title", "SARPBC_CONFIG": "/custom/config"}))
        self.assertEqual(data["env"]["PS3RECOMP_VK_WINDOW"], "0")
        self.assertEqual(data["env"]["PS3RECOMP_VK_GUEST_PROGRAMS"], "0")
        self.assertEqual(data["env"]["PS3_TITLE"], "Custom title")
        self.assertEqual(data["env"]["SARPBC_CONFIG"], "/custom/config")

    def test_overrides_arguments_and_exit_status(self):
        bd = self.root / "custom build"
        self.make_build(bd)
        env = {"BUILD_DIR": str(bd), "GAME_DIR": str(self.root / "game"),
               "VFS_DIR": str(self.root / "vfs"), "FAKE_EXIT": "7"}
        result = self.launch("--", "--example", "value with spaces", "", env=env)
        self.assertEqual(result.returncode, 7, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["argv"], [str(self.root / "game/EBOOT.elf"), str(self.root / "vfs"),
                                        "--example", "value with spaces", ""])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux renderer check")
    def test_null_build_requires_explicit_headless(self):
        for value in ("OFF", "false", "0", ""):
            with self.subTest(value=value):
                (self.bd / "CMakeCache.txt").write_text(f"PS3RECOMP_RSX_VULKAN:BOOL={value}\n")
                result = self.launch()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("PS3RECOMP_RSX_VULKAN=ON", result.stderr)
                self.assertEqual(result.stdout, "")
                self.data(self.launch(env={"PS3RECOMP_VK_WINDOW": "0"}))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux SDL video check")
    def test_headless_sdl_driver_requires_explicit_headless(self):
        for driver in ("dummy", "offscreen"):
            with self.subTest(driver=driver):
                result = self.launch(env={"SDL_VIDEODRIVER": driver})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("SDL_VIDEODRIVER", result.stderr)
                self.assertEqual(result.stdout, "")
                self.data(self.launch(env={"SDL_VIDEODRIVER": driver, "PS3RECOMP_VK_WINDOW": "0"}))

    def test_custom_binary_without_cmake_cache_is_allowed(self):
        (self.bd / "CMakeCache.txt").unlink()
        self.data(self.launch())

    def test_build_option_runs_builder_for_selected_version(self):
        self.make_build(self.root / "build")
        trace = self.root / "build-call.json"
        builder = self.root / "build.sh"
        builder.write_text(f'''#!{sys.executable}
import json, sys
from pathlib import Path
Path({str(trace)!r}).write_text(json.dumps(sys.argv[1:]))
''')
        builder.chmod(0o755)
        self.data(self.launch("--version", "0102", "--build"))
        self.assertEqual(json.loads(trace.read_text()), ["--version", "0102"])

    def test_help_documents_window_and_headless(self):
        result = self.launch("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("window", result.stdout)
        self.assertIn("PS3RECOMP_VK_WINDOW=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
