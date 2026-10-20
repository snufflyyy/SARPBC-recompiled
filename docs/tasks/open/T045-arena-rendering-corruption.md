# T045: In-level rendering mostly black with small corrupt rectangles after loading succeeds

Status: open
Owner: -
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
- 2026-10-20 11:28 pi: RELEASED: pi out of usage; claude continues (RSX_ENGINE_PASS_DUMP next, as pi planned)
- 2026-10-20 11:28 claude: claimed
- 2026-10-20 11:32 claude: Pass dump (RSX_ENGINE_PASS_DUMP_AFTER=85, run 20261020-112907-829394): scene target 0x0A130000 (FP16) all black; zeta 0x09570000 depth uniformly 1.0 even after the depth prepass (pass 008: 10 draws dt1 dw1 df 0x206 GEQUAL). Hypothesis: reversed-Z; game clears depth with ZSTENCIL_CLEAR_VALUE=0, rsx_draw_engine.c sink_clear maps zs==0 to 1.0 (upstream 4df0909, still in v0.16.0), so every GEQUAL fragment fails. Testing literal clear (temporary env gate) + logging clear values in passes.txt.
- 2026-10-20 11:38 claude: CONFIRMED: all 21 clears set ZSTENCIL_CLEAR_VALUE=0 (reversed-Z). Patch T045-zstencil-clear-zero (rsx_draw_engine.c sink_clear: zero clears to depth 0; pass capture logs color/zs per clear). Final binary, 105 s boot --pad 'cross@40*4/5,cross@70,r2:120@90,cross@100' (run 20261020-113603-891029): PROGRESSING, 5057 flips, unresolved 0, the arena draws (stadium, floor, goal, centre circle; camera moves between dumps). Before/after PNGs: captures/T045/ in the pi worktree (local only).
- 2026-10-20 11:38 claude: HANDOFF: done=arena is no longer black (reversed-Z depth clear fixed, merged to main). state=remaining defects: (1) noisy/dithered textures on some surfaces: the floor grid band, wall panels (look like a texture format, swizzle or mip/LOD issue: start from passes.txt/draws.txt texture formats f81/f86/f88/fA5 for those draws); (2) HUD quads (top centre, top right, boost meter bottom right) are garbage: likely the same texture decode, or a render-to-texture surface sampled as guest memory; (3) black border around the frame (safe-area setting?); (4) no car visible: check whether the camera is an intro flythrough or the car is not drawn; (5) the D3D12 path rsx_live_draw.c:7591 has the same !zs ? 1.0f (Windows, T011). Also no dedicated regression test for the clear yet. next=pass dump with RSX_ENGINE_PASS_DUMP_DRAWS=1 after ~90 s, find the draw that samples the noisy texture, compare its format/layout with the decoder. Recipe in subsystems.md 'Arena renders black'.
- 2026-10-20 11:38 claude: RELEASED: paused (user asked to wrap up); see HANDOFF
