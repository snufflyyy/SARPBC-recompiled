#!/usr/bin/env python3
"""Lift the SPURS job binaries a data-only PRX hands out from module_start.

SARPBC's SPUJOBS.SPRX (both 01.02 and 01.09) is a PPU PRX with no code of its
own beyond a 12-instruction module_start. That function copies four words from
its TOC into the caller's argp buffer:

    argp[0] = EA of job binary A   argp[1] = size of A   (Edge Geometry)
    argp[2] = EA of job binary B   argp[3] = size of B   (0x108 bytes)

and the game later hands those EAs to cellSpursJobChain as eaBinary. The
runtime (ps3recomp's sys_prx_load_module, patch T002) loads the same module at
run time and evaluates the same function; this script does it offline so the
job binaries can be lifted and registered by content fingerprint.

Nothing here is specific to one module version: the binaries are found by
relocating the PRX, evaluating module_start with the same leaf-only evaluator
the runtime uses, and reading (pointer, size) pairs out of argp. --blob OFF:SIZE
adds or overrides a binary by image offset when a module uses another protocol.

Each binary is wrapped as a minimal SPU ELF at LS 0 (job binaries are
position-independent and the job runner stages them at LS 0, see
runtime/spu/spurs_job.c), lifted with spu_lifter.py under a unique symbol
prefix, and registered with spu_workload_register_img under the FNV-1a-64 of
its bytes. A job header gives the binary size in 16-byte units, so the
16-byte-rounded size is registered as well when it differs.

Output (all generated; derived from game code, never commit it):
    <lifted>/spu_prxjob_<sha256>/spu_recomp.{c,h}   one dir per binary
    <register>                                    registration TU with a constructor

Usage (CMake compiles <SPU_DIR>/*/spu_recomp.c and <SPU_DIR>/jobmods_register.c):
    .venv/bin/python tools/lift_prx_jobs.py game/SPUJOBS.prx \\
        --lifted src/spu_gen --register src/spu_gen/jobmods_register.c
"""

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PS3RECOMP = os.environ.get("PS3RECOMP", os.path.join(ROOT, "external", "ps3recomp"))
TOOLS = os.path.join(PS3RECOMP, "tools")
sys.path.insert(0, TOOLS)

from lift_prx import Prx                                  # noqa: E402
from wrap_spu_elf import wrap                             # noqa: E402
from build_spu_workloads import fnv1a64, debase_includes  # noqa: E402

# Evaluate at a base that cannot be mistaken for a size, so pointers into the
# image are recognisable in argp.
EVAL_BASE = 0x10000000
NID_MODULE_START = 0xBC9A0086


def be32(b, o):
    return struct.unpack_from(">I", b, o)[0]


def be16(b, o):
    return struct.unpack_from(">H", b, o)[0]


def find_module_start(prx, img):
    """OPD address (EVAL_BASE-relative EA) of module_start, from the relocated
    module-level export table."""
    off0, va0, _, _ = prx.loads[0]
    mi = prx.modinfo_off - off0 + va0
    ent, ent_end = be32(img, mi + 0x24) - EVAL_BASE, be32(img, mi + 0x28) - EVAL_BASE
    while 0 <= ent < ent_end:
        size = img[ent]
        if size < 0x1C:
            break
        nfunc = be16(img, ent + 6)
        lib, nids, addrs = (be32(img, ent + o) for o in (0x10, 0x14, 0x18))
        if lib == 0:
            for k in range(nfunc):
                if be32(img, nids - EVAL_BASE + 4 * k) == NID_MODULE_START:
                    return be32(img, addrs - EVAL_BASE + 4 * k)
        ent += size
    return 0


def eval_leaf(img, code, toc, a0, a1, mem):
    """Mirror of prx_runtime_eval_leaf (runtime/prx/prx_runtime.c): loads,
    stores, immediates, mr; ends at blr. `mem` collects stores (EA -> u32)."""
    def rd32(ea):
        if ea in mem:
            return mem[ea]
        return be32(img, ea - EVAL_BASE)

    r = [0] * 32
    r[2], r[3], r[4] = toc, a0, a1
    pc = code
    for _ in range(64):
        w = rd32(pc)
        if w == 0x4E800020:
            return r[3]
        op, rt, ra, rb = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
        si = struct.unpack(">h", struct.pack(">H", w & 0xFFFF))[0]
        ui = w & 0xFFFF
        ea = (r[ra] + si) & 0xFFFFFFFF
        if op == 14:
            r[rt] = ((r[ra] if ra else 0) + si) & 0xFFFFFFFFFFFFFFFF
        elif op == 15:
            r[rt] = ((r[ra] if ra else 0) + (si << 16)) & 0xFFFFFFFFFFFFFFFF
        elif op == 24:
            r[ra] = r[rt] | ui
        elif op == 25:
            r[ra] = r[rt] | (ui << 16)
        elif op == 32 and ra not in (0, 1):
            r[rt] = rd32(ea)
        elif op == 36 and ra not in (0, 1):
            mem[ea] = r[rt] & 0xFFFFFFFF
        elif op == 31 and ((w >> 1) & 0x3FF) == 444 and not w & 1:
            r[ra] = r[rt] | r[rb]
        else:
            raise SystemExit(f"module_start at 0x{code - EVAL_BASE:X}: unsupported "
                             f"instruction 0x{w:08X} at +0x{pc - code:X}; use --blob")
        pc += 4
    raise SystemExit("module_start: no blr within 64 instructions; use --blob")


