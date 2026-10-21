# Reusing Drakengard 3's port (dod3-recomp + the soyjxck/ps3recomp fork)

T021 and T023, 2026-10-19; inventory completed 2026-10-20 (sonnet-2). Everything in the fork
and in dod3-recomp is now covered: **all 208 fork commits** (section "Every fork commit") and
every file of the dod3-recomp tree (section "dod3-recomp tree"). Background:
[reference-ports.md](reference-ports.md).

**Port next** comes first; the inventory follows. This round wrote no patches: T043 is
rebasing the patch stack onto upstream v0.16.0 (`749182e`) and the patch files are being
renumbered, so ours are named here by slug (`gcm-user-command-queue`), never by number.

## What was compared

- **Fork** `soyjxck/ps3recomp` at `93dbfdd` (2026-10-20): `git log --no-merges
  up/master..HEAD` against upstream v0.16.0 lists **208 commits**. `git cherry` marks all 208
  as not patch-equivalent (the fork rewrote history around its merges of upstream), so
  "already upstream" was decided by reading v0.16.0's *code*, not by `git apply`.
- **Port** `soyjxck/dod3-recomp` at `f6c24bf` ("0.3.0 alpha", 2026-10-20, 199 commits). Our
  `audio_mp3` and `input_kbm` overrides were ported from its earlier `96df4c3`.
- **Numbering.** The first T021/T023 passes numbered fork commits `0001..0173` (a position in
  `format-patch 5244db9..master`). That series is gone: since then the fork merged upstream
  v0.15.0 and added 35 commits (`29d843d` .. `93dbfdd`). This doc uses **fork shas**; old
  `NNNN` references in task notes map to the sha in the same row of the old tables
  (`6eb35c0` was 0049, `9d17419` 0168, `bbcf9a5` 0173).
- **Classes.** GEN = generic runtime/HLE/engine code. UE3 = any UE3 PS3 title, guest
  addresses must be re-found (dod3 is package version 860, SARPBC 539). DOD3 =
  Drakengard-specific. PLAT = Windows/macOS only. DIAG = diagnostic. CI = test plumbing.
- **Status.** ported = in our patch stack or `src/overrides`. in-pin = our v0.15.0 pin
  already had it. upstream = v0.16.0 has it (arrives with the bump). missing = applicable or
  possibly applicable, not ported. n/a = Windows/macOS, Drakengard-only, or SARPBC does not
  use the API.
- **Result.** 208 commits: 35 ported, 12 in-pin, 12 upstream (so **24 are already in v0.16.0**,
  12 of them in our pin; a few ported ones are also partly upstream), 87 missing (many of
  them diagnostics, test plumbing or the T009 lifter line), 62 n/a.
- To repeat the check: clone both repos and upstream, `git checkout 749182e` in the upstream
  clone, `git fetch` it into the fork clone as a remote, then `git log --no-merges
  up/master..HEAD`. Plain `git` is the only tool needed; the worktree guard rejects compound
  commands, so use `git -C <abs path>` and one command per call.

## Port next (ranked)

Ranking follows the project's priorities (visual bugs first, then a steady 30 fps in game).
Every "v0.16.0" claim below was checked in the v0.16.0 source, with file:line. Items 1, 2 and
8 are small and independent: good first patches after the T043 bump.

