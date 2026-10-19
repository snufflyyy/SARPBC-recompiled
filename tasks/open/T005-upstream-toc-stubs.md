# T005: Fix TOC-switch stub boundaries in ps3recomp's loader/lifter (upstreamable patch)

Status: open
Owner: -
Touches: patches/ps3recomp/T005-*.patch (external/ps3recomp/tools/ppu_loader.py, ppu_lifter.py, tools/test_*.py), tools/split_toc_stubs.py, tools/relift.sh (only the split step)
Reads: docs/pipeline.md (step 4), game/EBOOT.elf, analysis/

## Goal
tools/split_toc_stubs.py works around a general toolkit bug: linker TOC-switch stubs
(`std r2,40(r1); addis/addi r2,r2,imm; b target`, runs of them in multi-TOC EBOOTs) are
folded into the preceding function by ppu_loader.py, and the lifter then emits each stub as
a mid-function tail-entry wrapper that runs to the end of the run (27.2M vs 7.6M lines
here). Fix it in ps3recomp (loader or the lifter's boundary recovery), with a unit test in
the style of tools/test_ppu_*.py, as a patch T005-*.patch. Verify that a lift with
the patch and WITHOUT split_toc_stubs.py produces the same function count (64,397) and line
count as the current lift. Lift into your own worktree copy of src/recomp, never the shared
one. Then make relift.sh skip the workaround when the patch is present, or remove it.

## Done when
The patch and test are committed, the verification numbers are in the task log, and
docs/pipeline.md is updated.

## Log
