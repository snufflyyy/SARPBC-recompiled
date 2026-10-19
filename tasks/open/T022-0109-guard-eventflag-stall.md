# T022: 01.09 boot frontier — job guard 0x0133AA80 and event flag 0x01372000

Status: open
Owner: -
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
