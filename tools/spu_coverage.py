#!/usr/bin/env python3
"""List the bytes of each lifted SPU image that no generated function covers (task T010).

The SPU lifter's own report says "Function coverage: N / M bytes -- the rest is
data/padding embedded in .text". This tool checks that claim: it takes every image's
executable ranges (inventory.json), subtracts the function ranges the lifter generated
(lift.json / report.json), and gives each uncovered range a verdict from a disassembly of
its bytes and from who references it. Read-only; needs the git-ignored game-derived lift
output and the ps3recomp toolkit's SPU decoder (external/ps3recomp/tools).

  tools/spu_coverage.py [--version 0109|0102] [--spu-dir DIR] [--image NAMEPART]
                        [-v] [--json] [--strict]

  --version   which lift to read: 0109 (default, versions/0109/src/spu_gen) or 0102 (src/spu_gen)
  --spu-dir   read this spu_gen directory instead (inventory.json + spu_*/ dirs)
  --image     only images whose directory name contains this text (hash prefix, "prxjob")
  -v          list every uncovered range with its evidence, not just the per-image summary
  --json      machine-readable output
  --strict    exit 1 if any range is "code?" (a candidate missed function); default exit 0

Worktrees do not hold the game data or the submodule: both are looked up in the main
checkout (git common dir) when missing here.

Verdicts, in order of test (the first that matches wins):
  zero       every word is 0
  padding    only nop/lnop/zero words (alignment fill between functions)
  string     mostly printable ASCII / NUL (printf formats, zlib messages, names)
  data       words that decode as no SPU instruction, mostly small integers (jump-table offsets),
             mostly plausible float32 constants,
             an lqa/lqr target, or the 16-byte image signature quad at the segment start
  post-stop  decodes as code and sits right after a function that ends in `stop`: the
             compiler's epilogue after a noreturn call (unreachable by construction)
  code?      decodes as code and something reaches it: a word in data or an ila/ilhu+iohl
             constant equal to its start (function pointer), or the function before it
             falls through into it. A candidate missed function: needs a lifter fix.
  dead       decodes as code, nothing references it (an unused library function, dead tail)
  unclear    none of the above
"Decodes as code" = no undecodable word, at least 85% of the instructions use mnemonics that
occur at least twice in the image's own lifted functions, and every relative branch lands
inside an executable range.
"""
import argparse
import json
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

NOPS = {0x00000000, 0x00200000, 0x40200000}
CLASSES = ["zero", "padding", "string", "data", "post-stop", "code?", "dead", "unclear"]
ENDERS = ("stop", "stopd", "bi", "br", "bra", "iret")      # after these, control does not fall through
REL_BRANCH = ("br", "brsl", "brz", "brnz", "brhz", "brhnz", "hbrr")


def main_checkout():
    """The main checkout (agent worktrees do not hold game data or the submodule)."""
    try:
        out = subprocess.run(["git", "-C", ROOT, "rev-parse", "--git-common-dir"],
                             capture_output=True, text=True, check=True).stdout.strip()
        return os.path.dirname(os.path.normpath(os.path.join(ROOT, out)))
    except (OSError, subprocess.CalledProcessError):
        return ROOT


def first_existing(rel, roots):
    for r in roots:
        p = os.path.join(r, rel)
        if os.path.exists(p):
            return p
    return os.path.join(roots[0], rel)


def load_toolkit(roots):
    tools = first_existing("external/ps3recomp/tools/spu_disasm.py", roots)
    sys.path.insert(0, os.path.dirname(tools))
    import spu_disasm   # noqa: E402
    import spu_elf      # noqa: E402
    return spu_disasm, spu_elf


def merge(spans):
    out = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def subtract(ranges, covered):
    gaps = []
    for a, b in ranges:
        pos = a
        for s, e in covered:
            if e <= pos or s >= b:
                continue
            if s > pos:
                gaps.append((pos, s))
            pos = max(pos, e)
        if pos < b:
            gaps.append((pos, b))
    return gaps


def sane_float(w):
    """True for 0 and floats of magnitude 2^-20..2^40 (typical DSP/physics constants)."""
    if w == 0:
        return True
    exp = (w >> 23) & 0xFF
    return 107 <= exp <= 167


def simm16(w):
    v = (w >> 7) & 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


