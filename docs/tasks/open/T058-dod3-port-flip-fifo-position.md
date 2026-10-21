# T058: Port next 5: prepared flips execute at their FIFO position (fork 6eb35c0, 6cba82c)

Status: open
Owner: -
Priority: 13
Touches: patches/ps3recomp/NNNN-flip-at-fifo-position.patch (libs/video/cellGcmSys.c, rsx_commands.c), docs/dod3-reuse.md
Reads: docs/dod3-reuse.md Port next 5, fork commits 6eb35c0 and 6cba82c (MIT), docs/frame-pacing.md

## Goal
Prepared flips should execute when the drain reaches their marker in the FIFO, not when the user handler calls SetFlipImmediate. Fixes presenting a buffer still being drawn or flipping the wrong buffer. Careful: it changes frame pacing; verify menus, arena and round end (T052).

## Done when
Arena and menu boots unchanged or better (flips, fps), no mixed frames in captures, tests pass, patch exported.

## Log
- 2026-10-21 16:25 pi: Preflight: fetched MIT reference commits 6eb35c0/6cba82c. Port only prepared-flip marker/position behavior, not unrelated NV0039/Metal/diagnostics or a new backend presentation policy. Current batching presents pending flips before next drain; preserve it. Existing FIFO queued/reached counters apply to ordinary markers only: prepare executes a direct request at its GPU point and Immediate only acknowledges, avoiding double completion. Near-end fallback must not overwrite a pending event; cancellation on resync must not synthesize preparation. These are unimplemented design notes, not a claimed fix.
