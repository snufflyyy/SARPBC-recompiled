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
- `appMalloc` → a custom allocator over pages from `sys_memory_allocate` **[seen]**: almost
  all requests use 64 KB pages (`flags=0x200`; 423 of 641 calls are exactly 0x10000), and
  it **returns empty pages with `sys_memory_free` and asks for new ones** all through
  package loading (323 frees in the first 60 s). Live use after MAINMENU is ~69 MB. The
  runtime must reuse freed address ranges or the 256 MB window runs out (T001 patch).
  One `sys_mmapper_allocate_memory(0x700000)` comes first (lands at `0x40000000`).
- Out of memory shows up as `[null-write] guest wrote16 ... by guest-fn=0x005F8E38`: the
  OOM handler formats the UTF-16 text "OOM 4064..." into a NULL buffer (01.02 address;
  in 01.09 find it by the same null-write, or by a 2-byte store loop called from the
  allocator's failure path). It is followed by `IO Failure detected, callstack is:`.
- RTTI-free, exceptions off; `appErrorf`/`appFailAssert` paths print a message and halt —
  set a breakpoint/trace there to read asserts as text.
- Big-endian serialization (`FArchive`) with byte swapping in game code: lifted, so no
  action needed, but useful when reading memory dumps.

## Threads seen at boot (2026-10-18)

`FlipPump` (0x01BF2080), `spu_printf_handler` ×2, `PoolThread` (0x01BF14A8, waits on Edge
zlib completions), `RegisterTrophyContext` (0x684788), `AsyncIOSystem`,
`RenderingThread` (started, joined and restarted once during init). The main thread polls
`cellSysutilCheckCallback` from its loops.

Boot order after the first packages, 01.02, 2026-10-18 (with the T001 memory patch):
`ENGINE` → `../DLC` (opendir, ENOENT is fine) → `/dev_flash/sys/external/flashMP3.pic`
(MultiStream's firmware MP3 decoder, not shipped: open fails) → `TAGAME/DEMOS` (opendir)
→ `GUIDCACHE.XXX` → `MAINMENU.XXX` → `cellGcmMapMainMemory` ×2 (1 MB each at
`0x20A00000`, `0x20B00000`) → two `PPU PhysX thread`s (entry OPD `0x01C4F178`) →
`RenderingThread` restarted → `cellSysmoduleLoadModule(OVIS)` → PhysX init fails (see
debugging.md, T003) → the game exits through `sys_prx_exitspawn_with_level`. 01.09 runs
the same sequence (packages `PROJECTX`, `PSYNET`, `ONLINESUBSYSTEMPS3` instead of the
GameSpy ones; `MultiStream Update Thread` and `SaveData` threads start before PhysX).

**Game thread / rendering thread frame fence** **[seen]**: once per frame the game thread
waits for the rendering thread with a virtual `Wait(100)` on an event (an lv2 event
queue receive with a 100 ms timeout, retried until it reports success; 01.02
`func_000D6300` → lr `0x000D66EC`). A stuck rendering thread shows up as a steady stream
of `event_queue_receive(q=N timeout=100000) tid=1`, not as a block. The rendering thread
in turn waits for the RHI's SPURS job chain: `cellSpursRunJobChain` and then an
`appSleep` poll on a counter the jobs advance (01.02 `func_006DDFF0`, counter at
`obj+0x21180`; `func_006C61F0` is `appSleep`: float seconds → `sys_timer_usleep`).

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
- **GPU fences (01.09, T022) [seen].** Each RHI fence is a back-end label write to label
  255 (`0x1D6C 0xFF0`, `0x1D70 value`). The CPU waits in `func_000DD014`, which sleeps 250 µs
  (`sys_timer_usleep`) until label ≥ target, with wrap-around compare; the last value seen is
  kept at `0x01295480`. The fence bookkeeping object is at the base of the title's RSX heap
  (`0x20000000`: +0xFA4 next fence, +0xFA0 count, +0xC80 table).
- **RSX heap:** one `sys_mmapper_allocate_address(0x10000000, align 0x10000000)` via raw `sc`
  at `0x000DFA68`, of which `cellGcmMapMainMemory(0x20000000, 0xA00000)` is RSX-visible.
- **FIFO parks [seen].** The PPU writes a JUMP-to-self and keeps writing after it. Two
  kinds: (a) after `GET_REPORT` + user command `0xEB00`, released by the **flip handler**
  `func_000DC144` (OPD `0x012025A0`) through the user handler `func_000DC390` (OPD `0x012025B0`)
  → `cellGcmSetFlipImmediate`; vblank handler OPD `0x012025A8`. (b) Before
  `SET_SHADER_PROGRAM`, released by a **ShaderPatching** SPU job (chain `0x012B6F00`, command
  ring `0x01295D00`: 512 slots, a JOB per patched draw, LWSYNC (`0x12`) every 64 slots,
  NEXT back to the start at slot 512; descriptors 256 B from `0x01296D80`; job binary
  `0x0C000100` in SPUJOBS). The game appends by overwriting the END slot and calls
  `cellSpursRunJobChain` each time.

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
