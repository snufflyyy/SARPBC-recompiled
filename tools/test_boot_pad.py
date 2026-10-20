#!/usr/bin/env python3
"""Exercise boot_check's production --pad parser and writer without a game."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SOURCE = Path(__file__).with_name('boot_check.sh').read_text()
PARSER = SOURCE.split("PAD_EVENTS=$(python3 - \"$PAD\" <<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
DRIVER = SOURCE.split('# The pad driver:', 1)[1].split('\nEND=', 1)[0]
# The first line after this marker completes a two-line shell comment.
DRIVER = '# The pad driver:' + DRIVER


class BootPadTests(unittest.TestCase):
    def parse(self, spec, ok=True):
        result = subprocess.run([sys.executable, '-', spec], input=PARSER,
                                capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('boot_check:', result.stderr)

    def test_press_defaults(self):
        self.assertEqual(self.parse('cross@40'), '40 0x4000 3 cross\n')

    def test_combinations_and_sorted_repetition(self):
        self.assertEqual(self.parse('start+cross:2@4,circle@1*2/0.5'),
                         '1 0x2000 3 circle\n1.5 0x2000 3 circle\n4 0x4008 2 start+cross\n')

    def test_case_and_decimal_seconds(self):
        self.assertEqual(self.parse(' L2+R2@.25 '), '0.25 0x0300 3 l2+r2\n')

    def test_invalid_specs_fail_before_starting_a_game(self):
        for spec in ('unknown@1', 'cross@1..2', 'cross@-1', 'cross:0@1',
                     'cross@1*0/2', 'cross@1*2/0', ' , ', 'cross@1*1000000000/1'):
            with self.subTest(spec=spec):
                self.parse(spec, ok=False)

    def test_driver_writes_mask_poll_count_and_log(self):
        events = self.parse('cross:2@0,up@0.03')
        with tempfile.TemporaryDirectory(prefix='sarpbc-pad-test-') as name:
            root = Path(name)
            pad = root / 'pad.txt'
            # Shell command substitution strips the parser's final newline.
            env = dict(os.environ, RUN=name, PAD_FILE=str(pad), PAD_EVENTS=events.rstrip('\n'),
                       T0=str(time.time() - 1))
            result = subprocess.run(['bash', '-c', DRIVER + '\nwait "$PPID_PAD"\n'],
                                    env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(pad.read_text(), '0x0010 3\n')
            self.assertEqual((root / 'pad.log').read_text(),
                             '0 cross 0x4000 2\n0.03 up 0x0010 3\n')


if __name__ == '__main__':
    unittest.main()
