# T003: PhysX on SPU — cellOvis overlay table and SPU image #7

Status: claimed
Owner: agent-physx
Touches: patches/ps3recomp/T003-*.patch (external/ps3recomp/libs/** for cellOvis, tools/build_spu_workloads.py / spu_program_pipeline.py), docs/subsystems.md (PhysX bullets only, coordinate with T002 via notes)
Reads: analysis/spu_EBOOT_elf/, src/spu_gen/inventory.json, external/ps3recomp/runtime/spu/

## Goal
1. After `cellSysmoduleLoadModule(CELL_SYSMODULE_OVIS)` the game prints
   "PhysX: Error allocating memory for overlay table: 0 0". The game imports
   `cellOvisGetOverlayTableSize` and `cellOvisInitializeOverlayTable`. Implement them
   correctly (documented behaviour: overlay table for SPU overlays in PRX/ELF images) as
   a ps3recomp patch.
2. SPU image #7 (`spu_5af85a31...`, 323,840 bytes, PhysX, uses CellStackAllocator) is
   refused by build_spu_workloads: "overlapping PT_LOAD memory ranges (including BSS) are
   unsupported". These are probably SPU overlays (that's what cellOvis is for). Find out how
   the overlay segments are used and get the image lifted and registered (lifter/pipeline
   patch, or a port-side tool).

## Done when
No PhysX overlay-table error at boot; image #7 lifted and registered (or a documented
reason it can't be yet, plus the plan). Patches exported as T003-*.patch with tests if
upstream has a test pattern for the area.

## Log
- 2026-10-18 23:12 agent-physx: claimed
