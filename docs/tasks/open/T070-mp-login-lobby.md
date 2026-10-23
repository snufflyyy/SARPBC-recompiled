# T070: Login and online lobby against the real local server

Status: open
Owner: -
Priority: 14
Touches: src/overrides/online_*.cpp (new), tools/mp_overlay.py (new, package/config overlay for the mod's changes), tools/test_mp_overlay.py (new), docs/multiplayer.md, docs/multiplayer-protocol.md, docs/multiplayer-mod.md
Reads: docs/multiplayer.md, docs/multiplayer-protocol.md, docs/multiplayer-mod.md, docs/graphics-menu.md (overlay and package patching), tasks T066-T069

## Goal
Part of the multiplayer port (umbrella T015). Against the **unmodified** local server, take the game from the
main menu through "Logging in..." to the online menu and a lobby, and host/find a match entry:

1. Apply the mod's *intent* to 01.09 through the existing overlay machinery (`PS3_VFS_OVERLAY`, `tools/ue3`,
   the `tools/graphics_menu_patch.py` pattern): version strings, server/DB names, menu entries ("Unranked Match",
   "Join A Friend" if the mod adds them), input tweaks. Originals are never edited; the overlay is built at run
   time from the player's own files plus a patch description that holds no game bytes.
2. Whatever the client needs at the native level that the mod changes (T068's list) as `src/overrides/` entries
   keyed by 01.09 guest address, each with the reason and the address in a comment.
3. Boot request (`GetOnlineVariables`), login/registration, the online menu, **host registration + heartbeat**
   (the host appears in the server list), search results, leave/destroy. Every non-success reply the server can
   give maps to a message and a way back to the menu (no hang on "Logging in...", timeouts bounded).
4. Settings-live rule (AGENTS.md): the server and account can be changed without restart where a live route
   exists; if none, mark the row "(restart to apply)" and say why.

## Done when
From the main menu, Play Online → Unranked Match reaches the lobby with the local server, and a second client
(second instance) sees the first one's game in its list. Evidence: both boot-check logs and two captures.
Failure paths verified (server down, wrong version, empty/garbled reply) return to the menu without a stall.
`tools/verify.sh` OK.

## Log
- 2026-10-23 claude: created from the multiplayer research.
