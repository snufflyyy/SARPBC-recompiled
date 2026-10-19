# T015: Multiplayer through the community online mod (RPCN) — BLOCKED, lowest priority

Status: open
Owner: -
Priority: blocked
Touches: docs/online.md (multiplayer section), src/overrides/net_*.cpp, patches/ps3recomp/T015-*.patch (libs/network/**)
Reads: docs/game-profile.md "Versions and updates"

## BLOCKED — do not claim
Lowest priority (user, 2026-10-18: "multiplayer should be last priority, mainly focus on
offline play"). **The user must first get permission from the operators of the community
servers** to use them with this recomp, since it is heavily AI-assisted. Until the user says
so on the record, no agent connects to RPCN or any community server, nor works on this task.

## Goal (once unblocked)
**Stay on 01.09** (user, 2026-10-18): do not switch the port to the mod's 1.04 base. Port
the community multiplayer mod ("SARPBC Online Mod 1.15" by kuxir97, made for 1.02 → 1.04,
playing through RPCN; setup at github.com/eiddor/sarpbc-online) onto 01.09:
1. With the user-supplied mod packages, diff the mod against 1.04 (EBOOT patches, packages,
   UnrealScript, config) to get a precise list of what it changes and why.
2. Re-apply those changes to 01.09's EBOOT/packages: port-side overrides keyed to 01.09
   addresses, package/UnrealScript edits through an overlay (Drakengard 3's tools/ue3/
   pkgpatch approach), never by editing the original files.
3. Give the runtime what RPCN play needs (native RPCN client, or a bridge to ps3recomp's psnr).
4. Credit kuxir97 and the mod in the docs and the UI where appropriate.

## Done when
Two instances play an online match through an approved server.

## Log
