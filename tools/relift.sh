#!/usr/bin/env bash
# Regenerate everything git-ignored that is derived from the EBOOT: the loader
# analysis, the lifted PPU tree, the HLE NID table and the SPU images. Idempotent;
# run after a ps3recomp bump, a patch to the lifter, or a new decrypt.
#
#   tools/relift.sh            # JOBS=<n> CHUNKS=<n> to override the defaults below
#   GAME_DIR=versions/0109/game OUT_DIR=versions/0109 tools/relift.sh   # another version
#
# Inputs: $GAME_DIR/EBOOT.elf (default game/). Outputs under $OUT_DIR (default the repo
# root): analysis/, src/recomp/, src/spu_gen/.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PS3RECOMP=${PS3RECOMP:-$ROOT/external/ps3recomp}
PY=$ROOT/.venv/bin/python
GAME_DIR=$(realpath -m "${GAME_DIR:-$ROOT/game}")
OUT_DIR=$(realpath -m "${OUT_DIR:-$ROOT}")
ELF=$GAME_DIR/EBOOT.elf
ANALYSIS=$OUT_DIR/analysis
RECOMP=$OUT_DIR/src/recomp
SPU=$OUT_DIR/src/spu_gen

# Cut the lift by guest address into this many files. A relift that changes one
# function rewrites one file, and each TU stays small enough to compile in
# reasonable memory with -j$(nproc).
CHUNKS=${CHUNKS:-256}
# Lifter worker processes; each holds a large share of the image in memory.
JOBS=${JOBS:-8}

[ -f "$ELF" ] || { echo "no $ELF -- run tools/extract.sh and tools/decrypt.sh first"; exit 1; }

# End of the last executable section (.lib.stub in both 01.02 and 01.09). The R-X
# segment carries .rodata past it, which the branch-target pass would otherwise
# promote into thousands of bogus functions. Read it from the section headers so it
# follows the EBOOT version (01.02: 0x194FD80).
CODE_END=$(readelf -S -W "$ELF" | awk '$0 ~ /\] / && $(NF-3) ~ /X/ {
    a = strtonum("0x" $(NF-7)); s = strtonum("0x" $(NF-5)); if (a + s > e) e = a + s }
    END { printf "0x%X", e }')
echo "code end: $CODE_END"

mkdir -p "$ANALYSIS"
"$PY" "$PS3RECOMP/tools/ppu_loader.py" "$ELF" -o "$ANALYSIS/"
"$PY" "$PS3RECOMP/tools/gen_imports.py" "$ELF" -o "$ANALYSIS/imports_named.json"
# One function per linker TOC-switch stub; otherwise each stub lifts as a wrapper
# running to the end of the run (see the script's docstring).
"$PY" "$ROOT/tools/split_toc_stubs.py" "$ELF" "$ANALYSIS/EBOOT.functions.json" \
    -o "$ANALYSIS/EBOOT.functions.split.json"

# --hle-stubs rewrites each import trampoline as ps3_hle_call(nid); without it
# the first firmware call runs the raw stub and dies at 0x39800000.
rm -rf "$RECOMP"
mkdir -p "$RECOMP"
"$PY" "$PS3RECOMP/tools/ppu_lifter.py" "$ELF" \
    --functions "$ANALYSIS/EBOOT.functions.split.json" \
    --hle-stubs "$ANALYSIS/EBOOT.imports.json" \
    --code-end "$CODE_END" \
    --chunks "$CHUNKS" --jobs "$JOBS" \
    --output "$RECOMP/"

# No ppu_hle_nids.cpp here on purpose: without one in RECOMP_DIR, CMake generates the
# NID -> handler table inside each build dir from THAT build's ps3recomp checkout. The lift
# is shared read-only between worktrees whose patched toolkits differ, and a table naming
# handlers a worktree's runtime lacks fails to link there.
rm -f "$RECOMP/ppu_hle_nids.cpp"

# ---- SPU -------------------------------------------------------------------
# The SPU ELFs embedded in the EBOOT (Edge zlib, PhysX, MultiStream DSP, ...),
# lifted and registered by content fingerprint; cellSpurs dispatches to them.
# --allow-partial: every image lifts with no unsupported instructions but has a
# few executable bytes outside any detected function (padding / literal pools),
# which the strict mode refuses to register. The SPU interpreter covers a miss.
# Images with overlapping PT_LOADs (PhysX, 01.02 image 7) are skipped for now (T003).
rm -rf "$SPU"
"$PY" "$PS3RECOMP/tools/build_spu_workloads.py" --input "$ELF" \
    --lifted "$SPU" --out "$SPU/spu_workloads.c" \
    --constructor --allow-partial

echo "lifted -> $RECOMP ($(ls "$RECOMP" | wc -l) files, $(du -sh "$RECOMP" | cut -f1))"
