# Pipeline — from PKG to native executable

Each stage, its inputs/outputs, and the gotchas specific to this title. Scripts named
`tools/*.sh` are ours (planned; create them from the commands here). Paths starting with
`$PS3RECOMP` are in the pinned ps3recomp checkout (`external/ps3recomp` by default).

```
.pkg ─(1)─► vfs/dev_hdd0/game/NPUB30035/...  (plain data + still-encrypted SELFs)
.rap ─(2)─► game/EBOOT.elf, game/SPUJOBS.prx  (decrypted)
     ─(3)─► analysis/*.json                   (functions, imports, image, loader)
     ─(4)─► src/recomp/*.cpp (incl. ppu_hle_nids.cpp)
     ─(5)─► src/spu_gen/**, src/spu_workloads.c
     ─(6)─► build/sarpbc
```

## 1. Extract the PKG

`tools/extract.sh` does this (creates `.venv` if needed). By hand:

```bash
python -m venv .venv && .venv/bin/pip install -r $PS3RECOMP/requirements.txt  # pycryptodome!
.venv/bin/python $PS3RECOMP/tools/pkg_extract.py "<pkg>" vfs/dev_hdd0/game/NPUB30035
.venv/bin/python $PS3RECOMP/tools/pkg_extract.py "<pkg>" /tmp/x --list    # table only, instant
.venv/bin/python $PS3RECOMP/tools/pkg_extract.py "<pkg>" out --only EBOOT.BIN
```

- Without pycryptodome it falls back to pure-Python AES: fine for one small file, very
  slow for all 186 MB. Install it.
- `--only` matches the **basename**, not the path (`--only SPLASH.BMP` hits two files).
- The PKG layer needs no RAP. Output keeps the package tree: `PARAM.SFO`, `USRDIR/...`,
  `TROPDIR/...` — exactly the layout of an installed HDD game.
