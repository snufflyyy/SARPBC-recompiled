/* Optional guest-frame telemetry. Backend boot/fallback presents do not count.
 * Called only by the frame-clock thread; no extra worker or guest scheduling.
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
