#!/usr/bin/env python3
"""Compile the real optional telemetry sink with a fake clock/counter caller."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FrameStats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="frame-stats-")
        root = Path(cls.tmp.name)
        caller = root / "caller.cpp"
        caller.write_text('''#include <cstdint>
extern "C" void sarpbc_frame_stats_tick(uint64_t, unsigned);
int main() {
    sarpbc_frame_stats_tick(1000, 1);
    sarpbc_frame_stats_tick(1500, 100);
    sarpbc_frame_stats_tick(2000, 61);
    sarpbc_frame_stats_tick(3000, 61);
}
''')
        cls.binary = root / "fixture"
        subprocess.run([os.environ.get("CXX", "c++"), "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        str(caller), str(ROOT / "src/overrides/frame_stats.cpp"),
                        "-o", str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_fixture(self, value):
        env = dict(os.environ)
        env.pop("SARPBC_FRAME_STATS", None)
        if value is not None:
            env["SARPBC_FRAME_STATS"] = value
        return subprocess.run([str(self.binary)], env=env, capture_output=True,
                              text=True, check=True).stderr

    def test_enabled_counter_and_zero_progress(self):
        self.assertEqual(self.run_fixture("1").splitlines(), [
            "[frame-stats] clock_ms=1000 guest_frames=1",
            "[frame-stats] clock_ms=2000 guest_frames=61",
            "[frame-stats] clock_ms=3000 guest_frames=61",
        ])

    def test_disabled_is_silent(self):
        for value in (None, "", "0"):
            with self.subTest(value=value):
                self.assertEqual(self.run_fixture(value), "")


if __name__ == "__main__":
    unittest.main()
