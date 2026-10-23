#!/usr/bin/env bash
# Per-thread CPU profile of the running port, without perf (docs/debugging.md "CPU profile").
#
#   tools/cpu_profile.sh [--start S] [--secs N] [--top K] [-- boot_check args...]
#   tools/cpu_profile.sh --start 68 --secs 12 -- 90 --version 0109 --scenario single --quiet
#
# perf needs CAP_PERFMON, which containers here lack, and eu-stack/gdb samples are too slow to
# see a 10 us function. This preloads a small shim (tools/cpu_profile/prof.c) into the game: once
# S seconds have passed it arms a per-thread CPU-time timer (1 kHz) on every thread for N seconds,
# records the instruction pointer at each tick, and dumps the histogram. tools/cpu_profile/sym.py
# then names the functions with nm and prints each thread's top K (default 25), with the thread's
# sample count: 1000 samples per second is one core, so a thread's share is samples / (1000 * N).
# Everything after "--" goes to tools/boot_check.sh (default: 90 --scenario single --version 0109).
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
START=60 SECS=10 TOP=25 ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --start) START=$2; shift ;;
        --secs) SECS=$2; shift ;;
        --top) TOP=$2; shift ;;
        --) shift; ARGS=("$@"); break ;;
        -h|--help) sed -n '2,/^set -e/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
        *) echo "cpu_profile: unknown argument '$1' (try --help)" >&2; exit 2 ;;
    esac
    shift
done
[ "${#ARGS[@]}" -gt 0 ] || ARGS=(90 --version 0109 --scenario single --quiet)

CACHE=$ROOT/.cache/cpu_profile
mkdir -p "$CACHE"
if [ ! -f "$CACHE/prof.so" ] || [ "$ROOT/tools/cpu_profile/prof.c" -nt "$CACHE/prof.so" ]; then
    cc -O1 -shared -fPIC -o "$CACHE/prof.so" "$ROOT/tools/cpu_profile/prof.c" -lpthread -lrt
fi
# The binary boot_check runs, for nm: the same selection it makes.
VERSION=0109
for ((i = 0; i < ${#ARGS[@]}; i++)); do [ "${ARGS[i]}" = "--version" ] && VERSION=${ARGS[i+1]}; done
EXE=${BUILD_DIR:-$ROOT/versions/$VERSION/build}/sarpbc
[ -x "$EXE" ] || EXE=$ROOT/build/sarpbc

OUT=$CACHE/last.txt
rm -f "$OUT"
LD_PRELOAD=$CACHE/prof.so PROF_START=$START PROF_SECS=$SECS PROF_OUT=$OUT \
    "$ROOT/tools/boot_check.sh" "${ARGS[@]}" > "$CACHE/boot_check.out" 2>&1 || true
tail -1 "$CACHE/boot_check.out" | cut -c1-200
[ -s "$OUT" ] || { echo "cpu_profile: no samples (the run ended before --start $START?)" >&2; exit 1; }
python3 -I "$ROOT/tools/cpu_profile/sym.py" "$OUT" "$EXE" "$TOP"
