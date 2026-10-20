# T049: Make patch builds and task-board mutations predictable

Status: open
Owner: -
Priority: 3
Touches: build.sh, tools/apply_patches.sh, tools/task.sh, tools/test_build.py (new), tools/test_task.py (new), docs/project-audit.md (A04/A10), docs/workflow.md
Reads: docs/project-audit.md, docs/pipeline.md, docs/workflow.md

## Goal
Address T046 tooling hazards: verify patched-tree identity rather than commit count; fail closed on dirty mismatched runtimes; preflight before checkout mutations; lock the entire per-checkout build transaction. Serialize task ID allocation/mutations and verify owners.

## Done when
Throwaway source-only repository fixtures prove dirty refusal leaves checkout unchanged, wrong equal-length patch histories are rejected, concurrent builds cannot mutate one build tree together, task IDs stay unique under concurrency, and non-owners cannot complete/release tasks. Full lint/tests pass without modifying other agents' work.

## Log
