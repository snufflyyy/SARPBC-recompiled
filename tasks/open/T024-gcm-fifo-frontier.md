# T024: 01.09 menus: GCM FIFO jump-to-self at io 0x8B144 + fork GCM flip/FIFO fixes

Status: open
Owner: -
Touches: patches/ps3recomp/T024-*.patch (libs/gcm/**, runtime/rsx/**, libs/video/** only), src/overrides/gcm_*.cpp (new), docs/subsystems.md (Graphics section only)
Reads: docs/dod3-reuse.md (T023's ranked GCM list), docs/debugging.md, tasks/done/T023*

## Goal
**User priority (2026-10-19): get 01.09 into the menus.** T023 found that during loading the GCM
FIFO walker does 3 "stuck-get" resyncs (~120 KB of commands dropped). With fork commit 0014 plus
`GCM_FIFO_NO_RESYNC=1`, the FIFO parks on a jump-to-self at io `0x0008B144` (word `0x2008B144`)
right after vertex-array setup, and nothing overwrites it. Find out who is supposed to write it
(an SPU job such as Edge Geometry? a PPU thread waiting on a label / flip?) and make the boot
progress. Port the fork's GCM fixes in T023's ranked order when they help: 0049 (prepared flips
in FIFO order), 0018 (user-command queue), 0014/0024 (jump-to-self waits), then 0112, 0059/0062,
0096/0111, 0139. agent-frontier2 (T022) owns libs/spurs and the job guard 0x0133AA80; coordinate
through task notes if the two turn out to be the same stall.

## Done when
The boot gets measurably further toward the menus (boot_check summary before/after, frames
drawn), causes written in docs/subsystems.md Graphics.

## Log
