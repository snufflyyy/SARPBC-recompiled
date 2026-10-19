# T026: Per-thread guest callback stacks (ppu_guest_call shares 0xCFFE0000)

Status: claimed
Owner: agent-cbstack
Touches: patches/ps3recomp/T026-*.patch (runtime/ppu/** guest-call path only), docs/ps3recomp-primer.md
Reads: tasks/claimed|open/T024*, T022*

## Goal
Found by T024: `ppu_guest_call` and `ppu_guest_call_ct` run every guest callback on the same stack,
0xCFFE0000. Two callbacks at once on different threads, or one nested in another, write over each
other's frames. This applies to GCM handlers pumped at HLE calls (T022) and on T024's
`GCM_INTR_THREAD`. Give each host thread, or each nesting depth, its own callback stack carved from
guest memory. Test it upstream-style (two threads, plus a nested call).

## Done when
A test fails on the old code and passes on the new; a boot_check line with `GCM_INTR_THREAD=1`.

## Log
- 2026-10-19 10:04 agent-cbstack: claimed
- 2026-10-19 10:05 agent-cbstack: Reuse check: soyjxck/ps3recomp fork (bbcf9a5) ppu_loader.cpp has the identical fixed 0xCFFE0000 s_cb_sp in both ppu_guest_call and _ct; dod3-recomp has nothing. Nothing to port; writing our own.
- 2026-10-19 10:12 agent-cbstack: Test first: external/ps3recomp tools/test_ppu_guest_call_stacks.py (+ runtime/ppu/tests/test_ppu_guest_call_stacks.cpp) on the OLD code: 6 checks FAIL (both threads' frames at 0xCFFDFC00; nested outer/inner both 0xCFFDFC00; sp 0xCFFE0000 is inside RSX local memory 0xC0000000+256MB, cellGcmSys localSize is 256 MB, so the old callback stack also sat on top of VRAM).
- 2026-10-19 10:46 agent-cbstack: Implemented (ps3recomp commit on sarpbc-patches): per (host thread, depth) callback stacks carved from the TOP of the PPU stack region (g_vm_stack_alloc.region_end moves down), 256 KB + guard page, pooled on thread exit. Unit test PASS (was 6 FAIL). Boot evidence of real nesting on 01.09 with GCM_INTR_THREAD=1: flip handler 0xDC144 runs INSIDE the GCM user handler 0xDC390 (depth 1) on tid 1, tid 2 and the GCM interrupt thread; vblank 0xDC2DC concurrently on tids 0/4/6/8. New-code boots: run@10:23 'STALLED since 29.6s | last open TEXTURES.TFC@5.6s | ... flips 66', run@10:34 'STALLED since 27.1s | last open TEXTURES.TFC@6.1s | pkgs 13 | zlib 3279 | dumps 5 lit 5 distinct 3 | flips 57 | threads 13/9 alive | unresolved 0 | alerts assert' with ESRB screen + car as last frame @6.6s. Old-code baseline @10:19: flips 53, last frame black (no ESRB). Pre-existing unrelated: tools/test_ppu_entry_arguments.py fails to link (ppu_loaded_elf_path from patch 0004).
