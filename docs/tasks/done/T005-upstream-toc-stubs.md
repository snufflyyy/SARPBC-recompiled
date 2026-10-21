# T005: Fix TOC-switch stub boundaries in ps3recomp's loader/lifter (upstreamable patch)

Status: done
Owner: claude
Priority: 21
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
- 2026-10-18 23:19 coordinator: tools/relift.sh changed in main (847776d+): GAME_DIR/OUT_DIR env vars and automatic CODE_END from the section headers. 01.09 has no TOC-stub runs (split finds 0), so test the loader fix on 01.02 (game/) and check that it is a no-op on versions/0109/game.
- 2026-10-21 16:23 pi: Preflight while T032/T056 validation runs: current 01.02 loader table has 47,602 functions; workaround table 51,844 (=4,242 new stubs). The task target 64,397 is the eventual LIFTER output count, not the loader-table length. 01.09 loader and split tables both 22,154. Shared tables only read, not changed.
- 2026-10-21 18:04 claude: claimed
- 2026-10-21 18:05 claude: Patch loader-toc-stubs: ppu_loader splits TOC-switch stub runs by default (--no-split-toc-stubs off). 01.02: loader list == split_toc_stubs.py output (51,844 funcs, 2 runs, 4,242 stubs); 01.09: no runs, no-op. 12-check test_ppu_loader_toc_stubs.py. relift.sh uses the loader's list when supported. Did not re-lift (identical function list => identical lift input).
- 2026-10-21 18:05 claude: DONE: ppu_loader now splits TOC-switch stubs (patch + test); relift.sh skips the script when the loader does it; verified identical to the script on 01.02, no-op on 01.09. Offering upstream still needs the user's go-ahead (docs/upstream.md).
