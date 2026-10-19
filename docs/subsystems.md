# Subsystems — what each area needs for SARPBC

One section per area: what the game uses, what ps3recomp provides, and the expected
work. Update the **Status** line of a section when you change it.

## File system

- Game installs as an HDD title: guest paths are `/dev_hdd0/game/NPUB30035/USRDIR/SARB/...`.
  Map with `PS3_HDD0_ROOT=<dir containing game/>` (`runtime/ppu/ppu_fs.cpp`). `PS3_VFS_ROOT`
  covers `/dev_bdvd` — not used by this title unless it probes for a disc.
- **Case sensitivity: no problem.** The engine opens upper-case paths itself
  (`/dev_hdd0/game/NPUB30035/USRDIR/SARB/TAGAME/COOKEDPS3/CORE.XXX`), so they match the
  extracted tree as is (verified with `PS3_FSLOG=1`, 2026-10-18).
- Observed file order at boot: `PS3TOC.TXT`, `___LOCK` (created), `BINARIES/EPICINTERNAL.TXT`
  (ENOENT, fine), `COALESCED.INI`, `COALESCED.INT`, `SPLASH.BMP`, `LOADING.BMP`,
  `LOADSCREEN.VPO/FPO`, `GLOBALSHADERCACHE-PS3.BIN`, then packages `CORE`, `PSYUI`,
  `MAINMENU`, `STARTUP_INT`, `TASTATS`, `TAGAME`, `ONLINESUBSYSTEMGAMESPY(_LOC_INT)`,
  `IPDRV`, `ENGINE`, ...
- `cellGame` is used after all (`HddGameCheck` on `NPUB30035`), through the cellSysutil
  library rather than as its own import.
