#!/usr/bin/env python3
"""make_spu_overlays.py -- lift MultiStream's DSP plugin banks where they run.

Ported from Drakengard 3's port, soyjxck/dod3-recomp 96df4c3 tools/make_spu_overlays.py
(MIT, (c) soyjxck): the `wrap` + `register` steps for the DSP block. Its `standin`
step (our flashMP3.pic) lives in src/overrides/audio_mp3.cpp, which writes the file and
registers the native decoder at run time, so it is not repeated here; nor is its lift
of Sony's firmware decoder (we ship no firmware).

The MultiStream mixer (01.09: SPU image `spu_e33837bb...`, fingerprint C1759183E2FF7448)
copies the text of the DSP plugins the game uses, packed back to back, into one heap
block and GETs the whole block into its plugin area at **LS 0x37000**, then calls into
it (0x37018 with lr 0x03930, ...). The plugins are small position-independent SPU ELFs
linked at va 0x80 (`mstream_dsp_*.pic`, embedded in the EBOOT and lifted on their own
by build_spu_workloads.py, where nothing ever runs them). Lifted code is only right at
the address it was lifted for, so the block is rebuilt here exactly as the mixer lays
it out, wrapped as an SPU ELF at 0x37000, lifted once, and registered as a signature
overlay region (spu_overlay_register_sig_region, patch T007-audio-pacing-devflash-
sig-region): the runtime recognises the GET by the block's first 16 bytes, because the
heap copy's address differs from run to run.

SARPBC streams 12 KiB banks into the SAME LS 0x37000 swap area. The first bank
(01.09 dump, 2026-10-19) contains i3dl2 reverb at +0 (0x27C0 bytes) and parametric
EQ at +0x2800 (0x690 bytes). When MP3 starts, the mixer also loads the next bank,
containing the filter plugin at +0 (0x500 bytes; traced 2026-10-20). Register each
bank with a distinct image id and content signature: the filter's 0x37010 entry
must not dispatch the stale reverb lift at that same address. No runtime change
is needed. Both versions use MultiStream SDK 420; the 01.02 bank layout remains
unverified at runtime. dod3's 2013 layout differs, so these tables are per title.

Usage (tools/relift.sh runs it after build_spu_workloads.py):
  make_spu_overlays.py --spu <SPU_DIR> [--output <dir>] [--ps3recomp <dir>]
  --output keeps extracted inputs read-only and writes banks in a build directory.

Writes <SPU_DIR>/{spu_ovl_msdsp_37000,spu_ovl_msfilter_37000}/ with image.elf,
spu_recomp.c, spu_recomp.h and lift.log. Each registration constructor is appended
to its spu_recomp.c, so CMake's glob builds both without other changes.
"""
import argparse
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

MSDSP_LSA = 0x37000
MSDSP_NAME = "spu_ovl_msdsp_37000"
# An image id no content-derived id from build_spu_workloads.py uses ("MSD" 1); the
# MP3 stand-in in src/overrides/audio_mp3.cpp uses 0x4D503301 ("MP3" 1).
MSDSP_IMAGE_ID = 0x4D534401
# (SPUNAME of the plugin, offset of its text in the block)
PLUGINS = [
    ("mstream_dsp_i3dl2.pic", 0x0000),
    ("mstream_dsp_para_eq.pic", 0x2800),
]
BANKS = [
    (MSDSP_NAME, MSDSP_IMAGE_ID, PLUGINS),
    ("spu_ovl_msfilter_37000", MSDSP_IMAGE_ID + 1, [("mstream_dsp_filter.pic", 0)]),
]

BI_R0, NOP, LNOP = 0x35000000, 0x4020007F, 0x00200000


def text_segment(elf):
    entry, phoff = struct.unpack(">II", elf[0x18:0x20])
    phn, = struct.unpack(">H", elf[0x2C:0x2E])
    for i in range(phn):
        o = phoff + i * 32
        p_type, off, va, _pa, fsz, _msz, flags, _al = struct.unpack(">8I", elf[o:o + 32])
        if p_type == 1 and flags & 1:
            return entry, va, elf[off:off + fsz]
    sys.exit("make_spu_overlays: no executable PT_LOAD")


