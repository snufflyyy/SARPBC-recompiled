# T016: SPU lifter — unsupported instructions in two 01.09 images

Status: claimed
Owner: agent-spulift
Touches: patches/ps3recomp/T016-*.patch (external/ps3recomp/tools/spu_lifter.py, spu_disasm.py, runtime/spu/spu_helpers.h + their tests), docs/game-profile.md (01.09 SPU rows only)
Reads: versions/0109/src/spu_gen/inventory.json and its per-image lift.log, versions/0109/game/EBOOT.elf

## Goal
In 01.09, two embedded SPU images do not register: "unsupported instructions emitted by
lifter". They are `e33837bb55e5...` (95,636 B, the new image 0) and `d08b1ad818d0...` (38,100 B,
the new Edge zlib; a native PPU path covers it, but the lift should still work). Find
the exact opcodes (lift.log / grep the emitted C for the unsupported marker), implement them
in the SPU lifter/runtime per the SPU ISA, with a test in the upstream style
(runtime/spu/tests or tools/test_spu_*.py), and re-run build_spu_workloads on a COPY of the
01.09 SPU output (never the shared versions/0109/src/spu_gen).

## Done when
Both images register in your copy's inventory with no unsupported instructions; patch +
test exported as T016-*.patch; numbers in the task log.

## Log
- 2026-10-18 23:33 agent-spulift: claimed
- 2026-10-18 23:37 agent-spulift: Root cause found: NOT missing opcodes. All 213 (d08b1ad8) + 473 (e33837bb) 'unsupported' are '.word' = rodata (assert/printf strings, float/zlib/shuffle tables) lifted as code. Both images are section-stripped (no SHF_EXECINSTR sections), so code_ranges() falls back to the whole R-E PT_LOAD (0x3000-0xc350 / 0x3000-0x1a3f0) which holds .text+.rodata. find_spu_functions.collect_ila_continuation_targets seeds every ila/ilhu+iohl immediate inside the segment (string pointers passed to printf, table bases) as a function start; its 'cand in valid_starts' guard is a no-op since disassemble_spu emits an entry (.word) for every word. Images WITH sections (all other 01.09 images) have the same bogus seeds but get clipped to .text. Fix belongs in external/ps3recomp/tools/find_spu_functions.py, which is OUTSIDE my Touches; no other open/claimed task touches it (T003 has build_spu_workloads.py/spu_program_pipeline.py), so I am making the fix there in the T016 patch. Coordinator: please add find_spu_functions.py (+ its test) to T016 Touches or reject.
