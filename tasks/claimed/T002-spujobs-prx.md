# T002: Load SPUJOBS.SPRX (sys_prx_load_module / sys_prx_start_module are unresolved)

Status: claimed
Owner: agent-prx
Touches: src/overrides/prx_*.cpp (new), docs/subsystems.md (SPU section), docs/game-profile.md (SPU code section), tools/ (new scripts only)
Reads: game/SPUJOBS.prx, external/ps3recomp/tools/lift_prx.py, prx_exports.py, runtime/ppu/ppu_sysprx.cpp

## Goal
The game calls `sys_prx_load_module` (NID 0x26090058) and `sys_prx_start_module`
(0x9F18429D) for `/dev_hdd0/game/NPUB30035/USRDIR/SARB/BINARIES/PS3/SPU/SPUJOBS.SPRX`.
Both are unresolved, so the module never loads. It is a PPU PRX (`e_type 0xFFA4`, decrypted to
game/SPUJOBS.prx) whose contents are Edge Geometry SPU job images (raw SPURS job code,
not SPU ELFs). Work out what the game needs from it (exports it calls? job images it
hands to cellSpursJobChain?), then implement loading: either lift/relocate the PRX
(lift_prx.py, as libsre LLE does) and register its exports, or HLE the load and place
the job images where the game expects them. Also capture/lift the Edge Geometry job
images so cellSpurs job chains can dispatch them (SPU_DUMP_MISS, find_spu_functions --raw).

## Done when
`sys_prx_load_module/start_module` return the right values and the module's exports
(if any) resolve, with Edge Geometry jobs lifted and registered or a precise written
plan for them. Documented in docs/subsystems.md.

## Log
- 2026-10-18 23:12 agent-prx: claimed
- 2026-10-18 23:20 agent-prx: Findings: SPUJOBS.prx (01.02 and 01.09) is a data-only PRX: no imports, exports only module_start/stop/info (NIDs BC9A0086/AB779874/D7F43016). module_start (12 insns, identical in both) copies 4 TOC words into argp: {seg0+0x100 Edge Geometry job binary, size, seg0+tail job binary, 0x108}. 01.02: job1 size 0xFC00, job2 @seg0+0xFD80; 01.09: job1 size 0xBD80, job2 @seg0+0xBE80 (same 0x108 size). Relocs only ADDR32 (type 1), 16 entries. Game calls load(path,0,0) at lr 0x6E4A88 and start(id,4,argp=sp+0x98,modres=sp+0x70,0,0) at lr 0x6E4B08, then stores argp[0..3] into 4 globals (TOC-0x41F4/-0x41F0/-0x4164/-0x4160) and creates the ShaderPatching job chain. Plan: generic sys_prx_load/start/stop/unload in toolkit (file-driven loader + relocations + module table; decrypted copy looked up next to the loaded EBOOT.elf or PS3_PRX_DIR; module_start via lifted fn if registered, else a strict leaf-function evaluator), plus a tools/ script that extracts+lifts the job binaries listed by module_start.
