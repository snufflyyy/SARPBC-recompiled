#!/usr/bin/env bash
# Source this: sarpbc_overlay <vfs dir> builds the Graphics-menu overlay when needed (T065) and
# exports PS3_VFS_OVERLAY for the game. Never fatal: a failure leaves the game unpatched.
# SARPBC_NO_GRAPHICS_MENU=1 or an PS3_VFS_OVERLAY already set skips it.
sarpbc_overlay() {
    local vfs=$1 root ov
    root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
    [ -z "${PS3_VFS_OVERLAY:-}" ] || return 0
    case "${SARPBC_NO_GRAPHICS_MENU:-}" in 1|true) return 0 ;; esac
    [ -f "$vfs/dev_hdd0/game/NPUB30035/USRDIR/SARB/TAGAME/COOKEDPS3/TAGAME.XXX" ] || return 0
    ov=$(dirname "$vfs")/overlay
    if python3 -I "$root/tools/graphics_menu_patch.py" --ensure "$vfs" "$ov" >&2; then
        export PS3_VFS_OVERLAY=$ov
    else
        echo "overlay.sh: the Graphics menu patch failed; running the game unpatched" >&2
    fi
}
