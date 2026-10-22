/*
 * The Graphics page's settings (T065), shared with the features they switch (T062 unlocked
 * fps, T063 resolution and render scale, T064 FPS overlay). The page (graphics_menu.cpp)
 * writes them; each feature reads the one it owns. Persisted in graphics.ini
 * ($SARPBC_GFX_FILE, else gamedata/graphics.ini), read once at start.
 *
 * Environment variables set before the run win for the session (SARPBC_UNLOCK_FPS,
 * SARPBC_FPS_OVERLAY, SARPBC_FULLSCREEN, SARPBC_TEXTURE_QUALITY / _FILTER, SARPBC_BRIGHTNESS (indexes), SARPBC_SKIP_INTRO, SARPBC_WINDOW_SIZE=WxH, SARPBC_RENDER_SCALE=<percent>): they are the same switches
 * the tasks document; the page shows and changes the effective value.
 */
#pragma once
#include <atomic>

namespace sarpbc_gfx {

struct Settings {
    std::atomic<int> unlock_fps{0};    // 0 the game's own 60 Hz clock, 1 uncapped (T062)
    std::atomic<int> fps_overlay{0};   // 0 off, 1 on (T064)
    std::atomic<int> window_size{0};   // index into kWindowSizes (T063)
    std::atomic<int> texture_quality{1};  // index into kTextureQuality: 1 = Default (live)
    std::atomic<int> texture_filter{0};   // index into kTextureFilter: 0 = Default (live)
    std::atomic<int> brightness{2};       // index into kBrightnessGamma: 2 = 2.2, the game's (live)
    std::atomic<int> skip_intro{0};       // 1: the logos and ESRB screen are skipped (System page; read by the script)
    std::atomic<int> fullscreen{0};    // 0 windowed, 1 desktop fullscreen; live (F11, the page)
    std::atomic<int> render_scale{2};  // index into kRenderScalePercent: 2 = 100% (T063; at start)
};

struct Size { int w, h; };
constexpr Size kWindowSizes[] = {{1280, 720}, {1600, 900}, {1920, 1080}, {2560, 1440}, {3840, 2160}};
constexpr int kNumWindowSizes = sizeof kWindowSizes / sizeof kWindowSizes[0];
constexpr int kRenderScalePercent[] = {50, 75, 100, 150, 200, 300};
constexpr int kNumRenderScales = sizeof kRenderScalePercent / sizeof kRenderScalePercent[0];

// Texture and brightness settings are live. Texture filtering and quality go to the Vulkan sampler
// (rsx_vulkan_backend_set_texture_filtering: trilinear, anisotropy, mip LOD bias); brightness is the engine's
// own DisplayGamma, written into the running game (live_gamma.cpp) and, so the game starts with it, into the
// overlay's INI (tools/graphics_menu_patch.py: keep BRIGHTNESS_GAMMA in step with kBrightnessGamma).
constexpr const char* kTextureQualityNames[] = {"Low", "Default", "High"};
constexpr float kTextureLodBias[] = {1.5f, 0.0f, -0.5f};
constexpr const char* kTextureFilterNames[] = {"Default", "Trilinear", "Trilinear + 8x", "Trilinear + 16x"};
struct Filter { int trilinear; int anisotropy; };
constexpr Filter kTextureFilter[] = {{0, 0}, {1, 0}, {1, 8}, {1, 16}};
constexpr const char* kBrightnessNames[] = {"Darker", "Dark", "Default", "Bright", "Brighter"};
constexpr float kBrightnessGamma[] = {1.8f, 2.0f, 2.2f, 2.5f, 2.8f};   // DisplayGamma: lower is darker
constexpr int kNumTextureQuality = 3, kNumTextureFilter = 4, kNumBrightness = 5;

void start_live_gamma();   // live_gamma.cpp: a worker that keeps the engine's DisplayGamma at the setting

Settings& settings();
void load();                  // once, before the guest starts
void save();                  // after the page changes something
const char* path();

}  // namespace sarpbc_gfx
