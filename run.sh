#!/usr/bin/env bash
# Play the port in a window.
#
#   ./run.sh                   # 01.09 (the target version)
#   ./run.sh --version 0102    # the base 01.02 build
#   ./run.sh --build           # ./build.sh first, then run
#   ./run.sh -- <args>         # pass extra arguments to the game
#
# Keyboard and mouse act as pad 1 (Space = X; bindings in config.toml); a controller works
# through SDL. Env vars from docs/debugging.md pass straight through, e.g.
#   PS3RECOMP_VK_WINDOW=0 ./run.sh   for headless. For a timed boot report use
# tools/boot_check.sh instead.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
MAIN=$(dirname "$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)")

version=0109 build=0 extra=()
while [ $# -gt 0 ]; do
    case "$1" in
    --version) version=${2:?--version needs 0102 or 0109}; shift 2 ;;
    --version=*) version=${1#*=}; shift ;;
    --build) build=1; shift ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    --) shift; extra=("$@"); break ;;
    *) echo "unknown argument: $1 (see ./run.sh --help)" >&2; exit 1 ;;
    esac
done

case "$version" in
0109|01.09)
    if [ "$ROOT" = "$MAIN" ]; then bd=$ROOT/versions/0109/build; else bd=$ROOT/build-0109; fi
    export BUILD_DIR=${BUILD_DIR:-$bd}
    export GAME_DIR=${GAME_DIR:-$MAIN/versions/0109/game}
    export VFS_DIR=${VFS_DIR:-$MAIN/versions/0109/vfs} ;;
0102|01.02)
    export BUILD_DIR=${BUILD_DIR:-$ROOT/build}
    export GAME_DIR=${GAME_DIR:-$MAIN/game}
    export VFS_DIR=${VFS_DIR:-$MAIN/vfs} ;;
*) echo "unknown version $version (0102 or 0109)" >&2; exit 1 ;;
esac

[ $build = 1 ] && "$ROOT/build.sh" --version "$version"
[ -x "$BUILD_DIR/sarpbc" ] || { echo "no $BUILD_DIR/sarpbc yet: run ./build.sh --version $version" >&2; exit 1; }
[ -f "$GAME_DIR/EBOOT.elf" ] || { echo "no $GAME_DIR/EBOOT.elf: run the pipeline first (docs/pipeline.md)" >&2; exit 1; }

exec "$ROOT/tools/run.sh" "${extra[@]}"
