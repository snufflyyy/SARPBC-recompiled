#!/usr/bin/env bash
# Where does the time go? One boot_check under perf (or eu-stack samples), grouped for SPU work
# (docs/debugging.md, "Profiling"). Task T029.
#
#   tools/spu_profile.sh <secs> [--warmup N] [--version V] [--build-dir DIR]
#                        [--scenario NAME] [--pad SPEC] [--sampler S] [--interval SEC]
#                        [-- VAR=val ...]
#
#   secs          sample duration (default 60, final 3s reserved for shutdown)
#   --warmup N    boot N seconds before sampling (total boot = N + secs)
#   --version V   as boot_check: the staged versions/V/{build,game,vfs}
#   --build-dir D sets BUILD_DIR (e.g. build-0109)
#   --scenario N  passed to boot_check (menu, single, arena: its pad route; the boot
#                 length is still warmup + secs), e.g. --scenario menu --warmup 75 30
#   --pad SPEC    passed to boot_check (pad presses at wall-clock seconds)
#   --sampler S   auto (default: perf if it can record, else stacks), perf, stacks, none
#   --interval S  stacks sampler: seconds between rounds of captures (default 0.25)
#   -- VAR=val    extra environment for the game, e.g. -- GCM_INTR_THREAD=1 SPU_DMA_RANGE=58000000-58200000
#
# It runs tools/boot_check.sh under the boot lock (one game at a time), takes the PID
# boot_check prints ("game pid N"), and samples exactly that PID (never a process found
# by name): `perf record -F 499 --call-graph=fp -p N`, or, where perf cannot record (this
# container denies perf_event_open), the stacks sampler: every --interval seconds, each
# thread /proc shows running is unwound alone with `eu-stack -1 -p TID` (elfutils), which
# stops only that thread for ~25 ms (the report prints the total). tools/spu_profile.py
# turns the samples plus /proc/<pid>/task/*/stat deltas into
# analysis/spu_profile_<timestamp>.txt and prints one summary line. Needs python3 and perf
# or eu-stack; with neither it prints what to install and reports /proc thread CPU alone.
# It never uses sudo.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SECS=60 WARMUP=0 VERSION='' BDIR='' SCEN='' PADSPEC='' SAMPLER=auto INTERVAL=0.25 EXTRA=()
while [ $# -gt 0 ]; do
    case "$1" in
        --warmup) WARMUP=$2; shift ;;
        --scenario) SCEN=$2; shift ;;
        --pad) PADSPEC=$2; shift ;;
        --sampler) SAMPLER=$2; shift ;;
        --interval) INTERVAL=$2; shift ;;
        --version) VERSION=$2; shift ;;
        --build-dir) BDIR=$2; shift ;;
        -h|--help) sed -n '2,/^set -e/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
        --) shift; EXTRA=("$@"); break ;;
        [0-9]*) SECS=$1 ;;
        *) echo "spu_profile: unknown argument '$1' (try --help)" >&2; exit 2 ;;
    esac
    shift
done

