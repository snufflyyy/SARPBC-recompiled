# Reusing Drakengard 3's port (dod3-recomp + the soyjxck/ps3recomp fork)

T021 and T023, 2026-10-19. The runtime/syscall/SPU/lifter half of the fork is
inventoried and its generic fixes are ported (T021: 0013/0014, T023: the
`T023-*` patches below). T023 added the RSX/GCM half (a first pass, by
area) and the dod3-recomp `src/`/`tools/` tree, file by file. Background:
[reference-ports.md](reference-ports.md).

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

## Ported (T021 -> 0013/0014, T023 -> T023-*.patch)

| Patch | Source | What | Evidence |
|---|---|---|---|
| `0013-ppu-fs-open-flags.patch` (was T021-1) | fork `6371138` (0079), ppu_fs.cpp part, author soyjxck | `cellFsOpen` (runtime/ppu/ppu_fs.cpp, the path SARPBC's 20 cellFs imports use) used CREAT=0x200, TRUNC=0x400, APPEND=0x100. The SDK values are 0x40/0x80/0x200/0x400. Before this, `WRONLY\|CREAT` failed with ENOENT, `WRONLY\|CREAT\|TRUNC` created the file but **never truncated** it (a shorter save or config rewrite kept the old tail), and `O_APPEND` truncated. Adds O_EXCL | test below |
| `0014-sys-fs-h-open-flags-test.patch` (was T021-2) | ours | `runtime/syscalls/sys_fs.h` (lv2 `sys_fs_open`) had the octal SDK digits written as hex (CREAT 0x100, ...); the fork has the same bug. Fixed to octal. Adds `tools/test_ppu_fs_open_flags.py` + `runtime/ppu/tests/test_fs_open_flags.cpp` | test: 11/11 PASS with clang++. Not shown by a boot, because the 01.09 boot stalls (T019/T007/T020) before the game writes any file |

| `0018-spu-task-thread-stack-uaf.patch` | fork `d2ff9fb` (0012) + `2aaad6e` (0148), soyjxck; one commit of ours | The POSIX `spu_async_thread` (one per async SPU task, ~90 in SARPBC's first 6 s) now drops its stack range from the lock-line reserver set (`spu_coh_forget_range`) **and** the MFC slot table (`spu_mfc_forget_range`, ours: the fork predates it), as the Win32 thread does. Stack bounds from `pthread_getattr_np`; `_GNU_SOURCE` before the first header. 0148 needed its context fixed by hand (the fork has a `<pthread/qos.h>` include we lack) | boot below; no crash in 60 s before or after (the fork's crash was ~25 s in, on macOS) |
| `0019-lwcond-signals-wake.patch` | fork `f2cd69a` (0100), soyjxck, adapted; test ours | `sys_lwcond_signal/_all/_to` bump a per-lwcond generation (keyed by the `0x4Cxxxxxx` id create writes at +4) and wake waiters (striped condvars on POSIX, `WaitOnAddress` on Windows); `sys_lwcond_wait` sleeps until the generation moves, capped by `PS3_LWCOND_POLL_MS` (default 1) and the guest timeout. `PS3_LWCOND_SLEEP=1` = the old fixed 1 ms sleep. Adapted: our lwmutex is a bare semaphore, so the wait uses `ReleaseSemaphore`/`WaitForSingleObject` instead of the fork's `lwm_unlock_any`/`lwm_lock_wait`; MSVC links Synchronization.lib | `tools/test_ppu_lwcond_wake.py`: 14/14 PASS; the same fixture on the pre-port code fails 3 (57 returns from the wait per 60 ms hand-off) |
| `0020-ppu-thread-slots-stacks.patch` | fork `2c80040` (0166) + `9769173` (0167), soyjxck, both CLEAN | Ended PPU threads give back their slot (64) and their guest stack (pooled by size, zeroed). A thread created without `SYS_PPU_THREAD_CREATE_JOINABLE` (flags bit 0) is detached and frees itself, as on the console; joining it fails. Fixes three POSIX races at thread end. `PPU_THREAD_SLOTS=<n>` uses only n slots (to test turnover); `PPU_THREAD_END_STALL_US` (tests only). `sys_ppu_thread_create` now logs `flags=` and says when no slot is free | `ps3recomp_host --threads`: 600 threads (200 not joinable, 300 detached, 100 witnesses) OK, 3196 KB of stack cut for 600 threads (limit 8192 KB); `ps3recomp_boot_smoke` PASS (300-thread churn). SARPBC 01.09 creates **every** thread with `flags=0x1` (joinable) and joins RenderingThread (tid 2) 4 times, so the non-joinable rule changes nothing here; RenderingThread now reuses its stack |
| `0021-sys-fs-overlay-hdd0-symlinks.patch` | fork `585ff94` (0119), `ef46ea3` (0131), `f94a88e` (0132), soyjxck, all CLEAN | `PS3_VFS_OVERLAY=<dir>`: a regular file at the same path under `<dir>` (relative to `$PS3_VFS_ROOT`, which `src/main.cpp` sets to `<vfs>/dev_hdd0`) replaces the dump's, in all three path translators; first 32 logged as `[vfs] overlay:`. A `/dev_hdd0/...` path that exists under the root resolves there before the USRDIR flattening. `sys_fs_readdir` lists a symlinked folder (DT_LNK/DT_UNKNOWN) as a folder. Open-failure log names the guest path | builds; the boot opens the same 20 files. No overlay test yet (prerequisite for UE3 package patching, see menu_patch below) |
| `0022-spurs-task-error-codes.patch` | ours (T019's finding) | `CELL_SPURS_TASK_ERROR_*` in `libs/spurs/cellSpurs.h` were `0x80410721..32`; the SDK's are `0x804109xx` (AGAIN 01, INVAL 02, NOSYS 03, NOMEM 04, SRCH 05, NOENT 06, NOEXEC 07, PERM 09, BUSY 0A, FAULT 0D, ALIVE 0E, STAT 0F, ALIGN 10, NULL_POINTER 11), the values the literals in cellSpurs.c/cellSpursQueue.c already use. Core errors (`0x804107xx`) were right | ctest `spurs_task_exit_code_initialize`, `spurs_taskset_size` pass |

Boot, 01.09, `SPU_INTERP_UNLIFTED=1 BUILD_DIR=build-0109 tools/boot_check.sh 60 --version 0109`:
- before (main `bd42e4f`, 17 patches): `STALLED since 21.6s | last open GUIDCACHE.XXX@3.6s | pkgs 13 (GUIDCACHE last) | zlib 3147 | dumps 4 lit 4 distinct 1 | flips 9 | threads 13/9 alive | unresolved 0 | alerts open-fail,assert`
- after (+ T023-1..5): `STALLED since 21.6s | last open GUIDCACHE.XXX@3.6s | pkgs 13 (GUIDCACHE last) | zlib 3147 | dumps 4 lit 4 distinct 1 | flips 8 | threads 13/9 alive | unresolved 0 | alerts open-fail,assert`

Same frontier (job guard `0x0133AA80`), as expected: none of these touch it. The lwcond
speed-up should show in load times once the boot gets past the stall.

Pre-existing, found while testing (not caused by T023): `test_spurs_queue` (0015) hangs
in a **Release** ctest build, because its `assert(task_push_begin(...) == ...)` calls
vanish under NDEBUG; built without NDEBUG it passes. `spu_fnms_zero_extended`'s fixture
does not compile here. Upstream's `tools/title_hacks.py --check` reports
`lv2_register.c 11 -> 13` at the pin itself.

`tools/apply_patches.sh` applies the whole stack cleanly from `39a3629` (T021: 10 patches;
T023: 17 files + 5 = 40 commits).
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
| ~~1~~ | **ported (T023-1)** 0012 `d2ff9fb` + 0148 `2aaad6e` | POSIX `spu_async_thread` drops its stack from the lock-line reserver set (`spu_coh_forget_range`), as the Win32 one does. Add `spu_mfc_forget_range` too (the pin's Win32 path does both) | Use-after-free on Linux: the fork saw a crash ~25 s in. SARPBC spawns ~90 async SPU task threads in the first 6 s. 0012 applies **CLEAN** | runtime/spu (not audio): T021 | S |
| ~~2~~ | **ported (T023-2)** 0100 `f2cd69a` | lwcond signal/signal_all/signal_to wake their waiters (generation counter + striped condvars); wait capped by `PS3_LWCOND_POLL_MS` | The game imports `sys_lwcond_signal`/`wait`. In the pin a signal is a no-op and a wait is a 1 ms sleep. dod3's loads went 2-10x faster. Needs adapting: replace 0082's `lwm_unlock_any`/`lwm_lock_wait` with `ReleaseSemaphore`/`WaitForSingleObject` | runtime/ppu/ppu_sysprx.cpp: T021 | S |
| ~~3~~ | **ported (T023-3)** 0166 `2c80040` + 0167 `9769173` | Ended PPU threads give back their slot (64-slot table) and their guest stack. Non-joinable threads self-free. Fixes POSIX races. Includes smoke + `ps3recomp_host --threads` tests | SARPBC restarts RenderingThread repeatedly and makes SaveData/PhysX threads. A full table gives a silent EAGAIN and a hang. 0166 applies CLEAN; apply 0167 after it | runtime/syscalls/sys_ppu_thread.c, runtime/host: T021 | M |
| 4 | 0009 `1ef99ce` | sys_spinlock exchanges a 32-bit LONG, not an 8-byte `long` | Real LP64 bug, CLEAN. SARPBC does not import sys_spinlock, so low priority | ppu_sysprx.cpp | S |
| ~~5~~ | **ported (T023-4)** 0132 `f94a88e`, 0131 `ef46ea3` | sys_fs readdir: a symlinked folder lists as a folder (POSIX); a /dev_hdd0 path that exists resolves directly instead of through the USRDIR flattening | Our vfs is symlink-heavy (worktrees). Both CLEAN | runtime/syscalls/sys_fs.c | S |
| ~~6~~ | **ported (T023-4)** 0119 `585ff94` | `PS3_VFS_OVERLAY=<dir>`: patched game files laid over the dump | Prerequisite for UE3 package patching (dod3 `menu_patch`). CLEAN | sys_fs.c | S |
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

## RSX/GCM half of the fork (T023, first pass)

~80 commits (0014-0018, 0024, 0030-0032, 0042, 0046-0062, 0065-0068, 0072-0075, 0078,
0086-0087, 0090, 0093, 0095-0097, 0102-0109, 0112-0126, 0137-0143, 0149, 0151, 0156,
0160-0164, 0168, 0173). Nearly all CONFLICT against the pin, because upstream rewrote the
same files after the fork's base; so the check below is by **feature in the pin's code**,
not by `git apply`.

**Why it matters for SARPBC.** 01.09 imports exactly the GCM set those fixes are about:
`cellGcmSetPrepareFlip`, `cellGcmSetFlipImmediate`, `cellGcmSetUserHandler`,
`cellGcmSetVBlankHandler`, `cellGcmSetFlipHandler`, `cellGcmSetGraphicsHandler`
(analysis `EBOOT.imports.json`). The boot log shows `SetPrepareFlip(bufferId=0/1)` x9 and
`SetFlipImmediate` x8 during loading, and the three handlers registered
(vblank `0x012025A8`, flip `0x012025A0`, user `0x012025B0`). That is the UE3 PS3 RHI pattern
the fork's 0049 describes: PrepareFlip returns an id, a user command hands it to the vblank
handler, which calls SetFlipImmediate.

### What the pin already has (do not port)

| Fork | Feature | Pin |
|---|---|---|
| 0015 | GCM_SET_USER_COMMAND (0xEB00) reaches the cellGcmSetUserHandler handler | `cellGcmQueueUserCommand` from the walker (cellGcmSys.c ~l.1885), delivered by `ppu_gcm_pump` |
| 0032 | an explicit MAIN location resolves through the IO table first | `cellGcmResolveLocated` (IO first, then the offset guess) |
| 0048 | a draw that samples its own colour target samples a copy | backend op `color_snapshot` (rsx_draw_engine.h l.233) |
| 0053/0055/0057 (parts) | depth-compare shadow units, sRGB texture gamma | `rsx_fp_shadow_desc`, `rsx_fp_texture_gamma_units`, `_rsx_gamma_input` in rsx_fp_decompiler.c. Whether the pin's compare order is the RSX's "texel OP ref" (0055) is **not checked** |
| 0045 | SET_TRANSFORM_CONSTANT window | applies in reverse (T021) |

### Missing at the pin and generic: ranked for SARPBC

| # | Fork | What | Why SARPBC | Files | Effort |
|---|---|---|---|---|---|
| 1 | 0049 `gcm: prepared flips execute in FIFO order` | `cellGcmSetPrepareFlip` writes a marker into the FIFO and returns the id; the drain flips at the marker, in order with the draws; `SetFlipImmediate` of a prepared buffer does not flip twice. Also NV0039 copies incl. the report-memory source (`cellGcmSetTransferReportData`) | The pin's PrepareFlip flips **on the spot** (cellGcmSys.c ~l.2477: sets the current buffer, calls the flip handler). With the UE3 pattern above that presents a buffer still being drawn and flips buffer 0 every frame: dod3 saw 3 presents in 5 white/cyan/half-drawn. Expect the same flicker once SARPBC renders scenes | cellGcmSys.c, rsx_dispatch.c, rsx_draw_engine.c (fifo flip entry) | L (280 lines, 25 hunks, conflicts) |
| 2 | 0018 `gcm: queue user commands` | every user command queued in order (not one coalescing slot) | The pin keeps **one** pending user command (`GCM_USER_PENDING_STORE`, a single u64), so a second command before the pump runs overwrites the first. UE3 sends the flip id this way | cellGcmSys.c | S |
| 3 | 0014 `GCM_FIFO_NO_RESYNC=1` (+ 0024 `GCM_PARK_WATCH=1`) | keep waiting on a JUMP-to-self park instead of resyncing to `put` (dropping everything between); 0024 logs who patches a park | **Seen in SARPBC 01.09**: without it the walker "stuck-get" resyncs 3 times during loading (0x8C784->0x957BC, 0x95BAC->0x9BE18, 0xDAD7C->0xE9D4C), skipping ~120 KB of commands. With it (local experiment, not committed) the FIFO sits on a JUMP-to-self at io `0x0008B144` (word `0x2008B144`) right after vertex-array setup (methods 0x1740/0x1680/0x1FC0) and alpha state, and nothing patches it in 60 s; the stall itself is unchanged. Guess: an SPU job (Edge Geometry?) is meant to fill the hole and patch the jump, and its chain is the one waiting on guard `0x0133AA80`. Hand to T022 | cellGcmSys.c, sys_timer.c | S |
| 4 | 0112 `a flip whose marker does not fit fires at its FIFO position` | needs 1 | a 33 ms frame every 10-20 s in dod3 | cellGcmSys.c | M |
| 5 | 0059 + 0062 | report copies (NV0039 from report memory) run after the GPU work behind them; stop mirroring reports into local `0x0E000000` | occlusion queries: objects vanish for a frame. The pin's NV0039 is still "not implemented yet -- log first sightings" (`[GCM2D-UNH]`; none logged yet, the boot stalls first) | cellGcmSys.c, rsx_draw_engine.c | M |
| 6 | 0096 + 0111 (`g_lv2_usleep_hook`) | ring-full recycle kicks the walker and waits on its progress; every guest usleep kicks the walker | render-thread GPU-fence waits poll a label every 200 us; dod3 +8-18% fps in its heaviest scene. Needs a host "kick" in src/main.cpp | cellGcmSys.c, sys_timer.c, src/main.cpp | M |
| 7 | 0139 | `ppu_gcm_pump` reads the pending bits before taking the pump flag | 2% of dod3's main thread | cellGcmSys.c | S |
| 8 | 0050 (parts) | copy engine on subchannel 1 only; NV0039 methods kept out of the 3D register file; alpha-ref float formats 11/12/13 | wrong blend/alpha state after a copy | cellGcmSys.c, rsx_fp_decompiler.c | M, check against the pin first |
| 9 | 0067 | depth/stencil clears honour the scissor (UE3 clears each region of its shadow atlas with a scissored clear) | missing character shadows | rsx_draw_engine.c + a backend op | M |

Draw-engine diagnostics worth having when SARPBC draws scenes: 0042 (`RSX_DRAW_STATS`,
`RSX_DRAW_TRACE_FRAME`, `RSX_SURF_DUMP_DIR`), 0030/0036 (`TEX_DUMP_DIR`), 0072 (`[frametime]`),
0161. Performance, later: 0066 (vertex fetch by attribute, +23-37% replay speed), 0068
(vertex cache, -40% draw-engine CPU), 0087/0090/0109 (texture write-watch with `mprotect`,
needs `include/ps3emu/vm_watch.h` + `runtime/platform/vm_watch.c`, neither in the pin).

**The fork's Vulkan engine (0117/0149) is not a drop-in for Linux.** 0117's
`rsx_vulkan_engine.c` + `rsx_vulkan_encode.inc` is a batched engine (record stream,
timeline semaphore, dynamic rendering, Vulkan 1.3) that mirrors the fork's D3D12 engine,
and it is `#if defined(_WIN32) && defined(PS3RECOMP_HAVE_VULKAN)`. 0149 only makes
upstream's `rsx_vulkan_backend.c` (the one SARPBC uses: synchronous, one command buffer
per clear/draw/present, "slow and trivially correct") build on the fork's SPIR-V
translator contract. Porting the engine to Linux (drop vulkan-1.dll, add an SDL/X11
surface) is a performance task for after the game renders; not now.

Not relevant to SARPBC: Metal (0017, 0052, 0108, 0115-0116, 0122, 0125-0126, 0141-0143),
D3D12 (0078, 0086, 0093, 0097, 0102, 0106-0107, 0113, 0137-0138, 0173), Windows UI/AA/
resolution (0118, 0120-0121, 0123-0124), and rsx_capture/replay (0056, 0060, 0145) unless
we adopt the fork's replay harness.

## dod3-recomp `src/` and `tools/` (T023)

Classes: **GENERIC** (any title), **UE3** (any UE3 PS3 title, addresses differ),
**DOD3** (this game only), **PLATFORM** (Windows/macOS front end). Most UE3 pieces need the
fork's lifter `--hook <addr>` (0088/0089/0091/0092/0171, owned by T009) to replace a lifted
function. dod3's engine is UE3 package version **860** (2013); SARPBC's is **539** (2008),
so structure offsets and function shapes will differ: treat dod3's addresses as a map of
*what* to find, never *where*.

| File | Lines | Class | What | For SARPBC |
|---|---|---|---|---|
| `src/main.cpp` frame clock | 2075 | UE3 / GENERIC | vblank/flip ticker on real time; the FIFO walker sleeps and is **kicked by every guest usleep** (`g_lv2_usleep_hook`, fork 0111): UE3's render thread polls a GPU fence label every 200 us (`func_008B0C70` in dod3) | with GCM item 6 above. Our src/main.cpp uses the template's clock |
| `src/main.cpp` DOD3_FPS | | UE3 | replaces `UEngine::GetMaxTickRate` (the frame limiter `FEngineLoop::Tick` sleeps until 1/GetMaxTickRate s passed; dod3 `func_008EDC78`); checks the float 1.0 it expects before patching | recipe (untested): the limiter is the `sys_timer_usleep` caller in the game thread's tick loop, and the value it sleeps toward comes from a virtual call on the engine object (GetMaxTickRate). Config key names live in the packages, not the EBOOT (no `SmoothedFrameRate` string in 01.09), so find it from code |
| `src/patches/load_idle.cpp` | 97 | UE3 | while no scene is drawn and packages are pending, spend the frame limiter's sleep in `ProcessAsyncLoading` (UE3 loading is paced by frames, not work: 265 frames for dod3's first chapter) | after the boot works; same recipe as DOD3_FPS plus `UObject::StaticTick` |
| `src/patches/gc.cpp` + `gc_native.cpp` | 273 + 988 | UE3 | `UObject::CollectGarbage` wrapped, its reachability pass (`FArchiveRealtimeGC::PerformReachabilityAnalysis`) hand-translated (18-20 ms -> less per heavy GC); deferred purge at the top of `FEngineLoop::Tick` | perf, later. Recipe in gc_native.cpp's header (GObjObjects, token stream at class +0x150 in v860) |
| `src/cpu/uscript.h` | 85 | UE3 | the UnrealScript VM pieces a replaced native needs (FFrame +0x14 Object, +0x18 Code; GNatives 8 bytes per opcode; `FFrame::Step`) | offsets may differ in v539: check `FFrame` from an exec thunk |
| `src/patches/sysset.cpp` | 499 | UE3 | UE3 `FSystemSettings` (from `[SystemSettings]` in the engine INI) changed at run time: the `{name, &field}` tables `LoadFromIni` reads give each key's offset | SARPBC has `SystemSettings`, `_2P/_3P/_4P` sections (split screen). Useful for graphics options |
| `src/patches/spu_hooks.c` | 497 | UE3 | native fast path for the LZF copy loops of UE3's **ShaderPatching** SPU job (~200 runs a frame in dod3) | the string `ShaderPatching` is in SARPBC's EBOOT: likely the same job. Needs `--native-hook` in the SPU lifter (tools/lift_spu.sh) |
| `src/patches/edgezlib.cpp` | 151 | GENERIC (Edge) | hooks `edgeZlibAddInflateQueueElement` (lifter hook) and inflates on the PPU | ours (`src/overrides/edgezlib.cpp`) does the same at the LFQueue push HLE and works (3147 requests). Nothing to take |
| `src/patches/prompts.cpp` + `tools/prompt_atlas.py` + `src/res/prompts/*` | 448 | UE3 idea / DOD3 data | swaps the button-glyph atlas texture by content hash via `rsx_draw_engine_set_texture_standin` (fork 0151) | button prompts by pad type (T008 follow-up); needs 0151 and our own atlas art |
| `src/patches/menu_patch.cpp` + `tools/menu_patch.py` + `tools/ue3/*` | 351 + 477 + ~900 | UE3 method / DOD3 data | patches UnrealScript functions of the script package and serves the result through `PS3_VFS_OVERLAY` (now ported, T023-4) | the method is reusable; `tools/ue3/upk.py`/`script.py` read v860 packages and need v539 summary/bytecode changes first |
| `src/patches/collision_native.cpp` + `tools/lift_native.py` | 3032 + 144 | DOD3 output / GENERIC tool | one hot lifted function turned into native C++ (frame slots to locals) | the tool is generic (needs fork `--nonvolatile-locals` + `tools/ppu_frame_locals.py`, T009) |
| `src/cpu/hot.cpp`, `src/cpu/eboot.h` | 182, 126 | DOD3 | hook table and both versions' addresses | the pattern (one header of every address per EBOOT version) suits our 01.02/01.09 |
| `src/cpu/spu_check.h`, `src/cpu/cycles.h` | 69, 24 | GENERIC | run lifted SPU code to a pc and compare native vs lifted; TSC timer | with any SPU hook |
| `src/apu/*` (`mp3_native.c`, `mp3dec*.c`, `msdsp_hooks.c`, `mp3_standin.h`) | ~1900 | GENERIC (MultiStream) | native MP3 behind a stand-in SPU image; biquad fast path in MultiStream's DSP plugin | T007 (audio) |
| `src/input/kbm.cpp`, `camera.cpp` | 358, 192 | PLATFORM / DOD3 | keyboard+mouse as a pad; mouse as camera stick | kbm done in T008; camera is per game |
| `src/kernel/spurs_queue.cpp`, `spurs_lfqueue.cpp`, `tools/gen_libsre.py` | 208, 261, 170 | GENERIC | SPURS queue / LFQueue | T019 (ported as 0015) |
| `src/kernel/dlc.cpp` | 91 | DOD3 | writes the JP voice DLC's file lists | no |
| `src/install/*` | ~2400 | PLATFORM | PKG/SELF/ISO installer with **built-in keys** (`keys_builtin.h`) | **do not port** (AGENTS rule 1: keys go nowhere). We decrypt with RPCS3 (tools/decrypt.sh) |
| `src/ui/*`, `src/os/*`, `src/res/app.*` | ~2600 | PLATFORM | Win32/Cocoa settings menu, first-run wizard, icons | a Linux front end later, if at all |
| `tools/eboot_diff.py`, `addr_map.py`, `data_map.py` | 80, 41, 87 | GENERIC | map functions/code/data addresses between two builds (masks branch targets and address-forming immediates) | **useful now**: 01.02 -> 01.09 address map, so findings on one version carry to the other |
| `tools/make_spu_overlays.py`, `lift_spu.sh` | 286, 69 | GENERIC | SPU overlay lifting, `--native-hook` | we have our own overlay lift (0008); compare when hooking SPU code |
| `tools/compare_frames.py`, `hud_visible.py`, `ppm*.py`, `replay_regress.sh` | small | GENERIC | frame comparison and replay regression | with the fork's rsx_capture/replay, if adopted |
| `tools/autoplay.sh`, `live_bench.sh`, `bench_summary.py`, `run_timed.sh`, `stack_summary.py` | small | GENERIC (dod3 paths) | scripted runs and benchmarks | ideas for tools/boot_check.sh |
| `tools/gen_mp3_tables.py` | 208 | GENERIC | MP3 decoder tables | T007 |
| `tools/package_*.sh`, `build_*.bat`, `make_icon.py`, `capture_*.bat` | small | PLATFORM | packaging | no |

### Environment switches added by T023's patches

`PS3_LWCOND_POLL_MS=<ms>` (lwcond wait cap, default 1), `PS3_LWCOND_SLEEP=1` (old fixed
sleep), `PPU_THREAD_SLOTS=<n>` (use n of the 64 thread slots), `PPU_THREAD_END_STALL_US`
(tests only), `PS3_VFS_OVERLAY=<dir>` (files laid over the dump). They belong in
docs/debugging.md's env table too (outside T023's scope; coordinator).

## Notes

- The 01.09 lift has `TODO` words that are probably data, not unlifted instructions:
  `vmx_x531 v0,v17,v2` x470, `op31_x207` x35, `op31_x1023` x17, `op31_x547` x1
  (identical operands repeated). Worth a look in T010.
