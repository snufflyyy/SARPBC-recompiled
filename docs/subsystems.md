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
- **01.09 boot, 2026-10-19 (T007):** `cellAudio` Init / PortOpen(8 ch, 8 blocks, buffer
  `0x58000000`, read index `0x58100000`) / PortStart all succeed. The MultiStream mixer is
  **SPU image 0** (sha `e33837bb...`, fp `C1759183E2FF7448`, task ELF at EA `0x010AF300`),
  started as taskset `0x01370680` task 0. Its "MultiStream Update Thread" (entry OPD
  `0x01225628`) waits on SPURS event flag `0x01372000` bit 1, which the mixer sets.
- **Blocker 1: the DSP plugin block (FIXED 2026-10-19, `tools/make_spu_overlays.py`).** The
  mixer copies the DSP plugins' text into one heap block, GETs it to **LS 0x37000** and calls
  into it (0x37018, 0x37010, 0x37C20, then 0x39818/0x39810/0x39B50; return addresses
  0x03930/0x03AE0/0x04130). Nothing was lifted there, so the task ended with "branched into
  unlifted LS 0x37018" and flag `0x01372000` never got set (`EventFlagWait BLOCKED ...
  flagEA=0x01372000`). Layout, from `SPU_DUMP_OVL=<dir>,0x37000` on 01.09: one 0x2E90-byte
  block, **`mstream_dsp_i3dl2.pic` text at +0x0000 (0x27C0 bytes) and
  `mstream_dsp_para_eq.pic` at +0x2800 (0x690)**, byte for byte the ELFs' executable PT_LOADs
  (va 0x80 = block +0; no relocation applied). `mstream_dsp_filter.pic` is not loaded. dod3's
  2013 MultiStream packs three plugins at 0x0/0x2000/0x2900, so the table is per title.
  `tools/make_spu_overlays.py --spu <SPU_DIR>` (ported from dod3, MIT; `tools/relift.sh`
  runs it after `build_spu_workloads.py`) finds the plugins among the lifted images by their
  SPUNAME string, rebuilds the block, wraps it at 0x37000, lifts it as
  `<SPU_DIR>/spu_ovl_msdsp_37000/` (94 functions; seeds: entries, +0x10 of each plugin, the
  instruction after each `bi $r0`), and appends a constructor that registers it under image
  id `0x4D534401` with `spu_overlay_register_sig_region(first 16 bytes, 0x2E90)`; CMake's
  `*/spu_recomp.c` glob picks it up with no other change. Verified on 01.09 without
  `SPU_INTERP_UNLIFTED`: no "unlifted LS 0x37..." and no BLOCKED on `0x01372000`; perf shows
  the `spu_ovl_msdsp_37000_*` functions running. **01.02:** its plugins are different builds
  (i3dl2 0x2800, para_eq 0x680 bytes), so the tool lays para_eq at +0x2800 there too, but
  that layout is a guess (no 01.02 dump yet; check with `SPU_DUMP_OVL`).
- **Open: the mixer is too slow for real time.** One mixer cycle = one wait on `0x01372000`;
  each full cycle PUTs one 8 KB block (8 ch x 256 x float) into the cellAudio port
  (`SPU_DMA_RANGE=58000000-58200000`, PUT from SPU pc 0x095D0). Real time is 187.5 blocks/s
  = 1.536 MB/s. Measured (01.09, Ryzen 7 5700X, `SPURS_EF_STATS=1`): **75 cycles/s, 410 KB/s
  (27% of real time)**; built with `-DCMAKE_C_FLAGS=-msse4.1`: 120 cycles/s, 660 KB/s (43%).
  `perf` (default build): 37% of all samples in the out-of-line `spu_shufb` byte loop (the
  pshufb path needs `__SSE4_1__`, which our default x86-64 build does not define), ~17% in
  the scalar SPU float helpers (`spu_fa`/`spu_fs`/`spu__fma_any`; upstream vectorises them
  for NEON only), 28% in the lifted i3dl2/para_eq code (0x37614, 0x37198, 0x39A18, 0x37B20),
  16% in the mixer itself. The i3dl2 hot loop (0x37478-0x37974) is optimised SPU code (comb/
  allpass delay taps), not dod3's -O0 biquads, so dod3's `msdsp_hooks.c` addresses do not
  apply. Cheapest wins, both generic: build the SPU sources with SSE4.1 (or
  `-march=x86-64-v2`), and an SSE2/AVX version of the NEON float fast path in
  `runtime/spu/spu_helpers.h`. Until then real audio would stutter.
- **Blocker 2: `flashMP3.pic` (FIXED, untested end to end).** The PPU (01.09 `func_0082E690`)
  reads `/dev_flash/sys/external/flashMP3.pic` into a buffer and `func_00835588` parses its
  SPU ELF section table into a descriptor {+0 file EA, +4 body EA, +8 lowest sh_addr,
  +C size, +10 e_entry}. Without it: "Multistream: mp3 failed to load MP3 codec".
  `src/overrides/audio_mp3.cpp` (ported from dod3 `mp3_native.c`, MIT) writes a stand-in
  ELF of our own to `<exe dir>/dev_flash/` at start-up and sets `PS3_DEV_FLASH` (unless the
  user set it), registers a native `decodeFrame` at **LS 0x1A910** (body at 0x1A900, as in
  dod3; the mixer's descriptor sits at LS 0x1A880 and it calls decodeFrame at SPU 0x6E2C
  through the word at LS 0x3C4B0) and decodes with dod3's decoder
  (`audio_mp3dec.cpp`). Verified: the file opens and the error is gone. **Not verified:**
  no MP3 stream starts before the boot stalls at "Loading...", so decodeFrame has not been
  called yet. `SARPBC_MP3_TRACE=<n>` logs the first n calls, `SARPBC_MP3_NATIVE=0` turns it off.
- **cellAudio on Linux (patch `T007-audio-pacing-devflash-sig-region`):** the POSIX mixing
  loop now paces to the SDL queue (it used fixed 2/5 ms sleeps), and
  `AUDIO_RATE=1` / `AUDIO_PEAK=1` / `AUDIO_WAV=<file>` work on Linux. With PipeWire
  (`SDL_AUDIODRIVER=pulseaudio`): `[audio-rate] 187.5 blocks/s (real time 187.5), silent
  100.0%, dropped 0 frames/s, underruns 0`: the port runs at real time on a real device,
  but every block is silent (nothing reaches the port yet).
  The same patch moves the `/dev_flash` default off a Windows path
  (`$XDG_DATA_HOME/ps3recomp/dev_flash`) and adds `spu_overlay_register_sig_region()`.
- Still seen: `[mfc] REJECTED malformed transfer ... pc=0x0B1C8 lsa=0x30B60 size=0` from
  the mixer, a size-0 GET (a no-op on hardware too; probably an empty stream list).
- ps3recomp: cellAudio over SDL2 on Linux (`SDL_AUDIODRIVER=dummy` for silent runs,
  `PS3_NO_AUDIO` to disable).
- `cellMic` (15 imports) for voice chat — stub "no mic attached" first.
- Status (2026-10-19, T007): the port runs on a real device (pulseaudio, 0 underruns); the
  mixer runs lifted (DSP block at 0x37000) and PUTs every block it finishes into the port,
  but slower than real time (above); MP3 stand-in in place. Every block so far is silent
  (`AUDIO_PEAK=1`: peak 0.0000): the 01.09 boot stalls at "Loading..." before any sound
  plays, so nothing audible can be checked yet.

## Input

- Imports (sys_io): `cellPadInit/GetData/GetInfo2/ClearBuf/SetPortSetting/SetActDirect`
  (rumble), `cellKbRead`, `cellMouseGetDataList` — the game reads keyboard and mouse too.
  ps3recomp: cellPad over SDL2 (keyboard + gamepads).
- Rocket-car controls want analog sticks and triggers (L2/R2 likely throttle/brake) —
  verify SDL trigger mapping to the analog pressure values the game reads.
- `PAD_SCRIPT` lets automated runs press buttons at given frames.
- **What the game reads (01.09, from the lift):** `func_000D101C` calls cellPadGetData into
  a stack buffer at r1+0x80. Sticks are `(v - 127) * 1/127` (constant at `0x000D0FF4`),
  so the centre is 127/128. L2/R2 are the press-mode words button[18]/[19] (guest
  +0xA8/+0xAA) times 1/255 (`0x000D0FF8`): analog throttle and brake. SIXAXIS words
  (+0xAC..+0xB2) are read only under per-object flags. When `len == 0` it keeps the last
  values, and on an error with `len != 0` it calls ClearBuf. `func_000D1AF4` calls
  GetInfo2 and then `SetPortSetting(port, 2)` only if the port is connected and
  advertises PRESS_MODE. Rumble (`func_000D35D8` -> SetActDirect) sets the small motor
  to 0/1, switched on and off per frame for intensity, and the large motor to 0-255.
  `cellKbRead`/`cellMouseGetDataList` have **no callers**, and cellKbInit/cellMouseInit
  are not imported, so keyboard play must go through the virtual pad.
- **ps3recomp patches:** `T008-1-dod3-cellpad-sdl2-port.patch` contains Drakengard 3's
  13 libs/input commits (soyjxck, MIT, authors kept): an SDL pad thread, pads by instance
  id, rumble held, `cellPad_set_host_input`, host kind, PAD_NO_HOST.
  `T008-2-cellpad-racing-fixes.patch` adds our fixes: a half-pulled trigger no longer
  reads as 255 in press mode, the small motor is on/off (0xFFFF), an empty SDL port's
  sticks are 128 (was 0 = held up-left), `PAD_TRIGGERS="l2,r2[,from,until]"`, and
  `PAD_TRACE=1` (logs what reached the guest buffer). Test:
  `CC=clang python3 external/ps3recomp/libs/input/tests/test_cellpad_sdl.py` (SDL virtual
  gamepad, 36 checks).
- **Desk pads:** the SDL thread reads pads even without window focus, so a pad on the desk
  feeds headless runs. Use `PAD_NO_HOST=1` for hands-off runs.
- **Esc** closes the Vulkan window in `rsx_vulkan_backend_pump_messages`. While Esc is
  bound (it is START by default), `input_kbm.cpp` installs an `SDL_SetEventFilter` that
  drops the Esc key-down before the pump sees it. SDL updates its key state before it
  filters, so the key still reads as held. The window's close button still quits.
- `src/overrides/input_config.cpp`: UPPER-CASE keys in config.toml `[input]` become
  environment variables, and the environment wins (`KEY_R2=F tools/run.sh`). The file
  is `$SARPBC_CONFIG`, else `config.toml` beside the executable or one folder up
  (`build-0109/../config.toml`), else `./config.toml`. It runs from a static
  constructor, before main, so `PAD_*` switches can also live there. The run log
  prints `[input] <path>: N control setting(s)`.
- `src/overrides/input_kbm.cpp`: keyboard and mouse into pad port 0. Ported from
  dod3-recomp `96df4c3 src/input/kbm.cpp` (MIT): the binding table, the key parser and
  the 4-way sticks come from there. The key source is new: SDL2 `SDL_GetKeyboardState`
  by **scancode** (a physical key position, so WASD stays WASD on AZERTY),
  `SDL_GetMouseState` for the buttons, and the wheel counted in the event filter. It
  only acts while an SDL window has keyboard focus. It registers through
  `cellPad_set_host_input` (patch T008-1) and is merged with any real pad. The run
  log prints `[keyboard] keyboard and mouse on pad port 0`. `SARPBC_KEYBOARD=0` turns
  it off, and `SARPBC_KBM_LOG=1` logs every change. Not built on Windows or macOS (no
  SDL window there), where ps3recomp's own keyboard fallback stays. Mouse look (dod3
  `camera.cpp`) is not ported, because it patches Drakengard 3's own camera addresses.
- **sdl2-compat quirk (measured):** Fedora's SDL2 is sdl2-compat 2.32.74 on top of SDL3.
  A wheel notch reaches an SDL2 event filter as `wheel.y = 0, preciseY = 1.0`, so the
  filter also reads `preciseY`.

**Default bindings** (config.toml `[input]`; each value is a list of keys, `none` = unbound):

| PS3 | Car action (guess from RL conventions) | Gamepad (SDL, by position) | Keyboard / mouse | Setting |
|---|---|---|---|---|
| R2 (analog) | throttle | right trigger (0-255 pressure) | W (full pull) | `KEY_R2` |
| L2 (analog) | brake / reverse | left trigger | S | `KEY_L2` |
| left stick | steer, air pitch/yaw | left stick | W A S D | `KEY_MOVE_UP/_DOWN/_LEFT/_RIGHT` |
| right stick | camera | right stick | I K J L | `KEY_LOOK_UP/_DOWN/_LEFT/_RIGHT` |
| CROSS | jump | bottom face (A / Cross) | Space, right mouse | `KEY_CROSS` |
| CIRCLE | boost | right face (B / Circle) | Shift, left mouse, Backspace | `KEY_CIRCLE` |
| SQUARE | powerslide | left face (X / Square) | Ctrl | `KEY_SQUARE` |
| TRIANGLE | (ball cam?) | top face (Y / Triangle) | R | `KEY_TRIANGLE` |
| L1 / R1 | | shoulders | Q / E | `KEY_L1` / `KEY_R1` |
| L3 / R3 | | stick clicks | C / V | `KEY_L3` / `KEY_R3` |
| START | pause | Start / Options | Esc, Enter | `KEY_START` |
| SELECT | | Back / Share | Tab | `KEY_SELECT` |
| d-pad | menus | d-pad | arrow keys | `KEY_UP/_DOWN/_LEFT/_RIGHT` |

Key names: A-Z 0-9 F1-F12 Space Enter Tab Esc Backspace Shift Ctrl Alt LShift RShift
LCtrl RCtrl LAlt RAlt Up Down Left Right Insert Delete Home End PageUp PageDown CapsLock
Minus Equals LBracket RBracket Semicolon Quote Comma Period Slash Backslash Grave Num0-Num9
Mouse1 (left) Mouse2 (right) Mouse3 (middle) Mouse4 Mouse5 WheelUp WheelDown. The "car
action" column is a guess until menus and a match run; check it against the game's own
controls screen.

- **Verified (01.09, build-0109, 2026-10-19):**
  - The default command `PAD_TRACE=1 PAD_TRIGGERS=0,128,5 SPU_INTERP_UNLIFTED=1
    BUILD_DIR=build-0109 tools/boot_check.sh 60 --version 0109` reaches
    `SetPortSetting(port=0, setting=0x2)` (press mode) and the first `GetData` at about
    4.0 s, just before `RenderingThread` is created. `PAD_TRIGGERS` counts its `from`
    from the first GetData, though, so a 5 s start never meets a poll.
  - With `PAD_NO_HOST=1 PAD_TRACE=1 PAD_TRIGGERS=0,128,0,1` the game's own buffer shows
    the analog value:
    `[cellPad] trace port 0 @0FEFF360 len=24 btn=0200 L=(128,128) R=(128,128) L2=0 R2=128`.
    That is the R2 digital bit plus pressure word button[19] = 128, which the game
    scales by 1/255 to a half throttle. About 1.7 s later (~5.7 s) a second poll reads
    `R2=0`.
  - With the window at 15-16 s after the first poll (`PAD_TRIGGERS=0,200,15,16`) there
    is no trace line. The game stops polling once the main thread blocks in the
    loading stall (`STALLED since 21.6s | last open GUIDCACHE.XXX`, 8 flips), so in-game
    controls cannot be tested until that stall is fixed.
  - Keyboard path: a scratch harness (SDL `offscreen` driver, which gives the window
    keyboard focus) ran `input_kbm.cpp` and `input_config.cpp` with a fake
    `cellPad_set_host_input`. All 9 checks passed: registration before main, config
    file to env, env over file, lower-case keys ignored, nothing before SDL video,
    neutral with no key, Esc key-down dropped while Q passes, a wheel notch giving a
    70 ms stick press that then releases. A real key press cannot be injected
    headless (no xdotool/ydotool here), so held keys still need a manual check in a
    windowed run (`SARPBC_KBM_LOG=1`). boot_check runs with `PS3RECOMP_VK_WINDOW=0`,
    so SDL video is never started and the keyboard reports nothing there.
  - Rumble: `SetActDirect` goes to `SDL_GameControllerRumble` (patches T008-1/-2; the
    small motor is on/off at 0xFFFF, the large one 0-255 scaled). It is covered by the
    patch's test only. The game has not rumbled in a run yet because it does not reach
    gameplay.
- Status: T008 done for what the boot allows. Open: in-game check of the bindings and
  rumble once menus run; mouse camera; button prompts by host kind
  (`cellPad_host_kind`).

## SPU / SPURS

- **Status (2026-10-18):** 14 of 15 embedded images are lifted and registered
  (`build_spu_workloads.py --input --allow-partial` in `tools/relift.sh`). Image #7 (324 KB,
  PhysX Dynamics, an overlay image) lifts too once the T003 pipeline patch is in (see PhysX
  below). The Edge zlib task (image 1, fp
  `4100F6EDD2441719`) is dispatched, runs, and then idles in `WAIT_SIGNAL`, because Edge
  zlib requests are now serviced natively on the PPU (`src/overrides/edgezlib.cpp`).
- **PhysX "unlifted LS 0x20180" = an unseeded static constructor (T025, 2026-10-19).**
  01.09 boots logged `[spu] img=363824547 branched into unlifted LS 0x20180 (lr=0x20148) --
  ending the job` (image 7, `spu_5af85a31...`, SPU_DynamicsRelease.elf). Its `.ctors` at LS
  0x36E70 is `{-1, 0x20180, 0}`; crt0's loop at 0x20140 loads each entry and calls it with
  `bisl $r0` (the constructor itself is a bare `bi $r0`). Nothing branches to it by address
  and the list is shorter than the data fn-pointer-table scan's minimum run of 3, so
  `find_spu_functions.py` never seeded it. 9 of the 13 sectioned images had unseeded
  `.ctors`/`.dtors` entries (e.g. 0x31D8/0x31C8 in several PhysX images); the two
  section-stripped images (`d08b1ad8`, `e33837bb`) have empty lists (`-1, 0, -1, 0` at the
  start of their data segment). Patch `T025-spu-seed-ctors-dtors` seeds every
  `.ctors/.dtors/.init_array/.fini_array` word, and for stripped images finds lists by their
  `-1 ... 0` framing. A relift of 01.09 with it: 15/15 registered, complete, every ctor/dtor
  entry lifted (checked against functions.json). **Not yet verified at run time** (needs the
  shared 01.09 `spu_gen` relifted, or `-DSPU_DIR=<copy>`).
- **SPU speed baseline (T025, 01.09, before any change):** `SPURS_EF_STATS=1` flag
  `0x01372000` ~75 waits/s (mean 11 ms), `SPU_DMA_RANGE=58000000-58200000` PUT ~410 KB/s
  (27% of real time). `AUDIO_RATE=1` reports ~197.9 blocks/s with the dummy driver: that is
  the port's consumption, not the mixer's output, so use the two lines above to measure SPU speed.
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
