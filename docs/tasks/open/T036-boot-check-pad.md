# T036: boot_check --pad: short scripted button presses via PAD_FILE (menus need X at ~0.4 fps)

Status: open
Owner: -
Priority: 7
Touches: tools/boot_check.sh, tools/boot_report.py (only if needed), docs/debugging.md (boot_check section)
Reads: docs/tasks/*/T028* (HANDOFF: the PAD_FILE loop), docs/tasks/done/T008*

## Goal
From T028. The safe-area screen and the menus need X presses. At ~0.4 fps `PAD_AUTOPRESS` pulses too rarely, and `PAD_SCRIPT` holds each press for 40 polls, so the presses merge and X is never released. T028 drove `PAD_FILE` from a background loop: CROSS for 3 polls every 25 s from 70 s. Add `boot_check --pad '<button>@<sec>[,...]'` (or `--pad-every`) that does this with short presses, and document it.

## Done when
A boot_check run with --pad reaches the main menu with no manual loop (the same env as T028).

## Log
