# T050: Review Antigravity loading-screen orientation patch

Status: claimed
Owner: pi
Priority: 1
Touches: docs/t038-review.md (new), AGENTS.md (docs index), docs/status.md (review note only)
Reads: docs/subsystems.md (Graphics), docs/tasks/done/T038-loading-screen-flipped.md, patches/ps3recomp/0050-loadscreen-passthrough-orientation.patch

## Goal
Review Antigravity's already-merged T038 implementation, rendering contract, test coverage and captures. Do not silently merge twice or modify its renderer behavior without evidence.

## Done when
Record prioritized correctness findings and verified evidence, identify remaining merge work (if any), and file actionable follow-ups for issues that prevent general upstream acceptance.

## Log
- 2026-10-20 20:01 pi: claimed
- 2026-10-20 20:01 pi: User requested review/merge of Antigravity changes. T038 is already on main as ba70ca3 and preserved by T047; no unmerged branches exist. Reviewing implementation, backend contracts, tests and captures before making a readiness claim.
- 2026-10-20 20:07 pi: Confirmed P1 counterexample in analysis/t050-counterexample.log: synthetic MOV HPOS,v0; MOV TEX0,v8 and the same program plus a terminating NOP decompile to byte-identical HLSL but bind opposite Y transforms (-1,-0.5 versus +1,+0.5). Existing neutral draw-engine fixture still passes. Shared runtime selector checks length only, not opcodes/constants/backend. No renderer changes made.
- 2026-10-20 20:07 pi: boot_check 2026-10-20 20:04 v01.09 9c72623 120s: STALLED since 100.4s (frames still presented) | last open PYRAMID_COLLECTBOOST.XXX@56.2s | pkgs 15 (PYRAMID_COLLECTBOOST last) | zlib 3726 | dumps 49 lit 49 distinct 45 | flips 2630 | threads 19/9 alive | unresolved 0
- 2026-10-20 20:07 pi: Fresh 120s capture 20261020-200217-1296812: first lit frame is upright Loading text; last frame is upright tutorial arena/car/HUD. Final 10s have four distinct dumps, so STALLED is no-new-log-shape heuristic, not a render freeze. No new FPS or other-platform claim.
- 2026-10-20 20:09 pi: Review written in docs/t038-review.md. F01 (P1) is confirmed via semantic-equivalence counterexample; F02 (P2) corrects unsupported projection-dependent glslang rationale. Follow-up T051 is open at priority 1. Existing renderer suite passes; runtime patch remains unchanged. No additional implementation merge is necessary; merging documentation/board only.
