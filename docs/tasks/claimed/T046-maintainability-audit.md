# T046: Audit simplicity, hygiene and extension boundaries

Status: claimed
Owner: pi
Priority: 1
Touches: docs/project-audit.md (new), docs/status.md (audit entry only), AGENTS.md (docs index only)
Reads: AGENTS.md, docs/workflow.md, docs/status.md, patches/ps3recomp/README.md

## Goal
Audit correctness, security, performance and maintainability, with emphasis on simple extension boundaries. Read-only review of implementation; do not overlap Antigravity's T038 graphics changes.

## Done when
Evidence-backed findings and a small prioritized cleanup roadmap are documented; available hygiene and regression checks have been run and limitations recorded.

## Log
- 2026-10-20 19:22 pi: claimed
- 2026-10-20 19:22 pi: User-requested in-depth maintainability audit. Read-only implementation review; changes limited to audit documentation. Avoiding T038 graphics scope. Reusing existing clean pi worktree.
- 2026-10-20 19:29 pi: Audit evidence: main fast lint 0 problems; private full stack 67 commits applies. All 85 discovered test scripts return zero, plus 3 omitted nested SDL/Vulkan scripts pass explicitly. Found missing test discovery, optional-data-dependent doc lint, unchecked native zlib spans/size arithmetic and 1024-byte POSIX realpath buffer, count-based build provenance and test cleanup hazards. Report in pi/work docs/project-audit.md. No runtime edits or new game boot.
- 2026-10-20 19:31 pi: Audit report committed on pi/work. Main and private fast lint: 0; private lint required restoring expected local optional paths. All 85 discovered scripts and 3 nested SDL/Vulkan runners returned zero. Follow-up tasks: T047 native bounds, T048 verification, T049 tooling. No runtime implementation changes, game boot, network services or subagents.
