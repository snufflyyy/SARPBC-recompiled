# Pipeline — from PKG to native executable

Each stage, its inputs/outputs, and the gotchas specific to this title. Scripts named
`tools/*.sh` are ours (planned; create them from the commands here). Paths starting with
`$PS3RECOMP` are in the pinned ps3recomp checkout (`external/ps3recomp` by default).

```
.pkg ─(1)─► vfs/dev_hdd0/game/NPUB30035/...  (plain data + still-encrypted SELFs)
.rap ─(2)─► game/EBOOT.elf, game/SPUJOBS.prx  (decrypted)
     ─(3)─► analysis/*.json                   (functions, imports, image, loader)
     ─(4)─► src/recomp/*.cpp, src/gen/ppu_hle_nids.cpp
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
python $PS3RECOMP/tools/gen_hle_nids.py --all --out src/gen/ppu_hle_nids.cpp
```

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
[game-profile.md](game-profile.md#spu-code). The general sources:

| Source | How to get it | How to lift |
|---|---|---|
| SPU ELFs embedded in the EBOOT | `extract_spu_images.py` (step 3) | `build_spu_workloads.py --input` |
| `SPUJOBS.SPRX` | decrypted in step 2; inspect: PPU PRX (`lift_prx.py`) or SPU images inside (`extract_spu_images.py`) | as above |
| Raw job binaries built in memory | run with `SPU_DUMP_MISS=spu_dump`, one file per fingerprint | `find_spu_functions.py --raw --base 0` + `spu_lifter.py --symbol-prefix` |

Lifted SPU images are registered by content fingerprint (see `src/spu_workloads.c` in
simpsonsarcade-ps3 for the pattern). Until an image is lifted, a PPU-side fallback or the
SPU interpreter can stand in (`SPU_FALLBACK.md` upstream).

## 6. Build and run

See [build-linux.md](build-linux.md). Run:

```bash
PS3_HDD0_ROOT=$PWD/vfs/dev_hdd0 PS3RECOMP_VK_WINDOW=1 PS3RECOMP_VK_GUEST_PROGRAMS=1 \
    ./build/sarpbc game/EBOOT.elf
```

The executable takes the ELF and an optional VFS root. The game is an HDD title, so its
data must resolve under `/dev_hdd0/game/NPUB30035/` — `PS3_HDD0_ROOT` names the host
directory that contains `game/`. Confirm the boot path the runtime reports matches.

## Regenerating (`tools/relift.sh`)

One idempotent script runs steps 3–5 so any agent can rebuild generated code after a
ps3recomp bump or a lifter fix. Generated directories are deleted and recreated; never
hand-edit them. After a ps3recomp pin change: re-apply `patches/ps3recomp/`, relift,
rebuild, and note the result in [status.md](status.md).
