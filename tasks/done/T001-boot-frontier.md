# T001: Find and fix the stall after UE3 package loading (boot frontier)

Status: done
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
- 2026-10-18 23:18 agent-frontier: Cause 1 found: ps3recomp sys_memory is a bump allocator that never reuses freed ranges; UE3 frees/reallocs 64KB pages (323 frees in 60s) and walks off the 0x40000000-0x50000000 window -> ENOMEM -> OOM wide-string written to NULL by func_005F8E38, then 'IO Failure detected'. Fix (range table, first fit) in ps3recomp sys_memory.c: boot now opens DLC dir, flashMP3.pic, DEMOS, GUIDCACHE.XXX, MAINMENU.XXX. Also: edgezlib only prints first 4 requests (n<4); '4 requests' was a log limit.
- 2026-10-18 23:20 agent-frontier: Committed: sys_memory range-table patch (T001-sys-memory-reuse-freed-ranges.patch) + docs. New frontier: after MAINMENU.XXX PhysX prints 'Cannot load SPURS programs ... Cannot run without SPURS' and the game exits (sys_prx_exitspawn_with_level). That is T003 (cellOvis returns NOT_INITIALIZED, used as size 0x80420000). Next: checking what lies beyond by working around PhysX locally (not committed), and the hardcoded D:/recomp dev_flash path for flashMP3.pic.
- 2026-10-18 23:29 coordinator: FYI: coordinator edited src/main.cpp in main: setup_vfs() now calls cellGame_init_from_paramsfo(<game>/PARAM.SFO) (+ extern decl next to sarpbc_register_edgezlib). Needed for 01.09, which asks cellGame for its install dir. Expect a small merge in setup_vfs.
- 2026-10-18 23:34 agent-frontier: 01.02 frontier past PhysX (local experiment only): job chain with eaBinary=0 jobs (Edge Geometry from SPUJOBS.SPRX = T002) -> render thread waits on [obj+0x21180] in func_006DDFF0 -> game thread waits on frame fence q=7. Noted on T002. Now switching to 01.09 per coordinator.
- 2026-10-18 23:44 agent-frontier: Verified on 01.09 (build-0109, main 5098f45 + patches 0001,0002,T001): boot_check 60s -> 13 pkgs through GUIDCACHE@4.1s, zlib 3147 requests (was 295k looping), 0 zlib outputs below 0x01000000 (was NULL+0x10000..), 838 allocs / 324 frees, only ENOMEMs are the 4 bogus 0x80420000 PhysX overlay-table requests. 01.09 then stops at the same PhysX 'Cannot run without SPURS' exit as 01.02 (T003).
- 2026-10-18 23:47 agent-frontier: DONE: Stall after package loading was out-of-memory: ps3recomp sys_memory_allocate was a one-way bump pointer over 0x40000000-0x50000000 and sys_memory_free never returned ranges, while UE3 frees/re-requests 64 KB pages throughout loading (01.02: ENOMEM at 0x50000000 -> OOM text written to NULL by 0x005F8E38 -> 'IO Failure detected'; 01.09: Edge zlib inflating into NULL+offset, 295k requests). Fix: patches/ps3recomp/T001-sys-memory-reuse-freed-ranges.patch (sorted range table, first fit, reused ranges zeroed); runtime-level, verified on both versions (01.09: 3,147 zlib requests all valid, boot reaches GUIDCACHE/MultiStream/SaveData/PhysX threads). New frontier on both: PhysX quits on cellOvis overlay table (T003). With a local cellOvis 'no overlays' test, the next stall is the RHI job chain with eaBinary=0 jobs (SPUJOBS.SPRX, T002): render thread polls a counter the jobs advance, game thread waits on its frame fence. Docs: debugging.md hangs table + log-limit note, unreal-engine-3.md allocator, boot order and frame fence.
