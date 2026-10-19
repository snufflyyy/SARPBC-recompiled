# T009: Port the Drakengard 3 fork's lifter performance work as patches

Status: open
Owner: -
Touches: patches/ps3recomp/T009-*.patch (external/ps3recomp/tools/ppu_lifter.py, runtime/ppu/ppu_vm_fast.h & memory macros), docs/reference-ports.md (lifter section), docs/pipeline.md (lifter flags)
Reads: https://github.com/soyjxck/ps3recomp (MIT), its docs/PPU_RECOMP.md, dod3-recomp docs/TECHNICAL.md

## Goal
The fork (174 commits ahead) has `--nonvolatile-locals` (registers as C locals, written back
only where needed) and the 64 KiB page-table fast path for guest loads/stores
(`ppu_vm_fast.h`). Drakengard 3 measured large gains (main thread 4.6 -> 2.9 ms, binary
430 -> 293 MB). Port them onto our upstream pin as separate patches (keep the original
authorship), lift into your OWN copy of src/recomp, build, and measure: lifted line count,
binary size, build time, and boot to the same point with no new failures. Note
`--hook` too, but it is lower priority.

## Done when
Patches are exported, the measurements are in the task log and docs/reference-ports.md,
and a boot with the new lift reaches at least the same point as before.

## Log
