# T018: Clean shutdown on SIGTERM/SIGINT (upstreamable)

Status: open
Owner: -
Touches: patches/ps3recomp/T018-*.patch (runtime signal handling only), src/main.cpp (signal setup only; coordinate, T001 also edits main.cpp), docs/debugging.md (boot_check "killing" paragraph)
Reads: external/ps3recomp/runtime/ppu/ (where SIGINT is caught), tools/boot_check.sh

## Goal
The running game ignores SIGINT and SIGTERM, so every run ends with SIGKILL: logs are cut
mid-line and atexit reports (e.g. src/overrides/edgezlib.cpp's totals) never print. Find
where the runtime installs its handlers and make TERM/INT do an orderly exit: flush logs,
run atexit, stop the frame clock, and exit with a distinct status. Upstream it as a patch,
then simplify boot_check.sh's escalation if appropriate.

## Done when
`timeout -s TERM 20 tools/run.sh` exits within ~1 s with flushed logs and atexit output;
boot_check verified; patch exported.

## Log
