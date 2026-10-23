# T071: Two recomps play a match peer to peer

Status: open
Owner: -
Priority: blocked
Touches: patches/ps3recomp/NNNN-np-signaling-p2p.patch (libs/network/sceNpSignaling.c, sysNet.c, np_*), src/overrides/net_p2p.cpp (new), docs/multiplayer.md, docs/subsystems.md
Reads: docs/multiplayer.md (sections 4, 6, 8, 9), external/ps3recomp/docs/ONLINE.md (two players on one machine, P2P sockets), tasks T067-T070

## Goal
Part of the multiplayer port (umbrella T015). After T070 both clients know the host. Now carry the **game
traffic**: UE3's `IpDrv.TcpNetDriver` (UDP datagrams, `[URL] Port=7777`, 30 Hz) over sys_net, with
`bShouldUseNatTraversal=true`.

1. Find out which socket types the game uses for gameplay (`socket(2, 2, 17)`? P2P type 6 via the signaling
   port?) and how `sceNpSignalingActivateConnection` / `GetConnectionInfo` / the extended handler events feed
   it. Trace with `PS3_NET_TRACE=1` between two instances.
2. Signaling HLE (title-agnostic): `ActivateConnection(npid)` → established event with the peer's address from
   the T069 directory (or RPCN, T072); `GetConnectionInfo` (address, port, status), `GetLocalNetInfo`,
   `Deactivate/Terminate`, context and handler lifetime. Mirror psnr's tested timing rules (deferred
   "established", sin_vport semantics: external/ps3recomp/docs/ONLINE.md).
3. `TestNat` / `AddNatAndGetPingUtility` / `RemoveAllUnusedNats` natives (`OnlineGameInterfaceImpl_PS3`):
   NAT type, ping to the host for the server list.
4. One machine first (127.0.0.1, ports per instance), then two machines on the LAN (private ranges are allowed by
   the sandbox).
5. Play: lobby → car select (`CARSELECTIONLOBBY0-3`) → arena → goals → round end → results → back to the menu.
   Check clocks, ball and car state agree on both screens; host leaving, client leaving, and a 4-player lobby.

## Done when
Two instances play a full match to the results screen; scores and clocks match on both; no desync alerts or
null-access alerts in the boot report; leave and host-quit return both to the menu. Captures from both
instances in the task log (thumbnails, not PPMs: disk is tight). `tools/verify.sh` OK.

## Log
- 2026-10-23 claude: created from the multiplayer research. External prior art: ps3recomp's psnr two-instance
  Simpsons run (set `PS3_VERBOSE=0`, otherwise two instances crawl).
- 2026-10-23 user: "the server isn't open source like i assumed. just postpone the multiplayer plan." Set to blocked; resume when the user supplies the server (or decides on a different approach).
