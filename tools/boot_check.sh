#!/usr/bin/env bash
# Boot the port headless for N seconds and report how far it got
# (docs/debugging.md, "boot_check").
#
#   tools/boot_check.sh [seconds] [--version V] [--gdb] [--every N] [--keep N] [--quiet]
#   BUILD_DIR=versions/0109/build GAME_DIR=versions/0109/game VFS_DIR=versions/0109/vfs \
#       tools/boot_check.sh 60
#
#   seconds    how long to let the game run (default 60)
#   --version V  shorthand for BUILD_DIR/GAME_DIR/VFS_DIR = versions/V/{build,game,vfs}
#              (e.g. --version 0109); variables set explicitly win
#   --gdb      before stopping the game, attach gdb to it and dump every
#              thread's stack (guest frames are func_<addr>) into the report
#   --every N  dump every Nth presented frame (default 60; PS3RECOMP_VK_DUMP_EVERY)
#   --keep N   keep the last N runs under analysis/boot_check/ (default 5)
#   --quiet    print only the one-line summary
#
# BUILD_DIR, GAME_DIR and VFS_DIR mean what they mean to tools/run.sh (default:
# this checkout's build/, game/, vfs/). A relative path that does not exist from
# the current directory is looked up in the main checkout, where versions/ lives.
# It starts $BUILD_DIR/sarpbc the way tools/run.sh does, adding
# PS3RECOMP_VK_WINDOW=0, SDL_AUDIODRIVER=dummy, PS3_FSLOG=1 and a frame dump;
# anything set in the environment wins. It stops only the game
# it started itself (by PID, checked against its own timeout process), so it is
# safe while other agents' games run. Everything goes to
# analysis/boot_check/<id>/ (log, timeline, gdb) and captures/boot_check/<id>/
# (frame PNGs); the report is also copied to analysis/boot_report.txt. The first
# line of the report is the one-line summary for task logs.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
MAIN=$(dirname "$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)")
SECS=60 GDB=0 EVERY=60 KEEP=5 QUIET=0 VERSION=
while [ $# -gt 0 ]; do
    case "$1" in
        --gdb) GDB=1 ;;
        --version) VERSION=$2; shift ;;
        --every) EVERY=$2; shift ;;
        --keep) KEEP=$2; shift ;;
        -q|--quiet) QUIET=1 ;;
        -h|--help) sed -n '2,/^set -e/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
        [0-9]*) SECS=$1 ;;
        *) echo "boot_check: unknown argument '$1' (try --help)" >&2; exit 2 ;;
    esac
    shift
done

