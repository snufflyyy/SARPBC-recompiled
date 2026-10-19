#!/usr/bin/env bash
# Give an agent its own git worktree of this repo, buildable and runnable, cheaply
# (docs/workflow.md). Any agent the user starts (Claude Code, pi, Antigravity, ...)
# runs this once:
#
#   tools/agent_setup.sh <agent>   # from the main checkout: create .worktrees/<agent>
#                                  # on branch <agent>/work (from main) and set it up
#   tools/agent_setup.sh           # from inside an existing worktree: set it up
#
# Shares from the MAIN checkout, read-only by convention (symlinks):
#   game/  vfs/  .venv/  src/recomp/  src/spu_gen/
# Copies (small, yours to write): analysis/*.json
# Own copy: external/ps3recomp (cloned with the main one as reference, then
# tools/apply_patches.sh), build/ and build-0109/ (configured; compiles hit the
# shared ccache).
set -euo pipefail

HERE=$(cd "$(dirname "$0")/.." && pwd)
MAIN=$(dirname "$(git -C "$HERE" rev-parse --path-format=absolute --git-common-dir)")

if [ $# -ge 1 ]; then
    agent=$1
    [[ $agent =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "agent name: lowercase letters, digits, '-'" >&2; exit 1; }
    WT=$MAIN/.worktrees/$agent
    if [ ! -e "$WT" ]; then
        git -C "$MAIN" worktree add -q -b "$agent/work" "$WT" main
    fi
    exec "$WT/tools/agent_setup.sh"
fi

WT=$HERE
[ "$WT" != "$MAIN" ] || { echo "usage from the main checkout: tools/agent_setup.sh <agent>" >&2; exit 1; }

for p in game vfs .venv src/recomp src/spu_gen; do
    [ -e "$MAIN/$p" ] || { echo "main checkout has no $p -- run the pipeline there first (docs/pipeline.md)" >&2; exit 1; }
    if [ ! -e "$WT/$p" ]; then mkdir -p "$(dirname "$WT/$p")"; ln -s "$MAIN/$p" "$WT/$p"; fi
done
mkdir -p "$WT/analysis" "$WT/captures"
cp -n "$MAIN"/analysis/*.json "$WT/analysis/" 2>/dev/null || true

git -C "$WT" submodule update --init --reference "$MAIN/external/ps3recomp" external/ps3recomp >/dev/null
"$WT/tools/apply_patches.sh"

cmake -S "$WT" -B "$WT/build" -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ >/dev/null
if [ -d "$MAIN/versions/0109/src/recomp" ]; then
    cmake -S "$WT" -B "$WT/build-0109" -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
        -DRECOMP_DIR="$MAIN/versions/0109/src/recomp" -DSPU_DIR="$MAIN/versions/0109/src/spu_gen" >/dev/null
fi
echo "worktree ready: $WT (branch $(git -C "$WT" branch --show-current))"
echo "build:  tools/task.sh lock cpu cmake --build build-0109 -j16   (first build is mostly ccache hits)"
echo "boot:   tools/task.sh lock boot env BUILD_DIR=build-0109 tools/boot_check.sh 60 --version 0109"