def after_returns(code):
    """Offsets of the first real instruction after every `bi $r0`: functions laid
    out back to back, whose callers reach them only through tables."""
    words = struct.unpack(f">{len(code) // 4}I", code[:len(code) // 4 * 4])
    out = []
    for i, w in enumerate(words):
        if w != BI_R0:
            continue
        j = i + 1
        while j < len(words) and words[j] in (NOP, LNOP):
            j += 1
        if j < len(words) and words[j] != 0:
            out.append(j * 4)
    return out


def find_plugins(spu_dir):
    """SPUNAME -> image.elf bytes, over the images build_spu_workloads.py extracted
    (<SPU_DIR>/spu_<sha256>/image.elf). Found by name, so it follows the version."""
    found = {}
    for d in sorted(spu_dir.iterdir()):
        elf_path = d / "image.elf"
        if d.name in {name for name, _, _ in BANKS} or not elf_path.is_file():
            continue
        elf = elf_path.read_bytes()
        m = re.search(rb"mstream_dsp_[a-z0-9_]+\.pic", elf)
        if m:
            found[m.group(0).decode()] = elf
    return found


def build_msdsp(spu_dir, layout=PLUGINS):
    """-> (one bank at MSDSP_LSA, entry seeds, signature, span)."""
    plugins = find_plugins(spu_dir)
    block, entries = bytearray(), []
    for name, at in layout:
        if name not in plugins:
            sys.exit(f"make_spu_overlays: {name} not among the lifted SPU images in {spu_dir}")
        entry, va, code = text_segment(plugins[name])
        if len(block) > at:
            sys.exit(f"make_spu_overlays: {name} overlaps the previous plugin")
        block += bytes(at - len(block)) + code
        entries.append(MSDSP_LSA + at + (entry - va))
        # Every plugin opens with its 16-byte .SpuGUID, then the entry the host
        # calls through, at +0x10 (the mixer calls 0x37010 / 0x39810). Nothing
        # inside the module branches there, so the lifter only finds it as a seed.
        entries.append(MSDSP_LSA + at + 0x10)
        # The rest of a plugin's interface is a table of callbacks it hands the
        # mixer, computed position-independently (0x37C20, 0x39B50, ...), so no
        # branch in the image names them. Seed the first instruction after every return.
        entries += [MSDSP_LSA + at + o for o in after_returns(code)]
    return bytes(block), entries, bytes(block[:16]), len(block)


def debase_includes(path):
    """As build_spu_workloads.py: bare #include "spu_context.h", resolved by CMake."""
    txt = path.read_text(encoding="utf-8", errors="ignore")
    new = re.sub(r'#include\s+"(?:\.\./)+runtime/spu/([A-Za-z0-9_]+\.h)"', r'#include "\1"', txt)
    if new != txt:
        path.write_text(new, encoding="utf-8")


def lift_bank(spu_dir, tools, name, image_id, layout, output_dir=None):
    sys.path.insert(0, str(tools))
    from wrap_spu_elf import wrap as wrap_elf

    block, entries, sig, span = build_msdsp(spu_dir, layout)
    out = (output_dir or spu_dir) / name
    out.mkdir(parents=True, exist_ok=True)
    elf = out / "image.elf"
    elf.write_bytes(wrap_elf(block, base=MSDSP_LSA, entry=entries[0]))

    prefix = name + "_"
    extra = ",".join(f"0x{e:X}" for e in sorted(set(entries[1:])))
    cmd = [sys.executable, str(tools / "spu_lifter.py"), "--auto-functions", str(elf),
           "--symbol-prefix", prefix, "--extra-funcs", extra, "-o", str(out)]
    with open(out / "lift.log", "w") as log:
        if subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode != 0:
            sys.exit(f"make_spu_overlays: lift failed, see {out / 'lift.log'}")
    src = out / "spu_recomp.c"
    debase_includes(out / "spu_recomp.h")
    debase_includes(src)

    sig_c = ", ".join(f"0x{b:02X}" for b in sig)
    with open(src, "a", encoding="utf-8") as f:
        f.write(f"""
/* ---- GENERATED by tools/make_spu_overlays.py ----------------------------------
 * MultiStream's DSP bank ({", ".join(f"{n} @ +0x{a:X}" for n, a in layout)}),
 * lifted at LS 0x{MSDSP_LSA:X} and registered under image id 0x{image_id:X}: the
 * runtime makes it a resident code span of the mixer's context when a GET of >= 512
 * bytes starts with these 16 bytes (the first plugin's .SpuGUID). */
extern void spu_begin_image(int image_id);
extern void spu_overlay_register_sig_region(const uint8_t sig[16], uint32_t span, int image_id);

__attribute__((constructor)) static void {prefix}overlay_register(void)
{{
    static const uint8_t sig[16] = {{ {sig_c} }};
    spu_begin_image(0x{image_id:X});
    {prefix}spu_recomp_register();
    spu_begin_image(0);
    spu_overlay_register_sig_region(sig, 0x{span:X}u, 0x{image_id:X});
}}
""")
    print(f"make_spu_overlays: {name}: {len(block):#x} bytes at LS 0x{MSDSP_LSA:X}, "
          f"{len(set(entries))} seeds, image id 0x{image_id:X} -> {src}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    root = Path(__file__).resolve().parent.parent
    ap.add_argument("--spu", required=True, type=Path, help="SPU_DIR (src/spu_gen of the version)")
    ap.add_argument("--output", type=Path, help="Write banks here instead of modifying SPU_DIR")
    ap.add_argument("--ps3recomp", type=Path,
                    default=Path(os.environ.get("PS3RECOMP") or root / "external/ps3recomp"))
    args = ap.parse_args()
    for name, image_id, layout in BANKS:
        lift_bank(args.spu, args.ps3recomp / "tools", name, image_id, layout, args.output)


if __name__ == "__main__":
    main()
