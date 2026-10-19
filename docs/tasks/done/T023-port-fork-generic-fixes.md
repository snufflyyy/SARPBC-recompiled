# T023: Port the next generic fork fixes (from docs/dod3-reuse.md)

Status: done
Owner: agent-forkfix
Touches: patches/ps3recomp/T023-*.patch (runtime/** threads, lwcond, sys_fs; libs/spurs/cellSpurs.h error codes), docs/dod3-reuse.md
Reads: docs/dod3-reuse.md (T021 inventory), soyjxck/ps3recomp

## Goal
Port, with original authorship, these fork fixes that T021 ranked as generic and unowned: 0012+0148
(Linux SPU task thread stack use-after-free; ~90 such threads in 6 s here), 0100 (lwcond signals
wake waiters; today a wait is a 1 ms sleep), 0166+0167 (reclaim PPU thread slots and stacks), and
0131/0132/0119 (sys_fs). Also fix cellSpurs.h's error macros (0x804107xx; the real values are 0x804109xx,
found by T019). Then continue the inventory where T021 stopped (fork RSX/GCM/Vulkan commits; dod3
src/ and tools/).

## Done when
Ported with tests or boot evidence, with a boot_check summary before and after; docs/dod3-reuse.md updated.

## Log
- 2026-10-19 09:09 agent-forkfix: claimed
- 2026-10-19 09:12 agent-forkfix: baseline (before ports): boot_check 2026-10-19 09:11 v01.09 bd42e4f 60s: STALLED since 21.6s | last open GUIDCACHE.XXX@3.6s | pkgs 13 (GUIDCACHE last) | zlib 3147 | dumps 4 lit 4 distinct 1 | flips 9 | threads 13/9 alive | unresolved 0 | alerts open-fail,assert (SPU_INTERP_UNLIFTED=1 BUILD_DIR=build-0109). Applied fork 0012+0148 via git am (0148 context fixed by hand), plus our follow-up: POSIX async SPU thread also calls spu_mfc_forget_range.
- 2026-10-19 09:22 agent-forkfix: Ported on sarpbc-patches (5 patch files T023-1..5): 0012+0148 (+ our POSIX spu_mfc_forget_range), 0100 lwcond wake (adapted: ReleaseSemaphore/WaitForSingleObject) + new test tools/test_ppu_lwcond_wake.py (14/14 pass; old code fails 3: 57 wait returns per 60 ms hand-off), 0166+0167 clean (ps3recomp_host --threads: 600-thread turnover OK, 3196 KB stack cut vs 8192 limit; boot smoke PASS), 0119/0131/0132 clean, cellSpurs.h TASK errors 0x804109xx (core 0x804107xx were right). After-port boot: identical frontier (STALLED since 21.6s, guard 0x0133AA80). SARPBC threads all flags=0x1 (joinable), so 0166's non-joinable rule changes nothing here. Pre-existing: test_spurs_queue hangs in Release builds (asserts with side effects vanish under NDEBUG; passes with asserts), spu_fnms_zero_extended fixture fails to compile here, title_hacks --check: lv2_register.c 11->13 at the pin.
- 2026-10-19 09:24 agent-forkfix: FYI T022 (frontier): local experiment (uncommitted, reverted) with fork 0014 GCM_FIFO_NO_RESYNC=1: no resync; the FIFO then sits parked on a JUMP-to-self at io 0x0008B144 (w=0x2008B144) right after vertex-array setup (0x1740/0x1680/0x1FC0) and alpha state; nobody patches it within 60 s; the stall is unchanged (guard 0x0133AA80 closed at 21.6 s). Without the switch the walker 'stuck-get' resyncs past such parks 3 times (0x8C784->0x957BC, 0x95BAC->0x9BE18, 0xDAD7C->0xE9D4C), dropping ~36+25+61 KB of commands. Guess: a SPURS job (Edge Geometry?) is supposed to fill the hole and patch the jump; its chain is the one blocked on guard 0x0133AA80. Fork 0024 GCM_PARK_WATCH names whoever patches a park.
- 2026-10-19 09:27 agent-forkfix: HANDOFF: done=T023-1..5 patches (0012+0148+MFC, 0100 lwcond+test, 0166+0167, 0119/0131/0132, cellSpurs.h task errors 0x804109xx), dod3-reuse.md: ported table, RSX/GCM half ranked, dod3 src/tools classified; state=builds (build-0109), boot unchanged (STALLED since 21.6s, guard 0x0133AA80), tests: lwcond 14/14, host --threads OK, boot smoke PASS, apply_patches 40 commits clean; next=GCM ports for SARPBC's UE3 flip pattern (0049 PrepareFlip in FIFO order, 0018 user-command queue, 0014/0024 park handling: SARPBC parks on JUMP-to-self at io 0x8B144, see note), coordinator: renumber T023-* to 0018-0022, README rows, env vars into debugging.md, fix test_spurs_queue under NDEBUG; branch=worktree-agent-a2660a497ed6ae9e1
- 2026-10-19 09:27 agent-forkfix: DONE: Ported fork fixes as T023-1..5 (SPU task-thread stack UAF on POSIX + MFC slots, lwcond wakeups with a new test, PPU thread slot/stack reclaim, sys_fs overlay/hdd0/symlink readdir, cellSpurs.h task errors 0x804109xx). Tests: test_ppu_lwcond_wake 14/14 (old code fails 3), ps3recomp_host --threads OK, boot smoke PASS; 01.09 boot unchanged before/after (STALLED 21.6s, guard 0x0133AA80). dod3-reuse.md: RSX/GCM half ranked (PrepareFlip ordering 0049, user-command queue 0018, FIFO park 0014/0024 with SARPBC evidence) and dod3 src/tools classified with recipes.
