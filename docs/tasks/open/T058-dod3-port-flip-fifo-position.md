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