[ "$KEEP" -ge 1 ] 2>/dev/null || { echo "boot_check: --keep needs a number >= 1" >&2; exit 2; }
# Same variables and meaning as tools/run.sh; relative paths missing here fall back to MAIN.
resolve() {
    case "$1" in
        /*) realpath -m "$1" ;;
        *) if [ -e "$1" ] || [ ! -e "$MAIN/$1" ]; then realpath -m "$1"; else realpath -m "$MAIN/$1"; fi ;;
    esac
}
if [ -n "$VERSION" ]; then
    BUILD_DIR=${BUILD_DIR:-versions/$VERSION/build}
    GAME_DIR=${GAME_DIR:-versions/$VERSION/game}
    VFS_DIR=${VFS_DIR:-versions/$VERSION/vfs}
fi
BUILD_DIR=$(resolve "${BUILD_DIR:-$ROOT/build}")
GAME_DIR=$(resolve "${GAME_DIR:-$ROOT/game}")
VFS_DIR=$(resolve "${VFS_DIR:-$ROOT/vfs}")
[ -x "$BUILD_DIR/sarpbc" ] || { echo "boot_check: no $BUILD_DIR/sarpbc -- build first" >&2; exit 1; }
[ -e "$GAME_DIR/EBOOT.elf" ] || { echo "boot_check: no $GAME_DIR/EBOOT.elf" >&2; exit 1; }
[ -d "$VFS_DIR/dev_hdd0" ] || { echo "boot_check: no $VFS_DIR/dev_hdd0" >&2; exit 1; }
[ "$GDB" = 0 ] || command -v gdb >/dev/null || { echo "boot_check: --gdb needs gdb" >&2; exit 1; }

ID=$(date +%Y%m%d-%H%M%S)-$$
RUN=$ROOT/analysis/boot_check/$ID
CAP=$ROOT/captures/boot_check/$ID
mkdir -p "$RUN" "$CAP"
LOG=$RUN/run.log

export PS3RECOMP_VK_WINDOW=${PS3RECOMP_VK_WINDOW:-0}
export PS3RECOMP_VK_GUEST_PROGRAMS=${PS3RECOMP_VK_GUEST_PROGRAMS:-1}   # as tools/run.sh
export SDL_AUDIODRIVER=${SDL_AUDIODRIVER:-dummy}
export PS3_FSLOG=${PS3_FSLOG:-1}
export PS3RECOMP_VK_DUMP=${PS3RECOMP_VK_DUMP:-$CAP/frame.ppm}
export PS3RECOMP_VK_DUMP_EVERY=${PS3RECOMP_VK_DUMP_EVERY:-$EVERY}

# A safety net past our own deadline: if this script dies, timeout still ends the game.
LIMIT=$(( SECS + (GDB ? 180 : 30) ))
TPID= GPID= WPID=

# State of a PID from /proc ("" if gone); comm cannot contain ')' for our binary.
pstate() { local s; s=$(cat "/proc/$1/stat" 2>/dev/null) || return 0; s=${s##*) }; echo "${s%% *}"; }
alive() { local s; s=$(pstate "$1"); [ -n "$s" ] && [ "$s" != Z ]; }
# Is GPID still the game our own timeout started (guards against PID reuse)?
ours() {
    [ -n "$GPID" ] && alive "$GPID" || return 1
    local s; s=$(cat "/proc/$GPID/stat" 2>/dev/null) || return 1; s=${s##*) }
    set -- $s; [ "$2" = "$TPID" ]
}
stop_game() {
    ours || return 0
    kill -TERM "$GPID" 2>/dev/null || true
    # The runtime ignores SIGTERM as well as SIGINT (2026-10-18: the log keeps
    # growing after it), so the grace period before SIGKILL is short.
    for _ in $(seq 30); do ours || return 0; sleep 0.1; done
    kill -KILL "$GPID" 2>/dev/null || true
}
cleanup() {
    stop_game
    [ -z "$WPID" ] || { : > "$RUN/stop"; wait "$WPID" 2>/dev/null || true; }
}
trap cleanup EXIT
trap 'echo "boot_check: interrupted" >&2; exit 130' INT TERM

T0=$(date +%s.%N)
timeout -k 5 -s TERM "$LIMIT" "$BUILD_DIR/sarpbc" "$GAME_DIR/EBOOT.elf" "$VFS_DIR" > "$LOG" 2>&1 &
TPID=$!
for _ in $(seq 100); do       # timeout's only child is the game
    GPID=$(pgrep -P "$TPID" || true)
    [ -z "$GPID" ] || break
    alive "$TPID" || break
    sleep 0.05
done
[ -n "$GPID" ] || { echo "boot_check: the game did not start (see $LOG)" >&2; tail -5 "$LOG" >&2; exit 1; }

python3 "$ROOT/tools/boot_report.py" watch --log "$LOG" --pid "$GPID" --run-dir "$RUN" \
    --dump "$PS3RECOMP_VK_DUMP" --t0 "$T0" &
WPID=$!
[ "$QUIET" = 1 ] || echo "boot_check: game pid $GPID, ${SECS}s, $BUILD_DIR/sarpbc, log $LOG" >&2

END=$(( $(date +%s) + SECS ))
while [ "$(date +%s)" -lt "$END" ] && ours; do sleep 0.5; done

KILLED=0 STOP_T=
if ours; then
    KILLED=1
    STOP_T=$(python3 -c "import time; print(round(time.time() - $T0, 2))")
    if [ "$GDB" = 1 ]; then
        [ "$QUIET" = 1 ] || echo "boot_check: attaching gdb to $GPID" >&2
        timeout -k 5 150 gdb -p "$GPID" -batch -ex 'set pagination off' \
            -ex 'thread apply all bt 14' > "$RUN/gdb.txt" 2>&1 || true
    fi
    stop_game
fi
ELAPSED=$(python3 -c "import time; print(round(time.time() - $T0, 1))")
STATUS=0; wait "$TPID" 2>/dev/null || STATUS=$?
TFIRED=0; [ "$STATUS" = 124 ] && [ "$KILLED" = 0 ] && TFIRED=1
: > "$RUN/stop"; wait "$WPID" || true; WPID=
trap - EXIT

# Frames: keep PNGs of the first/last non-black and the last dump; drop the PPMs.
for f in "$RUN"/frame_*.ppm; do
    [ -e "$f" ] || continue
    python3 "$ROOT/tools/ppm2png.py" "$f" "$CAP/$(basename "${f%.ppm}").png" > /dev/null && rm -f "$f"
done
rm -f "$PS3RECOMP_VK_DUMP"

{
    echo "date=$(date '+%Y-%m-%d %H:%M')"
    echo "branch=$(git -C "$ROOT" branch --show-current 2>/dev/null || echo '?')"
    echo "rev=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo '?')$(git -C "$ROOT" status --porcelain --untracked-files=no 2>/dev/null | grep -q . && echo '+dirty' || true)"
    echo "seconds=$SECS"
    echo "stop_t=$STOP_T"
    echo "build_dir=$BUILD_DIR"
    echo "build_time=$(date -r "$BUILD_DIR/sarpbc" '+%Y-%m-%d %H:%M')"
    echo "game_dir=$GAME_DIR"
    echo "vfs_dir=$VFS_DIR"
    echo "elapsed=$ELAPSED"
    echo "pid=$GPID"
    echo "exit_status=$STATUS"
    echo "killed=$KILLED"
    echo "timeout_fired=$TFIRED"
    echo "dump_every=$PS3RECOMP_VK_DUMP_EVERY"
    echo "frames_dir=$CAP"
    echo "env=PS3RECOMP_VK_WINDOW=$PS3RECOMP_VK_WINDOW SDL_AUDIODRIVER=$SDL_AUDIODRIVER PS3_FSLOG=$PS3_FSLOG PS3RECOMP_VK_DUMP_EVERY=$PS3RECOMP_VK_DUMP_EVERY"
} > "$RUN/meta.txt"

python3 "$ROOT/tools/boot_report.py" report "$LOG" --run-dir "$RUN" --out "$RUN/report.txt" > /dev/null
cp "$RUN/report.txt" "$ROOT/analysis/.boot_report.$$" && mv -f "$ROOT/analysis/.boot_report.$$" "$ROOT/analysis/boot_report.txt"

# Prune finished runs (those with a report) beyond --keep; running ones have none yet.
ls -1d "$ROOT"/analysis/boot_check/*/ 2>/dev/null | sort | while read -r d; do
    [ -e "$d/report.txt" ] && echo "$d"
done | head -n "-$KEEP" | while read -r d; do
    rm -rf "$d" "$ROOT/captures/boot_check/$(basename "$d")"
done

if [ "$QUIET" = 1 ]; then head -1 "$RUN/report.txt"; else cat "$RUN/report.txt"; fi
