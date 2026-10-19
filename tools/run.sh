#!/usr/bin/env bash
# Run the port against the extracted install. Any environment variable set by the
# caller wins over the defaults here (see docs/debugging.md for the useful ones).
#
#   tools/run.sh [extra args]
#   BUILD_DIR=versions/0109/build GAME_DIR=versions/0109/game VFS_DIR=versions/0109/vfs tools/run.sh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BUILD_DIR=$(realpath -m "${BUILD_DIR:-$ROOT/build}")
GAME_DIR=$(realpath -m "${GAME_DIR:-$ROOT/game}")
VFS_DIR=$(realpath -m "${VFS_DIR:-$ROOT/vfs}")

# A visible window and the game's own shaders; set either to 0 to turn it off.
export PS3RECOMP_VK_WINDOW=${PS3RECOMP_VK_WINDOW:-1}
export PS3RECOMP_VK_GUEST_PROGRAMS=${PS3RECOMP_VK_GUEST_PROGRAMS:-1}

exec "$BUILD_DIR/sarpbc" "$GAME_DIR/EBOOT.elf" "$VFS_DIR" "$@"