class Image:
    def __init__(self, name, blob, layout, ranges, funcs, dis):
        self.name = name
        self.ranges = merge(ranges)
        self.funcs = merge(funcs)
        self.blob = blob
        self.loads = layout["loads"]
        self.insn = {}
        for x in layout["executable"]:
            seg = blob[x["off"]:x["off"] + x["filesz"]]
            for ins in dis.disassemble_spu(seg, base_addr=x["addr"]):
                self.insn[ins.addr] = ins
        self.gaps = subtract(self.ranges, self.funcs)
        self._mnemonics()
        self._refs()

    def in_func(self, a):
        return any(s <= a < e for s, e in self.funcs)

    def in_ranges(self, a):
        return any(s <= a < e for s, e in self.ranges)

    def _mnemonics(self):
        """Mnemonic frequencies over the lifted functions: what this image's real code looks like."""
        hist = {}
        n = 0
        for s, e in self.funcs:
            for a in range(s, e, 4):
                i = self.insn.get(a)
                if i:
                    hist[i.mnemonic] = hist.get(i.mnemonic, 0) + 1
                    n += 1
        self.common = {m for m, c in hist.items() if m != ".word" and c >= 2} | {"nop", "lnop"}

    def _refs(self):
        """What points at an address: data loads, constants, and pointer words outside any function."""
        self.lq = set()        # lqa/lqr/stqa/stqr targets (data access)
        self.consts = set()    # ila / ilhu+iohl constants (code or data pointer)
        ilhu = {}
        for a, ins in sorted(self.insn.items()):
            w, m = ins.raw, ins.mnemonic
            if m in ("lqa", "stqa"):
                self.lq.add((simm16(w) << 2) & 0x3FFFF)
            elif m in ("lqr", "stqr"):
                self.lq.add((a + (simm16(w) << 2)) & 0x3FFFF)
            elif m == "ila":
                self.consts.add((w >> 7) & 0x3FFFF)
            elif m == "ilhu":
                ilhu[w & 0x7F] = ((w >> 7) & 0xFFFF) << 16
            elif m == "iohl" and (w & 0x7F) in ilhu:
                self.consts.add((ilhu[w & 0x7F] | ((w >> 7) & 0xFFFF)) & 0x3FFFF)
        # 32-bit words in bytes that no lifted function covers (data segments, gaps):
        # a function-pointer table or vtable would show up as one of these.
        self.ptr_src = {}
        for p in self.loads:
            seg = self.blob[p["off"]:p["off"] + p["filesz"]]
            for o in range(0, len(seg) - 3, 4):
                addr = p["addr"] + o
                if self.in_func(addr):
                    continue
                v = struct.unpack_from(">I", seg, o)[0]
                if v and v < 0x40000 and v % 4 == 0:
                    self.ptr_src.setdefault(v, []).append(addr)

    def code_like(self, a, b):
        insns = [self.insn[x] for x in range(a, b, 4) if x in self.insn]
        if not insns or any(i.mnemonic == ".word" for i in insns):
            return False
        if sum(1 for i in insns if i.mnemonic in self.common) < 0.85 * len(insns):
            return False
        for i in insns:
            if i.mnemonic in REL_BRANCH:
                t = (i.addr + (simm16(i.raw) << 2)) & 0x3FFFF
                if not self.in_ranges(t):
                    return False
        return True

    def classify(self, a, b):
        ws = [self.insn[x].raw for x in range(a, b, 4) if x in self.insn]
        raw = b"".join(struct.pack(">I", w) for w in ws)
        n = len(ws)
        st = dict(start=a, end=b, size=b - a)
        if n == 0:
            st["verdict"] = "unclear"
            return st
        insns = [self.insn[x] for x in range(a, b, 4)]
        undec = sum(1 for i in insns if i.mnemonic == ".word")
        floats = sum(1 for w in ws if sane_float(w))
        small = sum(1 for w in ws if 0 < w < 0x400000)   # jump-table offsets / small ints (decode as stop)
        printable = sum(1 for c in raw if c == 0 or 0x20 <= c < 0x7F)
        run = text_run = 0
        for c in raw:
            run = run + 1 if 0x20 <= c < 0x7F else 0
            text_run = max(text_run, run)
        lq_hit = any(a <= r < b for r in self.lq)
        prev = self.insn.get(a - 4)
        after_func = prev is not None and self.in_func(a - 4)
        after_stop = after_func and prev.mnemonic == "stop"
        falls = after_func and prev.mnemonic not in ENDERS
        sig = (a % 0x10 == 0 and b - a == 16 and not after_func
               and all(i.mnemonic == "ila" and i.raw & 0x7F == 2 for i in insns))
        refs = [r for r in self.ptr_src.get(a, []) if not a <= r < b]
        st.update(undecodable=undec, float_like=round(floats / n, 2), ascii_frac=round(printable / len(raw), 2),
                  lq_ref=lq_hit, const_ref=a in self.consts, ptr_refs=refs[:4], after_stop=after_stop,
                  falls_through=falls, signature=sig)
        if all(w == 0 for w in ws):
            v = "zero"
        elif all(w in NOPS for w in ws):
            v = "padding"
        elif text_run >= 6 and printable / len(raw) >= 0.6:
            v = "string"
        elif sig or undec or small >= 0.5 * n or floats / n >= 0.6 or lq_hit:
            v = "data"
        elif self.code_like(a, b):
            if after_stop:
                v = "post-stop"
            elif refs or a in self.consts or falls:
                v = "code?"
            else:
                v = "dead"
        else:
            v = "unclear"
        st["verdict"] = v
        return st


