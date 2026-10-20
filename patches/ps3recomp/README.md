# Patches against ps3recomp

`external/ps3recomp` is pinned to upstream [sp00nznet/ps3recomp](https://github.com/sp00nznet/ps3recomp).
Everything we change in it lives here as a patch, so the submodule pointer always names
a real upstream commit and a bump is a rebase of this folder.

## The "middle path"

Upstream is the base. Features from the Drakengard 3 fork
([soyjxck/ps3recomp](https://github.com/soyjxck/ps3recomp), MIT) are ported over one at a
time, **only when this title needs them**, as separate patches (inventory:
`docs/dod3-reuse.md`). Ported so far: the SDL pad thread (0016), the T023 generic fixes
(0018-0021), the job-chain re-walk (0024) and GCM fixes (0025, 0026, part of 0034). Still
open: the lifter's `--hook`/`--nonvolatile-locals` and the guest page-table fast path (T009),
libsre's real `_cellSpursLFQueuePushBody` (ours is the Edge-zlib-only
`src/overrides/edgezlib.cpp`).

**Upstream moved on (checked 2026-10-20):** v0.16.0 (`749182e`, 117 commits past our pin)
merged 44 PRs, among them fixes we carry: the game type from PARAM.SFO CATEGORY (#359, our
0002), the `CELL_FS_O_*` values (#349, our 0013/0014), the small motor (#372, part of 0017),
SSE2/AVX2 SPU floats (#369/#370, our 0032), and a Vulkan present rework (#351). Replayed onto
v0.16.0 in order (skipping the ones that fail), 32 of our 40 files apply and 8 conflict: 0013,
0016, 0017, 0021, 0027, 0032, 0039, 0040. The bump is its own task (T043).

## Conventions

- One change per patch, named `NNNN-short-description.patch` (`git format-patch` output;
  a file may hold a short series, e.g. a ported fork commit plus its test), applied in
  order by `tools/apply_patches.sh` (`git am` from the pin; `./build.sh` runs it when the
  stack changed).
- Each patch keeps the upstream tests building and passing on the whole stack
  (`tools/lint.py --tests`): a patch that changes a function a test extracts or links fixes
  that test in the same patch.
- Each patch's commit message says why we need it and where it came from (upstream PR,
  dod3 fork commit, or our own). Keep the original author on ported commits.
- Generic fixes are also opened as upstream PRs; drop the patch once it lands.
- On a pin bump: `git -C external/ps3recomp checkout <new>`, re-apply, fix conflicts,
  re-export, relift, rebuild, and record the result in `docs/status.md`.

## Current patches

| Patch | What | Upstream |
|---|---|---|
| `0001-trophy-deliver-RegisterContext-statuses-synchronousl.patch` | `sceNpTrophyRegisterContext` delivers PROCESSING_COMPLETE synchronously again (17047c9 deferred it, which races SARPBC's -1 "done" marker); test updated | to offer (it reverts a recent upstream choice, so explain the firmware ordering) |
| `0002-cellGame-take-the-game-type-from-PARAM.SFO-CATEGORY-.patch` | cellGame reports HG titles as HDD games (01.09 builds its paths from BootCheck) | to offer |
| `0003-hle-trivial-missing-imports.patch` | T004: offline sys_net model (connect/accept/send fail cleanly), cellKbRead, OSK device mask, SPURS queue detach, `_sys_spu_printf_initialize/finalize` | to offer |
| `0004-sys-prx-load-module.patch` | T002: `sys_prx_load_module/start/stop/unload` with a PRX loader (`runtime/prx/prx_runtime.c`), relocations, exports, `module_start` via lifted code or a strict leaf evaluator | to offer |
| `0005-sys-memory-reuse-freed-ranges.patch` | T001: the sys_memory/mmapper window is a sorted range table with first-fit reuse (the bump pointer ran out after ~256 MB of churn: UE3 OOM) | to offer |
| `0006-spu-detector-rodata-seeds.patch` | T016: SPU function finder keeps an `ila`/branch/table seed only if it decodes as code, isn't a NUL-terminated string, and reaches a branch/stop (section-stripped images lifted .rodata as code); test added | to offer |
| `0007-cellovis-overlay-table.patch` | T003: real `cellOvisGetOverlayTableSize`/`InitializeOverlayTable` (upstream's were invented API); test | to offer |
| `0008-spu-overlay-lift.patch` | T003: build_spu_workloads lifts SPU images with overlays (resident code + one code overlay as one LS image); drops data-only ranges. Rebased onto 0006 by the coordinator (merged seed filter + cross-segment call seeds) | to offer |
| `0009-cellMsgDialogOpenErrorCode.patch` | T020: `cellMsgDialogOpenErrorCode` prints the code and delivers BUTTON_OK on the next sysutil poll (the unresolved path never called back) | to offer |
| `0010-cellVoice-InitEx-StartEx-notify-queue.patch` | T020: `cellVoiceInitEx/StartEx` and a real notify event queue (the faked CELL_OK left libvoice uninitialized and the queue id unwritten) | to offer |
| `0011-cellMusic-utility.patch` | T020: cellMusic utility as an empty library whose result callbacks fire (01.09 polls a mailbox at 0x00092F10) | to offer |
| `0012-cellRec-videoexport-videoupload-sdk-names.patch` | T020: cellRec/cellVideoExport/cellVideoUpload define the SDK entry points (invented names matched no NID) | to offer |
| `0013-ppu-fs-open-flags.patch` | T021 (from the dod3 fork): ppu_fs uses the Cell SDK open flags (O_CREAT 0x40, O_TRUNC 0x200) | to offer (fork author's fix) |
| `0014-sys-fs-h-open-flags-test.patch` | T021 (from the dod3 fork): sys_fs.h octal open flags; cellFsOpen flag test | to offer (fork author's fix) |
| `0015-spurs-queue-ppu.patch` | T019: real PPU side of SPURS Queue (PopBody/PushBody, attach/detach) and LFQueue init in the task-side layout | to offer |
| `0016-dod3-cellpad-sdl2-port.patch` | T008: Drakengard 3 fork's 13 libs/input commits (SDL pad thread, pads by instance id, rumble held, `cellPad_set_host_input`, host kind, PAD_NO_HOST); soyjxck, MIT, authors kept | fork author's work: offer with them |
| `0017-cellpad-racing-fixes.patch` | T008: press-mode trigger pressure (a half pull read 255), small motor on/off at 0xFFFF, empty ports' sticks centred at 128, `PAD_TRIGGERS`/`PAD_TRACE`; test `libs/input/tests/test_cellpad_sdl.py` | to offer |
| `0018-spu-task-thread-stack-uaf.patch` | T023: fork 0012+0148 (soyjxck): Linux SPU task thread leaves the lock-line reserver set when it ends, plus ours: and the MFC slot table (as on Windows) | fork author's work |
| `0019-lwcond-signals-wake.patch` | T023: fork 0100: `sys_lwcond_signal*` wake waiters (was a 1 ms sleep poll); adapted to our semaphore lwmutex; test `tools/test_ppu_lwcond_wake.py` | fork author's work |
| `0020-ppu-thread-slots-stacks.patch` | T023: fork 0166+0167: ended PPU threads give back their slot and guest stack; non-joinable threads self-free | fork author's work |
| `0021-sys-fs-overlay-hdd0-symlinks.patch` | T023: fork 0119/0131/0132: `PS3_VFS_OVERLAY`, existing `/dev_hdd0` paths used directly, readdir lists symlinked dirs as dirs | fork author's work |
| `0022-spurs-task-error-codes.patch` | T023: `CELL_SPURS_TASK_ERROR_*` use the SDK's 0x804109xx values (were 0x804107xx) | to offer |
| `0023-audio-pacing-devflash-sig-region.patch` | T007: POSIX cellAudio pacing (+ `AUDIO_RATE`/`AUDIO_PEAK`/`AUDIO_WAV`), `/dev_flash` default off a Windows path, `spu_overlay_register_sig_region` (register an overlay by its first bytes over a span; used by `tools/make_spu_overlays.py`) | to offer |
| `0024-spurs-job-chain-rewalk-resume-guard.patch` | T022: a RunJobChain that arrives mid-walk queues a re-walk (it was dropped, so ShaderPatching jobs that release FIFO parks never ran); walks resume where they stopped; a never-notified guard waits 200 ms, not 20 s. Ported from soyjxck/ps3recomp 26fdd50, 0f2870a, 6371138 (MIT) | fork author's work |
| `0025-gcm-user-command-queue.patch` | T024: fork 0018 (soyjxck d2e6c1b): user commands queue in order instead of sharing one slot | fork author's work |
| `0026-gcm-pump-fast-exit.patch` | T024: fork 0139 (soyjxck b6e4e18): GCM pump fast exit | fork author's work |
| `0027-gcm-intr-thread-park-handling.patch` | T024: the stuck-get watchdog no longer resyncs away from a jump-to-itself park; `GCM_PARK_GRACE_MS` (50), `GCM_PARK_LOG`, opt-in `GCM_INTR_THREAD=1` host interrupt thread for vblank/flip/user handlers | to offer |
| `0028-spu-seed-ctors-dtors.patch` | T025: `find_spu_functions.py` seeds `.ctors/.dtors/.init_array/.fini_array` entries (and `-1..0` framed lists in stripped images); PhysX LS 0x20180 is a static ctor | to offer |
| `0029-win32-compat-srw-writer-preference.patch` | T027: SRW-lock emulation prefers writers on glibc (`PTHREAD_RWLOCK_PREFER_WRITER_NONRECURSIVE_NP`); fixes the ShaderPatching job starving on `mfc_for` with 01.09 at the ESRB screen. Test `test_srw_writer_progress` | to offer |
| `0030-ppu-guest-call-stacks.patch` | T026: `ppu_guest_call`/`_ct` run each callback on a per-(host thread, nesting depth) stack carved from the top of the PPU stack region (256 KB + guard page, pooled; `PPU_CB_STACK_SIZE`), not the shared 0xCFFE0000 that also sat in RSX local memory. Test `test_ppu_guest_call_stacks.py` | to offer |
| `0031-spu-ctor-dtor-seed-test.patch` | T025: unit test for `collect_ctor_dtor_targets` (0028) | with 0028 |
| `0032-spu-sse2-float-helpers.patch` | T025: SSE2 port of the NEON `fa/fs/fm/fma/fms/fnms` fast path in `spu_helpers.h`, bit-exact (`test_spu_float_sse.c`); fma+fm 12 ns vs 33 ns | to offer |
| `0033-spu-mfc-cache-lockline-ttas.patch` | T030: `mfc_for` looks up the engine only for MFC_Cmd/WrTagUpdate/WrListStallAck, cached in `spu_context` (`mfc_cache`, `mfc_cache_gen`, invalidated by a registry generation); POSIX `spu_lockline_lock` is TTAS + `_mm_pause` + `sched_yield`/256 like MSVC. 01.09 flips 100 -> 514 in 90 s (one run) | to offer |
| `0034-gcm-prepare-flip-returns-id.patch` | T024: `cellGcmSetPrepareFlip` returns the buffer id and does not flip on the spot (part of fork 0049); SARPBC's user handler 0xDC390 flips the id it got back, so every flip was buffer 0. `GCM_PREPARE_FLIPS_NOW=1` = old behaviour. Test `test_gcm_prepare_flip.py` | to offer |
| `0035-gcm-ring-recycle-drains-tail.patch` | T024: recycling the title's ring no longer teleports `get` to the start while the walker is still parked in the tail (dropped ~31 KB incl. the fence) | to offer |
| `0036-gcm-no-drain-recycle-runtime-callback.patch` | T024: no recycle from the drain thread while the title's context still uses the runtime buffer-full callback (raced it; one boot stuck on Loading) | to offer |
| `0037-spu-coherence-context-index.patch` | T030: private, unbounded context-pointer index for GETLLAR registry membership. Notification order, reservation semantics, and context ABI unchanged. 300-context lifecycle/collision tests and benchmark. 01.09: 588–589 vs 320–374 flips in 60 s, CPU unchanged | to offer |
| `0038-spurs-task-runs-once.patch` | T033: `cellSpursCreateTask` marks a task running before its ready bit is published, and both dispatch sites pass the task id explicitly (`spu_workload_dispatch_task_async`); a task exiting in the window started a second copy (542 per 90 s on SARPBC 01.09; the copies spun forever, ~1500% CPU). Flips 404 -> 1920, CPU 1532% -> 96% | to offer |
| `0039-vk-present-centre-readback.patch` | T024 (pi): `vk_cb_present` copies a 1x1 centre texel instead of the whole frame unless a PPM dump is due (3.6 MB + a round trip per present before). Test `libs/video/tests/test_vulkan_present_readback.py` (mocked Vulkan, `--sanitize`) | to offer |
| `0040-vk-engine-draw-batching.patch` | T040: Vulkan engine draws batched into one command buffer (per-draw arena slices + descriptor sets; flushed by any other GPU op, destroy or `submit_and_wait`), vertex/index content cache in device-local host-visible memory, unchanged constants reused, no present readback on the engine path. `PS3RECOMP_VK_BATCH=0`, `PS3RECOMP_VK_GEO_CACHE=0`, diagnostics `PS3RECOMP_VK_BATCH_STATS`, `PS3RECOMP_VK_DRAW_TIMES`. SARPBC Choose Profile ~23 -> 32.5 fps, main menu 19.8 -> 29.5 (with 0038/0039) | to offer |
| `0041-vk-wayland-surface-formats.patch` | T042: allocate the complete Vulkan surface-format list instead of truncating it to 64; retry `VK_INCOMPLETE` up to four times. RADV Wayland reports 99 pairs on this desktop. GPU-independent tests cover selection, changing counts, errors and allocation cleanup | to offer |
| `0042-spurs-taskset-attribute-args.patch` | T037 (Claude; pi integration tests): retain the taskset attribute's 64-bit argument and per-SPU priority bytes, and forward the argument into taskset creation. Collision tasks previously received a zero work-pool argument and blocked arena loading. Tests cover full-width arguments, priority byte order and existing layout/canary validation | to offer |
| `0043-spurs-job-completion-events.patch` | T037 (pi): port the MIT fork's `SPURS_JC_DONE_EVENTS=0` gate without changing the runtime's legacy default. SARPBC disables fabricated job completions in its own config: a ShaderPatching job-index-0 broadcast otherwise shuts down the attached slab service. Tests cover opt-out, default/explicit enable, payloads and intact real SPU port bindings | to offer |
| `0044-spurs-priority-array.patch` | T037 integration review: priorities are a guest byte-array pointer, not a packed integer. Copy the table with backing validation; retain Claude's full-width taskset argument repair. Tests use distinct priority bytes and ensure bad backing leaves the attribute intact | to offer |
| `0045-gcm-interrupt-affinity.patch` | T044: with a dedicated GCM interrupt worker, foreign HLE callers leave callbacks pending instead of stealing them onto a render thread that may wait for itself. Keep manual/no-worker fallback and clean up failed startup. GCC/Clang tests cover ownership, pending ticks, FIFO/exact-once delivery and mocked CreateThread failure | to offer |

Making a new one: commit inside `external/ps3recomp` on branch `sarpbc-patches`, then
`git -C external/ps3recomp format-patch -1 -o ../../patches/ps3recomp/ --start-number N`.
On a task branch, name it `T###-description.patch` (`T###-1-...`, `T###-2-...` for several, in
apply order) and add its row to the table above; `tools/merge_to_main.sh` gives it the next free
number when it merges (docs/workflow.md).

Upstream's unit tests assume macOS's `-dead_strip`. On Linux, build them with
`-ffunction-sections -fdata-sections -Wl,--gc-sections -Wl,-z,muldefs` and a no-op shim for
`cellMsgDialog_tick`, `np_psnr_pump`, `cellGame_get_title_id`, `vm_write32`, `vm_write8`.

## To upstream (handled port-side for now)

- **Linux guest VM in the template** (`templates/project/main.cpp`, `boot_main.cpp`):
  `calloc` → 4 GB-aligned `mmap`; see docs/build-linux.md.
- **`_cellSpursLFQueuePushBody`** has no HLE. Ours (`src/overrides/edgezlib.cpp`) is
  Edge-zlib specific; a general one needs libsre's push protocol.

- **`tools/test_ppu_lift.py` rewrites `scratch/ppu_conformance.cpp`** in the source tree each
  run (the file is tracked), so a test run leaves the submodule dirty and `apply_patches.sh`
  then refuses to run. `tools/lint.py --tests` puts it back; upstream should write to a temp dir.

- **Linker TOC-switch stubs** fold into the preceding function in `ppu_loader.py`, and
  the lifter turns each one into a wrapper running to the end of the run (3.6× source
  bloat on this EBOOT). Our workaround is `tools/split_toc_stubs.py`. The proper fix is in
  `ppu_loader.py` (or the lifter's boundary recovery): treat a run of
  `std r2,40(r1); addis/addi r2,r2; b` as one function per stub.
