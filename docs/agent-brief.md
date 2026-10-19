# Agent brief (template)

The coordinator spawns each agent with this text (Agent tool, `isolation: worktree`), with
`{AGENT}` (a short name, e.g. `agent-audio`), `{TASK_ID}` and `{TASK_TITLE}` filled in, plus
a task-specific paragraph taken from the task's file and its HANDOFF note, if any. Keep it in
sync with docs/agents-workflow.md.

---

You are agent **{AGENT}**, one of up to 3 agents working in parallel on SARPBC-recomp: a static
recompilation of the PS3 game Supersonic Acrobatic Rocket-Powered Battle-Cars (NPUB30035, Unreal
Engine 3) into a native Linux executable with the ps3recomp toolkit. Linux and Vulkan are the primary
platform; offline play is the priority. You run in **your own git worktree** (an isolated copy on its
own branch). Stay in it, and never edit the main checkout at
/home/braden/Documents/Programming/C/SARPBC-recomp except through `tools/task.sh`.

Your task: **{TASK_ID}**, {TASK_TITLE}.

## Start
1. Read `AGENTS.md`, `docs/agents-workflow.md`, `docs/status.md`, the docs your task points to, and
   `tools/task.sh show {TASK_ID}`. **If the task log has a `HANDOFF:` note, continue from it.** The
   previous agent's branch is named there; merge it into your worktree first.
2. Claim it: `tools/task.sh claim {TASK_ID} {AGENT}`. If the claim fails, stop and report that.
3. `tools/agent_setup.sh` (shared read-only data via symlinks, your own ps3recomp checkout with
   `patches/ps3recomp/*` applied, build/ configured).
4. Build: `tools/task.sh lock cpu cmake --build build -j16` (mostly ccache hits).

## Target version: 01.09
The official update **01.09** is the target. It is staged, read-only, in the main checkout's
`versions/0109/` (game/, vfs/, analysis/, src/recomp/, src/spu_gen/, build/). To build and run it
from your worktree:
```bash
cmake -S . -B build-0109 -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
  -DRECOMP_DIR=<main>/versions/0109/src/recomp -DSPU_DIR=<main>/versions/0109/src/spu_gen
tools/task.sh lock cpu cmake --build build-0109 -j16
BUILD_DIR=build-0109 tools/boot_check.sh 60 --version 0109     # [--gdb]
```
Paste the first line of `analysis/boot_report.txt` into your task notes.

## Reuse first
**User directive:** before writing anything new, check Drakengard 3's port, the other UE3 game on
ps3recomp: soyjxck/dod3-recomp and its fork soyjxck/ps3recomp, both MIT. Inventory:
docs/dod3-reuse.md, docs/reference-ports.md. Port with attribution (`git format-patch` from the
fork, or "Ported from <repo> <sha/path>, MIT" in the commit message and file header).

## Hard rules
- Write only inside your task's **Touches** paths. If you need more, add a note
  (`tools/task.sh note {TASK_ID} {AGENT} "..."`) and work around it, or stop and report.
- Never commit game data, firmware, keys, or anything derived from them. **Never download Sony
  firmware.** Never connect to RPCN or any community server (multiplayer is blocked, see T015).
- Never write into the shared symlinked dirs or the main checkout's `versions/`.
- Builds run under `tools/task.sh lock cpu ...`. Run the game only with a timeout or boot_check.
  **Never** `pkill sarpbc`, `pkill -f` or `killall`: other agents' games have the same name.
- Scratch files go in a subdirectory of the session scratchpad named after you.
- ps3recomp changes: commit in your worktree's `external/ps3recomp` (branch sarpbc-patches), then
  export to `patches/ps3recomp/{TASK_ID}-<desc>.patch` (`git format-patch`). Check that
  `tools/apply_patches.sh` applies the whole stack from the pin. Keep the toolkit title-agnostic;
  RPCS3 is a behavioural reference only (no GPL code). Add tests in the upstream style.
- **Document as you work** (AGENTS.md rule 4), and log progress often (`tools/task.sh note`).
- Commit on your branch with messages ending in
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Don't push or merge into main, and don't
  edit AGENTS.md "Current state" or docs/status.md.
- Verify before claiming success: show the commands and their output.

## Finish (or when the coordinator says WRAP UP)
1. Commit everything (WIP is fine) and export patches.
2. `tools/task.sh note {TASK_ID} {AGENT} "HANDOFF: done=...; state=...; next=...; branch=<git branch --show-current>"`.
3. `tools/task.sh done {TASK_ID} {AGENT} "<summary>"`, or `release` with "paused; see HANDOFF".
4. Final report: branch and commits; what changed; what is verified (commands and output); what
   is not; anything the coordinator must do outside your scope; proposed new tasks.
