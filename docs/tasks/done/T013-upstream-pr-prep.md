# T013: Prepare upstream contributions (local branches + PR texts, no pushing)

Status: done
Owner: claude
Priority: 24
Touches: docs/upstream.md (new)
Reads: patches/ps3recomp/*, patches/ps3recomp/README.md, src/main.cpp (VM fix), tools/split_toc_stubs.py, src/overrides/edgezlib.cpp

## Goal
We fix general ps3recomp problems that other ports will hit: Linux guest VM alignment in
the template/boot_main, the trophy completion ordering, TOC-stub boundaries (T005), the
missing _cellSpursLFQueuePushBody, and upstream unit tests that only link on macOS. For each,
write the upstream PR as it would be filed: title, motivation with evidence, the diff
against upstream master (not our pin, so check whether master has moved), and tests. Keep
them as text and local branches only. **Do not push, fork, or open anything on GitHub.**
That needs the user's approval: ask first.

## Done when
docs/upstream.md lists each contribution with status, a ready-to-file description, and the
local branch or patch that implements it, rebased on current upstream master.

## Log
- 2026-10-21 02:01 claude: claimed
- 2026-10-21 02:01 claude: docs/upstream.md: all 58 patches grouped into 10 PR drafts (motivation, evidence, patch table). Upstream master == our pin (749182e) so no rebase needed. NOT filed: awaiting the user's approval.
- 2026-10-21 02:01 claude: DONE: 
