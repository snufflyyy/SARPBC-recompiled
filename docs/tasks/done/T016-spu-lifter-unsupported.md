# T016: SPU lifter — unsupported instructions in two 01.09 images

Status: done
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
- 2026-10-18 23:48 agent-spulift: Fix: find_spu_functions.py keeps a derived seed only if it decodes, is not a NUL-padded C string, and a straight-line walk reaches br/bra/bi/bie/bid/iret/stop before a .word or segment end (patch T016-spu-detector-rodata-seeds.patch + tools/test_spu_find_functions_rodata.py). 01.09 relift into worktree: 14/15 registered (only PhysX 5af85a31 left, T003). d08b1ad8: 661->625 funcs, 213->0 unsupported, 36 seeds dropped. e33837bb: 1201->1151 funcs, 473->0 unsupported, 50 seeds dropped. Other 12 images: spu_recomp.c byte-identical to versions/0109/src/spu_gen. Over 20 distinct images (01.02+01.09) no seed inside a real exec section dropped (a first string-check version wrongly dropped fcgt+nop 'XAn$@ \0\x7F' in PhysX images 034ddc73/0e1192e6; fixed by requiring NUL padding). Image 0 e33837bb = MultiStream main mixer (strings 'Skipping DSP', 'MP3 STARVED OF DATA', 'ERROR! Multistream'). Boot 01.09 w/ my SPU (boot_check 30): 'dispatch HIT (async) fp=0x00E729804474449A ... spawning thread', task runs to SPURS syscall 2 and sleeps in WAIT_SIGNAL (native PPU path services zlib). Summary: PROGRESSING | last open MAINMENU.XXX@1.1s | pkgs 12 | zlib 231964. Pre-existing, unrelated: runtime/spu/tests/run_tests.sh fails 10/11 on Linux both before and after (clock_gettime under -std=c11, stale out_* files).
- 2026-10-18 23:48 agent-spulift: DONE: No opcodes were missing: all 213 (Edge zlib d08b1ad8) and 473 (image 0 e33837bb = MultiStream mixer) unsupported entries were .word, i.e. .rodata lifted as code. Both images are section-stripped, so the whole R+X PT_LOAD is code to the pipeline, and find_spu_functions.py seeded every string/table address loaded by ila as a function start. Fix in find_spu_functions.py (outside the listed Touches, noted; no other task touches it): derived seeds must decode, not be a NUL-padded C string, and reach a branch/return/stop before a .word or segment end. Patch patches/ps3recomp/T016-spu-detector-rodata-seeds.patch with test tools/test_spu_find_functions_rodata.py (fails on old code, passes now). 01.09 relift in worktree: 14/15 registered, both images 0 unsupported (625/1151 funcs), other 12 byte-identical; no real .text seed dropped across 20 images. 01.09 boot with this lift: dispatch HIT fp=0x00E729804474449A, task reaches its SPURS WAIT_SIGNAL. Docs: game-profile.md 01.09 SPU rows. Branch worktree-agent-acd691fc36f2a10b3, commit fd66f9e.
