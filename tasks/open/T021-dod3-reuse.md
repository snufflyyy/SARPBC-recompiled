# T021: Reuse Drakengard 3's port — inventory, then port the generic pieces

Status: open
Owner: -
Touches: docs/dod3-reuse.md (new), docs/reference-ports.md, patches/ps3recomp/T021-*.patch (runtime/** and libs/** pieces NOT owned by an active task: see "Exclusions"), src/overrides/dod3_*.cpp (new)
Reads: https://github.com/soyjxck/dod3-recomp and https://github.com/soyjxck/ps3recomp (both MIT), docs/reference-ports.md, tasks/claimed/*

## Goal
**User directive (2026-10-18): reuse as much as possible from the other UE3 ps3recomp port.**
1. Inventory every dod3-recomp component and every fork commit on soyjxck/ps3recomp
   (174 ahead of the upstream pin's base). For each, record what it does, whether it is
   generic (runtime/HLE), UE3-generic (needs address re-finding: dod3 is UE3 v860, ours is v539
   (01.02) / 01.09), or Drakengard-specific, plus its applicability here, the effort, and which
   task owns that area. Write this up as docs/dod3-reuse.md: a ranked table with links to the source.
2. Port the generic runtime/HLE fixes that no active task owns, as patches with original
   authorship kept (`git format-patch` from the fork where it applies; otherwise a port with
   "Ported from soyjxck/ps3recomp <sha>" in the message). Likely candidates: user-mode
   sys_lwmutex, sys_lwcond wakeups, the guest memory page-table fast path, SPU task thread
   pooling, MFC/reservation per context, frozen guest clocks, RSX texture write-watching, and
   occlusion-query sync.
3. For each UE3-generic piece (frame clock, GetMaxTickRate, load_idle, native GC, Bink tick rate,
   prompts, camera), write how to find the corresponding addresses in our EBOOT (strings,
   patterns, call sites) and propose follow-up tasks.

## Exclusions (owned by active tasks, so only inventory these and tell the coordinator)
SPURS queue/LFQueue (T019), MultiStream/MP3/audio (T007), input incl. kbm/camera (T008),
HLE wait gaps (T020), lifter perf `--nonvolatile-locals`/`--hook` (T009, open).

## Done when
docs/dod3-reuse.md is complete; generic ports are exported as patches with tests or boot evidence;
follow-up tasks are proposed.

## Log
- 2026-10-18 23:57 agent-reuse: claimed
- 2026-10-19 00:04 agent-reuse: Setup done (worktree, build-0109). Baseline 01.09: boot_check 2026-10-19 00:02 v01.09 36a324e 60s: STALLED since 22.1s | last open GUIDCACHE.XXX@4.1s | pkgs 13 (GUIDCACHE last) | zlib 3147 | dumps 4 lit 4 distinct 1 | flips 18 | threads 13/9 alive | unresolved 4 | alerts open-fail,blocked. Fork = 174 commits on upstream 5244db9 (v0.13.0); our pin 39a3629 already has many of its fixes via upstream PRs (lwmutex on POSIX, lwcond layout, stvlx/stvrx, vcmpequb CR6, callee-save epilogue, BE-correct VMX packs via ppu_vmx.h, MFC slot release, SET_TRANSFORM_CONSTANT window, cellOvis via our 0007). Still missing in pin and generic: cellFsOpen flag values in ppu_fs.cpp AND sys_fs.h (CREAT/TRUNC/APPEND wrong: WRONLY|CREAT|TRUNC saves would not truncate), POSIX SPU task thread never drops its stack from the lock-line reserver set (use-after-free), sys_spinlock 8-byte long on LP64, lwcond signals are no-ops (1 ms poll), PPU thread slots/stacks never recycled. Porting these as T021-* patches.
- 2026-10-19 00:07 agent-reuse: HANDOFF: done=T021-1 ppu_fs Cell open flags (fork 6371138, author kept) + T021-2 sys_fs.h octal flags + tools/test_ppu_fs_open_flags.py (11/11 PASS); stack applies from 39a3629; not boot-verified (01.09 stalls before any file write). inventory covered=fork runtime/syscall/SPU/lifter commits, with already-in-pin list and owner hand-offs (T019/T007/T008/T009/T018) in docs/dod3-reuse.md. next=port 0012+0148 (POSIX SPU thread reserver cleanup, use-after-free, CLEAN), 0100 (lwcond wakeups, adapt), 0166+0167 (PPU thread slot/stack recycling), 0132/0131/0119 sys_fs; inventory RSX/GCM fork commits and dod3-recomp src/+tools (UE3 address recipes). T019 should look at fork 0079's SPURS_GUARD_FIRST_MS: 01.09 stalls right after 'guard 0x0133AA80 still closed after 20 s'. branch=worktree-agent-af4f1ac0749811197 (ee5c128)
- 2026-10-19 00:07 agent-reuse: RELEASED: paused for usage; see HANDOFF note
