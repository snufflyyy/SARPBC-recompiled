/*
 * The Graphics page's settings (T065), shared with the features they switch (T062 unlocked
 * fps, T063 resolution and render scale, T064 FPS overlay). The page (graphics_menu.cpp)
 * writes them; each feature reads the one it owns. Persisted in graphics.ini
 * ($SARPBC_GFX_FILE, else gamedata/graphics.ini), read once at start.
 *
 * Environment variables set before the run win for the session (SARPBC_UNLOCK_FPS,
 * SARPBC_FPS_OVERLAY, SARPBC_FULLSCREEN, SARPBC_WINDOW_SIZE=WxH, SARPBC_RENDER_SCALE=<percent>): they are the same switches
 * the tasks document; the page shows and changes the effective value.
 */
#pragma once
#include <atomic>

namespace sarpbc_gfx {

struct Settings {
    std::atomic<int> unlock_fps{0};    // 0 the game's own 60 Hz clock, 1 uncapped (T062)
    std::atomic<int> fps_overlay{0};   // 0 off, 1 on (T064)
    std::atomic<int> window_size{0};   // index into kWindowSizes (T063)
    std::atomic<int> fullscreen{0};    // 0 windowed, 1 desktop fullscreen; live (F11, the page)
    std::atomic<int> render_scale{2};  // index into kRenderScalePercent: 2 = 100% (T063; at start)
};

struct Size { int w, h; };
constexpr Size kWindowSizes[] = {{1280, 720}, {1600, 900}, {1920, 1080}, {2560, 1440}, {3840, 2160}};
constexpr int kNumWindowSizes = sizeof kWindowSizes / sizeof kWindowSizes[0];
constexpr int kRenderScalePercent[] = {50, 75, 100, 150, 200, 300};
constexpr int kNumRenderScales = sizeof kRenderScalePercent / sizeof kRenderScalePercent[0];

Settings& settings();
void load();                  // once, before the guest starts
void save();                  // after the page changes something
const char* path();

}  // namespace sarpbc_gfx