- `..\` relative paths and backslashes are resolved by the game against its own base
  dir; watch the first opens to see what reaches cellFs.
- Save data: the EBOOT imports **no** cellSaveData or cellGame — saves likely go through
  raw `sys_fs` into a path the engine builds (verify with `PS3_FSLOG`). Save icons ship in
  `SARB/BINARIES/PS3/SAVE/`. Status: not started.

## Graphics (RSX → Vulkan)

- Game uses libgcm directly (UE3 PS3RHI). ps3recomp: cellGcmSys + FIFO walker + NV4097
  draw engine + Vulkan backend running guest programs.
- Expected issues: flip/vblank pacing (game smooths to 60 fps, vsync on), labels/reports
  used as render-thread fences, tiled surfaces, zcull, post-FX render-to-texture, DXT
  textures from TFC, Bink YCrCb shaders.
- First milestone: `LOADSCREEN` program draws the splash/loading screen.
- Status: not started. Linux/Vulkan is the least-proven upstream path.

## Audio

- `PS3Drv.PS3AudioDevice`, 32 voices, LPCM up to 7.1 + Dolby Digital per PARAM.SFO.
- **Confirmed: MultiStream** (statically linked `cellMS*`, incl. MP3 stream functions)
  on SPU, with DSP effects as embedded SPU ELFs (`mstream_dsp_i3dl2/filter/para_eq`),
  outputting through cellAudio (10 imports). `cellMusicUtility` = custom soundtrack.
- Same stack as Drakengard 3: their native MP3 decoder stand-in and DSP hooks
  (`src/apu/`) are the reference if MultiStream asks for a firmware decoder.
- ps3recomp: cellAudio over SDL2 on Linux (`SDL_AUDIODRIVER=dummy` for silent runs,
  `PS3_NO_AUDIO` to disable).
- `cellMic` (15 imports) for voice chat — stub "no mic attached" first.
- Status: not started.

## Input

- Imports (sys_io): `cellPadInit/GetData/GetInfo2/ClearBuf/SetPortSetting/SetActDirect`
  (rumble), `cellKbRead`, `cellMouseGetDataList` — the game reads keyboard and mouse too.
  ps3recomp: cellPad over SDL2 (keyboard + gamepads).
- Rocket-car controls want analog sticks and triggers (L2/R2 likely throttle/brake) —
  verify SDL trigger mapping to the analog pressure values the game reads.
- `PAD_SCRIPT` lets automated runs press buttons at given frames.
- Status: not started.

## SPU / SPURS

- **Status (2026-10-18):** 14 of 15 embedded images are lifted and registered
  (`build_spu_workloads.py --input --allow-partial` in `tools/relift.sh`). Image #7 (324 KB,
  PhysX Dynamics, an overlay image) lifts too once the T003 pipeline patch is in (see PhysX
  below). The Edge zlib task (image 1, fp
  `4100F6EDD2441719`) is dispatched, runs, and then idles in `WAIT_SIGNAL`, because Edge
  zlib requests are now serviced natively on the PPU (`src/overrides/edgezlib.cpp`).
- **`_cellSpursLFQueuePushBody` (NID `0x8A85674D`) has no HLE upstream.** The override
  handles only 32-byte (Edge zlib) queues and refuses others loudly.
  Request layout: in/out EA, in/out size, counter EA|inflate bit, flag EA, flag bits,
  skips. This title passes counter 0 and flag `0x01DC8E00` bits `0x0001`.
- **SPUJOBS.SPRX loads (T002, 2026-10-18).** ps3recomp patch `T002-sys-prx-load-module`
  adds general `sys_prx_load_module` / `_on_memcontainer` / `start` / `stop` /
  `unload` (`runtime/prx/prx_runtime.c` + handlers in `runtime/ppu/ppu_sysprx.cpp`):
  - The guest file is an NPDRM SELF the runtime cannot decrypt, so the loader looks
    for a decrypted copy beside the booted ELF (`game/SPUJOBS.prx` next to
    `game/EBOOT.elf`; tries `FOO.prx`, `foo.prx`, `FOO.PRX`, `FOO.elf`) or in
    `$PS3_PRX_DIR`. No per-title table: everything comes from the module file.
  - Segments go into a bump window at `0x0C000000..0x0D000000`
    (`prx_runtime_window_base/end`, or `PS3_PRX_LOAD_BASE`). It must stay below
    `0x10000000`: the job-chain walker skips binaries at or above it as implausible.
  - module_start runs as lifted code if there is any at its address; otherwise a
    strict leaf evaluator (loads, stores, immediates, `mr`, `blr`; nothing else)
    runs it. That covers SPUJobs, whose module_start only copies four TOC words.
  - Log of a run: `[prx] loaded 'SPUJobs' ... id=0x23001001 at 0x0C000000 size
    0xFF20: 2 segment(s), 16 relocation(s), toc 0x0C017F10` then
    `sys_prx_start_module(0x23001001 'SPUJobs') -> CELL_OK, modres=0, argp ...:
    0C000100 0000FC00 0C00FD80 00000108`.
- **Edge Geometry / ShaderPatching job binaries:** `tools/lift_prx_jobs.py <prx>
  --lifted <SPU_DIR> --register <SPU_DIR>/jobmods_register.c` finds them by
  evaluating module_start offline, lifts each at LS 0 (01.02: A 677 functions, 86
  `.word`; B 6 functions; 01.09: A 714 / 143 `.word`, B 6), and writes a constructor
  that registers them by fingerprint. `jobmods_register.c` is a name the
  CMakeLists already compiles from `SPU_DIR` if present, so no CMake change is
  needed. Verified with gdb on a running build: `spu_workload_fingerprint` of the
  bytes at `0x0C000100` (0xFC00) and `0x0C00FD80` (0x110) both resolve through
  `spu_workload_find`, and the game's globals at `0x01D32690` hold the four argp
  words. Not yet seen dispatched: no job chain runs before the current boot stall.
  Details of the module: [game-profile.md](game-profile.md#spu-code).
- **PhysX on SPU (T003, 2026-10-18).**
  - Ten PhysX SPU programs, listed by a table at `0x1CCB8E0` of `{name EA, ELF EA, overlay
    table EA}` x 10 (accessors `0x2245C8` = ELF, `0x224610` = table). ELF EA minus `0x10000`
    is the EBOOT file offset, i.e. the image number in [game-profile.md](game-profile.md#spu-code):
    11 `SPU_IslandGenerationRelease.elf`, **7 `SPU_DynamicsRelease.elf`**, 10/9/8
    `SPU_NarrowPhase1/2/3Release.elf`, 6 `Cloth`, 5 `HeightField`, 4 `Raycast`,
    2 `FluidSpatialHash`, 3 `FluidCollision`.
  - **cellOvis (libovis)** builds the main-memory image an SPU overlay manager DMAs from.
    Init loop `0x224F94` (function `0x224E58`, TOC `0x1C9E6CC`), right after
    `cellSysmoduleLoadModule(CELL_SYSMODULE_OVIS)`: for each program,
    `size = cellOvisGetOverlayTableSize(elf EA)`; skip on 0 or `0x80410402` (INVAL); else
    allocate `size + 0x84` and align to 128 (original pointer at `t - 4`), then
    `cellOvisInitializeOverlayTable(t, elf)`, and any non-zero result is fatal ("PhysX: Error
    initializing overlay table: %i %i"). The table pointer goes verbatim into the SPU task
    context: `struct + 0x4B4` at `0x5793C4`, i.e. offset `0x34` of the context at
    `struct + 0x480`. The SPU checks it is 128-aligned (`0x80410410` = ALIGN otherwise).
  - **Before T003** upstream's cellOvis was invented API: `GetOverlayTableSize(path, u32*)`
    returned NOT_INITIALIZED (`0x80410701`, nothing calls its fake `cellOvisInit`), the
    game asked the allocator for ~2 GB and printed "Error allocating memory for overlay
    table: 0 0"; `cellOvisInitializeOverlayTable` (`0xA876C911`) was not registered at all.
    Patch `T003-cellovis-overlay-table.patch` implements both real functions: size = highest
    overlay `p_paddr + p_memsz` rounded to 128 (`0x77480` for image 7), INVAL for an ELF with
    no overlay; init zeroes the table and copies each overlay to `t + p_paddr`. Overlay =
    PT_LOAD with `p_paddr` >= 256 KiB and != `p_vaddr`. Boot now logs
    `GetOverlayTableSize(elf=0x01A7F000) -> 0x77480` and `InitializeOverlayTable(table=0x40EF0080, ...)`
    and no PhysX error; the other nine programs have no overlays and are skipped.
    `cellOvisFixSpuSegments` / `InvalidateOverlappedSegments` are still missing (not imported).
  - **Image 7 overlays.** PT_LOADs: `.SpuGUID` (16 B at `0x3000`), `.text`+`.rodata` at
    `0x20080`, `.data`/`.bss` at `0x36C80`, and two overlays at VMA `0x3080`:
    `OverlaySmallIsland` (code + inline strings, LMA `0x40000`, `0x1A470` B) and
    `OverlayLargeIsland` (LMA `0x5A480`, `0x1D000` B, all zero: a scratch buffer). The SPU
    manager (`0x33C00`, load-and-mark `0x33DC0`) walks `{vma, size, lma, loaded}` x 3 at LS
    `0x36C80` (count at `0x36CB0`) and DMA-GETs `size` bytes from `table + lma`, clearing
    `loaded` on overlays it overwrites. `0x20188` brings in LargeIsland, after which a stack
    allocator (`0x37120` cursor, `0x37130` end) hands out `0x3080..0x20080` as scratch;
    `0x20338` brings SmallIsland back and resets the allocator to `0x164F0..0x1D4F0`
    (the free tail of the code overlay). `.text` then calls straight into it (`brsl 0x9170`
    at `0x236CC`, `0x23DC4`).
  - **Lifting it** (patch `T003-spu-overlay-lift.patch`): only one overlay holds code, so the
    pipeline lifts `.text` and SmallIsland together as one image (one LS image spanning both,
    each at its own address; 1,463 functions, 495 in the overlay) and registers it by full-ELF
    fingerprint `39119073A3F69512`. Same-address code overlays would need separate lifts and
    are still refused. Ranges holding an undecodable word (inline strings seeded by `ila`) are
    dropped as data; that also fixes the 01.09 images `e33837bb55e5` and `d08b1ad818d0`.
  - **Not yet seen running:** the PhysX taskset is created (`CreateTaskset() ea=0x01CEE680`)
    but no PhysX task starts before the boot stall, so image 7 has not been HIT at run time.
- Confirmed sources ([game-profile.md](game-profile.md#spu-code)): 15 SPU ELFs embedded
  in the EBOOT — **Edge zlib** (package inflate), **PhysX** tasks, **MultiStream** DSP,
  several unidentified — and **Edge Geometry** job images inside `SPUJOBS.prx`
  (a PPU PRX loaded with `sys_prx_load_module`).
- SPURS features used: tasksets, tasks, job chains, event flags, job guards, **Queue
  and LFQueue**. Drakengard 3 lifted Sony's libsre for Queue/LFQueue; we cannot ship
  firmware, so T019 wrote the PPU side from the task-side code instead.
- **SPURS Queue (T019, patch `T019-spurs-queue-ppu.patch`, `libs/spurs/cellSpursQueue.c`).**
  PhysX tasks report to the PPU through SPU2PPU queues (task helper "sendResponseToPPUAndExit":
  non-blocking push retried on AGAIN/BUSY, then push end). Line layout, derived from the
  task-side push in the PhysX images (image `7bde2a3f`: begin LS `0x6990`, end `0x6E88`,
  event throw `0x7608`, task signal `0x7238`): pop index `+0x00`, push index `+0x04` (both in
  `[0, 2*depth)`, stored as `~index` while that side is in progress), size `+0x08`, depth
  `+0x0C`, buffer u64 `+0x10`, SPU port `+0x18` (-1 = none), direction `+0x1C`, waiter lists
  `+0x20` pop / `+0x30` push (u8 count + task ids; workload ids at `+0x40`/`+0x50`), taskset
  u64 `+0x60`. Upstream's old init put size/buffer at `+0x10`/`+0x18` (wrong).
  - Game calls (01.09): `_cellSpursQueueInitialize(0, taskset, q, buf, 16, 128, SPU2PPU)` at
    `0x008496B0`, then `cellSpursQueueAttachLv2EventQueue(q)`; `cellSpursQueuePopBody(q, buf,
    isPeek=0, isBlocking=1)` at `0x008482EC` (any error is fatal) and `(…, 0, 0)` at
    `0x00848394`, which treats `0x80410901` (AGAIN) as "empty". Elements are 16 bytes; the PPU
    reads words `+8` and `+0xC`. Note `cellSpurs.h`'s `CELL_SPURS_TASK_ERROR_*` macros are
    `0x804107xx`; the real values are `0x804109xx` (the queue code spells its own).
  - Blocking pop/push = retried non-blocking tries that sleep until an SPU commits the queue
    line (SPU line-commit hook) or 1 ms (dod3's design). The PPU never parks holding the pop
    side, so the task never needs to throw the `+0x18` event.
  - Verified: `test_spurs_queue` (ctest `spurs_queue`) and a 01.09 boot: six queues init and
    attach (ports 17-22), three blocking pops return real task results, no "Error writing to
    SPURS queue". The boot then stalls elsewhere (EventFlagWait on `0x01372000`, job guard
    `0x0133AA80` closed 20 s).
  - LFQueue: init now writes libsre's CellSyncLFQueue line (from dod3); a general
    `_cellSpursLFQueuePushBody` is still missing (Edge zlib is serviced natively).
- Bink: no Bink SPU image identified yet; may decode on PPU.
- ps3recomp: SPU lifter, workload registry by fingerprint, SPURS (tasks, job chains, job
  queues, policy modules), interpreter fallback, `SPU_DUMP_MISS` capture.
- Typical failure: a PPU thread waiting forever on an event flag / sync word an SPU job
  never set — see [debugging.md](debugging.md).
- Status: in progress (T002 done: SPUJOBS loads; job binaries lifted and registered).

## Video (Bink)

- BinkPS3 is statically linked game code; the three `BINKPS3_*.BIN` files are its RSX
  shaders. No HLE module involved — it works when PPU lifting, SPU jobs and RSX do.
- If intros block progress early, consider skipping them (find the movie-play call)
  rather than debugging Bink first; record any such override in `src/overrides/`.

## Network and online

- The game uses **GameSpy** (`OnlineSubsystemGameSpy`, peerchat.gamespy.com) over
  `IpDrv.TcpNetDriver`. GameSpy died in 2014, so official online is gone.
- NP imports (43): `sceNpDrmIsAvailable` (license check — must return OK),
  Manager (NP ID, online name, ticket), Basic (friends), Lookup, **Score**
  (leaderboards — psnr implements Score), **Signaling** (P2P). sys_net 22, cellNetCtl 8.
- `cellRec`, `cellVideoUpload`, `cellVideoExportUtility`: replay recording/upload —
  stub as unavailable.
- Plan: boot **offline** first — sceNp reports signed-out, sys_net with
  `PS3_NET_ONLINE` unset. Make sure the "can't connect" paths don't block menus.
- Later options: OpenSpy-style GameSpy replacement via DNS/host redirect, or LAN/direct
  IP if the engine exposes it. ps3recomp's psnr only covers NP matching, not GameSpy.
- Local split-screen (up to 4 pads) is the more valuable multiplayer goal.
- Status: not started.

## Trophies, system UI, misc

- Trophy set `NPWR00406_00`: registration works (status callback `0x683B48` stores
  `completed` at arg+4; the registration thread `0x684788` writes -1 there when done). It
  needs patch 0001: upstream's deferred completion raced that -1.
- System dialogs (cellMsgDialog, cellOskDialog for names), cellSysutil callbacks (XMB
  exit, game-exit request) — implemented upstream; watch for an unhandled callback stall.
- `PS3LOGO.DAT`, `ICON1.PAM` are XMB assets the game never reads.
