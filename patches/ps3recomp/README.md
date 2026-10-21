# Patches against ps3recomp

`external/ps3recomp` is pinned to upstream [sp00nznet/ps3recomp](https://github.com/sp00nznet/ps3recomp).
Everything we change in it lives here as a patch, so the submodule pointer always names
a real upstream commit and a bump is a rebase of this folder.

## The "middle path"

Upstream is the base. Features from the Drakengard 3 fork
([soyjxck/ps3recomp](https://github.com/soyjxck/ps3recomp), MIT) are ported over one at a
time, **only when this title needs them**, as separate patches (inventory:
`docs/dod3-reuse.md`). Ported so far: the SDL pad thread (0014), the T023 generic fixes
(0016-0019), the job-chain re-walk (0022) and GCM fixes (0023, 0024, part of 0032). Still
open: the lifter's `--hook`/`--nonvolatile-locals` and the guest page-table fast path (T009),
libsre's real `_cellSpursLFQueuePushBody` (ours is the Edge-zlib-only
`src/overrides/edgezlib.cpp`).

**Pin: upstream v0.16.0 (`749182e`), since 2026-10-20 (T043).** The bump from v0.15.0
(`39a3629`, 117 upstream commits, 44 PRs) rebased every patch onto it:
- **Dropped, upstream has them:** the game type from PARAM.SFO CATEGORY (was 0002; #359) and
  ppu_fs's open flag values (was 0013; #349). Upstream did not take 0013's `O_EXCL` mapping;
  that line now rides in 0012 (`sys_fs.h` octal flags + test), which upstream still lacks.
- **Merged with upstream's version of the same thing:** cellPad rumble (#372) in 0014/0015 (the
  pad thread sends upstream's `pad_rumble_levels`; `test_pad_rumble.c` now checks the thread);
  SPU float SIMD (#369 AVX2) in 0030, which stays as the SSE2 fallback after the AVX2 path; the
  Vulkan present on its own command buffer (#351) in 0037/0038 (centre texel only, and on the
  engine path no copy and no wait unless a dump is due); GCM flip completion in the command
  stream in 0025 (our interrupt thread kicks after it).
- **Tests fixed inside their patches:** upstream's new `test_gcm_flip_stream`,
  `test_gcm_get_on_jump` (`SetEvent` stub, 0025), `test_spinlock_word_width` (extraction stops
  before the PRX loader, 0003), and our lwcond test (`avconf_register_ctx` stub, 0017).

The files were renumbered to close the gaps. Older notes (status log, task logs) use the old
numbers:

| old | new |
|---|---|
| 0002 | dropped |
| 0003 | 0002 |
| 0004 | 0003 |
| 0005 | 0004 |
| 0006 | 0005 |
| 0007 | 0006 |
| 0008 | 0007 |
| 0009 | 0008 |
| 0010 | 0009 |
| 0011 | 0010 |
| 0012 | 0011 |
| 0013 | dropped |
| 0014 | 0012 |
| 0015 | 0013 |
| 0016 | 0014 |
| 0017 | 0015 |
| 0018 | 0016 |
| 0019 | 0017 |
| 0020 | 0018 |
| 0021 | 0019 |
| 0022 | 0020 |
| 0023 | 0021 |
| 0024 | 0022 |
| 0025 | 0023 |
| 0026 | 0024 |
| 0027 | 0025 |
| 0028 | 0026 |
| 0029 | 0027 |
| 0030 | 0028 |
| 0031 | 0029 |
| 0032 | 0030 |
| 0033 | 0031 |
| 0034 | 0032 |
| 0035 | 0033 |
| 0036 | 0034 |
| 0037 | 0035 |
| 0038 | 0036 |
| 0039 | 0037 |
| 0040 | 0038 |
| 0041 | 0039 |
| 0042 | 0040 |
| 0043 | 0041 |
| 0044 | 0042 |
| 0045 | 0043 |
| 0046 | 0044 |
| 0047 | 0045 |
| 0048 | 0046 |
| 0049 | 0047 |

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
| `0002-hle-trivial-missing-imports.patch` | T004: offline sys_net model (connect/accept/send fail cleanly), cellKbRead, OSK device mask, SPURS queue detach, `_sys_spu_printf_initialize/finalize` | to offer |
| `0003-sys-prx-load-module.patch` | T002: `sys_prx_load_module/start/stop/unload` with a PRX loader (`runtime/prx/prx_runtime.c`), relocations, exports, `module_start` via lifted code or a strict leaf evaluator | to offer |
| `0004-sys-memory-reuse-freed-ranges.patch` | T001: the sys_memory/mmapper window is a sorted range table with first-fit reuse (the bump pointer ran out after ~256 MB of churn: UE3 OOM) | to offer |
| `0005-spu-detector-rodata-seeds.patch` | T016: SPU function finder keeps an `ila`/branch/table seed only if it decodes as code, isn't a NUL-terminated string, and reaches a branch/stop (section-stripped images lifted .rodata as code); test added | to offer |
| `0006-cellovis-overlay-table.patch` | T003: real `cellOvisGetOverlayTableSize`/`InitializeOverlayTable` (upstream's were invented API); test | to offer |
| `0007-spu-overlay-lift.patch` | T003: build_spu_workloads lifts SPU images with overlays (resident code + one code overlay as one LS image); drops data-only ranges. Rebased onto 0006 by the coordinator (merged seed filter + cross-segment call seeds) | to offer |
| `0008-cellMsgDialogOpenErrorCode.patch` | T020: `cellMsgDialogOpenErrorCode` prints the code and delivers BUTTON_OK on the next sysutil poll (the unresolved path never called back) | to offer |
| `0009-cellVoice-InitEx-StartEx-notify-queue.patch` | T020: `cellVoiceInitEx/StartEx` and a real notify event queue (the faked CELL_OK left libvoice uninitialized and the queue id unwritten) | to offer |
| `0010-cellMusic-utility.patch` | T020: cellMusic utility as an empty library whose result callbacks fire (01.09 polls a mailbox at 0x00092F10) | to offer |
| `0011-cellRec-videoexport-videoupload-sdk-names.patch` | T020: cellRec/cellVideoExport/cellVideoUpload define the SDK entry points (invented names matched no NID) | to offer |
| `0012-sys-fs-h-open-flags-test.patch` | T021 (from the dod3 fork): sys_fs.h octal open flags; cellFsOpen flag test | to offer (fork author's fix) |
| `0013-spurs-queue-ppu.patch` | T019: real PPU side of SPURS Queue (PopBody/PushBody, attach/detach) and LFQueue init in the task-side layout | to offer |
| `0014-dod3-cellpad-sdl2-port.patch` | T008: Drakengard 3 fork's 13 libs/input commits (SDL pad thread, pads by instance id, rumble held, `cellPad_set_host_input`, host kind, PAD_NO_HOST); soyjxck, MIT, authors kept | fork author's work: offer with them |
| `0015-cellpad-racing-fixes.patch` | T008: press-mode trigger pressure (a half pull read 255), small motor on/off at 0xFFFF, empty ports' sticks centred at 128, `PAD_TRIGGERS`/`PAD_TRACE`; test `libs/input/tests/test_cellpad_sdl.py` | to offer |
| `0016-spu-task-thread-stack-uaf.patch` | T023: fork 0012+0148 (soyjxck): Linux SPU task thread leaves the lock-line reserver set when it ends, plus ours: and the MFC slot table (as on Windows) | fork author's work |
| `0017-lwcond-signals-wake.patch` | T023: fork 0100: `sys_lwcond_signal*` wake waiters (was a 1 ms sleep poll); adapted to our semaphore lwmutex; test `tools/test_ppu_lwcond_wake.py` | fork author's work |
| `0018-ppu-thread-slots-stacks.patch` | T023: fork 0166+0167: ended PPU threads give back their slot and guest stack; non-joinable threads self-free | fork author's work |
| `0019-sys-fs-overlay-hdd0-symlinks.patch` | T023: fork 0119/0131/0132: `PS3_VFS_OVERLAY`, existing `/dev_hdd0` paths used directly, readdir lists symlinked dirs as dirs | fork author's work |
| `0020-spurs-task-error-codes.patch` | T023: `CELL_SPURS_TASK_ERROR_*` use the SDK's 0x804109xx values (were 0x804107xx) | to offer |
| `0021-audio-pacing-devflash-sig-region.patch` | T007: POSIX cellAudio pacing (+ `AUDIO_RATE`/`AUDIO_PEAK`/`AUDIO_WAV`), `/dev_flash` default off a Windows path, `spu_overlay_register_sig_region` (register an overlay by its first bytes over a span; used by `tools/make_spu_overlays.py`) | to offer |
| `0022-spurs-job-chain-rewalk-resume-guard.patch` | T022: a RunJobChain that arrives mid-walk queues a re-walk (it was dropped, so ShaderPatching jobs that release FIFO parks never ran); walks resume where they stopped; a never-notified guard waits 200 ms, not 20 s. Ported from soyjxck/ps3recomp 26fdd50, 0f2870a, 6371138 (MIT) | fork author's work |
| `0023-gcm-user-command-queue.patch` | T024: fork 0018 (soyjxck d2e6c1b): user commands queue in order instead of sharing one slot | fork author's work |
| `0024-gcm-pump-fast-exit.patch` | T024: fork 0139 (soyjxck b6e4e18): GCM pump fast exit | fork author's work |
| `0025-gcm-intr-thread-park-handling.patch` | T024: the stuck-get watchdog no longer resyncs away from a jump-to-itself park; `GCM_PARK_GRACE_MS` (50), `GCM_PARK_LOG`, opt-in `GCM_INTR_THREAD=1` host interrupt thread for vblank/flip/user handlers | to offer |
| `0026-spu-seed-ctors-dtors.patch` | T025: `find_spu_functions.py` seeds `.ctors/.dtors/.init_array/.fini_array` entries (and `-1..0` framed lists in stripped images); PhysX LS 0x20180 is a static ctor | to offer |
| `0027-win32-compat-srw-writer-preference.patch` | T027: SRW-lock emulation prefers writers on glibc (`PTHREAD_RWLOCK_PREFER_WRITER_NONRECURSIVE_NP`); fixes the ShaderPatching job starving on `mfc_for` with 01.09 at the ESRB screen. Test `test_srw_writer_progress` | to offer |
| `0028-ppu-guest-call-stacks.patch` | T026: `ppu_guest_call`/`_ct` run each callback on a per-(host thread, nesting depth) stack carved from the top of the PPU stack region (256 KB + guard page, pooled; `PPU_CB_STACK_SIZE`), not the shared 0xCFFE0000 that also sat in RSX local memory. Test `test_ppu_guest_call_stacks.py` | to offer |
| `0029-spu-ctor-dtor-seed-test.patch` | T025: unit test for `collect_ctor_dtor_targets` (0028) | with 0028 |
| `0030-spu-sse2-float-helpers.patch` | T025: SSE2 port of the NEON `fa/fs/fm/fma/fms/fnms` fast path in `spu_helpers.h`, bit-exact (`test_spu_float_sse.c`); fma+fm 12 ns vs 33 ns | to offer |
| `0031-spu-mfc-cache-lockline-ttas.patch` | T030: `mfc_for` looks up the engine only for MFC_Cmd/WrTagUpdate/WrListStallAck, cached in `spu_context` (`mfc_cache`, `mfc_cache_gen`, invalidated by a registry generation); POSIX `spu_lockline_lock` is TTAS + `_mm_pause` + `sched_yield`/256 like MSVC. 01.09 flips 100 -> 514 in 90 s (one run) | to offer |
| `0032-gcm-prepare-flip-returns-id.patch` | T024: `cellGcmSetPrepareFlip` returns the buffer id and does not flip on the spot (part of fork 0049); SARPBC's user handler 0xDC390 flips the id it got back, so every flip was buffer 0. `GCM_PREPARE_FLIPS_NOW=1` = old behaviour. Test `test_gcm_prepare_flip.py` | to offer |
| `0033-gcm-ring-recycle-drains-tail.patch` | T024: recycling the title's ring no longer teleports `get` to the start while the walker is still parked in the tail (dropped ~31 KB incl. the fence) | to offer |
| `0034-gcm-no-drain-recycle-runtime-callback.patch` | T024: no recycle from the drain thread while the title's context still uses the runtime buffer-full callback (raced it; one boot stuck on Loading) | to offer |
| `0035-spu-coherence-context-index.patch` | T030: private, unbounded context-pointer index for GETLLAR registry membership. Notification order, reservation semantics, and context ABI unchanged. 300-context lifecycle/collision tests and benchmark. 01.09: 588–589 vs 320–374 flips in 60 s, CPU unchanged | to offer |
| `0036-spurs-task-runs-once.patch` | T033: `cellSpursCreateTask` marks a task running before its ready bit is published, and both dispatch sites pass the task id explicitly (`spu_workload_dispatch_task_async`); a task exiting in the window started a second copy (542 per 90 s on SARPBC 01.09; the copies spun forever, ~1500% CPU). Flips 404 -> 1920, CPU 1532% -> 96% | to offer |
| `0037-vk-present-centre-readback.patch` | T024 (pi): `vk_cb_present` copies a 1x1 centre texel instead of the whole frame unless a PPM dump is due (3.6 MB + a round trip per present before). Test `libs/video/tests/test_vulkan_present_readback.py` (mocked Vulkan, `--sanitize`) | to offer |
| `0038-vk-engine-draw-batching.patch` | T040: Vulkan engine draws batched into one command buffer (per-draw arena slices + descriptor sets; flushed by any other GPU op, destroy or `submit_and_wait`), vertex/index content cache in device-local host-visible memory, unchanged constants reused, no present readback on the engine path. `PS3RECOMP_VK_BATCH=0`, `PS3RECOMP_VK_GEO_CACHE=0`, diagnostics `PS3RECOMP_VK_BATCH_STATS`, `PS3RECOMP_VK_DRAW_TIMES`. SARPBC Choose Profile ~23 -> 32.5 fps, main menu 19.8 -> 29.5 (with 0038/0039) | to offer |
| `0039-vk-wayland-surface-formats.patch` | T042: allocate the complete Vulkan surface-format list instead of truncating it to 64; retry `VK_INCOMPLETE` up to four times. RADV Wayland reports 99 pairs on this desktop. GPU-independent tests cover selection, changing counts, errors and allocation cleanup | to offer |
| `0040-spurs-taskset-attribute-args.patch` | T037 (Claude; pi integration tests): retain the taskset attribute's 64-bit argument and per-SPU priority bytes, and forward the argument into taskset creation. Collision tasks previously received a zero work-pool argument and blocked arena loading. Tests cover full-width arguments, priority byte order and existing layout/canary validation | to offer |
| `0041-spurs-job-completion-events.patch` | T037 (pi): port the MIT fork's `SPURS_JC_DONE_EVENTS=0` gate without changing the runtime's legacy default. SARPBC disables fabricated job completions in its own config: a ShaderPatching job-index-0 broadcast otherwise shuts down the attached slab service. Tests cover opt-out, default/explicit enable, payloads and intact real SPU port bindings | to offer |
| `0042-spurs-priority-array.patch` | T037 integration review: priorities are a guest byte-array pointer, not a packed integer. Copy the table with backing validation; retain Claude's full-width taskset argument repair. Tests use distinct priority bytes and ensure bad backing leaves the attribute intact | to offer |
| `0043-gcm-interrupt-affinity.patch` | T044: with a dedicated GCM interrupt worker, foreign HLE callers leave callbacks pending instead of stealing them onto a render thread that may wait for itself. Keep manual/no-worker fallback and clean up failed startup. GCC/Clang tests cover ownership, pending ticks, FIFO/exact-once delivery and mocked CreateThread failure | to offer |
| `0044-zstencil-clear-zero.patch` | T045: the draw engine clears depth to 0 when `ZSTENCIL_CLEAR_VALUE` is 0 instead of reading 0 as 1.0 (the register is already seeded with the nv40 reset 0xFFFFFF00). Reversed-Z titles (GEQUAL) drew nothing: SARPBC's arena was black. The pass capture logs each clear's values. No dedicated regression test yet; the D3D12 path (`rsx_live_draw.c`) has the same special case | to offer |
| `0045-pass-dump-textures.patch` | T045: the pass capture logs each sampled texture's mip count, pitch, filter and control0, and `RSX_ENGINE_PASS_DUMP_TEX=1` writes every texture level decoded during the capture (BC as .dds), re-decoding the cached ones once. `draws.txt` also has each texture's wrap register (its compare function). Diagnostics only | to offer |
| `0046-nv0039-copy-engine.patch` | T045: NV0039 copies (libgcm's default subchannel 1: cellGcmSetTransferData, and report-area copies) are performed; subchannel 1 is NV0039 until it carries a method NV0039 lacks (keeps Twisted Metal's NV4097 there); only 3D-routed subchannels reach the draw engine (NV3062/NV3089 methods were overwriting alpha-test/blend registers). SARPBC's arena textures and HUD sampled stale VRAM without it. Test `tools/test_gcm_nv0039.py` | to offer |
| `0047-shadow-compare-direction.patch` | T045: depth-texture compares are `depth OP reference` (RSX), not ARB_shadow's `reference OP depth` (upstream 4033da8). SARPBC's car shadow (normal-Z map, zfunc GEQUAL) was a dark square over the whole shadow frustum. Helper, `docs/SHADOW_COMPARISON.md` and the Metal test's expected values flipped; the C shadow tests pass unchanged; Metal test not run on Linux | to offer (explain with the title evidence) |
| `0048-fp-alpha-ref-float-formats.patch` | Alpha-test reference read in the SDK's float surface formats (0x0B half, 0x0C/0x0D float; it checked 14/15/16), as the fork's `3f20f13`. SARPBC's arena renders into FP16 (0x0B). Test `tools/test_fp_alpha_ref.py` | to offer |
| `0049-zero-vertex-stride-constant.patch` | T021 port of fork `0eee9dd` (soyjxck, author kept): a zero vertex stride is a constant attribute, not a packed array (UE3's shared white vertex-colour stream). Draw-engine C tests pass | fork author's fix: offer with them |
| `0050-loadscreen-passthrough-orientation.patch` | T038 historical workaround: flips Y for every two-instruction guest VP. T050 disproved its generic safety; the cause was ignored PNG output row order, not projection-dependent Vulkan behavior. T051 removes this heuristic | superseded; do not offer |
| `0051-pngdec-output-mode.patch` | T051: honour and report per-decoder PNG top-to-bottom/bottom-to-top output order; reject invalid modes atomically. Synthetic guest-ABI coverage for 72 row-order/channel/pitch cases and invalid-mode handling | to offer |
| `0052-shader-independent-viewports.patch` | T051: fully undo 0050's shader-length Y flip after fixing the decoder cause. Add neutral-backend regressions for equivalent NOP-padded VPs, constant/arithmetic VPs, both viewport signs and non-centered offsets | reversal is downstream-only; offer tests |
| `0053-vulkan-shared-render-pass.patch` | T040: consecutive engine draws into one framebuffer share a render pass (a per-draw pass loaded/stored every attachment: ~33 us x 400 draws a menu frame); a draw sampling its own attachment still starts a new pass | Vulkan-only; offer upstream |
| `0054-vertex-decode-inline.patch` | T040: `rsx_vertex_decode_element` with the type switch outside the component loop, inlined into `rsx_vertex_fetch_one`; bit-identical (2M random cases vs the old loop) | generic, offer upstream |
| `0055-vulkan-batch-clears-snapshots.patch` | T040: colour/depth clears and colour snapshots record into the open draw batch (ends the shared render pass) instead of submit-and-wait | Vulkan-only; offer upstream |
| `0056-vertex-fetch-all.patch` | T040: `rsx_vertex_fetch_all` fetches a draw attribute by attribute (type switch and plan resolved once per attribute); the draw engine uses it. Checked byte for byte against `rsx_vertex_fetch_one` in test_vertex_fetch_plan | generic, offer upstream |
| `0057-callback-stack-lock-and-tls.patch` | T034: callback stacks are carved by `ppu_stack_carve()` under the thread-table lock instead of relying on a 16 MB headroom; a callback runs with the calling guest thread's r13 (its TLS block) and the shared block only on host-only threads. Tests: r13 inheritance, carve/allocate race | generic, offer upstream |
| `0058-unresolved-imports-report.patch` | T020: unresolved imports take `ps3_hle_unresolved()`: one report per NID with the first caller's lr and thread (no 40-NID cap), thread-safe, `PS3_HLE_UNRESOLVED=fail` works (it was dead code). Test: 8 threads x 3 NIDs, both modes | generic, offer upstream |
| `0059-netctl-offline-dialog-canceled.patch` | T014: offline `cellNetCtlNetStartDialogUnloadAsync` reports DIALOG_CANCELED (result 0 = connected contradicted the failing GetState, so SARPBC's Play Online sat on 'Logging in...' for ~18 s before 'Timed out'; now the online-service error shows within ~8 s). `PS3_NET_ONLINE=1` keeps result 0 | generic, offer upstream |
| `0060-spu-x86-qbyte-fast-float-lean-ls.patch` | T053: x86 pshufb quadword byte shifts/rotates (lqd+rotqby was a ~100-instruction byte loop), opt-in SPU_FAST_FLOAT (native SSE fa/fm/fma) and SPU_LEAN_LS (no LS probes) per translation unit; tests test_spu_qbyte.c, test_spu_fast_float.c | generic, offer upstream |
| `0061-usleep-scale-by-thread-name.patch` | T053: PS3_USLEEP_SCALE=<thread name>:<percent> shortens the sleeps of a named PPU thread (a guest loop napping a hardware-sized interval around work that is several times slower on the host) | generic, offer upstream |
| `0062-audio-gaps-diagnostics.patch` | T053: AUDIO_GAPS ring-map log when a block is empty at read time; PS3_FTRACE kind 15 (silent block instants) | generic, offer upstream |
| `0063-pass-dump-alpha.patch` | T054: RSX_ENGINE_PASS_DUMP_ALPHA dumps FP16 target alpha (screen-space shadow depth) | generic diagnostic, offer upstream |
| `0064-depth-snapshot-crop.patch` | T054: depth snapshot cropped to the sampling texture; a 512x512 shadow map in the 1280x720 zeta was sampled whole, so the car shadow landed in the wrong place and swam | generic, offer upstream (dod3 'cropped depth copies for shadows') |
| `0065-fp-ddx-ddy-nrm.patch` | T021 (Port next 8): fp decompiler DDX/DDY and NRM zero vector, from fork c42065f+93dbfdd | generic, ported from soyjxck fork (MIT), offer upstream |
| `0066-vulkan-anisotropic.patch` | T021 (Port next 10b): anisotropic filtering of mipmapped guest textures, RSX_ANISO (idea: fork 66fd0a9) | generic Vulkan, offer upstream |
| `0067-coherent-taskset-lifecycle.patch` | T052: serialize guest task-exit bitsets and PPU bitset read/modify/write with the SPU lock-line lock; invalidate stale reservations and dispatch after unlocking. Prevents completed tasks being resurrected and producing stale extra queue results. 419 synthetic checks cover tagged ELFs, reservation loss, all 128 task bits and store hooks; ASan/UBSan clean. Both boundaries are required; see docs/debugging.md | generic, offer upstream |
| `0068-spu-dma-put-fast-paths.patch` | T032: DMA PUT asks the reserved-line bitmap about its whole span at once (`spu_coh_span_reserved`), the POISON-DMA payload scan is opt-in (`SPU_POISON_DMA=1`), and the wedged-job repeat detector keeps its state per context in `mfc_engine` instead of shared statics. Bench (`bench_spu_dma.c`): PUT 1 KiB 167 -> 55 ns, 16 KiB 1961 -> 335 ns, lists 2.6x, 8-thread aggregate 3.7x; arena mixer thread DMA 84 -> 62 ms/s. Test: `tools/test_spu_dma_hotpath.py` (byte model + digest) | generic, offer upstream |
| `0069-gcm-spu-put-lookup.patch` | T056: conservative atomic EA-region occupancy and allocation high-water mark reject unmapped SPU PUTs without scanning 512 IO slots; preserves sparse mappings and pushbuffer coalescing. 50k randomized oracle comparisons, boundary/full-table tests and ASan/UBSan; actual hook ~257 to ~21.6 ns in arena | generic, offer upstream |
| `0070-pipe-times.patch` | T059: RSX_ENGINE_PIPE_TIMES per-pipeline build time diagnostic | generic diagnostic |

Making a new one: commit inside `external/ps3recomp` on branch `sarpbc-patches`, then
`tools/export_patch.sh <slug> "<description>" ["<upstream status>"]` (next free number, the README row,
and a check that the branch is exactly the stack plus your commit; `--count N` for a short series).
By hand that is `git -C external/ps3recomp format-patch -1 -o ../../patches/ps3recomp/ --start-number N`.
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
