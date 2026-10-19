# T030: SPU perf: busy-wait loops (GETLLAR reservation spins, channel waits, idle SPURS kernels)

Status: open
Owner: -
Touches: patches/ps3recomp/T030-*.patch (runtime/spu/spu_channels.c, runtime/spu/spu_coherency.*)
Reads: T022 notes (GETLLAR 0x0133B880 spin), T028 notes, docs/subsystems.md

## Goal
**Phase: SPU performance, easy wins only** (user, 2026-10-19). Start after the main menu is reached. Measure before and after every change: T029's harness once it exists, otherwise `perf record` on a 60 s 01.09 boot_check and the T025 mixer metric (`SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000`). Keep a change only if the numbers improve and the SPU tests pass; results must stay bit-exact. Nothing deep (no new JIT, no lifter redesign). Write anything bigger up as a proposed task instead.

SPU code on PS3 often waits by polling: GETLLAR or lost-reservation loops, channel reads, SPURS kernels polling for work. On the host each of these burns a whole core and starves real work (T022 saw dozens of spinning PhysX threads). Find the hot wait loops (T029, perf) and make them cheap without changing semantics: backoff, `_mm_pause`, a futex or condvar wait on reservation-lost or channel events, wakeups on writes to the reservation granule. T027 owns runtime/platform locks.

## Done when
Before/after numbers in docs/subsystems.md (SPU/SPURS section, your own subsection), tests green, patches apply in the stack.

## Log
