# T001: Find and fix the stall after UE3 package loading (boot frontier)

Status: claimed
Owner: agent-frontier
Touches: src/overrides/ (new files only; edgezlib.cpp is shared with T002/T004 — note before editing), src/main.cpp, docs/unreal-engine-3.md, docs/debugging.md
Reads: everything

## Goal
Boot currently reaches the "Loading..." screen and the package loader opens CORE, PSYUI,
MAINMENU, STARTUP_INT, TASTATS, TAGAME, ONLINESUBSYSTEMGAMESPY(_LOC_INT), IPDRV, ENGINE
(4 Edge zlib requests serviced, 0 failures) and then makes no visible progress. Find the
first thing that goes wrong after that point and fix it at the right layer (override in
src/overrides/, or a ps3recomp patch T001-*.patch), then repeat until the boot reaches
the next milestone (intro movies / main menu) or you hit something that belongs to
another task (log it and stop there).

Start: `timeout -k 5 -s TERM 90 tools/run.sh` with PS3_FSLOG=1 and the log filter in
docs/debugging.md; gdb thread stacks; PS3_HLE_TRACE. Check whether only 4 zlib requests
is plausible (each package is compressed chunks; maybe the loader waits on something
else, e.g. a different completion or the SPUJOBS/Edge Geometry job chain).

## Done when
The boot gets measurably further (new files opened / new frames drawn / main menu), each
fix is committed with its evidence, and docs/debugging.md "Hangs found so far" has a row
per cause. Report the new frontier.

## Log
- 2026-10-18 23:12 agent-frontier: claimed
