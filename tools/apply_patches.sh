#!/usr/bin/env bash
# Put external/ps3recomp on branch sarpbc-patches = the pinned upstream commit +
# patches/ps3recomp/*.patch, in order. Run it after a clone, after `git submodule
# update`, and after adding or editing a patch. Rebuild afterwards (the runtime is
# compiled from it).
#
#   tools/apply_patches.sh            # rebuild the branch from the pin, unconditionally
#   tools/apply_patches.sh --ensure   # only when the checkout is not already that tree (build.sh)
#
# The patched tree is first built in a scratch worktree, so a patch that no longer applies,
# or a dirty checkout, leaves external/ps3recomp exactly as it was. "Already right" means
# the checkout's tree hash equals the scratch result's: patch contents are compared, not
# commit counts. A stamp in the submodule's git dir ("<hash of pin + patches> <tree>")
# skips even the scratch build while nothing changed.
#
# A dirty checkout is refused (exit 1). SARPBC_ALLOW_DIRTY_RUNTIME=1 downgrades that, in
# --ensure mode only, to a warning that builds whatever is there (experiments).
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SUB=$ROOT/external/ps3recomp
ensure=0
case "${1:-}" in
    '') ;;
    --ensure) ensure=1 ;;
    *) echo "usage: tools/apply_patches.sh [--ensure]" >&2; exit 1 ;;
esac

[ -e "$SUB/.git" ] || git -C "$ROOT" submodule update --init external/ps3recomp >/dev/null
# The commit the superproject pins (not whatever the submodule has checked out).
PIN=$(git -C "$ROOT" ls-tree HEAD external/ps3recomp | awk '{print $3}')
GITDIR=$(git -C "$SUB" rev-parse --absolute-git-dir)
STAMP=$GITDIR/sarpbc-patches.stamp
shopt -s nullglob
patches=("$ROOT"/patches/ps3recomp/*.patch)

# Preflight: nothing below touches the checkout until these pass.
if ! git -C "$SUB" diff --quiet || ! git -C "$SUB" diff --cached --quiet \
   || [ -e "$GITDIR/rebase-apply" ] || [ -e "$GITDIR/rebase-merge" ]; then
    if [ $ensure = 1 ] && [ "${SARPBC_ALLOW_DIRTY_RUNTIME:-}" = 1 ]; then
        echo "warning: external/ps3recomp has uncommitted changes; building it as is (SARPBC_ALLOW_DIRTY_RUNTIME=1)" >&2
        exit 0
    fi
    echo "external/ps3recomp has uncommitted changes or an unfinished git am; commit them to a patch first" >&2
    exit 1
fi

want=$( { echo "$PIN"; cat "${patches[@]}" 2>/dev/null; } | sha256sum | cut -d' ' -f1)
tree=$(git -C "$SUB" rev-parse 'HEAD^{tree}')
on_branch=$([ "$(git -C "$SUB" branch --show-current)" = sarpbc-patches ] && echo 1 || echo 0)
if [ "$ensure" = 1 ] && [ "$on_branch" = 1 ]; then
    read -r have_want have_tree 2>/dev/null < "$STAMP" || have_want='' have_tree=''
    if [ "$have_want" = "$want" ] && [ "$have_tree" = "$tree" ]; then exit 0; fi
fi

if ! git -C "$SUB" cat-file -e "$PIN^{commit}" 2>/dev/null; then
    git -C "$ROOT" submodule update --init external/ps3recomp >/dev/null
fi

# Build the expected result away from the checkout.
scratch=$(mktemp -d "$GITDIR/sarpbc-scratch.XXXXXX")
cleanup() { git -C "$SUB" worktree remove --force "$scratch" 2>/dev/null || rm -rf "$scratch"; git -C "$SUB" worktree prune; }
trap cleanup EXIT
git -C "$SUB" worktree add -q --detach "$scratch" "$PIN"
if [ ${#patches[@]} -gt 0 ]; then
    if ! git -C "$scratch" -c user.name=sarpbc -c user.email=sarpbc@localhost am -q --keep-cr --committer-date-is-author-date "${patches[@]}"; then
        echo "patch stack does not apply on ${PIN:0:7}; external/ps3recomp was not touched" >&2
        exit 1
    fi
fi
result=$(git -C "$scratch" rev-parse HEAD)
expected=$(git -C "$scratch" rev-parse 'HEAD^{tree}')

if [ "$ensure" = 1 ] && [ "$on_branch" = 1 ] && [ "$tree" = "$expected" ]; then
    echo "$want $tree" > "$STAMP"
    exit 0
fi

# Moving the branch: keep the old tip reachable in case it held unexported commits.
old=$(git -C "$SUB" rev-parse HEAD)
if [ "$old" != "$result" ] && [ "$old" != "$PIN" ]; then
    git -C "$SUB" update-ref "refs/sarpbc-backup/$(date +%Y%m%d-%H%M%S)-${old:0:7}" "$old"
    echo "note: previous external/ps3recomp HEAD ${old:0:7} kept as refs/sarpbc-backup/*" >&2
fi
cleanup; trap - EXIT
git -C "$SUB" checkout -q -B sarpbc-patches "$result"
echo "$want $expected" > "$STAMP"
echo "external/ps3recomp: $(git -C "$SUB" rev-list --count "$PIN"..HEAD) patch(es) on ${PIN:0:7}"
