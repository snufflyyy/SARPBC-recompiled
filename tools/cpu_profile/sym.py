#!/usr/bin/env python3
"""Name the instruction pointers in a tools/cpu_profile.sh dump and print each thread's top functions.

  sym.py <dump> <exe> [top]

The dump holds MAP lines (executable mappings), T lines (thread names), and S lines
(<tid> <rip> <samples>). The game is a PIE whose virtual addresses equal its file offsets, so a
sample's symbol is the last `nm` function at or below rip - (map start - map offset). Lifted guest
functions keep their func_XXXXXXXX names; a sample in a library shows the library's file name.
"""
import bisect
import collections
import subprocess
import sys


def main():
    dump, exe = sys.argv[1], sys.argv[2]
    top = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    maps, samples, thread_names = [], [], {}
    for line in open(dump):
        p = line.split()
        if p[0] == "T":
            thread_names[p[1]] = " ".join(p[2:])
        elif p[0] == "MAP":
            maps.append((int(p[1], 16), int(p[2], 16), int(p[3], 16), p[4]))
        elif p[0] == "S":
            samples.append((int(p[1]), int(p[2], 16), int(p[3])))
    nm = subprocess.run(["nm", "-n", "--defined-only", exe], capture_output=True, text=True).stdout
    addrs, names = [], []
    for line in nm.split("\n"):
        q = line.split(None, 2)
        if len(q) == 3 and q[1] in "tTwW":
            addrs.append(int(q[0], 16))
            names.append(q[2])
    exe_name = exe.split("/")[-1]

    def symbol(rip):
        for lo, hi, off, path in maps:
            if lo <= rip < hi:
                if path.endswith(exe_name):
                    i = bisect.bisect_right(addrs, rip - (lo - off)) - 1
                    return names[i] if i >= 0 else "?"
                return path.split("/")[-1]
        return "?"

    by_thread = collections.defaultdict(collections.Counter)
    total = collections.Counter()
    for tid, rip, count in samples:
        by_thread[tid][symbol(rip)] += count
        total[tid] += count
    for tid, t in total.most_common(6):
        print(f"TID {tid} [{thread_names.get(str(tid), '?')}]: {t} samples")
        for name, v in by_thread[tid].most_common(top):
            print(f"  {100 * v / t:5.1f}% {name}")


if __name__ == "__main__":
    main()
