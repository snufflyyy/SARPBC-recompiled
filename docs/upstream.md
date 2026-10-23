# Upstream contributions (T013)

Ready-to-file descriptions for our `patches/ps3recomp/` stack against `sp00nznet/ps3recomp`.
**Nothing here has been pushed, forked or opened. Filing anything on GitHub needs the user's
approval; ask first.** Our pin is upstream's `master` HEAD (v0.16.0, `749182e`, checked
2026-10-21 with `git ls-remote`), so the patches are already on current master: no rebase is needed
until upstream moves. `tools/apply_patches.sh` proves the stack applies from the pin.

How to make a PR from a group: branch from upstream master in a scratch clone, `git am` the group's
patches (they are `git format-patch` output, in numeric order; a patch that depends on an earlier
one in another group is noted), run `tools/lint.py --tests`-equivalent tests that the patch ships
with, then use the group's text below. Patches marked "fork author" carry soyjxck's authorship (MIT).
Not offered: 0050 (superseded by 0052).

Status of every group: **drafted, not filed.**


## PR A: SPU function finder and overlay lifting

**Motivation.** build_spu_workloads / find_spu_functions mis-lift stripped SPU images: .rodata lifted as code, overlays dropped, static ctors unseeded.

**Evidence.** Run on a title with section-stripped SPU ELFs and overlays (SARPBC's PhysX and MultiStream images). Unit tests in each patch.

| Patch | Change | Status in our README |
|---|---|---|
| `0005-spu-detector-rodata-seeds.patch` | T016: SPU function finder keeps an `ila`/branch/table seed only if it decodes as code, isn't a NUL-terminated string, and reaches a branch/stop (section-stripped images lifted .rodata as code); test added | to offer |
| `0006-cellovis-overlay-table.patch` | T003: real `cellOvisGetOverlayTableSize`/`InitializeOverlayTable` (upstream's were invented API); test | to offer |
| `0007-spu-overlay-lift.patch` | T003: build_spu_workloads lifts SPU images with overlays (resident code + one code overlay as one LS image); drops data-only ranges. Rebased onto 0006 by the coordinator (merged seed filter + cross-segment call seeds) | to offer |
| `0026-spu-seed-ctors-dtors.patch` | T025: `find_spu_functions.py` seeds `.ctors/.dtors/.init_array/.fini_array` entries (and `-1..0` framed lists in stripped images); PhysX LS 0x20180 is a static ctor | to offer |
| `0029-spu-ctor-dtor-seed-test.patch` | T025: unit test for `collect_ctor_dtor_targets` (0028) | with 0028 |

## PR B: SPU runtime performance and coherence

**Motivation.** SPU DMA/atomics and float paths cost far more on Linux than they need to.

**Evidence.** 01.09 flips 100 -> 514 (0031) and 320 -> 588 per minute (0035); fma+fm 12 ns vs 33 ns (0030). Bit-exact and lifecycle tests.

| Patch | Change | Status in our README |
|---|---|---|
| `0016-spu-task-thread-stack-uaf.patch` | T023: fork 0012+0148 (soyjxck): Linux SPU task thread leaves the lock-line reserver set when it ends, plus ours: and the MFC slot table (as on Windows) | fork author's work |
| `0030-spu-sse2-float-helpers.patch` | T025: SSE2 port of the NEON `fa/fs/fm/fma/fms/fnms` fast path in `spu_helpers.h`, bit-exact (`test_spu_float_sse.c`); fma+fm 12 ns vs 33 ns | to offer |
| `0031-spu-mfc-cache-lockline-ttas.patch` | T030: `mfc_for` looks up the engine only for MFC_Cmd/WrTagUpdate/WrListStallAck, cached in `spu_context` (`mfc_cache`, `mfc_cache_gen`, invalidated by a registry generation); POSIX `spu_lockline_lock` is TTAS + `_mm_pause` + `sched_yield`/256 like MSVC. 01.09 flips 100 -> 514 in 90 s (one run) | to offer |
| `0035-spu-coherence-context-index.patch` | T030: private, unbounded context-pointer index for GETLLAR registry membership. Notification order, reservation semantics, and context ABI unchanged. 300-context lifecycle/collision tests and benchmark. 01.09: 588–589 vs 320–374 flips in 60 s, CPU unchanged | to offer |

## PR C: SPURS (tasksets, queues, job chains)

**Motivation.** SPURS HLE gaps seen by a UE3 title: queue PPU side, error codes, taskset attributes, job chain re-walks, double-started tasks.

**Evidence.** Each patch names its failing boot (loading never finishing, ShaderPatching jobs never running, 1500% CPU spin). Tests per patch; 0041 keeps the legacy default.

| Patch | Change | Status in our README |
|---|---|---|
| `0013-spurs-queue-ppu.patch` | T019: real PPU side of SPURS Queue (PopBody/PushBody, attach/detach) and LFQueue init in the task-side layout | to offer |
| `0020-spurs-task-error-codes.patch` | T023: `CELL_SPURS_TASK_ERROR_*` use the SDK's 0x804109xx values (were 0x804107xx) | to offer |
| `0022-spurs-job-chain-rewalk-resume-guard.patch` | T022: a RunJobChain that arrives mid-walk queues a re-walk (it was dropped, so ShaderPatching jobs that release FIFO parks never ran); walks resume where they stopped; a never-notified guard waits 200 ms, not 20 s. Ported from soyjxck/ps3recomp 26fdd50, 0f2870a, 6371138 (MIT) | fork author's work |
| `0036-spurs-task-runs-once.patch` | T033: `cellSpursCreateTask` marks a task running before its ready bit is published, and both dispatch sites pass the task id explicitly (`spu_workload_dispatch_task_async`); a task exiting in the window started a second copy (542 per 90 s on SARPBC 01.09; the copies spun forever, ~1500% CPU). Flips 404 -> 1920, CPU 1532% -> 96% | to offer |
| `0040-spurs-taskset-attribute-args.patch` | T037 (Claude; pi integration tests): retain the taskset attribute's 64-bit argument and per-SPU priority bytes, and forward the argument into taskset creation. Collision tasks previously received a zero work-pool argument and blocked arena loading. Tests cover full-width arguments, priority byte order and existing layout/canary validation | to offer |
| `0041-spurs-job-completion-events.patch` | T037 (pi): port the MIT fork's `SPURS_JC_DONE_EVENTS=0` gate without changing the runtime's legacy default. SARPBC disables fabricated job completions in its own config: a ShaderPatching job-index-0 broadcast otherwise shuts down the attached slab service. Tests cover opt-out, default/explicit enable, payloads and intact real SPU port bindings | to offer |
| `0042-spurs-priority-array.patch` | T037 integration review: priorities are a guest byte-array pointer, not a packed integer. Copy the table with backing validation; retain Claude's full-width taskset argument repair. Tests use distinct priority bytes and ensure bad backing leaves the attribute intact | to offer |
| `0085-spu-job-fingerprint-memo.patch` | T075: content-verified memo of the job-image FNV fingerprint (46 of 67 us per ShaderPatching job); exact when the binary at an address changes | to offer |
| `0086-spu-job-context-pool.patch` | T075: pooled job contexts staged in place, store copied out only after a title polls for it (+ `tools/test_spu_job_hotpath.py`) | to offer |
| `0087-spurs-job-chain-linger.patch` | T075: the walker waits 1 ms (`SPURS_JC_LINGER_US`) for the next Run instead of one host thread per Run; Join ends the wait | to offer |
| `0089-vulkan-output-size.patch` | `rsx_vulkan_backend_output_size` (the window's drawable size, from the event pump) so a host can make the render scale relative to the output; the scale limit 4 to 8 | to offer |
| `0090-ppu-inline-stores.patch` | Lifted guest stores take an inline fast path like loads (`vm_store_span`, exported `spu_coh_bitmap`, `PPU_SLOW_STORES` A/B switch, `tools/test_ppu_inline_stores.py`); needs a re-lift. Mini-Games 31 to 44 fps | to offer |

## PR D: GCM command processing and interrupt delivery

**Motivation.** Ordering and recycle bugs in the GCM FIFO pump and callbacks.

**Evidence.** 0032: SetPrepareFlip returned no id so every flip was buffer 0; 0033/0034: dropped commands on ring recycle; 0043: callback stealing deadlock. Tests per patch.

| Patch | Change | Status in our README |
|---|---|---|
| `0023-gcm-user-command-queue.patch` | T024: fork 0018 (soyjxck d2e6c1b): user commands queue in order instead of sharing one slot | fork author's work |
| `0024-gcm-pump-fast-exit.patch` | T024: fork 0139 (soyjxck b6e4e18): GCM pump fast exit | fork author's work |
| `0025-gcm-intr-thread-park-handling.patch` | T024: the stuck-get watchdog no longer resyncs away from a jump-to-itself park; `GCM_PARK_GRACE_MS` (50), `GCM_PARK_LOG`, opt-in `GCM_INTR_THREAD=1` host interrupt thread for vblank/flip/user handlers | to offer |
| `0032-gcm-prepare-flip-returns-id.patch` | T024: `cellGcmSetPrepareFlip` returns the buffer id and does not flip on the spot (part of fork 0049); SARPBC's user handler 0xDC390 flips the id it got back, so every flip was buffer 0. The historical `GCM_PREPARE_FLIPS_NOW` toggle was removed by T058, which completes the prepared FIFO path while preserving PPU callback policy. Test `test_gcm_prepare_flip.py` | to offer |
| `0033-gcm-ring-recycle-drains-tail.patch` | T024: recycling the title's ring no longer teleports `get` to the start while the walker is still parked in the tail (dropped ~31 KB incl. the fence) | to offer |
| `0034-gcm-no-drain-recycle-runtime-callback.patch` | T024: no recycle from the drain thread while the title's context still uses the runtime buffer-full callback (raced it; one boot stuck on Loading) | to offer |
| `0043-gcm-interrupt-affinity.patch` | T044: with a dedicated GCM interrupt worker, foreign HLE callers leave callbacks pending instead of stealing them onto a render thread that may wait for itself. Keep manual/no-worker fallback and clean up failed startup. GCC/Clang tests cover ownership, pending ticks, FIFO/exact-once delivery and mocked CreateThread failure | to offer |

## PR E: PPU threads, memory and callbacks

**Motivation.** Guest memory/threads/callbacks: freed-range reuse, thread slot and stack reuse, per-thread callback stacks, writer-preferring SRW locks, lwcond wakeups.

**Evidence.** UE3 ran out of mmapper window after ~256 MB churn (0004); shared callback stack aliased RSX memory (0028, 0057); writer starvation (0027). Tests.

| Patch | Change | Status in our README |
|---|---|---|
| `0004-sys-memory-reuse-freed-ranges.patch` | T001: the sys_memory/mmapper window is a sorted range table with first-fit reuse (the bump pointer ran out after ~256 MB of churn: UE3 OOM) | to offer |
| `0017-lwcond-signals-wake.patch` | T023: fork 0100: `sys_lwcond_signal*` wake waiters (was a 1 ms sleep poll); adapted to our semaphore lwmutex; test `tools/test_ppu_lwcond_wake.py` | fork author's work |
| `0018-ppu-thread-slots-stacks.patch` | T023: fork 0166+0167: ended PPU threads give back their slot and guest stack; non-joinable threads self-free | fork author's work |
| `0027-win32-compat-srw-writer-preference.patch` | T027: SRW-lock emulation prefers writers on glibc (`PTHREAD_RWLOCK_PREFER_WRITER_NONRECURSIVE_NP`); fixes the ShaderPatching job starving on `mfc_for` with 01.09 at the ESRB screen. Test `test_srw_writer_progress` | to offer |
| `0028-ppu-guest-call-stacks.patch` | T026: `ppu_guest_call`/`_ct` run each callback on a per-(host thread, nesting depth) stack carved from the top of the PPU stack region (256 KB + guard page, pooled; `PPU_CB_STACK_SIZE`), not the shared 0xCFFE0000 that also sat in RSX local memory. Test `test_ppu_guest_call_stacks.py` | to offer |
| `0057-callback-stack-lock-and-tls.patch` | T034: callback stacks are carved by `ppu_stack_carve()` under the thread-table lock instead of relying on a 16 MB headroom; a callback runs with the calling guest thread's r13 (its TLS block) and the shared block only on host-only threads. Tests: r13 inheritance, carve/allocate race | generic, offer upstream |

## PR F: HLE modules with invented or missing APIs

**Motivation.** cellMsgDialog error code, cellVoice InitEx, cellMusic, cellRec/VideoExport/VideoUpload names, sys_prx, offline sys_net, unresolved-import reporting.

**Evidence.** Each fixes an import that matched no NID or faked CELL_OK where the title waits on a callback. Tests per module.

| Patch | Change | Status in our README |
|---|---|---|
| `0002-hle-trivial-missing-imports.patch` | T004: offline sys_net model (connect/accept/send fail cleanly), cellKbRead, OSK device mask, SPURS queue detach, `_sys_spu_printf_initialize/finalize` | to offer |
| `0003-sys-prx-load-module.patch` | T002: `sys_prx_load_module/start/stop/unload` with a PRX loader (`runtime/prx/prx_runtime.c`), relocations, exports, `module_start` via lifted code or a strict leaf evaluator | to offer |
| `0008-cellMsgDialogOpenErrorCode.patch` | T020: `cellMsgDialogOpenErrorCode` prints the code and delivers BUTTON_OK on the next sysutil poll (the unresolved path never called back) | to offer |
| `0009-cellVoice-InitEx-StartEx-notify-queue.patch` | T020: `cellVoiceInitEx/StartEx` and a real notify event queue (the faked CELL_OK left libvoice uninitialized and the queue id unwritten) | to offer |
| `0010-cellMusic-utility.patch` | T020: cellMusic utility as an empty library whose result callbacks fire (01.09 polls a mailbox at 0x00092F10) | to offer |
| `0011-cellRec-videoexport-videoupload-sdk-names.patch` | T020: cellRec/cellVideoExport/cellVideoUpload define the SDK entry points (invented names matched no NID) | to offer |
| `0058-unresolved-imports-report.patch` | T020: unresolved imports take `ps3_hle_unresolved()`: one report per NID with the first caller's lr and thread (no 40-NID cap), thread-safe, `PS3_HLE_UNRESOLVED=fail` works (it was dead code). Test: 8 threads x 3 NIDs, both modes | generic, offer upstream |

## PR G: Input (SDL pad) and filesystem overlay

**Motivation.** The Drakengard 3 fork's pad work and fs overlay, plus fixes. Authored by soyjxck (MIT); authors must stay on the commits.

**Evidence.** Offer together with the fork author or point at their repo; do not file as ours alone.

| Patch | Change | Status in our README |
|---|---|---|
| `0012-sys-fs-h-open-flags-test.patch` | T021 (from the dod3 fork): sys_fs.h octal open flags; cellFsOpen flag test | to offer (fork author's fix) |
| `0014-dod3-cellpad-sdl2-port.patch` | T008: Drakengard 3 fork's 13 libs/input commits (SDL pad thread, pads by instance id, rumble held, `cellPad_set_host_input`, host kind, PAD_NO_HOST); soyjxck, MIT, authors kept | fork author's work: offer with them |
| `0015-cellpad-racing-fixes.patch` | T008: press-mode trigger pressure (a half pull read 255), small motor on/off at 0xFFFF, empty ports' sticks centred at 128, `PAD_TRIGGERS`/`PAD_TRACE`; test `libs/input/tests/test_cellpad_sdl.py` | to offer |
| `0019-sys-fs-overlay-hdd0-symlinks.patch` | T023: fork 0119/0131/0132: `PS3_VFS_OVERLAY`, existing `/dev_hdd0` paths used directly, readdir lists symlinked dirs as dirs | fork author's work |

## PR H: Vulkan backend

**Motivation.** Draw batching, shared render passes, batched clears/snapshots, cheap present readback, complete Wayland surface format list.

**Evidence.** RTX 2070 SUPER, PCIe 2.0 x4: Single Player 19.5 -> 54 fps, arena ~30 -> 38 (0038, 0053, 0055). Validation layer clean. Vulkan-only.

| Patch | Change | Status in our README |
|---|---|---|
| `0037-vk-present-centre-readback.patch` | T024 (pi): `vk_cb_present` copies a 1x1 centre texel instead of the whole frame unless a PPM dump is due (3.6 MB + a round trip per present before). Test `libs/video/tests/test_vulkan_present_readback.py` (mocked Vulkan, `--sanitize`) | to offer |
| `0038-vk-engine-draw-batching.patch` | T040: Vulkan engine draws batched into one command buffer (per-draw arena slices + descriptor sets; flushed by any other GPU op, destroy or `submit_and_wait`), vertex/index content cache in device-local host-visible memory, unchanged constants reused, no present readback on the engine path. `PS3RECOMP_VK_BATCH=0`, `PS3RECOMP_VK_GEO_CACHE=0`, diagnostics `PS3RECOMP_VK_BATCH_STATS`, `PS3RECOMP_VK_DRAW_TIMES`. SARPBC Choose Profile ~23 -> 32.5 fps, main menu 19.8 -> 29.5 (with 0038/0039) | to offer |
| `0039-vk-wayland-surface-formats.patch` | T042: allocate the complete Vulkan surface-format list instead of truncating it to 64; retry `VK_INCOMPLETE` up to four times. RADV Wayland reports 99 pairs on this desktop. GPU-independent tests cover selection, changing counts, errors and allocation cleanup | to offer |
| `0053-vulkan-shared-render-pass.patch` | T040: consecutive engine draws into one framebuffer share a render pass (a per-draw pass loaded/stored every attachment: ~33 us x 400 draws a menu frame); a draw sampling its own attachment still starts a new pass | Vulkan-only; offer upstream |
| `0055-vulkan-batch-clears-snapshots.patch` | T040: colour/depth clears and colour snapshots record into the open draw batch (ends the shared render pass) instead of submit-and-wait | Vulkan-only; offer upstream |

## PR I: RSX draw engine and vertex fetch

**Motivation.** Reversed-Z clear, NV0039 copies, shadow compare direction, float surface alpha ref, zero-stride constants, vertex fetch speed, PNG decoder output order, viewport/VP independence.

**Evidence.** Each has the title evidence in its message (black arena, shadow squares, upside-down loading screen). 0054 and 0056 are bit/byte-exact against the old code.

| Patch | Change | Status in our README |
|---|---|---|
| `0044-zstencil-clear-zero.patch` | T045: the draw engine clears depth to 0 when `ZSTENCIL_CLEAR_VALUE` is 0 instead of reading 0 as 1.0 (the register is already seeded with the nv40 reset 0xFFFFFF00). Reversed-Z titles (GEQUAL) drew nothing: SARPBC's arena was black. The pass capture logs each clear's values. No dedicated regression test yet; the D3D12 path (`rsx_live_draw.c`) has the same special case | to offer |
| `0045-pass-dump-textures.patch` | T045: the pass capture logs each sampled texture's mip count, pitch, filter and control0, and `RSX_ENGINE_PASS_DUMP_TEX=1` writes every texture level decoded during the capture (BC as .dds), re-decoding the cached ones once. `draws.txt` also has each texture's wrap register (its compare function). Diagnostics only | to offer |
| `0046-nv0039-copy-engine.patch` | T045: NV0039 copies (libgcm's default subchannel 1: cellGcmSetTransferData, and report-area copies) are performed; subchannel 1 is NV0039 until it carries a method NV0039 lacks (keeps Twisted Metal's NV4097 there); only 3D-routed subchannels reach the draw engine (NV3062/NV3089 methods were overwriting alpha-test/blend registers). SARPBC's arena textures and HUD sampled stale VRAM without it. Test `tools/test_gcm_nv0039.py` | to offer |
| `0047-shadow-compare-direction.patch` | T045: depth-texture compares are `depth OP reference` (RSX), not ARB_shadow's `reference OP depth` (upstream 4033da8). SARPBC's car shadow (normal-Z map, zfunc GEQUAL) was a dark square over the whole shadow frustum. Helper, `docs/SHADOW_COMPARISON.md` and the Metal test's expected values flipped; the C shadow tests pass unchanged; Metal test not run on Linux | to offer (explain with the title evidence) |
| `0048-fp-alpha-ref-float-formats.patch` | Alpha-test reference read in the SDK's float surface formats (0x0B half, 0x0C/0x0D float; it checked 14/15/16), as the fork's `3f20f13`. SARPBC's arena renders into FP16 (0x0B). Test `tools/test_fp_alpha_ref.py` | to offer |
| `0049-zero-vertex-stride-constant.patch` | T021 port of fork `0eee9dd` (soyjxck, author kept): a zero vertex stride is a constant attribute, not a packed array (UE3's shared white vertex-colour stream). Draw-engine C tests pass | fork author's fix: offer with them |
| `0051-pngdec-output-mode.patch` | T051: honour and report per-decoder PNG top-to-bottom/bottom-to-top output order; reject invalid modes atomically. Synthetic guest-ABI coverage for 72 row-order/channel/pitch cases and invalid-mode handling | to offer |
| `0052-shader-independent-viewports.patch` | T051: fully undo 0050's shader-length Y flip after fixing the decoder cause. Add neutral-backend regressions for equivalent NOP-padded VPs, constant/arithmetic VPs, both viewport signs and non-centered offsets | reversal is downstream-only; offer tests |
| `0054-vertex-decode-inline.patch` | T040: `rsx_vertex_decode_element` with the type switch outside the component loop, inlined into `rsx_vertex_fetch_one`; bit-identical (2M random cases vs the old loop) | generic, offer upstream |
| `0056-vertex-fetch-all.patch` | T040: `rsx_vertex_fetch_all` fetches a draw attribute by attribute (type switch and plan resolved once per attribute); the draw engine uses it. Checked byte for byte against `rsx_vertex_fetch_one` in test_vertex_fetch_plan | generic, offer upstream |

## PR J: Trophy and audio

**Motivation.** sceNpTrophyRegisterContext delivery (reverts a recent upstream choice: explain the firmware ordering) and POSIX audio pacing.

**Evidence.** 0001 changes behavior upstream chose recently: needs the strongest write-up.

| Patch | Change | Status in our README |
|---|---|---|
| `0001-trophy-deliver-RegisterContext-statuses-synchronousl.patch` | `sceNpTrophyRegisterContext` delivers PROCESSING_COMPLETE synchronously again (17047c9 deferred it, which races SARPBC's -1 "done" marker); test updated | to offer (it reverts a recent upstream choice, so explain the firmware ordering) |
| `0021-audio-pacing-devflash-sig-region.patch` | T007: POSIX cellAudio pacing (+ `AUDIO_RATE`/`AUDIO_PEAK`/`AUDIO_WAV`), `/dev_flash` default off a Windows path, `spu_overlay_register_sig_region` (register an overlay by its first bytes over a span; used by `tools/make_spu_overlays.py`) | to offer |

## Not grouped

none
