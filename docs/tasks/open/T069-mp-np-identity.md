# T069: NP online identity: manager ONLINE, ticket, friends, presence, lookup

Status: open
Owner: -
Priority: blocked
Touches: patches/ps3recomp/NNNN-np-online-identity.patch (libs/network/sceNp.c, sceNpBasic.c, sceNpLookup.c, np_*), src/overrides/np_online.cpp (new), docs/multiplayer.md, docs/hle-coverage.md
Reads: docs/multiplayer.md (sections 4.2, 5), docs/hle-coverage.md (sceNp rows), docs/online.md, external/ps3recomp/docs/ONLINE.md, tasks T066, T068

## Goal
Part of the multiplayer port (umbrella T015). The game's login gate and friend features call sceNp, and today
`sceNpManagerGetStatus` is always OFFLINE. Make it ONLINE when `[online] enabled` (T067), with a believable
identity, **without a real PSN or RPCN**:

1. Manager: status ONLINE + the callback event, `GetNpId`/`GetOnlineId`/`GetOnlineName` from config (PSN rules:
   3-16 chars), `GetTicket` and the unnamed `0x7E2FEF28` (`RequestTicket`, verify the name by signature) with a
   locally built ticket in the format the title reads, content-rating/chat flags unrestricted.
2. Basic: friend list entries and count (from config or the local directory), `SetPresence`, the unnamed
   `0x32C78A6A` (`GetFriendPresenceByIndex`) and `0xBE81C71C` (`SetPresenceDetails`), `AddPlayersHistoryAsync`,
   context-sensitive handler registration.
3. Lookup: `LookupNpId(Async)`/poll answering from the local identity table.
4. **NP-lite local directory** (the same data psnr and RPCN would give): a tiny shared table NP ID → host,
   P2P port, presence, reachable by two instances on one machine (file or loopback UDP). Interface kept
   narrow so T072 can swap an RPCN client in behind it.
5. Name the unnamed NIDs in `tools/hle_coverage.py`'s table source and update docs/hle-coverage.md.
6. If T068 answers D1 = "RPCN needed" for ticket validation, the ticket must be what the server accepts:
   revisit with T072.

## Done when
`OnlinePlayerInterfaceImpl_PS3` login succeeds in the game (log shows `GetLoginStatus` logged in, no
`OnLoginFailed`), the friend list screen opens with config-provided friends, and offline default is unchanged.
Unit tests in the upstream style for the new HLE paths (`libs/network/tests/`). `tools/verify.sh` OK.

## Log
- 2026-10-23 claude: created from the multiplayer research. Needs T066 (what the login gate checks) and T068 (D1).
- 2026-10-23 user: "the server isn't open source like i assumed. just postpone the multiplayer plan." Set to blocked; resume when the user supplies the server (or decides on a different approach).
