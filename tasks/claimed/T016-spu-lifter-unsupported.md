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
