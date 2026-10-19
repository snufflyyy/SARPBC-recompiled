#!/usr/bin/env bash
# Task board and locks for the agents the user starts (docs/workflow.md): Claude
# Code, pi, Antigravity, ... each under its own name. No agent spawns another.
#
# The board is tasks/{open,claimed,done}/<ID>-<slug>.md in the MAIN checkout,
# whichever worktree this runs from, so every agent sees the same live state.
# Claiming is a rename(2) of the task file from open/ to claimed/: atomic, so
# exactly one agent wins; the loser gets "already claimed".
# Queue order is each task's "Priority:" line (lower first; "blocked" = never
# picked; no line = last).
#
#   tools/task.sh list                               # open by priority; claimed with owner + last activity
#   tools/task.sh next                               # the open task to take next, and what is claimed
#   tools/task.sh show    <ID>
#   tools/task.sh claim   <ID> <agent>
#   tools/task.sh note    <ID> <agent> <text...>     # append to the task's log
#   tools/task.sh done    <ID> <agent> <summary...>
#   tools/task.sh release <ID> <agent> <reason...>   # back to open/
#   tools/task.sh new     <slug> <title...>           # next free ID
#   tools/task.sh lock    <name> <command...>         # run under $MAIN/.locks/<name>.lock
set -euo pipefail

MAIN=$(dirname "$(git -C "$(dirname "$0")" rev-parse --path-format=absolute --git-common-dir)")
B=$MAIN/tasks
mkdir -p "$B/open" "$B/claimed" "$B/done" "$MAIN/.locks"

now() { date '+%Y-%m-%d %H:%M'; }
find_task() {   # find_task <ID> <state...> -> path or empty
    local id=$1; shift
    for s in "$@"; do
        for f in "$B/$s/$id"-*.md; do [ -e "$f" ] && { echo "$f"; return; }; done
    done
}
log() { printf -- '- %s %s: %s\n' "$(now)" "$2" "$3" >> "$1"; }
field() { grep -m1 "^$2:" "$1" | cut -d' ' -f2- || true; }   # field <file> <name>
prio() {        # prio <file> -> sort key
    local p; p=$(field "$1" Priority)
    case "$p" in blocked) echo 9999 ;; ''|*[!0-9]*) echo 999 ;; *) echo "$p" ;; esac
}
open_by_prio() {    # open task files, queue order
    for f in "$B/open"/*.md; do [ -e "$f" ] && printf '%s\t%s\n' "$(prio "$f")" "$f"; done | sort -n -k1,1 -s | cut -f2
}
last_log() { grep -E '^- [0-9]{4}-' "$1" | tail -1 | cut -c3-18; }

cmd=${1:-list}; shift || true
case "$cmd" in
list)
    echo "== open (queue order)"
    open_by_prio | while read -r f; do
        printf '  P%-8s %s\n' "$(field "$f" Priority)" "$(basename "$f" .md)"
    done
    echo "== claimed"
    for f in "$B/claimed"/*.md; do
        [ -e "$f" ] || continue
        printf '  %-40s (%s, last log %s)\n' "$(basename "$f" .md)" "$(field "$f" Owner)" "$(last_log "$f")"
    done
    echo "== done"
    for f in "$B/done"/*.md; do [ -e "$f" ] && printf '  %s\n' "$(basename "$f" .md)"; done ;;
next)
    echo "== claimed (don't overlap their Touches)"
    for f in "$B/claimed"/*.md; do
        [ -e "$f" ] || continue
        printf '  %s (%s): %s\n' "$(basename "$f" .md)" "$(field "$f" Owner)" "$(field "$f" Touches)"
    done
    echo "== next open, in order"
    open_by_prio | while read -r f; do
        [ "$(field "$f" Priority)" = blocked ] && continue
        printf '  P%-4s %s\n         Touches: %s\n' "$(field "$f" Priority)" "$(basename "$f" .md)" "$(field "$f" Touches)"
    done | head -9 ;;
show)
    f=$(find_task "$1" open claimed done); [ -n "$f" ] || { echo "no task $1" >&2; exit 1; }
    cat "$f" ;;
claim)
    id=$1 agent=$2
    f=$(find_task "$id" open); [ -n "$f" ] || { echo "task $id is not open (already claimed or unknown)" >&2; exit 1; }
    dest=$B/claimed/$(basename "$f")
    if ! mv "$f" "$dest" 2>/dev/null; then echo "task $id: already claimed" >&2; exit 1; fi
    sed -i "s/^Status:.*/Status: claimed/; s/^Owner:.*/Owner: $agent/" "$dest"
    grep -q '^Owner:' "$dest" || sed -i "/^Status:/a Owner: $agent" "$dest"
    log "$dest" "$agent" "claimed"
    echo "claimed $id -> $dest" ;;
note)
    id=$1 agent=$2; shift 2
    f=$(find_task "$id" claimed open); [ -n "$f" ] || { echo "no task $id" >&2; exit 1; }
    log "$f" "$agent" "$*" ;;
done)
    id=$1 agent=$2; shift 2
    f=$(find_task "$id" claimed); [ -n "$f" ] || { echo "task $id is not claimed" >&2; exit 1; }
    log "$f" "$agent" "DONE: $*"
    sed -i "s/^Status:.*/Status: done/" "$f"
    mv "$f" "$B/done/"
    echo "done $id" ;;
release)
    id=$1 agent=$2; shift 2
    f=$(find_task "$id" claimed); [ -n "$f" ] || { echo "task $id is not claimed" >&2; exit 1; }
    log "$f" "$agent" "RELEASED: $*"
    sed -i "s/^Status:.*/Status: open/; s/^Owner:.*/Owner: -/" "$f"
    mv "$f" "$B/open/"
    echo "released $id" ;;
new)
    slug=$1; shift
    last=$(ls "$B"/*/ 2>/dev/null | grep -o '^T[0-9]\{3\}' | sort | tail -1)
    last=${last:-T000}
    n=$(( 10#${last#T} + 1 ))
    id=$(printf 'T%03d' "$n")
    f=$B/open/$id-$slug.md
    printf '# %s: %s\n\nStatus: open\nOwner: -\nPriority: \nTouches: \nReads: \n\n## Goal\n\n## Done when\n\n## Log\n' "$id" "$*" > "$f"
    echo "$f" ;;
lock)
    name=$1; shift
    exec flock "$MAIN/.locks/$name.lock" "$@" ;;
*)
    sed -n '2,23p' "$0"; exit 1 ;;
esac