- File names come out **upper-case** (`USRDIR/SARB/TAGAME/COOKEDPS3/...`). That is how
  they sit on a real PS3 install too; see [subsystems.md](subsystems.md#file-system) for
  the case question.

## 2. Decrypt the NPDRM SELFs

`EBOOT.BIN` and `SPUJOBS.SPRX` are NPDRM SELFs (`NPD\0`, license type 2 = local), so
decryption needs the klicensee derived from the `.rap`. **ps3recomp cannot do this**
(`unfself.py` only handles unencrypted debug fSELFs).

**`tools/decrypt.sh`** does it headlessly with RPCS3's CLI:
- downloads the latest `RPCS3/rpcs3-binaries-linux` AppImage into `tools/rpcs3/` on first
  use (git-ignored) and extracts it (`--appimage-extract`, no FUSE needed);
- runs it with `XDG_CONFIG_HOME=tools/rpcs3/config`, so `~/.config/rpcs3` is never
  touched, and `QT_QPA_PLATFORM=offscreen`;
- copies the `.rap` to `config/rpcs3/dev_hdd0/home/00000001/exdata/`, where
  `--decrypt` looks it up by content ID (no firmware needed);
- calls `--decrypt <file>` **once per file**: given several paths it silently does only
  the first;
- writes `game/EBOOT.elf` and `game/SPUJOBS.prx`.

Last verified 2026-10-18 with RPCS3 v0.0.43-20336-bd179ffd. Expected hashes are in
[game-profile.md](game-profile.md) ("Decrypted executable").
Klicensees and keys are never written to the repo.

Sanity check: `file game/EBOOT.elf` says ELF 64-bit MSB PowerPC (Cell LV2), and
`python $PS3RECOMP/tools/triage_elf.py game/EBOOT.elf` prints imports and SPU/NP flags.

## 3. Load / analyse

```bash
python $PS3RECOMP/tools/ppu_loader.py game/EBOOT.elf -o analysis/
python $PS3RECOMP/tools/gen_imports.py game/EBOOT.elf -o analysis/imports_named.json
python $PS3RECOMP/tools/extract_spu_images.py game/EBOOT.elf --output analysis/spu_embedded/
```

`ppu_loader.py` writes `EBOOT.functions.json` (OPD-derived `[{start,end,toc,opd}]`),
`EBOOT.imports.json` (`[{library,nid,stub}]`), `EBOOT.image.json` (PT_LOAD manifest),
`EBOOT.loader.json` (entry, TOC). For our EBOOT it reports 47,602 unique functions and
274 imports; anything far off means the ELF is wrong.

Gotcha: run ps3recomp tools **without** `python -I` — they import sibling modules
(`spu_elf`, ...) from their own directory.

OPD only lists address-taken functions. If static-only functions are missed, run
`find_functions.py game/EBOOT.elf --seed-json analysis/EBOOT.functions.json --output ...`
and, if it invents functions from `.rodata`, bound it with the lifter's `--code-end`
(end of the last executable section — read it from the section headers).

## 4. Lift the PPU code

```bash
python $PS3RECOMP/tools/ppu_lifter.py game/EBOOT.elf \
    --functions analysis/EBOOT.functions.json \
    --hle-stubs analysis/EBOOT.imports.json \
    --chunks 64 --jobs $(nproc) \
    --output src/recomp/
python $PS3RECOMP/tools/gen_hle_nids.py --all --out src/recomp/ppu_hle_nids.cpp   # CMake uses it when present
```

- **Split the linker's TOC-switch stubs first** (`tools/split_toc_stubs.py`, run by
  `relift.sh`; the lifter is fed `EBOOT.functions.split.json`). The EBOOT uses four TOCs, so
  the linker emits 4,242 `std r2,40(r1); addis/addi r2; b` stubs in two runs
  (`0x61B6A8..0x61CA98`, `0x1921350..0x1930880`). ppu_loader folds each run into the
  preceding function, and the lifter then emits every stub as a tail-entry wrapper
  running to the end of the run. That took the lift from 7.6M lines to 27.2M (two thirds
  dead code), with ~170 of the 256 chunks holding nothing else. Upstream candidate.
- `--hle-stubs` is mandatory; without it, or without `ppu_hle_nids.cpp` compiled in, the
  first import call fails with `unresolved indirect call -> 0x39800000`.
- `--chunks N` splits output by guest address and rewrites only changed files —
  important for a 30 MB EBOOT so incremental builds stay cheap.
- Other flags: `--code-end`, `--names` (symbol names, e.g. from Ghidra), `--toc`,
  `--symbol-prefix`, `--raw --base` (raw images/PRXs), `--single-file`.
- Re-run CMake configure after a fresh lift (the template globs `src/recomp/*.cpp`).

## 5. SPU code

