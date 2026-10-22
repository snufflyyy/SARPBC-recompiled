# T064: FPS overlay in the top left corner (T064)

Status: open
Owner: -
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