def read_funcs(d):
    for fn in ("lift.json", "report.json"):
        p = os.path.join(d, fn)
        if os.path.isfile(p):
            with open(p) as f:
                return [tuple(x) for x in json.load(f)["functions"]]
    return None


def audit(spu_dir, only, dis, elf):
    with open(os.path.join(spu_dir, "inventory.json")) as f:
        inv = json.load(f)
    dirs = [(p["name"], p) for p in inv["programs"]]
    known = {n for n, _ in dirs}
    for extra in sorted(os.listdir(spu_dir)):
        if extra.startswith("spu_prxjob_") and extra not in known:
            dirs.append((extra, None))
    results = []
    for name, prog in dirs:
        if only and only not in name:
            continue
        d = os.path.join(spu_dir, name)
        funcs = read_funcs(d)
        img = os.path.join(d, "image.elf")
        if funcs is None or not os.path.isfile(img):
            continue
        with open(img, "rb") as f:
            blob = f.read()
        layout = elf.validate_spu_elf(blob)
        if prog and prog.get("executable_ranges"):
            ranges = [tuple(r) for r in prog["executable_ranges"]]
        else:
            sec = [(s["addr"], s["addr"] + s["size"]) for s in layout["sections"] if s["flags"] & 4 and s["size"]]
            ranges = sorted(sec) or sorted((x["addr"], x["addr"] + x["filesz"]) for x in layout["executable"])
        im = Image(name, blob, layout, ranges, funcs, dis)
        rows = [im.classify(a, b) for a, b in im.gaps]
        total = sum(b - a for a, b in im.ranges)
        results.append(dict(name=name, fingerprint=(prog or {}).get("fingerprint"),
                            exec_bytes=total, uncovered=sum(r["size"] for r in rows),
                            functions=len(funcs), ranges=rows))
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--version", default="0109", choices=["0109", "0102"])
    ap.add_argument("--spu-dir")
    ap.add_argument("--image")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    roots = [ROOT]
    mc = main_checkout()
    if mc != ROOT:
        roots.append(mc)
    dis, elf = load_toolkit(roots)
    rel = "versions/0109/src/spu_gen" if args.version == "0109" else "src/spu_gen"
    spu_dir = args.spu_dir or os.path.dirname(first_existing(rel + "/inventory.json", roots))
    res = audit(spu_dir, args.image, dis, elf)
    if args.json:
        json.dump(res, sys.stdout, indent=1)
        print()
    else:
        print("%-16s %8s %8s %5s  %s" % ("image", "exec B", "uncov B", "gaps", " ".join("%9s" % c for c in CLASSES)))
        tot = dict.fromkeys(CLASSES, 0)
        tot_b = dict.fromkeys(CLASSES, 0)
        for r in res:
            cnt = dict.fromkeys(CLASSES, 0)
            for g in r["ranges"]:
                cnt[g["verdict"]] += 1
                tot[g["verdict"]] += 1
                tot_b[g["verdict"]] += g["size"]
            print("%-16s %8d %8d %5d  %s" % (r["name"].replace("spu_", "")[:16], r["exec_bytes"], r["uncovered"],
                                             len(r["ranges"]), " ".join("%9d" % cnt[c] for c in CLASSES)))
            if args.verbose:
                for g in r["ranges"]:
                    flags = "".join(" " + k for k in ("lq_ref", "const_ref", "after_stop", "falls_through", "signature")
                                    if g.get(k))
                    if g.get("ptr_refs"):
                        flags += " ptr@" + ",".join("%X" % x for x in g["ptr_refs"])
                    print("    %05X-%05X %6d B  %-9s undec=%d float=%.2f ascii=%.2f%s" % (
                        g["start"], g["end"], g["size"], g["verdict"], g.get("undecodable", 0),
                        g.get("float_like", 0), g.get("ascii_frac", 0), flags))
        print("%-16s %8s %8s %5d  %s" % ("total gaps", "", "", sum(tot.values()), " ".join("%9d" % tot[c] for c in CLASSES)))
        print("%-16s %8s %8d %5s  %s" % ("total bytes", "", sum(tot_b.values()), "", " ".join("%9d" % tot_b[c] for c in CLASSES)))
    if args.strict and any(g["verdict"] == "code?" for r in res for g in r["ranges"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
