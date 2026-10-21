# HLE coverage — every firmware import vs. the HLE registry

Which of the EBOOT's firmware imports have an HLE handler, whether that handler does
real work, and which ones the boot actually calls. **Primary version: 01.09** (the
port's target since 2026-10-18, staged in `versions/0109/`); 01.02 is kept as a column.
Written by T004 on 2026-10-18 against ps3recomp `39a3629` + patch 0001 + the T004 patch.

Regenerate the generated block at the end of this file with:

```bash
# boot hit data: a headless run with the milestone log on (cheap, timing-neutral)
PS3RECOMP_VK_WINDOW=0 SDL_AUDIODRIVER=dummy PS3_MILESTONE_OUT=$PWD/analysis/milestone.txt \
  timeout -k 5 -s TERM 90 tools/run.sh > analysis/run.log 2>&1
tools/hle_coverage.py --check-names                     # re-verify the computed names
tools/hle_coverage.py --set 01.09 versions/0109/analysis/imports_named.json regen \
  --set 01.02 analysis/imports_named.json regen \
  --hits 01.09=analysis/milestone_0109.txt --hits 01.02=analysis/milestone.txt \
  --doc docs/hle-coverage.md
```

With no `--set`, the tool reads the NID tables the builds use (CMake generates
`<build>/ppu_hle_nids.cpp` with `gen_hle_nids.py --all` whenever a `libs/*.c` changes; `tools/relift.sh`
deletes any copy in `src/recomp/`). `regen` instead asks `gen_hle_nids.py --all` what the
current `external/ps3recomp` tree would register (use it to see a toolkit patch before the
build regenerates the table). `--format json` gives the same data as JSON.

## How an import gets resolved (what the table columns mean)

`ps3_hle_call(nid)` (`external/ps3recomp/runtime/ppu/ppu_hle.cpp`) tries, in order:

1. **Loaded PRX export** (`prx_resolve_export`) — only when a real Sony PRX is loaded
   (none in this port today). Shown as `via PRX` in the hit column.
2. **ctx** — handlers registered with `ps3_hle_register_ctx()`: they get the whole
   `ppu_context`. Registered by `runtime/ppu/ppu_sysprx.cpp` (sysPrxForUser core, the
   sys_net offline model, GCM init), `runtime/ppu/ppu_fs.cpp` (all cellFs), `spu_raw.c`,
   `lv2_register.c`, `sceNpScore.c`, `cellSaveData.c`, and our `src/overrides/*.cpp`
   (`_cellSpursLFQueuePushBody`). **First registration of a NID wins.**
3. **generic** — the generated table (`gen_hle_nids.py --all`): every non-static
   `cell*/sce*/sys*` function defined in `libs/**/*.c`, NID computed from its C name.
   The adapter passes r3..r10 raw, so a function only matches an import if the C name
   **is** the SDK name.
4. **missing** — nothing registered: the dispatcher calls `ps3_hle_unresolved()` (T020, patch
   0058): it prints `[hle] UNRESOLVED NID 0x... -> faking CELL_OK (... first call from lr=0x..,
   tid=N)` once per distinct NID (thread-safe, no cap below 512 distinct) and returns r3 = 0,
   leaving out-params untouched. `PS3_HLE_UNRESOLVED=fail` returns CELL_ERROR_ERROR
   (0x8001003F) instead, to find which unresolved import the title depends on.

`online` (with `--online`): sys_net handlers that only exist with `PS3_NET_ONLINE` set
(`libs/network/sysNet.c`, registered before the offline model, so they win).

**Class** is a heuristic over the handler's C body (`classify()` in the tool): count the
statements left after removing logging, `(void)` casts, guards and returns; a body that
just `return other(...)` is graded by `other`. `stub` = no effect beyond the return
value (the Return column shows it); `thin N` = 1–3 statements (usually one out-param or
flag); `impl N` = more. A stub is not automatically wrong (`cellPadClearBuf` has nothing
to clear), and `impl` is not proof of correctness. **Hit** is the milestone occurrence
bucket (`1`, `2-9`, ... `100k+`) from the run given with `--hits`.

## Results (2026-10-18)

| | 01.09 before T004 | 01.09 with T004 patch | 01.02 with T004 patch |
|---|---|---|---|
| Imports / libraries | 288 / 21 | 288 / 21 | 274 / 20 |
| Handler registered (ctx + generic) | 237 (53 + 184) | **252** (61 + 191) | 235 (61 + 174) |
| Missing (faked CELL_OK) | 51 | **36** | 39 |
| Unnamed by the toolkit DB → named by T004 | 20 → 0 | 20 → 0 | 17 → 0 |
| Distinct imports hit in a 90 s boot | 67 | 67 | 90 |
| …of which unresolved | 1 (`_sys_spu_printf_initialize`) | 0 once the table is regenerated | 4 |

01.09's 36 remaining gaps are all non-trivial or owned by other tasks (list below).
The generated block has the exact counts per class and library.

### Boot runs used for the hit column

- **01.09**: `versions/0109/build/sarpbc` (coordinator's build, before the T004 patch)
  with a scratch copy of `versions/0109/vfs`, 90 s, headless. It records **79 HLE first
  sightings and then stops making new calls** (frames keep flipping). The last new calls
  are `cellGameDataCheck`, `cellGameCreateGameData`, `cellFsMkdir`, `cellGameGetSizeKB`,
  `cellFsOpendir/Readdir/Closedir`. The one unresolved NID hit is `0x45FE2FCE`
  `_sys_spu_printf_initialize` (right after the game starts its own `_SPU_printf_server`
  thread); the T004 patch registers it.
- **01.02**: `build/sarpbc` in T004's worktree, 90 s, headless, 90 distinct imports. The
  unresolved hits are `sys_prx_load_module`/`sys_prx_start_module` (T002),
  `cellGameDataGetSizeKB` (`0xA9B0C1D9`, early, after `cellHddGameCheck`) and
  **`cellGameDataExitBroken` (`0x9949BF82`)**, which is the *last* new HLE call of the
  boot: `lr=0x00683F2C`, args `r3=0 r4=0x01D932D8 r5=1 r6=7`, after `STARTUP_INT.XXX`
  is opened (`PS3_HLE_ARGS=9949BF82 PS3_FSLOG=1`). On firmware this shows "game data
  is corrupted" and terminates the game; faked as CELL_OK the game keeps flipping. So
  the 01.02 stall is the engine deciding its data is broken (a guess at the cause: a
  UE3 I/O failure path), not a missing handler. Moot if the port stays on 01.09.

### 01.09 boot blocker found on the way (not an HLE gap)

01.09 imports **cellGame** (01.02 did not). `cellGameBootCheck` answers
`type=1 (DISC), titleId='BLES00000'` — the toolkit's defaults — because `src/main.cpp`
never calls `cellGame_init_from_paramsfo()` / `cellGame_set_title_id()`, and
`libs/system/cellGame.c` has no way to set the game type (`s_game_type` is fixed to
`CELL_GAME_GAMETYPE_DISC`; PARAM.SFO `CATEGORY=HG` should mean HDD). The game then
builds its paths under `/dev_hdd0/game/BLES00000/USRDIR/UNREALENGINE3/`, finds no
`PS3TOC.TXT` or `COALESCED.INI` there, and goes quiet. Evidence: `analysis/run_0109.log`
lines `[cellGame] BootCheck: type=1, titleId='BLES00000'`,
`[cellGame] ContentPermit() -> /dev_bdvd/PS3_GAME`,
`[fs] stat '.../BLES00000/USRDIR/UNREALENGINE3/TAGAME/CONFIG/BATTLEBALL/PS3/COOKED/COALESCED.INI' -> ENOENT`.
This is the first thing to fix for 01.09 (suggested task below).

## The NIDs the database could not name

Every name below was found by computing `compute_nid(name)` (SHA-1 of name + the 16-byte
suffix, first 4 bytes little-endian; `external/ps3recomp/tools/nid_database.py`) over
candidate SDK names and matching the import's NID exactly. They are stored in
`KNOWN_NAMES` in `tools/hle_coverage.py`, which re-checks all of them on every run
(`--check-names`: "all 29 entries match"). None is a guess.

| Library | NID | Name | 01.02 | 01.09 |
|---|---|---|---|---|
| cellSysutil | `A9B0C1D9` | cellGameDataGetSizeKB | ✓ | — (01.09 uses cellGame) |
| cellSysutil | `9949BF82` | cellGameDataExitBroken | ✓ | — |
| sys_net | `3F09E20A` | socketselect | ✓ | ✓ |
| sys_net | `F7AC8941` | gethostbyaddr | ✓ | ✓ |
| cellMic | `05709BBF` | cellMicOpenEx | ✓ | — (01.09 uses cellVoice) |
| cellMic | `65336418` | cellMicRemoveNotifyEventQueue | ✓ | — |
| cellMic | `6BC46AAB` | cellMicReset | ✓ | — |
| cellMic | `7903400E` | cellMicSetNotifyEventQueue | ✓ | — |
| cellMic | `B2C16321` | cellMicSetDeviceAttr | ✓ | — |
| cellVoice | `2A01013E` | cellVoiceCreateNotifyEventQueue | — | ✓ |
| cellVoice | `35D84910` | cellVoiceSetNotifyEventQueue | — | ✓ |
| cellVoice | `94D51F92` | cellVoiceStartEx | — | ✓ |
| cellVoice | `B1A2C38F` | cellVoiceInitEx | — | ✓ |
| sceNp | `7DEB244C` | sceNpScoreCensorComment | ✓ | — |
| sceNp | `7E2FEF28` | sceNpManagerRequestTicket | ✓ | ✓ |
| sceNp | `166DCC11` | sceNpLookupNpId | — | ✓ |
| sceNp | `32C78A6A` | sceNpBasicGetFriendPresenceByIndex | — | ✓ |
| sceNp | `BE81C71C` | sceNpBasicSetPresenceDetails | — | ✓ |
| cellVideoExportUtility | `2F457571` | cellVideoExportInitialize2 | ✓ | ✓ |
| cellVideoExportUtility | `81296524` | cellVideoExportFromFile | ✓ | ✓ |
| cellVideoExportUtility | `C15BE817` | cellVideoExportFinalize | ✓ | ✓ |
| cellVideoUpload | `122E0D0F` | cellVideoUploadInitialize | ✓ | ✓ |
| cellMusicUtility | `8793EF97` | cellMusicGetSelectionContext2 | ✓ | — |
| cellMusicUtility | `AD04CDDD` | cellMusicSelectContents2 | ✓ | ✓ |
| cellMusicUtility | `0B461648` | cellMusicGetSelectionContext | — | ✓ |
| cellMusicUtility | `5BFF31BF` | cellMusicSetSelectionContext | — | ✓ |
| cellMusicUtility | `72EC14B5` | cellMusicInitialize | — | ✓ |
| cellMusicUtility | `A0661626` | cellMusicSetPlaybackCommand | — | ✓ |
| cellMusicUtility | `E74CE7BD` | cellMusicSetVolume | — | ✓ |

Two toolkit registrations use a non-SDK label for an SDK NID (harmless, dispatch is by
NID): `0x3F09E20A` is registered as "sys_net_bnet_select" and the libnet offline model
names `bind/sendto/socket/...` "netBind/netSendTo/netSocket". They are not added to the
toolkit's NID database: `nid_from_protos.json` only takes names validated against a
debug build's symbol table, and these were validated by hash only.

Also found: upstream's `libs/misc/cellVideoExport.c` (`cellVideoExportInit/End/Start`),
`cellVideoUpload.c` (`cellVideoUploadInit/Term/Start`) and `cellGameRecording.c` use
invented names that match no SDK NID, so they can never resolve an import; there is no
cellRec or cellMusic (utility) module at all.

## What the T004 patch adds (`patches/ps3recomp/0002-hle-trivial-missing-imports.patch`)

Only handlers whose correct behaviour is obvious (offline / "nothing to do"):

| Import(s) | Handler |
|---|---|
| sys_net `listen`, `shutdown` | 0 (offline model, like `bind`) |
| sys_net `accept` | -1, errno EWOULDBLOCK (like `recv`) |
| sys_net `connect` | -1, errno ENETUNREACH (51) — was faked as "connected" |
| sys_net `send` | -1, errno ENOTCONN (57) |
| sys_net `getsockopt` | 0 and zeroes `*optval` (SO_ERROR = 0) |
| sys_net `getsockname` | 0 and an unbound AF_INET `0.0.0.0:0` |
| sys_net `inet_addr` | parses a dotted quad, INADDR_NONE otherwise |
| sys_net `gethostbyaddr` | NULL (DNS down, like `gethostbyname`) |
| sys_io `cellKbRead` | `cellKbGetData` (same contract) — faked OK left the buffer untouched |
| cellSysutil `cellOskDialogSetDeviceMask`, `SetKeyLayoutOption` | CELL_OK, like `SetLayoutMode` |
| cellSpurs `cellSpursQueueDetachLv2EventQueue`, `cellSpursLFQueueDetachLv2EventQueue` | CELL_OK (the attach stubs bind nothing) |
| sysPrxForUser `_sys_spu_printf_initialize/_finalize` | CELL_OK (01.09 calls the init at boot) |

The sys_net handlers are ctx registrations and take effect on the next build. The
others are generic: they need a regenerated `ppu_hle_nids.cpp` (at the time a manual
`gen_hle_nids.py --all`; the build now does it by itself) — the table goes from 1,195 to 1,202 handlers. Verified:
the patch applies from the pin with `tools/apply_patches.sh`, builds, a scratch
`gen_hle_nids.py --all` registers all 7 new generic NIDs, and a 90 s 01.02 boot calls
exactly the same 90 imports as before the patch (no behaviour change on that path).

## Gaps that remain, ranked by how likely they are to block boot (01.09)

1. **cellGame title/type configuration** (above) — not a missing NID, but it is what
   stops 01.09 today.
2. **`sys_prx_load_module` / `sys_prx_start_module` / `sys_prx_register_library`** —
   T002. 01.02 calls the first two at boot (SPUJOBS.SPRX, Edge Geometry).
3. **`cellOvisInitializeOverlayTable`** — T003 (PhysX overlay table).
4. **`cellSpursQueuePopBody`** (`0x91066667`) — SPURS Queue consumer on the PPU side;
   faked OK means "popped" with an unwritten buffer. Drakengard 3 needed real libsre
   Queue semantics. Likely to bite as soon as PhysX or another queue user runs.
5. **`cellMsgDialogOpenErrorCode`** — error dialogs; faked OK never fires the close
   callback, so a game waiting for the user to dismiss an error waits forever. Only on
   error paths, but those are exactly what a port hits.
6. **`_cellGcmFunc15`** (`0x3A33C1FD`) — semantics unknown here (RPCS3 treats it as a
   no-op, unconfirmed); faked OK is probably fine. Not hit yet.
7. **cellMusicUtility** (7 in 01.09, no module upstream) — custom soundtracks. If the
   game initializes it at boot it will wait for an `INITIALIZE_RESULT` callback that
   never comes. Not hit in either run so far.
8. **cellVoice** `InitEx`, `StartEx`, `CreateNotifyEventQueue`, `SetNotifyEventQueue`
   — voice chat; `CreateNotifyEventQueue` faked OK leaves the queue id unwritten.
9. **sceNp** `ManagerRequestTicket`, `ManagerGetTicket`, `LookupNpId(+Async)`,
   `SignalingAddExtendedHandler`, `SignalingTerminateConnection`,
   `BasicGetFriendPresenceByIndex`, `BasicSetPresenceDetails`,
   `DrmExecuteGamePurchase` — online paths; `sceNpManagerGetStatus` reports OFFLINE, so
   these should stay unused offline.
10. **cellRec** (5), **cellVideoExportUtility** (3), **cellVideoUpload** (1) — replay
    recording/export/upload, user-triggered only.

Stubs worth knowing about (registered, but no effect): `sys_lwcond_signal*` are no-ops
and `sys_lwcond_wait` is poll-style (drops the mutex for ~1 ms and returns), so
waits always "wake"; `cellFsUnlink/Rmdir/Chmod/Utime` and `cellSaveDataDelete2` return
CELL_OK without touching anything (deletes silently fail); `sys_mmapper_map/unmap/free`
are no-ops by design (flat VM).

## Generated tables

Columns: **Handler** = registered name when it differs from the import name (`=` when
the same); **Kind** = ctx / generic / missing; **Class** with its statement count;
**Return** = what a stub returns; **Defined in** = file under `external/ps3recomp/`;
**Hit** = boot occurrence bucket; later columns = the same NID in the other versions.
`01.09` = with the T004 patch (`regen`); `01.09-built` = the table and toolkit the
coordinator's 01.09 build used. The 01.09 hit data comes from that pre-patch build, so
`_sys_spu_printf_initialize` still shows `UNRESOLVED` in the Hit column. Produced with:

```bash
tools/hle_coverage.py --set 01.09 versions/0109/analysis/imports_named.json regen \
  --set 01.09-built versions/0109/analysis/imports_named.json versions/0109/src/recomp/ppu_hle_nids.cpp \
  --set 01.02 analysis/imports_named.json regen --tree 01.09-built=<pin+0001 ps3recomp tree> \
  --hits 01.09=analysis/milestone_0109.txt --hits 01.09-built=analysis/milestone_0109.txt \
  --hits 01.02=analysis/milestone1.txt --doc docs/hle-coverage.md
```

<!-- BEGIN GENERATED: tools/hle_coverage.py -->
| Version | Imports | Libraries | ctx | generic | missing | of which stub | thin | impl | unnamed by DB | hit at boot | hit & unresolved |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01.09 | 288 | 21 | 61 | 191 | 36 | 50 | 82 | 120 | 20 | 67 | 1 |
| 01.09-built | 288 | 21 | 53 | 184 | 51 | 42 | 78 | 117 | 20 | 67 | 1 |
| 01.02 | 274 | 20 | 61 | 174 | 39 | 47 | 82 | 106 | 17 | 90 | 4 |

### Per library (01.09)

| Library | Imports | ctx | generic | missing | stub | thin | impl | hit |
|---|---|---|---|---|---|---|---|---|
| sceNp | 42 | 0 | 33 | 9 | 3 | 21 | 9 | 0 |
| cellSpurs | 36 | 1 | 34 | 1 | 6 | 8 | 21 | 12 |
| cellGcmSys | 31 | 1 | 29 | 1 | 5 | 13 | 12 | 18 |
| cellSysutil | 31 | 0 | 30 | 1 | 10 | 3 | 17 | 8 |
| sysPrxForUser | 30 | 22 | 5 | 3 | 11 | 5 | 11 | 13 |
| sys_net | 20 | 20 | 0 | 0 | 8 | 9 | 3 | 0 |
| sys_fs | 20 | 17 | 3 | 0 | 4 | 3 | 13 | 8 |
| cellVoice | 10 | 0 | 6 | 4 | 2 | 3 | 1 | 0 |
| sys_io | 8 | 0 | 8 | 0 | 1 | 1 | 6 | 1 |
| cellNetCtl | 8 | 0 | 8 | 0 | 0 | 5 | 3 | 0 |
| sceNpTrophy | 8 | 0 | 8 | 0 | 0 | 3 | 5 | 0 |
| cellMusicUtility | 7 | 0 | 0 | 7 | 0 | 0 | 0 | 0 |
| cellGame | 7 | 0 | 7 | 0 | 0 | 1 | 6 | 6 |
| cellPngDec | 7 | 0 | 7 | 0 | 0 | 1 | 6 | 0 |
| cellAudio | 5 | 0 | 5 | 0 | 0 | 1 | 4 | 0 |
| cellRtc | 5 | 0 | 5 | 0 | 0 | 2 | 3 | 0 |
| cellRec | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| cellVideoExportUtility | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| cellSysmodule | 2 | 0 | 2 | 0 | 0 | 2 | 0 | 1 |
| cellOvis | 2 | 0 | 1 | 1 | 0 | 1 | 0 | 0 |
| cellVideoUpload | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |

### Full table (01.09)

| Library | NID | Name | Handler | Kind | Class | Return | Defined in | Hit | 01.09-built | 01.02 |
|---|---|---|---|---|---|---|---|---|---|---|
| sys_net | `6005CDE1` | _sys_net_errno_loc | = | ctx | thin 2 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sys_net | `C94F6939` | accept | = | ctx | thin 2 |  | runtime/ppu/ppu_sysprx.cpp |  | missing | ctx |
| sys_net | `B0A59804` | bind | netBind | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sys_net | `64F66D35` | connect | = | ctx | thin 1 |  | runtime/ppu/ppu_sysprx.cpp |  | missing | ctx |
| sys_net | `F7AC8941` | gethostbyaddr ¹ | = | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | missing | ctx |
| sys_net | `71F4C717` | gethostbyname | netGetHostByName | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sys_net | `13EFE7F5` | getsockname | = | ctx | impl 6 |  | runtime/ppu/ppu_sysprx.cpp |  | missing | ctx |
| sys_net | `5A045BD1` | getsockopt | = | ctx | thin 3 |  | runtime/ppu/ppu_sysprx.cpp |  | missing | ctx |
| sys_net | `DABBC2C0` | inet_addr | = | ctx | impl 15 |  | runtime/ppu/ppu_sysprx.cpp |  | missing | ctx |
| sys_net | `28E208BB` | listen | = | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | missing | ctx |
| sys_net | `FBA04F37` | recv | sys_net_bnet_recv | ctx | thin 2 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sys_net | `1F953B9F` | recvfrom | sys_net_bnet_recvfrom | ctx | thin 2 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sys_net | `DC751B40` | send | = | ctx | thin 1 |  | runtime/ppu/ppu_sysprx.cpp |  | missing | ctx |
| sys_net | `9647570B` | sendto | netSendTo | ctx | thin 1 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sys_net | `88F03575` | setsockopt | netSetSockOpt | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sys_net | `9C056962` | socket | netSocket | ctx | thin 1 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sys_net | `6DB6E8CD` | socketclose | netClose | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sys_net | `3F09E20A` | socketselect ¹ | sys_net_bnet_select | ctx | impl 13 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sys_net | `B68D5625` | sys_net_finalize_network | netFinalizeNetwork | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sys_net | `139A9E9B` | sys_net_initialize_network_ex | netInitializeNetworkEx | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx / 1 |
| sys_io | `FF0A21B7` | cellKbRead | = | generic | impl 23 |  | libs/input/cellKb.c |  | missing | generic |
| sys_io | `6BD131F0` | cellMouseGetDataList | = | generic | impl 19 |  | libs/input/cellMouse.c |  | generic | generic |
| sys_io | `0D5F2C14` | cellPadClearBuf | = | generic | stub | `CELL_OK` | libs/input/cellPad.c |  | generic | generic |
| sys_io | `8B72CDA1` | cellPadGetData | = | generic | impl 205 |  | libs/input/cellPad.c |  | generic | generic / 1 |
| sys_io | `A703A51D` | cellPadGetInfo2 | = | generic | impl 19 |  | libs/input/cellPad.c |  | generic | generic / 2-9 |
| sys_io | `1CF98800` | cellPadInit | = | generic | impl 6 |  | libs/input/cellPad.c | 1 | generic / 1 | generic / 1 |
| sys_io | `F65544EE` | cellPadSetActDirect | = | generic | impl 9 |  | libs/input/cellPad.c |  | generic | generic |
| sys_io | `578E3C98` | cellPadSetPortSetting | = | generic | thin 1 |  | libs/input/cellPad.c |  | generic | generic / 1 |
| sys_fs | `99406D0B` | cellFsChmod | = | ctx | stub | `CELL_OK` | runtime/ppu/ppu_fs.cpp |  | ctx | ctx |
| sys_fs | `2CB51F0D` | cellFsClose | = | ctx | impl 8 |  | runtime/ppu/ppu_fs.cpp | 2-9 | ctx / 2-9 | ctx / 10-99 |
| sys_fs | `FF42DCC3` | cellFsClosedir | = | ctx | thin 3 |  | runtime/ppu/ppu_fs.cpp | 1 | ctx / 1 | ctx / 10-99 |
| sys_fs | `EF3EFA34` | cellFsFstat | = | ctx | impl 17 |  | runtime/ppu/ppu_fs.cpp |  | ctx | ctx / 10-99 |
| sys_fs | `967A162B` | cellFsFsync | = | ctx | thin 1 |  | runtime/ppu/ppu_fs.cpp |  | ctx | ctx |
| sys_fs | `0E2939E5` | cellFsFtruncate | = | generic | impl 5 |  | libs/filesystem/cellFs.c |  | generic | generic |
| sys_fs | `AA3B4BCD` | cellFsGetFreeSize | = | ctx | thin 3 |  | runtime/ppu/ppu_fs.cpp | 1 | ctx / 1 | ctx / 1 |
| sys_fs | `A397D042` | cellFsLseek | = | ctx | impl 12 |  | runtime/ppu/ppu_fs.cpp |  | ctx | ctx / 100-999 |
| sys_fs | `BA901FE6` | cellFsMkdir | = | ctx | impl 5 |  | runtime/ppu/ppu_fs.cpp | 2-9 | ctx / 2-9 | ctx |
| sys_fs | `718BF5F8` | cellFsOpen | = | ctx | impl 35 |  | runtime/ppu/ppu_fs.cpp | 2-9 | ctx / 2-9 | ctx / 10-99 |
| sys_fs | `3F61245C` | cellFsOpendir | = | ctx | impl 12 |  | runtime/ppu/ppu_fs.cpp | 2-9 | ctx / 2-9 | ctx / 10-99 |
| sys_fs | `4D5FF8E2` | cellFsRead | = | ctx | impl 52 |  | runtime/ppu/ppu_fs.cpp |  | ctx | ctx / 100-999 |
| sys_fs | `5C74903D` | cellFsReaddir | = | ctx | impl 18 |  | runtime/ppu/ppu_fs.cpp | 2-9 | ctx / 2-9 | ctx / 100-999 |
| sys_fs | `F12EECC8` | cellFsRename | = | generic | impl 6 |  | libs/filesystem/cellFs.c |  | generic | generic |
| sys_fs | `2796FDF3` | cellFsRmdir | = | ctx | stub | `CELL_OK` | runtime/ppu/ppu_fs.cpp |  | ctx | ctx |
| sys_fs | `7DE6DCED` | cellFsStat | = | ctx | impl 12 |  | runtime/ppu/ppu_fs.cpp | 10-99 | ctx / 10-99 | ctx / 2-9 |
| sys_fs | `C9DC3AC5` | cellFsTruncate | = | generic | impl 10 |  | libs/filesystem/cellFs.c |  | generic | generic |
| sys_fs | `7F4677A8` | cellFsUnlink | = | ctx | stub | `CELL_OK` | runtime/ppu/ppu_fs.cpp |  | ctx | ctx |
| sys_fs | `BEF554A4` | cellFsUtime | = | ctx | stub | `CELL_OK` | runtime/ppu/ppu_fs.cpp |  | ctx | ctx |
| sys_fs | `ECDCF2AB` | cellFsWrite | = | ctx | impl 26 |  | runtime/ppu/ppu_fs.cpp |  | ctx | ctx |
| cellGcmSys | `3A33C1FD` | _cellGcmFunc15 |  | missing | missing |  |  |  | missing | missing |
| cellGcmSys | `15BAE46B` | _cellGcmInitBody | = | ctx | impl 5 |  | runtime/ppu/ppu_sysprx.cpp | 1 | ctx / 1 | ctx / 1 |
| cellGcmSys | `21397818` | _cellGcmSetFlipCommand | = | generic | thin 1 |  | libs/video/cellGcmSys.c |  | generic | not imported |
| cellGcmSys | `D8F88E1A` | _cellGcmSetFlipCommandWithWaitLabel | = | generic | thin 1 |  | libs/video/cellGcmSys.c |  | generic | not imported |
| cellGcmSys | `21AC3697` | cellGcmAddressToOffset | = | generic | impl 29 |  | libs/video/cellGcmSys.c | 1k-9k | generic / 1k-9k | generic / 1k-9k |
| cellGcmSys | `4524CCCD` | cellGcmBindTile | = | generic | thin 1 |  | libs/video/cellGcmSys.c | 2-9 | generic / 2-9 | generic / 10-99 |
| cellGcmSys | `9DC04436` | cellGcmBindZcull | = | generic | thin 1 |  | libs/video/cellGcmSys.c |  | generic | generic / 2-9 |
| cellGcmSys | `E315A0B2` | cellGcmGetConfiguration | = | generic | impl 7 |  | libs/video/cellGcmSys.c | 1 | generic / 1 | generic / 1 |
| cellGcmSys | `A547ADDE` | cellGcmGetControlRegister | = | generic | stub | `(CellGcmControl*)(uintptr_t)GCM_CONTROL_GUEST_ADDR` | libs/video/cellGcmSys.c | 1k-9k | generic / 1k-9k | generic / 1k-9k |
| cellGcmSys | `5E2EE0F0` | cellGcmGetDefaultCommandWordSize | = | generic | stub | `0x400` | libs/video/cellGcmSys.c |  | generic | not imported |
| cellGcmSys | `8CDF8C70` | cellGcmGetDefaultSegmentWordSize | = | generic | stub | `0x100` | libs/video/cellGcmSys.c |  | generic | not imported |
| cellGcmSys | `72A577CE` | cellGcmGetFlipStatus | = | generic | thin 1 |  | libs/video/cellGcmSys.c |  | generic | not imported |
| cellGcmSys | `F80196C1` | cellGcmGetLabelAddress | = | generic | stub | `(u32*)(uintptr_t)(GCM_LABEL_GUEST_BASE + (u32)index * GCM_LABEL_STRIDE)` | libs/video/cellGcmSys.c | 2-9 | generic / 2-9 | generic / 2-9 |
| cellGcmSys | `055BD74D` | cellGcmGetTiledPitchSize | = | generic | impl 6 |  | libs/video/cellGcmSys.c | 2-9 | generic / 2-9 | generic / 10-99 |
| cellGcmSys | `5A41C10F` | cellGcmGetTimeStamp | = | generic | thin 1 |  | libs/video/cellGcmSys.c | 1k-9k | generic / 1k-9k | generic / 1k-9k |
| cellGcmSys | `A114EC67` | cellGcmMapMainMemory | = | generic | impl 10 |  | libs/video/cellGcmSys.c | 1 | generic / 1 | generic / 1 |
| cellGcmSys | `B2E761D4` | cellGcmResetFlipStatus | = | generic | thin 2 |  | libs/video/cellGcmSys.c |  | generic | not imported |
| cellGcmSys | `9BA451E4` | cellGcmSetDefaultFifoSize | = | generic | thin 1 |  | libs/video/cellGcmSys.c |  | generic | not imported |
| cellGcmSys | `A53D12AE` | cellGcmSetDisplayBuffer | = | generic | impl 7 |  | libs/video/cellGcmSys.c | 2-9 | generic / 2-9 | generic / 2-9 |
| cellGcmSys | `A41EF7E8` | cellGcmSetFlipHandler | = | generic | impl 5 |  | libs/video/cellGcmSys.c | 1 | generic / 1 | generic / 1 |
| cellGcmSys | `ACEE8542` | cellGcmSetFlipImmediate | = | generic | impl 26 |  | libs/video/cellGcmSys.c | 1k-9k | generic / 1k-9k | generic / 1k-9k |
| cellGcmSys | `4AE8D215` | cellGcmSetFlipMode | = | generic | thin 1 |  | libs/video/cellGcmSys.c | 1 | generic / 1 | generic / 1 |
| cellGcmSys | `D01B570D` | cellGcmSetGraphicsHandler | = | generic | thin 1 |  | libs/video/cellGcmSys.c | 1 | generic / 1 | generic / 1 |
| cellGcmSys | `0B4B62D5` | cellGcmSetPrepareFlip | = | generic | impl 4 |  | libs/video/cellGcmSys.c | 1k-9k | generic / 1k-9k | generic / 1k-9k |
| cellGcmSys | `BD100DBC` | cellGcmSetTileInfo | = | generic | impl 9 |  | libs/video/cellGcmSys.c | 2-9 | generic / 2-9 | generic / 10-99 |
| cellGcmSys | `06EDEA9E` | cellGcmSetUserHandler | = | generic | thin 3 |  | libs/video/cellGcmSys.c | 1 | generic / 1 | generic / 1 |
| cellGcmSys | `A91B0402` | cellGcmSetVBlankHandler | = | generic | impl 5 |  | libs/video/cellGcmSys.c | 1 | generic / 1 | generic / 1 |
| cellGcmSys | `25B40AB4` | cellGcmSortRemapEaIoAddress | = | generic | stub |  | libs/video/cellGcmSys.c |  | generic | generic |
| cellGcmSys | `D9B7653E` | cellGcmUnbindTile | = | generic | thin 1 |  | libs/video/cellGcmSys.c |  | generic | generic |
| cellGcmSys | `A75640E8` | cellGcmUnbindZcull | = | generic | thin 1 |  | libs/video/cellGcmSys.c |  | generic | generic |
| cellGcmSys | `DB23E867` | cellGcmUnmapIoAddress | = | generic | impl 4 |  | libs/video/cellGcmSys.c |  | generic | generic |
| cellAudio | `74A66AF0` | cellAudioGetPortConfig | = | generic | impl 10 |  | libs/audio/cellAudio.c |  | generic | generic |
| cellAudio | `0B168F92` | cellAudioInit | = | generic | impl 16 |  | libs/audio/cellAudio.c |  | generic | generic |
| cellAudio | `CD7BC431` | cellAudioPortOpen | = | generic | impl 34 |  | libs/audio/cellAudio.c |  | generic | generic |
| cellAudio | `89BE28F2` | cellAudioPortStart | = | generic | thin 3 |  | libs/audio/cellAudio.c |  | generic | generic |
| cellAudio | `CA5AC370` | cellAudioQuit | = | generic | impl 10 |  | libs/audio/cellAudio.c |  | generic | generic |
| cellSysutil | `4692AB35` | cellAudioOutConfigure | = | generic | stub | `0` | libs/misc/cellAvconfExt.c |  | generic | generic |
| cellSysutil | `ED5D96AF` | cellAudioOutGetConfiguration | = | generic | impl 4 |  | libs/misc/cellAvconfExt.c |  | generic | not imported |
| cellSysutil | `7663E368` | cellAudioOutGetDeviceInfo | = | generic | impl 14 |  | libs/misc/cellAvconfExt.c |  | generic | not imported |
| cellSysutil | `E5E2B09D` | cellAudioOutGetNumberOfDevice | = | generic | stub | `1` | libs/misc/cellAvconfExt.c |  | generic | not imported |
| cellSysutil | `C01B4E7C` | cellAudioOutGetSoundAvailability | = | generic | stub | `0` | libs/misc/cellAvconfExt.c |  | generic | generic |
| cellSysutil | `F4E3CAA0` | cellAudioOutGetState | = | generic | impl 11 |  | libs/misc/cellAvconfExt.c |  | generic | generic |
| cellSysutil | `62B0F803` | cellMsgDialogAbort | = | generic | impl 4 |  | libs/system/cellMsgDialog.c |  | generic | generic |
| cellSysutil | `7603D3DB` | cellMsgDialogOpen2 | = | generic | impl 25 |  | libs/system/cellMsgDialog.c |  | generic | generic / 1 |
| cellSysutil | `3E22CB4B` | cellMsgDialogOpenErrorCode |  | missing | missing |  |  |  | missing | missing |
| cellSysutil | `B6D84526` | cellOskDialogAbort | = | generic | thin 1 |  | libs/misc/cellOskDialog.c |  | generic | generic |
| cellSysutil | `7FCFC915` | cellOskDialogLoadAsync | = | generic | impl 18 |  | libs/misc/cellOskDialog.c |  | generic | generic |
| cellSysutil | `D3790A86` | cellOskDialogSetDeviceMask | = | generic | stub | `CELL_OK` | libs/misc/cellOskDialog.c |  | missing | generic |
| cellSysutil | `C427890C` | cellOskDialogSetInitialKeyLayout | = | generic | stub | `CELL_OK` | libs/misc/cellOskDialog.c |  | generic | generic |
| cellSysutil | `B53C54FA` | cellOskDialogSetKeyLayoutOption | = | generic | stub | `CELL_OK` | libs/misc/cellOskDialog.c |  | missing | generic |
| cellSysutil | `F0EC3CCC` | cellOskDialogSetLayoutMode | = | generic | stub | `CELL_OK` | libs/misc/cellOskDialog.c |  | generic | generic |
| cellSysutil | `3D1E1931` | cellOskDialogUnloadAsync | = | generic | impl 8 |  | libs/misc/cellOskDialog.c |  | generic | generic |
| cellSysutil | `FBD5C856` | cellSaveDataAutoLoad2 | = | generic | impl 5 |  | libs/system/cellSaveData.c |  | generic | generic |
| cellSysutil | `8B7ED64B` | cellSaveDataAutoSave2 | = | generic | thin 1 |  | libs/system/cellSaveData.c |  | generic | generic |
| cellSysutil | `EDADD797` | cellSaveDataDelete2 | = | generic | stub | `CELL_OK` | libs/system/cellSaveData.c |  | generic | generic |
| cellSysutil | `2AAE9EF5` | cellSaveDataFixedSave2 | = | generic | impl 44 |  | libs/system/cellSaveData.c |  | generic | not imported |
| cellSysutil | `1DFBFDD6` | cellSaveDataListLoad2 | = | generic | impl 20 |  | libs/system/cellSaveData.c |  | generic | not imported |
| cellSysutil | `189A74DA` | cellSysutilCheckCallback | = | generic | impl 12 |  | libs/system/cellSysutil.c | 1k-9k | generic / 1k-9k | generic / 1k-9k |
| cellSysutil | `40E895D3` | cellSysutilGetSystemParamInt | = | generic | impl 32 |  | libs/system/cellSysutil.c | 2-9 | generic / 2-9 | generic / 2-9 |
| cellSysutil | `938013A0` | cellSysutilGetSystemParamString | = | generic | impl 20 |  | libs/system/cellSysutil.c |  | generic | generic |
| cellSysutil | `9D98AFA0` | cellSysutilRegisterCallback | = | generic | impl 8 |  | libs/system/cellSysutil.c | 1 | generic / 1 | generic / 1 |
| cellSysutil | `02FF3C1B` | cellSysutilUnregisterCallback | = | generic | thin 3 |  | libs/system/cellSysutil.c |  | generic | generic |
| cellSysutil | `0BAE8772` | cellVideoOutConfigure | = | generic | impl 9 |  | libs/video/cellVideoOut.c | 1 | generic / 1 | generic / 1 |
| cellSysutil | `1E930EEF` | cellVideoOutGetDeviceInfo | = | generic | impl 21 |  | libs/video/cellVideoOut.c | 1 | generic / 1 | generic / 1 |
| cellSysutil | `75BBB672` | cellVideoOutGetNumberOfDevice | = | generic | stub | `0` | libs/video/cellVideoOut.c | 1 | generic / 1 | generic / 1 |
| cellSysutil | `E558748D` | cellVideoOutGetResolution | = | generic | impl 5 |  | libs/video/cellVideoOut.c | 1 | generic / 1 | generic / 1 |
| cellSysutil | `A322DB75` | cellVideoOutGetResolutionAvailability | = | generic | stub | `(videoOut == CELL_VIDEO_OUT_PRIMARY) ? 1 : 0` | libs/video/cellVideoOut.c | 1 | generic / 1 | generic / 1 |
| cellNetCtl | `0CE13C6B` | cellNetCtlAddHandler | = | generic | impl 7 |  | libs/network/cellNetCtl.c |  | generic | generic / 1 |
| cellNetCtl | `1E585B5D` | cellNetCtlGetInfo | = | generic | impl 42 |  | libs/network/cellNetCtl.c |  | generic | generic |
| cellNetCtl | `3A12865F` | cellNetCtlGetNatInfo | = | generic | impl 6 |  | libs/network/cellNetCtl.c |  | generic | generic |
| cellNetCtl | `8B3EBA69` | cellNetCtlGetState | = | generic | thin 3 |  | libs/network/cellNetCtl.c |  | generic | generic / 1 |
| cellNetCtl | `BD5A59FC` | cellNetCtlInit | = | generic | thin 2 |  | libs/network/cellNetCtl.c |  | generic | generic / 1 |
| cellNetCtl | `04459230` | cellNetCtlNetStartDialogLoadAsync | = | generic | thin 2 |  | libs/network/cellNetCtl.c |  | generic | generic |
| cellNetCtl | `0F1F13D3` | cellNetCtlNetStartDialogUnloadAsync | = | generic | thin 3 |  | libs/network/cellNetCtl.c |  | generic | generic |
| cellNetCtl | `105EE2CB` | cellNetCtlTerm | = | generic | thin 2 |  | libs/network/cellNetCtl.c |  | generic | generic |
| cellSpurs | `95180230` | _cellSpursAttributeInitialize | = | generic | impl 6 |  | libs/spurs/cellSpurs.c | 2-9 | generic / 2-9 | not imported |
| cellSpurs | `5EF96465` | _cellSpursEventFlagInitialize | = | generic | impl 12 |  | libs/spurs/cellSpurs.c | 1 | generic / 1 | generic / 1 |
| cellSpurs | `3548F483` | _cellSpursJobChainAttributeInitialize | = | generic | impl 15 |  | libs/spurs/cellSpurs.c |  | generic | generic / 1 |
| cellSpurs | `011EE38B` | _cellSpursLFQueueInitialize | = | generic | impl 10 |  | libs/spurs/cellSpurs.c | 1 | generic / 1 | generic / 1 |
| cellSpurs | `8A85674D` | _cellSpursLFQueuePushBody | = | ctx | impl 25 |  | src/overrides/edgezlib.cpp |  | ctx | ctx / 1k-9k |
| cellSpurs | `082BFB09` | _cellSpursQueueInitialize | = | generic | impl 10 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `E0A6DBE4` | _cellSpursSendSignal | = | generic | thin 2 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `16394A4E` | _cellSpursTasksetAttributeInitialize | = | generic | impl 4 |  | libs/spurs/cellSpurs.c | 1 | generic / 1 | generic / 1 |
| cellSpurs | `B9BC6207` | cellSpursAttachLv2EventQueue | = | generic | impl 23 |  | libs/spurs/cellSpurs.c |  | generic | generic / 2-9 |
| cellSpurs | `07529113` | cellSpursAttributeSetNamePrefix | = | generic | impl 6 |  | libs/spurs/cellSpurs.c | 2-9 | generic / 2-9 | not imported |
| cellSpurs | `A839A4D9` | cellSpursAttributeSetSpuThreadGroupType | = | generic | stub | `CELL_OK` | libs/spurs/cellSpurs.c | 1 | generic / 1 | not imported |
| cellSpurs | `303C19CD` | cellSpursCreateJobChainWithAttribute | = | generic | impl 8 |  | libs/spurs/cellSpurs.c |  | generic | generic / 1 |
| cellSpurs | `BEB600AC` | cellSpursCreateTask | = | generic | impl 54 |  | libs/spurs/cellSpurs.c | 1 | generic / 1 | generic / 1 |
| cellSpurs | `52CC6C82` | cellSpursCreateTaskset | = | generic | impl 9 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `C10931CB` | cellSpursCreateTasksetWithAttribute | = | generic | impl 4 |  | libs/spurs/cellSpurs.c | 1 | generic / 1 | generic / 1 |
| cellSpurs | `4E66D483` | cellSpursDetachLv2EventQueue | = | generic | thin 3 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `87630976` | cellSpursEventFlagAttachLv2EventQueue | = | generic | thin 1 |  | libs/spurs/cellSpurs.c | 1 | generic / 1 | generic / 1 |
| cellSpurs | `22AAB31D` | cellSpursEventFlagDetachLv2EventQueue | = | generic | thin 1 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `373523D4` | cellSpursEventFlagWait | = | generic | impl 28 |  | libs/spurs/cellSpurs.c |  | generic | generic / 1k-9k |
| cellSpurs | `CA4C4600` | cellSpursFinalize | = | generic | impl 10 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `ACFC8DBC` | cellSpursInitialize | = | generic | impl 27 |  | libs/spurs/cellSpurs.c |  | generic | generic / 2-9 |
| cellSpurs | `AA6269A8` | cellSpursInitializeWithAttribute | = | generic | thin 2 |  | libs/spurs/cellSpurs.c | 2-9 | generic / 2-9 | not imported |
| cellSpurs | `9FEF70C2` | cellSpursJobChainAttributeSetName | = | generic | thin 1 |  | libs/spurs/cellSpurs.c |  | generic | generic / 1 |
| cellSpurs | `68AAEBA9` | cellSpursJobGuardInitialize | = | generic | impl 12 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `D5D0B256` | cellSpursJobGuardNotify | = | generic | impl 6 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `A7C066DE` | cellSpursJoinJobChain | = | generic | impl 7 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `9F72ADD3` | cellSpursJoinTaskset | = | generic | thin 1 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `1656D49F` | cellSpursLFQueueAttachLv2EventQueue | = | generic | stub | `CELL_OK` | libs/spurs/cellSpurs.c | 1 | generic / 1 | generic / 1 |
| cellSpurs | `73E06F91` | cellSpursLFQueueDetachLv2EventQueue | = | generic | stub | `CELL_OK` | libs/spurs/cellSpurs.c |  | missing | generic |
| cellSpurs | `E5443BE7` | cellSpursQueueAttachLv2EventQueue | = | generic | stub | `CELL_OK` | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `039D70B7` | cellSpursQueueDetachLv2EventQueue | = | generic | stub | `CELL_OK` | libs/spurs/cellSpurs.c |  | missing | generic |
| cellSpurs | `91066667` | cellSpursQueuePopBody |  | missing | missing |  |  |  | missing | missing |
| cellSpurs | `F31731BB` | cellSpursRunJobChain | = | generic | impl 12 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `738E40E6` | cellSpursShutdownJobChain | = | generic | impl 5 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `A789E631` | cellSpursShutdownTaskset | = | generic | thin 1 |  | libs/spurs/cellSpurs.c |  | generic | generic |
| cellSpurs | `652B70E2` | cellSpursTasksetAttributeSetName | = | generic | stub | `CELL_OK` | libs/spurs/cellSpurs.c | 1 | generic / 1 | generic / 1 |
| cellSysmodule | `32267A31` | cellSysmoduleLoadModule | = | generic | thin 2 |  | libs/system/cellSysmodule.c | 10-99 | generic / 10-99 | generic / 10-99 |
| cellSysmodule | `112A5EE9` | cellSysmoduleUnloadModule | = | generic | thin 2 |  | libs/system/cellSysmodule.c |  | generic | generic / 1 |
| cellRtc | `2CCE9CF5` | cellRtcGetCurrentClockLocalTime | = | generic | impl 9 |  | libs/system/cellRtc.c |  | generic | generic |
| cellRtc | `C2D8CF95` | cellRtcGetDayOfWeek | = | generic | impl 4 |  | libs/system/cellRtc.c |  | generic | generic |
| cellRtc | `C7BDB7EB` | cellRtcGetTick | = | generic | impl 6 |  | libs/system/cellRtc.c |  | generic | generic |
| cellRtc | `CB90C761` | cellRtcGetTime_t | = | generic | thin 3 |  | libs/system/cellRtc.c |  | generic | generic |
| cellRtc | `BB543189` | cellRtcSetTime_t | = | generic | thin 1 |  | libs/system/cellRtc.c |  | generic | generic |
| sceNp | `BCDBB2AB` | sceNpBasicAddPlayersHistoryAsync | = | generic | thin 1 |  | libs/network/sceNpBasic.c |  | generic | not imported |
| sceNp | `04372385` | sceNpBasicGetFriendListEntry | = | generic | thin 1 |  | libs/network/sceNpBasic.c |  | generic | generic |
| sceNp | `AFEF640D` | sceNpBasicGetFriendListEntryCount | = | generic | thin 1 |  | libs/network/sceNpBasic.c |  | generic | generic |
| sceNp | `32C78A6A` | sceNpBasicGetFriendPresenceByIndex ¹ |  | missing | missing |  |  |  | missing | not imported |
| sceNp | `4026EAC5` | sceNpBasicRegisterContextSensitiveHandler | = | generic | stub | `CELL_OK` | libs/network/sceNpBasic.c |  | generic | not imported |
| sceNp | `3F0808AA` | sceNpBasicSetPresence | = | generic | thin 3 |  | libs/network/sceNpBasic.c |  | generic | not imported |
| sceNp | `BE81C71C` | sceNpBasicSetPresenceDetails ¹ |  | missing | missing |  |  |  | missing | not imported |
| sceNp | `ACB9EE8E` | sceNpBasicUnregisterHandler | = | generic | impl 4 |  | libs/network/sceNpBasic.c |  | generic | generic |
| sceNp | `F283C143` | sceNpDrmExecuteGamePurchase |  | missing | missing |  |  |  | missing | not imported |
| sceNp | `AD218FAF` | sceNpDrmIsAvailable | = | generic | thin 3 |  | libs/network/sceNp.c |  | generic | generic / 1 |
| sceNp | `BD28FDBF` | sceNpInit | = | generic | thin 1 |  | libs/network/sceNp.c |  | generic | generic / 1 |
| sceNp | `CE81C7F0` | sceNpLookupCreateTitleCtx | = | generic | impl 4 |  | libs/network/sceNpLookup.c |  | generic | generic |
| sceNp | `EA2E9FFC` | sceNpLookupCreateTransactionCtx | = | generic | impl 4 |  | libs/network/sceNpLookup.c |  | generic | generic |
| sceNp | `FB87CF5E` | sceNpLookupDestroyTransactionCtx | = | generic | thin 1 |  | libs/network/sceNpLookup.c |  | generic | generic |
| sceNp | `5F2D9257` | sceNpLookupInit | = | generic | thin 1 |  | libs/network/sceNpLookup.c |  | generic | generic |
| sceNp | `166DCC11` | sceNpLookupNpId ¹ |  | missing | missing |  |  |  | missing | not imported |
| sceNp | `D12E40AE` | sceNpLookupNpIdAsync |  | missing | missing |  |  |  | missing | missing |
| sceNp | `7508112E` | sceNpLookupPollAsync | = | generic | thin 2 |  | libs/network/sceNpLookup.c |  | generic | generic |
| sceNp | `EB7A3D84` | sceNpManagerGetChatRestrictionFlag | = | generic | thin 1 |  | libs/network/sceNp.c |  | generic | generic |
| sceNp | `6EE62ED2` | sceNpManagerGetContentRatingFlag | = | generic | thin 2 |  | libs/network/sceNp.c |  | generic | generic |
| sceNp | `FE37A7F4` | sceNpManagerGetNpId | = | generic | thin 2 |  | libs/network/sceNp.c |  | generic | generic |
| sceNp | `BE07C708` | sceNpManagerGetOnlineId | = | generic | impl 4 |  | libs/network/sceNp.c |  | generic | generic |
| sceNp | `F42C0DF8` | sceNpManagerGetOnlineName | = | generic | thin 3 |  | libs/network/sceNp.c |  | generic | generic |
| sceNp | `A7BFF757` | sceNpManagerGetStatus | = | generic | impl 4 |  | libs/network/sceNp.c |  | generic | generic |
| sceNp | `0968AA36` | sceNpManagerGetTicket |  | missing | missing |  |  |  | missing | missing |
| sceNp | `E7DCD3B4` | sceNpManagerRegisterCallback | = | generic | impl 6 |  | libs/network/sceNp.c |  | generic | generic |
| sceNp | `7E2FEF28` | sceNpManagerRequestTicket ¹ |  | missing | missing |  |  |  | missing | missing |
| sceNp | `B9F93BBB` | sceNpScoreCreateTitleCtx | = | generic | impl 10 |  | libs/network/sceNpScore.c |  | generic | generic |
| sceNp | `259113B8` | sceNpScoreDestroyTitleCtx | = | generic | thin 1 |  | libs/network/sceNpScore.c |  | generic | generic |
| sceNp | `C5F4CF82` | sceNpScoreDestroyTransactionCtx | = | generic | thin 2 |  | libs/network/sceNpScore.c |  | generic | generic |
| sceNp | `32CF311F` | sceNpScoreInit | = | generic | thin 1 |  | libs/network/sceNp.c |  | generic | generic |
| sceNp | `9851F805` | sceNpScoreTerm | = | generic | thin 1 |  | libs/network/sceNp.c |  | generic | generic |
| sceNp | `60897C38` | sceNpSignalingActivateConnection | = | generic | stub | `(s32)SCE_NP_SIGNALING_ERROR_NOT_CONNECTED` | libs/network/sceNpSignaling.c |  | generic | generic |
| sceNp | `50B86D94` | sceNpSignalingAddExtendedHandler |  | missing | missing |  |  |  | missing | missing |
| sceNp | `6356082E` | sceNpSignalingCreateCtx | = | generic | impl 8 |  | libs/network/sceNpSignaling.c |  | generic | generic |
| sceNp | `FD0EB5AE` | sceNpSignalingDeactivateConnection | = | generic | stub | `CELL_OK` | libs/network/sceNpSignaling.c |  | generic | generic |
| sceNp | `A8CF8451` | sceNpSignalingDestroyCtx | = | generic | thin 1 |  | libs/network/sceNpSignaling.c |  | generic | generic |
| sceNp | `155DE760` | sceNpSignalingGetConnectionInfo | = | generic | impl 5 |  | libs/network/sceNpSignaling.c |  | generic | generic |
| sceNp | `9AD7FBD1` | sceNpSignalingGetLocalNetInfo | = | generic | thin 2 |  | libs/network/sceNpSignaling.c |  | generic | generic |
| sceNp | `95C7BBA3` | sceNpSignalingTerminateConnection |  | missing | missing |  |  |  | missing | missing |
| sceNp | `4885AA18` | sceNpTerm | = | generic | thin 1 |  | libs/network/sceNp.c |  | generic | generic / 1 |
| sceNp | `D208F91D` | sceNpUtilCmpNpId | = | generic | thin 1 |  | libs/network/sceNpUtil.c |  | generic | generic |
| cellRec | `4AC76585` | cellRecClose |  | missing | missing |  |  |  | missing | missing |
| cellRec | `39651E01` | cellRecOpen |  | missing | missing |  |  |  | missing | missing |
| cellRec | `DBF22BD1` | cellRecQueryMemSize |  | missing | missing |  |  |  | missing | missing |
| cellRec | `964CD1B8` | cellRecStart |  | missing | missing |  |  |  | missing | missing |
| cellRec | `5B45439D` | cellRecStop |  | missing | missing |  |  |  | missing | missing |
| cellVideoExportUtility | `C15BE817` | cellVideoExportFinalize ¹ |  | missing | missing |  |  |  | missing | missing |
| cellVideoExportUtility | `81296524` | cellVideoExportFromFile ¹ |  | missing | missing |  |  |  | missing | missing |
| cellVideoExportUtility | `2F457571` | cellVideoExportInitialize2 ¹ |  | missing | missing |  |  |  | missing | missing |
| cellVideoUpload | `122E0D0F` | cellVideoUploadInitialize ¹ |  | missing | missing |  |  |  | missing | missing |
| cellMusicUtility | `0B461648` | cellMusicGetSelectionContext ¹ |  | missing | missing |  |  |  | missing | not imported |
| cellMusicUtility | `72EC14B5` | cellMusicInitialize ¹ |  | missing | missing |  |  |  | missing | not imported |
| cellMusicUtility | `AD04CDDD` | cellMusicSelectContents2 ¹ |  | missing | missing |  |  |  | missing | missing |
| cellMusicUtility | `A0661626` | cellMusicSetPlaybackCommand ¹ |  | missing | missing |  |  |  | missing | not imported |
| cellMusicUtility | `98947A6E` | cellMusicSetPlaybackCommand2 |  | missing | missing |  |  |  | missing | missing |
| cellMusicUtility | `5BFF31BF` | cellMusicSetSelectionContext ¹ |  | missing | missing |  |  |  | missing | not imported |
| cellMusicUtility | `E74CE7BD` | cellMusicSetVolume ¹ |  | missing | missing |  |  |  | missing | not imported |
| cellGame | `F52639EA` | cellGameBootCheck | = | generic | impl 26 |  | libs/system/cellGame.c | 1 | generic / 1 | not imported |
| cellGame | `B0A1F8C6` | cellGameContentErrorDialog | = | generic | impl 18 |  | libs/system/cellGame.c |  | generic | not imported |
| cellGame | `70ACEC67` | cellGameContentPermit | = | generic | impl 12 |  | libs/system/cellGame.c | 2-9 | generic / 2-9 | not imported |
| cellGame | `42A2E133` | cellGameCreateGameData | = | generic | impl 11 |  | libs/system/cellGame.c | 1 | generic / 1 | not imported |
| cellGame | `DB9819F3` | cellGameDataCheck | = | generic | impl 12 |  | libs/system/cellGame.c | 1 | generic / 1 | not imported |
| cellGame | `3A5D726A` | cellGameGetParamString | = | generic | impl 18 |  | libs/system/cellGame.c | 1 | generic / 1 | not imported |
| cellGame | `EF9D42D5` | cellGameGetSizeKB | = | generic | thin 2 |  | libs/system/cellGame.c | 1 | generic / 1 | not imported |
| sceNpTrophy | `E3BF9A28` | sceNpTrophyCreateContext | = | generic | impl 9 |  | libs/network/sceNpTrophy.c |  | generic | generic / 1 |
| sceNpTrophy | `1C25470D` | sceNpTrophyCreateHandle | = | generic | impl 5 |  | libs/network/sceNpTrophy.c |  | generic | generic / 1 |
| sceNpTrophy | `3741ECC7` | sceNpTrophyDestroyContext | = | generic | thin 2 |  | libs/network/sceNpTrophy.c |  | generic | generic |
| sceNpTrophy | `623CD2DC` | sceNpTrophyDestroyHandle | = | generic | thin 1 |  | libs/network/sceNpTrophy.c |  | generic | generic |
| sceNpTrophy | `39567781` | sceNpTrophyInit | = | generic | thin 3 |  | libs/network/sceNpTrophy.c |  | generic | generic / 1 |
| sceNpTrophy | `1197B52C` | sceNpTrophyRegisterContext | = | generic | impl 4 |  | libs/network/sceNpTrophy.c |  | generic | generic / 1 |
| sceNpTrophy | `A7FABF4D` | sceNpTrophyTerm | = | generic | impl 7 |  | libs/network/sceNpTrophy.c |  | generic | not imported |
| sceNpTrophy | `8CEEDD21` | sceNpTrophyUnlockTrophy | = | generic | impl 5 |  | libs/network/sceNpTrophy.c |  | generic | generic |
| cellPngDec | `5B3D1FF1` | cellPngDecClose | = | generic | thin 2 |  | libs/codec/cellPngDec.c |  | generic | not imported |
| cellPngDec | `157D30C5` | cellPngDecCreate | = | generic | impl 6 |  | libs/codec/cellPngDec.c |  | generic | not imported |
| cellPngDec | `2310F155` | cellPngDecDecodeData | = | generic | impl 37 |  | libs/codec/cellPngDec.c |  | generic | not imported |
| cellPngDec | `820DAE1A` | cellPngDecDestroy | = | generic | impl 6 |  | libs/codec/cellPngDec.c |  | generic | not imported |
| cellPngDec | `D2BC5BFD` | cellPngDecOpen | = | generic | impl 18 |  | libs/codec/cellPngDec.c |  | generic | not imported |
| cellPngDec | `9CCDCC95` | cellPngDecReadHeader | = | generic | impl 60 |  | libs/codec/cellPngDec.c |  | generic | not imported |
| cellPngDec | `E97C9BD4` | cellPngDecSetParameter | = | generic | impl 32 |  | libs/codec/cellPngDec.c |  | generic | not imported |
| cellVoice | `AE6A21D5` | cellVoiceConnectIPortToOPort | = | generic | stub | `CELL_OK` | libs/audio/cellVoice.c |  | generic | not imported |
| cellVoice | `2A01013E` | cellVoiceCreateNotifyEventQueue ¹ |  | missing | missing |  |  |  | missing | not imported |
| cellVoice | `2DE54871` | cellVoiceCreatePort | = | generic | impl 6 |  | libs/audio/cellVoice.c |  | generic | not imported |
| cellVoice | `54AC3519` | cellVoiceGetPortInfo | = | generic | thin 1 |  | libs/audio/cellVoice.c |  | generic | not imported |
| cellVoice | `B1A2C38F` | cellVoiceInitEx ¹ |  | missing | missing |  |  |  | missing | not imported |
| cellVoice | `36472C57` | cellVoiceReadFromOPort | = | generic | thin 1 |  | libs/audio/cellVoice.c |  | generic | not imported |
| cellVoice | `35D84910` | cellVoiceSetNotifyEventQueue ¹ |  | missing | missing |  |  |  | missing | not imported |
| cellVoice | `D5AE37D8` | cellVoiceSetVolume | = | generic | stub | `CELL_OK` | libs/audio/cellVoice.c |  | generic | not imported |
| cellVoice | `94D51F92` | cellVoiceStartEx ¹ |  | missing | missing |  |  |  | missing | not imported |
| cellVoice | `3DAD26E7` | cellVoiceWriteToIPort | = | generic | thin 1 |  | libs/audio/cellVoice.c |  | generic | not imported |
| cellOvis | `82F294B2` | cellOvisGetOverlayTableSize | = | generic | thin 1 |  | libs/misc/cellOvis.c |  | generic | generic / 1 |
| cellOvis | `A876C911` | cellOvisInitializeOverlayTable |  | missing | missing |  |  |  | missing | missing |
| sysPrxForUser | `96328741` | _sys_process_at_Exitspawn | = | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp | 1 | ctx / 1 | ctx / 1 |
| sysPrxForUser | `2C847572` | _sys_process_atexitspawn | = | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp | 1 | ctx / 1 | ctx / 1 |
| sysPrxForUser | `DD3B27AC` | _sys_spu_printf_finalize | = | generic | stub | `CELL_OK` | libs/system/sysPrxForUser.c |  | missing | not imported |
| sysPrxForUser | `45FE2FCE` | _sys_spu_printf_initialize | = | generic | stub | `CELL_OK` | libs/system/sysPrxForUser.c | UNRESOLVED (1) | missing / UNRESOLVED (1) | not imported |
| sysPrxForUser | `744680A2` | sys_initialize_tls | = | ctx | impl 9 |  | runtime/ppu/ppu_sysprx.cpp | 1 | ctx / 1 | ctx / 1 |
| sysPrxForUser | `DA0EB71A` | sys_lwcond_create | = | ctx | impl 5 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sysPrxForUser | `1C9A942C` | sys_lwcond_destroy | = | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sysPrxForUser | `EF87A695` | sys_lwcond_signal | = | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sysPrxForUser | `2A6D9D51` | sys_lwcond_wait | = | ctx | impl 12 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sysPrxForUser | `2F85C0EF` | sys_lwmutex_create | = | ctx | impl 13 |  | runtime/ppu/ppu_sysprx.cpp | 10-99 | ctx / 10-99 | ctx / 10-99 |
| sysPrxForUser | `C3476D0C` | sys_lwmutex_destroy | = | ctx | thin 2 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sysPrxForUser | `1573DC3F` | sys_lwmutex_lock | = | ctx | impl 29 |  | runtime/ppu/ppu_sysprx.cpp | 100k+ | ctx / 100k+ | ctx / 100k+ |
| sysPrxForUser | `AEB78725` | sys_lwmutex_trylock | = | ctx | impl 15 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sysPrxForUser | `1BC200F4` | sys_lwmutex_unlock | = | ctx | impl 25 |  | runtime/ppu/ppu_sysprx.cpp | 100k+ | ctx / 100k+ | ctx / 100k+ |
| sysPrxForUser | `B257540B` | sys_mmapper_allocate_memory | = | ctx | impl 5 |  | runtime/ppu/ppu_sysprx.cpp | 10-99 | ctx / 10-99 | ctx / 10-99 |
| sysPrxForUser | `409AD939` | sys_mmapper_free_memory | = | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sysPrxForUser | `DC578057` | sys_mmapper_map_memory | = | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp | 10-99 | ctx / 10-99 | ctx / 10-99 |
| sysPrxForUser | `4643BA6E` | sys_mmapper_unmap_memory | = | ctx | stub | `0` | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx |
| sysPrxForUser | `24A1EA07` | sys_ppu_thread_create | = | ctx | thin 1 |  | runtime/ppu/ppu_sysprx.cpp | 2-9 | ctx / 2-9 | ctx / 2-9 |
| sysPrxForUser | `AFF080A4` | sys_ppu_thread_exit | = | ctx | thin 1 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | ctx / 2-9 |
| sysPrxForUser | `350D454E` | sys_ppu_thread_get_id | = | ctx | thin 2 |  | runtime/ppu/ppu_sysprx.cpp | 2-9 | ctx / 2-9 | ctx / 10-99 |
| sysPrxForUser | `A3E3BE68` | sys_ppu_thread_once | = | generic | impl 5 |  | libs/system/sysPrxForUser.c | 1 | generic / 1 | not imported |
| sysPrxForUser | `E6F2C1E7` | sys_process_exit | = | generic | impl 14 |  | libs/system/sysPrxForUser.c |  | generic | generic |
| sysPrxForUser | `4F7172C9` | sys_process_is_stack | = | ctx | thin 2 |  | runtime/ppu/ppu_sysprx.cpp |  | ctx | not imported |
| sysPrxForUser | `A2C7BA64` | sys_prx_exitspawn_with_level | = | generic | stub | `CELL_OK` | libs/system/sysPrxForUser.c |  | generic | generic |
| sysPrxForUser | `26090058` | sys_prx_load_module |  | missing | missing |  |  |  | missing | missing / UNRESOLVED (1) |
| sysPrxForUser | `42B23552` | sys_prx_register_library |  | missing | missing |  |  |  | missing | missing |
| sysPrxForUser | `9F18429D` | sys_prx_start_module |  | missing | missing |  |  |  | missing | missing / UNRESOLVED (1) |
| sysPrxForUser | `E0DA8EFD` | sys_spu_image_close | = | ctx | stub | `CELL_OK` | runtime/spu/spu_raw.c |  | ctx | ctx |
| sysPrxForUser | `8461E528` | sys_time_get_system_time | = | ctx | impl 10 |  | runtime/ppu/ppu_sysprx.cpp | 1 | ctx / 1 | ctx / 2-9 |

### Imported by 01.02 only (43)

| Library | NID | Name | Kind | Class | Hit |
|---|---|---|---|---|---|
| cellAudio | `4129FE2D` | cellAudioPortClose | generic | impl |  |
| cellAudio | `5B1E2C73` | cellAudioPortStop | generic | thin |  |
| cellAudio | `FF3626FD` | cellAudioRemoveNotifyEventQueue | generic | impl |  |
| cellAudio | `377E0CD9` | cellAudioSetNotifyEventQueue | generic | impl |  |
| cellAudio | `56DFE179` | cellAudioSetPortLevel | missing | missing |  |
| cellGcmSys | `2922AED0` | cellGcmGetOffsetTable | generic | impl |  |
| cellMic | `8D229F8E` | cellMicClose | generic | stub |  |
| cellMic | `C6328CAA` | cellMicEnd | generic | thin |  |
| cellMic | `B30780EB` | cellMicGetSignalState | generic | thin |  |
| cellMic | `A52D2AE4` | cellMicGetType | generic | thin |  |
| cellMic | `8325E02D` | cellMicInit | generic | thin |  |
| cellMic | `1B42101B` | cellMicIsAttached | generic | stub |  |
| cellMic | `186CB1FB` | cellMicIsOpen | generic | stub |  |
| cellMic | `05709BBF` | cellMicOpenEx ¹ | missing | missing |  |
| cellMic | `07E1B12C` | cellMicRead | generic | thin |  |
| cellMic | `65336418` | cellMicRemoveNotifyEventQueue ¹ | missing | missing |  |
| cellMic | `6BC46AAB` | cellMicReset ¹ | missing | missing |  |
| cellMic | `B2C16321` | cellMicSetDeviceAttr ¹ | missing | missing |  |
| cellMic | `7903400E` | cellMicSetNotifyEventQueue ¹ | missing | missing |  |
| cellMic | `DD724314` | cellMicStart | generic | stub |  |
| cellMic | `FCFAF246` | cellMicStop | generic | stub |  |
| cellMusicUtility | `8793EF97` | cellMusicGetSelectionContext2 ¹ | missing | missing |  |
| cellMusicUtility | `BE50B11E` | cellMusicInitialize2 | missing | missing |  |
| cellMusicUtility | `2BDC5D6B` | cellMusicSetSelectionContext2 | missing | missing |  |
| cellMusicUtility | `4014C246` | cellMusicSetVolume2 | missing | missing |  |
| cellSync | `D59AA307` | cellSyncLFQueueGetDirection | generic | thin |  |
| cellSysutil | `C9645C41` | cellGameDataCheckCreate2 | generic | thin |  |
| cellSysutil | `9949BF82` | cellGameDataExitBroken ¹ | missing | missing | UNRESOLVED (1) |
| cellSysutil | `A9B0C1D9` | cellGameDataGetSizeKB ¹ | missing | missing | UNRESOLVED (1) |
| cellSysutil | `9117DF20` | cellHddGameCheck | generic | thin | 1 |
| cellSysutil | `20543730` | cellMsgDialogClose | generic | impl | 1 |
| cellSysutil | `94862702` | cellMsgDialogProgressBarInc | generic | thin | 2-9 |
| cellSysutil | `918288FB` | cellStorageDataImport | missing | missing |  |
| sceNp | `1AE8A549` | sceNpBasicAddBlockListEntry | generic | thin |  |
| sceNp | `F2B3338A` | sceNpBasicGetBlockListEntry | missing | missing |  |
| sceNp | `73931BD0` | sceNpBasicGetBlockListEntryCount | generic | thin |  |
| sceNp | `BCC09FE7` | sceNpBasicRegisterHandler | generic | impl |  |
| sceNp | `5DE61626` | sceNpLookupDestroyTitleCtx | generic | thin |  |
| sceNp | `8440537C` | sceNpLookupTerm | generic | thin |  |
| sceNp | `7DEB244C` | sceNpScoreCensorComment ¹ | missing | missing |  |
| sceNp | `6F5E8143` | sceNpScoreCreateTransactionCtx | generic | impl |  |
| sys_net | `858A930B` | inet_ntoa | missing | missing |  |
| sys_net | `A50777C6` | shutdown | ctx | stub |  |

¹ named by T004: NID computed from the name and matched, not in the toolkit database. `=` in Handler: registered under the import's own name.
<!-- END GENERATED -->