def job_blobs(prx_path):
    prx = Prx(prx_path)
    img, _ = prx.build_image(EVAL_BASE)
    opd = find_module_start(prx, img)
    if not opd:
        raise SystemExit(f"{prx_path}: no module_start export; use --blob")
    code, toc = be32(img, opd - EVAL_BASE), be32(img, opd - EVAL_BASE + 4)
    argp = 0xF0000000          # outside the image: stores land only in `mem`
    mem = {}
    eval_leaf(img, code, toc, 4, argp, mem)
    words = [mem.get(argp + 4 * i, 0) for i in range(16)]
    blobs = []
    for i in range(len(words) - 1):
        p, s = words[i], words[i + 1]
        if EVAL_BASE <= p < EVAL_BASE + len(img) and 0 < s <= EVAL_BASE + len(img) - p:
            blobs.append((p - EVAL_BASE, s))
    return img, blobs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prx", help="decrypted PRX (e.g. game/SPUJOBS.prx)")
    ap.add_argument("--lifted", required=True, help="dir for spu_prxjob_<sha>/ lift dirs")
    ap.add_argument("--register", required=True, help="registration C file to write")
    ap.add_argument("--blob", action="append", default=[], metavar="OFF:SIZE",
                    help="job binary at image offset OFF (hex ok), SIZE bytes; repeatable")
    ap.add_argument("--register-fn", default="sarpbc_prx_jobs_register")
    ap.add_argument("--manifest", help="also write a JSON manifest here")
    args = ap.parse_args()

    img, blobs = job_blobs(args.prx)
    for spec in args.blob:
        off, size = (int(x, 0) for x in spec.split(":"))
        blobs.append((off, size))
    if not blobs:
        raise SystemExit("no job binaries found")

    lifter = os.path.join(TOOLS, "spu_lifter.py")
    entries = []
    for off, size in blobs:
        raw = bytes(img[off:off + size])
        sha = hashlib.sha256(raw).hexdigest()
        name = f"spu_prxjob_{sha[:16]}"
        prefix = name + "_"
        outdir = os.path.join(args.lifted, name)
        os.makedirs(outdir, exist_ok=True)
        elf = os.path.join(outdir, "image.elf")
        with open(elf, "wb") as f:
            f.write(wrap(raw, base=0, entry=0))
        cmd = [sys.executable, lifter, "--auto-functions", elf,
               "--symbol-prefix", prefix, "-o", outdir,
               "--report", os.path.join(outdir, "report.json")]
        print(f"[lift_prx_jobs] LIFT image+0x{off:X} size 0x{size:X} -> {outdir}")
        if subprocess.run(cmd).returncode != 0:
            raise SystemExit(f"lift failed for image+0x{off:X}")
        for fn in ("spu_recomp.h", "spu_recomp.c"):
            debase_includes(os.path.join(outdir, fn))
        hdr = open(os.path.join(outdir, "spu_recomp.h"), encoding="utf-8", errors="ignore").read()
        if f"{prefix}spu_func_00000000(" not in hdr:
            raise SystemExit(f"{name}: no function at LS 0 in the lift")
        fps = {fnv1a64(raw): size}
        r16 = (size + 15) & ~15
        if r16 != size:
            fps[fnv1a64(bytes(img[off:off + r16]).ljust(r16, b"\0"))] = r16
        image_id = 0x40000000 | (int(sha[:8], 16) & 0x3FFFFFFF)
        entries.append(dict(name=name, prefix=prefix, offset=off, size=size,
                            sha256=sha, image_id=image_id,
                            fingerprints={f"0x{k:016X}": v for k, v in fps.items()}))

    L = [f"/* {os.path.basename(args.register)} -- GENERATED by tools/lift_prx_jobs.py from",
         f" * {os.path.basename(args.prx)}. Registers the SPURS job binaries that the module's",
         " * module_start hands to the title, by FNV-1a-64 of the bytes the job header",
         " * names (exact and 16-byte-rounded size). Derived from game code: never commit. */",
         '#include "spu_workload.h"', "",
         "extern void spu_begin_image(int image_id);", ""]
    for e in entries:
        L.append(f"extern void {e['prefix']}spu_func_00000000(spu_context*);")
        L.append(f"extern void {e['prefix']}spu_recomp_register(void);")
    L += ["", f"void {args.register_fn}(void)", "{"]
    for e in entries:
        L.append(f"    /* image+0x{e['offset']:X}, 0x{e['size']:X} bytes, sha256 {e['sha256'][:16]}... */")
        L.append(f"    spu_begin_image({e['image_id']}); {e['prefix']}spu_recomp_register();")
        for fp, sz in e["fingerprints"].items():
            L.append(f"    spu_workload_register_img({fp}ULL, {e['prefix']}spu_func_00000000, "
                     f"{e['image_id']}, \"{e['name']}/{sz:#x}\");")
    L += ["    spu_begin_image(0);", "}", "",
          f"__attribute__((constructor)) static void {args.register_fn}_ctor(void)",
          "{", f"    {args.register_fn}();", "}", ""]
    os.makedirs(os.path.dirname(os.path.abspath(args.register)), exist_ok=True)
    with open(args.register, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))
    if args.manifest:
        with open(args.manifest, "w") as f:
            json.dump(entries, f, indent=2)
    for e in entries:
        print(f"[lift_prx_jobs] {e['name']}: image+0x{e['offset']:X} size 0x{e['size']:X} "
              f"fp {', '.join(e['fingerprints'])}")
    print(f"[lift_prx_jobs] wrote {args.register} ({len(entries)} job binaries)")


if __name__ == "__main__":
    main()
