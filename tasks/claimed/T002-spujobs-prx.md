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
