#!/usr/bin/env bash
# Export the newest commit(s) on external/ps3recomp's sarpbc-patches branch as the next
# numbered patch in patches/ps3recomp/, with its README table row, in one step.
#
#   tools/export_patch.sh <slug> "<README description>" ["<upstream status>"] [--count N]
#   tools/export_patch.sh vulkan-foo "T040: what and why" "generic, offer upstream"
#
# Commit inside external/ps3recomp first (clean tree, on sarpbc-patches). The patch is
# 'NNNN-<slug>.patch' with NNNN the next free number; --count N exports the last N commits
# as one file (a short series). The checkout must hold exactly the patch stack so far:
# if tools/apply_patches.sh would change it, the export refuses (a stale stack would make
# a patch that does not apply from the pin). No commit is made in the superproject.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SUB=$ROOT/external/ps3recomp
DIR=$ROOT/patches/ps3recomp
COUNT=1 ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --count) COUNT=$2; shift ;;
        -h|--help) sed -n '2,/^set -e/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
        *) ARGS+=("$1") ;;
    esac
    shift
done
[ "${#ARGS[@]}" -ge 2 ] && [ "${#ARGS[@]}" -le 3 ] || { echo "usage: tools/export_patch.sh <slug> \"<description>\" [\"<upstream status>\"] [--count N]" >&2; exit 2; }
SLUG=${ARGS[0]} DESC=${ARGS[1]} STATUS=${ARGS[2]:-offer upstream}
[[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "export_patch: slug must be lower-case words joined by '-'" >&2; exit 2; }
[[ "$COUNT" =~ ^[1-9][0-9]*$ ]] || { echo "export_patch: --count needs a number >= 1" >&2; exit 2; }
case "$DESC$STATUS" in *'|'*) echo "export_patch: no '|' in the description (it is a table cell)" >&2; exit 2 ;; esac

[ "$(git -C "$SUB" rev-parse --abbrev-ref HEAD)" = sarpbc-patches ] || { echo "export_patch: external/ps3recomp is not on sarpbc-patches" >&2; exit 1; }
[ -z "$(git -C "$SUB" status --porcelain --untracked-files=no)" ] || { echo "export_patch: external/ps3recomp has uncommitted changes; commit them first" >&2; exit 1; }

n=$(find "$DIR" -maxdepth 1 -name '[0-9][0-9][0-9][0-9]-*.patch' | sed 's#.*/##; s/-.*//' | sort | tail -1)
N=$(printf '%04d' $((10#${n:-0000} + 1)))
OUT=$DIR/$N-$SLUG.patch
# The commits being exported must not already be in the stack: the stack's own patches are
# applied commits too, so compare counts (pin..HEAD) with the number of patch files.
have=$(cat "$DIR"/[0-9][0-9][0-9][0-9]-*.patch | grep -c '^From [0-9a-f]\{40\} ' || true)
pin=$(git -C "$ROOT" ls-tree HEAD external/ps3recomp | awk '{print $3}')
commits=$(git -C "$SUB" rev-list --count "$pin"..HEAD)
[ "$commits" -eq $((have + COUNT)) ] || { echo "export_patch: the branch has $commits commits over the pin, the stack has $have; expected exactly $COUNT new. Run tools/apply_patches.sh or fix --count." >&2; exit 1; }

git -C "$SUB" format-patch -"$COUNT" --stdout > "$OUT"
printf '| `%s` | %s | %s |\n' "$N-$SLUG.patch" "$DESC" "$STATUS" > "$OUT.row"
python3 - "$DIR/README.md" "$OUT.row" <<'PY'
import sys
readme, rowfile = sys.argv[1:]
row = open(rowfile).read()
lines = open(readme).read().split('\n')
last = max(i for i, l in enumerate(lines) if l.startswith('| `0') and '.patch`' in l)
lines.insert(last + 1, row.rstrip('\n'))
open(readme, 'w').write('\n'.join(lines))
PY
rm -f "$OUT.row"
echo "exported $OUT"
echo "README row added; next: tools/lint.py --tests, then commit patches/ps3recomp/ in the superproject."