# Take the boot lock for the whole run, unless the caller already holds it.
if [ -z "${SPU_PROFILE_LOCKED:-}" ]; then
    ARGS=("$SECS" --warmup "$WARMUP"); [ -z "$VERSION" ] || ARGS+=(--version "$VERSION")
    [ -z "$BDIR" ] || ARGS+=(--build-dir "$BDIR")
    [ -z "$SCEN" ] || ARGS+=(--scenario "$SCEN")
    [ -z "$PADSPEC" ] || ARGS+=(--pad "$PADSPEC")
    ARGS+=(--sampler "$SAMPLER" --interval "$INTERVAL")
    [ ${#EXTRA[@]} -eq 0 ] || ARGS+=(-- "${EXTRA[@]}")
    exec "$ROOT/tools/task.sh" lock boot env SPU_PROFILE_LOCKED=1 "$0" "${ARGS[@]}"
fi

[ "$SECS" -ge 8 ] 2>/dev/null || { echo "spu_profile: need at least 8 seconds" >&2; exit 2; }
[[ "$WARMUP" =~ ^[0-9]+$ ]] || { echo "spu_profile: --warmup needs nonnegative integer seconds" >&2; exit 2; }
WARMUP=$((10#$WARMUP))
case "$SAMPLER" in auto|perf|stacks|none) ;; *) echo "spu_profile: --sampler is auto, perf, stacks or none" >&2; exit 2 ;; esac
[[ "$INTERVAL" =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo "spu_profile: --interval needs seconds" >&2; exit 2; }
TS=$(date +%Y%m%d-%H%M%S)
OUT=$ROOT/analysis/spu_profile_$TS.txt
WORK=$ROOT/analysis/spu_profile_$TS.d
mkdir -p "$WORK"

# Which sampler? perf if it can record; a container can deny perf_event_open even at
# paranoid <= 2, so probe it once with a trivial child before the game starts.
PERF=0 STACKS=0 WHY=
perf_why() {
    if ! command -v perf >/dev/null; then
        echo "perf is not installed. Run: sudo dnf install perf   (or: sudo apt install linux-perf)"; return
    fi
    local par; par=$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null || echo 2)
    if [ "$par" -gt 2 ]; then
        echo "perf_event_paranoid=$par blocks perf. Run: sudo sysctl kernel.perf_event_paranoid=1"; return
    fi
    if ! perf record -q -o "$WORK/probe.data" -- true > "$WORK/perf_probe.log" 2>&1; then
        echo "perf cannot record here (see $WORK/perf_probe.log)"; return
    fi
    rm -f "$WORK/probe.data"
}
if [ "$SAMPLER" = auto ] || [ "$SAMPLER" = perf ]; then
    WHY=$(perf_why)
    [ -n "$WHY" ] || PERF=1
fi
if [ "$PERF" = 0 ] && { [ "$SAMPLER" = auto ] || [ "$SAMPLER" = stacks ]; }; then
    if command -v eu-stack >/dev/null; then
        STACKS=1
    else
        WHY="${WHY:+$WHY; }eu-stack is not installed. Run: sudo dnf install elfutils   (or: sudo apt install elfutils)"
    fi
fi
[ "$SAMPLER" != none ] || WHY="--sampler none"
if [ "$PERF" = 0 ] && [ "$STACKS" = 0 ]; then
    echo "spu_profile: $WHY -- /proc thread CPU only" >&2
elif [ "$STACKS" = 1 ] && [ -n "$WHY" ]; then
    echo "spu_profile: $WHY -- using eu-stack stack samples every ${INTERVAL}s" >&2
fi

BARGS=("$((SECS + WARMUP))"); [ -z "$VERSION" ] || BARGS+=(--version "$VERSION")
[ -z "$SCEN" ] || BARGS+=(--scenario "$SCEN")
[ -z "$PADSPEC" ] || BARGS+=(--pad "$PADSPEC")
[ -z "$BDIR" ] || export BUILD_DIR=$BDIR
[ ${#EXTRA[@]} -eq 0 ] || export "${EXTRA[@]}"
export SARPBC_FRAME_STATS=${SARPBC_FRAME_STATS-1}
export SPURS_EF_STATS=${SPURS_EF_STATS-1}
export SPU_DMA_RANGE=${SPU_DMA_RANGE-58000000-58200000}

BLOG=$WORK/boot_check.out
"$ROOT/tools/boot_check.sh" "${BARGS[@]}" > "$BLOG" 2> "$WORK/boot_check.err" &
BPID=$!
trap 'kill -TERM "$BPID" 2>/dev/null || true' INT TERM    # boot_check stops its own game

GPID=
for _ in $(seq 400); do
    GPID=$(sed -n 's/^boot_check: game pid \([0-9]*\),.*/\1/p' "$WORK/boot_check.err" | head -1)
    [ -z "$GPID" ] || break
    kill -0 "$BPID" 2>/dev/null || break
    sleep 0.1
done
[ -n "$GPID" ] || { echo "spu_profile: boot_check did not start a game:" >&2; cat "$WORK/boot_check.err" >&2; exit 1; }

# Warm up before taking either CPU snapshot or starting a sampler.
[ "$WARMUP" = 0 ] || sleep "$WARMUP"
# Sampling lasts SECS-3 s, so it ends before boot_check stops the game.
REC=$(( SECS - 3 ))
python3 "$ROOT/tools/spu_profile.py" snap "$GPID" "$WORK/proc0.json"
if [ "$PERF" = 1 ]; then
    perf record -F 499 --call-graph=fp -p "$GPID" -o "$WORK/perf.data" -- sleep "$REC" \
        > "$WORK/perf_record.log" 2>&1 || {
            echo "spu_profile: perf record failed:" >&2
            tail -5 "$WORK/perf_record.log" >&2
            PERF=0 WHY="perf record failed (see $WORK/perf_record.log)"
            # auto: sample stacks for whatever is left of the window
            [ "$SAMPLER" != auto ] || ! command -v eu-stack >/dev/null || STACKS=1
        }
fi
# A recorder that fails at the start or partway through still leaves the /proc
# snapshots REC seconds apart (not startup milliseconds, and no extra full window after
# a partial recording): the stacks sampler, or a plain wait, fills the remaining time.
python3 "$ROOT/tools/spu_profile.py" stacks "$GPID" "$WORK/stacks.txt" \
    --since "$WORK/proc0.json" --secs "$REC" --interval "$INTERVAL" --sample "$STACKS"
python3 "$ROOT/tools/spu_profile.py" snap "$GPID" "$WORK/proc1.json"
wait "$BPID" || true

if [ "$PERF" = 1 ]; then
    perf script -i "$WORK/perf.data" --no-inline --max-stack 6 -F tid,ip,sym,dso 2>/dev/null > "$WORK/perf.script" || true
fi
python3 "$ROOT/tools/spu_profile.py" report --work "$WORK" --out "$OUT" --perf "$PERF" \
    --why "$WHY" --boot "$BLOG" --secs "$REC" --stacks "$STACKS"
rm -f "$WORK/perf.script"        # large; perf.data is kept for re-analysis
echo "spu_profile: report $OUT (raw data in $WORK; delete it when done)" >&2
