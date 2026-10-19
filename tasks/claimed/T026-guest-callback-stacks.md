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
