#!/usr/bin/env python3
"""Deterministic runtime-counter tests, without game files or perf permissions."""
import unittest

import spu_profile as profile


class RuntimeMetrics(unittest.TestCase):
    def test_counts_guest_frames_not_backend_dump_chatter(self):
        text = """dumped 9999 backend frames
[frame-stats] clock_ms=9000 guest_frames=100
[frame-stats] clock_ms=10000 guest_frames=160
[frame-stats] clock_ms=11000 guest_frames=220
"""
        result = profile.runtime_metrics(text, 9000, 11000)
        self.assertEqual(result["frame_fps"], 60)
        self.assertEqual(result["frame_seconds"], 2)
        self.assertEqual(result["frame_min_fps"], 60)

    def test_excludes_intro_outside_measurement_window(self):
        lines = [f"[frame-stats] clock_ms={t} guest_frames={n}"
                 for t, n in [(1000, 1000), (9000, 2000), (10000, 2001), (11000, 2002)]]
        result = profile.runtime_metrics("\n".join(lines), 9000, 11000)
        self.assertEqual(result["frame_fps"], 1)

    def test_stale_or_missing_telemetry_is_not_high_fps(self):
        text = "[frame-stats] clock_ms=1000 guest_frames=60\n"
        result = profile.runtime_metrics(text, 9000, 69000)
        self.assertIsNone(result["frame_fps"])
        self.assertIn("unavailable", result["frame_reason"])
        self.assertIsNone(profile.runtime_metrics("", 0, 1000)["frame_fps"])

    def test_zero_frames_and_stalls_are_visible(self):
        text = """[frame-stats] clock_ms=1000 guest_frames=100
[frame-stats] clock_ms=2000 guest_frames=100
[frame-stats] clock_ms=3000 guest_frames=220
"""
        result = profile.runtime_metrics(text, 1000, 3000)
        self.assertEqual(result["frame_fps"], 60)
        self.assertEqual(result["frame_min_fps"], 0)

    def test_counter_reset_is_rejected(self):
        text = """[frame-stats] clock_ms=1000 guest_frames=100
[frame-stats] clock_ms=2000 guest_frames=0
"""
        result = profile.runtime_metrics(text, 1000, 2000)
        self.assertIsNone(result["frame_fps"])
        self.assertIn("reset", result["frame_reason"])

    def test_mixer_rates_are_observed_windows_not_a_run_average(self):
        text = """[dma-range] 768000 B/s put, 0 B/s get
[ef-stats] flag=0x01372000 waits=90.5/s mean=6000us max=8000us
[dma-range] 1536000 B/s put, 0 B/s get
[ef-stats] flag=0x01329100 waits=999.0/s mean=0us max=0us
"""
        result = profile.runtime_metrics(text, 0, 1000)
        self.assertEqual(result["mixer_put_bps"], [768000, 1536000])
        self.assertEqual(result["mixer_waits"], [90.5])


if __name__ == "__main__":
    unittest.main()
