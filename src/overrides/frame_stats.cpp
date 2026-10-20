/*
 * Guest frame rate, for measuring (T029): SARPBC_FRAME_STATS=1.
 *
 * Once a second, logs "[frame-stats] clock_ms=<ms> guest_frames=<n>" to stderr,
 * where n is ppu_boot_frames_presented(): the frames the game itself flipped
 * (the backend's boot/fallback presents do not count). Two lines give the fps
 * over any window; tools/spu_profile.sh and the menu recipe in
 * docs/subsystems.md "Menu frame rate" read them. Use this, not the 0.5 s
 * timestamps in frames.jsonl.
 *
 * Called only by the frame-clock thread (src/main.cpp frame_clock), so there is
 * no extra worker and no guest scheduling.
 */
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

extern "C" void sarpbc_frame_stats_tick(uint64_t clock_ms, unsigned guest_frames)
{
    static const bool enabled = [] {
        const char* value = std::getenv("SARPBC_FRAME_STATS");
        return value && *value && std::strcmp(value, "0") != 0;
    }();
    static uint64_t last_ms = 0;
    if (!enabled || (last_ms && clock_ms - last_ms < 1000)) return;
    std::fprintf(stderr, "[frame-stats] clock_ms=%llu guest_frames=%u\n",
                 static_cast<unsigned long long>(clock_ms), guest_frames);
    last_ms = clock_ms;
}
