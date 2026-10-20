# T042: Fix native Wayland Vulkan surface-format enumeration

Status: done
Owner: pi
Priority: 0
Touches: libs/video/rsx_vulkan_backend.c (surface-format enumeration only), libs/video/tests/test_vulkan_surface_formats.* (new), patches/ps3recomp/0041-*.patch, patches/ps3recomp/README.md, docs/build-linux.md (Wayland section), docs/status.md, specs/IMPACT_LATEST.md
Reads: docs/build-linux.md, patches/ps3recomp/README.md, T041 desktop launch notes

## Goal
Fix the native Wayland launch requested by the user. The current backend clamps the
surface-format list to 64 entries and treats VK_INCOMPLETE as fatal, dropping the
window and continuing headless on this RADV desktop.

## Done when
Regression tests cover more than 64 formats, changing counts and error handling;
the patch is exported; the native Wayland launcher creates a swapchain and presents
frames on the user's desktop without a headless fallback.

## Notes
Work in the main checkout per docs/status.md session 9 user instruction (supersedes
older worktree procedure). WSI scope does not change T040 batching or T024 readback.

## Log
- 2026-10-19 21:04 pi: claimed
- 2026-10-19 21:05 pi: Isolated WSI probe confirms exact failure: native Wayland advertises >64 surface formats, old 64-entry fill returns VK_INCOMPLETE (5); complete allocation succeeds (see next recorded output). Vulkan spec requires retry/full enumeration, not fatal handling. No game data involved.
- 2026-10-19 21:06 pi: Probe: wayland exposes99 formats, clamped fill returns5, full99 fill returns0. New mocked test FAILED pre-fix at99 formats; dynamic enumeration + 4 bounded retries now passes all cases. GCC sanitizer runtime absent locally; retry sanitizer checks with clang.
- 2026-10-19 21:07 pi: Regression green with GCC and clang; 9 launcher tests pass; existing mocked present/readback test passes. ASan/UBSan could not link: system GCC symlinks target missing libasan.so.8.0.0/libubsan.so.1.0.0, ROCm clang sanitizer archives also absent. Allocation-tracking regression verifies all success/error/retry paths release memory. Sanitizer prerequisite gap recorded, not a renderer failure.
- 2026-10-19 21:09 pi: Build succeeded with tools/task.sh lock cpu cmake --build versions/0109/build -j10 (backend object, runtime archive and sarpbc linked). Runtime commit19eb24b exported as0039-vk-wayland-surface-formats.patch. Native Wayland45s smoke now running with protocol debug, frame telemetry and frame capture; exact-owned timeout provides cleanup. AGENTS.md patch-count line included to keep41 accurate.
- 2026-10-19 21:10 pi: Entire41-patch stack applies cleanly in isolated shared clone at analysis/pi-desktop/patch-stack-*/runtime; resulting full tree equals runtime19eb24b, and regression passes there. Refreshed build.sh hash/HEAD stamp only after full-tree equality, avoiding unnecessary reset/recompile on next user build. Valgrind Memcheck passes15 allocations/frees, zero errors/leaks.
- 2026-10-19 21:11 pi: Native Wayland45s smoke PASS: SDLwayland, 1280x720 four-image swapchain format44,3581 guest frames, no fallback/acquire/present errors; compositor log has3637 surface attaches/commits. Inspected capture: Guest1 CHOOSE PROFILE rendered correctly. Evidence analysis/pi-desktop/wayland-fixed.{log,ppm,png}; timed run stopped only its own game (137 expected). X11 regression queued separately under boot lock.
- 2026-10-19 21:12 pi: Final validation: X1130s smoke PASS,2074 guest frames,1280x720 four-image swapchain, no fallback/presentation errors; test stopped its own game. GCC/Clang mocked tests +9 launcher tests +present regression +Valgrind +full41-patch application +01.09 build +native Wayland/X11 smoke all pass. Self-review: bounded retries and calloc/free safe on every path, no added dependencies/secrets/game data; existing UNORM policy unchanged; only WSI enumeration changed. HANDOFF: implementation complete; runtime19eb24b exported as0041; native ./run.sh needs no X11 workaround. ASan/UBSan unavailable (missing host runtimes); Valgrind zero leaks/errors substitutes memory check. No game intentionally left running.
- 2026-10-19 21:12 pi: DONE: Fixed native Wayland surface enumeration (99 formats vs old64 cap), patch0041. Built01.09; native Wayland3581frames/45s and X112074frames/30s pass. Unit/launcher/present regressions, Valgrind and full patch stack pass. See build-linux.md; no game left running.
