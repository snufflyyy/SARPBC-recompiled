#!/usr/bin/env python3
"""Regression for tools/audio_wav_report.py on synthetic captures (no game, no audio device).

Run: python3 tools/test_audio_wav_report.py
"""
import array
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audio_wav_report as awr  # noqa: E402


def tone(blocks, start=0, amp=0.3, shift=0):
    out = array.array("f")
    for n in range(start * awr.BLOCK + shift, (start + blocks) * awr.BLOCK + shift):
        v = amp * math.sin(2 * math.pi * 440 * n / awr.RATE)
        out.extend((v, v))
    return out


def silence(blocks):
    return array.array("f", [0.0] * (blocks * awr.BLOCK * 2))


class Report(unittest.TestCase):
    def test_continuous_tone_is_clean(self):
        r = awr.analyse(tone(400))
        self.assertEqual((r["silent_blocks"], r["gaps"], r["clicks"]), (0, 0, 0))

    def test_leading_silence_is_not_a_gap(self):
        r = awr.analyse(silence(50) + tone(200, start=50))
        self.assertEqual((r["silent_blocks"], r["gaps"], r["first_sound_block"]), (0, 0, 50))

    def test_alternating_blocks_are_gaps(self):
        # what the crackle looked like: a block of sound, a block of silence, ...
        a = array.array("f")
        for b in range(0, 200, 2):
            a += tone(1, start=b)
            a += silence(1)
        r = awr.analyse(a)
        self.assertEqual(r["silent_blocks"], 100)
        self.assertEqual(r["gaps"], 100)

    def test_dropped_block_leaves_a_click_at_the_edge(self):
        a = tone(100)
        a += tone(100, start=100, shift=27)   # the stream skipped 27 frames: a quarter of a 440 Hz cycle
        r = awr.analyse(a)
        self.assertEqual(r["silent_blocks"], 0)
        self.assertGreaterEqual(r["clicks"], 1)

    def test_window_and_cli_exit_status(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.f32"
            p.write_bytes((tone(300) + silence(10) + tone(300, start=310)).tobytes())
            self.assertEqual(awr.main([str(p), "--max-gaps", "1"]), 0)
            self.assertEqual(awr.main([str(p), "--max-gaps", "0"]), 1)
            self.assertEqual(awr.main([str(p), "--from", "0", "--to", "1", "--max-gaps", "0", "--max-clicks", "0"]), 0)


if __name__ == "__main__":
    unittest.main()
