# Reusing Drakengard 3's port (dod3-recomp + the soyjxck/ps3recomp fork)

T021, 2026-10-19. **Partial**: paused for usage. The runtime/syscall/SPU/lifter half
of the fork is inventoried. The RSX/GCM half and the dod3-recomp `src/` tree are not
written up yet (see "Not yet inventoried"). Background: [reference-ports.md](reference-ports.md).

## How the fork relates to our pin

- The fork `soyjxck/ps3recomp` is 174 non-merge commits on top of upstream `5244db9`
  (v0.13.0), which it merged at `4a6992a`. Our pin `39a3629` (v0.15.0+2) is **268
  upstream commits later**, and several of the fork's fixes reached upstream through
  other contributors' PRs. Check the pin's *code* before porting anything; a failed
  `git apply` says little either way.
- How to repeat the check (read-only):
  `git -C <fork> format-patch -o forkpatches upstream/master..master`, then for each patch
  `git apply --check` / `--check -R` / `--check -3` inside `external/ps3recomp`.
  Each patch is checked alone, so a CONFLICT is often just a missing earlier fork commit.
  The worktree guard rejects compound git commands, so keep the loop in a script.
  `patch(1)` is not installed here.
- Patch numbers below (`NNNN`) are positions in that `format-patch` series (oldest = 0001).

## Ported (patches/ps3recomp/T021-*.patch)

