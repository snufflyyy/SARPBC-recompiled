# T029: SPU perf: profiling harness (where SPU time goes, per image/function, spin share)

Status: open
Owner: -
Model: sonnet
Touches: tools/spu_profile.sh (new), docs/debugging.md (a new "Profiling" section only)
Reads: tasks/*/T025*, docs/subsystems.md

## Goal
**Phase: SPU performance, easy wins only** (user, 2026-10-19). Start after the main menu is reached. Measure before and after every change: T029's harness once it exists, otherwise `perf record` on a 60 s 01.09 boot_check and the T025 mixer metric (`SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000`). Keep a change only if the numbers improve and the SPU tests pass; results must stay bit-exact. Nothing deep (no new JIT, no lifter redesign). Write anything bigger up as a proposed task instead.

Build the measuring stick for the other SPU perf tasks. `tools/spu_profile.sh <secs> [--version 0109]` runs boot_check under `perf record` (or samples), and reports top symbols grouped by SPU image hash, lifted function vs interpreter vs runtime helper vs lock or spin, plus host CPU per SPU thread and the T025 mixer metric. Its output should be one line suitable for task notes, plus a full report file in analysis/. Do this first, because T030-T033 use it.

## Done when
Before/after numbers in docs/subsystems.md (SPU/SPURS section, your own subsection), tests green, patches apply in the stack.

## Log
