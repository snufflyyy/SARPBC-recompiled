# Unreal Engine 3 on PS3 — what the lifted code is doing

SARPBC is a UE3 game (package version 539, licensee 1 — an engine drop from about 2008).
Most of what we lift is engine code, not Psyonix gameplay code. Knowing UE3's shape tells
you where to look before you have symbols. Facts about *this* binary are marked
**[seen]**; general UE3 knowledge is marked *(UE3, verify in binary)*.

## Layout of the game

- Base dir `USRDIR/SARB/`; executable-relative paths start at `SARB/Binaries`
  (PS3TOC.TXT uses `..\TAGame\...`, `..\Engine\...`) **[seen]**.
- Game module `TAGame` (Psyonix's "TA" prefix; later Rocket League keeps it) **[seen]**.
- `PS3TOC.TXT` lists every file with its size; the PS3 file layer reads it at startup so
  it can stat/open without hitting the disk *(UE3, verify)*. Missing or mismatched sizes
  there are a classic cause of load failures.
- Config is read from `COALESCED.INI` (all ini files packed) and `COALESCED.INT`
  (localised strings) — no loose .ini files exist on PS3 **[seen]**.
- Startup loads `STARTUP_INT.XXX` (always-loaded content, 40 MB), `CORE`, `ENGINE`,
  `TAGAME`, then maps (`MAINMENU`, `MP_*`, `PYRAMID_*`) via seek-free loading
  (file list **[seen]**; load order unverified).

## Packages (.XXX / .UPK)

- Magic `9E 2A 83 C1`, version 539, big-endian, cooked for PS3, compressed chunks
  (zlib or LZO on PS3 era UE3 *(verify)*). The decompressor runs as lifted PPU code — if it
  misbehaves, suspect a lifter bug in integer/rotate ops, not the data.
- `TEXTURES.TFC` holds streamed texture mips referenced from packages.
- `GLOBALSHADERCACHE-PS3.BIN` (`GSMB`) and per-package shader caches hold **precompiled
  RSX (NV40) vertex/fragment microcode**. There is no shader compilation at run time;
  ps3recomp translates these programs when they are bound.
- UnrealScript bytecode lives inside packages and is interpreted by the engine's VM
  (`UObject::ProcessEvent`, the `GNatives` table) — it is data, not something we lift.
  Native functions are reached through function-pointer tables: they appear in OPD, so
  they should be in the function list.

## Code shape to expect

- Huge C++ binary: virtual calls everywhere. On PS3 the vtable holds pointers to OPD
  descriptors, so targets are covered by `EBOOT.functions.json`; an unresolved indirect
  call usually means a corrupt object (bad memory/HLE value), not a missing function.
- `appMalloc` → a custom allocator over large blocks from `sys_memory_allocate` /
  `sys_mmapper` *(UE3, verify)*. Out-of-memory at boot = check the runtime's container
  sizes vs what the game asks for.
- RTTI-free, exceptions off; `appErrorf`/`appFailAssert` paths print a message and halt —
  set a breakpoint/trace there to read asserts as text.
- Big-endian serialization (`FArchive`) with byte swapping in game code: lifted, so no
  action needed, but useful when reading memory dumps.

## Threads seen at boot (2026-10-18)

`FlipPump` (0x01BF2080), `spu_printf_handler` ×2, `PoolThread` (0x01BF14A8, waits on Edge
zlib completions), `RegisterTrophyContext` (0x684788), `AsyncIOSystem`,
`RenderingThread` (started, joined and restarted once during init). The main thread polls
`cellSysutilCheckCallback` from its loops.

## Threads *(UE3, verify against `sys_ppu_thread_create` calls at boot)*

| Thread | Role |
|---|---|
| Game thread | main loop: `UEngine::Tick`, UnrealScript, physics |
| Rendering thread | consumes enqueued render commands, owns libgcm |
| Async I/O / streaming | package and texture streaming |
| Audio | PS3 audio device mixing / streaming |
| Online/net | GameSpy + sockets (`IpDrv`) |

Hangs at boot are frequently a game→render-thread fence that never completes because a
GCM label/report or flip event did not fire. See [debugging.md](debugging.md).

## Renderer (PS3RHI)

- Direct libgcm: command buffer writes, `cellGcmSetFlip`, labels/reports for fences,
  tiled render targets, zcull *(UE3, verify)*. Native target 1280×720 **[seen in config]**.
- Post-processing: bloom and DOF chain (`PostFX_Basic`) **[seen]** — expect
  render-to-texture and MRT, which the ps3recomp draw engine supports.
- `LOADSCREEN.FPO/VPO` are the boot loading-screen programs **[seen]** — the first
  thing that should draw.

## Subsystems in the engine build

- **Bink** video (BinkPS3 shaders present **[seen]**): software decode on PPU and/or SPU,
  YCrCb→RGB on RSX. It is game code, not an HLE module.
- **PhysX** 2.x present (`bDisablePhysXHardwareSupport`) **[seen]**; on PS3 it may
  offload to SPU *(verify)* — likely heavy user of SPUJOBS or embedded SPU code.
- **Audio**: `PS3Drv.PS3AudioDevice`, 32 channels, on **MultiStream** (SPU) → cellAudio
  **[seen]**.
- **Edge**: Edge zlib (SPU package inflate) in the EBOOT, Edge Geometry jobs in
  `SPUJOBS.prx` **[seen]**.
- **Online**: `OnlineSubsystemGameSpy` + `IpDrv.TcpNetDriver` **[seen]**. See
  [subsystems.md](subsystems.md#network-and-online).

## Proven in another port

Drakengard 3 (UE3 v860) runs on ps3recomp. The UE3 behaviours its port had to handle —
frame clock / GCM label fences, `UEngine::GetMaxTickRate`, Bink ticked by the render
thread, async-loader pacing, the garbage collector's cost, Edge zlib package inflate
on SPU, MultiStream audio with a firmware MP3 decoder, PhysX tasksets, package hash
checks in the EBOOT — are listed with their fixes in
[reference-ports.md](reference-ports.md). Check there first.

## Useful references

- UE3 public documentation (UDN mirrors) and the UE3-era UDK for class names and the
  general object/package model — names transfer, PS3-specific code does not.
- Ports of other UE3 PS3 titles in RPCS3's compatibility notes: common UE3 PS3 issues
  there (SPU-related hangs, RSX fences) are good hints.
- Rocket League (Psyonix, also UE3) for TAGame class names — never copy code or assets.
