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
- 2026-10-19 11:25 coordinator: **This is now the main SPU perf task.** T030 found that PhysX's `CreateTask` spawns a host thread per SPURS task: 140-220 at once (561 by 300 s per T028), against 6 SPUs on real hardware. They all queue on the single global lock-line lock, and at ~297 s taskset 0x01335080 runs out of its 128 task ids (CreateTask 0x80410904, "PhysX: Error starting spurs task"). Proposed fix (T030 a): run SPURS tasks on ~6 host worker threads (a pool), not one thread per task. Also find out why the tasks never exit (T028: workers never see state 2 on line 0x0133B880 +0x1C; HALT-ASSERT 0x24884 may kill a worker mid-step). This may need libs/spurs as well: add it to Touches if no claimed task holds it. Measure with tools/spu_profile.sh.
