# T022: 01.09 boot frontier — job guard 0x0133AA80 and event flag 0x01372000

Status: claimed
Owner: agent-frontier2
Touches: src/overrides/ (new files), patches/ps3recomp/T022-*.patch (libs/spurs/** job guard/job chain only), docs/debugging.md, docs/unreal-engine-3.md
Reads: docs/dod3-reuse.md, docs/subsystems.md, tasks/done/T019*, T007's HANDOFF note

## Goal
With patches 0001-0015, 01.09 passes PhysX (SPURS queues work) and then hangs: an event-flag wait on
`0x01372000` (MultiStream; see T007) stays blocked, and the SPURS job guard `0x0133AA80` stays closed
for 20 s ("chain gives up"). First check the fork's `SPURS_GUARD_FIRST_MS` change (a never-notified
job guard waits 200 ms, not 20 s; see docs/dod3-reuse.md) and the ShaderPatching/Edge Geometry job
chain from SPUJOBS (T002: dispatch HIT?). Push the boot to intro movies / main menu.

## Done when
The boot gets measurably further (boot_check summary before and after), with causes in debugging.md.

## Log
- 2026-10-19 08:58 agent-frontier2: claimed
- 2026-10-19 09:01 agent-frontier2: baseline (patches 0001-0015, build-0109): boot_check 2026-10-19 09:00 v01.09 c4fc252 60s: HUNG (log silent for the last 10s) | last open GUIDCACHE.XXX@3.6s | pkgs 13 (GUIDCACHE last) | zlib 3147 | dumps 4 lit 4 distinct 1 | flips 12 | threads 13/9 alive | unresolved 0 | alerts open-fail,blocked. Guard chain jc=0x0133AC00 = GUARD 0x0133AA80, JOBLIST 0x0133AA00, SYNC, JOB 0x0133AD80, NEXT (service loop); never notified in 60 s; our walker is async (own thread) so the 20 s guard wait does NOT block the boot (fork's SPURS_GUARD_FIRST_MS mattered because fork walks sync). ShaderPatching chain jobs dispatch HIT (fp 83BD7B3A22EDAF27) and return rc=0.
