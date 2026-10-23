# T072: RPCN client in ps3recomp (only if the mod needs RPCN)

Status: open
Owner: -
Priority: blocked
Touches: patches/ps3recomp/NNNN-np-rpcn-client.patch (libs/network/np_rpcn.c, sceNp*.c, CMake), docs/multiplayer.md, docs/upstream.md
Reads: docs/multiplayer.md (section 5, decision D1), docs/multiplayer-mod.md, tasks T067, T068, T069

## Goal
**Blocked until T068 answers decision D1 with "RPCN is a real dependency"** (tickets the web service checks,
friends/presence for Join A Friend, signaling through RPCN). Set Priority to 16 then. If D1 says no, close this
task as "not needed" with the evidence.

Write a native RPCN client, as our own code from the observed protocol (RPCN is AGPL-3.0, RPCS3 is GPL: read
behaviour, copy nothing; docs/multiplayer.md section 1):

1. TLS over TCP to the configured host (default port 31313), self-signed server certificate (pin or accept
   per config; never accept arbitrary certificates for a non-loopback host). System OpenSSL via CMake, optional,
   off by default so the offline build is unchanged.
2. Framing: 15-byte header (type u8, command u16, size u32, id u64), `ServerInfo` first (protocol version 34;
   refuse another version with a clear message), request/reply/notification matching by id.
3. Commands the game needs: `Login(npid, password, token)`, `RequestTicket`, friends list and presence
   (`SetPresence`, notifications), `RequestSignalingInfos`, `GetNetworkTime`, `Terminate`; UDP 3657 probe
   handshake for signaling and the P2P port (3658 by default).
4. Plug it in behind the T069 directory interface; NP-lite stays the default when RPCN is not configured.
5. Tests: a loopback fake RPCN in `libs/network/tests/` for framing and login; then against the real local RPCN
   the user runs (`tools/mp_local.sh`). Account creation stays outside the game (RPCN's own tooling).

## Done when
Login, friends, presence, ticket and signaling info against a local RPCN verified with logs from both ends;
psnr and offline paths unaffected; patch exported (`tools/export_patch.sh`) with a README row.

## Log
- 2026-10-23 claude: created as conditional work from the multiplayer research (public RPCN stays off-limits:
  local server only).