For this title: 15 SPU ELFs embedded in the EBOOT (Edge zlib, PhysX, MultiStream DSP,
...) and Edge Geometry job images inside `SPUJOBS.prx` (a PPU PRX, no SPU ELFs) — see
[game-profile.md](game-profile.md#spu-code). After a relift, `tools/spu_coverage.py` audits the bytes no lifted function covers (T010). The general sources:

| Source | How to get it | How to lift |
|---|---|---|
| SPU ELFs embedded in the EBOOT | `extract_spu_images.py` (step 3) | `build_spu_workloads.py --input` |
| `SPUJOBS.SPRX` | decrypted in step 2; inspect: PPU PRX (`lift_prx.py`) or SPU images inside (`extract_spu_images.py`) | as above |
| Raw job binaries built in memory | run with `SPU_DUMP_MISS=spu_dump`, one file per fingerprint | `find_spu_functions.py --raw --base 0` + `spu_lifter.py --symbol-prefix` |

Lifted SPU images are registered by content fingerprint (see `simpsonsarcade-ps3/src/spu_workloads.c` in
simpsonsarcade-ps3 for the pattern). Until an image is lifted, a PPU-side fallback or the
SPU interpreter can stand in (`SPU_FALLBACK.md` upstream).

## 6. Build and run

See [build-linux.md](build-linux.md). The short way, from the repo root:

```bash
./build.sh [--version 0102] [--clean]   # default 01.09 -> versions/0109/build (build-0109/ in a worktree)
./run.sh   [--version 0102] [--build] [-- game args]
```

`build.sh` re-applies `patches/ps3recomp/` only when the patches or the pin changed, or the
submodule was moved off the commit it last patched. It keeps a stamp (`<hash of pin+patches>
<HEAD>`) in the submodule's git dir. Re-applying rewrites the runtime headers, and every lifted
file includes them, so an unneeded re-apply costs a full recompile (~1 min of ccache hits, more on
a cold cache). It never runs `git submodule update` on an existing checkout: that detaches the
submodule at the bare pin, and the next build fails to link against the unpatched runtime (seen
2026-10-19). `run.sh` picks the build, game and vfs dirs for the version and calls:

```bash
tools/run.sh      # = build/sarpbc game/EBOOT.elf vfs, with Vulkan window + guest shaders
```

`build/sarpbc <EBOOT.elf> [vfs root]`. The game is an HDD title, so `setup_vfs()` in
`src/main.cpp` points the runtime's three path translators at
`<vfs>/dev_hdd0/game/NPUB30035/` by defaulting `PS3_VFS_ROOT`, `PS3_HDD0_ROOT`,
`PS3_USRDIR_BASE`, and sets the guest's argv[0] (`PS3_BOOT_PATH`) to
`/dev_hdd0/game/NPUB30035/USRDIR/EBOOT.BIN`. Any of them set in the environment wins.

### What `tools/relift.sh` does for SPU

`build_spu_workloads.py --input game/EBOOT.elf --lifted src/spu_gen --out
src/spu_gen/spu_workloads.c --constructor --allow-partial` finds the embedded SPU ELFs,
lifts each into `src/spu_gen/spu_<sha256>/`, and writes a registry keyed by content
fingerprint. `--allow-partial` is needed: strict mode refuses all 14 because a few
executable bytes fall outside any detected function (padding), even though nothing is
unsupported. `src/spu_gen/inventory.json` lists each image's status and reason. CMake picks
the images up from `src/spu_gen/*/spu_recomp.c` (reconfigure after a relift).

Then `tools/make_spu_overlays.py --spu src/spu_gen --ps3recomp external/ps3recomp` (T007)
rebuilds two MultiStream DSP banks at the same LS 0x37000: i3dl2 + parametric EQ
(0x2E90 bytes) and the filter (0x500 bytes). It writes `spu_ovl_msdsp_37000/` and
`spu_ovl_msfilter_37000/` under the output directory, with separate image ids and
content signatures (patch 0023's `spu_overlay_register_sig_region`). The filter
bank is loaded when MP3 streams start; omitting it kills the mixer at LS 0x37010.
The step must follow `build_spu_workloads.py`, which deletes `src/spu_gen`.

For older shared lifts that have only the first bank, CMake generates both in
its own build directory (`spu_audio/`) and excludes the old first-bank source
from that target. The normal build therefore needs no shared relift. It uses
`.venv/bin/python` (or `.venv/Scripts/python.exe`), with the configured Python as
fallback. Input ELFs and relevant SPU tools are build dependencies. The manual
read-only equivalent is `tools/make_spu_overlays.py --spu <SPU_DIR> --output <BUILD_DIR>/spu_audio`.
The two generated constructors must be linked together; never register both
banks under one image id.

## Regenerating (`tools/relift.sh`)

One idempotent script runs steps 3–5 so any agent can rebuild generated code after a
ps3recomp bump or a lifter fix. Generated directories are deleted and recreated; never
hand-edit them. After a ps3recomp pin change: re-apply `patches/ps3recomp/`, relift,
rebuild, and note the result in [status.md](status.md). Patches are applied with
`tools/apply_patches.sh`.
