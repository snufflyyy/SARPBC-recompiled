# T074: One-command two-client online check, docs and credits

Status: open
Owner: -
Priority: blocked
Touches: tools/mp_check.sh (new), tools/verify.sh, tools/boot_check.sh, tools/test_mp_check.py (new), docs/multiplayer.md, docs/online.md, docs/status.md, AGENTS.md, README.md
Reads: docs/multiplayer.md, docs/workflow.md, tools/verify.sh, tools/boot_check.sh (--scenario)

## Goal
Part of the multiplayer port (umbrella T015). Make the whole thing repeatable by any agent:

1. `tools/mp_check.sh`: start the local server stack (`tools/mp_local.sh`), two clients with separate saves and
   ports under the `boot` lock (both of them: the lock is per machine), scripted pads (`--pad`) to host and join,
   wait for the arena, play a few seconds, assert both reach it, then stop **only its own processes**. Output:
   one summary line like `boot_check` plus per-client reports in `analysis/mp_check/`.
2. `tools/verify.sh --scenario online` calls it; the default verify stays offline and fast.
3. Docs: replace the "plan" language in docs/multiplayer.md with the working procedure; docs/online.md
   (offline) points to it; docs/status.md and the AGENTS.md current-state line; README mention with the user
   instructions (what to install, where the mod files go, which ports).
4. Credits: kuxir97, eiddor, SARPBC+ community, RPCN (RipleyTom) in the docs and, if the game's credits page is
   patchable cheaply, there too.
5. Policy text in docs/workflow.md: local servers only; the public RPCN/community servers stay out of scope until
   the user says so on the record.

## Done when
`tools/verify.sh --scenario online` prints PASS on a clean checkout with the local server, two clients reach the
arena and return to the menu; the docs let a new agent reproduce it in minutes; lint clean.

## Log
- 2026-10-23 claude: created from the multiplayer research.
- 2026-10-23 user: "the server isn't open source like i assumed. just postpone the multiplayer plan." Set to blocked; resume when the user supplies the server (or decides on a different approach).
