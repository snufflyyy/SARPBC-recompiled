# T014: Robust offline play — online paths fail fast and cleanly

Status: open
Owner: -
Touches: docs/online.md (new), src/overrides/net_*.cpp (new), patches/ps3recomp/T014-*.patch (libs/network/** only, offline behaviour)
Reads: docs/subsystems.md (network), analysis/imports_named.json (sys_net, sceNp*, cellNetCtl)

## Goal
**Priority: offline play first** (user, 2026-10-18). The official servers are gone, so
every online path must fail fast and cleanly offline: cellNetCtl "not connected", sceNp
signed out, no long socket or DNS timeouts in menus, no hang when the player picks an
online mode. Document what the game does in each online menu and on each NP call. Local
split-screen (up to 4 cellPad ports) is the offline multiplayer: check that it works.

**Do not connect to any external server** (RPCN, psnr instances, community servers). That
is T015, which is blocked on the user's permission.

## Done when
docs/online.md describes the offline behaviour with evidence; online menus fail fast
(measured); split-screen checked; fast-fail overrides implemented where needed.

## Log
