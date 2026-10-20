# T036: boot_check --pad: short scripted button presses via PAD_FILE

Status: open
Owner: -
Priority: 7
Touches: tools/boot_check.sh, tools/boot_report.py (only if needed), docs/debugging.md (boot_check section)
Reads: docs/tasks/*/T028* (HANDOFF: the PAD_FILE loop), docs/tasks/done/T008*

## Goal
From T028. The safe-area screen and the menus need X presses. At T028's ~0.4 fps `PAD_AUTOPRESS` pulsed too rarely, and `PAD_SCRIPT` holds each press for 40 polls, so the presses merged and X was never released. Now (~30 fps, 2026-10-20) the main menu needs CROSS for 3 polls at 45 s and again at 50 s (one press only reaches Choose Profile); every perf measurement re-implements that with a background `PAD_FILE` writer (docs/subsystems.md "Menu frame rate"). Add `boot_check --pad '<button>@<sec>[,...]'` (or `--pad-every`) that does this with short presses, and document it.

## Done when
A boot_check run with --pad reaches the main menu with no manual loop (the same env as T028).

## Log
