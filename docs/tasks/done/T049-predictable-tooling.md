# T049: Make patch builds and task-board mutations predictable

Status: done
Owner: claude
Priority: 3
Touches: build.sh, tools/apply_patches.sh, tools/task.sh, tools/test_build.py (new), tools/test_task.py (new), docs/project-audit.md (A04/A10), docs/workflow.md
Reads: docs/project-audit.md, docs/pipeline.md, docs/workflow.md

## Goal
Address T046 tooling hazards: verify patched-tree identity rather than commit count; fail closed on dirty mismatched runtimes; preflight before checkout mutations; lock the entire per-checkout build transaction. Serialize task ID allocation/mutations and verify owners.

## Done when
Throwaway source-only repository fixtures prove dirty refusal leaves checkout unchanged, wrong equal-length patch histories are rejected, concurrent builds cannot mutate one build tree together, task IDs stay unique under concurrency, and non-owners cannot complete/release tasks. Full lint/tests pass without modifying other agents' work.

## Log
- 2026-10-20 21:44 claude: claimed
- 2026-10-20 21:44 claude: task.sh: board lock + owner checks added; test_task.py next
- 2026-10-20 21:47 claude: DONE: scratch-worktree tree-identity patch check, dirty refusal, per-checkout build lock, board lock + owner checks; test_build.py/test_task.py pass; lint --tests 0 problems (90 scripts)
