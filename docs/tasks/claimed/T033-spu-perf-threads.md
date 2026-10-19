# T033: SPU perf: host thread count, oversubscription, scheduling

Status: claimed
Owner: claude
Priority: 1
Touches: patches/ps3recomp/T033-*.patch (runtime/spu/spu_lifted_thread.*, runtime/spu/spu_workload.*, runtime/spu/spurs_policy.c, runtime/spu/spu_dispatch_mt.c, libs/spurs/spurs_taskset.* and the task-creation path in libs/spurs/cellSpurs.c)
Reads: docs/subsystems.md, libs/spurs (read only)

## Goal
**Phase: SPU performance, easy wins only** (user, 2026-10-19). Start after the main menu is reached. Measure before and after every change: T029's harness once it exists, otherwise `perf record` on a 60 s 01.09 boot_check and the T025 mixer metric (`SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000`). Keep a change only if the numbers improve and the SPU tests pass; results must stay bit-exact. Nothing deep (no new JIT, no lifter redesign). Write anything bigger up as a proposed task instead.

How many host threads run SPU code, compared with host cores? (The PS3 has 6 SPUs; SPURS kernels and raw SPU threads may each get a host thread.) Find easy wins: cap or affinity-pin SPU host threads, park idle SPURS kernels instead of polling, avoid oversubscription with the PPU threads, and check scheduler latency. Measure frame/flip rate and mixer throughput.

## Done when
Before/after numbers in docs/subsystems.md (SPU/SPURS section, your own subsection), tests green, patches apply in the stack.

## Log
- 2026-10-19 11:25 coordinator: **This is now the main SPU perf task.** T030 found that PhysX's `CreateTask` spawns a host thread per SPURS task: 140-220 at once (561 by 300 s per T028), against 6 SPUs on real hardware. They all queue on the single global lock-line lock, and at ~297 s taskset 0x01335080 runs out of its 128 task ids (CreateTask 0x80410904, "PhysX: Error starting spurs task"). Proposed fix (T030 a): run SPURS tasks on ~6 host worker threads (a pool), not one thread per task. Also find out why the tasks never exit (T028: workers never see state 2 on line 0x0133B880 +0x1C; HALT-ASSERT 0x24884 may kill a worker mid-step). This may need libs/spurs as well: add it to Touches if no claimed task holds it. Measure with tools/spu_profile.sh.
- 2026-10-19 22:54 claude: claimed
- 2026-10-19 23:04 pi: Coordination from T030: my changes limited to spu_coherency.c + registry tests/bench (private pointer hash speeds reserve membership; no ABI/channel/task edits). Building baseline 01.09 under cpu lock, -j8 to fit 15GiB host; next run profile before/after under boot lock. agent_setup failed on missing base src/recomp, so manually configured against main versions/0109 generated sources.
- 2026-10-19 23:10 claude: New machine (2026-10-19 evening): Debian 13 container on a Fedora host, 16 threads, 15 GB RAM, ~16 GB free disk, RTX 2070 SUPER (NVIDIA Vulkan; was RX 7800 XT). Fresh clone: claude extracted base PKG -> vfs/, downloaded 01.09 from Sony (SHA-1 9cc78619...a7cb3c235 ok) -> versions/0109/vfs (base + update), decrypted (EBOOT 85d698f5, SPUJOBS 189316bc, as documented), relifted 01.09 (41431 fns, 387 MB) and 01.02. Debian needed: gawk (relift.sh uses strtonum; mawk lacks it), libopengl0 (RPCS3 decrypt), libsdl2-dev glslang-dev ccache gdb. Other agents: one build at a time (cpu lock) and expect OOM above ~-j8 with 15 GB; disk is tight, keep one build tree per agent (01.09 only) and consider -DSARPBC_CCACHE=OFF (ccache cap is 40G).
- 2026-10-19 23:11 pi: Baseline build almost linked. For cleaner A/B, I will hold cpu during the two 60s profiles (each also takes boot), after a tiny coherency-only rebuild. Thus no concurrent build noise; total extra cpu hold ~2min. Only one 01.09 build tree + saved baseline binary.
- 2026-10-19 23:25 pi: T030 first controlled A/B: hash index speeds reserve lookups ~24x at 256 contexts; game flips 374 -> 589/60s, but threads 263 -> 961 at 57s, CPU ~1250% unchanged. Faster work accelerates pre-existing accumulation, so your pool is still critical. Running one reverse-order pair; no task/pool files touched.
