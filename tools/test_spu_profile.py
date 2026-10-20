#!/usr/bin/env python3
"""Regression for /proc sampling when perf is present but cannot record.

Uses a fake boot and recorder, not a game or real performance counters.
Run: python3 tools/test_spu_profile.py
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def executable(path, text):
    path.write_text(text)
    path.chmod(0o755)


class PerfFailureWindow(unittest.TestCase):
    def test_failed_recorder_preserves_sample_deadline(self):
        for delay in (0, 2):
            with self.subTest(failure_delay=delay), tempfile.TemporaryDirectory(
                prefix="spu-profile-fixture-"
            ) as tmp:
                root = Path(tmp)
                tools = root / "tools"
                tools.mkdir()
                bin_dir = root / "bin"
                bin_dir.mkdir()
                shutil.copyfile(ROOT / "tools/spu_profile.sh", tools / "spu_profile.sh")
                executable(tools / "boot_check.sh", """#!/usr/bin/env bash
printf 'boot_check: game pid %s, fixture\n' "$$" >&2
date +%s.%N
sleep "$1"
echo 'boot_check fixture finished'
""")
                executable(bin_dir / "perf", """#!/usr/bin/env bash
sleep "$FAKE_PERF_DELAY"
echo 'fixture: perf_event_open denied' >&2
exit 1
""")
                # Keep the preflight branch independent of the test host.
                executable(bin_dir / "cat", """#!/usr/bin/env bash
if [ "$1" = /proc/sys/kernel/perf_event_paranoid ]; then
    echo 2
else
    exec /bin/cat "$@"
fi
""")
                (tools / "spu_profile.py").write_text("""import json, pathlib, sys, time
if sys.argv[1] == 'snap':
    pathlib.Path(sys.argv[3]).write_text(json.dumps({'t': time.time()}))
else:
    args = sys.argv
    work = pathlib.Path(args[args.index('--work') + 1])
    start = json.loads((work / 'proc0.json').read_text())['t']
    end = json.loads((work / 'proc1.json').read_text())['t']
    (work.parent / 'fixture-result.json').write_text(json.dumps({
        'elapsed': end - start,
        'perf': args[args.index('--perf') + 1],
        'why': args[args.index('--why') + 1],
    }))
""")
                env = dict(os.environ, SPU_PROFILE_LOCKED="1", FAKE_PERF_DELAY=str(delay))
                env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
                warmup = 2 if delay else 0
                result = subprocess.run(
                    ["bash", str(tools / "spu_profile.sh"), "8", "--warmup", str(warmup)],
                    env=env, capture_output=True, text=True, timeout=17,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads((root / "analysis/fixture-result.json").read_text())
                # REC=8-3=5. A fixed sleep after partial failure would take 7s.
                self.assertGreaterEqual(data["elapsed"], 4.8)
                self.assertLess(data["elapsed"], 6.5)
                self.assertEqual(data["perf"], "0")
                self.assertIn("perf record failed", data["why"])
                self.assertIn("fixture: perf_event_open denied", result.stderr)
                work = next((root / "analysis").glob("*.d"))
                started = float((work / "boot_check.out").read_text().splitlines()[0])
                sample_start = json.loads((work / "proc0.json").read_text())["t"]
                self.assertGreaterEqual(sample_start - started, warmup - 0.1)


if __name__ == "__main__":
    unittest.main()
