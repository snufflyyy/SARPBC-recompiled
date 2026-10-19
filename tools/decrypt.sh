#!/usr/bin/env bash
# Decrypt the title's NPDRM SELFs (EBOOT.BIN, SPUJOBS.SPRX) to game/ with RPCS3's CLI.
#
# Both are bound to the RAP (NPD license type 2), which ps3recomp cannot use. RPCS3's
# `--decrypt` finds the RAP by content ID under dev_hdd0/home/00000001/exdata/, so this
# runs RPCS3 with its own config dir inside tools/rpcs3/ and never touches ~/.config.
# The AppImage is downloaded on first use (latest RPCS3/rpcs3-binaries-linux release).
#
#   tools/extract.sh && tools/decrypt.sh
#   VFS_DIR=versions/0109/vfs GAME_DIR=versions/0109/game tools/decrypt.sh   # another version
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
R=$ROOT/tools/rpcs3
CFG=$R/config
VFS_DIR=$(realpath -m "${VFS_DIR:-$ROOT/vfs}")
GAME_DIR=$(realpath -m "${GAME_DIR:-$ROOT/game}")
USRDIR=$VFS_DIR/dev_hdd0/game/NPUB30035/USRDIR
RAP=$(ls "$ROOT"/Supersonic*/*.rap)

[ -f "$USRDIR/EBOOT.BIN" ] || { echo "no $USRDIR/EBOOT.BIN -- run tools/extract.sh first"; exit 1; }

if [ ! -x "$R/squashfs-root/AppRun" ]; then
    mkdir -p "$R"
    gh release download -R RPCS3/rpcs3-binaries-linux --pattern '*linux64.AppImage' -D "$R" --clobber
    chmod +x "$R"/*.AppImage
    # Extracting avoids needing FUSE to mount the AppImage.
    (cd "$R" && ./*.AppImage --appimage-extract >/dev/null)
fi

mkdir -p "$CFG/rpcs3/dev_hdd0/home/00000001/exdata"
cp "$RAP" "$CFG/rpcs3/dev_hdd0/home/00000001/exdata/"

WORK=$(mktemp -d "$R/work.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
cp "$USRDIR/EBOOT.BIN" "$USRDIR/SARB/BINARIES/PS3/SPU/SPUJOBS.SPRX" "$WORK/"

# One file per call: given several paths, --decrypt silently processes only the first.
# stdin from /dev/null: if a key is wrong RPCS3 prompts for a KLIC; an empty answer ends it.
for f in EBOOT.BIN SPUJOBS.SPRX; do
    XDG_CONFIG_HOME=$CFG XDG_CACHE_HOME=$R/cache QT_QPA_PLATFORM=offscreen \
        "$R/squashfs-root/AppRun" --decrypt "$WORK/$f" </dev/null
done

mkdir -p "$GAME_DIR"
mv "$WORK/EBOOT.elf" "$GAME_DIR/EBOOT.elf"
mv "$WORK/SPUJOBS.prx" "$GAME_DIR/SPUJOBS.prx"
sha256sum "$GAME_DIR/EBOOT.elf" "$GAME_DIR/SPUJOBS.prx"
