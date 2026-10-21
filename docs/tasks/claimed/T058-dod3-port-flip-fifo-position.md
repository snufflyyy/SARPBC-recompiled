# T058: Port next 5: prepared flips execute at their FIFO position (fork 6eb35c0, 6cba82c)

Status: claimed
Owner: pi
Priority: 13
Touches: patches/ps3recomp/NNNN-flip-at-fifo-position.patch (libs/video/cellGcmSys.c, rsx_commands.c), docs/dod3-reuse.md
Reads: docs/dod3-reuse.md Port next 5, fork commits 6eb35c0 and 6cba82c (MIT), docs/frame-pacing.md

## Goal
Prepared flips should execute when the drain reaches their marker in the FIFO, not when the user handler calls SetFlipImmediate. Fixes presenting a buffer still being drawn or flipping the wrong buffer. Careful: it changes frame pacing; verify menus, arena and round end (T052).

## Done when
Arena and menu boots unchanged or better (flips, fps), no mixed frames in captures, tests pass, patch exported.

## Log
- 2026-10-21 16:25 pi: Preflight: fetched MIT reference commits 6eb35c0/6cba82c. Port only prepared-flip marker/position behavior, not unrelated NV0039/Metal/diagnostics or a new backend presentation policy. Current batching presents pending flips before next drain; preserve it. Existing FIFO queued/reached counters apply to ordinary markers only: prepare executes a direct request at its GPU point and Immediate only acknowledges, avoiding double completion. Near-end fallback must not overwrite a pending event; cancellation on resync must not synthesize preparation. These are unimplemented design notes, not a claimed fix.
- 2026-10-21 16:29 pi: claimed
- 2026-10-21 16:43 pi: Synthetic FIFO/ack/position/resync tests are green and ASan/UBSan clean, but static review caught an important callback constraint before any game run: the existing park-release path depends on the legacy early callback from Immediate, and the GPU drain must never invoke guest code while holding its FIFO lock. Split request bookkeeping from callback delivery: prepared markers record/present at GPU position, Immediate acknowledgement retains only the existing optional legacy callback (not a second request), while strict ONTICK still uses completion. Extending tests to assert zero drain callbacks in both modes.
- 2026-10-21 16:50 pi: Implemented/exported 071e50c (runtime adapted commit reapplied in 88-commit stack), fork author preserved. Both callback modes pass FIFO/fence/ack/position/resync/context tests and ASan/UBSan; full100-script gate96pass4skip. Retained red counterexamples: missing GPU marker; callback from locked drain. Immediate successful ack preserves legacy early PPU callback without second request; logging still counts successful acks for boot metrics. Matched baseline130s then patched300s/menu verification running; no unsafe GPU-guest-callback version was booted.
- 2026-10-21 17:01 pi: First actual-game validation: 300s run 20261021-165217-1746815 returned MAINMENU@205.5s, 4810 zlib, 11008 acknowledged flips, unresolved 0, no NULL/SIGSEGV. Review of excess presentation captures found the existing native frame-clock post-drain fc!=last_flip fallback presents without consuming the pending flag; synchronous FIFO preparations make this reliably present a second time next iteration. Expanding Touches to src/main.cpp plus a focused native-loop regression test to consume that gate before the fallback present, preserving the existing clock/drain architecture. Not ready to merge yet.
