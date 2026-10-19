#!/usr/bin/env bash
# Regenerate everything git-ignored that is derived from the EBOOT: the loader
# analysis, the lifted PPU tree and the HLE NID table. Idempotent; run after a
# ps3recomp bump, a patch to the lifter, or a new decrypt.
#
#   tools/relift.sh            # JOBS=<n> CHUNKS=<n> to override the defaults below
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PS3RECOMP=${PS3RECOMP:-$ROOT/external/ps3recomp}
PY=$ROOT/.venv/bin/python
ELF=$ROOT/game/EBOOT.elf

# End of the last executable section (.lib.stub, 0x194DB40 + 0x2240). The R-X
# segment carries .rodata past it, which the branch-target pass would otherwise
# promote into thousands of bogus functions.
CODE_END=0x194FD80
# Cut the lift by guest address into this many files. A relift that changes one
# function rewrites one file, and each TU stays small enough to compile in
# reasonable memory with -j$(nproc).
CHUNKS=${CHUNKS:-256}
# Lifter worker processes; each holds a large share of the image in memory.
JOBS=${JOBS:-8}

[ -f "$ELF" ] || { echo "no $ELF -- run tools/extract.sh and tools/decrypt.sh first"; exit 1; }

mkdir -p "$ROOT/analysis"
"$PY" "$PS3RECOMP/tools/ppu_loader.py" "$ELF" -o "$ROOT/analysis/"
"$PY" "$PS3RECOMP/tools/gen_imports.py" "$ELF" -o "$ROOT/analysis/imports_named.json"
# One function per linker TOC-switch stub; otherwise each stub lifts as a wrapper
# running to the end of the run (see the script's docstring).
"$PY" "$ROOT/tools/split_toc_stubs.py" "$ELF" "$ROOT/analysis/EBOOT.functions.json" \
    -o "$ROOT/analysis/EBOOT.functions.split.json"

# --hle-stubs rewrites each import trampoline as ps3_hle_call(nid); without it
# the first firmware call runs the raw stub and dies at 0x39800000.
rm -rf "$ROOT/src/recomp"
mkdir -p "$ROOT/src/recomp"
"$PY" "$PS3RECOMP/tools/ppu_lifter.py" "$ELF" \
    --functions "$ROOT/analysis/EBOOT.functions.split.json" \
    --hle-stubs "$ROOT/analysis/EBOOT.imports.json" \
    --code-end "$CODE_END" \
    --chunks "$CHUNKS" --jobs "$JOBS" \
    --output "$ROOT/src/recomp/"

"$PY" "$PS3RECOMP/tools/gen_hle_nids.py" --all --out "$ROOT/src/recomp/ppu_hle_nids.cpp"

# ---- SPU -------------------------------------------------------------------
# The 15 SPU ELFs embedded in the EBOOT (Edge zlib, PhysX, MultiStream DSP, ...),
# lifted and registered by content fingerprint; cellSpurs dispatches to them.
# --allow-partial: every image lifts with no unsupported instructions but has a
# few executable bytes outside any detected function (padding / literal pools),
# which the strict mode refuses to register. The SPU interpreter covers a miss.
# The 324 KB PhysX image has overlapping PT_LOADs and is skipped for now.
rm -rf "$ROOT/src/spu_gen"
"$PY" "$PS3RECOMP/tools/build_spu_workloads.py" --input "$ELF" \
    --lifted "$ROOT/src/spu_gen" --out "$ROOT/src/spu_gen/spu_workloads.c" \
    --constructor --allow-partial

echo "lifted -> $ROOT/src/recomp ($(ls "$ROOT/src/recomp" | wc -l) files, $(du -sh "$ROOT/src/recomp" | cut -f1))"
