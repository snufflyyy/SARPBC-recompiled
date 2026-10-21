# T009: Port the Drakengard 3 fork's lifter performance work as patches

Status: open
Owner: -
Priority: 19
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
- 2026-10-21 01:47 claude: 2026-10-21 reviewed fork commits (e635033, 8dde556, afa9c69, d2c054a = ~900 lifter lines + 1730-line ppu_nv_dirty.py; ee004d6/1cbca03 = page-table loads). Our runtime already does plain vm_base+addr loads (no per-access page test), so the page-table piece is a store-gate for SPU/RSX coherency, not a speedup here. The fork's own commit message says its hot code was 'float/vector and memory, not r14-r31' (game thread 9.4-10.0 ms unchanged). Not ported: large, risky lifter change with unproven gain on this game. Revisit only if a guest-side profile shows spills of r14-r31 dominating.
