#!/usr/bin/env bash
# Extract the PSN package into the layout a PS3 installs it to, so the runtime can map
# vfs/dev_hdd0 as /dev_hdd0 (PS3_HDD0_ROOT). Safe to re-run; files are overwritten.
#
#   tools/extract.sh [path/to/game.pkg]
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PS3RECOMP=${PS3RECOMP:-$ROOT/external/ps3recomp}
PKG=${1:-$(ls "$ROOT"/Supersonic*/*.pkg)}
OUT=$ROOT/vfs/dev_hdd0/game/NPUB30035

# pkg_extract falls back to pure-Python AES without pycryptodome: minutes, not seconds.
if [ ! -x "$ROOT/.venv/bin/python" ]; then
    python3 -m venv "$ROOT/.venv"
    "$ROOT/.venv/bin/pip" install -q -r "$PS3RECOMP/requirements.txt"
fi

mkdir -p "$OUT"
"$ROOT/.venv/bin/python" "$PS3RECOMP/tools/pkg_extract.py" "$PKG" "$OUT"
echo "extracted -> $OUT"
