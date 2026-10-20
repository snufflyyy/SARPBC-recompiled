# T045: In-level rendering mostly black with small corrupt rectangles after loading succeeds

Status: claimed
Owner: pi
Priority: 1
Touches: patches/ps3recomp/T045-*.patch (libs/video/rsx_vulkan_backend.c, runtime/rsx/**), docs/subsystems.md (Graphics), docs/debugging.md (arena frontier)
Reads: docs/tasks/claimed/T044-arena-flip-callback-stall.md, docs/subsystems.md (Graphics), docs/dod3-reuse.md

## Goal
After the slab-service and callback-affinity fixes, the challenge level loads and physics/frames continue, but the frame is mostly black with small corrupt rectangles. Establish the renderer root cause and display an interactive arena correctly. First A/B disables Vulkan batching and geometry cache to exclude the menu-only performance changes.

## Done when
An in-level capture shows the arena and car with usable HUD and input. Any remaining visual defects are stated explicitly; a changing corrupt frame is not proof of playability.

## Log
- 2026-10-20 pi: Baseline .worktrees/pi/analysis/boot_check/20261020-094804-706462/:7755 flips over150s, 66distinct captures, no unlifted/unresolved calls, slab and mixer alive. PAD_FILE throttle/jump/boost reach guest and rumble is observed. Last frame is mostly black with small noisy patches. Conservative Vulkan + native Wayland A/B queued.
- 2026-10-20 09:55 pi: claimed
- 2026-10-20 09:59 pi: Conservative Vulkan A/B (both batching and geometry cache off) still has same corrupt arena image; no improvement. Native Wayland window runs through menus+challenge load with continuous frames, no unresolved imports; real audio187.5 blocks/s,0 underruns. Report run20261020-095526-758530, flips4060,64distinct captures. This rules out those two T040 optimizations as the primary corruption cause. Next use built-in RSX_ENGINE_PASS_DUMP after85s to locate first wrong render pass.
