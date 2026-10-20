# T043: Bump the ps3recomp pin to upstream v0.16.0 and rebase the patch stack

Status: open
Owner: -
Priority: 2
Touches: .gitmodules pin (`external/ps3recomp` gitlink), patches/ps3recomp/** (all of it), patches/experimental/**, CMakeLists.txt (only if upstream's build changed), docs/status.md, docs/ps3recomp-primer.md, AGENTS.md key facts. **Claim it only when no other task is claimed**: every build changes under it
Reads: patches/ps3recomp/README.md ("Upstream moved on"), docs/pipeline.md, upstream's CHANGELOG for v0.16.0

## Goal
Found by the T039 audit (2026-10-20): upstream `sp00nznet/ps3recomp` is at v0.16.0 (`749182e`,
117 commits past our pin `39a3629`, 44 merged PRs). Move the pin there and rebase our 40 patch
files (58 commits) onto it.
- Replayed in order onto `749182e` (skipping failures), 32 files apply and 8 conflict: 0013, 0016,
  0017, 0021, 0027, 0032, 0039, 0040. Some of these are upstream merging the same fix: drop ours
  where it did (0002 vs #359 CATEGORY game type, 0013/0014 vs #349 open flags, 0017's small motor
  vs #372, 0032 vs #369/#370 SPU float SIMD). 0039/0040 run into #351 (present on its own command
  buffer): redo them on top of it.
- Upstream perf work that hits the menu frame directly (T040's ~18 ms of CPU): #375 sparse
  texture re-hash (`eng_texture_content_hash`), #357 per-vertex span found once per draw
  (`rsx_vertex_fetch_one`), #348 transfers a pixel at a time. Measure the menu before/after.
- Re-check on the new base: the remaining fork GCM candidates from T024 (0112, 0059/0062,
  0096/0111) and hunk (1) of `patches/experimental/T022-esrb-experiment.diff`.
- Relift both versions only if the lifter changed in a way that matters (`tools/relift.sh`); the
  build regenerates the HLE NID table by itself.

## Done when
`tools/apply_patches.sh` applies the rebased stack from the new pin; both versions build;
`tools/lint.py --tests` passes; a 120 s 01.09 boot reaches the main menu (`boot_check` first line
in the log) and the menu fps is measured as in docs/subsystems.md "Menu frame rate"; the patch
README rows say which patches were dropped because upstream has them.

## Log
- 2026-10-20 02:20 claude: Created by T039 (audit). Replay method: clone external/ps3recomp to a temp dir, fetch upstream HEAD, then for each patch file in order: git am --3way, on failure git am --abort and record it.
