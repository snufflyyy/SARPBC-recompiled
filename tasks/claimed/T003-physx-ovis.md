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
- 2026-10-18 23:20 agent-frontier: Caller detail (01.02, func containing 0x00224F94-0x00225010, call sites lr=0x00224FA4 / 0x00225010): loops 10 SPU ELFs; size=cellOvisGetOverlayTableSize(elf_ea) is the s32 return value (single arg r3=elf ea); size==0 or size==0x80410402 => skip this ELF (no overlays); else alloc(size+0x84) and cellOvisInitializeOverlayTable(table_ea, elf_ea), result 0 = ok. So the HLE must take one arg and return the size (or 0x80410402 when the ELF has no overlay segments).
- 2026-10-18 23:28 agent-physx: cellOvis done (ps3recomp commit 'cellOvis: implement the real overlay-table API' + tests/test_ovis_overlay_table.c PASS). Run: '[cellOvis] GetOverlayTableSize(elf=0x01A7F000) -> 0x77480 (2 overlay segments)' / 'InitializeOverlayTable(table=0x40EF0080, ...)', no PhysX overlay error. Needs ppu_hle_nids.cpp regenerated (gen_hle_nids.py --all) - removed invented cellOvisInit/CreateOverlay/... and added 0xA876C911. Now: pipeline support for image 7 (multi executable PT_LOAD + overlays).
- 2026-10-18 23:36 agent-physx: Pipeline: image 7 now lifts+registers (1463 fns, 495 in OverlaySmallIsland, 0 unsupported); inventory complete=True 15/15; other 14 images byte-identical outputs. ps3recomp commit 'build_spu_workloads --input: lift SPU overlay images' + tests (test_spu_program_pipeline 15 OK). Building/running with worktree-local src/spu_gen.
- 2026-10-18 23:48 agent-physx: Re 01.09: the pipeline change also fixes e33837bb55e5 and d08b1ad818d0 ('unsupported instructions'): those .word were floats/ASCII literal pools seeded as functions via ila; detected ranges containing an undecodable word are now dropped. Local lift of versions/0109 EBOOT: 15/15 registered, complete=True; other 12 byte-identical to the coordinator's 01.09 lift. 01.02: 15/15, the 14 old ones byte-identical.
