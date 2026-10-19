# Subsystems — what each area needs for SARPBC

One section per area: what the game uses, what ps3recomp provides, and the expected
work. Update the **Status** line of a section when you change it.

## File system

- Game installs as an HDD title: guest paths are `/dev_hdd0/game/NPUB30035/USRDIR/SARB/...`.
  Map with `PS3_HDD0_ROOT=<dir containing game/>` (`runtime/ppu/ppu_fs.cpp`). `PS3_VFS_ROOT`
  covers `/dev_bdvd` — not used by this title unless it probes for a disc.
- **Case sensitivity**: the PKG ships upper-case names; the engine asks for mixed case
  (`..\TAGame\CookedPS3\Startup_int.xxx`). Real PS3 hardware is case-sensitive too, so
  the engine must already normalise (probably upper-cases) — confirm with `PS3_FSLOG=1`
  on the first run before adding any case-folding.
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

- Confirmed sources ([game-profile.md](game-profile.md#spu-code)): 15 SPU ELFs embedded
  in the EBOOT — **Edge zlib** (package inflate), **PhysX** tasks, **MultiStream** DSP,
  several unidentified — and **Edge Geometry** job images inside `SPUJOBS.prx`
  (a PPU PRX loaded with `sys_prx_load_module`).
- SPURS features used: tasksets, tasks, job chains, event flags, job guards, **Queue
  and LFQueue**. Drakengard 3 needed Sony's libsre lifted for Queue/LFQueue and a native
  Edge zlib — expect the same here.
- Bink: no Bink SPU image identified yet; may decode on PPU.
- ps3recomp: SPU lifter, workload registry by fingerprint, SPURS (tasks, job chains, job
  queues, policy modules), interpreter fallback, `SPU_DUMP_MISS` capture.
- Typical failure: a PPU thread waiting forever on an event flag / sync word an SPU job
  never set — see [debugging.md](debugging.md).
- Status: not started.

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

- Trophy set `NPWR00406_00` (`TROPHY.TRP`): sceNpTrophy HLE exists; it needs the TRP
  readable at its install path.
- System dialogs (cellMsgDialog, cellOskDialog for names), cellSysutil callbacks (XMB
  exit, game-exit request) — implemented upstream; watch for an unhandled callback stall.
- `PS3LOGO.DAT`, `ICON1.PAM` are XMB assets the game never reads.
