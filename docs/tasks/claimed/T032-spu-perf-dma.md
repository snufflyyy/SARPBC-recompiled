# T032: SPU perf: DMA/MFC fast paths and lock granularity

Status: claimed
Owner: opus-2
Priority: 4
Touches: patches/ps3recomp/T032-*.patch (runtime/spu/spu_dma.h, runtime/spu/spu_drain.c, runtime/spu/spu_lockstep.*)
Reads: docs/tasks/*/T027* (the mfc_for rwlock), docs/subsystems.md

## Goal
**Phase: SPU performance, easy wins only** (user, 2026-10-19). Start after the main menu is reached. Measure before and after every change: T029's harness once it exists, otherwise `perf record` on a 60 s 01.09 boot_check and the T025 mixer metric (`SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000`). Keep a change only if the numbers improve and the SPU tests pass; results must stay bit-exact. Nothing deep (no new JIT, no lifter redesign). Write anything bigger up as a proposed task instead.

MFC DMA is on every SPU job's hot path. Find easy wins: memcpy fast paths for aligned and large transfers, avoiding byte-swapping or per-element loops where the layout allows, list-DMA batching, and a narrower lock scope than the global mfc_for rwlock (per-granule or per-page, with T027's writer-preference as the baseline). Check correctness against the coherency tests.

## Done when
Before/after numbers in docs/subsystems.md (SPU/SPURS section, your own subsection), tests green, patches apply in the stack.

## Log
- 2026-10-20 22:22 claude: 2026-10-20 measurement (main + 0053, Single Player screen, /proc thread CPU over 20 s at 72-92 s): whole game ~190% CPU; busiest threads 74%, 59%, 43% then 10%, 4%, rest ~0%. No thread looks like SPU spin; the T033 fix removed the 90% lock/spin of the 2026-10-19 profile. SPU speed is not limiting the menu/arena now, so no SPU change was made. Revisit only if an SPU-heavy scene (arena with physics/audio) shows SPU threads near 100%.
- 2026-10-21 13:38 opus-2: claimed
- 2026-10-21 14:26 opus-2: Scope: mfc_for is already lock-free on its hot path (cached slot + generation), so T027's rwlock is off the DMA path; changes are in spu_dma.h plus one new function spu_coh_span_reserved in spu_coherency.{c,h} (outside Touches, no claimed task owns it) and a one-line stub in runtime/spu/tests/test_mfc_resume_elements.c.
- 2026-10-21 14:26 opus-2: Measured (perf blocked; throwaway rdtsc wrapper around spu_wrch(MFC_Cmd), arena scenario 105-125 s): only ONE thread issues DMA, the MultiStream mixer SPU (spu_ovl_msdsp_37000_*, busiest thread ~85%): 168k GET/s 287 MB/s 161 ns each, 65k PUT/s 164 MB/s 853 ns each, ~600 atomics/s 1.2 us each, no lists. DMA = 83.7 ms/s of that thread. eu-stack -p <pid> works here as a stack sampler (gdb not needed).
- 2026-10-21 14:26 opus-2: PUT cost breakdown: per-128B-line spu_coh_is_reserved calls x2, POISON-DMA payload scan on every PUT (print-only; baseline printed 12 hitregion lines for ordinary PUTs into 0x40003000-0x40005000), shared repeat-detector statics (every DMA wrote one global line: 8-thread aggregate 35.6 ns/cmd vs 9.1 without it), and the GCM put hook gcm_note_spu_put walking 512 s_io_mappings (~300 ns/PUT, experiment with hook skipped: PUT 218 ns). Hook is libs/video -> new task T056.
- 2026-10-21 14:26 opus-2: Patch T032-spu-dma-put-fast-paths: spu_coh_span_reserved (bitmap bytes), SPU_POISON_DMA=1 gate, repeat state in mfc_engine (TLS version cost ~4 ns/DMA single-thread, engine field costs nothing). Bench bench_spu_dma.c same host: PUT 1K 167->55 ns, 4K 518->116, 16K 1961->335, GETL/PUTL 16x1K 1427->546, GET unchanged, 8 thr x128B 35.6->9.7 ns/cmd. Game (rdtsc build, 14x5 s): PUT 853->517 ns, mixer DMA 83.7->61.9 ms/s; mixer thread CPU 85.6/86.9% -> 82.3/83.7%; arena fps ~37 and process CPU ~211% unchanged (mixer is real-time paced). No 'identical transfers' halts before/after.
- 2026-10-21 14:26 opus-2: Tests: new tools/test_spu_dma_hotpath.py (real spu_dma.h+spu_coherency.c vs byte model, span check vs per-line on 200k random spans, per-context repeat halt; digest a1c01d73f9a48d1e; steps 1-4 digest 86102f76477d0bbe identical with baseline headers; baseline fails only the new per-context repeat check, as intended). clang+gcc+ASan/UBSan clean. All tools/test_spu_*.py, test_mfc_*.py, test_spurs*.py pass. Legacy runtime/spu/tests/run_tests.sh does not build at the pin (win32_compat.h clock_gettime/pthread_rwlockattr_t errors, untouched file) and rewrites its tracked out_* files.