| Patch | Source | What | Evidence |
|---|---|---|---|
| `T021-1-ppu-fs-open-flags.patch` | fork `6371138` (0079), ppu_fs.cpp part, author soyjxck | `cellFsOpen` (runtime/ppu/ppu_fs.cpp, the path SARPBC's 20 cellFs imports use) used CREAT=0x200, TRUNC=0x400, APPEND=0x100. The SDK values are 0x40/0x80/0x200/0x400. Before this, `WRONLY\|CREAT` failed with ENOENT, `WRONLY\|CREAT\|TRUNC` created the file but **never truncated** it (a shorter save or config rewrite kept the old tail), and `O_APPEND` truncated. Adds O_EXCL | test below |
| `T021-2-sys-fs-h-open-flags-test.patch` | ours | `runtime/syscalls/sys_fs.h` (lv2 `sys_fs_open`) had the octal SDK digits written as hex (CREAT 0x100, ...); the fork has the same bug. Fixed to octal. Adds `tools/test_ppu_fs_open_flags.py` + `runtime/ppu/tests/test_fs_open_flags.cpp` | test: 11/11 PASS with clang++. Not shown by a boot, because the 01.09 boot stalls (T019/T007/T020) before the game writes any file |

`tools/apply_patches.sh` applies the whole stack (10 patches) cleanly from `39a3629`.
Not rebuilt or booted after the port. Baseline 01.09 before the port:
`boot_check 2026-10-19 00:02 v01.09 36a324e 60s: STALLED since 22.1s | last open GUIDCACHE.XXX@4.1s | pkgs 13 (GUIDCACHE last) | zlib 3147 | dumps 4 lit 4 distinct 1 | flips 18 | threads 13/9 alive | unresolved 4 | alerts open-fail,blocked`.

## Already in our pin (do not port)

| Fork commit | Fix | Where it is in the pin |
|---|---|---|
| 0003 `0eb2734` | sys_lwcond_t is two be32 words | ppu_sysprx.cpp `sys_lwcond_create` |
| 0008 `96c0c92` | lwmutex/lwcond lock for real on POSIX | ppu_sysprx.cpp (no `_WIN32` guards) |
| 0013 `da70e07` | lwmutex trace clock on POSIX | `lwm_now_us` |
| 0005 `f93af17` | real cellOvis API | our patch 0007 |
| 0027 `ec042fd` | stvlx/stvrx lifted | ppu_lifter.py ~l.2555 |
| 0043/0044 | callee-save epilogue snapshot; vcmpequb./h. set CR6 | `_is_epilogue_restore`, tests present |
| 0064 `e28b286` | vpkswss + big-endian vector packs | lifted code calls `ppu_vmx.h` `VMX_PACK` helpers (BE lanes). The inline branches in ppu_lifter.py ~l.3548 still cast `int16_t*`, but the 01.09 lift does not use them (it emits `vmx_vpkuhus`/`vmx_vpkuwus` x91 each) |
| 0045 `0319c85` | SET_TRANSFORM_CONSTANT 32-dword window | applies in reverse |
| 0098 (part) | job contexts release their MFC slot | `spu_mfc_release` in spurs_job.c / spu_lifted_job.h |
| 0011/0016/0020/0041 (sys_memory part) | slots, overflow window, freed-range reuse | our patch 0005 (range table, 4096 ranges). The fork's 0x70000000 overflow window is not ported; only needed if 01.09 passes 256 MB |

## Still missing and generic: ranked port list (next session)

| # | Fork commit(s) | What | Why SARPBC | Area / owner | Effort |
|---|---|---|---|---|---|
| 1 | 0012 `d2ff9fb` + 0148 `2aaad6e` | POSIX `spu_async_thread` drops its stack from the lock-line reserver set (`spu_coh_forget_range`), as the Win32 one does. Add `spu_mfc_forget_range` too (the pin's Win32 path does both) | Use-after-free on Linux: the fork saw a crash ~25 s in. SARPBC spawns ~90 async SPU task threads in the first 6 s. 0012 applies **CLEAN** | runtime/spu (not audio): T021 | S |
| 2 | 0100 `f2cd69a` | lwcond signal/signal_all/signal_to wake their waiters (generation counter + striped condvars); wait capped by `PS3_LWCOND_POLL_MS` | The game imports `sys_lwcond_signal`/`wait`. In the pin a signal is a no-op and a wait is a 1 ms sleep. dod3's loads went 2-10x faster. Needs adapting: replace 0082's `lwm_unlock_any`/`lwm_lock_wait` with `ReleaseSemaphore`/`WaitForSingleObject` | runtime/ppu/ppu_sysprx.cpp: T021 | S |
| 3 | 0166 `2c80040` + 0167 `9769173` | Ended PPU threads give back their slot (64-slot table) and their guest stack. Non-joinable threads self-free. Fixes POSIX races. Includes smoke + `ps3recomp_host --threads` tests | SARPBC restarts RenderingThread repeatedly and makes SaveData/PhysX threads. A full table gives a silent EAGAIN and a hang. 0166 applies CLEAN; apply 0167 after it | runtime/syscalls/sys_ppu_thread.c, runtime/host: T021 | M |
| 4 | 0009 `1ef99ce` | sys_spinlock exchanges a 32-bit LONG, not an 8-byte `long` | Real LP64 bug, CLEAN. SARPBC does not import sys_spinlock, so low priority | ppu_sysprx.cpp | S |
| 5 | 0132 `f94a88e`, 0131 `ef46ea3` | sys_fs readdir: a symlinked folder lists as a folder (POSIX); a /dev_hdd0 path that exists resolves directly instead of through the USRDIR flattening | Our vfs is symlink-heavy (worktrees). Both CLEAN | runtime/syscalls/sys_fs.c | S |
| 6 | 0119 `585ff94` | `PS3_VFS_OVERLAY=<dir>`: patched game files laid over the dump | Prerequisite for UE3 package patching (dod3 `menu_patch`). CLEAN | sys_fs.c | S |
| 7 | 0071 `260ccb8`, 0111 `f606486` | `PPU_WAITPROF` wait profiler; `g_lv2_usleep_hook` / `g_lv2_usleep_pre` | Diagnostic for our stalls. The hooks are the base of dod3's frame clock and its GC-in-limiter-sleep. ppu_hle.cpp overlaps T020, so coordinate | T012 follow-up | M |
| 8 | 0127 `c5763ce` | Guest clocks that stand still while paused (`ps3_guest_ticks`) | Pause on focus loss. Later | runtime/sys_timer | M |
| 9 | 0038 `8a6c1d9` (spu_dma.h part) | acquire before a SPU GET, release before a PUT | x86 is TSO, so this only stops compiler reordering. Low | runtime/spu | S |

## Owned by other tasks (inventory only: hand to the owner)

- **T019 (SPURS)**: 0004 tasksets per instance (LFQueue signal word), 0006 a second
  PPU EventFlagWait gets BUSY (CLEAN), 0019 `SPURS_DYNPORT_LOW` (lv2 picks the lowest
  free port), 0021/0022/0040/0041 task slot claim/publish races (duplicate task runs
  give stale queue pops: dod3's PhysX), 0023 RunJobChain overlap queues a re-walk,
  0025 `SPURS_JC_SYNC`, 0026 `SPURS_JC_DONE_EVENTS=0`, 0029/0033/0034 job context reuse
  and resume a halted chain at its END slot (big perf), 0035/0099 tasks in creation
  order and taskset maxContention (PhysX=3), 0069/0085/0110 pooled task threads and
  local store reuse, 0077 second SPU line-commit hook (wakes PPU queue waiters).
  **0079's SPURS part: a job guard nobody ever notified waits 200 ms
  (`SPURS_GUARD_FIRST_MS`), not 20 s.** Our 01.09 baseline logs
  `guard 0x0133AA80 still closed after 20 s -- chain gives up` at 22.1 s, exactly where
  boot_check says STALLED. Check this first.
- **T007 (audio)**: 0010 overlay regions by content signature (MultiStream DSP plugins),
  0058/0080/0081 cellAudio pacing/read lag, 0076 audio QoS and AUDIO_GAPS, 0165 (audio
  half), dod3 `src/apu/` (native MP3 behind a stand-in SPU image).
- **T008 (input)**: 0028/0063/0094/0135/0136/0152/0154/0172 cellPad (SDL2 thread,
  kbm as pad 0, PAD_FILE/PAD_NO_HOST), 0153 rsx_host_mouse, dod3 `src/input/`.
- **T009 (lifter perf)**: 0031/0037/0074/0084/0170 `ppu_vm_fast.h` page-table fast path
  (+80% fps in dod3), 0088/0089/0091/0092/0171 `--nonvolatile-locals`/`--hook`,
  0150/0155 `tools/ppu_frame_locals.py`, 0083 env cache.
- **T018 (clean exit)**: 0165 SDL leaves SIGINT/SIGTERM alone (in cellPad.c/cellAudio.c,
  so coordinate with T007/T008). Note: on Linux/Vulkan the window *is* SDL's, so it needs
  a pump that acts on SDL_QUIT.

## Not yet inventoried (next session)

1. **RSX/GCM commits** (~80: 0014-0018, 0024, 0030-0032, 0042, 0046-0062, 0065-0068,
   0072-0075, 0078, 0086-0087, 0090, 0093, 0095-0097, 0102-0109, 0112-0126, 0137-0143,
   0149, 0151, 0156, 0160-0164, 0168, 0173). The questions: is the fork's Vulkan engine
   (0117/0149) worth porting over upstream's `rsx_vulkan_backend.c`? Which cellGcmSys
   fixes (flip order 0049, user commands 0015/0018, copy-engine subchannel 0050, MAIN
   through the IO table 0032, ring-full recycle 0096, flip marker 0112) are missing at the
   pin? How do texture write-watch (0087/0090/0109) and occlusion sync (0059) depend on vm
   changes?
2. **dod3-recomp `src/` and `tools/`** (22.7k lines): per-file class
   (GENERIC/UE3-GENERIC/DOD3/PLATFORM), and for each UE3-generic piece (frame clock in
   `src/main.cpp`, `GetMaxTickRate`/DOD3_FPS, Bink tick, `load_idle.cpp`,
   `gc*.cpp`, `collision_native.cpp`, `uscript.h`, `prompts.cpp`, `spu_hooks.c`,
   `menu_patch.cpp` + `tools/ue3/`) a recipe for finding its addresses in our v539 EBOOT.
   `src/kernel/spurs_queue.cpp`/`spurs_lfqueue.cpp` and `tools/gen_libsre.py` go to T019.
   `src/patches/edgezlib.cpp` (151 lines) is worth diffing against our
   `src/overrides/edgezlib.cpp` (Adler-32 check mode).

## Notes

- The 01.09 lift has `TODO` words that are probably data, not unlifted instructions:
  `vmx_x531 v0,v17,v2` x470, `op31_x207` x35, `op31_x1023` x17, `op31_x547` x1
  (identical operands repeated). Worth a look in T010.
