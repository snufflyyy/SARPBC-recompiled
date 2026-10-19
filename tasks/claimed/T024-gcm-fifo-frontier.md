# T024: 01.09 menus: GCM FIFO jump-to-self at io 0x8B144 + fork GCM flip/FIFO fixes

Status: claimed
Owner: agent-gcm
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
- 2026-10-19 09:29 agent-gcm: claimed
- 2026-10-19 09:30 agent-gcm: baseline: boot_check 2026-10-19 09:30 v01.09 1e5406b 60s: STALLED since 21.6s | last open GUIDCACHE.XXX@4.1s | pkgs 13 (GUIDCACHE last) | zlib 3147 | dumps 5 lit 5 distinct 2 | flips 7 | threads 13/8 alive | unresolved 0 | alerts open-fail,assert (SPU_INTERP_UNLIFTED=1 BUILD_DIR=build-0109)
- 2026-10-19 09:32 agent-gcm: T022 (agent-frontier2 note 09:27) already found who releases the park: FIFO user command 0xEB00 -> user handler 0xDC390 -> cellGcmSetFlipImmediate -> flip handler func_000DC144 patches the park. Not a SPURS job. The pump only runs at HLE imports, the RenderingThread sleeps in sys_timer_usleep (a syscall), so delivery is late and stuck-get resyncs past the park after 8 drains. Plan: port fork 0018+0139, keep self-JUMP parks (no resync), deliver user commands on a GCM interrupt thread.