| # | Item (fork commit) | What it fixes for SARPBC | Repo area it touches | Effort |
|---|---|---|---|---|
| 1 | **Alpha-test reference for float colour targets** (`3f20f13`, one hunk) | `rsx_fp_alpha_ref` decodes surface formats 14/15/16 as float; the SDK's are 11 (F_W16Z16Y16X16), 12, 13. The arena scene goes into an FP16 target (cfmt 11, T045 log), so an alpha-tested draw into it compares against `(raw & 0xFF)/255` instead of the half-float ref. Guess: wrong cut-outs (fences, foliage, particles). Not yet seen as a symptom | ps3recomp `libs/video/rsx_fp_decompiler.c` (+ `test_fp_decompiler.c`): new patch | S |
| 2 | **Zero vertex stride = constant attribute** (`0eee9dd`, 13 lines in `rsx_vertex_compact.c`) | v0.16.0 reads stride 0 as tightly packed (`rsx_vertex_compact.c:130-131`). UE3 binds a shared white vertex-colour stream with stride 0, so vertex N reads the N-th element past it: every mesh without its own vertex colours drew black in dod3 (most props). SARPBC is UE3 too. (`rsx_fetch_attrib`, `rsx_vertex_fetch.c:41`, treats stride 0 as the constant register, a third behaviour) | ps3recomp `libs/video/rsx_vertex_compact.c` (+ `test_vertex_fetch_plan.c`) | S |
| 3 | **Wake the FIFO walker on every guest `usleep`** (`260ccb8` `g_lv2_usleep_hook` in `sys_timer.c`, 8 lines; `2b6ae46` ring-full kick; `bfa00d4` `g_gcm_label_write_hook`; dod3 `src/main.cpp:226-340` for the host half) | Steady 30 fps. The render thread's GPU fence wait (`func_000DD014`, 250 us `sys_timer_usleep` polls, unreal-engine-3.md) waits for a label only a drain writes. Our `frame_clock` drains every 4 ms (`FRAME_CLOCK_SLEEP_MS`, `src/main.cpp:199-260`) and the menu profile shows ~4.6 ms idle in `Sleep(4)` plus ~8 ms of GPU waits per 31 ms frame (subsystems.md). dod3: "cost the render thread up to the whole 4 ms sleep, several times a frame". v0.16.0's #353 only delivers GCM *callbacks* at usleep, it does not wake the walker | ps3recomp `runtime/syscalls/sys_timer.c` (patch), `src/main.cpp` frame_clock (a kick condvar, then drop the 4 ms cadence), optionally `cellGcmSys.c` | S-M |
| 4 | **Fetch vertices attribute by attribute** (`df94c65`; self-checking with `RSX_VFETCH_CHECK=1`) | Steady 30 fps in menus and play. The menu's biggest CPU item is the draw engine's vertex decode (`rsx_vertex_fetch_one` per vertex, `rsx_draw_engine.c:1926`; ~18 of 31 ms with `eng_texture_content_hash`, which #375 cuts in the bump). dod3: replays 23-37% faster, byte-identical. Self-contained (182 lines) | ps3recomp `libs/video/rsx_draw_engine.c`, `rsx_vertex_compact.{c,h}` | S-M |
| 5 | **Prepared flips execute at their FIFO position** (`6eb35c0`, plus `6cba82c` when the marker does not fit) | Presenting a buffer still being drawn, flipping the wrong buffer. Our patch `gcm-prepare-flip-returns-id` returns the id and stops flipping on the spot, but the flip still happens when the user handler calls `SetFlipImmediate`, not when the drain reaches the end of the frame's draws. Expect half-drawn presents under load (dod3: 3 in 5 presents). v0.16.0 already has the machinery to reuse: `GCM_FLIP_MARKER` written into the ring and handled by the drain for `SetFlipCommand` (`cellGcmSys.c:2582-2640`, `1516`, `1873`, #343), so the port is smaller than the fork's 285 lines | ps3recomp `libs/video/cellGcmSys.c`, `rsx_dispatch.c`, `rsx_draw_engine.c` | M |
| 6 | **Even presents + a steady frame cap** (`9d17419` `rsx_present_pace.{c,h}`; dod3 `fps_get_max_tick_rate`, `src/main.cpp:395-845`) | The goal itself. `rsx_present_pace` holds each finished frame to an even schedule (a 3x-variation margin, off unless enabled or `RSX_PRESENT_PACE=1`); 1-7% of presents more than 15% off the previous one, 40-65% without. Self-contained, but the fork wires it into its own Windows engines only; our Vulkan backend needs one call before `vkQueuePresentKHR` (`rsx_vulkan_backend.c:527`, FIFO present mode at `:1808`). Second half (UE3): replace `UEngine::GetMaxTickRate` so the engine's 22-30 fps smoothing cannot move the cap. See "Frame pacing recipe" below. Hypothesis: part of the menu's 26-32 fps windows is the engine's own smoothing following slow frames | ps3recomp new `libs/video/rsx_present_pace.{c,h}` + `rsx_vulkan_backend.c`; `src/overrides/` (new `frame_rate.cpp`: the GetMaxTickRate replacement) | M |
| 7 | **(depth copies cropped: DONE by SARPBC's own `0064-depth-snapshot-crop`, T054; scissored clears still open)** **Scissored depth/stencil clears; depth copies cropped to the sampled texture** (`1f4997a`, `691962e`) | Missing or flickering shadows. v0.16.0 clears the whole target whatever the scissor (`rsx_draw_engine.c:2742-2778`) and sizes depth targets to at least the canvas (`:838-839`), so a 512x512 shadow map sits in the corner of a screen-sized depth image and its 0..1 coordinates miss. dod3 saw exactly that for UE3's per-object shadow atlas. Our car shadow (T045) is already right; check other shadows (second car, ball) with the pass capture first | ps3recomp `libs/video/rsx_draw_engine.c`, `rsx_draw_engine.h` (new clear op), `rsx_vulkan_backend.c` | M |
| 8 | **(DDX/DDY and NRM DONE: `0065-fp-ddx-ddy-nrm`; precision clamp open)** **Fragment decompiler: `DDX`/`DDY`, `NRM` of a zero vector, output precision clamp** (`c42065f`, `93dbfdd`, `0eee9dd` part, `a06c0fc` for the log) | v0.16.0 has no case for `OP_DDX/OP_DDY` (declared at `rsx_fp_decompiler.c:70`, never emitted: the destination keeps stale data) and `OP_NRM` is a bare `normalize` (`:948`, NaN for a zero vector: black blocks through HDR bloom in dod3). The precision field (bits 22-23) is not applied (fixed12 [-2,2], fixed9 [-1,1], half). Check first: grep a boot log for `unhandled FP opcode` (the HLSL comment at `:1040`; `a06c0fc` also prints it once to stderr) | ps3recomp `libs/video/rsx_fp_decompiler.c` (+ test) | S each |
| 9 | **Vertex cache and texture write-watch** (`1aaa14b`, `bf2c9e8`, `95001f1`, `72be31b`, `5746ab2`) | Draw-engine CPU: dod3 measured -40% (3.26 to 1.97 s per 120-300 replay frames) and a third of the walker's time in texture hashing. v0.16.0's sparse re-hash (#375) takes the first bite; the write-watch removes hashing and validates the vertex cache without hashing. POSIX `mprotect` version exists (`72be31b`) but needs `include/ps3emu/vm_watch.h` and `runtime/platform/vm_watch.c`, absent in v0.16.0. Do after items 3-4 and re-profile | ps3recomp `libs/video/rsx_draw_engine.c`, new `vm_watch.{h,c}`, `rsx_dispatch.c` | M-L |
| 10 | **Shader pipelines built off the walker; anisotropic filtering** (`baa72c0`, `382482c`; `66fd0a9`) | Hitches when new effects first appear (the arena's first frames) and sharper floors. dod3: 200-450 ms per new pipeline on the walker, up to 0.9 s freezes. v0.16.0 builds on the walker and has no `VkPipelineCache`; #346 caches HLSL to SPIR-V translations only. `rsx_vulkan_backend.c` creates no anisotropic samplers (`:999`, `:1340` create pipelines inline) | ps3recomp `libs/video/rsx_draw_engine.c`, `rsx_vulkan_backend.c` (thread-safe `pipeline_create`) | M |

**Below the top 10** (still applicable): SPU task thread pool and `spu_hop` fast path
(`cfe1fef`, `210e6cf`, `bfa00d4`: SARPBC starts ~90 task threads in the first 6 s; PhysX runs
tasks every frame in play); tasks in creation order and `maxContention` (`0e0adb5`,
`bd565f9`); SPURS job fingerprint cache and region zeroing (`d9e1849`, `781b96d`); `PPU_WAITPROF`
(`260ccb8`: finds what the render thread waits for without gdb sampling); `ppu_vmx.h`
x86-64-v3 float forms (`006af3d`; UE3 is vmaddfp-heavy; measure first, T009/T031); the whole
`--nonvolatile-locals` / `ppu_vm_fast.h` line (T009, L, +80% in dod3, but the menu is
drain-bound); `AUDIO_GAPS` (`d608a98`) to measure audio health; `fe4d252` (walker bulk
uploads); frame capture/replay (`0eee9dd`, `6567f6d`) as a headless regression and bench harness; the
one-line `ppu_prof_stamp` wrap (`21f2763`).

**Do not port:** real occlusion counts (`927a0b8`, `0a3d539` part: v0.16.0 answers "visible",
which is why objects do not vanish); the fork's Vulkan *engine* and D3D12/Metal engines
(section F); `src/install/*` (built-in keys, AGENTS.md rule 1); the Windows UI.

### Evidence and recipes for the top items

- **Items 1, 2, 8** need no guest addresses. For each, first confirm SARPBC hits it:
  the pass capture (`RSX_ENGINE_PASS_DUMP`, patches `pass-dump-textures`) writes `draws.txt`
  with each draw's alpha func/ref and attribute strides; a boot log shows `unhandled FP opcode`.
  Port with the fork's author kept (`git format-patch` from the fork clone, then fix context).
- **Item 3, host half.** dod3 `src/main.cpp`: `fifo_kick()` signals a condvar the walker
  waits on between drains; `guest_usleep_hook(lr, usec)` kicks it on every guest usleep and,
  for the one call site `DOD3_FAST_POLL_LR` names (the fence poll, `func_008B0C70`), waits on
  "a label was written or a drain finished" instead of sleeping, never longer than asked. The
  SARPBC call site is `func_000DD014` (01.09, docs/unreal-engine-3.md); find its return
  address in the hook's `lr` argument with `PS3_VERBOSE=1` (the `timer_usleep(250 us)` lines).
  Measure with `FRAME_CLOCK_STATS=1` before/after.
- **Item 5.** Fork `6eb35c0` writes `GCM_PREPARE_MARKER` into the ring at `cellGcmSetPrepareFlip`
  and returns the id; the drain flips at the marker and records it; `SetFlipImmediate` of a
  prepared buffer succeeds without a second flip and otherwise fails as hardware does;
  host-clock presents are ignored once a title flips through the FIFO. `3f20f13` adds: markers
  never wrap the ring for the title, and the drain does not call the title's flip handler
  itself (the pump delivers it at the next vblank). SARPBC's flow: PrepareFlip, user command
  (`0xDC390`), vblank handler, SetFlipImmediate (patch `gcm-prepare-flip-returns-id`).
- **Item 7.** The clear-with-scissor op is `clear_depth_stencil_rect` (a backend op that
  writes the clear value inside the scissor); `RSX_CLEAR_NO_SCISSOR=1` restores the old clear.
  Whether SARPBC clears shadow atlas regions with scissors is a guess from UE3 (v860);
  v539's shadow code predates that atlas, so look at the trace before porting.

## Frame pacing recipe for SARPBC (UE3, from dod3)

What dod3 does, in `src/main.cpp` (l. = line in `f6c24bf`), and what to look for here. The
dod3 addresses are v860 values; ours are different.

| Piece | dod3 | SARPBC |
|---|---|---|
| Frame limiter | `appUpdateTimeAndHandleMaxTickRate` (`func_008EDC78`) sleeps until `1/GetMaxTickRate()` has passed. `GetMaxTickRate` is a virtual on `GEngine` (vtable +0x138; `GEngine` pointer at 0x01999164) doing the smoothing: `bSmoothFrameRate`, a ~300-frame running average clamped to `MinSmoothedFrameRate 22`..`MaxSmoothedFrameRate 30` (l. 395-420) | `appSleep` is `func_006C61F0` in 01.02 (float seconds to `sys_timer_usleep`, docs/unreal-engine-3.md). The caller in the game thread's tick loop is the limiter; the virtual it calls for the cap is `GetMaxTickRate`. The `Smoothed*FrameRate` keys are in the cooked packages, not the EBOOT (no string in 01.09), so find the call from code. **Untested** |
| How to replace it | `ppu_register_function(code, fn)` on the code address read from the vtable at run time (`fps_install_override`, l. 825): virtual calls go through the function registry, so no lifter `--hook` is needed. The replacement returns the cap in f1; with the lock 0 it can follow the scene (`fps_adaptive_rate`, l. 697-800: highest rate of a ladder that 95% of the last 1.5 s of frames met) | same mechanism; first log what the original returns per frame (f1 in, f1 out) to see whether it dips below 30 under load. If the original returns 22-29 during slow frames, the cap itself is the unsteadiness. **Hypothesis** (the menu's 1 s windows are 26.3-32.3 fps) |
| Vblank rate | the title's vblank handler flips on every second vblank, so dod3 runs vblank at `8 x fps` Hz and a late frame waits a fraction of a ms (l. 409-415) | our `frame_clock` ticks vblank+flip at ~60 Hz (16 ms) and drains every 4 ms. How many vblanks SARPBC's handler (`0x012025A8`) needs per flip is unknown: compare `[present]` intervals with ticks. A late frame waits up to a 16 ms tick today (guess) |
| Fence poll | the render thread's label poll sleeps on "label written / drain done" (l. 258-300) | Port next 3 |
| Even presents | `rsx_present_pace` told the cap by `rsx_present_pace_period` | Port next 6 |
| Loading | `load_idle.cpp`: while no scene is drawn and packages are pending, spend the limiter's sleep in `ProcessAsyncLoading` (265 frames for dod3's first chapter at 30 fps = 9 s) | after play works: same recipe, `UObject::StaticTick` + the async-load function; SARPBC's loads are paced by frames too (guess) |
| Out of focus | `DOD3_UNFOCUSED=pause`: frame clock stops, mixer held, guest clocks frozen | `c5763ce` (`ps3_guest_ticks`) |

Measured-as-no-gain list from dod3's TECHNICAL.md (nobody repeats them): pinning to P-cores,
skipping occlusion-query sync, early partial-batch submits, parallel job-chain workers, vsync off at a cap,
`-O3` / PGO on the lifted units.

## Ported so far

Patches are named by slug (the numbers change on the T043 rebase). Source = fork sha. The
README at `patches/ps3recomp/README.md` has the full table with upstream status.

| Patch slug | Source | What | Evidence |
|---|---|---|---|
| `ppu-fs-open-flags` | `6371138` (ppu_fs.cpp part), soyjxck | `cellFsOpen` used CREAT=0x200, TRUNC=0x400, APPEND=0x100; the SDK values are 0x40/0x80/0x200/0x400. `WRONLY\|CREAT` failed with ENOENT, `WRONLY\|CREAT\|TRUNC` never truncated, `O_APPEND` truncated. Adds O_EXCL | test below. v0.16.0 has the same fix (#349): the patch drops out on the bump |
| `sys-fs-h-open-flags-test` | ours | `sys_fs.h` had the octal SDK digits written as hex; adds `tools/test_ppu_fs_open_flags.py` | 11/11 PASS |
| `spu-task-thread-stack-uaf` | `d2ff9fb` + `2aaad6e`, soyjxck; one commit of ours | POSIX async SPU task thread drops its stack from the lock-line reserver set and the MFC slot table | no crash in 60 s (the fork's was ~25 s in, on macOS) |
| `lwcond-signals-wake` | `f2cd69a`, adapted; test ours | `sys_lwcond_signal*` wake waiters; `PS3_LWCOND_POLL_MS`, `PS3_LWCOND_SLEEP=1` | `tools/test_ppu_lwcond_wake.py` 14/14 |
| `ppu-thread-slots-stacks` | `2c80040` + `9769173`, soyjxck | ended threads give back slot (64) and guest stack; detached threads self-free; `PPU_THREAD_SLOTS`, `PPU_THREAD_END_STALL_US` | 600-thread churn OK; SARPBC creates every thread joinable |
| `sys-fs-overlay-hdd0-symlinks` | `585ff94`, `ef46ea3`, `f94a88e`, soyjxck | `PS3_VFS_OVERLAY=<dir>`; existing `/dev_hdd0` paths used directly; readdir lists symlinked dirs | builds; no overlay test yet |
| `spurs-task-error-codes` | ours | `CELL_SPURS_TASK_ERROR_*` are `0x804109xx` | ctest |
| `audio-pacing-devflash-sig-region` | `997f3c8`, `8961d0a` (POSIX audio part) in our form | queue-depth pacing, `AUDIO_RATE`, overlay signature regions | T007 |
| `spurs-job-chain-rewalk-resume-guard` | `26fdd50`, `0f2870a`, `6371138` (guard part), soyjxck | re-walk queue, resume at the END slot, 200 ms first-guard wait | T022 |
| `gcm-user-command-queue`, `gcm-pump-fast-exit` | `d2e6c1b`, `b6e4e18`, soyjxck | user commands queue in order; the pump leaves at once when idle | T024 |
| `gcm-intr-thread-park-handling` | ours (idea of `561803c`, `d9b9fcb`) | watchdog does not resync away from a jump-to-self park; opt-in interrupt thread | T024 |
| `gcm-prepare-flip-returns-id` | ours (half of `6eb35c0`) | PrepareFlip returns the id and does not flip on the spot | `test_gcm_prepare_flip.py` |
| `gcm-ring-recycle-drains-tail`, `gcm-no-drain-recycle-runtime-callback` | ours (class of `3f20f13`'s recycle races) | no teleport of `get` while the walker is in the tail; no recycle from the drain with the runtime callback | T024 |
| `nv0039-copy-engine` | ours (`6eb35c0`/`3f20f13` NV0039 part) | NV0039 copies on subchannel 1 performed; only 3D-routed subchannels reach the draw engine | `tools/test_gcm_nv0039.py` |
| `shadow-compare-direction` | ours (`213290c`/`8961d0a` idea) | depth-texture compares are `depth OP reference` | T045 |
| `pass-dump-textures` | ours (`e0ccd05`, `309b907` idea) | pass capture lists sampled textures and writes decoded levels | diagnostics |
| `dod3-cellpad-sdl2-port` | the fork's 13 `libs/input` commits | SDL pad thread, pads by instance id, rumble held, host input, `PAD_NO_HOST` | T008 |
| `spu-sse2-float-helpers` | ours (from the NEON path); v0.16.0 has SSE2/AVX2 (#369/#370) | SPU single-precision fast path | redundant after the bump |
| `spurs-task-runs-once` | ours (class of `c81d337`, `253eafd`, `e0d9c77`) | `cellSpursCreateTask` marks the task running before publishing it; dispatch passes the task id | T033: 1532% to 96% CPU |
| `sys-memory-reuse-freed-ranges` | ours (class of `4c69b99`) | sorted range table with first-fit reuse | T001 |
| `spurs-job-completion-events` | `54ac02b`, soyjxck | `SPURS_JC_DONE_EVENTS=0` | T037 |
| `src/overrides/audio_mp3*.cpp` | dod3-recomp `96df4c3` `src/apu/mp3_native.c` | native MP3 behind a stand-in SPU image | T007 |
| `src/overrides/input_kbm.cpp` | dod3-recomp `96df4c3` `src/input/kbm.cpp` | keyboard and mouse as pad 0 | T008 |

## Already in v0.16.0 or in our pin (do not port)

Table rows marked in-pin / upstream in the full inventory. In short: lwcond layout, POSIX
lwmutex locks, lwmutex trace clock, `stvlx/stvrx`, callee-save epilogue snapshot, `vcmpequb./h.`
CR6, BE vector packs (`ppu_vmx.h` `VMX_PACK`), the 32-dword `SET_TRANSFORM_CONSTANT` window,
explicit-MAIN IO resolution, own-target colour snapshots, `GCM_SET_USER_COMMAND` delivery,
`sys_spinlock` width (#326), GCM callbacks at usleep (#353), vertex-span-once (#357), SPU
float SIMD (#369/#370), the `cellFsOpen` flag values (#349), the PARAM.SFO game type (#359),
TC8/TC9/FACING and `perspective_corr` reads (#328/#329), sRGB gamma and `_bx2` expansion
(#331), predicated-write select (`e99cbbf`), the 32 KB fragment preamble, `GET_REPORT`
writing the guest report area, sparse texture re-hash (#375), SPIR-V cache (#346), the Vulkan
colour-feedback snapshots (#352). Note for the rebase: `fcea4f9` (the HDD game's
`/dev_hdd0/game/<id>/` is the booted tree) and #349 overlap our `sys-fs-overlay-hdd0-symlinks`
and `ppu-fs-open-flags`; #353 and #343 overlap `gcm-pump-fast-exit`,
`gcm-intr-thread-park-handling` and the flip code.

## Owned by other tasks

| Task | Fork commits (see the inventory for status) |
|---|---|
| T019 / T033 (SPURS) | `e925418`, `2200b15`, `7b24b6a`, `f877ed4`, `d9e1849`, `781b96d`, `0e0adb5`, `bd565f9`, `cfe1fef`, `210e6cf`, `bfa00d4`, `8575619`, `50c43aa` |
| T007 (audio) | `a06186b`, `d608a98`, `9574bb9`, `28e9575`; dod3 `src/apu/msdsp_hooks.c` (MultiStream biquads) |
| T008 (input) | `7e52cef`, `cd2ab9b`, `6408875`, `6ce47d7`, `9fd90e3`, `de08397`, `1c1723d` (button-prompt stand-in) |
| T009 (lifter speed) | section B |
| T018 (clean exit) | `f58d67d` (SDL leaves SIGINT/SIGTERM alone; on Linux/Vulkan the window is SDL's, so exit needs an SDL_QUIT pump) |

## Every fork commit

Source for the table: `git log --no-merges --reverse up/master..HEAD` in the fork clone, 208
commits, each exactly once as a primary entry (a sha in parentheses is a secondary mention).
Dates are 2026-10-03 to 2026-10-20.

### A. PPU runtime, lv2 syscalls, HLE

| Fork commit(s) | What it does | Class | In v0.16.0? | For SARPBC (value / effort) | Status |
|---|---|---|---|---|---|
| `0eb2734` | `sys_lwcond_t` is two be32 words | GEN | yes (in the v0.15.0 pin already) | - | in-pin |
| `96c0c92` `da70e07` | lwmutex/lwcond lock for real on POSIX; lwmutex trace clock | GEN | yes (in pin) | - | in-pin |
| `1ef99ce` | `sys_spinlock` works on the 32-bit guest word, not a host `long` | GEN | yes: #326 (`e3b6fed`) | SARPBC does not import sys_spinlock | upstream |
| `4c69b99` | 4096 `sys_memory` allocation slots; say why an allocate fails | GEN | no (a different fix is in our patch) | done differently: patch `sys-memory-reuse-freed-ranges` (range table) | ported |
| `5d7a459` `326af48` | `sys_memory` overflow window 0x70000000..0x80000000, `SYS_MEM_OVERFLOW_END`, 16384 slots | GEN | no | only if 01.09 outgrows the 256 MB window; no sign of it so far. Low / S | missing |
| `f2cd69a` | `sys_lwcond_signal*` wake their waiters (was a 1 ms poll) | GEN | no: signals are still no-ops (`ppu_sysprx.cpp:344-346`) | done: patch `lwcond-signals-wake` | ported |
| `c18043d` | lwmutex as a user-mode lock word on Windows | PLAT | no | Linux already uses the host primitive. n/a | n/a |
| `2c80040` `9769173` | Ended PPU threads give back slot and guest stack; detached threads self-free | GEN | no | done: patch `ppu-thread-slots-stacks` | ported |
| `21f2763` | `ppu_prof_stamp`'s switched-off print (`_n++ < 0`) switches on after 2^31 calls (about 6 h at dod3's rate) | GEN | no: still at `sys_ppu_thread.c:321` | stability in long sessions; one line. Low / S | missing |
| `43d5812` `e3819a3` `dcf3a05` | Same wrap bug in ~300 `if (n++ < N) fprintf` gates; `tools/audit_log_gates.py --fix` | GEN | no | only multi-hour runs reach it. Running the tool touches 35+ files and conflicts with every patch of ours: run it once at the end of a rebase, or skip. Low / S | missing |
| `edb6611` | Wall clock on Windows is the wall clock; `sys_time_get_timezone` | GEN/PLAT | timezone yes (`sys_timer.c:290`); the Windows clock fix no | Linux only. n/a | n/a |
| `c5763ce` | Guest clocks stand still while paused (`ps3_guest_ticks`, `ps3_guest_clock_pause`); an audio hold | GEN | no | pause on focus loss, later. Low / M | missing |
| `260ccb8` | `PPU_WAITPROF` wait profiler (per guest thread and call site); `g_lv2_usleep_hook` (see Port next 3) | GEN | no | the hook is Port next 3; the profiler answers 'what is the render thread waiting for' without gdb sampling. Medium / M | missing |
| `f606486` | `g_lv2_usleep_pre`: a hook that may use a guest sleep's time (dod3 runs its GC there) | GEN | no | only with a native GC / load-idle (later). Low / S | missing |
| `0e967d8` | Cached `getenv` (`ps3emu/env_cache.h`) on hot paths; XInput probe | GEN | no | the cost was the Windows CRT lock; glibc getenv is a scan. Low / M | missing |
| `cf036ff` | Flat indirect-call table, HLE calls without lookups, no audio spin on Windows | GEN | no | T009-class PPU speed; dod3 measured +0.8 fps. Needs the profiler first. Low / M | missing |
| `6e927ba` `e819474` `af41796` `090522d` | HLE handler index instead of a scan; plumbing so tests still link | GEN | no | T009-class; `ps3_hle_call` scans on every HLE call. Low / S | missing |
| `475332e` | `LWM_BLOCK_LOG=<n>`: lwmutex block log cap and caller | DIAG | no | Low / S | missing |
| `e89fdd6` | `FS_READ_TIME=1`: every read with time stamp, size, host time | DIAG | no | useful for loading-time work. Low / S | missing |
| `585ff94` `ef46ea3` `f94a88e` | `PS3_VFS_OVERLAY`; existing `/dev_hdd0` paths resolve directly; readdir lists symlinked dirs | GEN | no, but #349/`fcea4f9` touch the same translators | done: patch `sys-fs-overlay-hdd0-symlinks`. Expect a conflict with `fcea4f9` (`/dev_hdd0/game/<id>/` is the booted tree) on the pin bump | ported |
| `6371138` | Cell `cellFsOpen` flags; WASAPI conversion; first-guard wait; Windows priorities; async builds | GEN/PLAT | open flags yes: #349 | flags and the 200 ms first-guard wait are done (`ppu-fs-open-flags`, `sys-fs-h-open-flags-test`, `spurs-job-chain-rewalk-resume-guard`); the rest is Windows | ported |
| `6b2dffe` | `PS3_GAME_PATCH=1`: boot as the title's installed update (`cellGamePatchCheck`) | GEN | partly: #359 and `fcea4f9` | SARPBC does not import cellGamePatchCheck. n/a | n/a |
| `26d3d46` | An EDAT with no key and a 0-byte header opens as an empty file | GEN | no | dod3 DLC; SARPBC has no EDAT use yet. n/a | n/a |
| `8acdefd` | `cellSysCacheMount` really clears the cache it says it cleared | GEN | no | SARPBC does not import it. n/a | n/a |
| `6a3fe75` | `sceNpTrophyGetGameInfo/GetTrophyInfo` store fields big-endian | GEN | no (`sceNpTrophy.c:391-435` still stores native) | SARPBC imports neither call. n/a until it does | n/a |
| `f93af17` | Real libovis API (`cellOvis`) | GEN | no | done: patch `cellovis-overlay-table` (our own version) | ported |
| `997f3c8` | SPU overlay regions recognised by content signature | GEN | no | done: patch `audio-pacing-devflash-sig-region` (`spu_overlay_register_sig_region`) | ported |
| `1a90f50` | `rsx_vertex_compact`: per-vertex span once per draw (upstream #357) | GEN | yes: #357 | arrives with the bump | upstream |
| `6e98530` | GCM callbacks delivered at `sys_timer_usleep`/`sleep` (upstream #353) | GEN | yes: #353 | arrives with the bump; our patch `gcm-pump-fast-exit` and `gcm-intr-thread-park-handling` touch the same pump: rebase carefully | upstream |

### B. PPU lifter and generated-code speed (T009)

| Fork commit(s) | What it does | Class | In v0.16.0? | For SARPBC (value / effort) | Status |
|---|---|---|---|---|---|
| `ec042fd` | `stvlx`/`stvrx` lifted | GEN | yes (in pin) | - | in-pin |
| `fdf3195` `4e0834d` | Callee-save snapshot only for an epilogue restore; `vcmpequb.`/`vcmpequh.` set CR6 | GEN | yes (in pin) | - | in-pin |
| `e28b286` | `vpkswss` and big-endian vector packs | GEN | yes (in pin via `ppu_vmx.h` `VMX_PACK`) | - | in-pin |
| `0319c85` | `SET_TRANSFORM_CONSTANT` is a 32-dword window | GEN | yes (in pin) | - | in-pin |
| `e635033` `8dde556` `afa9c69` | `--nonvolatile-locals` (r14-r31, FPR/VR/CR/XER/CTR as C locals), SSE AltiVec helpers, `--hook <addr>` | GEN | no (`tools/ppu_lifter.py` has neither flag) | the largest single speed-up in dod3 (430 to 293 MB, about a third off frame time). T009 / L | missing |
| `f8520f0` `fa3a763` | `tools/ppu_frame_locals.py`: a function's own frame slots become C locals; whole-lift verify mode | GEN | no | T009 follow-on to the line above. M | missing |
| `d2c054a` `f1fdcf4` `67cdff2` `d3071c8` `32d817d` | Dirty write-back (`tools/ppu_nv_dirty.py`), XER[SO] elided when no setter exists, VSCR[NJ] constant, `lvx`/`stvx` as one 16-byte copy | GEN | no | T009, after `--nonvolatile-locals`. M | missing |
| `cebbd8d` | One NaN test per float op on the hot path (bit-identical) | GEN | no | T009 / S | missing |
| `c168ab8` `ee004d6` `1cbca03` `3cf81dc` | `ppu_vm_fast.h`: inline loads/stores, then one page-table test (`g_ppu_vm_page`), base as an argument, store-conditionals take the ctx; indirect-call fast path | GEN | no (`ppu_vm_fast.h` absent) | T009 / L. +80% fps in dod3. Not for 'steady 30 in the menu' (the menu is FIFO-drain bound, not PPU bound) | missing |
| `bda9757` | Hot paths: NEON shufb, guarded watch hooks, inline coherence flag (`g_spu_coh_armed`) | GEN | no | the NEON part is n/a; the rest rides with `ppu_vm_fast.h` | missing |
| `006af3d` `a49553d` `0f53677` | `ppu_vmx.h` x86-64-v3 (AVX2/FMA) and arm64 NEON forms of the float ops and word shifts, bit for bit | GEN | no: `ppu_vmx.h` has no SIMD at all | UE3 is vmaddfp-heavy (33,884 sites in dod3's lift). Measure the share first. T009/T031 / M | missing |

### C. SPU, SPURS and tasks (T019, T033, T030)

| Fork commit(s) | What it does | Class | In v0.16.0? | For SARPBC (value / effort) | Status |
|---|---|---|---|---|---|
| `d2ff9fb` `2aaad6e` | POSIX SPU task thread leaves the lock-line reserver set; `_GNU_SOURCE` for clang | GEN | no | done: patch `spu-task-thread-stack-uaf` (+ MFC slot forget) | ported |
| `e925418` | Tasksets recorded per SPURS instance (LFQueue signal word) | GEN | no | T019. Only matters with two SPURS instances. Low / M | missing |
| `2200b15` | A second PPU `EventFlagWait` gets BUSY, as on hardware | GEN | no | T019. Clean. Low / S | missing |
| `7b24b6a` | `SPURS_DYNPORT_LOW=1`: dynamic SPU ports lowest-first | GEN | no | T019. Low / S | missing |
| `e0d9c77` `c81d337` `253eafd` | Task slot and taskset passed to dispatch, not globals; slot claimed before it is published | GEN | no | done in effect, written separately: patch `spurs-task-runs-once` (1500% to ~100% CPU) | ported |
| `26fdd50` `0f2870a` | RunJobChain overlapping a walk queues a re-walk; resume a halted chain at its END slot | GEN | no | done: patch `spurs-job-chain-rewalk-resume-guard` | ported |
| `f877ed4` | `SPURS_JC_SYNC=1` walks a kicked job chain inside RunJobChain | GEN | no | T019 option. Low / S | missing |
| `54ac02b` | `SPURS_JC_DONE_EVENTS=0` stops fabricated job completions | GEN | no | done: patch `spurs-job-completion-events` | ported |
| `d9e1849` `781b96d` | Spurs jobs: per-thread SPU context, cached binary fingerprint, zero only the job's regions; `SPURS_JOB_STATS` | GEN | no | dod3's ShaderPatching job ran ~2700/s; SARPBC's job rate is unmeasured. Perf, medium if ShaderPatching is hot. M | missing |
| `0e0adb5` `bd565f9` | Tasks start in creation order; single-SPU tasksets serialise; a taskset is held to `maxContention`; `SPU_TASK_STATS` | GEN | no | matters if SARPBC's PhysX tasks race (the stale-queue-pop class). Medium / M | missing |
| `cfe1fef` `210e6cf` `bfa00d4` | Cheaper SPU control transfers (`spu_hop`), pooled task threads (POSIX had none; Windows too), reused local store, cached task lookup, label-write hook | GEN | no: there is no pool in `spu_workload.c` | SARPBC starts ~90 async task threads in the first 6 s and PhysX runs tasks every frame in play. In-game CPU/perf, medium / M-L | missing |
| `dbe4445` | Job contexts give their MFC slot back; 64 slots; per-thread slot cache | GEN | partly: `spu_mfc_release` is in the pin | the 64-slot/per-thread cache part is T030's `mfc_cache` (patch `spu-mfc-cache-lockline-ttas`) | in-pin |
| `8575619` | Second SPU line-commit listener (`g_spu_line_commit_hook2`); host thread names on macOS | GEN | no | T019: wakes PPU queue waiters at once instead of a 100 us retry. Low / S | missing |
| `50c43aa` | Three freezes: `SPU_CRI_IMAGE` (image-id keyed, dod3), taskset bits under the lock, freed guest memory recycled | GEN/DOD3 | bits: yes, #340; cri: no | bits arrive with the bump; recycling is our `sys-memory-reuse-freed-ranges`; the cri part is dod3-specific. n/a | upstream |
| `8a6c1d9` | `spu_dma.h` acquire before GET, release before PUT; GCM ref reads keep their side effect | GEN | no | x86 is TSO: compiler reordering only. Low / S | missing |
| `5746ab2` | Frame-less SPU longjmp; `PS3_EVQ_WHO` event-queue diagnostic (and the vertex-cache validation in section E) | GEN/DIAG | no | Low / S | missing |
| `f788adc` | `mfc_for` answers from a per-thread copy | GEN | no | done in our own form: patch `spu-mfc-cache-lockline-ttas` | ported |
| `0ec5689` `864540e` | SPU float fast path on SSE4.1 (exact), `shufb` in 10 ops, `selb`/byte shifts in SSE | GEN | float: #369/#370 (SSE2/AVX2); the rest no | float path arrives with the bump (and our `spu-sse2-float-helpers` becomes redundant). shufb/selb: small SPU speed-up. Low / S | upstream |

### D. GCM, FIFO walker, flips and reports

| Fork commit(s) | What it does | Class | In v0.16.0? | For SARPBC (value / effort) | Status |
|---|---|---|---|---|---|
| `532f20f` | `GCM_SET_USER_COMMAND` reaches the `cellGcmSetUserHandler` handler | GEN | yes (in pin) | - | in-pin |
| `5fe4b4c` | An explicit MAIN location resolves through the IO table first | GEN | yes (in pin) | - | in-pin |
| `561803c` `d9b9fcb` | `GCM_FIFO_NO_RESYNC=1`; `GCM_PARK_WATCH=1` names who patches a parked FIFO | GEN | no | done in our own form: patch `gcm-intr-thread-park-handling` (`GCM_PARK_GRACE_MS`, `GCM_PARK_LOG`) | ported |
| `d2e6c1b` | User commands queue in order | GEN | no | done: patch `gcm-user-command-queue` | ported |
| `b6e4e18` | `ppu_gcm_pump` leaves at once when nothing is pending | GEN | no | done: patch `gcm-pump-fast-exit` | ported |
| `6eb35c0` | Prepared flips execute in FIFO order; presents come from the drain; NV0039 copies incl. report reads | GEN | no: `cellGcmSetPrepareFlip` still flips on the spot (`cellGcmSys.c:2687`); v0.16.0 does have the `GCM_FLIP_MARKER` machinery for `SetFlipCommand` (`:2582-2640`, #343) | half done: patch `gcm-prepare-flip-returns-id` (returns the id, no flip on the spot); NV0039 copies done by `nv0039-copy-engine`. The FIFO-position flip is Port next 5 | missing |
| `6cba82c` | A flip whose marker does not fit fires at its FIFO position; trace event | GEN | no | needs Port next 5. M | missing |
| `97a2933` | Trace event for each pump delivery (`g_gcm_trace_hook` type 11) | DIAG | no | Low / S | missing |
| `3f20f13` | Copy engine on its own subchannel; ring-recycle races; drain does not take the title's buffer-full callback for an overrun; callback wait bounded at 20 s without progress; **alpha-ref float formats 11/12/13** | GEN | subchannel and recycle: no; alpha ref: no (`rsx_fp_decompiler.c:1433-1445` still 14/15/16) | subchannel: done (`nv0039-copy-engine`); recycle races: done in our form (`gcm-ring-recycle-drains-tail`, `gcm-no-drain-recycle-runtime-callback`); alpha ref is Port next 1 | missing |
| `2b6ae46` | Ring-full recycle wakes the walker (`g_gcm_fifo_kick_hook`) and waits on its progress | GEN | no | part of Port next 3. S | missing |
| `309b907` | `GET_REPORT` lands in the guest report area; draw-engine drop counters, draw trace, surface dump | GEN | report write yes (`cellGcmSys.c:2186-2210`); the diagnostics no | reports: nothing to port. Diagnostics: see section I | upstream |
| `b8feb29` | Do not mirror reports into local `0x0E000000` (title VRAM) | GEN | yes: no mirror in v0.16.0 | - | upstream |
| `927a0b8` `0a3d539` | Real occlusion counts, ready before the title reads them (report copies run after the GPU work); sRGB texture gamma and biased normal expansion | GEN | gamma/expand yes (`rsx_fp_texture_gamma_units`, `_rsx_gamma_input`, #331); occlusion no: ZPASS reports 'visible' (`0xFFFF`) | constant 'visible' is the safe answer: vanishing objects came from real counts arriving a frame late. Do not port. n/a | upstream |
| `9d17419` | RSX presents at even intervals while the host caps the frame rate (`rsx_present_pace.{c,h}`) | GEN | no | Port next 6. M | missing |
| `fe4d252` | Walker and draw engine: bulk constant/program uploads to the register file, less work per word and per draw | GEN | no | the drain is the menu's critical path (~18 ms of ~31 per frame, subsystems.md). Medium / M-L | missing |
| `e2ff7ed` | Draws a host marks are moved on the target (`rsx_canvas_remap_set`); a movie found by its own picture | DOD3 | no | dod3 HUD for ultrawide. n/a | n/a |

### E. Draw engine, shaders, textures

| Fork commit(s) | What it does | Class | In v0.16.0? | For SARPBC (value / effort) | Status |
|---|---|---|---|---|---|
| `46fcdb0` | A draw that samples its own colour target samples a copy (`color_snapshot`) | GEN | yes (in pin; Vulkan side #352 arrives with the bump) | - | in-pin |
| `213290c` `8961d0a` | Shadow-map units compare 'texel OP reference' | GEN | yes: `rsx_fp_shadow_desc`; direction fixed by our patch | done: patch `shadow-compare-direction` (SARPBC car shadow) | ported |
| `c7a24d3` | Room for per-unit helpers in the fragment preamble (a 10-texture terrain material overflowed 2 KB) | GEN | yes: preamble is 32 KB (`rsx_fp_decompiler.c:1247`) | - | upstream |
| `bcfc012` | Predicated fragment writes are a select, not a lerp | GEN | yes (`e99cbbf`) | - | upstream |
| `a06c0fc` | Name each opcode the fragment decompiler skips, once | GEN | partly: the HLSL carries a `TODO: unhandled FP opcode` comment (`:1040`), nothing on stderr | makes missing opcodes findable in a boot log. S | missing |
| `c42065f` `93dbfdd` | Fragment `DDX`/`DDY` (screen-space derivatives); `NRM` leaves a zero vector as it is (normalize gave NaN, black blocks in the HDR chain) | GEN | no: `OP_DDX/DDY` have no case, `OP_NRM` is a bare `normalize` (`:948`) | Port next 8. S | missing |
| `0eee9dd` | Frame capture + offline replay (`rsx_capture.c`, `runtime/host/rsx_replay.c`); **zero-stride attribute is a constant**; TEX8/9 routed; fragment output precision clamp (fixed12/fixed9/half); `PS3_SAVEDATA_ROOT` | GEN | TEX8/9 yes (#328); precision clamp no; zero stride no (`rsx_vertex_compact.c:130`); capture/replay no | zero stride is Port next 2; precision clamp is Port next 8; capture/replay is the regression harness (`RSX_CAPTURE`, `rsx_replay --bench`): high value for perf work, needs zlib and a headless Vulkan path. L | missing |
| `546eccf` | Per-program output-alpha clamp `RSX_FP_SAT_ALPHA`; fp-struct ids; file-triggered capture | DOD3 | no | dod3 point-light shafts. n/a | n/a |
| `691962e` `1f4997a` | Depth snapshots cropped to the sampled texture; depth/stencil clears honour the scissor | UE3 | no: depth targets are at least canvas-sized (`rsx_draw_engine.c:838-839`) and clears ignore the scissor (`:2742-2778`) | Port next 7. M | missing |
| `934ab19` | Release the old depth snapshot per shadow-map clear; reuse freed IO space | GEN | Vulkan backend reuses one snapshot per zeta (`vk_eng_depth_snapshot`), so no leak here; IO allocator still bump (`:2925`) | Metal-only bug. IO reuse only matters if SARPBC maps and unmaps IO ranges often. n/a | n/a |
| `df94c65` | `rsx_vertex_fetch_all`: decode a draw's vertices one attribute at a time; 8-lane texture hash; `RSX_VFETCH_CHECK=1` | GEN | no: still `rsx_vertex_fetch_one` per vertex (`rsx_draw_engine.c:1926`); sparse texture rehash yes (#375) | Port next 4. S-M | missing |
| `1aaa14b` (`5746ab2`) | Vertex cache (keyed on layout and a hash of the source bytes, validated by the write-watch), GPU-resident staging, constant and program reuse | GEN | no | Port next 9. M-L | missing |
| `bf2c9e8` `95001f1` `72be31b` | Texture write-watch instead of a hash per frame (`vm_watch`, `mprotect` on POSIX); never re-commit watched pages | GEN | no (`vm_watch.h`/`.c` absent); #375 hashes sparsely instead | Port next 9. M | missing |
| `c425224` `d168a54` | Bind only the texture units a fragment program samples; decode an index run per width; reuse a repeated pipeline key | GEN | no | small draw-engine CPU wins. S-M each | missing |
| `a796972` | No own-target copy for a unit the program never samples; `RSX_SNAP_STATS` | GEN | no | saves full-target copies when a program leaves a unit enabled. Low / S | missing |
| `baa72c0` `382482c` | Build new shader pipelines off the walker (`RSX_ASYNC_SHADERS`, 8 ms budget); 'compiling' is not 'FAILED' | GEN | no | Port next 10. M | missing |
| `1c1723d` | `rsx_draw_engine_set_texture_standin`: a port replaces one of the title's textures | GEN | no | button-prompt atlases (T008 follow-up). Low / S | missing |
| `66fd0a9` | Anisotropic filtering (`RSX_ANISO`, default 16x, only for real mipped guest textures) | GEN | no: `rsx_vulkan_backend.c` creates no anisotropic samplers; Metal has `PS3_ANISO` (#373) | ground and wall texture sharpness. Quality; Port next 10. S | missing |
| `e5b5a55` `94cc1ac` | `[frametime]` line every 5 s; `RSX_EARLY_COMMIT`; skinned-draw counts and bound textures in traces | DIAG | no | `[frametime]` is a cheap fps log (we have `SARPBC_FRAME_STATS`). Low / S | missing |
| `e0ccd05` `72bb749` | `TEX_DUMP_DIR`, `TEX_UP_LOG`, uploads log | DIAG | no | ours: patch `pass-dump-textures` does the same job | ported |
| `0c06274` `1beb3bb` | Draw trace carries target/blend/depth/cull state; `RSX_TRACE_ON_WHITE` | DIAG | no | Low / S | missing |
| `67990d5` | Draw engine counts a host can read (`g_rsx_video_plane_uploads`, `g_rsx_frame_draws`) | GEN | no | Low / S | missing |
| `fc069db` `1d95b63` `ae07267` | `rsx_present_layout`: frame fitted to the window, aspect ratio, content aspect | DOD3/GEN | no | ultrawide for dod3. n/a (note: SARPBC's 85% border is the game's own safe area) | n/a |

### F. Backends (Metal, Direct3D 12, Vulkan)

| Fork commit(s) | What it does | Class | In v0.16.0? | For SARPBC (value / effort) | Status |
|---|---|---|---|---|---|
| `132f791` `4542244` `e89f5d6` `20f1132` `20ff8a8` `c6989bf` `fdc082b` `14c07f5` `f700bff` `701c9a9` `0201f8a` (`ae07267`) | Metal engine: present the flipped buffer, MSL cache, occlusion across passes, menu bar, resolution/display modes, live settings, MSAA/FXAA, binary pipeline archive | PLAT | partly (#373-#374 PS3_ANISO, PS3_AA) | macOS only. n/a | n/a |
| `55e2135` `d1c9e57` `ce2bcd6` `d1a04f1` `4c64e87` `ce551a6` `c9aa30c` `7a9c219` `bbcf9a5` `ae3f391` `d079b50` `a4d3763` `8430222` `4b4340f` | Direct3D 12 engine: resolution scale, tearing, incremental snapshots, async PSO builds, MSAA tweaks, upload alignment, sync/GPU-time diagnostics | PLAT | no | Windows only. n/a | n/a |
| `b6ad593` `cb88782` `47ab24a` `85a432f` `2a040d5` | Fork Vulkan *engine* (`rsx_vulkan_engine.c` + `.inc`, Vulkan 1.3, dynamic rendering, timeline semaphore); live settings; zero new targets; FXAA/MSAA | GEN | no | `#if defined(_WIN32)`; a Linux port is a performance project of its own (see below). L | n/a |
| `b054266` `a91af4a` | Vulkan *backend* (Linux) moved onto the fork's SPIR-V translator | GEN | no | upstream's backend (which we use and patch) has its own translator contract; this is the fork reconciling the two. n/a | n/a |

### G. Audio

| Fork commit(s) | What it does | Class | In v0.16.0? | For SARPBC (value / effort) | Status |
|---|---|---|---|---|---|
| `a06186b` | `AUDIO_PORT_RAW` dumps raw blocks of ports other than 0 | DIAG | no | Low / S | missing |
| `d608a98` | Opt-in user-interactive QoS for named PPU threads and SPU images; `AUDIO_GAPS=1` late-block log | GEN/PLAT | no | QoS is macOS; the gap log is a cheap check of audio health: Low / S | missing |
| `9574bb9` `28e9575` | Windows mixer: one block per 5.33 ms by the clock, MMCSS, `AUDIO_LAG_BLOCKS`, `AUDIO_WRITEPOS` histogram, lag default 0 | GEN/PLAT | no | the POSIX half (queue-depth pacing, `AUDIO_RATE`) is done: patch `audio-pacing-devflash-sig-region`. The read-lag idea is Windows-device specific | ported |
| `f58d67d` | SDL leaves SIGINT/SIGTERM alone (pad + audio) | GEN | no | T018. Our Vulkan window is SDL's, so exit goes through SDL_QUIT instead. Low / S | missing |

### H. Input

| Fork commit(s) | What it does | Class | In v0.16.0? | For SARPBC (value / effort) | Status |
|---|---|---|---|---|---|
| `a6dc0ff` `7f3b485` | macOS keyboard fallback; arrows = left stick, D-pad TFGH | PLAT | no | n/a (our kbm is `input_kbm.cpp`) | n/a |
| `7e52cef` `cd2ab9b` `6408875` `6ce47d7` `9fd90e3` `de08397` | SDL2 pad on its own thread, rumble held, `PAD_STICK_FILE`, pad kind, host input as port 0, `PAD_NO_HOST` | GEN | partly (#372 rumble) | done: patch `dod3-cellpad-sdl2-port` and the racing fixes | ported |
| `d3c8284` `c231b9d` | `rsx_host_mouse`: the presenting window's mouse (Windows) | PLAT | no | SARPBC ignores the mouse; our kbm reads SDL. n/a | n/a |

### I. Diagnostics, tools, CI and tests

| Fork commit(s) | What it does | Class | In v0.16.0? | For SARPBC (value / effort) | Status |
|---|---|---|---|---|---|
| `43efc70` `af6123d` | Build: `-msse4.1` only on x86 hosts; find `<SDL2/SDL.h>` with Homebrew SDL2 | PLAT | - | macOS/arm64 only. n/a | n/a |
| `fa106e3` | `build_spu_workloads.py --native-hook IMAGE=ADDR:FN`: a lifted SPU function starts with `if (FN(ctx)) return;` | GEN | no | the way dod3 hooks ShaderPatching's LZF loops and MultiStream's biquads. SARPBC's EBOOT has a `ShaderPatching` string. Needed only for an SPU native fast path. M | missing |
| `cdee04d` | Screenshot on request (`PS3RECOMP_METAL_FRAME_GRAB=<prefix>`); faster frame dumps | DIAG | no | our boot_check already captures frames. Low / S | missing |
| `bdf365f` `e2c8d34` | `RSX_HITCH_LOG=<ms>`, `PS3_USLEEP_LOG`, GPU waits per frame; texture-upload timing split, `D3D12_DBG` | DIAG | no | a frame-time hitch finder; the Vulkan side would need its own GPU-wait counters. Medium for the steady-30 work / S-M | missing |
| `c1e8b7b` | Six per-event log lines quiet unless verbose (`ps3_log_verbose()`) | DIAG | no (we already have `ps3_log.h`/`PS3_VERBOSE`) | - | n/a |
| `6567f6d` `6971379` | `rsx_replay --bench <n>`, sampling profiler (Windows unwinder), replay write-watch | DIAG | no | needs the capture/replay of section E. Windows profiler part n/a. L | n/a |
| `1eda10c` `dcbfab7` `9ef94db` `1ee3bf1` `91445a8` `29d843d` `07483a3` `bfcd604` `1f7724b` | Test and CI plumbing: stand-ins for the fork's extra runtime symbols (`g_spu_coh_armed`, `vm_watch_touch`, `ps3_guest_ticks`, env cache, ...), optional zlib, libm-free half decode, skipped host scenes | CI | no | exists only because the fork added those symbols. We need such stand-ins only for the features we port (the same fixture rule as `patches/ps3recomp/README.md`). n/a | n/a |


**The fork's Vulkan engine is not a drop-in for Linux.** `b6ad593` adds
`rsx_vulkan_engine.c` + `rsx_vulkan_encode.inc`: a batched engine (record stream, timeline
semaphore, dynamic rendering, Vulkan 1.3) mirroring its D3D12 engine, guarded by
`#if defined(_WIN32) && defined(PS3RECOMP_HAVE_VULKAN)`. `b054266` only makes upstream's
`rsx_vulkan_backend.c` build on the fork's SPIR-V translator contract. The Vulkan backend we
patch is upstream's (synchronous per op, now batched by our `vk-engine-draw-batching`).
Porting the engine to Linux (drop vulkan-1.dll, add an SDL surface) is a performance project
for after the game renders well; the pieces worth taking from it individually are items 6, 7
and 10 above (present pacing, depth/clear handling, anisotropy), which are engine-independent.

## dod3-recomp tree

Every file of `f6c24bf`. dod3's engine is UE3 package version **860** (2013); SARPBC's is
**539** (2008), so treat dod3's addresses as a map of *what* to find, never *where*. Most UE3
pieces need the lifter's `--hook <addr>` (T009) to replace a lifted function by address, except
virtual calls, which resolve through the function registry (`ppu_register_function`).

| File | Lines | Class | What | For SARPBC |
|---|---|---|---|---|
| `src/main.cpp` frame clock | 2147 | UE3 / GEN | vblank/flip ticker on real time; the walker sleeps between drains and is kicked by every guest usleep; the fence poll waits on label writes (l. 226-340, 1317-1347) | Port next 3 and 6; recipe above |
| `src/main.cpp` `DOD3_FPS` | | UE3 | replaces `UEngine::GetMaxTickRate` (l. 395-845); `DOD3_FPS=adaptive` follows the scene on a ladder of caps; vblank at `8 x fps` Hz | Port next 6; recipe above |
| `src/main.cpp` rest | | mixed | render-tick rate for Bink movies (`DOD3_RENDER_TICK_HZ`, l. 480-510), `DOD3_AB=` in-run A/B switch tester (l. 960-1075), hitch trace ring, title defaults | the A/B tester is a good idea for our perf work (paired windows, standard error); Bink n/a (no Bink in 01.09) |
| `src/patches/load_idle.cpp` | 97 | UE3 | spend the frame limiter's sleep in `ProcessAsyncLoading` while no scene is drawn and packages are pending | after play works |
| `src/patches/gc.cpp` + `gc_native.cpp` | 273 + 988 | UE3 | `UObject::CollectGarbage` wrapped; reachability pass (`FArchiveRealtimeGC::PerformReachabilityAnalysis`) hand-translated, 8 workers; purge deferred into the limiter's sleep | perf, later (needs `g_lv2_usleep_pre`, `f606486`) |
| `src/cpu/uscript.h` | 85 | UE3 | UnrealScript VM pieces a replaced native needs (FFrame +0x14 Object, +0x18 Code; GNatives 8 bytes per opcode) | offsets may differ in v539 |
| `src/patches/sysset.cpp` | 499 | UE3 | UE3 `FSystemSettings` changed at run time via the `LoadFromIni` field tables | SARPBC has `SystemSettings` and `_2P/_3P/_4P` sections; graphics options |
| `src/patches/spu_hooks.c` | 497 | UE3 | native LZF copy loops for the ShaderPatching SPU job (~200 runs a frame) | `ShaderPatching` is in SARPBC's EBOOT; needs `--native-hook` (`fa106e3`) |
| `src/patches/edgezlib.cpp` | 151 | GEN | inflates on the PPU | ours (`src/overrides/edgezlib.cpp`) does the same; nothing to take |
| `src/patches/hud_aspect.cpp` (+`.h`) | 400 + 16 | DOD3 | HUD laid out for ultrawide views: canvas transform stack, radar remap (`rsx_canvas_remap_set`), content aspect | n/a (dod3 HUD) |
| `src/patches/prompts.cpp` + `tools/prompt_atlas.py` + `src/res/prompts/*` | 448 + 431 | UE3 idea / DOD3 data | swaps the button-glyph atlas texture by content hash via `rsx_draw_engine_set_texture_standin` (`1c1723d`) | button prompts by pad type (T008 follow-up); needs our own art |
| `src/patches/menu_patch.cpp` + `menu_patch_data*.h` + `tools/menu_patch.py` | 351 + 1033 x2 + 583 | UE3 method / DOD3 data | patches UnrealScript functions of the script package and serves it via `PS3_VFS_OVERLAY` (now ported); rewrites the package hash in the EBOOT's table and the `PS3TOC.TXT` line | the method is reusable; the data is dod3's |
| `tools/ue3/*` (`upk`, `dis`, `script`, `build`, `diff`, `pkgpatch`, `__main__`) | 100, 270, 258, 177, 69, 66, 46 | UE3 | package reader, script disassembler, bytecode tree editor, cross-build script diff (`python tools/ue3 dis\|diff\|info`) | written for v860; v539 differs in the package summary and some bytecode |
| `src/patches/collision_native.cpp` + `tools/lift_native.py` | 3041 + 144 | DOD3 output / GEN tool | one hot lifted function made native (frame slots to locals) | the tool is generic (needs `--nonvolatile-locals`, T009) |
| `src/cpu/hot.cpp`, `src/cpu/eboot.h` | 182, 132 | DOD3 | hook table with check mode; one header of every address per EBOOT version | the pattern suits our 01.02/01.09 |
| `src/cpu/spu_check.h`, `cycles.h`, `ppu.h` | 69, 24, 21 | GEN | run lifted SPU code to a pc and compare native vs lifted; TSC timer | with any SPU hook |
| `src/apu/*` (`mp3_native.c`, `mp3dec*.c`, `msdsp_hooks.c`, `mp3_standin.h`) | ~2100 | GEN (MultiStream) | native MP3 behind a stand-in SPU image; biquad fast path in the DSP plugin | MP3 ported (`audio_mp3*.cpp`); the biquad hook is T007 follow-up (perf) |
| `src/input/kbm.cpp`, `camera.cpp` | 358, 192 | PLAT / DOD3 | keyboard+mouse as a pad; mouse as camera stick, stick speed scaled by (1/30)/dt above 30 fps | kbm ported; camera is per game |
| `src/kernel/spurs_queue.cpp`, `spurs_lfqueue.cpp`, `tools/gen_libsre.py` | 208, 261, 170 | GEN | SPURS queue / LFQueue lifted from libsre at build time | T019 (we have `spurs-queue-ppu`) |
| `src/kernel/hle.cpp` | 55 | GEN idea | `cellFsGetFreeSize` override: `/dev_hdd1` reported full so FIOS does not start a disc cache whose index a killed process leaves half-written | SARPBC imports `cellFsGetFreeSize`; if a cache file under `/dev_hdd1` ever misbehaves after a killed run, copy this |
| `src/kernel/dlc.cpp` | 91 | DOD3 | writes the JP voice DLC's file lists | no |
| `src/os/win32/prof.cpp` | 794 | PLAT | in-process sampling profiler (`DOD3_PROF`, `DOD3_STALL_MS`: per-thread hot functions, waits, stalled-frame stack dumps), lifted code named via the function table | Windows only; the idea (stack dump on a stalled frame, hot functions as `ppu:<addr>`) suits a gdb-based script for us (perf is denied here) |
| `src/util.{h,cpp}` | 54, 58 | GEN | BE access helpers, monotonic clock, setenv on Windows | no |
| `src/install/*` | ~2400 | PLAT | PKG/SELF/ISO installer with **built-in keys** | **do not port** (AGENTS.md rule 1). We decrypt with RPCS3 (`tools/decrypt.sh`) |
| `src/ui/*`, `src/os/macos`, `src/os/win32/setup_win.cpp`, `src/res/app.*`, `third_party/imgui` | ~2600 + imgui | PLAT | settings menu (ImGui over D3D12/Metal), first-run wizard, icons | a Linux front end later, if at all |
| `dod3.ini` | 167 | DOD3 | every `DOD3_*`/`RSX_*` switch as an ini key | our `config.toml` plays this role |
| `CMakeLists.txt` | 631 | PLAT | flags for the lifted units (x86-64-v3, `/Zc:tlsGuards-`, per-unit builds) | check our flags when T009 starts |
| `docs/TECHNICAL.md`, `DEBUGGING.md`, `BUILDING.md`, `PLAYING.md`, `CONTRIBUTING.md` | 310, 244, 185, 231, 87 | docs | TECHNICAL: how the port works (read for pacing, GC, write-watch, MSAA); DEBUGGING: every switch and the measured-as-no-gain list | read TECHNICAL before any perf work |
| `tools/eboot_diff.py`, `addr_map.py`, `data_map.py` | 80, 41, 87 | GEN | map function/code/data addresses between two EBOOT builds | **useful now**: a 01.02 to 01.09 map, so findings on one version carry to the other |
| `tools/make_spu_overlays.py`, `lift_spu.sh` | 286, 69 | GEN | SPU overlay lifting, `--native-hook` | we have our own overlay lift (`spu-overlay-lift`) |
| `tools/compare_frames.py`, `hud_visible.py`, `ppm.py`, `ppm2png.py`, `replay_regress.sh` | small | GEN | frame comparison, HUD-visible check, PPM tools, replay regression | with the fork's rsx_capture/replay, if adopted; `hud_visible.py` shows how dod3 asks "is the game in play?" from a frame |
| `tools/autoplay.sh`, `live_bench.sh`, `bench_summary.py`, `run_timed.sh`, `stack_summary.py` | 143, 82, 63, 19, 34 | GEN (dod3 paths) | scripted runs and benchmarks (`[frametime]` windows: median and quartiles, share of frames over 34 ms) | ideas for `tools/boot_check.sh --pad` and a fps summary |
| `tools/gen_mp3_tables.py` | 208 | GEN | MP3 decoder tables | done with the MP3 port |
| `tools/package_*.sh`, `build_*.bat`, `build_mac_deps.sh`, `make_icon.py`, `capture_*.bat` | small | PLAT | packaging | no |

### Environment switches added by our ports

`PS3_LWCOND_POLL_MS=<ms>` (lwcond wait cap, default 1), `PS3_LWCOND_SLEEP=1` (old fixed
sleep), `PPU_THREAD_SLOTS=<n>` (use n of the 64 thread slots), `PPU_THREAD_END_STALL_US`
(tests only), `PS3_VFS_OVERLAY=<dir>` (files laid over the dump). They belong in
docs/debugging.md's env table too (outside this doc's scope; coordinator).

## Notes

- Pre-existing, found while testing T023: `test_spurs_queue` hangs in a **Release** ctest
  build because its `assert(task_push_begin(...))` vanishes under NDEBUG; built without NDEBUG
  it passes. `spu_fnms_zero_extended`'s fixture does not compile here. Upstream's
  `tools/title_hacks.py --check` reported `lv2_register.c 11 -> 13` at the old pin.
- The 01.09 lift has `TODO` words that are probably data, not unlifted instructions:
  `vmx_x531 v0,v17,v2` x470, `op31_x207` x35, `op31_x1023` x17, `op31_x547` x1 (identical
  operands repeated). Worth a look in T010.
- v0.16.0 adds `PS3_FTRACE` (#339: a frame timeline of who waits for whom, `ps3_ftrace.h`,
  `tools/ftrace_report.py`). It arrives with the bump and answers part of what `PPU_WAITPROF`
  does; try it before porting `260ccb8`'s profiler.
- First-pass details that are still true: the boot log showed `SetPrepareFlip(bufferId=0/1)` x9
  and `SetFlipImmediate` x8 during loading and the three GCM handlers registered (vblank
  `0x012025A8`, flip `0x012025A0`, user `0x012025B0`); SARPBC 01.09 imports exactly the GCM
  set the flip fixes are about (`cellGcmSetPrepareFlip`, `SetFlipImmediate`,
  `SetUserHandler`, `SetVBlankHandler`, `SetFlipHandler`, `SetGraphicsHandler`), and does not
  import `cellGcmSetTransferData`, `SetTransferReportData`, `SetReportData`,
  `sys_spinlock`, `cellSysCacheMount`, `cellGamePatchCheck`, `sceNpTrophyGetGameInfo`
  (`analysis/imports_named.json`, checked 2026-10-20).
