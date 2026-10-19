# T030: SPU perf: busy-wait loops (GETLLAR reservation spins, channel waits, idle SPURS kernels)

Status: open
Owner: -
Touches: patches/ps3recomp/T030-*.patch (runtime/spu/spu_channels.c, runtime/spu/spu_coherency.*, runtime/spu/spu_context.h for a cached engine pointer only)
Reads: T022 notes (GETLLAR 0x0133B880 spin), T028 notes, docs/subsystems.md

## Goal
**Phase: SPU performance, easy wins only** (user, 2026-10-19). **Started early by the user (2026-10-19): one 01.09 boot uses ~1460% CPU (15 of 16 cores) because SPU threads spin.** Measure before and after every change: T029's harness once it exists, otherwise `perf record` on a 60 s 01.09 boot_check and the T025 mixer metric (`SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000`). Keep a change only if the numbers improve and the SPU tests pass; results must stay bit-exact. Nothing deep (no new JIT, no lifter redesign). Write anything bigger up as a proposed task instead.

SPU code on PS3 often waits by polling: GETLLAR or lost-reservation loops, channel reads, SPURS kernels polling for work. On the host each of these burns a whole core and starves real work (T022 saw dozens of spinning PhysX threads). Find the hot wait loops (T029, perf) and make them cheap without changing semantics: backoff, `_mm_pause`, a futex or condvar wait on reservation-lost or channel events, wakeups on writes to the reservation granule. T027 owns runtime/platform locks.

## Done when
Before/after numbers in docs/subsystems.md (SPU/SPURS section, your own subsection), tests green, patches apply in the stack.

## Log
- 2026-10-19 10:50 coordinator: From T027 (done, patch 0029). 50+ PhysX SPU task threads spin at SPU pc 0x32B44 (`GETLLAR 0x0133B880`), and every channel access goes through `mfc_for`'s shared lock. gdb dumps showed 91 and 172 threads. That congests the lock under either policy, and frames drop after the logos. Proposed fix, now part of T030: take `mfc_for`'s hot path off the lock, for example by caching the engine pointer in `spu_context`. Also: `HALT-ASSERT heqi pc=0x24884` in image 363824547 (PhysX), ~52 per 60 s. Baseline env to reach ESRB and past it: `GCM_INTR_THREAD=1 GCM_PARK_GRACE_MS=600000` (T024 is choosing the default).
