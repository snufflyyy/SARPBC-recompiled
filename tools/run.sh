#!/usr/bin/env bash
# Run the port against the extracted install. Any environment variable set by the
# caller wins over the defaults here (see docs/debugging.md for the useful ones).
#
#   tools/run.sh [extra args]
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)

# A visible window and the game's own shaders; set either to 0 to turn it off.
export PS3RECOMP_VK_WINDOW=${PS3RECOMP_VK_WINDOW:-1}
export PS3RECOMP_VK_GUEST_PROGRAMS=${PS3RECOMP_VK_GUEST_PROGRAMS:-1}

exec "$ROOT/build/sarpbc" "$ROOT/game/EBOOT.elf" "$ROOT/vfs" "$@"
