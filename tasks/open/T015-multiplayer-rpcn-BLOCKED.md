# T015: Multiplayer through the community online mod (RPCN) — BLOCKED, lowest priority

Status: open
Owner: -
Touches: docs/online.md (multiplayer section), src/overrides/net_*.cpp, patches/ps3recomp/T015-*.patch (libs/network/**)
Reads: docs/game-profile.md "Versions and updates"

## BLOCKED — do not claim
Lowest priority (user, 2026-10-18: "multiplayer should be last priority, mainly focus on
offline play"). **The user must first get permission from the operators of the community
servers** to use them with this recomp, since it is heavily AI-assisted. Until the user says
so on the record, no agent connects to RPCN or any community server, nor works on this task.

## Goal (once unblocked)
The user's chosen route is the open-source community one: "SARPBC Online Mod 1.15" by kuxir97
(over 1.02 → 1.04), playing through RPCN (open-source PSN replacement,
github.com/RipleyTom/rpcn; setup at github.com/eiddor/sarpbc-online). Find out what the
mod changes, which NP APIs it uses, and what the runtime needs to talk to RPCN (native RPCN
client, or a bridge to ps3recomp's psnr); implement it.

## Done when
Two instances play an online match through an approved server.

## Log
