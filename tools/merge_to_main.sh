#!/usr/bin/env bash
# Merge this worktree's branch into main (docs/workflow.md "Finishing a task").
# There is no coordinator: each agent merges its own verified work, under the
# merge lock so two agents never merge at once. Run from your worktree, with
# everything committed, built and verified:
#
#   tools/task.sh lock merge tools/merge_to_main.sh
#
#   1. merge main into your branch (stops on conflicts: resolve, commit, verify, rerun)
#   2. renumber patches/ps3recomp/T###-*.patch to the next free 00NN- numbers, in
#      their current (apply) order, and fix their names in the patch README and docs/
#   3. check the whole patch stack applies from the pin (tools/apply_patches.sh) and
#      that tools/lint.py passes
#   4. fast-forward main in the main checkout, re-apply the patch stack there if it
#      changed, and commit the task board (docs/tasks/ lives uncommitted in the main
#      checkout)
#   5. push main to origin, if there is one. If the push fails, the merge has still
#      happened: fix the cause and rerun (every step above is a no-op the second time)
set -euo pipefail

WT=$(cd "$(dirname "$0")/.." && pwd)
MAIN=$(dirname "$(git -C "$WT" rev-parse --path-format=absolute --git-common-dir)")
[ "$WT" != "$MAIN" ] || { echo "run this from your worktree, not the main checkout" >&2; exit 1; }
BR=$(git -C "$WT" branch --show-current)
[ -n "$BR" ] && [ "$BR" != main ] || { echo "your worktree must be on its own branch" >&2; exit 1; }
[ -z "$(git -C "$WT" status --porcelain --untracked-files=no --ignore-submodules=all)" ] \
    || { echo "commit your changes first" >&2; exit 1; }
[ "$(git -C "$MAIN" branch --show-current)" = main ] || { echo "the main checkout is not on main" >&2; exit 1; }
dirty=$(git -C "$MAIN" status --porcelain --untracked-files=no --ignore-submodules=all -- . ':!docs/tasks')
[ -z "$dirty" ] || { printf 'the main checkout has changes outside docs/tasks/:\n%s\n' "$dirty" >&2; exit 1; }

# 1. Bring main in.
if ! git -C "$WT" merge -q --no-edit main; then
    echo "merge conflicts with main: resolve them, commit, rebuild and verify, then rerun" >&2
    exit 1
fi

# 2. Renumber this branch's patches.
P=$WT/patches/ps3recomp
last=$(cd "$P" && ls [0-9][0-9][0-9][0-9]-*.patch 2>/dev/null | tail -1 | cut -c1-4)
n=$((10#${last:-0}))
renamed=()
for f in "$P"/T[0-9][0-9][0-9]-*.patch; do
    [ -e "$f" ] || continue
    old=$(basename "$f")
    n=$((n + 1))
    new=$(printf '%04d-%s' "$n" "$(sed -E 's/^T[0-9]{3}-([0-9]+-)?//' <<<"$old")")
    git -C "$WT" mv "patches/ps3recomp/$old" "patches/ps3recomp/$new"
    # The README row, and every doc that names the patch (with or without .patch).
    grep -lF "${old%.patch}" "$P/README.md" "$WT"/AGENTS.md "$WT"/docs/*.md \
        | xargs -r sed -i "s/${old%.patch}/${new%.patch}/g"
    renamed+=("$old -> $new")
done
if [ ${#renamed[@]} -gt 0 ]; then
    git -C "$WT" add patches/ps3recomp/README.md AGENTS.md docs/*.md
    git -C "$WT" commit -q -m "patches: renumber for merge ($(printf '%s; ' "${renamed[@]}" | sed 's/; $//'))"
    printf 'renumbered: %s\n' "${renamed[@]}"
fi

# 3. The whole stack must apply from the pin, and the repo must lint clean.
"$WT/tools/apply_patches.sh"
"$WT/tools/lint.py" || { echo "tools/lint.py found problems: fix them, commit, rerun" >&2; exit 1; }

# 4. Fast-forward main, sync its submodule, commit the board.
before=$(git -C "$MAIN" rev-parse main)
git -C "$MAIN" merge -q --ff-only "$BR"
if ! git -C "$MAIN" diff --quiet "$before" main -- patches/ps3recomp; then
    "$MAIN/tools/apply_patches.sh"
fi
if [ -n "$(git -C "$MAIN" status --porcelain -- docs/tasks)" ]; then
    git -C "$MAIN" add docs/tasks
    git -C "$MAIN" commit -q -m "tasks: board after merging $BR"
fi
echo "merged $BR into main: ${before:0:7}..$(git -C "$MAIN" rev-parse --short main)"

# 5. Publish main. Only main is pushed: agent branches stay local.
if git -C "$MAIN" remote get-url origin >/dev/null 2>&1; then
    if ! git -C "$MAIN" push -q origin main; then
        echo "push to origin failed: main is merged locally; fix the cause and rerun this script" >&2
        exit 1
    fi
    echo "pushed main to origin"
fi
echo "main's own builds are stale now; rebuild them when you next need them"
