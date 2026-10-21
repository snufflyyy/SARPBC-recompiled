# T021: Reuse Drakengard 3's port — inventory, then port the generic pieces

Status: claimed
Owner: claude
Priority: 17
Touches: docs/dod3-reuse.md (new), docs/reference-ports.md, patches/ps3recomp/T021-*.patch (runtime/** and libs/** pieces NOT owned by an active task: see "Exclusions"), src/overrides/dod3_*.cpp (new)
Reads: https://github.com/soyjxck/dod3-recomp and https://github.com/soyjxck/ps3recomp (both MIT), docs/reference-ports.md, docs/tasks/claimed/*

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

## Exclusions (have their own tasks: only inventory these, and note what you find on that task)
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
- 2026-10-20 18:00 sonnet-2: claimed
- 2026-10-20 18:00 sonnet-2: Started by claude as a Sonnet 5.5 subagent (user request 2026-10-20), isolated worktree; scope this round: finish the inventory (docs/dod3-reuse.md, docs/reference-ports.md) only. No patches: T043 is rebasing the whole stack.
- 2026-10-20 18:19 sonnet-2: Findings: v0.16.0 still lacks (checked in code) alpha-ref for float surface formats 11/12/13 (rsx_fp_decompiler.c:1433), zero-stride vertex attribute as constant (rsx_vertex_compact.c:130), DDX/DDY and NRM-zero in the fp decompiler, scissored depth clears, vertex fetch by attribute, walker kick on usleep, rsx_present_pace, FIFO-position PrepareFlip. Arena FP16 target is cfmt 11 so alpha-ref matters. 208 fork commits: 35 ported, 12 in-pin, 12 upstream, 87 missing, 62 n/a.
- 2026-10-20 18:19 sonnet-2: DONE-READY (inventory): branch worktree-agent-a1adb7e6c8c6fb98d commit 8aa8db3; docs/dod3-reuse.md rewritten (ranked Port next top 10, frame pacing recipe, all 208 fork commits, full dod3-recomp tree), docs/reference-ports.md and AGENTS.md index row updated. Not merged.
- 2026-10-20 18:24 sonnet-2: RELEASED: Inventory part done and merged (claude): 208 fork commits classified against v0.16.0, ranked Port next list at the top of docs/dod3-reuse.md. Porting is the next step (do it as patches on the v0.16.0 stack); top picks: alpha-test ref for float targets (3f20f13), zero vertex stride (0eee9dd), FIFO wake on guest usleep (260ccb8).
- 2026-10-20 18:28 claude: Ported Port-next #1 and #2 as patches 0048 (alpha ref float formats, fork 3f20f13; ours + test) and 0049 (zero vertex stride, fork 0eee9dd, author kept). Arena boot fine (125 s, 2612 flips); no visible change in the survey scenes (the white shards at boost pickups are probably the glass canisters shattering, unverified).
- 2026-10-21 13:51 claude: claimed
- 2026-10-21 14:03 claude: Ported Port-next #8 (DDX/DDY, NRM zero vector) as patch 0065 (author soyjxck kept, +3 checks in test_fp_decompiler: 77 pass); arena boot 130 s fine. #7: the cropped-depth half is already fixed by T054's 0064 (snapshot cropped to the sampling texture); scissored clears not needed (whole-target clear to 1.0 is a superset for the shadow map).
- 2026-10-21 14:16 claude: Port-next #10 (aniso half) done: patch vulkan-anisotropic (idea from fork 66fd0a9, own Vulkan implementation). Arena capture sharper floors, fps 36.9, no speckle. Remaining open: #3 FIFO wake on usleep, #4 per-attribute vertex fetch, #5 prepared flips at FIFO position, #6 present pace, pipeline cache.
