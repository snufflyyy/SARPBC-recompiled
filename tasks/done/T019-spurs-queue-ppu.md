# T019: SPURS Queue — real PPU side (QueuePopBody/PushBody, attach/detach)

Status: done
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
- 2026-10-19 00:05 agent-spursq: Queue layout derived from the task-side libspurs push in the PhysX SPU images (push begin LS 0x6990, end 0x6E88 in image 7bde2a3f): pop idx +0x00, push idx +0x04 (both over [0,2*depth), ~idx while that side is in progress), size +0x08, depth +0x0C, buffer u64 +0x10, SPU port +0x18 (-1 none; task throws event there when it completes a push into an empty queue whose pop side is held), direction +0x1C (task push refuses 2=PPU2SPU with PERM), waiter lists +0x20 pop / +0x30 push (u8 count + task ids), workload ids +0x40/+0x50, taskset u64 +0x60. Upstream's init had size/buffer at the wrong offsets. Game: _cellSpursQueueInitialize(0, taskset, q, buf, 16, 128, SPU2PPU) at 0x008496B0; PopBody(q, buf, isPeek=0, isBlocking=1/0) at 0x008482EC/0x00848394, the latter expects AGAIN=0x80410901 (cellSpurs.h TASK_ERROR macros are 0x804107xx, wrong). Implemented libs/spurs/cellSpursQueue.c (dod3 structure: blocking = retried tries woken by SPU line commits) + tests/test_spurs_queue.c, passes 30/30.
- 2026-10-19 00:07 agent-spursq: HANDOFF: done=libs/spurs/cellSpursQueue.c (patch T019-spurs-queue-ppu.patch, applies on 0001-0008): real _cellSpursQueueInitialize/PopBody/PushBody/Clear/Attach/Detach + libsre LFQueue init (dod3 port), test_spurs_queue passes 30/30; 01.09 boot: 6 queues init+attach, 3 blocking pops of real PhysX task results, no queue error; state=boot then stalls on EventFlagWait flagEA=0x01372000 + job guard 0x0133AA80 closed 20s; next=coordinator renumbers patch; general _cellSpursLFQueuePushBody still missing; cellSpurs.h CELL_SPURS_TASK_ERROR_* are 0x804107xx (real 0x804109xx); PPU push vs real task pop unverified (no task pop code in this title); branch=worktree-agent-a2175056f565ad2ab
- 2026-10-19 00:07 agent-spursq: DONE: SPURS Queue PPU side in patch T019-spurs-queue-ppu.patch (libs/spurs/cellSpursQueue.c): line layout derived from the task-side libspurs push in the PhysX SPU images; PopBody/PushBody/Clear/Attach/Detach on lock-line-atomic pointer primitives with dod3-style blocking; libsre LFQueue init ported from dod3 (MIT). ctest spurs_queue round-trips PPU and task model on the big-endian line. 01.09 boot: queues init/attach and blocking pops return real PhysX results, no queue error; boot stalls later on an event flag/job guard.
