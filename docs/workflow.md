# Workflow — the task board, for agents the user starts

The user starts every agent themselves (Claude Code, pi, Antigravity, ...): one, or several at
once. **No agent spawns subagents** (Claude Code's Agent tool, workflows, or the like) unless the
user asks: that used too much usage (user, 2026-10-19). There's no coordinator either. Each
agent picks its own task from the board, works in its own worktree, and merges its own work.

## The pieces

| Piece | Where | What it is for |
|---|---|---|
| Task board | `docs/tasks/{open,claimed,done}/T###-slug.md` in the **main checkout** | One file per task: priority, scope (**Touches**), reading list (**Reads**), goal, done-when, and a log of findings and HANDOFF notes. `tools/task.sh` always acts on the main checkout's board, from any worktree. **Never commit `docs/tasks/` from your worktree**: `merge_to_main.sh` commits it |
| Queue | each task's `Priority:` line | Lower goes first; `blocked` is never picked. `tools/task.sh next` prints the next open tasks and what is claimed |
| Claiming | `tools/task.sh claim <ID> <agent>` | An atomic rename from `open/` to `claimed/`: exactly one agent gets a task. If it fails, take another |
| Worktree per agent | `.worktrees/<agent>`, branch `<agent>/work` (`tools/agent_setup.sh <agent>`) | One agent's half-finished edit never breaks another agent's build. The main checkout stays on `main` and only receives merges |
| Shared, read-only | `game/ vfs/ .venv/ src/recomp/ src/spu_gen/ versions/` | Symlinked or looked up from the main checkout. **Never write into them** |
| Compiler cache | `<main>/.cache/ccache` | Shared by every worktree (`CMakeLists.txt`); a fresh worktree's build is mostly cache hits |
| Locks | `tools/task.sh lock <name> <cmd...>` (flock on `<main>/.locks/<name>.lock`) | `cpu`: builds, one at a time (each uses all 16 threads). `boot`: game runs, one at a time. `merge`: merging into main |

**Agent names**: short and lowercase, the harness plus a number if you run two of the same:
`claude`, `pi`, `antigravity`, `pi-2`. Use the same name for the worktree, claims and notes.

## Procedure

1. Read AGENTS.md, [status.md](status.md) "Resume here", then `tools/task.sh next`. Take the
   first open task whose **Touches** doesn't overlap a claimed task's (or the one the user
   names). Read it with `tools/task.sh show <ID>`; **if its log has a `HANDOFF:` note, continue
   from there.**
2. `tools/task.sh claim <ID> <agent>`.
3. Once per agent, from the main checkout: `tools/agent_setup.sh <agent>`. It creates
   `.worktrees/<agent>` on branch `<agent>/work`, links the shared data, applies the patch stack
   to its own `external/ps3recomp` and configures `build/` (01.02) and `build-0109/` (01.09,
   the target). **Work only inside that worktree from now on.** For a later task in the same
   worktree, just keep going: the branch is level with main after each merge.
4. Build and run, from the worktree:
   ```bash
   tools/task.sh lock cpu cmake --build build-0109 -j16
   tools/task.sh lock boot env BUILD_DIR=build-0109 tools/boot_check.sh 60 --version 0109   # [--gdb]
   ```
   Paste the first line of `analysis/boot_report.txt` into the task log. Run the game only with
   a timeout or through `boot_check`. **Never** `pkill sarpbc` / `pkill -f` / `killall`: other
   agents' games have the same name. To attach gdb, use the PID your own `timeout` started
   (`pgrep -P <timeout pid>`).
5. Stay inside the task's **Touches**. If you need something outside it, log a note
   (`tools/task.sh note <ID> <agent> "need X in Y because Z"`). Then work around it, or make the
   change if no claimed task touches that path, and say so in the log.
6. Log as you go: `tools/task.sh note <ID> <agent> "..."` (findings, dead ends, numbers).
   Anything that isn't written down is lost when the context runs out.
7. **Document as you work** (AGENTS.md rule 4): facts go into the matching `docs/*.md`, in the
   same commit as the code that relies on them.
8. ps3recomp changes: commit inside your worktree's `external/ps3recomp` (branch
   `sarpbc-patches`), export with `git format-patch` to `patches/ps3recomp/T###-<desc>.patch`
   (`T###-1-...`, `T###-2-...` for several, in apply order), add a row to its README table, and
   check that `tools/apply_patches.sh` applies the whole stack. The merge gives them numbers.
