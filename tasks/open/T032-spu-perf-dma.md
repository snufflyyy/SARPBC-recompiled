# T032: SPU perf: DMA/MFC fast paths and lock granularity

Status: open
Owner: -
Priority: 4
Touches: patches/ps3recomp/T032-*.patch (runtime/spu/spu_dma.h, runtime/spu/spu_drain.c, runtime/spu/spu_lockstep.*)
Reads: tasks/*/T027* (the mfc_for rwlock), docs/subsystems.md

## Goal
**Phase: SPU performance, easy wins only** (user, 2026-10-19). Start after the main menu is reached. Measure before and after every change: T029's harness once it exists, otherwise `perf record` on a 60 s 01.09 boot_check and the T025 mixer metric (`SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000`). Keep a change only if the numbers improve and the SPU tests pass; results must stay bit-exact. Nothing deep (no new JIT, no lifter redesign). Write anything bigger up as a proposed task instead.

MFC DMA is on every SPU job's hot path. Find easy wins: memcpy fast paths for aligned and large transfers, avoiding byte-swapping or per-element loops where the layout allows, list-DMA batching, and a narrower lock scope than the global mfc_for rwlock (per-granule or per-page, with T027's writer-preference as the baseline). Check correctness against the coherency tests.

## Done when
Before/after numbers in docs/subsystems.md (SPU/SPURS section, your own subsection), tests green, patches apply in the stack.

## Log
