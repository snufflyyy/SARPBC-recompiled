# T037: 01.09: hang after New Game, right after MP_SOCCARARENA.XXX opens (~164 s)

Status: open
Owner: -
Touches: src/overrides/frontier_*.cpp (new), docs/debugging.md, docs/unreal-engine-3.md
Reads: tasks/*/T028*

## Goal
From T028: after New Game the arena package MP_SOCCARARENA.XXX opens at ~164 s, then the log goes silent (HUNG). Find out why: map load, PhysX scene creation (the task pile-up from T030 may run out of the 128 task ids at ~297 s), or something else. Wait for T030 first if the pile-up is still there.

## Done when
Cause identified with evidence; a boot gets further into the arena, or the fix is handed to the owning task.

## Log
