#!/usr/bin/env python3
"""Regression for /proc sampling when perf is present but cannot record, and for the
eu-stack fallback sampler (choice, sample window, parser and categories).

Uses a fake boot, recorder and eu-stack, not a game or real performance counters.
Run: python3 tools/test_spu_profile.py
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import spu_profile as profile  # noqa: E402


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
case "$*" in *probe.data*) [ "$FAKE_PROBE_OK" = 1 ] && exit 0 ;; esac
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
                # eu-stack only has to exist: the stub below stands in for the sampler
                executable(bin_dir / "eu-stack", "#!/bin/sh\nexit 2\n")
                (tools / "spu_profile.py").write_text("""import json, pathlib, sys, time
if sys.argv[1] == 'snap':
    pathlib.Path(sys.argv[3]).write_text(json.dumps({'t': time.time()}))
elif sys.argv[1] == 'stacks':
    args = sys.argv
    start = json.loads(pathlib.Path(args[args.index('--since') + 1]).read_text())['t']
    secs = float(args[args.index('--secs') + 1])
    time.sleep(max(0.0, start + secs - time.time()))
    pathlib.Path(args[3]).write_text(args[args.index('--sample') + 1])
else:
    args = sys.argv
    work = pathlib.Path(args[args.index('--work') + 1])
    start = json.loads((work / 'proc0.json').read_text())['t']
    end = json.loads((work / 'proc1.json').read_text())['t']
    (work.parent / 'fixture-result.json').write_text(json.dumps({
        'elapsed': end - start,
        'perf': args[args.index('--perf') + 1],
        'why': args[args.index('--why') + 1],
        'stacks': args[args.index('--stacks') + 1],
    }))
""")
                # delay 0: perf_event_open denied at the probe -> stacks from the start;
                # delay 2: probe passes, recording fails 2 s in -> stacks for the rest.
                env = dict(os.environ, SPU_PROFILE_LOCKED="1", FAKE_PERF_DELAY=str(delay),
                           FAKE_PROBE_OK="1" if delay else "0")
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
                self.assertEqual(data["stacks"], "1")
                if delay:
                    self.assertIn("perf record failed", data["why"])
                    self.assertIn("fixture: perf_event_open denied", result.stderr)
                else:
                    self.assertIn("perf cannot record here", data["why"])
                    self.assertIn("using eu-stack", result.stderr)
                work = next((root / "analysis").glob("*.d"))
                started = float((work / "boot_check.out").read_text().splitlines()[0])
                sample_start = json.loads((work / "proc0.json").read_text())["t"]
                self.assertGreaterEqual(sample_start - started, warmup - 0.1)



CAPTURE = """\
@@ capture t=100.000 dur=0.020 rc=1 running=11
TID 11:
#0  0x000055000000a000 spu_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa_spu_func_00001230 - /x/sarpbc
#1  0x000055000000a100 spu_drain_call - /x/sarpbc
@@ capture t=100.020 dur=0.030 rc=1 running=12
TID 12:
#0  0x000055000000b000 mfc_do_transfer - /x/sarpbc
#1  0x000055000000b100 spu_ovl_msdsp_37000_spu_func_000373A0 - /x/sarpbc
@@ capture t=100.050 dur=0.020 rc=1 running=13
TID 13:
#0  0x000055000000c000 func_00112233(ppu_context*) - /x/sarpbc
#1  0x000055000000c100 func_00445566(ppu_context*) - /x/sarpbc
@@ capture t=100.070 dur=0.020 rc=1 running=14
TID 14:
#0  0x00007f0000000003 - /usr/lib/x86_64-linux-gnu/libc.so.6
#1  0x00007f0000000004 sched_yield - /usr/lib/x86_64-linux-gnu/libc.so.6
@@ capture t=100.090 dur=0.020 rc=1 running=15
TID 15:
#0  0x000055000000d000 rsx_dispatch_method - /x/sarpbc
@@ capture t=100.110 dur=0.020 rc=1 running=16
TID 16:
#0  0x00007f0000000001 - /usr/lib/x86_64-linux-gnu/libc.so.6
#1  0x00007f0000000002 pthread_cond_timedwait - /usr/lib/x86_64-linux-gnu/libc.so.6
#2  0x000055000000e000 func_00778899(ppu_context*) - /x/sarpbc
@@ capture t=101.000 dur=0.300 rc=1 running=13
TID 13:
#0  0x000055000000c000 func_00112233(ppu_context*) - /x/sarpbc
TID 15:
#0  0x000055000000d000 rsx_dispatch_method - /x/sarpbc
"""


class StackSamples(unittest.TestCase):
    def test_only_running_threads_count_and_categories(self):
        with tempfile.TemporaryDirectory(prefix="spu-profile-stacks-") as tmp:
            path = Path(tmp) / "stacks.txt"
            path.write_text(CAPTURE)
            samples, meta = profile.parse_stacks(str(path))
        self.assertEqual(meta["captures"], 7)
        self.assertAlmostEqual(meta["stopped"], 0.43)
        self.assertAlmostEqual(meta["last"] - meta["first"], 1.3)
        # tid 15 is in the last capture's output but was not the thread running then
        self.assertEqual([t for t, _ in samples], ["11", "12", "13", "14", "15", "16", "13"])
        cats = [profile.classify(*profile.leaf(chain)) for _, chain in samples]
        self.assertEqual(cats, [("spu_lifted", "aaaaaaaaaaaa"), ("spu_runtime", None),
                                ("ppu_lifted", None), ("lock_wait", None),
                                ("gcm_vulkan", None), ("lock_wait", None), ("ppu_lifted", None)])
        parts = []
        lines, roles = profile.categories(samples, "test", {}, {}, parts, "stacks", drop_blocked=True)
        body = "\n".join(lines)
        self.assertEqual(roles, {"11": "SPU", "12": "SPU", "13": "PPU", "14": "host",
                                 "15": "RSX", "16": "PPU"})
        # tid 16 had blocked in pthread_cond_timedwait before the capture reached it
        self.assertIn("left out, blocked by the time the capture reached the thread: 1", body)
        # the helper under the overlay counts for that overlay image (inclusive column)
        self.assertIn("spu_ovl_msdsp_37000", body)
        self.assertIn("6 stacks", parts)
        self.assertIn("SPU lifted 16.7% interp 0.0% rt 16.7%", parts)
        self.assertIn("PPU 33.3%", parts)

    def test_strip_demangled_arguments(self):
        self.assertEqual(profile.strip_args("func_00B60184(ppu_context*)"), "func_00B60184")
        self.assertEqual(profile.strip_args("(anonymous namespace)::watcher()"),
                         "(anonymous namespace)::watcher")
        self.assertEqual(profile.strip_args("memcpy"), "memcpy")


if __name__ == "__main__":
    unittest.main()
