# T029: SPU perf: profiling harness (where SPU time goes, per image/function, spin share)

Status: claimed
Owner: pi
Priority: 3
Touches: tools/spu_profile.sh (new), docs/debugging.md (a new "Profiling" section only)
Reads: docs/tasks/*/T025*, docs/subsystems.md

## Goal
**Phase: SPU performance, easy wins only** (user, 2026-10-19). Start after the main menu is reached. Measure before and after every change: T029's harness once it exists, otherwise `perf record` on a 60 s 01.09 boot_check and the T025 mixer metric (`SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000`). Keep a change only if the numbers improve and the SPU tests pass; results must stay bit-exact. Nothing deep (no new JIT, no lifter redesign). Write anything bigger up as a proposed task instead.

Build the measuring stick for the other SPU perf tasks. `tools/spu_profile.sh <secs> [--version 0109]` runs boot_check under `perf record` (or samples), and reports top symbols grouped by SPU image hash, lifted function vs interpreter vs runtime helper vs lock or spin, plus host CPU per SPU thread and the T025 mixer metric. Its output should be one line suitable for task notes, plus a full report file in analysis/. Do this first, because T030-T033 use it.

## Done when
Before/after numbers in docs/subsystems.md (SPU/SPURS section, your own subsection), tests green, patches apply in the stack.

## Log
- 2026-10-19 10:59 agent-profile: claimed
- 2026-10-19 11:13 agent-profile: 01.09 60s GCM_INTR_THREAD=1: spu_profile 2026-10-19 | host 1331% CPU, 167 threads | 375k samples | SPU lifted 0.8% interp 0.0% rt 6.6% | lock/spin 90.1% (spu_lockline_lock 83%, rwlock unlock/rdlock 6.8%) | PPU 0.2% | GCM/VK 0.2% | top image 5af85a31=0.6%. HANDOFF: done=tools/spu_profile.sh+.py+docs Profiling, one real run; state=works (final rerun of the shell script after adding --no-inline not repeated, report regenerated from saved perf.data); next=rerun once end-to-end, T030 targets spu_lockline_lock; branch=worktree-agent-a7309d44b142f11e0
- 2026-10-19 11:13 agent-profile: RELEASED: paused; see HANDOFF
- 2026-10-19 23:12 pi: claimed
- 2026-10-19 23:12 pi: Blocker found while profiling T030: perf_event_paranoid=2 but container denies perf_event_open (EPERM). spu_profile.sh falls back after record failure yet immediately takes proc1 instead of waiting the requested window, so reported CPU covers startup milliseconds, not 57s. Will preserve sample deadline on failure and add mocked regression (no game data).
- 2026-10-19 23:14 pi: Regression proved: old harness samples only 0.042s on immediate perf denial and 2.037s on delayed denial (expected 5s for an 8s boot), two failing subcases. Added deadline wait from proc0 timestamp, preserving remaining time after partial perf failure, and a report reason pointing to perf_record.log. tools/test_spu_profile.py now passes both fake-boot cases (~16s total), no game data needed. Real end-to-end rerun queued under cpu/boot locks.
- 2026-10-19 23:17 pi: Real failed-perf run completed end-to-end, but exposed misleading result: host 98% CPU over 0s, 2 threads, though game boot reached 156 flips/13 packages/3279 zlib in 60s. Do not use that CPU result. Fixed-window rerun queued.
- 2026-10-19 23:28 pi: Corrected real runs now report full 57s CPU windows: 1247%/263 threads; 1284%/961; 1278%/997; 1288%/270. All end-to-end boots completed with the expected frontier and zero unresolved calls. perf unavailable (container EPERM), so category percentages cannot be remeasured here. Remaining original goal: parse/report mixer metric (currently only raw diagnostics via EXTRA flags), not part of this fallback fix.
- 2026-10-19 23:34 pi: HANDOFF: done=perf-denial fallback fix + mocked immediate/partial failure regressions + four real full-window profiles, committed b1d85a3 on pi/work; state=verified, being merged with T030; next=finish original mixer-metric requirement in tools/spu_profile.py/report (currently raw SPURS_EF_STATS/SPU_DMA_RANGE only), perf symbol-category rerun needs a host allowing perf_event_open; branch=pi/work.
- 2026-10-19 23:34 pi: RELEASED: Verified fallback fix; remaining mixer-report feature is documented in HANDOFF
- 2026-10-19 23:36 pi: claimed
- 2026-10-19 23:36 pi: User target is now at least 60 FPS in the main menu. Resuming profiler to establish steady-state menu FPS (distinguish guest flips/unique frames from presentation duplicates), finish mixer reporting, and identify next non-overlapping optimization. Claude still owns T033; no worker-pool edits.
- 2026-10-19 23:39 pi: Need scope extension: src/main.cpp adds a call on the existing frame-clock thread, new src/overrides/frame_stats.cpp logs cumulative guest-boundary frame count once/s, tools/spu_profile.py + tests add exact counter/window analysis and mixer stats, --warmup separates menu timing from intro. No claimed task owns these paths. Existing ppu_boot_frames_presented excludes pre-first-flip backend presents; backend dump counts do not, and the 500ms dump sampler can miss writes. Impact: diagnostic-only, env gated, no scheduling/guest/ABI changes; tests must reject stale/reset frame counters rather than manufacture FPS.
- 2026-10-19 23:41 pi: User hardware constraint: RTX 2070 SUPER is installed in a bottom PCIe slot and is slower than normal. All acceptance measurements target this configuration; do not compare to normal full-bandwidth 2070 SUPER expectations. Will query negotiated current/max link under load rather than assume lane count.
