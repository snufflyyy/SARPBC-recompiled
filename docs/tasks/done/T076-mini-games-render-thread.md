# T076: Mini-Games fps: the render thread's guest stores (inline fast path)

Status: done
Owner: claude
Priority: 1
Touches: external/ps3recomp (ppu_lifter.py header, ppu_loader.cpp, spu_coherency.c; patch 0090), tools/cpu_profile*, docs/subsystems.md, docs/debugging.md
Reads: docs/subsystems.md (ShaderPatching job chain, T075), docs/dod3-reuse.md (Port next 9)

## Goal

Mini-Games sat at ~31-38 fps after T075. The remaining limit was said to be the FIFO drain (~1000 draws a frame).
Find what really limits it and fix that.

## Done when

The limiter is named with a measurement, the fix is an A/B in one binary, the arena and menus do not regress,
`tools/lint.py --tests` passes.

## Log
- 2026-10-23 21:33 claude: claimed
- 2026-10-23 21:34 claude: Skip-draws A/B: drain is ~15% of the frame. Render thread 84% busy, 33% of it guest stores (vm_write32/64 + spu_coh_is_reserved). Patch 0090 inline stores in the lifter header + relift: Mini-Games 31 -> 44 fps interleaved A/B, arena 59.8, lint --tests pending.
- 2026-10-23 21:37 claude: DONE: Mini-Games 31 -> 44 fps (interleaved A/B, one binary): the render thread's guest stores were a call into the loader plus an out-of-line reservation check (33% of its CPU); patch 0090 inlines them in the lifted header (needs relift). The drain was ~15% of the frame. New tools/cpu_profile.sh. Left: 3 MB ring wrap waits, ps3_indirect_call_impl, -O1.
