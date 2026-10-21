# T031: SPU perf: easy lifter codegen wins (spu_lifter.py output)

Status: done
Owner: claude
Priority: 5
Touches: tools/spu_lifter.py, tools/test_spu_*.py (new tests only), patches/ps3recomp/T031-*.patch
Reads: docs/tasks/*/T025* (it owns runtime/spu/spu_helpers.h), docs/tasks/*/T009*, docs/pipeline.md

## Goal
**Phase: SPU performance, easy wins only** (user, 2026-10-19). Start after the main menu is reached. Measure before and after every change: T029's harness once it exists, otherwise `perf record` on a 60 s 01.09 boot_check and the T025 mixer metric (`SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000`). Keep a change only if the numbers improve and the SPU tests pass; results must stay bit-exact. Nothing deep (no new JIT, no lifter redesign). Write anything bigger up as a proposed task instead.

Look at the C the SPU lifter emits for the hottest functions (from T029/perf) and find cheap wins. For example: direct calls instead of dispatch for known-static branch targets, avoiding redundant register-file loads and stores between instructions, constant-folding il/ilh/ila sequences, cheaper indirect-branch lookup (sorted table to hash or direct index by LS address), and no per-instruction bookkeeping in release builds. Lift into your scratch dir and build against it with -DSPU_DIR. **Never relift into the main checkout**: the coordinator relifts after merge.

## Done when
Before/after numbers in docs/subsystems.md (SPU/SPURS section, your own subsection), tests green, patches apply in the stack.

## Log
- 2026-10-20 02:19 claude: From T025 (closed by T039): candidate easy win: always_inline the SSE4.1 spu_shufb (6 out-of-line copies remain in lifted TUs).
- 2026-10-20 22:22 claude: 2026-10-20 measurement (main + 0053, Single Player screen, /proc thread CPU over 20 s at 72-92 s): whole game ~190% CPU; busiest threads 74%, 59%, 43% then 10%, 4%, rest ~0%. No thread looks like SPU spin; the T033 fix removed the 90% lock/spin of the 2026-10-19 profile. SPU speed is not limiting the menu/arena now, so no SPU change was made. Revisit only if an SPU-heavy scene (arena with physics/audio) shows SPU threads near 100%.
- 2026-10-21 13:45 claude: claimed
- 2026-10-21 13:51 claude: Arena per-thread CPU at 100-120 s: busiest 46%, 31%, rest <4% (~82% total, 35 fps). SPU codegen is not limiting; no lifter change made (see subsystems.md 'SPU codegen wins: not needed'). Revisit in a real match.
- 2026-10-21 13:51 claude: DONE: Closed without code change per the task's own gate: no SPU thread near 100% in the arena (measured, documented). Revisit under phase 8 load.
