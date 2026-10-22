/*
 * The FPS counter in the window's top left corner (T064).
 *
 * Called by the frame-clock thread with the clock and the number of frames the game itself
 * flipped (the same two numbers as frame_stats.cpp). Twice a second, while the setting is on
 * (Options > Graphics > FPS Counter, F3, SARPBC_FPS_OVERLAY=1), it formats the guest's frame
 * rate and frame time and hands them to the Vulkan backend, which copies a small bitmap into
 * each presented image (rsx_vulkan_backend_set_overlay_text): nothing is added to the guest's
 * surfaces, the draw engine or the GPU's work, and with the setting off this is one load.
 */
#include <cstdint>
#include <cstdio>

#include "graphics_settings.h"

#if defined(PS3RECOMP_RSX_VULKAN)
extern "C" void rsx_vulkan_backend_set_overlay_text(const char* text);
#else
static void rsx_vulkan_backend_set_overlay_text(const char*) {}
#endif

extern "C" void sarpbc_fps_overlay_tick(uint64_t clock_ms, unsigned guest_frames)
{
    static bool shown = false;
    static uint64_t last_ms = 0;
    static unsigned last_frames = 0;
    if (!sarpbc_gfx::settings().fps_overlay.load(std::memory_order_relaxed)) {
        if (shown) rsx_vulkan_backend_set_overlay_text(nullptr);
        shown = false;
        last_ms = 0;
        return;
    }
    if (!last_ms) {
        last_ms = clock_ms;
        last_frames = guest_frames;
        return;
    }
    if (clock_ms - last_ms < 500) return;
    const double fps = (guest_frames - last_frames) * 1000.0 / (double)(clock_ms - last_ms);
    char text[48];
    std::snprintf(text, sizeof text, "%.0f FPS  %.1f MS", fps, fps > 0.5 ? 1000.0 / fps : 0.0);
    rsx_vulkan_backend_set_overlay_text(text);
    shown = true;
    last_ms = clock_ms;
    last_frames = guest_frames;
}
