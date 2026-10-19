# T010: Audit the SPU lifts' "incomplete coverage" and the unidentified images

Status: open
Owner: -
Touches: docs/game-profile.md (SPU table only), tools/spu_coverage.py (new)
Reads: src/spu_gen/inventory.json, src/spu_gen/*/lift.json, analysis/spu_EBOOT_elf/

## Goal
All 14 images lift with no unsupported instructions, but strict mode refused them for
"incomplete coverage", and we registered them with --allow-partial. Prove the uncovered
bytes are padding or literal pools and not missed code (a missed function = SPU
interpreter fallback, or a crash). Write a script listing each image's uncovered ranges
with a disassembly verdict. Also identify images 0, 3-5 and 8-10 (strings, call
patterns, which SPURS API dispatches them at runtime: taskset/job chain/raw SPU).

## Done when
The game-profile.md SPU table names every image, and coverage gaps are classified with
evidence, plus a list of anything that needs a lifter fix.

## Log
