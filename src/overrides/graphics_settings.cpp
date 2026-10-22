/* The Graphics page's settings, persisted (graphics_settings.h). */
#include "graphics_settings.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace sarpbc_gfx {

Settings& settings()
{
    static Settings s;
    return s;
}

const char* path()
{
    const char* e = getenv("SARPBC_GFX_FILE");
    return e && *e ? e : "gamedata/graphics.ini";
}

static int clamp(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }

static void apply(const char* key, int v)
{
    Settings& s = settings();
    if (!strcmp(key, "unlock_fps")) s.unlock_fps = clamp(v, 0, 1);
    else if (!strcmp(key, "fps_overlay")) s.fps_overlay = clamp(v, 0, 1);
    else if (!strcmp(key, "window_size")) s.window_size = clamp(v, 0, kNumWindowSizes - 1);
    else if (!strcmp(key, "render_scale")) s.render_scale = clamp(v, 0, kNumRenderScales - 1);
}

void load()
{
    if (FILE* f = fopen(path(), "r")) {
        char line[128];
        while (fgets(line, sizeof line, f)) {
            char key[64];
            int v;
            if (sscanf(line, "%63[a-z_] = %d", key, &v) == 2) apply(key, v);
        }
        fclose(f);
    }
    // The documented environment switches win for this run (they are not written back).
    if (const char* e = getenv("SARPBC_UNLOCK_FPS")) apply("unlock_fps", atoi(e));
    if (const char* e = getenv("SARPBC_FPS_OVERLAY")) apply("fps_overlay", atoi(e));
    if (const char* e = getenv("SARPBC_RENDER_SCALE")) {
        const int pct = atoi(e);
        for (int i = 0; i < kNumRenderScales; i++)
            if (kRenderScalePercent[i] == pct) apply("render_scale", i);
    }
}

void save()
{
    Settings& s = settings();
    FILE* f = fopen(path(), "w");
    if (!f) return;
    fprintf(f, "unlock_fps = %d\nfps_overlay = %d\nwindow_size = %d\nrender_scale = %d\n", s.unlock_fps.load(),
            s.fps_overlay.load(), s.window_size.load(), s.render_scale.load());
    fclose(f);
}

}  // namespace sarpbc_gfx
