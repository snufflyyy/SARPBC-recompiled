# Working in parallel — task board, worktrees, locks

Several agents (up to **5** at once) work on this port at the same time. This page is
the protocol that keeps them from breaking each other's builds, runs and commits. A
coordinator (the main session) creates tasks, spawns agents, reviews and merges.

## The pieces

| Piece | Where | What it is for |
|---|---|---|
| Task board | `tasks/{open,claimed,done}/T###-slug.md` in the **main checkout** | One file per task: goal, the paths it may touch, a log. `tools/task.sh` always acts on the main checkout's board, from any worktree |
| Claiming | `tools/task.sh claim <ID> <agent>` | An atomic rename from `open/` to `claimed/`: exactly one agent gets a task. If it fails, pick another task; never edit a task you do not own |
| Worktree per agent | your own `git worktree`, your own branch | Source isolation: one agent's half-finished edit never breaks another agent's build |
| Shared, read-only | `game/ vfs/ .venv/ src/recomp/ src/spu_gen/` | Symlinked from the main checkout by `tools/agent_setup.sh`. **Never write into them** (see "Relifting" below) |
| Shared compiler cache | `<main>/.cache/ccache` | Set up by `CMakeLists.txt`; a worktree's first build is mostly cache hits (the lift is 7.5M lines) |
| Locks | `tools/task.sh lock <name> <cmd...>` (flock on `<main>/.locks/<name>.lock`) | Serialize the few shared resources, listed below |

## Agent procedure

1. `tools/task.sh list`, read the task with `tools/task.sh show <ID>`, then claim it:
   `tools/task.sh claim <ID> <your-agent-name>`. If the claim fails, choose another open task.
2. Set up your worktree once: `tools/agent_setup.sh`.
3. Work only inside the task's **Touches** paths. If you need to change something outside
   them, write a note (`tools/task.sh note <ID> <you> "need X in file Y because Z"`) and
   either work around it or stop and report. The coordinator resolves overlaps.
4. Build under the CPU lock: `tools/task.sh lock cpu cmake --build build -j16`.
5. Run the game with a timeout, **never** `pkill sarpbc` / `pkill -f`. Other agents' game
   instances have the same name:
   `timeout -k 5 -s TERM 60 tools/run.sh > analysis/run.log 2>&1`.
   To attach gdb, use the PID your own `timeout` started (e.g. `pgrep -P <timeout pid>`).
6. Log progress as you go: `tools/task.sh note <ID> <you> "..."` (findings, dead ends,
   numbers). Losing context mid-task loses everything that isn't written down.
7. **Document as you work** (AGENTS.md rule 4). Put facts about the game or toolkit
   in the matching `docs/*.md` file in your worktree, in the same commit as the code that
   relies on them. Don't leave it for the end.
8. Commit on your worktree branch with clear messages (end them with the attribution line
   from the system prompt). Do not push and do not merge into `main`; the coordinator does.
9. Finish with `tools/task.sh done <ID> <you> "<one-paragraph summary>"` and say in your
   final report: branch name, commits, what changed, what is verified (with the command
   and output), and what is left open.

## Shared resources and their rules

| Resource | Rule |
|---|---|
| CPU | Builds take the `cpu` lock, so one build runs at a time (each uses all 16 threads) |
| `src/recomp/`, `src/spu_gen/`, `analysis/` in main | Only the coordinator relifts. A task that needs a different lift copies `src/recomp` into its worktree (replace the symlink with a real copy) and sets `-DRECOMP_DIR`; it does not write to the main one |
| `external/ps3recomp` | Each worktree has its own checkout. Changes become a commit there plus an exported patch in `patches/ps3recomp/` named `T###-short-description.patch`. The coordinator renumbers it on merge |
| `AGENTS.md` "Current state", `docs/status.md` | Coordinator only. Agents put status in their task log and their final report |
| `game/`, `vfs/`, keys, RAP | Read-only. Never commit anything derived from the game (AGENTS.md rule 1) |
| `tools/rpcs3/` | Coordinator only |
| The session scratchpad (`/tmp/claude-*/.../scratchpad`) | **Shared by all agents.** Put your files under a subdirectory named after your agent (e.g. `scratchpad/agent-physx/`), never at the top level (one agent's `msg1.txt` overwrote another's) |

## Coordinator procedure

- Create tasks with `tools/task.sh new <slug> <title>` and fill in **Touches** (exclusive
  write scope) and **Reads**. No two open or claimed tasks may share a Touches path.
- Spawn at most 5 agents, each with `isolation: worktree`, and tell each its task ID.
- On completion: review the branch diff, merge into `main`, renumber patches, run
  `tools/apply_patches.sh`, rebuild, re-run, and update `docs/status.md` and the
  AGENTS.md current-state paragraph. Commit the task board (`tasks/`) with the merge.
