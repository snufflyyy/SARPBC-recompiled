# T064: FPS overlay in the top left corner (T064)

Status: done
Owner: claude
Priority: 2
Touches: patches/ps3recomp/NNNN-*.patch (libs/video/rsx_vulkan_backend.c: overlay drawn onto the presented image), src/main.cpp (toggle, fps source), src/overrides/frame_stats.cpp, config.toml, docs/debugging.md
Reads: src/overrides/frame_stats.cpp (guest fps counter, T029), docs/frame-pacing.md

## Goal
User request 2026-10-22: an FPS overlay in the top left corner of the window. Show guest fps (flips per
second, from frame_stats) and optionally host present fps / frame time (ms) and CPU drain ms. Drawn by the
Vulkan backend onto the final image after the game frame (a tiny built-in bitmap font, no game data, no
new dependency), top left, inside the window, not into the guest's surfaces and not into boot_check frame
dumps unless asked. Toggle with a key (F3, via the SDL events the backend already pumps) and
`SARPBC_FPS_OVERLAY=1` / config.toml; off by default. Must not add a GPU wait or a sync op (see subsystems.md
"Async batches": the overlay must be recorded in the present's own command buffer).

- Settings are also exposed in the game's Options > Graphics screen (T065), not only config.toml/env.

## Done when
Overlay visible top left in a windowed run and in a headless frame dump when enabled (capture checked), off
by default with no cost, toggle works, no new stalls in `FRAME_CLOCK_STATS`, test for the digit renderer,
patch exported, docs/debugging.md updated.

## Log

## Log
- 2026-10-22 19:07 claude: Done 2026-10-22: overlay (patch 0078, rsx_overlay.h font + test), src/overrides/fps_overlay.cpp, F3 toggle in input_kbm.cpp, the Graphics page's FPS Counter row. Verified: headless dump with PS3RECOMP_VK_OVERLAY_DUMP=1 shows '60 FPS 16.7 MS' top left; windowed under Xvfb + the RTX 2070 SUPER, a PIL screen grab shows '36 FPS 28.0 MS' in the real swapchain image. Docs: debugging.md.
- 2026-10-22 19:08 claude: claimed
- 2026-10-22 19:08 claude: Done 2026-10-22: overlay (patch 0078, rsx_overlay.h font + test), src/overrides/fps_overlay.cpp, F3 toggle in input_kbm.cpp, the Graphics page's FPS Counter row. Verified: headless dump with PS3RECOMP_VK_OVERLAY_DUMP=1 shows '60 FPS 16.7 MS'; windowed under Xvfb + the RTX 2070 SUPER, a PIL screen grab shows '36 FPS 28.0 MS' in the real swapchain image. Docs: debugging.md.
- 2026-10-22 19:08 claude: DONE: FPS overlay top left (guest fps and frame time), off by default, F3 / Graphics page / SARPBC_FPS_OVERLAY; patch 0078 + test; verified headless and in an Xvfb window
