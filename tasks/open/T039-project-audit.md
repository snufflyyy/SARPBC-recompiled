# T039: Project audit: cleanliness, tidiness, extensibility (after the SPU easy wins)

Status: open
Owner: -
Priority: 11
Touches: docs/**, tools/** (scripts and their docs), patches/ps3recomp/README.md, src/overrides/** (comments and structure only), tasks/ (stale claims, priorities, closing done work). **Claim it only when no other task is claimed**: it touches everyone's files
Reads: AGENTS.md, every docs/*.md, tasks/, `git log`

## Goal
Step 3 of the user's plan (docs/status.md "Resume here"): once the SPU easy wins (T033, T030,
T029, T032, T031, T025) are done or parked, audit the project read-only, then fix what you find.
- Docs vs. reality: every command, path, env var and address in AGENTS.md and docs/ still exists
  and still means what the doc says; the docs index lists every doc.
- Patch stack: `tools/apply_patches.sh` applies cleanly from the pin; README table matches the
  files; no stale `T###-*.patch` names; each patch's upstream status is current.
- Scripts in tools/: usage headers are accurate, no dead scripts, shellcheck-clean where cheap.
- src/overrides/: each override says why, with the guest address; nothing that belongs upstream.
- Task board: every open task still makes sense, has a Priority, and its Touches are current;
  close what is done; release stale claims.
- Left-over worktrees and branches under `.claude/worktrees/` (subagent era, all merged): remove.

## Done when
Findings logged on this task, fixes committed, and docs/status.md + the AGENTS.md current-state
line updated.

## Log
