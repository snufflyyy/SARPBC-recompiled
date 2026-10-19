#!/usr/bin/env bash
# Put external/ps3recomp on branch sarpbc-patches = the pinned upstream commit +
# patches/ps3recomp/*.patch, in order. Idempotent: the branch is rebuilt from the
# pin every time, so run it after a clone, after `git submodule update`, and after
# adding or editing a patch. Rebuild afterwards (the runtime is compiled from it).
#
#   tools/apply_patches.sh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SUB=$ROOT/external/ps3recomp

git -C "$ROOT" submodule update --init external/ps3recomp >/dev/null
# The commit the superproject pins (not whatever the submodule has checked out).
PIN=$(git -C "$ROOT" ls-tree HEAD external/ps3recomp | awk '{print $3}')

if ! git -C "$SUB" diff --quiet || ! git -C "$SUB" diff --cached --quiet; then
    echo "external/ps3recomp has uncommitted changes; commit them to a patch first" >&2
    exit 1
fi

git -C "$SUB" checkout -q -B sarpbc-patches "$PIN"
shopt -s nullglob
patches=("$ROOT"/patches/ps3recomp/*.patch)
if [ ${#patches[@]} -gt 0 ]; then
    git -C "$SUB" -c user.name=sarpbc -c user.email=sarpbc@localhost am -q --committer-date-is-author-date "${patches[@]}"
fi
echo "external/ps3recomp: $(git -C "$SUB" log --oneline "$PIN"..HEAD | wc -l) patch(es) on ${PIN:0:7}"
