#!/usr/bin/env bash
# Where does the time go? One boot_check under `perf record`, grouped for SPU work
# (docs/debugging.md, "Profiling"). Task T029.
#
#   tools/spu_profile.sh <secs> [--warmup N] [--version V] [--build-dir DIR] [-- VAR=val ...]
#
#   secs          sample duration (default 60, final 3s reserved for shutdown)
#   --warmup N    boot N seconds before sampling (total boot = N + secs)
#   --version V   as boot_check: the staged versions/V/{build,game,vfs}
#   --build-dir D sets BUILD_DIR (e.g. build-0109)
#   -- VAR=val    extra environment for the game, e.g. -- GCM_INTR_THREAD=1 SPU_DMA_RANGE=58000000-58200000
#
# It runs tools/boot_check.sh under the boot lock (one game at a time), takes the PID
# boot_check prints ("game pid N"), and attaches `perf record -F 499 --call-graph=fp -p N`
# to exactly that PID (never a process found by name). tools/spu_profile.py turns the
# samples plus /proc/<pid>/task/*/stat deltas into analysis/spu_profile_<timestamp>.txt and
# prints one summary line. Needs only perf and python3. If perf is missing or blocked by
# perf_event_paranoid, it prints what to run and falls back to /proc thread sampling alone.
# It never uses sudo.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SECS=60 WARMUP=0 VERSION='' BDIR='' EXTRA=()
while [ $# -gt 0 ]; do
    case "$1" in
        --warmup) WARMUP=$2; shift ;;
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
    [ ${#EXTRA[@]} -eq 0 ] || ARGS+=(-- "${EXTRA[@]}")
    exec "$ROOT/tools/task.sh" lock boot env SPU_PROFILE_LOCKED=1 "$0" "${ARGS[@]}"
fi

[ "$SECS" -ge 8 ] 2>/dev/null || { echo "spu_profile: need at least 8 seconds" >&2; exit 2; }
[[ "$WARMUP" =~ ^[0-9]+$ ]] || { echo "spu_profile: --warmup needs nonnegative integer seconds" >&2; exit 2; }
WARMUP=$((10#$WARMUP))
TS=$(date +%Y%m%d-%H%M%S)
OUT=$ROOT/analysis/spu_profile_$TS.txt
WORK=$ROOT/analysis/spu_profile_$TS.d
mkdir -p "$WORK"

# perf usable? (at paranoid 2 user-space sampling of our own child still works)
PERF=1 WHY=
if ! command -v perf >/dev/null; then
    PERF=0 WHY="perf is not installed. Run: sudo dnf install perf   (or: sudo apt install linux-perf)"
else
    PAR=$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null || echo 2)
    if [ "$PAR" -gt 2 ]; then
        PERF=0 WHY="perf_event_paranoid=$PAR blocks perf. Run: sudo sysctl kernel.perf_event_paranoid=1"
    fi
fi
[ "$PERF" = 1 ] || echo "spu_profile: $WHY -- falling back to /proc thread sampling only" >&2

BARGS=("$((SECS + WARMUP))"); [ -z "$VERSION" ] || BARGS+=(--version "$VERSION")
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

# Warm up before taking either CPU snapshot or starting the perf recorder.
[ "$WARMUP" = 0 ] || sleep "$WARMUP"
# perf records for SECS-3 s, so it ends before boot_check stops the game.
REC=$(( SECS - 3 ))
python3 "$ROOT/tools/spu_profile.py" snap "$GPID" "$WORK/proc0.json"
if [ "$PERF" = 1 ]; then
    perf record -F 499 --call-graph=fp -p "$GPID" -o "$WORK/perf.data" -- sleep "$REC" \
        > "$WORK/perf_record.log" 2>&1 || {
            echo "spu_profile: perf record failed:" >&2
            tail -5 "$WORK/perf_record.log" >&2
            PERF=0 WHY="perf record failed (see $WORK/perf_record.log)"
        }
fi
# A container can deny perf_event_open even with paranoid <= 2. A failed
# recorder can return immediately or partway through the window. In either
# case keep the /proc snapshots REC seconds apart, not just startup milliseconds
# (and do not add a full second window after a partial recording).
python3 - "$WORK/proc0.json" "$REC" <<'PY'
import json, sys, time
start = json.load(open(sys.argv[1]))["t"]
time.sleep(max(0.0, float(sys.argv[2]) - (time.time() - start)))
PY
python3 "$ROOT/tools/spu_profile.py" snap "$GPID" "$WORK/proc1.json"
wait "$BPID" || true

if [ "$PERF" = 1 ]; then
    perf script -i "$WORK/perf.data" --no-inline --max-stack 6 -F tid,ip,sym,dso 2>/dev/null > "$WORK/perf.script" || true
fi
python3 "$ROOT/tools/spu_profile.py" report --work "$WORK" --out "$OUT" --perf "$PERF" \
    --why "$WHY" --boot "$BLOG" --secs "$REC"
rm -f "$WORK/perf.script"        # large; perf.data is kept for re-analysis
echo "spu_profile: report $OUT (raw data in $WORK; delete it when done)" >&2
