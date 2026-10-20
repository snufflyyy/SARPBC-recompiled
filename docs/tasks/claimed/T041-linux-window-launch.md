# T041: Ensure run.sh opens a visible window on desktop Linux

Status: claimed
Owner: pi
Priority: 1
Touches: tools/run.sh, tools/test_run.py (new), docs/build-linux.md (desktop launcher section), .gitignore (runtime savedata only)
Reads: run.sh, docs/build-linux.md, docs/pipeline.md, docs/workflow.md

## Goal
Ensure ./run.sh defaults to a visible Linux desktop window, with explicit headless operation preserved.

## Done when
Real public launcher opens a stable mapped Vulkan window in a display test; launcher regression tests pass; known null-renderer/headless SDL misconfigurations fail with actionable messages; documented and merged.

## Log
- 2026-10-20 00:04 pi: claimed
- 2026-10-20 00:04 pi: Scope: run.sh help/default UX, tools/run.sh Linux window preflight/default title, new tools/test_run.py, docs/build-linux.md launcher section. No src/main.cpp or Vulkan batching edits (Claude/T040 owns them). Existing lower launcher exports PS3RECOMP_VK_WINDOW=1 and guest programs=1, but currently accepts an OFF/null build or dummy SDL video driver and backend silently falls back headless. Will test actual root launcher under Xvfb and guard known incompatible launch configurations while retaining explicit window=0.
- 2026-10-20 00:06 pi: Launcher regression suite added against real scripts with fake executable/ELF fixture in temporary git repo and paths containing spaces. RED: default title/config absent; windowed launch accepts known Vulkan-OFF cache and SDL dummy/offscreen driver. Existing window=1 default, explicit window=0, argument/exit forwarding and version selection are covered.
- 2026-10-20 00:07 pi: Eight launcher tests green (including subcases): default window=1, real entrypoint version/argument/exit propagation, title/config defaults, explicit window=0 compatibility, known null-build and dummy/offscreen-video rejection. No DISPLAY/Wayland env is required by mock tests; actual WSI smoke will use dedicated Xvfb display.
- 2026-10-20 00:08 pi: Real ./run.sh smoke under dedicated Xvfb X11: SDL x11 surface extensions, Vulkan swapchain1280x720/3 images, SARPBC window Map State:IsViewable continuously for5s. Executed from outside checkout; input config loaded via absolute default. Harness cleanup needed SIGKILL after guest ignored TERM; stopped only known own PID331697. Adding inner timeout before final confirmation.
- 2026-10-20 00:10 pi: Scope extension .gitignore: menu/save path writes gamedata/dev_hdd0/home/... including copied game icons. Added /gamedata/ under copyrighted runtime data exclusions; no generated saves/assets staged or edited. The launcher defaults also locate config.toml absolutely for desktop shortcuts launched outside checkout.
- 2026-10-19 21:01 pi: Desktop launch requested by user: default SDL wayland on Fedora/RADV RX 7800 XT fails vkGetPhysicalDeviceSurfaceFormatsKHR (VkResult 5), silently falls back headless despite scaffold window-open line. Stopped only own headless PID517773. SDL_VIDEODRIVER=x11 ./run.sh opens real 1280x720 four-image swapchain; Xlib confirms SARPBC 0x2c0002f map_state=2 (IsViewable). Left desktop game running under boot lock with 2h safety timeout; logs analysis/pi-desktop/game{,-x11}.log. Workaround documented in docs/build-linux.md. HANDOFF: default Wayland failure still needs runtime investigation; no runtime or launcher changes made.
