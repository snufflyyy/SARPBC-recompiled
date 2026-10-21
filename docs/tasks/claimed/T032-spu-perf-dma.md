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
