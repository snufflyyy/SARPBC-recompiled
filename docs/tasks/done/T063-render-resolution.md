# T063: Selectable render resolution / internal scale (T063)

Status: done
Owner: claude
Priority: 4
Touches: src/main.cpp (WINDOW_WIDTH/HEIGHT, backend init), config.toml, patches/ps3recomp/NNNN-*.patch (libs/video/rsx_vulkan_backend.c, rsx_draw_engine.c surface sizing), docs/subsystems.md
Reads: docs/subsystems.md "Arena textures" (the 85% safe-area border), docs/build-linux.md, rsx_vulkan_backend.h

## Goal
User request 2026-10-22: a selectable resolution. The game renders a fixed 1280x720 canvas (WINDOW_WIDTH/HEIGHT
in main.cpp; the guest's colour/depth surfaces are that size). Add (1) the output window/swapchain size
(any size, scaled blit, aspect kept) and (2) an internal render scale (e.g. 1.5x/2x/3x: engine colour and
depth targets created scaled, viewport/scissor scaled, post-process and screen-space passes sampling the
scaled targets correctly, UI/HUD sharp), via config.toml and an env override. Watch for effects that assume
canvas-sized textures (the shadow snapshot crop, 0064; depth reads from the FP16 target alpha).

- Settings are also exposed in the game's Options > Graphics screen (T065), not only config.toml/env.

## Done when
Window size and internal scale selectable, 720p default byte-identical to today, captures at 2x show no
broken shadows/HUD/post effects, fps cost measured (GPU is at P8 here: note it), tests and lint pass.

## Log

## Log
- 2026-10-22 19:19 claude: claimed
- 2026-10-22 19:19 claude: Window/output size done (Resolution row, SARPBC_WINDOW_SIZE=WxH, patch 0080, checked under Xvfb at 1920x1080). Internal render scale NOT done: ScreenPercentage in the engine INI does nothing (surfaces stay 1280x720); a real scale needs the draw engine to scale every surface/viewport/copy and the screen-space shader constants. Analysis in docs/graphics-menu.md 'Render scale'. HANDOFF: done=window size; next=draw-engine surface scale (rsx_draw_engine.c surface creation ~line 609, vk_eng_surface_view) + fragment resolution constants; branch=main
- 2026-10-22 19:19 claude: RELEASED: paused: window size done, internal render scale open; see HANDOFF
- 2026-10-22 20:34 claude: claimed
- 2026-10-22 20:34 claude: Render scale done in the Vulkan backend (patch 0081): scaled colour/depth targets, viewport/scissor/transfers/snapshots converted at the boundary, display image = scaled canvas. Checked 50/100/150/200/300 % (640x360 .. 3840x2160), menus, loading screens, arena; effects match 100 %. 300 % ~23 fps. Menu row Render Scale (applies at start). Speed: unlocked fps verified against the match clock.
- 2026-10-22 20:34 claude: DONE: Window size (patch 0080) and internal render scale 50-300 % (patch 0081) with Options > Graphics rows; verified by captures at each scale
