# T002: Load SPUJOBS.SPRX (sys_prx_load_module / sys_prx_start_module are unresolved)

Status: done
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
- 2026-10-18 23:34 agent-frontier: FYI from T001 (01.02, with sys_memory patch + a LOCAL experiment making cellOvisGetOverlayTableSize return 0x80410402 so PhysX passes): the next stall is yours. Render thread func_006DDFF0 calls cellSpursRunJobChain(obj+0x21200) then appSleep-polls until u32 [obj+0x21180] reaches its fence value; the chain jc=0x01D53900 (entry 0x01D32700) has jobs with eaBinary=0 size=0 (cellSpurs: 'implausible binary -- skipped'), so the counter never advances. Game thread (func_000D6300, lr 0x000D66EC) loops on a 100 ms event wait (q=7) for the frame. FIFO also hits an old-style JUMP-to-self (e.g. w=0x20104708 at io 0x00104708) - a placeholder the jobs should overwrite; cellGcmSys resyncs past it. Presumably the job descriptors get eaBinary from SPUJOBS.SPRX exports once it is loaded.
- 2026-10-18 23:44 agent-prx: 01.02 vs 01.09 SPUJOBS: same structure, same 12-insn module_start, same 16 ADDR32 relocs and TOC layout; seg0 0xFF00 vs 0xC000; job A (Edge Geometry) 0xFC00 vs 0xBD80 bytes at seg0+0x100; job B 0x108 bytes at seg0+0xFD80 vs +0xBE80 (bytes differ). Loader + tools/lift_prx_jobs.py are file-driven and verified on both files (01.09 offline only: lift_prx_jobs ran clean, 714+6 functions). Verified on 01.02 run: [prx] start -> argp 0C000100 0000FC00 0C00FD80 00000108; gdb: runtime fingerprints of guest bytes at 0x0C000100/0xFC00 and 0x0C00FD80/0x110 both found in the registry. Coordinator: add to tools/relift.sh after build_spu_workloads: '.venv/bin/python tools/lift_prx_jobs.py game/SPUJOBS.prx --lifted src/spu_gen --register src/spu_gen/jobmods_register.c', then reconfigure.
- 2026-10-18 23:44 agent-prx: DONE: SPUJOBS.SPRX now loads and starts. New ps3recomp patch T002-sys-prx-load-module adds general sys_prx_load_module/_on_memcontainer/start/stop/unload: decrypted module looked up beside the booted ELF (or $PS3_PRX_DIR), segments placed at 0x0C000000 (main memory, below 0x10000000 so the job-chain walker accepts job binaries there), PPURELA relocations applied, module table and exports parsed; module_start runs as lifted code or through a strict leaf evaluator (SPUJobs' module_start only copies 4 TOC words). The game receives {0x0C000100, 0xFC00, 0x0C00FD80, 0x108} = Edge Geometry job and the ShaderPatching job. tools/lift_prx_jobs.py lifts both job binaries (01.02 and 01.09) and writes a fingerprint registry (jobmods_register.c, already compiled by CMake from SPU_DIR); gdb confirms the in-guest binaries' fingerprints resolve to the lifted entries. No job has been dispatched yet because no job chain runs before the T001 stall. Needs a relift.sh step (see note).
