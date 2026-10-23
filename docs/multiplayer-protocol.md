# Multiplayer: the callproc web protocol (01.09 client side)

Living document for T066 (client side) and T068 (server side). What the 01.09 client sends to the web service
that replaced Psyonix's `sarb.psyonix.com`, and what it expects back. Overview and plan:
[multiplayer.md](multiplayer.md). Labels: **[seen]** observed at run time, **[code]** read from the game's
packages or lifted code, **[guess]**. Never write the `CallProcKey` value or any other game-derived constant
here (AGENTS.md rule 1).

## Transport [seen, 2026-10-23]

- `gethostbyname("sarb.psyonix.com")`, then `socket(AF_INET, SOCK_STREAM)` and `connect` to **port 80**: plain
  HTTP, no TLS, although the configured URL is `https://sarb.psyonix.com/v001/callproc.php` (wide string at
  `0xf81e28` in the 01.09 EBOOT). One connection per request, `Connection: close`.
- The request is sent as two `send` calls: headers (215 bytes), then the body (85 bytes in the observed case).
  The reply is read with `recv(1)`, one byte at a time, until the connection closes or the framing says done.
- The native HTTP client is shared with `UHTTPDownload` (`GET %s HTTP/1.1`, `POST %s HTTP/1.1`,
  `Content-Type: application/x-www-form-urlencoded`; strings at `0xfdf1dc`-`0xfdf32c`).

## Request [seen]

```
POST /v001/callproc.php HTTP/1.1
Host: sarb.psyonix.com
User-Agent: UE3-TA
Content-Type: application/x-www-form-urlencoded
CallProcKey: <32 characters; a constant the game sends; not recorded>
Content-Length: <n>
Connection: close

DB=SARPBC_Prod&Proc[]=GetOnlineVariables()&VersionCheck=ValidateVersion('00.00.0006')
```

- `DB=` database name. PROJECTX has the enum `DBE_Dev`, `DBE_Staging`, `DBE_Test`, `DBE_Production` [code];
  `SARPBC_Prod` is what production sends [seen]. Format string: `&Proc[]=%s(` and `&VersionCheck=ValidateVersion`
  (`0xf81d78`, `0xf81dd8`) [code].
- `Proc[]=Name(args)` repeats for several calls in one request [guess from the `[]` and the `%s(` template;
  T066 confirms from `PsyWebServer_X::HandleSendRequest`).
- `VersionCheck=ValidateVersion('<v>')`: `'00.00.0006'` is the *global DB version*; the other string in PROJECTX
  defaults is `00.01.0004` (the *game DB version*, "1.04") [code]. `bRequiresGlobalVersion` /
  `bRequiresGameVersion` on `PsyWebServerQuery_X` choose which are sent [code].

## When the client sends what

| Moment | Request | Source |
|---|---|---|
| Boot, ~6 s in, before the main menu | `GetOnlineVariables()` + `ValidateVersion('00.00.0006')` | [seen] `OnlineGame_X.CheckOnlineVariables` [code] |
| Play Online pressed (after the NetStartDialog, "Logging in...") | the same request again | [seen] |
| Login / registration | `PlayerLogin`, `PlayerRegister`, `RegisterPlayer*`, `ValidatePsyonixID`, `CreatePsyonixUser`, `GetAllPsyonixUsers` | names only [code]; arguments T066 |
| Host registers a game | `CreateGameProcedureName` (a config string) then `Heartbeat` every `HeartbeatTime`; `RegisteredServerID` | names only [code]; T066 |
| Search | `HandleFindInternetGame` / `OnlineGameServerList_X.StartNewGameSearch` | names only [code]; T066 |
| End of match | `ClientWriteOnlineStats*`, `TAStats` | names only [code]; T066 |

## Response

Unknown. What is known: an empty `200 OK` (no body) leaves the game on "Logging in..." with no error within
~20 s [seen]; a refused connection gives "An error occurred when retrieving data from the online service" within
~8 s [seen, online.md]. UnrealScript receives results through `HttpResponse`/`WebServerHttpResponse`,
`ProcedureResult`, `ProcedureKeyValuePair`, `ProcedureParam` (PROJECTX) [code]. T066 reads the parser; T068
checks it against the real server.

## Open questions

1. Response body grammar (text? key=value? JSON?) and how several `Proc[]` results are separated.
2. What `GetOnlineVariables` returns and how the client uses it (names suggest tuning variables; the
   `CheckOnlineVariablesComplete` path decides whether online play is allowed).
3. Does the unmodified community server accept `'00.00.0006'` and the retail `CallProcKey`, or only the mod
   client's values? (T068)
4. Is the host's IP taken from the TCP connection (server side) or sent by the client? NAT traversal needs
   the public/LAN address of the host in the server list entry.
5. Are NP tickets or NP IDs sent to the service (login would then depend on T069/T072)?
