# T031: SPU perf: easy lifter codegen wins (spu_lifter.py output)

Status: open
Owner: -
Touches: tools/spu_lifter.py, tools/test_spu_*.py (new tests only), patches/ps3recomp/T031-*.patch
Reads: tasks/*/T025* (it owns runtime/spu/spu_helpers.h), tasks/*/T009*, docs/pipeline.md

## Goal
**Phase: SPU performance, easy wins only** (user, 2026-10-19). Start after the main menu is reached. Measure before and after every change: T029's harness once it exists, otherwise `perf record` on a 60 s 01.09 boot_check and the T025 mixer metric (`SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000`). Keep a change only if the numbers improve and the SPU tests pass; results must stay bit-exact. Nothing deep (no new JIT, no lifter redesign). Write anything bigger up as a proposed task instead.

Look at the C the SPU lifter emits for the hottest functions (from T029/perf) and find cheap wins. For example: direct calls instead of dispatch for known-static branch targets, avoiding redundant register-file loads and stores between instructions, constant-folding il/ilh/ila sequences, cheaper indirect-branch lookup (sorted table to hash or direct index by LS address), and no per-instruction bookkeeping in release builds. Lift into your scratch dir and build against it with -DSPU_DIR. **Never relift into the main checkout**: the coordinator relifts after merge.

## Done when
Before/after numbers in docs/subsystems.md (SPU/SPURS section, your own subsection), tests green, patches apply in the stack.

## Log