9. Commit on your branch, ending messages with your harness's attribution line, if it has
   one. Don't push by hand: your branch stays local, and `merge_to_main.sh` pushes `main`.

## Finishing a task

1. Verify it: build, boot or test, and keep the command and its output for the log.
2. Add one bullet to the newest [status.md](status.md) log entry, or start today's entry. Update
   "Resume here" and the AGENTS.md current-state line if the headline changed. Keep these edits
   small: other agents edit the same lines.
3. Commit, then merge into main from your worktree:
   `tools/task.sh lock merge tools/merge_to_main.sh`. The script merges main into your branch
   and stops on conflicts (resolve them, rebuild, verify, rerun). It renumbers your patches,
   checks that the stack applies, fast-forwards main, commits the board, and pushes `main` to
   `origin` (https://github.com/snufflyyy/SARPBC-recompiled). If only the push fails, the merge
   is done locally: fix the cause (network, auth) and rerun the script.
4. `tools/task.sh done <ID> <agent> "<summary: what changed, what's verified, what's left>"`.
   Add follow-up tasks with `tools/task.sh new <slug> <title>` (fill in Priority, Touches,
   Reads, Goal, Done when).
5. Take the next task (`tools/task.sh next`).

## Pausing and resuming

**Pausing** (usage running low, end of session): commit WIP on your branch and write a HANDOFF
note: `tools/task.sh note <ID> <agent> "HANDOFF: done=...; state=...; next=...; branch=<agent>/work"`.
Then `tools/task.sh release <ID> <agent> "paused; see HANDOFF"`. Merge only if the work is
verified and leaves main working; otherwise leave it on the branch (the note names it).

**Resuming:** start any agent in the main checkout and say:
> Read AGENTS.md, docs/status.md "Resume here" and docs/workflow.md, then take the next task
> from `tools/task.sh next`.

To run several at once, start each one with that prompt and a different agent name. Stale
claims (an agent that died) show up in `tools/task.sh list` with their last log time. Release them
with `tools/task.sh release <ID> <agent> "stale"`; the HANDOFF note, if any, names the branch
that holds the work.

## Rules for every agent

- **Target version 01.09** (`versions/0109/` in the main checkout: game, vfs, analysis,
  src/recomp, src/spu_gen, build). Relifting the shared tree is the user's call: a task that
  needs a different lift copies `src/recomp` into its worktree and points `-DRECOMP_DIR` there.
- **Reuse first** (user directive): before writing anything new, check Drakengard 3's port,
  soyjxck/dod3-recomp and its fork soyjxck/ps3recomp (both MIT). Inventory: docs/dod3-reuse.md,
  docs/reference-ports.md. Port with attribution ("Ported from <repo> <sha/path>, MIT" in the
  commit message and file header, or `git format-patch` from the fork).
- Never commit game data or anything derived from it (AGENTS.md rule 1). **Never download Sony
  firmware.** Never connect to RPCN or any community server (multiplayer is blocked, T015).
- Keep the toolkit title-agnostic. RPCS3 is a behavioural reference only (no GPL code). Add
  tests in the upstream style.
- Verify before claiming success: show the command and its output.
- Scratch files go in your worktree's `analysis/` (git-ignored) or a temp dir named after you,
  never at the top of a shared directory.

## History

On 2026-10-18/19 one Claude Code session ran up to 5 subagents (in worktrees under
`.claude/worktrees/`) and acted as their coordinator. Task logs still name those agents
(`agent-audio`, `agent-gcm`, ...) and their HANDOFF `branch=` fields. **All of those branches
are merged into `main`**, so ignore the branch field on those notes. Notes that point at a file
"in this worktree" or in an agent's scratchpad refer to copies that no longer exist. The one
capture that mattered (T028's main menu) is in
`captures/boot_check/20261019-111110-397302-T028-main-menu/`.
