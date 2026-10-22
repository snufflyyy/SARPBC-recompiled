# T061: Draw-engine CPU: vertex fetch/remap and texture hashing (T061)

Status: done
Owner: claude
Priority: 1
Touches: patches/ps3recomp/NNNN-*.patch (libs/video/rsx_draw_engine.c, rsx_vertex_compact.c, rsx_vulkan_backend.c vk_geo_*), docs/subsystems.md
Reads: docs/dod3-reuse.md Port next 9, docs/subsystems.md "Async batches"

## Goal
After T060 the arena is bound by the frame-clock thread's CPU work in the draw engine (~15 ms of every frame:
vertex remap/fetch/decode, vk_geo_get hashing, texture content hashing). Cut it, byte-identical output.

## Done when
Profile before/after (gdb stack samples of the clock thread, FRAME_CLOCK_STATS fifo ms per frame), rendering
unchanged in captures, tests pass, patch exported, docs updated.

## Log
- 2026-10-22 17:09 claude: claimed
- 2026-10-22 17:49 claude: Profile (70 drain samples): vk_geo_get 17%, fetch/decode 26%, remap 13%, texture hash 7%. 0076: vc_* decoded-vertex cache (key = layout + refs + merged attribute-span bytes, 128-bit 4-lane hash), geometry_hint ids to the Vulkan backend (s_geo_id), texture hash index + 4-lane hash. divider_mask rejection dropped (only matters for frequency>1 attrs, already refused). Per draw us: backend 9.4->3.8, textures 5.6->4.5. Arena drain 15->7.4 ms/frame, clock idle 53%, 60 fps (cap). Check modes: 1.05M hits/0 mismatches (cache), 0 (geo ids). 330 s pad run through results screen OK, 2.28M hits.
- 2026-10-22 17:49 claude: DONE: Decoded-vertex cache + geometry ids + texture index (patch 0076): arena FIFO drain 15 to 7.4 ms/frame, 0 mismatches in check modes, test_vertex_cache added, lint --tests 98/0, 330 s through results. Left: ref-list build 5.5 us/draw (hash raw index bytes), texture sparse check, rebuilt-index cache.
