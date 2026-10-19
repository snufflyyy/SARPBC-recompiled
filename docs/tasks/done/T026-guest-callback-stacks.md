# T026: Per-thread guest callback stacks (ppu_guest_call shares 0xCFFE0000)

Status: done
Owner: agent-cbstack
Touches: patches/ps3recomp/T026-*.patch (runtime/ppu/** guest-call path only), docs/ps3recomp-primer.md
Reads: docs/tasks/claimed|open/T024*, T022*

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
- 2026-10-19 10:57 agent-cbstack: Final boot (patch stack from pin, 47 patches): 'boot_check 2026-10-19 10:57 v01.09 63e8968 60s: STALLED since 21.6s | last open TEXTURES.TFC@6.1s | pkgs 13 (GUIDCACHE last) | zlib 3279 | dumps 6 lit 6 distinct 2 | flips 66 | threads 13/9 alive | unresolved 0 | alerts assert' (GCM_INTR_THREAD=1, ESRB frame lit 2951 @6.6s). Baseline old-code boots 10:43/10:51: flips 56/66, also ESRB. No boot-visible difference; correctness fix only. No guard faults, no 'no room', 13 callback slots.
- 2026-10-19 10:57 agent-cbstack: HANDOFF: done=per-(host thread, depth) guest callback stacks, test (6 FAIL old -> PASS new), primer section, patch patches/ps3recomp/T026-ppu-guest-call-stacks.patch; state=complete, boot unchanged (ESRB then T027 stall); next=optional: export a locked ppu_stack_carve() from runtime/syscalls/sys_ppu_thread.c (outside T026 Touches) and give callbacks the caller's r13 instead of PPU_TLS_TP; branch=worktree-agent-ac8b9ee2d9b13d6e9
- 2026-10-19 10:57 agent-cbstack: DONE: ppu_guest_call/_ct now run each callback on a stack per (host thread, nesting depth), 256 KB + guard page, carved from the top of the PPU stack region (region_end moves down), pooled on thread exit; was a shared 0xCFFE0000 inside RSX local memory. Boot shows real nesting on 01.09 (flip handler 0xDC144 inside GCM user handler 0xDC390 on tids 1, 2 and the GCM interrupt thread). New test tools/test_ppu_guest_call_stacks.py: 6 FAIL on old code, PASS on new. Boot with GCM_INTR_THREAD=1 unchanged vs baseline (ESRB, then stall). Patch T026-ppu-guest-call-stacks.patch; docs/ps3recomp-primer.md.
