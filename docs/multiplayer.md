# Multiplayer: porting the community online mod to the 01.09 recomp

**Status: POSTPONED (user, 2026-10-23: the community server is not open source, so there is nothing to test against; T015 and T066-T074 are `blocked`).** Resume when the user provides a server or its protocol.

Research and plan, written 2026-10-23 (T015 and its sub-tasks T066-T074). Goal (user, 2026-10-23): "port
the custom multiplayer to our 1.09 recomp", **using the community server unmodified**, hosted **locally**
for testing. Nothing here is implemented yet; the only code run so far is a throwaway loopback listener
(section 4). Labels: **[verified]** = observed in a run of the recomp or in the files; **[code]** = read from
the game's lifted code or packages, not yet seen at run time; **[unverified]** = from public sources or a guess.

Companion docs: [online.md](online.md) (what the title does offline), [subsystems.md](subsystems.md#network-and-online)
(network notes), [game-profile.md](game-profile.md#versions-and-updates-researched-2026-10-18) (versions),
[graphics-menu.md](graphics-menu.md) (package patching, which this plan reuses), [workflow.md](workflow.md).

## 1. Ground rules for this work

- **Permission (user, 2026-10-23): the server is hosted locally, so work on it is allowed.** That lifts the old
  "never connect to RPCN or any community server" rule *only for servers the user runs on this machine or
  their LAN*. Public RPCN (`np.rpcs3.net`) and any community-hosted server stay off-limits until the user
  says so on the record (the operators' permission was the original blocker, T015).
- Every online experiment runs with `PS3_NET_SANDBOX=1`: DNS is never touched and `connect`/`sendto` only reach
  loopback, `PS3_NET_HOSTMAP` targets and private LAN ranges (patch 0073). A blocked destination is logged as
  `[sys_net] SANDBOX blocked`. Run games under `tools/task.sh lock boot`.
- **The server is never modified.** All adaptation happens in the client (our recomp, the player's own game
  packages through an overlay). If the server needs something the 01.09 client does not send, the client
  changes, not the server.
- Game data stays out of git (AGENTS.md rule 1). That includes the mod's `.pkg` files, anything extracted
  from them, and the constant `CallProcKey` header value the game sends (game-derived; not recorded here).
- Credit **kuxir97** (the mod, "SARPBC Online Mod 1.15"), **eiddor** (the setup guide) and the SARPBC+
  community in docs and, where a UI shows it, in the game's credits page.
- Licences: RPCN is AGPL-3.0, RPCS3 is GPL. We read their protocol behaviour; **no code is copied** into this
  tree. A client we write is our own code from the observed protocol. `psnr` (MIT, vendored in ps3recomp) is
  a different server and not RPCN.

## 2. What "the custom multiplayer" is

| Piece | What is known |
|---|---|
| The mod | "SARPBC Online Mod 1.15" by kuxir97, distributed as `.pkg` through the SARPBC+ Discord (https://discord.gg/qzDfqkaVTB). Install order 1.02 → 1.04 → 1.15 (+ optional "stuttering fix"). Built for RPCS3. Setup guide: https://github.com/eiddor/sarpbc-online [unverified, read 2026-10-23]. |
| In the game | "Play Online" → **Unranked Match** (host) / **Join A Friend**; the host starts matchmaking from the lobby. Known issues from the guide: slow for ~2 min after boot, scoring on **Galleon** crashes, saving replays crashes, engine fps is uncapped so players cap it at 120-180; the mod "adjusts some input values" (deadzones) [unverified]. |
| The servers | The guide names only **RPCN**: enable PSN status RPCN, create an RPCN account (email token), add friends. The RPCS3 wiki's RPCN compatibility row says **"Requires OpenSpy patch and a custom pkg; custom server available"**, all of connect/lobby/matching **Untested**. Third-party configs (ps5sx3-rpcn-configs) just set DNS 8.8.8.8 and RPCN, i.e. no redirect on the emulator side: **the redirect of the game's web service must be inside the mod's package** [unverified inference]. |
| What we do not have | The mod's `.pkg` files, the 1.04 patch, and the server software or its address. **Not on this machine** (searched 2026-10-23). The mod's server is never named in public text; the "OpenSpy" note looks like a leftover from the GameSpy-era (1.02) approach. |

**Which server is it? Two candidates, possibly both** (decided by T068, which needs the user's files):

1. **A callproc web service**, the replacement for Psyonix's `sarb.psyonix.com`: login/version/server list/
   stats. Section 4 proves the 01.09 client needs one. Whoever revived the game must run something like this.
2. **RPCN** (open source, self-hostable): NP identity, friends, presence, signaling. Section 5.

The plan builds the client side of (1) first because it is certain, and gates (2) on evidence.

## 3. 01.09 and the mod's base version

- PROJECTX's default properties contain two version strings, **`00.00.0006`** and **`00.01.0004`** [verified,
  `versions/0109/.../PROJECTX.XXX`, offset ~149161 of the decompressed package]. `00.01.0004` reads as
  "**1.04**", the mod's required base. 01.09 is the PSN `APP_VER`; Psyonix's own number for the same build is
  probably 1.04 [unverified guess, strong]. T068 settles it by comparing the mod's 1.04 package against our 01.09
  files (EBOOT hash, packages).
- If they are the same build, **the mod's 1.15 delta is a patch on exactly what we run**, and "porting" means:
  apply the delta's intent to the 01.09 files through our overlay (packages, config, EBOOT-level behaviour as
  port-side overrides), and implement what the delta needs from the runtime.
- If they differ, the delta is re-derived against 01.09 by diffing (the lifted code of both EBOOTs would need
  a second lift; do not do that without asking: it is the user's call, workflow.md).

## 4. The 01.09 online stack (verified findings)

### 4.1 Layers

```
 UnrealScript   ProjectX.OnlineGame_Base_X / OnlineGame_X     (host/search/join, stats, login gate)
                PsyNet.OnlineSubsystemPsyNet, OnlineGameInterfaceImpl_PN, OnlinePlayerInterface_PN (web-backed)
                OnlineSubsystemPS3.* (player, game, system, voice interfaces; native NP)
 native (EBOOT) UPsyWebServer_X (queue, HandleSendRequest, Tick), UHttpRequestInterface, UHTTPDownload
                OnlineGameInterfaceImpl_PS3 (TestNat, RemoveAllUnusedNats, AddNatAndGetPingUtility)
 PS3 libs       sys_net (22 imports), cellNetCtl (8), sceNp (43): Manager, Basic, Lookup, Score, Signaling; cellVoice (10)
```

`TAEngine.ini` (the game's own config, from `COALESCED.INI` in the 01.09 install): `DefaultOnlineSubsystemName=OnlineSubsystemPS3.OnlineSubsystemPS3`
(GameSpy is commented out), `OnlineGame_Base_X` uses `OnlineSubsystemPS3.*Impl_PS3` for player/game/system/voice and
`PsyNet.OnlineNewsInterfaceImpl_PN` for news, `LocationUrl=bbUS`, `bShouldUseNatTraversal=true`, net driver
`IpDrv.TcpNetDriver` (UE3's UDP game driver), `[URL] Port=7777`, `NetServerMaxTickRate=30`. News comes from
`http://www.psyonix.com/sarbnews.xml` (in the PSYNET package; harmless if it fails).

### 4.2 Imports that matter [verified, `versions/0109/analysis/imports_named.json`]

- **No `sceNpMatching2`, no `sceNpMatching`, no `cellHttp`, no `cellSsl`.** Matchmaking cannot be NP rooms, and
  TLS is not provided by the console libraries.
- sceNp: Manager (`GetStatus`, `RegisterCallback`, `GetNpId`, `GetOnlineId`, `GetOnlineName`, `GetTicket`,
  unnamed `0x7E2FEF28` = `RequestTicket`, `GetContentRatingFlag`, `GetChatRestrictionFlag`); Basic (friend
  list entries + count, `SetPresence`, `RegisterContextSensitiveHandler`, `UnregisterHandler`,
  `AddPlayersHistoryAsync`, unnamed `0x32C78A6A` = `GetFriendPresenceByIndex`, `0xBE81C71C` = `SetPresenceDetails`);
  Lookup (title/transaction ctx, `PollAsync`, `NpIdAsync`, unnamed `0x166DCC11` = `LookupNpId`); Score (init/term/
  ctx create/destroy only; no record or ranking call imported); **Signaling** (`CreateCtx`, `DestroyCtx`,
  `AddExtendedHandler`, `ActivateConnection`, `DeactivateConnection`, `TerminateConnection`,
  `GetConnectionInfo`, `GetLocalNetInfo`); `UtilCmpNpId`; `DrmIsAvailable`, `DrmExecuteGamePurchase`.
- sys_net: socket, connect, bind, listen, accept, send, sendto, recv, recvfrom, select, get/setsockopt,
  getsockname, gethostbyname, inet_addr, errno, close. cellVoice: InitEx, ports, `WriteToIPort`/`ReadFromOPort` etc.
  (01.09 replaced cellMic with cellVoice).

### 4.3 The web service [verified by a run on 2026-10-23]

The EBOOT holds the URL `https://sarb.psyonix.com/v001/callproc.php` (wide string at `0xf81e28`), the request
templates `&Proc[]=%s(` (`0xf81d78`), `&VersionCheck=ValidateVersion` (`0xf81dd8`), `CallProcKey` (`0xf81e80`), `GET %s HTTP/1.1` /
`POST %s HTTP/1.1` + `Content-Type: application/x-www-form-urlencoded` (`0xfdf1dc`..`0xfdf32c`, shared with
`UHTTPDownload`). UE3 natives: `PsyWebServer_X` (`CreateRequest`, `HandleSendRequest`, `AddQueuedResponse`,
`FlushRequests`, `Tick`) and `PsyWebServerQuery_X` (`SetDatabase`, `SetPlayerNum`, `SetRequiresGameVersion`,
`SetRequiresGlobalVersion`).

Probe: boot 01.09 with `PS3_NET_ONLINE=1 PS3_NET_SANDBOX=1 PS3_NET_TRACE=1`, `tools/boot_check.sh 80 --version 0109
--pad 'cross@45,down@50,cross@55,cross@64'` (Play Online), and a throwaway logger on `127.0.0.1:80` answering
`200` with an empty body. Result:

```
[sys_net] gethostbyname('sarb.psyonix.com') SANDBOXED -> 127.0.0.1 (no DNS)
[sys_net] socket(2, 1, 6) -> 1            connect(1, 127.0.0.1:80)          <- plain HTTP, port 80, no TLS
send(1) -> 215 bytes (headers), send(1) -> 85 bytes (body), then recv(1) one byte at a time
POST /v001/callproc.php HTTP/1.1
Host: sarb.psyonix.com
User-Agent: UE3-TA
Content-Type: application/x-www-form-urlencoded
CallProcKey: <32 characters, value not recorded>
Content-Length: 85
Connection: close

DB=SARPBC_Prod&Proc[]=GetOnlineVariables()&VersionCheck=ValidateVersion('00.00.0006')
```

- The same request is sent **once at boot (~6 s, before the main menu)** and **again on Play Online**.
  `sceNpManagerGetStatus` returned OFFLINE both times: the web call does not wait for NP.
- With the loopback listener answering an empty `200`, the game stays on **"Logging in..."** (capture
  `captures/boot_check/20261023-020748-*`, deleted if disk is tight): an empty body is not an error and not a
  success. With nothing listening (connect refused) the old path holds: error dialog within ~8 s (online.md).
- The `https://` scheme in the URL is ignored: the client never speaks TLS. A local server needs only
  plain HTTP on port 80. (Port 80 is privileged: bind as root, `setcap cap_net_bind_service`, or add a host
  port map to patch 0073, see T067.)
- `DB=` is a database name (`DBE_Production/Staging/Dev/Test` enum in PROJECTX; `SARPBC_Prod` = production).
  `Proc[]=` is a stored-procedure call with its arguments inline; several `Proc[]` can be batched in one
  request. `VersionCheck=ValidateVersion('<global version>')` rides along; the two version strings in 3 are
  presumably the *global* (`00.00.0006`) and *game* (`00.01.0004`) database versions
  (`bRequiresGlobalVersion`, `bRequiresGameVersion`, `DBVersion_Global`, `DBVersion_Game`).
  **An unmodified server will probably reject a version it does not know.** Which string the mod's client
  sends is exactly what T068 has to find out.

### 4.4 What still has to be read out of the client (T066, no mod needed)

Procedure names and argument layouts for: login/`PlayerLogin`, `RegisterPlayer`, `CreatePsyonixUser`,
`ValidatePsyonixID`, `GetAllPsyonixUsers`, the host's server registration (`CreateGameProcedureName`,
`HandleCreateInternetGame`, `Heartbeat`, `HeartbeatTime`, `RegisteredServerID`, `HandleDestroyInternetGame`,
`HandleUpdateOnlineGame`), search (`HandleFindInternetGame`, `OnlineGameSearch_X`, `OnlineGameServerList_X`),
friends (`ReadFriendsList`, `JoinFriendGameByName`), stats writes (`TAStats`, `ClientWriteOnlineStats*`), and the
**response format** (parsed in `PsyWebServer_X::HandleSendRequest`/`AddQueuedResponse`, then `HttpResponse`
in UnrealScript: `ProcedureResult`, `ProcedureKeyValuePair`, `ProcedureParam`). Tools: `tools/ue3`
(`dis`, `tree`, `find`), and the lifted functions near the natives above in `versions/0109/src/recomp`.

## 5. The NP side and RPCN

RPCN (https://github.com/RipleyTom/rpcn, Rust, AGPL-3.0; v1.12.1 read 2026-10-23) [unverified against a
running instance]:

| Aspect | Facts |
|---|---|
| Transport | TLS over TCP, **port 31313** (`Host=0.0.0.0`, `Port=31313` in `rpcn.cfg`); self-signed `cert.pem`/`key.pem` made by `rpcn --cert-gen` (RSA 4096). Packet header 15 bytes (type u8, command u16, size u32, id u64); on connect the server sends a `ServerInfo` packet with **protocol version 34**. |
| UDP | **port 3657**: the signaling helper (probe/reply so peers can learn each other's public address); P2P game traffic itself goes peer to peer (default 3658 in RPCS3). |
| Accounts | `Login(npid, password, token)`; with `EmailUrl=` empty there is no email token. `CreateMissing=true` (default) creates unknown NP communication IDs: **no per-game server code is needed**; `servers.cfg` only lists games with several servers/worlds (SARPBC is not in it). `SignTickets=false` by default (tickets unsigned; `SignTickets=true` signs with `ticket_private.pem`). |
| Provides | friends + presence (`SetPresence`, friend notifications), `RequestTicket`, `RequestSignalingInfos` (NpId → peer address; same public IP → the peer's LAN address on port 3658), Matching2 rooms, scoreboards, TUS, trophies, GUI rooms. |
| Build / run | Rust ≥ 1.85 (edition 2024), `protoc`, a C toolchain (openssl and sqlite are vendored/bundled); `cargo build --release`, `rpcn --cert-gen`, `rpcn` in a directory with the `*.cfg` files. A Dockerfile exists. **Neither cargo nor docker/podman is installed on this machine** (checked 2026-10-23). |

What the game would use from it: Manager status/ticket/online ID, friends and presence for **Join A Friend**,
and Signaling for NAT traversal to the host. It would not use rooms, Score, TUS or trophies (not imported).
What the recomp has: ps3recomp speaks **psnr** (another server, Matching2-oriented) and has no RPCN client.
Today: `sceNpManagerGetStatus` always OFFLINE, the friends/presence/ticket/lookup calls mostly stubs
(`docs/hle-coverage.md`), Signaling stubbed.

**Decision gate D1 (T068):** is RPCN a real dependency, or is the web service enough?
- Evidence that RPCN is needed: the mod's server list holds NP IDs that must be signaled; "Join A Friend" needs
  friends/presence; the web service validates tickets.
- If not needed, a local "NP-lite" (synthetic online ID, locally generated ticket, in-process friend list and a
  tiny local directory mapping an NP ID to a host address for signaling) is enough for local testing and LAN.
- If needed: T072 writes an RPCN client in ps3recomp (TLS: system OpenSSL; own code, protocol v34).

## 6. Target architecture

```
 recomp client (01.09)                                   local server machine (loopback/LAN)
 ┌────────────────────────────────────────┐             ┌──────────────────────────────────┐
 │ guest game (UE3)                       │  HTTP :80   │ community web service (unmodified)│  <- T068 identifies it
 │  PsyWebServer_X ── sys_net ────────────┼────────────►│  callproc.php stored procedures   │
 │  OnlineSubsystemPS3 ── sceNp* ─┐       │             └──────────────────────────────────┘
 │  TcpNetDriver (UDP) ── sys_net ┼──P2P──┼──► other recomp client (127.0.0.1 / LAN)
 └────────────────────────────────┼───────┘             ┌──────────────────────────────────┐
   HLE (ps3recomp patches, ours):  │   TLS :31313/UDP   │ RPCN (unmodified), only if D1 = needed│
   NP manager/friends/signaling ───┴───────────────────►│                                  │
   sys_net hostmap + port map, sandbox                  └──────────────────────────────────┘
```

Client-side changes, by where they live (AGENTS.md rules 2-3):

| Where | What | Task |
|---|---|---|
| `external/ps3recomp` patches (title-agnostic) | sys_net host port map (`name:80=ip:8080`), NP manager ONLINE + ticket + online-ID/name from config, friend list/presence, lookup, signaling with a pluggable peer directory, optional RPCN client, multi-instance P2P port rules | T067, T069, T071, T072 |
| `src/overrides/` | game-specific: online config (server host, account name), version-string handling, any EBOOT-level behaviour of the mod keyed by 01.09 address/NID | T067-T071 |
| player package overlay (`PS3_VFS_OVERLAY`, `tools/ue3`, `tools/graphics_menu_patch.py` pattern) | UnrealScript/default-property changes the mod makes (server names, version strings, "Play Online" menu items, input tweaks) re-applied to 01.09's own packages, never editing the originals | T068-T070 |
| `tools/` | the T066 probe tool (`callproc_probe.py`, to be added under tools/) (loopback logger/stub), `mp_local.sh` (T067, to be added under tools/) (start/stop the local server stack), `mp_check.sh` (T074, to be added under tools/) (two-client scripted match) | T066, T067, T074 |
| `config.toml` `[online]` | server host/IP, account name, port map, P2P port; env overrides; sandbox on by default | T067 |

## 7. Task plan

Order is by priority number on the board. T015 stays as the umbrella (`blocked`, do not claim).

| Task | What | Needs | Done when |
|---|---|---|---|
| **T066** client protocol | Read the callproc protocol out of the 01.09 client: procedure names, arguments, response format, error handling, the version gate, which calls happen at boot / login / host / search / join / leave / stats. Commit the T066 probe tool (`callproc_probe.py`, to be added under tools/) (logs requests, serves canned replies) and `docs/multiplayer-protocol.md`. | nothing: start now | Every `Proc[]` the client can send is listed with args and where it is sent from; the response grammar is written down with evidence; the probe can drive the client past "Logging in..." with a canned reply |
| **T067** local rig and redirect | `config.toml [online]`; port map for `sarb.psyonix.com:80`; `mp_local.sh` (T067, to be added under tools/); install the toolchain for RPCN **after asking the user**; sandbox stays on; per-instance saves/ports for two clients on one machine | T066 started | `Play Online` talks to a server on 127.0.0.1 through config only (no env hacks), nothing leaves the host (sandbox log clean), two instances start side by side |
| **T068** mod and server inputs | The user supplies the mod `.pkg` files (1.04, 1.15, stutter fix) and the server software or its source. Extract with `tools/extract.sh`-style steps into a git-ignored dir; diff the mod against 01.09 (EBOOT, every package, COALESCED, SFO); identify the server and how the mod redirects to it; answer D1; update the protocol doc | the user's files | `docs/multiplayer-mod.md` lists every changed file/function/default property with its purpose; D1 answered; the version string the server accepts is known |
| **T069** NP identity | sceNpManager ONLINE, online ID/name from config, ticket, friend list + presence, lookup, `GetLocalNetInfo`/signaling as NP-lite; unnamed NIDs named (`0x7E2FEF28`, `0x32C78A6A`, `0xBE81C71C`, `0x166DCC11`) | T066, T068 (D1) | The game's login gate passes (`CanPlayOnline`, `GetLoginStatus` = logged in) with the real local server |
| **T070** login and lobby | Drive the real server through boot, "Logging in...", the online menu, Unranked Match search and host registration + heartbeat; apply the mod's package/config changes as an overlay | T066, T068, T069 | From the main menu, Play Online → Unranked Match → lobby shows and the host appears in the server list of a second client |
| **T071** peer-to-peer match | UE3 UDP game traffic between two recomps on one machine, then LAN; Signaling established events; `TestNat`/`AddNatAndGetPingUtility`; per-instance P2P ports; play a full match; round end, leave, host quit | T070 | Two instances play a match to the results screen; goals and clocks agree on both; no desync alerts; leaving returns both to the menu |
| **T072** RPCN client (conditional) | Only if D1 says RPCN is needed: TLS client for protocol v34 (login, ticket, friends, presence, signaling infos + UDP probe), in ps3recomp, own code | D1, T067 toolchain | Login/friends/presence/signaling against a local RPCN verified; psnr unaffected |
| **T073** edges | cellVoice (no audio, no failures), stats writes, leaderboards, disconnect/abandon, the known Galleon scoring and replay-save crashes (check whether our recomp has them), four-player lobbies, timeouts | T071 | Each edge has a test or a documented non-goal |
| **T074** verify and polish | `mp_check.sh` (T074, to be added under tools/) + `verify.sh --scenario online` (server + two clients, scripted pad), docs, credits, "Online" notes in the options pages if useful | T071 | One command boots the stack and prints PASS with evidence |

Rules of thumb for every task here: patch ps3recomp title-agnostically (the web service redirect and port map
are general; the Psyonix specifics are overrides); no `PS3_NET_ONLINE` default; run under the `boot` lock;
update this file and `docs/multiplayer-protocol.md` in the same commit as the code.

## 8. Local test topology

Everything on one machine; ports in use:

| Port | Who | Notes |
|---|---|---|
| 80/tcp | web service (callproc) | the client dials `sarb.psyonix.com:80`; map it to `127.0.0.1:80` (root) or `127.0.0.1:8080` (port map) |
| 31313/tcp | RPCN | only if D1 needs it; TLS, self-signed |
| 3657/udp | RPCN signaling | only with RPCN |
| 3658/udp+tcp, 3659... | client P2P (`PS3_NET_P2P_PORT`) | one per instance; two clients on one machine need two ports |
| 7777/udp | UE3 net driver | `[URL] Port=7777`; the second instance must use another port |

Starting a client for these tests:
`PS3_NET_ONLINE=1 PS3_NET_SANDBOX=1 PS3_NET_HOSTMAP=sarb.psyonix.com=127.0.0.1 PS3_NP_ONLINE_ID=alice PS3_NET_P2P_PORT=3658 ./run.sh`
(T067 replaces the env block with `config.toml`). Second client: another online ID and P2P port, **its own
`gamedata/` and VFS save directory** (saves and profile are per install; two instances sharing one profile
will clash).

## 9. Risks and unknowns, ranked

1. **We have not seen the server or the mod.** Everything about the response format, procedure set and the
   accepted version string is client-side inference until T068. Mitigation: T066 reads the client's parser; the
   probe tool lets us test a canned reply per procedure; T068 is the first thing to ask the user for.
2. **Version/key gates** (`ValidateVersion`, `CallProcKey`): an unmodified server may only accept the mod
   client's exact values. The values live in package/config data, so the overlay can set them. Never record
   the key value in git.
3. **RPCN may or may not be a dependency (D1).** If it is, T072 is a real project (TLS client, protocol v34,
   UDP signaling). If it is not, NP-lite is small.
4. **Peer-to-peer on one machine**: two guests, two UE3 net drivers, NAT-test natives, `sceNpSignaling`
   semantics, one profile per instance, and fps: two instances at 55-60 fps each is probably fine (the
   psnr two-instance runs crawled only with verbose logging; run with `PS3_VERBOSE=0`).
5. **The 1.04 = 01.09 assumption** (section 3). If wrong, the mod's EBOOT changes need a re-lift: ask the user.
6. **Hangs on odd replies**: the client waits on "Logging in..." with an empty 200. Any unexpected body
   needs a timeout story; keep a canned "server down" reply path so the menu never wedges.
7. **Known mod issues** (Galleon scoring crash, replay save crash): may be emulator-specific; test on the recomp
   before assuming. The mod's input tweaks (deadzones) must be mirrored or the pad feel differs from other players.
8. **Port 80 and sandbox**: the sandbox blocks non-private destinations. A server on another LAN machine works
   (private ranges); a server on a public IP needs explicit `PS3_NET_HOSTMAP` and the user's say-so.

## 10. What to ask the user (in this order)

1. The mod's files: `SARPBC Online Mod 1.15.pkg`, the 1.04 PKG, the optional stuttering-fix PKG (and where the
   user got them; they are not on this machine).
2. The server: software or source for the web service the mod talks to (and RPCN if the user runs one), how it
   is started, its address and ports, and a test account if accounts exist.
3. Permission to install a Rust toolchain and `protobuf-compiler` (and optionally docker/podman) to build RPCN
   locally, if RPCN is in scope.
4. Whether the real mod behaviour (menus: "Unranked Match", "Join A Friend") should be matched exactly in our UI,
   or only made to work. Default here: match what the mod's package does.

## 11. Evidence log

- 2026-10-23 02:04-02:09: `PS3_NET_ONLINE=1 PS3_NET_SANDBOX=1 PS3_NET_TRACE=1 tools/boot_check.sh 80 --version 0109 --pad
  'cross@45,down@50,cross@55,cross@64'`; run dirs `analysis/boot_check/20261023-020423-*` (nothing listening:
  `connect(1, 127.0.0.1:80)` fails with errno 36/111, boot report PROGRESSING) and `20261023-020748-*` (listener:
  two POSTs, the second after Play Online; frame_last_lit.png shows "Logging in..."). Throwaway listener lived
  only in the session scratchpad; T066 turns it into the T066 probe tool (`callproc_probe.py`, to be added under tools/).
- EBOOT string scan: `python3 -I` over `versions/0109/game/EBOOT.elf` for UTF-16BE strings (addresses above).
- Package scan: `tools/ue3 find/info` and a regex over the decompressed `PROJECTX`, `PSYNET`, `ONLINESUBSYSTEMPS3`,
  `IPDRV` (decompressing TAGAME/MAINMENU/STARTUP_INT in pure Python takes minutes: run it in the background).
- RPCN source read from https://github.com/RipleyTom/rpcn (master, 2026-10-23): `rpcn.cfg`, `servers.cfg`,
  the RPCN repo files `server.rs` (protocol version 34, TLS), `client.rs` (command list) and `udp_server.rs` (3657).
- Public pages read: https://github.com/eiddor/sarpbc-online ; RPCS3 wiki row via a search snippet (the wiki
  itself is behind a Cloudflare check); https://github.com/Lucidic15/ps5sx3-rpcn-configs (`game_configs/config_NPUB30035.yml`).
