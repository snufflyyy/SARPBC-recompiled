# T066: Read the callproc protocol out of the 01.09 client and write the probe tool

Status: open
Owner: -
Priority: blocked
Touches: docs/multiplayer-protocol.md (new), tools/callproc_probe.py (new), tools/test_callproc_probe.py (new), docs/multiplayer.md
Reads: docs/multiplayer.md (sections 4 and 7), docs/unreal-engine-3.md, docs/graphics-menu.md (tools/ue3), docs/subsystems.md (network)

## Goal
Part of the multiplayer port (umbrella T015, user 2026-10-23). The 01.09 client talks to a web service with
`POST /v001/callproc.php`, body `DB=SARPBC_Prod&Proc[]=Name(args)&VersionCheck=ValidateVersion('00.00.0006')`
(verified, docs/multiplayer.md 4.3). No mod files or server are needed for this task: read everything the
client sends and expects from the client itself.

1. **Requests**: every procedure the client can send, its argument layout and where it is sent from: boot
   (`OnlineGame_X.CheckOnlineVariables` / `GetOnlineVariables`), login (`OnlinePlayerInterfaceImpl_PN.Login`,
   `HandlePlayerLogin`, `RegisterPlayer*`, `ValidatePsyonixID`, `CreatePsyonixUser`, `GetAllPsyonixUsers`), host
   (`CreateGameProcedureName`, `HandleCreateInternetGame`, `Heartbeat`, `HandleUpdateOnlineGame`,
   `HandleDestroyInternetGame`), search (`HandleFindInternetGame`, `OnlineGameServerList_X`), friends, stats
   (`TAStats`, `ClientWriteOnlineStats*`). Sources: `tools/ue3 dis/tree` on PROJECTX, PSYNET, TAGAME, TASTATS, and
   the lifted natives around `UPsyWebServer_X` / `UPsyWebServerQuery_X` (strings at `0xf81d78`..`0xf81e80` in the
   01.09 EBOOT; look in `versions/0109/src/recomp`). Where a value is built from `%s` templates, say what fills it.
2. **Responses**: the grammar the client parses (`PsyWebServer_X::HandleSendRequest`, `AddQueuedResponse`, then
   `ProcedureResult` / `ProcedureKeyValuePair` / `ProcedureParam` in UnrealScript): status line, headers it
   needs, body encoding, how multiple `Proc[]` results are separated, how errors and `VersionMismatch` /
   `InvalidLogin` / `OSCS_DuplicateLoginDetected` / `PsyConnectionError` are signalled, timeouts, and what it does
   on an empty body (it waits on "Logging in..." today).
3. **Where the endpoint and the version strings come from**: the URL (`0xf81e28`), `DB=` selection
   (`DBE_Production`...), the global/game version strings (`00.00.0006`, `00.01.0004` in PROJECTX defaults) and
   `CallProcKey` (value is game-derived: **do not write it in git**, say where it is read from).
4. **`tools/callproc_probe.py`** (our own code, header + mode like the other tools, pyflakes clean): a loopback
   HTTP server that logs whole requests (headers + decoded body) as JSON lines and serves replies from a small
   table or file; `--port`, `--log`, `--replies`. Option to refuse anything not from loopback/LAN. Unit test
   `tools/test_callproc_probe.py` (stdlib only, added to `lint.py --tests` the way the other tests are).
5. `docs/multiplayer-protocol.md` (new, add to the AGENTS.md docs index): requests, responses, flows (boot, login,
   host, search, join, leave, stats), open questions. Mark each fact **[seen at run time]**, **[code]** or **[guess]**.

## Done when
Every `Proc[]` the client can send is listed with arguments and trigger; the response grammar is written down
with evidence (disassembly addresses and a run); the probe, driven with canned replies, gets the client past
"Logging in..." to the next screen or error (screenshot hash or log line in the task log). No server and no
mod file used. `tools/lint.py --tests` is clean. Sandbox on for every run (`PS3_NET_SANDBOX=1`), games under
`tools/task.sh lock boot`.

## Log
- 2026-10-23 claude: created from the multiplayer research (docs/multiplayer.md). First probe already run: boot
  request at ~6 s and on Play Online, `GetOnlineVariables()` + `ValidateVersion('00.00.0006')`; an empty 200 leaves
  the game on "Logging in...".
- 2026-10-23 user: "the server isn't open source like i assumed. just postpone the multiplayer plan." Set to blocked; resume when the user supplies the server (or decides on a different approach).
