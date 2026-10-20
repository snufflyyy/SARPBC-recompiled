# T010: Audit the SPU lifts' "incomplete coverage" and the unidentified images

Status: done
Owner: sonnet-1
Priority: 22
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
- 2026-10-20 18:00 sonnet-1: claimed
- 2026-10-20 18:00 sonnet-1: Started by claude as a Sonnet 5.5 subagent (user request 2026-10-20), isolated worktree; scope: analysis + tools/spu_coverage.py + game-profile.md SPU table, no builds/boots.
- 2026-10-20 18:10 sonnet-1: All 15 images identified (see game-profile SPU table). Coverage on 01.09: 512 uncovered ranges/62,088 B = 370 padding, 13 zero, 7 string, 55 data (tables, jump tables, signature quads), 7 post-stop epilogues, 58 dead (unreferenced) functions, 2 code? = function pointers in .rodata: 906761dc LS 0x12E30 (ptr@0x21C78) and 034ddc73 LS 0x16130 (ptr@0x22CD4); need --extra-funcs seeds. No directly reachable missed code.
- 2026-10-20 18:10 sonnet-1: DONE-READY: branch worktree-agent-a4168eced2ee4ee76 commit ac64c77: tools/spu_coverage.py, game-profile SPU table (all 15 named) + coverage section, pipeline pointer
- 2026-10-20 18:24 sonnet-1: DONE: Merged (claude): tools/spu_coverage.py; all 15 images + 2 jobs identified; 512 uncovered ranges on 01.09 classified, none is code the lifted functions reach directly. Two candidates for a lifter seed, never seen called: 906761dc LS 0x12E30 (ptr at 0x21C78), 034ddc73 LS 0x16130 (ptr at 0x22CD4); seed with --extra-funcs if 'branched into unlifted LS' ever names them.
