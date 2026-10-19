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
- 2026-10-18 23:18 agent-frontier: FYI from T001: with the sys_memory free fix (T001 patch) boot reaches MAINMENU.XXX, then 'PhysX: Cannot load SPURS programs. Error allocating memory for overlay table: 0 1. Cannot run without SPURS.' and the game calls sys_prx_exitspawn_with_level (quits) -> PhysX is now the boot frontier. Evidence for the size: game calls sys_memory_allocate(size=0x80420000) twice right before the error = VM_ALIGN_UP(0x80410701, 64K): ps3recomp cellOvisGetOverlayTableSize returns CELL_OVIS_ERROR_NOT_INITIALIZED (needs an init the game never calls; also its signature takes an out-pointer, while the SDK returns the size as the s32 result) and the game uses the return value as the table size.
- 2026-10-18 23:19 agent-physx: Findings: PPU loop at 0x224F94 (fn 0x224E58, TOC 0x1C9E6CC) walks a 10-entry table {elf EA, table ptr, name} at 0x1CCB8E4 (PhysX SPU_*Release.elf, images 2-11); per ELF: size=cellOvisGetOverlayTableSize(elf); skip if 0 or 0x80410402; malloc(size+0x84) 128-aligned; cellOvisInitializeOverlayTable(tbl, elf). Error '0 0' comes from upstream stub returning NOT_INITIALIZED (0x80410701, game never calls cellOvisInit) -> malloc(huge) fails. Image 7 = SPU_NarrowPhase1Release.elf: overlay OverlaySmallIsland (code, VMA 0x3080, LMA 0x40000, 0x1A470) and OverlayLargeIsland (all-zero scratch, VMA 0x3080, LMA 0x5A480, 0x1D000). SPU overlay manager at 0x33C00 reads LS table at 0x36C80 {vma,size,lma,loaded}x3 and DMAs from ctx+0x34 (=PPU struct+0x4B4, the cellOvis table ptr, stored at 0x5793C4) + lma. So the table must hold each overlay at offset p_paddr. Plan: real cellOvis + pipeline lifts .text and the code overlay as one image (composite LS).
