# T006: One-command boot check that reports how far the game got

Status: open
Owner: -
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
