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
export PS3_TITLE=${PS3_TITLE:-SARPBC}
# Desktop shortcuts need not start with the checkout as their working directory.
export SARPBC_CONFIG=${SARPBC_CONFIG:-$ROOT/config.toml}

# The Vulkan runtime can fall back to headless after an SDL/window failure.
# Catch known incompatible desktop launch settings instead of starting an
# invisible game. Explicit headless use still works, including null builds.
if [ "$(uname -s)" = Linux ] && [[ "$PS3RECOMP_VK_WINDOW" != 0* ]]; then
    case "${SDL_VIDEODRIVER-}" in
        dummy|offscreen)
            echo "run.sh: SDL_VIDEODRIVER=$SDL_VIDEODRIVER cannot show a game window." >&2
            echo "Unset SDL_VIDEODRIVER for desktop play, or set PS3RECOMP_VK_WINDOW=0 for headless use." >&2
            exit 1 ;;
    esac
    if [ -f "$BUILD_DIR/CMakeCache.txt" ] &&
       grep -Eiq '^PS3RECOMP_RSX_VULKAN:[^=]+=(|OFF|FALSE|NO|N|0|IGNORE|.*-NOTFOUND)$' "$BUILD_DIR/CMakeCache.txt"; then
        echo "run.sh: this Linux build has Vulkan disabled; it cannot show a game window." >&2
        printf 'Reconfigure with: cmake -S %q -B %q -DPS3RECOMP_RSX_VULKAN=ON\n' "$ROOT" "$BUILD_DIR" >&2
        printf 'Then rebuild with: cmake --build %q\n' "$BUILD_DIR" >&2
        echo "For an intentional headless run, set PS3RECOMP_VK_WINDOW=0." >&2
        exit 1
    fi
fi

exec "$BUILD_DIR/sarpbc" "$GAME_DIR/EBOOT.elf" "$VFS_DIR" "$@"
