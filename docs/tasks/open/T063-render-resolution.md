# T063: Selectable render resolution / internal scale (T063)

Status: open
Owner: -
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
