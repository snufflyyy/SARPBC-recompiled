#!/usr/bin/env python3
"""Give the linker's TOC-switch stubs function boundaries of their own.

The EBOOT is big enough to need several TOCs, so the linker emits a run of
stubs that switch r2 before branching into another TOC's code:

    std   r2,40(r1)
    addis r2,r2,HI      (and/or)
    addi  r2,r2,LO
    b     target

The run (4,242 stubs at 0x1921350..0x1930880 in 1.02) sits after the last
OPD function, so ppu_loader folds the whole run into that function's range.
Every stub is a call target, so the lifter then emits each one as a
mid-function tail-entry wrapper that runs to the end of the range: ~6,000
lines of dead code per 16-byte stub, two thirds of the lifted source.

This splits every run of at least MIN_RUN consecutive stubs into one function
per stub and ends any function that overlapped the run where the run starts.

    python tools/split_toc_stubs.py game/EBOOT.elf analysis/EBOOT.functions.json \
        -o analysis/EBOOT.functions.split.json
"""
import argparse
import json
import struct
import sys

STD_R2_40_R1 = 0xF8410028
MIN_RUN = 4         # a lone std r2,40(r1) can be ordinary code; runs are stubs


def load_text(path):
    d = open(path, "rb").read()
    phoff, = struct.unpack_from(">Q", d, 0x20)
    phentsize, phnum = struct.unpack_from(">HH", d, 0x36)
    for i in range(phnum):
        p = phoff + i * phentsize
        p_type, p_flags = struct.unpack_from(">II", d, p)
        off, vaddr, _, filesz = struct.unpack_from(">QQQQ", d, p + 8)
        if p_type == 1 and p_flags & 1:          # PT_LOAD, executable
            return vaddr, d[off:off + filesz]
    sys.exit("no executable PT_LOAD segment")


def stub_end(word, a):
    """Address just past the stub starting at a, or None if a is not a stub."""
    if word(a) != STD_R2_40_R1:
        return None
    for k in range(1, 4):
        w = word(a + 4 * k)
        if w >> 26 == 18 and not w & 3:          # b target (no link, relative)
            return a + 4 * (k + 1)
        if w >> 16 not in (0x3C42, 0x3842):      # addis/addi r2,r2,imm
            return None
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("elf")
    ap.add_argument("functions", help="ppu_loader EBOOT.functions.json")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    base, text = load_text(args.elf)
    word = lambda a: struct.unpack_from(">I", text, a - base)[0] if base <= a < base + len(text) - 3 else 0

    runs, a, end = [], base, base + len(text)
    while a < end:
        stubs, b = [], a
        while (e := stub_end(word, b)) is not None:
            stubs.append((b, e))
            b = e
        if len(stubs) >= MIN_RUN:
            runs.append(stubs)
            a = b
        else:
            a += 4

    funcs = json.load(open(args.functions))
    h = lambda v: int(str(v), 0)
    out, trimmed = [], 0
    run_starts = sorted(r[0][0] for r in runs)
    for f in funcs:
        s, e = h(f["start"]), h(f["end"])
        inside = [r for r in run_starts if s < r < e]
        if inside:
            f = dict(f, end=hex(inside[0]))
            trimmed += 1
        if not any(r[0][0] <= s < r[-1][1] for r in runs):
            out.append(f)
    for r in runs:
        out.extend({"start": hex(s), "end": hex(e)} for s, e in r)
    out.sort(key=lambda f: h(f["start"]))

    json.dump(out, open(args.output, "w"), indent=1)
    n = sum(len(r) for r in runs)
    print(f"toc stubs: {len(runs)} run(s), {n} stubs "
          + ", ".join(f"{hex(r[0][0])}..{hex(r[-1][1])}" for r in runs)
          + f"; trimmed {trimmed} function(s) -> {args.output}")


if __name__ == "__main__":
    main()
