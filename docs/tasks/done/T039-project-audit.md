# T039: Project audit: cleanliness, tidiness, extensibility (after the SPU easy wins)

Status: done
Owner: claude
Priority: 11
Touches: docs/**, tools/** (scripts and their docs), patches/ps3recomp/README.md, src/overrides/** (comments and structure only), docs/tasks/ (stale claims, priorities, closing done work). **Claim it only when no other task is claimed**: it touches everyone's files
Reads: AGENTS.md, every docs/*.md, docs/tasks/, `git log`

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
- 2026-10-20 02:07 claude: claimed
- 2026-10-20 02:22 claude: Findings (all fixed unless noted): (1) data: no game data/generated code tracked or in history; largest tracked file < 200 KB. (2) patches: stack applies from the pin and equals sarpbc-patches; README rows stale (candidate list, 0005 out of order, git am line); 4 upstream tests broken by our patches: test_ppu_entry_arguments (0004), test_spurs_scheduler (0015), test_lwcond_layout (0019), test_spu_taskset_elf_flags (0038, mine) -> fixtures fixed inside those patches (fixup + autosquash in a scratch clone, then reset --mixed so no rebuild); 73/73 test scripts pass. Upstream v0.16.0 (749182e): 32/40 files replay, 8 conflict -> T043 (was T042 in the audit). upstream test_ppu_lift.py rewrites tracked scratch/ppu_conformance.cpp (noted in README To upstream). (3) tools: hle_coverage.py crashed with defaults (ppu_hle_nids.cpp now in the build dir); shellcheck -S warning had 8 warnings (fixed); pyflakes clean; 5 scripts not executable; build.sh printed an error reading a missing stamp. (4) docs: ~30 stale T### patch names, ppu_hle_nids/coordinator wording, other-repo paths; status Resume here/phases/open questions stale; AGENTS layout was 'planned'. (5) board: uniform fields; T024/T025/T035/T041 met done-when -> closed; T036/T040 premises updated; T043 created (was T042; renumbered at the merge with the Wayland T042). (6) worktrees: no .claude/worktrees here; removed .worktrees/claude (merged); .worktrees/pi kept (clean, merged, 1.4 GB, its analysis/ holds the T029 baseline evidence). Guard: tools/lint.py [--tests], run by merge_to_main.sh.
- 2026-10-20 02:22 claude: DONE: audit run; fixes committed (see findings note); tools/lint.py [--tests] added and wired into merge_to_main.sh; status.md and AGENTS.md updated. Open follow-ups: T043 (pin bump), pi's worktree left in place for the user.
