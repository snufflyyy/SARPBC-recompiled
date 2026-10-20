#!/usr/bin/env bash
# Build the port: the one command to use after a pull or an edit.
#
#   ./build.sh                 # 01.09 (the target version)
#   ./build.sh --version 0102  # the base 01.02 build
#   ./build.sh --clean         # wipe the build dir first (reconfigure + full build)
#
# What it does, in order:
#   1. re-applies patches/ps3recomp/ to external/ps3recomp, but only when the
#      patches or the pin changed (tools/apply_patches.sh rewrites the runtime
#      headers, which would recompile all 7.5M lifted lines)
#   2. configures the build dir with clang + Ninja if it isn't configured yet
#   3. builds under the shared `cpu` lock, so it never runs alongside an agent's build
#
# The whole script runs under a per-checkout `build-<id>` lock, so patching, configuring,
# --clean and compiling of one checkout never interleave. A dirty external/ps3recomp is
# refused (SARPBC_ALLOW_DIRTY_RUNTIME=1 builds it as is).
#
# Build dirs: versions/0109/build and build/ in the main checkout; build-0109/ and
# build/ in an agent worktree (tools/agent_setup.sh). The lifted code comes from
# tools/relift.sh (docs/pipeline.md); this script never relifts.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
MAIN=$(dirname "$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)")
if [ -z "${SARPBC_BUILD_LOCKED:-}" ]; then
    mkdir -p "$MAIN/.locks"
    exec flock "$MAIN/.locks/build-$(printf %s "$ROOT" | sha256sum | cut -c1-12).lock" \
        env SARPBC_BUILD_LOCKED=1 "$0" "$@"
fi

version=0109 clean=0
while [ $# -gt 0 ]; do
    case "$1" in
    --version) version=${2:?--version needs 0102 or 0109}; shift 2 ;;
    --version=*) version=${1#*=}; shift ;;
    --clean) clean=1; shift ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1 (see ./build.sh --help)" >&2; exit 1 ;;
    esac
done

case "$version" in
0109|01.09)
    RECOMP=$MAIN/versions/0109/src/recomp SPU=$MAIN/versions/0109/src/spu_gen
    if [ "$ROOT" = "$MAIN" ]; then BUILD=$ROOT/versions/0109/build; else BUILD=$ROOT/build-0109; fi ;;
0102|01.02)
    RECOMP=$ROOT/src/recomp SPU=$ROOT/src/spu_gen BUILD=$ROOT/build ;;
*) echo "unknown version $version (0102 or 0109)" >&2; exit 1 ;;
esac
[ -d "$RECOMP" ] || { echo "no lifted code at $RECOMP: run the pipeline first (docs/pipeline.md)" >&2; exit 1; }

# 1. Patch stack: tools/apply_patches.sh --ensure compares the checkout's tree with
# pin + patches (not a commit count), refuses a dirty runtime and leaves the checkout
# untouched when a patch fails. It rewrites headers only when the stack really changed.
"$ROOT/tools/apply_patches.sh" --ensure

# 2. Configure.
[ $clean = 1 ] && rm -rf "$BUILD"
if [ ! -f "$BUILD/build.ninja" ]; then
    cmake -S "$ROOT" -B "$BUILD" -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
        -DRECOMP_DIR="$RECOMP" -DSPU_DIR="$SPU"
fi

# 3. Build.
"$ROOT/tools/task.sh" lock cpu cmake --build "$BUILD" -j"$(nproc)"
hint=; [ "$version" = 0109 ] || [ "$version" = 01.09 ] || hint=" --version $version"
echo "built: $BUILD/sarpbc   (run it with ./run.sh$hint)"
