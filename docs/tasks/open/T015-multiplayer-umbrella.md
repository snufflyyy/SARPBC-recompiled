# T015: Multiplayer: port the community online mod to the 01.09 recomp (umbrella, do not claim)

Status: open
Owner: -
Priority: blocked
Touches: docs/multiplayer.md, docs/multiplayer-protocol.md, docs/multiplayer-mod.md
Reads: docs/multiplayer.md, docs/online.md, docs/workflow.md

## Goal
**User, 2026-10-23: "port the custom multiplayer to our 1.09 recomp", using the community server unmodified,
hosted locally for testing.** The user's permission covers servers they run on this machine or their LAN; public
RPCN and community-hosted servers stay out of scope until the user says so on the record (the original blocker of
this task, 2026-10-18). Stay on 01.09 (user, 2026-10-18): do not switch the port to the mod's 1.04 base (probably
the same build, T068 checks).

This is the umbrella: the research and the plan are in docs/multiplayer.md; work happens in the sub-tasks, in
priority order:

| Task | What |
|---|---|
| T066 | read the callproc web protocol out of the 01.09 client; probe tool (starts now) |
| T067 | local rig: config-driven redirect, port map, two instances |
| T068 | the user's mod + server files, mod diff, decision D1 (is RPCN needed) |
| T069 | NP online identity (manager ONLINE, ticket, friends, presence, lookup) |
| T070 | login and online lobby against the real local server |
| T071 | two recomps play a match peer to peer |
| T072 | RPCN client (conditional on D1; blocked until then) |
| T073 | edges: voice, stats, leave/abandon, known mod crashes |
| T074 | one-command two-client check, docs, credits |

## Done when
Two instances play an online match through the user's local server (T071), `tools/verify.sh --scenario online`
passes (T074), docs and credits are in place. Close this task with a summary when T074 is done.

## Log
- 2026-10-18 user: multiplayer last priority, offline play first; permission from the server operators needed.
- 2026-10-23 user: allowed because the server is hosted locally; asked for research and a plan split into tasks
  in docs/ (docs/multiplayer.md), then "port the custom multiplayer to our 1.09 recomp".
- 2026-10-23 claude: researched; findings in docs/multiplayer.md (the client's matchmaking is an HTTP stored-
  procedure web service at `sarb.psyonix.com/v001/callproc.php`, plain HTTP on port 80, verified in a sandboxed
  run; NP is only identity/friends/presence/signaling; RPCN may or may not be needed). Created T066-T074.
