#!/usr/bin/env bash
# One command for "is my change good": build, lint with tests, then a scripted boot.
#
#   tools/verify.sh [--scenario NAME] [--no-boot] [--version V]
#
# Runs ./build.sh, `tools/lint.py --tests`, and (unless --no-boot) tools/boot_check.sh
# --scenario NAME (default menu) against version V (default 0109). Fails on the first
# step that fails, and when the boot verdict is neither PROGRESSING nor
# "STALLED (frames still presented)" (a menu waiting for input), i.e. it exited, crashed or hung. Prints the boot's one-line summary last, ready for a task note.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SCENARIO=menu BOOT=1 VERSION=0109
while [ $# -gt 0 ]; do
    case "$1" in
        --scenario) SCENARIO=$2; shift ;;
        --version) VERSION=$2; shift ;;
        --no-boot) BOOT=0 ;;
        -h|--help) sed -n '2,/^set -e/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
        *) echo "verify: unknown argument '$1' (try --help)" >&2; exit 2 ;;
    esac
    shift
done

cd "$ROOT"
echo "== build"; ./build.sh
echo "== lint --tests"; tools/lint.py --tests
[ "$BOOT" = 1 ] || { echo "verify: OK (no boot)"; exit 0; }
echo "== boot_check --scenario $SCENARIO"
out=$(tools/boot_check.sh --version "$VERSION" --scenario "$SCENARIO" --quiet)
echo "$out"
case "$out" in
    *": PROGRESSING"* | *"(frames still presented)"*) echo "verify: OK" ;;
    *) echo "verify: FAILED, the boot ended neither PROGRESSING nor idling at a menu with frames (see analysis/boot_report.txt)" >&2; exit 1 ;;
esac
