# Patches against ps3recomp

`external/ps3recomp` is pinned to upstream [sp00nznet/ps3recomp](https://github.com/sp00nznet/ps3recomp).
Everything we change in it lives here as a patch, so the submodule pointer always names
a real upstream commit and a bump is a rebase of this folder.

## The "middle path"

Upstream is the base. Features from the Drakengard 3 fork
([soyjxck/ps3recomp](https://github.com/soyjxck/ps3recomp), MIT) are ported over one at a
time, **only when this title needs them**, as separate patches. Candidates, roughly in the
order we expect to need them (details in `docs/reference-ports.md`):

1. Vulkan draw engine (`libs/video/rsx_vulkan_engine.c`) — upstream has only the backend.
2. SPURS Queue / LFQueue paths lifted from libsre (dod3's `tools/gen_libsre.py`).
3. Lifter `--hook <addr>` (native replacements) and `--nonvolatile-locals` (performance).
4. Guest memory page-table fast path, user-mode `sys_lwmutex`, `sys_lwcond` wakeups.

## Conventions

- One change per patch, named `NNNN-short-description.patch` (`git format-patch` output),
  applied in order with `git -C external/ps3recomp am ../../patches/ps3recomp/*.patch`.
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
| `0006-spu-detector-rodata-seeds.patch` | T016: SPU function finder keeps an `ila`/branch/table seed only if it decodes as code, isn't a NUL-terminated string, and reaches a branch/stop (section-stripped images lifted .rodata as code); test added | to offer |
| `0007-cellovis-overlay-table.patch` | T003: real `cellOvisGetOverlayTableSize`/`InitializeOverlayTable` (upstream's were invented API); test | to offer |
| `0008-spu-overlay-lift.patch` | T003: build_spu_workloads lifts SPU images with overlays (resident code + one code overlay as one LS image); drops data-only ranges. Rebased onto 0006 by the coordinator (merged seed filter + cross-segment call seeds) | to offer |
| `0005-sys-memory-reuse-freed-ranges.patch` | T001: the sys_memory/mmapper window is a sorted range table with first-fit reuse (the bump pointer ran out after ~256 MB of churn: UE3 OOM) | to offer |
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

Making a new one: commit inside `external/ps3recomp` on branch `sarpbc-patches`, then
`git -C external/ps3recomp format-patch -1 -o ../../patches/ps3recomp/ --start-number N`.
Agents working in parallel name theirs `T###-description.patch`; the coordinator
renumbers them on merge.

Upstream's unit tests assume macOS's `-dead_strip`. On Linux, build them with
`-ffunction-sections -fdata-sections -Wl,--gc-sections -Wl,-z,muldefs` and a no-op shim for
`cellMsgDialog_tick`, `np_psnr_pump`, `cellGame_get_title_id`, `vm_write32`, `vm_write8`.

## To upstream (handled port-side for now)

- **Linux guest VM in the template** (`templates/project/main.cpp`, `boot_main.cpp`):
  `calloc` → 4 GB-aligned `mmap`; see docs/build-linux.md.
- **`_cellSpursLFQueuePushBody`** has no HLE. Ours (`src/overrides/edgezlib.cpp`) is
  Edge-zlib specific; a general one needs libsre's push protocol.

- **Linker TOC-switch stubs** fold into the preceding function in `ppu_loader.py`, and
  the lifter turns each one into a wrapper running to the end of the run (3.6× source
  bloat on this EBOOT). Our workaround is `tools/split_toc_stubs.py`. The proper fix is in
  `ppu_loader.py` (or the lifter's boundary recovery): treat a run of
  `std r2,40(r1); addis/addi r2,r2; b` as one function per stub.
