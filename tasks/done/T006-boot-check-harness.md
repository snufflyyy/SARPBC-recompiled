# T006: One-command boot check that reports how far the game got

Status: done
Owner: agent-harness
Touches: tools/boot_check.sh (new), tools/boot_report.py (new), docs/debugging.md (a "boot_check" section only)
Reads: analysis/run*.log, docs/debugging.md

## Goal
Every agent re-derives "how far did the boot get" by hand-grepping 20k-line logs. Write
`tools/boot_check.sh [seconds]`: runs the game headless with a timeout (only killing its
own PID), frame dumps on, and prints a short report: last file opened, packages opened
in order, Edge zlib request count, frames presented / non-black frames (via
tools/ppm2png.py logic), unresolved NIDs, threads created, the last 20 distinct
non-noise log lines, and whether it is still progressing in the final 10 s (log growth,
new files). Optionally `--gdb` to attach and dump guest stacks at the end. Output
`analysis/boot_report.txt` plus a one-line summary for task logs.

## Done when
`tools/boot_check.sh 60` works from a worktree, is documented in docs/debugging.md, and
the coordinator can paste its summary line into status.md.

## Log
- 2026-10-18 23:12 agent-harness: claimed
- 2026-10-18 23:12 agent-harness: claimed; worktree set up; first build running
- 2026-10-18 23:22 agent-harness: tools/boot_check.sh + boot_report.py committed; first 60 s run OK (STALLED since ~5s, Loading... static). Runtime ignores SIGTERM too (log keeps growing), so boot_check sends SIGKILL after 3 s grace. Coordinator req: BUILD_DIR/GAME_DIR/VFS_DIR + --version V supported by passing paths straight to the binary (run.sh untouched, outside Touches).
- 2026-10-18 23:28 agent-harness: Finding: edgezlib logs only #0-3 unless SARPBC_ZLIB_TRACE=1 (boot_check sets it): ~1500 requests in 10 s, not 4. Boot is nondeterministic: 1 of 6 runs went to a white screen at 15 s and aborted at 36 s with [ppu] FATAL stuck calling 0x00000373 (NULL vtable on obj 0x30004, callers func_010F64A0/func_010E7E90). Usual stall: guest threads all in func_006C61F0 -> sys_timer_usleep. Parallel runs verified against 4 other agents' live games.
- 2026-10-18 23:30 agent-harness: DONE: tools/boot_check.sh [secs] [--version V] [--gdb] [--quiet] runs the game headless (WINDOW=0, dummy audio, PS3_FSLOG=1, SARPBC_ZLIB_TRACE=1, frame dump every 60th present) under its own timeout, samples log+frames with tools/boot_report.py watch, stops only its own PID (checked against its timeout parent; SIGTERM is ignored by the runtime so SIGKILL after 3 s), optionally dumps gdb guest stacks, and writes analysis/boot_report.txt whose first line is a paste-able summary (verdict PROGRESSING/STALLED since Ns/HUNG/EXITED/CRASHED, last open, pkgs, zlib count, frames lit/distinct, threads, unresolved NIDs, alerts). BUILD_DIR/GAME_DIR/VFS_DIR as in run.sh, plus --version 0109; header shows APP_VER from PARAM.SFO. Verified with 9 real runs incl. concurrent runs and 4 other agents' live games (all survived). Findings: edgezlib logs only #0-3 without the trace (~1500 requests really); 01.02 boot is nondeterministic (1/6 runs reached a white screen then FATAL stuck calling 0x373); 01.09 stalls at 1 s looking under BLES00000/USRDIR/UNREALENGINE3. Branch worktree-agent-ae569008b821d8557, commits 34a39c8 c7e55f6.
