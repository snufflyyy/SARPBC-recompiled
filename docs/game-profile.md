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

| # | Offset | Size | Identified by strings |
|---|---|---|---|
| 0 | `0x19F0700` | 85,300 | unknown |
| 1 | `0x1A05480` | 37,708 | **Edge zlib** (package decompression) |
| 2, 6, 11 | `0x1A0F000`, `0x1A65780`, `0x1B21D00` | 10–39 KB | **PhysX** SPU tasks (SPURS queue) |
| 3–5, 8–10 | `0x1A11700`... | 42–163 KB | unknown, likely PhysX/engine tasks |
| 7 | `0x1A6F000` | 323,840 | uses `CellStackAllocator` (PhysX?) |
| 12–14 | `0x1CBC400`... | 2–11 KB | **MultiStream DSP**: `mstream_dsp_i3dl2`, `_filter`, `_para_eq` |

**`SPUJOBS.SPRX`** → `game/SPUJOBS.prx`: a PPU PRX (`e_type 0xFFA4`) with no SPU ELFs
inside; its strings are **Edge Geometry** errors (vertex/index decompression, blend
shapes, skinning). So it carries raw SPURS job images for Edge Geometry, run through
job chains. Capture them with `SPU_DUMP_MISS` or carve them from the PRX.

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
| SPU images registered | 14/15 | 12/15 |

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
