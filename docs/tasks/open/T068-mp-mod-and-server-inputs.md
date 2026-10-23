# T068: Get the mod and the server from the user, diff the mod against 01.09, decide whether RPCN is needed

Status: open
Owner: -
Priority: blocked
Touches: docs/multiplayer-mod.md (new), docs/multiplayer.md, docs/multiplayer-protocol.md, tools/mod_diff.py (new), tools/test_mod_diff.py (new)
Reads: docs/multiplayer.md (sections 2, 3, 5, 9, 10), docs/game-profile.md "Versions and updates", docs/pipeline.md (tools/extract.sh), docs/graphics-menu.md (package tools)

## Goal
Part of the multiplayer port (umbrella T015). **Starts with a question to the user**: the mod's `.pkg` files
(`SARPBC Online Mod 1.15.pkg`, the 1.04 PKG, the optional stuttering fix) and the server (software or source for
the web service the mod talks to, RPCN if used, how it is started, address/ports, a test account). Not on this
machine (docs/multiplayer.md section 10). Do not start the diff before they are here; T066 does not wait for this.

1. Extract the packages with the same path as `tools/extract.sh` (ps3recomp `tools/pkg_extract.py`, RAP where
   needed) into a **git-ignored** directory (`mods/`, add it to `.gitignore` and the lint no-game-data check).
2. `tools/mod_diff.py`: compare an installed tree against `versions/0109/`: file list, hashes, EBOOT/SPRX byte
   diff (as ranges, no disassembly dumped into git), every UE3 package function and default property that
   differs (via `tools/ue3`), COALESCED.INI/INT keys, PARAM.SFO. Output is a text report; the report goes in
   `docs/multiplayer-mod.md` **summarised by purpose** (no game bytes, no key values).
3. **Is mod base 1.04 the same build as 01.09?** Compare hashes (decrypted EBOOT, packages). Record yes/no and
   what differs. If they differ in code, stop and ask the user (a second lift is their call).
4. Identify the **server**: its name, protocol, how the mod redirects `sarb.psyonix.com` (patched URL in the
   EBOOT, a package default, a DNS trick), whether the mod's client sends a different version string/`CallProcKey`
   /`DB=`, and what the mod changes in the menus (Unranked Match, Join A Friend) and input.
5. **Decision D1**: is RPCN needed (tickets, friends, presence, signaling) or is the web service enough? Evidence
   from the diff and the server's source/config. Write the answer at the top of docs/multiplayer.md and move
   T069/T072 priorities accordingly.
6. Update docs/multiplayer-protocol.md with the server-side view (procedure set, response format, version rule).

## Done when
`docs/multiplayer-mod.md` lists every difference between the mod and 01.09 with its purpose; the server is
identified and can be started locally by the user's instructions; D1 is answered with evidence; the version
string and key handling the server expects are known; nothing from the mod is tracked by git (`tools/lint.py`).

## Log
- 2026-10-23 claude: created from the multiplayer research. Blocked on the user's files, not on any agent.
- 2026-10-23 user: "the server isn't open source like i assumed. just postpone the multiplayer plan." Set to blocked; resume when the user supplies the server (or decides on a different approach).
