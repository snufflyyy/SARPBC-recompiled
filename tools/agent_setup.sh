#!/usr/bin/env bash
# Make a fresh git worktree of this repo buildable and runnable, cheaply.
# Run once from inside the worktree (docs/agents-workflow.md):
#
#   tools/agent_setup.sh
#
# Shares from the MAIN checkout, read-only by convention (symlinks):
#   game/  vfs/  .venv/  src/recomp/  src/spu_gen/
# Copies (small, yours to write): analysis/*.json
# Own copy: external/ps3recomp (cloned with the main one as reference, then
# tools/apply_patches.sh), and build/ (configured; compiles hit the shared ccache).
set -euo pipefail

WT=$(cd "$(dirname "$0")/.." && pwd)
MAIN=$(dirname "$(git -C "$WT" rev-parse --path-format=absolute --git-common-dir)")
[ "$WT" != "$MAIN" ] || { echo "run this in a worktree, not the main checkout" >&2; exit 1; }

for p in game vfs .venv src/recomp src/spu_gen; do
    [ -e "$MAIN/$p" ] || { echo "main checkout has no $p -- ask the coordinator" >&2; exit 1; }
    if [ ! -e "$WT/$p" ]; then mkdir -p "$(dirname "$WT/$p")"; ln -s "$MAIN/$p" "$WT/$p"; fi
done
mkdir -p "$WT/analysis" "$WT/captures"
cp -n "$MAIN"/analysis/*.json "$WT/analysis/" 2>/dev/null || true

git -C "$WT" submodule update --init --reference "$MAIN/external/ps3recomp" external/ps3recomp >/dev/null
"$WT/tools/apply_patches.sh"

cmake -S "$WT" -B "$WT/build" -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ >/dev/null
echo "worktree ready: $WT"
echo "build:  tools/task.sh lock cpu cmake --build build -j8   (first build is mostly ccache hits)"
echo "run:    timeout -k 5 -s TERM 60 tools/run.sh > analysis/run.log 2>&1"
