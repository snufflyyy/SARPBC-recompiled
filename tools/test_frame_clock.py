#!/usr/bin/env python3
"""Run the real native frame clock against deterministic FIFO/tick/present hooks."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FrameClock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="pi-t058-frame-clock-")
        root = Path(cls.tmp.name)
        source = (ROOT / "src/main.cpp").read_text()
        start = source.index("static std::atomic<unsigned> g_frames_presented")
        end = source.index("\n/* ---------------------------------------------------------------------------\n"
                           " * Guest file system", start)
        fixture = root / "fixture.cpp"
        fixture.write_text(r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <vector>
using DWORD = unsigned long;
using LPVOID = void*;
#define WINAPI
#define WINDOW_WIDTH 1280
#define WINDOW_HEIGHT 720
#define RSX_BACKEND_NAME "fixture"
struct Stop {};
static unsigned long long clock_us;
static unsigned requests, drains, ticks, current_frame, stats_frames;
static bool pending;
static int scenario;
static std::vector<unsigned> presented;
static void Sleep(DWORD ms) {
    clock_us += std::max<unsigned long long>(ms * 1000ull, 100ull);
    if (clock_us >= 300000) throw Stop{};
}
static int fixture_clock_gettime(int, timespec* ts) {
    ts->tv_sec = clock_us / 1000000;
    ts->tv_nsec = (clock_us % 1000000) * 1000;
    return 0;
}
#define clock_gettime fixture_clock_gettime
static unsigned long long GetTickCount64() { return clock_us / 1000; }
static int rsx_backend_init(uint32_t, uint32_t, const char*) { return 0; }
static int rsx_backend_pump() { return 0; }
static void rsx_backend_present() { presented.push_back(current_frame); }
static void flip() { current_frame = ++requests; pending = true; }
static void cellGcmTickVBlank() {
    ++ticks;
    if (ticks == 1 && scenario == 5) flip();  // legacy PPU-side request
    if (ticks == 1 && scenario == 6) ++requests;  // queued, not executed
}
static void cellGcmTickFlip() {}
static unsigned cellGcm_flip_request_count() { return requests; }
static int cellGcm_take_flip_pending() {
    const bool was_pending = pending;
    pending = false;
    return was_pending;
}
static void cellGcm_rsx_process_fifo() {
    assert(!pending);  // never draw the next frame over an unpresented one
    ++drains;
    if ((scenario == 0 && drains == 2) ||  // outer-cadence drain
        (scenario == 1 && drains == 1) ||  // tick drain
        (scenario == 2 && drains <= 2) ||  // adjacent tick/outer markers
        (scenario == 3 && drains <= 5))    // catch-up ticks and outer drain
        flip();
    if (scenario == 6 && drains == 12) {  // the queued marker finally executes
        current_frame = requests;
        pending = true;
    }
}
static void sarpbc_frame_stats_tick(unsigned long long, unsigned frames) {
    stats_frames = frames;
}
''' + source[start:end] + r'''
int main(int argc, char** argv) {
    assert(argc == 2);
    scenario = std::atoi(argv[1]);
    try { frame_clock(nullptr); } catch (const Stop&) {}
    std::vector<unsigned> guest;
    for (unsigned frame : presented) if (frame) guest.push_back(frame);
    std::vector<unsigned> expected;
    const unsigned count = scenario == 4 ? 0 : scenario == 2 ? 2 : scenario == 3 ? 5 : 1;
    for (unsigned i = 1; i <= count; ++i) expected.push_back(i);
    assert(guest == expected);  // ordered exactly once, not next-loop duplicates
    assert(ppu_boot_frames_presented() == count);
    assert(stats_frames == count);
    assert(!presented.empty());  // pre-first-flip boot fallback stays available
    assert(!pending);
}
''')
        cls.binary = root / "fixture"
        subprocess.run([os.environ.get("CXX", "c++"), "-std=c++20", "-Wall", "-Wextra",
                        "-Werror", str(fixture), "-o", str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_present_once_at_each_guest_boundary(self):
        for cap in ("0", "30"):
            for scenario in range(7):
                with self.subTest(cap=cap, scenario=scenario):
                    env = dict(os.environ)
                    env.pop("FRAME_CLOCK_STATS", None)
                    env["SARPBC_FPS_CAP"] = cap
                    env["FRAME_CLOCK_SLEEP_MS"] = "50" if scenario == 3 else "1"
                    result = subprocess.run([str(self.binary), str(scenario)], env=env,
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
