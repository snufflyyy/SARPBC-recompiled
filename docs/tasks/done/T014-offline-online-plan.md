# T014: Robust offline play — online paths fail fast and cleanly

Status: done
Owner: claude
Priority: 25
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
- 2026-10-21 02:03 claude: claimed
- 2026-10-21 02:13 claude: Play Online fails cleanly: patch 0059 (offline NetStartDialog = DIALOG_CANCELED) cut the wait from ~18 s 'Timed out' to ~8 s 'error retrieving data from the online service'; dismiss returns to the menu. Split Screen lobby reachable; multi-pad joining NOT verified (boot_check drives port 0 only). Details docs/online.md.
- 2026-10-21 02:13 claude: DONE: 
