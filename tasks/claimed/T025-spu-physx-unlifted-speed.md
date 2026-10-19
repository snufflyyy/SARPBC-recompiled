# T025: PhysX unlifted LS 0x20180 + SPU x86 speed (SSE4.1 shufb, SIMD float helpers)

Status: claimed
Owner: agent-spuperf
Touches: CMakeLists.txt (compile flags only), patches/ps3recomp/T025-*.patch (runtime/spu/spu_helpers.h, runtime/spu/tests/** new tests, tools/build_spu_workloads.py / find_spu_functions.py only; narrowed 2026-10-19 so T030/T032/T033 can own the rest of runtime/spu), tools/make_spu_overlays.py (only to add a PhysX overlay case), docs/subsystems.md (SPU/SPURS section only)
Reads: tasks/done/T007*, tasks/done/T003*, docs/dod3-reuse.md

## Goal
**User priority: menus first.** After T007 the only unlifted SPU branch left in a 01.09 boot is in
PhysX (image 363824547, branch to LS 0x20180). Find out what lives at 0x20180 (a second PhysX
overlay? a DMA'd code block like MultiStream's?) and lift + register it the way T003/T007 did, so
the boot never falls into the interpreter. Second: SPU code is too slow on x86. T007 measured the
MultiStream mixer at 27% of real time (43% with -msse4.1); perf puts 37% in the byte-loop `shufb`
helper (no SSE4.1 path compiled) and ~17% in scalar `spu_fa/fs/fm/fma`. Build with
`-march=x86-64-v2` (or -msse4.1 on SPU sources) and add x86 SIMD paths in
`runtime/spu/spu_helpers.h` (upstream vectorises only for ARM). This speeds up PhysX and Edge too,
which loading depends on.

## Done when
No "unlifted LS" line in a 60 s 01.09 boot_check; mixer throughput (AUDIO_RATE=1) and a
boot_check summary before/after; numbers in docs/subsystems.md.

## Log
- 2026-10-19 09:33 agent-spuperf: claimed
- 2026-10-19 09:38 agent-spuperf: Baseline (build-0109, main d14c18c, 41 patches): boot_check 2026-10-19 09:38 v01.09 60s: STALLED since 21.6s | last open GUIDCACHE.XXX@3.6s | pkgs 13 | zlib 3147 | unresolved 0. Mixer: SPURS_EF_STATS flag 0x01372000 ~75 waits/s mean 11ms, SPU_DMA_RANGE PUT ~410 KB/s (27% of 1.536 MB/s). AUDIO_RATE port consumption 197.9 blocks/s silent 100% (dummy driver; that measures the port, not the mixer). LS 0x20180 = a C++ global ctor of SPU_DynamicsRelease.elf (image 7, 5af85a31): .ctors at 0x36E70 = {-1, 0x20180, 0}, crt0 loop at 0x20140 calls it via bisl; body is just 'bi $r0'. find_spu_functions.py never seeds .ctors/.dtors (fptr-table scan needs >=3 entries). 9 of 13 sectioned images have unseeded ctor/dtor entries.
- 2026-10-19 09:41 agent-spuperf: HANDOFF: done=patch T025-spu-seed-ctors-dtors (find_spu_functions.py seeds .ctors/.dtors/.init_array/.fini_array entries, plus -1..0 framed lists in stripped images). LS 0x20180 = PhysX Dynamics static ctor (.ctors {-1,0x20180,0}, called by the crt0 loop at 0x20140). An offline relift of 01.09 into scratchpad/agent-spuperf/spu_gen_0109 (no overlay/prxjob steps yet): 15/15 registered, complete, every ctor/dtor entry in 9 images now lifted; existing finder test OK; the stack applies (42 patches). Docs: subsystems.md SPU section (cause + baseline). state=not booted with the new lift. Baseline: STALLED since 21.6s | last open GUIDCACHE.XXX@3.6s | pkgs 13; mixer ~75 waits/s, PUT ~410 KB/s. Speed work not started. next=(1) finish the scratch lift: make_spu_overlays.py --spu <copy> and lift_prx_jobs.py versions/0109/game/SPUJOBS.prx --lifted <copy> --register <copy>/jobmods_register.c, then cmake -DSPU_DIR=<copy>, build and boot_check (expect no 'unlifted LS 0x20180'); add a unit test for collect_ctor_dtor_targets; (2) build SPU sources with -msse4.1/x86-64-v2 (CMakeLists, scoped to SPU+runtime), x86 SIMD spu_fa/fs/fm/fma in runtime/spu/spu_helpers.h; measure with SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000. branch=worktree-agent-a4cc29237e98a2e6f
- 2026-10-19 09:41 agent-spuperf: RELEASED: paused; see HANDOFF
- 2026-10-19 10:05 agent-spuperf: claimed
- 2026-10-19 10:07 agent-spuperf: Step 1 verified on main 171c84d (relifted 0109 lift, no SPU_INTERP_UNLIFTED): boot_check 2026-10-19 10:07 v01.09 171c84d 60s: STALLED since 30.1s | last open TEXTURES.TFC@6.1s | pkgs 13 (GUIDCACHE last) | zlib 3279 | dumps 5 lit 5 distinct 3 | flips 62 | threads 13/9 alive | unresolved 0 | alerts assert. 0 'unlifted' lines in the log. Still 52x '[spu] HALT-ASSERT heqi pc=0x24884 img=363824547' (PhysX).
- 2026-10-19 10:31 agent-spuperf: Ctor test: patches/ps3recomp/T025-spu-ctor-dtor-seed-test.patch (tools/test_spu_find_functions_ctors.py, 7 tests OK). Speed: T025-spu-sse2-float-helpers.patch = SSE2 port of the NEON fa/fs/fm/fma fast path (needs no flag); test_spu_float_sse.c bit-identical vs exact path (clang+gcc, -O2/v2/v3); microbench fma+fm 12 ns vs 33 ns scalar fast path. shufb already had an SSE4.1 path: the runtime lib builds with -msse4.1, but the lifted SPU TUs (built in our CMakeLists) did not -> CMakeLists adds -march=x86-64-v2 (SARPBC_SPU_X86_ARCH) to SPU_SOURCES only. A/B boot runs under lock boot in progress (base / shufb-only / full).
