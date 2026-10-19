# T019: SPURS Queue — real PPU side (QueuePopBody/PushBody, attach/detach)

Status: claimed
Owner: agent-spursq
Touches: patches/ps3recomp/T019-*.patch (external/ps3recomp/libs/spurs/** queue code + tests), src/overrides/edgezlib.cpp (only if the LFQueue push becomes general; coordinate), docs/subsystems.md (SPU/SPURS queue bullets)
Reads: docs/hle-coverage.md, docs/reference-ports.md (dod3 lifted libsre's queue paths), external/ps3recomp/libs/spurs/cellSpurs.c

## Goal
The game imports `_cellSpursQueueInitialize`, `cellSpursQueuePopBody`, `cellSpursQueuePushBody`
(check), `cellSpursQueueAttach/DetachLv2EventQueue`, and the LFQueue equivalents. PhysX's SPU
tasks (images 2, 6, 11: "PhysX: Error writing to SPURS queue") talk to the PPU through a
SPURS queue. Upstream's `cellSpursQueuePopBody` is missing (a faked CELL_OK reads as "popped"
with nothing written), and its other queue paths are thin. The consumer or producer on the
other side is lifted SPU code that uses lock-line atomics on the queue in guest memory, so the
PPU side must keep the real big-endian CellSpursQueue/CellSyncQueue layout, as
_cellSpursLFQueueInitialize already does for its line. Implement the PPU queue operations
compatibly (blocking and non-blocking, with event-queue wakeups), written from the documented
behaviour and the SPU code's own reads and writes. No GPL code. Add tests.

## Done when
A test proves PPU↔SPU queue round-trips against the queue layout. In a boot, the PhysX tasks
either run (no "Error writing to SPURS queue") or the precise remaining gap is logged. Patch exported.

## Log
- 2026-10-18 23:48 agent-spursq: claimed
