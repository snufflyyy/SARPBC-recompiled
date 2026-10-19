# T033: SPU perf: host thread count, oversubscription, scheduling

Status: open
Owner: -
Touches: patches/ps3recomp/T033-*.patch (runtime/spu/spu_lifted_thread.*, runtime/spu/spu_workload.*, runtime/spu/spurs_policy.c, runtime/spu/spu_dispatch_mt.c)
Reads: docs/subsystems.md, libs/spurs (read only)

## Goal
**Phase: SPU performance, easy wins only** (user, 2026-10-19). Start after the main menu is reached. Measure before and after every change: T029's harness once it exists, otherwise `perf record` on a 60 s 01.09 boot_check and the T025 mixer metric (`SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000`). Keep a change only if the numbers improve and the SPU tests pass; results must stay bit-exact. Nothing deep (no new JIT, no lifter redesign). Write anything bigger up as a proposed task instead.

How many host threads run SPU code, compared with host cores? (The PS3 has 6 SPUs; SPURS kernels and raw SPU threads may each get a host thread.) Find easy wins: cap or affinity-pin SPU host threads, park idle SPURS kernels instead of polling, avoid oversubscription with the PPU threads, and check scheduler latency. Measure frame/flip rate and mixer throughput.

## Done when
Before/after numbers in docs/subsystems.md (SPU/SPURS section, your own subsection), tests green, patches apply in the stack.

## Log
