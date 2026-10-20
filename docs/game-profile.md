# Game profile — what is in the box

Everything here was read directly from the user's PKG on 2026-10-18 unless marked
*(unverified)*. Re-derive nothing below; extend it.

## Source files

`Supersonic Acrobatic Rocket-Powered Battle-Cars (USA)/`

| File | Size | What |
|---|---|---|
| `8332ldc...Mk.pkg` | 185,944,288 | Retail PSN package, finalized (AES-128-CTR, public PS3 GPKG key), 84 entries |
| `UP2002-NPUB30035_00-SARBATTLECARS001.rap` | 16 | License key for the NPDRM content (→ klicensee) |

The PKG opens with ps3recomp's `tools/pkg_extract.py` (no RAP needed for the package
layer). The SELF files inside are a second, NPDRM layer that **does** need the RAP — see
[pipeline.md](pipeline.md#2-decrypt-the-npdrm-selfs).

## PARAM.SFO

| Key | Value |
|---|---|
| TITLE | Supersonic Acrobatic Rocket-Powered Battle-Cars |
| TITLE_ID | NPUB30035 |
| APP_VER / VERSION | 01.02 / 01.02 |
| PS3_SYSTEM_VER | 02.4000 |
| CATEGORY | `HG` — HDD game (installs to `/dev_hdd0/game/NPUB30035/`) |
| RESOLUTION | `0x37` — 480, 576, 720 (+ 480/576 widescreen); **no 1080** |
| SOUND_FORMAT | `0x117` — LPCM 2.0 / 5.1 / 7.1 + Dolby Digital |
| BOOTABLE / ATTRIBUTE / PARENTAL_LEVEL | `1` / `0` / `3` |

## Package tree (sizes in bytes)

```
PS3LOGO.DAT 5120   PARAM.SFO 1040   ICON0.PNG   ICON1.PAM (animated icon)   PIC1.PNG
TROPDIR/NPWR00406_00/TROPHY.TRP          1,112,752   trophy set NPWR00406_00
USRDIR/EBOOT.BIN                        30,160,944   NPDRM SELF (PPU executable)
USRDIR/SARB/                                         UE3 "base dir" of the game
  BINARIES/PS3/BINK/BINKPS3_*.BIN        ~1 KB each  Bink RSX shaders (VS, YCrCb->RGB(A))
  BINARIES/PS3/SAVE/{ICON0,PIC1,BGPIC1}.PNG TEMPICON1.PAM   save-data icons
  BINARIES/PS3/SPU/SPUJOBS.SPRX             69,568   NPDRM SELF, SPU job code
  ENGINE/SPLASH/PS3/LOADSCREEN.{FPO,VPO}             compiled RSX fragment/vertex program
  ENGINE/SPLASH/PS3/SPLASH.BMP
  TAGAME/PS3TOC.TXT                           3,548  UE3 table of contents (size + path per file)
  TAGAME/CONFIG/BATTLEBALL/PS3/COOKED/COALESCED.INI  all .ini files, coalesced, plaintext
  TAGAME/LOCALIZATION/COALESCED.INT                  English (INT) strings, coalesced
  TAGAME/SPLASH/PS3/{LOADING,SPLASH}.BMP
  TAGAME/COOKEDPS3/                                  cooked UE3 packages (.XXX)
```

Cooked packages in `TAGAME/COOKEDPS3/` (largest first): `STARTUP_INT.XXX` 40.7 MB,
`TEXTURES.TFC` 26.5 MB (texture file cache), `MAINMENU.XXX` 17.9 MB, `TAGAME.XXX` 13.3 MB,
`MP_BOWLARENA` 8.6 MB, `MP_RINGARENA` 7.8 MB, `LOCALLOBBY` 5.3 MB, `QUICKMATCH` 4.9 MB,
`MP_SOCCARARENA` 4.5 MB, `PSYUI` 2.0 MB, `ENGINE` 1.4 MB, plus `CORE`, `ENTRY`, `IPDRV`,
`GUIDCACHE`, `GLOBALPERSISTENTCOOKERDATA.UPK`, `GLOBALSHADERCACHE-PS3.BIN`, `TASTATS`,
`ONLINESUBSYSTEMGAMESPY(_LOC_INT)`, `CARSELECTIONLOBBY0-3`, and 19 `PYRAMID_*` maps
(training/challenge levels: BallRain, GoalieDrill, QuickShot, ...).

Three arenas: **MP_SoccarArena** (Soccar), **MP_BowlArena**, **MP_RingArena**.

PS3TOC.TXT paths are relative to `SARB/Binaries` (`..\TAGame\CookedPS3\...`), mixed
case, Windows separators. The PKG stores upper-case names. The PS3 file system is
case-sensitive on host Linux, so **path case is a real risk** — see
[subsystems.md](subsystems.md#file-system).

## File format notes

| File | Header | Meaning |
|---|---|---|
| `*.XXX` | `9E 2A 83 C1`, ver `0x021B`, licensee `0x0001` | UE3 package, file version 539, big-endian, compressed chunks |
| `GLOBALSHADERCACHE-PS3.BIN` | `GSMB`, ver `0x021B` | UE3 global shader map (precompiled RSX programs) |
| `COALESCED.INI/.INT` | BE u32 count, then (name, contents) | plaintext, not encrypted |
| `EBOOT.BIN`, `SPUJOBS.SPRX` | `SCE\0`, key rev 1, `NPD\0` v1, license 2 (local) | NPDRM-encrypted SELF; decrypted copies in `game/` |

## Config highlights (from COALESCED.INI)

- `NativeResX=1280 NativeResY=720`, `UseVsync=true`, `bSmoothFrameRate=TRUE`,
  `MaxSmoothedFrameRate=60`, `ScreenPercentage=100`, `UpscaleScreenPercentage=true`.
- Audio device: `PS3Drv.PS3AudioDevice`; `MaxChannels=32`.
- Online: `DefaultOnlineSubsystemName=OnlineSubsystemGameSpy.OnlineSubsystemGameSpy`,
  `ChatServerAddress=peerchat.gamespy.com`, net driver `IpDrv.TcpNetDriver`.
  GameSpy shut down in 2014 — online play is dead without a replacement server.
- `bDisablePhysXHardwareSupport=True` (PhysX present; refers to the PC PPU card).
- Post-process: `FX_Game.Other.PostFX_Basic` with bloom + DOF.
- Config hierarchy: `PS3-TA*.ini` BasedOn `..\TAGame\Config\PS3\PS3*.ini`, plus `TAAI`,
  `TAVehicles`, `TAChallenges`, `TAGamespy`, `TAMaps`, `TAProfile`, `TAPsyUI`, ...

## Decrypted executable (`game/EBOOT.elf`, made by `tools/decrypt.sh` on 2026-10-18)

sha256 `8a76237bd58d53f62054d36bf0dcf5ce7cd4f72834591f4e595238b29daa16f1`, 30,158,208 bytes.
ELF64 big-endian PPC64, `ET_EXEC`, **stripped** (no symbols — names must come from
analysis, strings, or the Drakengard 3 port's UE3 knowledge).

| `ppu_loader.py` output | |
|---|---|
| Entry OPD | `0x1BE8EC0` → code `0x10230`, TOC `0x1C6EA28` |
| Module TOC (r2) | `0x1C9E6CC` |
| OPD region | `0x1BE8EB0`, size `0x7DB78`: 64,367 descriptors, **47,602 unique functions** |
| Segment 0 (RX) | vaddr `0x10000`, size `0x1B274C8` (27.2 MB code + rodata) |
| Segment 1 (RW) | vaddr `0x1B40000`, filesz `0x18FF00`, memsz `0x31F010` (bss `0x18F110`) |
| Imports | **274 across 20 libraries**, 257 named by the NID database, 17 unnamed |

Imports per library: sceNp 43, cellSysutil 33, cellSpurs 32, sysPrxForUser 26,
cellGcmSys 25, sys_net 22, sys_fs 20, cellMic 15, cellAudio 10, sys_io 8, cellNetCtl 8,
sceNpTrophy 7, cellMusicUtility 6, cellRtc 5, cellRec 5, cellVideoExportUtility 3,
cellSysmodule 2, cellOvis 2, cellVideoUpload 1, cellSync 1. Full list:
`analysis/imports_named.json` (regenerate with `gen_imports.py`).

Notable imports:
- **cellSpurs**: tasksets, tasks, job chains, event flags, **SPURS Queue and LFQueue**
  (`_cellSpursQueueInitialize`, `cellSpursQueuePopBody`, `_cellSpursLFQueuePushBody`),
  job guards. Drakengard 3 had to lift Sony's libsre for Queue/LFQueue — see
  [reference-ports.md](reference-ports.md).
- **sysPrxForUser**: `sys_prx_load_module`/`start_module` (loads `SPUJOBS.SPRX`),
  `sys_mmapper_*`, lwmutex/lwcond, `sys_spu_image_close`.
- **sys_io**: cellPad (incl. `cellPadSetActDirect` rumble, `cellPadGetInfo2`), cellKbRead,
  cellMouseGetDataList — keyboard and mouse are read.
- **sceNp**: `sceNpDrmIsAvailable` (license check), Manager (NP ID, ticket, status),
  Basic (friends/block list), Lookup, **Score** (leaderboards), **Signaling** (P2P).
- **cellMic** (voice chat), **cellRec + cellVideoUpload + cellVideoExportUtility**
  (recording/uploading replays), **cellMusicUtility** (custom soundtracks), **cellOvis**
  (overlay table init).
- No import of cellPngDec/cellJpgDec/cellFont/cellSaveData/cellGame: images, fonts and
  saves are handled by engine code (saves possibly via sys_fs directly — verify).

`triage_elf.py` also finds **MultiStream** (`cellMS*` — statically linked, not imported),
including `cellMSStreamGetMP3FrameInfo`. In Drakengard 3, MultiStream loaded an MP3
decoder from console firmware that a port has to replace — check whether we hit that.

## SPU code

**15 SPU ELFs embedded in the EBOOT** (`extract_spu_images.py` →
`analysis/spu_EBOOT_elf/`, 1.28 MB total):

Image numbers are the EBOOT order (the same in both versions). The table is for **01.09**
(`versions/0109/`; sha256 prefix, size, ELF EA = EBOOT file offset + `0x10000`). All 15 are
identified (T010, 2026-10-20; strings per image, the PhysX name table, and the first reference
to each ELF EA in the EBOOT's data). In 01.02 the PhysX images (2-11) are byte-identical; 0, 1
and 12-14 are different builds (lift prefixes `0e193327`, `3077b344`, `0a01540b`, `6417c94e`,
`7cc4abec`).

| # | 01.09 image, EA | Size | What it is | How it runs | Confidence |
|---|---|---|---|---|---|
| 0 | `e33837bb`, `0x10AF300` | 95,636 | **MultiStream mixer** (build path string `spu/msngSPURS_MP3`; MP3 decode, DSP slots) | SPURS taskset `0x01370680`, task 0 (T007). EA stored beside two float constants at `0x1261A50` and in a `{3,0,EA,0}` record at `0x1268AEC` | high |
| 1 | `d08b1ad8`, `0x10C6900` | 38,100 | **Edge zlib** inflate task (`edgezlib_inflate_task.cpp`) | Requests go through the SPURS LFQueue push, which `src/overrides/edgezlib.cpp` serves natively: this image is **never dispatched** at run time. EA referenced from a struct at `0x1239470` | high |
| 2 | `11d77ed9`, `0x10D0600` | 9,968 | PhysX `SPU_FluidSpatialHash.elf` | SPURS task (PhysX taskset; `CellSPURSSupport`, SPURS queue to the PPU) | high (name table) |
| 3 | `013103a1`, `0x10D2D00` | 138,888 | PhysX `SPU_FluidCollision.elf` | same | high |
| 4 | `4b403ab6`, `0x10F4C00` | 42,232 | PhysX `SPU_RaycastRelease.elf` | same | high |
| 5 | `2f214d8c`, `0x10FF100` | 162,872 | PhysX `SPU_HeightFieldRelease.elf` | same | high |
| 6 | `239e932f`, `0x1126D80` | 39,016 | PhysX `SPU_ClothRelease.elf` | same | high |
| 7 | `5af85a31`, `0x1130600` | 323,840 | PhysX **`SPU_DynamicsRelease.elf`**, entry `0x200F0`; two overlays at LS `0x3080` (`OverlaySmallIsland` code, LMA `0x40000`; `OverlayLargeIsland` zero scratch, LMA `0x5A480`) loaded via the cellOvis table, see [subsystems.md](subsystems.md#spu--spurs) | SPURS task on taskset `0x01335080`, 16 per frame; seen running | high |
| 8 | `906761dc`, `0x117F780` | 131,328 | PhysX `SPU_NarrowPhase3Release.elf` (sphere/capsule/box vs mesh and heightfield: `PxcContactCapsuleMesh`, `...SphereMesh`) | same | high |
| 9 | `034ddc73`, `0x119F900` | 135,488 | PhysX `SPU_NarrowPhase2Release.elf` (adds `PxcContactCapsuleConvex`, `SphereConvex`) | same | high |
| 10 | `0e1192e6`, `0x11C0A80` | 141,436 | PhysX `SPU_NarrowPhase1Release.elf` (convex/hull/box pairs: `ConvexConvex`, `HullHull`, `BoxConvex`, `PlaneConvex`) | same | high |
| 11 | `7bde2a3f`, `0x11E3300` | 20,304 | PhysX `SPU_IslandGenerationRelease.elf` | same; seen spinning at LS `0x68E0` (T030) | high |
| 12 | `615f0131` | 10,828 | MultiStream DSP plugin `mstream_dsp_i3dl2.pic` | Not a SPURS image: position-independent plugin the mixer copies into a heap block and runs at LS `0x37000` (overlay `spu_ovl_msdsp_37000`, `tools/make_spu_overlays.py`). Registered as a stand-alone image too; nothing is known to dispatch it (guess) | high |
| 13 | `16bab42d` | 1,932 | MultiStream DSP plugin `mstream_dsp_filter.pic` | same | high |
| 14 | `8bec3b25` | 2,332 | MultiStream DSP plugin `mstream_dsp_para_eq.pic` | same | high |

The PhysX table (`{name EA, ELF EA, overlay table EA}` x 10) is at `0x1261A90` in 01.09
(`0x1CCB8E0` in 01.02, see subsystems.md); the order is IslandGeneration, Dynamics,
NarrowPhase1, 2, 3, Cloth, HeightField, Raycast, FluidSpatialHash, FluidCollision. The six
PhysX images that were "unknown" here (3-5, 8-10) are therefore confirmed by name; the new
facts are the 01.09 addresses and the per-image string evidence above (PhysX 2.80 for PS3,
`PS3-PhysX_280_` build path; `SPUNAME` strings in the DSP plugins).

### SPU coverage audit (T010, 2026-10-20)

`--allow-partial` was needed because the lifter's functions do not cover every byte of an
image's executable range. `tools/spu_coverage.py` (read-only; `--version 0102` for the base
game, `-v` for every range, `--strict` to fail on a missed-function candidate) subtracts the
lifted functions from each image's executable ranges and classifies every uncovered range by
disassembly and by who references it. On 01.09 (15 images + the two SPUJOBS jobs): **512
uncovered ranges, 62,088 bytes**:

| Verdict | Ranges | Bytes | What |
|---|---|---|---|
| padding | 370 | 1,676 | `nop`/`lnop` alignment between functions |
| zero | 13 | 220 | zero words |
| string | 7 | 34,208 | assertion/printf strings (Edge zlib, MultiStream, PhysX Dynamics `.rodata` inside the overlay) |
| data | 55 | 16,232 | float tables, small-integer tables, switch jump tables (offsets decode as `stop N`), `lqr`-loaded constants, and the 16-byte image signature quad at the segment start (four `ila $r2,imm`-looking words at LS `0x3000`, `0x80` in the DSP plugins; never executed, the entry is `0x3050`/`0x3080`) |
| post-stop | 7 | 240 | `bi $lr` after a function that ends in `stop`: the compiler's epilogue after a noreturn call (a `hbr` hint names it) |
| code? (referenced) | 2 | 324 | see below |
| dead (unreferenced code) | 58 | 9,188 | whole functions nothing calls or points to |

Reading it: **no uncovered range is a missed function the lifted code reaches directly**
(the pipeline already refuses an image when a direct branch/call target has no function
entry). All string, table and padding bytes are literals as expected. Two classes need a
caveat:

- **Dead code (58 ranges, 14 in the Edge Geometry job).** Real, fully decodable functions
  (e.g. a 120-byte MFC DMA helper in Edge zlib at `0xAD40`, 760 bytes at `0x16DD0` in
  FluidCollision) that no `brsl`, branch, `ila`/`ilhu+iohl` constant, `lqr` or pointer word in
  the image refers to: unused library functions linked in with the PhysX/Edge code. They would
  matter only if the PPU passed their address in a task argument (not seen) or an indirect
  branch computed it. Not a lifter fault; list below if a run ever logs `branched into
  unlifted LS`.
- **Two real candidates (`code?`), both PhysX NarrowPhase**: `906761dc` function at LS
  `0x12E30` (260 B) and `034ddc73` function at LS `0x16130` (64 B). Each is referenced by one
  32-bit pointer word in `.rodata` (`0x21C78` and `0x22CD4`, alone in an otherwise zero
  table), i.e. a function pointer stored in data, which `find_spu_functions.py`'s pointer-table
  seeder does not pick up. If the game ever calls through that slot the runtime would hit an
  unlifted address (`SPU_INTERP_UNLIFTED` fallback or "ending the job"). Fix: pass them as
  extra function seeds (`build_spu_workloads.py` `--extra-funcs name=ADDR`, kept in
  `tools/relift.sh`), or teach the seeder to take single `.rodata` pointers that land on a
  decodable 16-byte aligned prologue. Both exist identically in 01.02. Not yet observed to be
  called.

Re-run the tool after every relift; it needs the `src/spu_gen` lift output but no build.

**`SPUJOBS.SPRX`** → `game/SPUJOBS.prx`: a PPU PRX (`e_type 0xFFA4`) with no SPU ELFs
inside; its strings are **Edge Geometry** errors (vertex/index decompression, blend
shapes, skinning). It is a **data-only module** that carries two raw SPURS job
binaries (read from the file 2026-10-18, both versions):

| | 01.02 (`game/SPUJOBS.prx`, 67,856 B) | 01.09 (`versions/0109/game/SPUJOBS.prx`, 51,344 B, sha256 `189316bc…`) |
|---|---|---|
| Segments | seg0 RX 0x0..0xFF00, seg1 RW 0xFF00..0xFF20 | seg0 RX 0x0..0xC000, seg1 RW 0xC000..0xC020 |
| Job A (Edge Geometry) | seg0+0x100, 0xFC00 bytes | seg0+0x100, 0xBD80 bytes |
| Job B (shader patching, see below) | seg0+0xFD80, 0x108 bytes | seg0+0xBE80, 0x108 bytes (different bytes) |
| Relocations | 16, all `R_PPC64_ADDR32` | same 16, same targets |

- Module name `SPUJobs`, version 1.1. **No imports.** Exports only the module-level
  `module_start` (NID `0xBC9A0086`, OPD at seg1+0), `module_stop` (`0xAB779874`, OPD
  seg1+8, `li r3,0; blr`) and `module_info` (`0xD7F43016`). TOC = seg1 + 0x8010.
- `module_start(args, argp)` is 12 instructions, identical in both versions: it
  loads TOC-0x8000..-0x7FF4 (seg1+0x10..0x1C) and stores them to `argp[0..3]` =
  `{job A EA, job A size, job B EA, job B size}`; returns 0. The job binaries are
  not touched by any relocation, so their bytes (and fingerprints) do not depend on
  where the module loads.
- Caller (01.02): `func_006E4450` (TOC `0x1C6EA28`) calls `sys_prx_load_module(path,
  0, 0)` (lr `0x6E4A88`) after `sceNpDrmIsAvailable`, then `sys_prx_start_module(id,
  4, argp=sp+0x98, modres=sp+0x70, 0, 0)` (lr `0x6E4B08`), and copies argp into
  the globals `0x01D32690` (A EA), `0x01D32694` (A size), `0x01D32698` (B EA),
  `0x01D3269C` (B size). It then calls `func_006DB6B8(0x01D32700)`, which creates the
  "ShaderPatching" job chain (its command list is at `0x01D32700`).
- Job B is what the ShaderPatching chain runs: `func_006DEBF8` / `006DECE0` /
  `006DEE10` / `006DEF28` read B's EA/size, build a job with `func_006DE6D8(ea,
  size)` and call `cellSpursRunJobChain`. Job A (EA/size) is read by
  `func_006DF040`. (From reading the lifted code; the chain has not run yet in a
  boot, so this is not observed at run time.)
- Both are raw job binaries entered at LS 0 (first word `ila`), lifted by
  `tools/lift_prx_jobs.py`; FNV-1a-64 fingerprints: 01.02 A `0xE13FC05B93FA6AF6`,
  B `0x6982B12EFDE17A51` (0x108 B) / `0xC5F68493430B2E71` (0x110 B, the size a job
  header names); 01.09 A `0x83BD7B3A22EDAF27`, B `0x9CA670E2D5FBFF30` /
  `0xCC5206038B0FC530`. How it loads at run time: [subsystems.md](subsystems.md#spu--spurs).

## Versions and updates (researched 2026-10-18)

| Version | Source | What | Status here |
|---|---|---|---|
| **01.02** | the user's PSN package (base install) | 30.2 MB EBOOT, 3 arenas, GameSpy online | **what is ported today** |
| 01.04 | community-archived patch (not on Sony's server any more) | base of the community online mod | not obtained |
| SARPBC Online Mod 1.15 | community patch by kuxir97 (distributed via the SARPBC+ Discord; documented at [eiddor/sarpbc-online](https://github.com/eiddor/sarpbc-online)) | online play through **RPCN** (open-source PSN replacement): "Play Online" → Unranked Match / Join A Friend; installed as 1.02 → 1.04 → 1.15 | not obtained; this is the multiplayer route the user chose |
| **01.09** | official title update, still on Sony's update server: `https://a0.ww.np.dl.playstation.net/tpl/np/NPUB30035/NPUB30035-ver.xml` | 205,355,568 bytes, needs FW 4.60; SHA-1 (file minus its last 32 bytes) `9cc78619...a7cb3c235`, verified. Downloaded to `updates/` (git-ignored) | downloaded, not ported |

What 01.09 changes (from its file table, 108 entries): a new **19.2 MB EBOOT** (a different
build: every address differs from 01.02), a new SPUJOBS.SPRX (53 KB), **three new arenas**
(`MP_COSMIC`, `MP_GALLEON`, `MP_STADIUM`), replays (`SAVE/REPLAY/*.PNG`), `DEMOSCREEN`,
and **GameSpy replaced** by `ONLINESUBSYSTEMPS3` + `PSYNET` (the Psyonix server list that
was shut down on 2023-01-24). An update installs over the base under the same
`/dev_hdd0/game/NPUB30035/`.

Known issues the community reports under RPCS3 with the online mod (worth checking in
our port): scoring on Galleon crashes ("fails to allocate memory"), saving replays crashes,
and the frame rate is uncapped in the engine.

### 01.09 at a glance (staged in `versions/0109/`, 2026-10-18)

| | 01.02 | 01.09 |
|---|---|---|
| EBOOT.elf sha256 | `8a76237b…` | `85d698f5…` |
| Code (exec segment) | 27.8 MB | 18.3 MB |
| OPD functions / lifted | 47,602 / 64,397 | 22,154 / 41,431 (13,601 split by prologue, 5,387 tail-entry wrappers) |
| Lifted source | 7.57M lines, 442 MB | 5.79M lines, 387 MB |
| Code end (`.lib.stub`) | `0x194FD80` | `0xF8F718` |
| Entry OPD / TOC | `0x1BE8EC0` / `0x1C6EA28` | `0x12018A8` → `0xADB68` / `0x123C6D0` |
| TOC-switch stub runs | 2 (4,242 stubs) | 0 |
| Imports | 274 / 20 libs, 17 unnamed | 288 / 21 libs, 20 unnamed |
| SPU images registered | 15/15 + 2 SPUJOBS jobs (patches 0006-0007) | 15/15 + 2 SPUJOBS jobs (12/15 before 0005) |

Import changes in 01.09: **+cellGame** (BootCheck, DataCheck, ContentPermit,
CreateGameData, GetParamString, GetSizeKB, ContentErrorDialog), **+cellPngDec** (7),
**+cellSaveData** via cellSysutil (FixedSave2, ListLoad2), **+cellVoice** (10, replacing
**cellMic**), +cellAudioOut device queries, more cellGcm flip/FIFO calls
(_cellGcmSetFlipCommand(WithWaitLabel), Get/ResetFlipStatus, SetDefaultFifoSize),
cellSpursInitializeWithAttribute, sys_ppu_thread_once, _sys_spu_printf_initialize/finalize,
sceNpBasicSetPresence / AddPlayersHistoryAsync, sceNpDrmExecuteGamePurchase. Removed:
cellMsgDialogProgressBarInc / Close (the call behind the 01.02 trophy race), cellHddGameCheck,
several cellAudio port calls, cellSyncLFQueueGetDirection.

SPU in 01.09: all PhysX images are byte-identical to 01.02 (image `5af85a31…` is still
refused for overlapping PT_LOADs). The MultiStream DSP images changed. Image 0
(`e33837bb…`, 95,636 B) and Edge zlib (`d08b1ad8…`, 38,100 B) changed and fail with
"unsupported instructions emitted by lifter" (T016). SPUJOBS.prx is a new 53 KB module
(`189316bc…`).

Why those two failed (T016, 2026-10-18): **no SPU opcode was missing.** Every one of the
213 (`d08b1ad8…`) and 473 (`e33837bb…`) unsupported entries is `.word`, i.e. .rodata lifted
as code. Both images are **section-stripped** (no section headers, one `R E` PT_LOAD
at `0x3000`: `0x3000-0xC350` and `0x3000-0x1A3F0`), so the pipeline treats the whole segment
as code, and the linker put .rodata after .text in it. `find_spu_functions.py`'s
`ila`-continuation and branch-target seeders took every string/table address loaded by
`ila` as a function start (printf/assert format strings, float tables, zlib tables).
Images that keep a section table get the same bogus seeds, but they are clipped to
`.text`, which is why the other 12 registered.

| Image | Data region (LS) | What is there | Bogus seeds |
|---|---|---|---|
| `d08b1ad8…` Edge zlib (fp `0x00E729804474449A`) | `0xB290-0xB8A0`, `0xC1B0-0xC20C` | "EDGE ZLIB ERROR: ...", "edgezlib_inflate", "1.2.3.0-PS3-SPU-...", zlib messages ("invalid distance too far back") and code tables | 36 |
| `e33837bb…` image 0 (fp `0xC1759183E2FF7448`) | `0x171D0-0x1A1CC` | **MultiStream** mixer strings ("Skipping DSP (slot %d)...", "MP3 Size to do...", "ERROR! Multistream...", "STARVED OF DATA"), float tables at `0x17700-0x19200` | 50 |

Image 0 is therefore MultiStream's main SPU mixer (MP3 decode and DSP slots); the strings
say so. The fix (patch `0005-spu-detector-rodata-seeds.patch`) keeps a derived seed only if it decodes, is not a
NUL-padded C string, and a straight-line walk from it reaches a branch/return/stop before
an undecodable word or the segment end. Result on 01.09: **14/15 registered**, the two
images lift with 0 unsupported (625 and 1,151 functions); the other 12 lift byte-identical
to before. Across both versions' 20 distinct images, no seed inside a real `.text` section
is dropped. A few table addresses that decode cleanly up to a `stop` (zlib tables at
`0xC0A0`, `0xC0E0`, `0xC240` in `d08b1ad8…`) are still lifted as tiny dead functions;
harmless.
