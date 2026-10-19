# Status

Living document. Update the phase table, "Next steps" and the log at the end of each
work session. Newest log entry first. Use absolute dates.

## Phases

| # | Phase | State |
|---|---|---|
| 0 | Docs, git, submodule, `.gitignore` | done 2026-10-18 |
| 1 | Extract PKG to `vfs/` (`tools/extract.sh`) | done 2026-10-18 |
| 2 | Decrypt EBOOT.BIN + SPUJOBS.SPRX (`tools/decrypt.sh`) | done 2026-10-18 |
| 3 | Load + triage ELF, record imports/SPU/NP facts | done 2026-10-18 (see game-profile.md) |
| 4 | Project skeleton from the template, first lift + build on Linux | skeleton + lift done 2026-10-18; build waiting on system packages |
| 5 | Boot to first file opens / first HLE gaps | — |
| 6 | Loading screen draws (`LOADSCREEN` FPO/VPO) | — |
| 7 | Intro movies / main menu | — |
| 8 | Offline match in an arena, with input and audio | — |
| 9 | Polish: saves, trophies, perf, split-screen; online later | — |

## Decisions

- **2026-10-18 — toolkit: middle path.** Pin upstream `sp00nznet/ps3recomp`; port features
  from the Drakengard 3 fork (`soyjxck/ps3recomp`) as patches when needed. See
  `patches/ps3recomp/README.md`.
- **2026-10-18 — decryption via RPCS3 CLI**, isolated config, scripted in `tools/decrypt.sh`.
- **2026-10-18 — platforms: Linux primary with Vulkan; Windows later with D3D12.** CMake
  turns `PS3RECOMP_RSX_VULKAN` on for Linux; `src/main.cpp` selects Vulkan → D3D12 →
  Metal → null. Linux-only conveniences need a Windows branch.

## Next steps

1. User installs build deps: `sudo dnf install SDL2-devel vulkan-headers glslang-devel`.
2. Build the runtime alone first (`ps3recomp_host --draw` with Vulkan), then
   `cmake -S . -B build -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++`
   and `cmake --build build`. Watch RAM (256 TUs of ~100k lines) and disk (~20 GB free).
3. First run with `PS3_FSLOG=1 tools/run.sh`; record what breaks.
4. Lift the 15 embedded SPU ELFs (`build_spu_workloads.py --input`); work out how to get
   the Edge Geometry job images out of `SPUJOBS.prx`.

## Open questions

- What are SPU images 0, 3–5, 8–10 (unidentified by strings)?
- Does MultiStream need the firmware MP3 decoder like Drakengard 3 did?
- Does the game block on `sceNpDrmIsAvailable` or NP sign-in when offline?
- How are saves written (no cellSaveData import — raw sys_fs?)
- Does the upstream POSIX boot scaffold get a UE3-sized title to `main` on Linux?

## Log

### 2026-10-18 (session 3)
- Copied ps3recomp `templates/project` (@ `838800e`) to `CMakeLists.txt`, `src/main.cpp`,
  `src/stubs.cpp`, `config.toml`. Changes: project `sarpbc`, Release default,
  `PS3RECOMP_RSX_VULKAN` on for Linux, paths for `external/ps3recomp`, `src/recomp`,
  `src/spu_gen`; `main.cpp` picks Vulkan on Linux and `setup_vfs()` maps the HDD title.
- `tools/relift.sh` + `tools/run.sh` written. First lift: 2 min 50 s, 60,152 functions
  lifted (OPD 47,602 + 12,275 split by prologue scan) + 4,245 mid-function tail-entry
  wrappers = 64,397 emitted; 351 jump tables (3,080 cases); 274 import stubs →
  `ps3_hle_call`; NID table 1,195 handlers / 93 modules. Output 1.6 GB, 27.2M lines in
  256 chunks of ~100k lines. No unhandled instructions; 6,815 `/* TODO: .word */`
  (data words inside code ranges).
- Build blocked: SDL2, Vulkan headers and glslang dev packages are not installed.

### 2026-10-18 (session 2)
- `git init` (branch `main`), `.gitignore` excluding all game data and generated output,
  submodule `external/ps3recomp` at upstream `39a3629` (v0.15.0+2).
- Downloaded RPCS3 v0.0.43-20336-bd179ffd (AppImage sha256 `0e642edc…50f8e9`, matches
  release notes) into `tools/rpcs3/`. `--decrypt` decrypted both SELFs headlessly with the
  RAP in an isolated `dev_hdd0`. Found: one path per `--decrypt` call.
- `tools/extract.sh` and `tools/decrypt.sh` written and verified (reproducible hashes).
- Loader/triage: 47,602 functions, 274 imports / 20 libs, 15 embedded SPU ELFs (Edge zlib,
  PhysX, MultiStream DSP), SPUJOBS.prx = PPU PRX with Edge Geometry jobs, SPURS
  Queue/LFQueue in use (same as Drakengard 3).

### 2026-10-18 (session 1)
- Created `AGENTS.md`, `CLAUDE.md` and `docs/`.
- Inspected the PKG with ps3recomp `pkg_extract.py`: 84 entries, finalized retail package,
  extracts without the RAP. Identified UE3 v539 (`TAGame`), Bink, GameSpy, PhysX, trophy
  set `NPWR00406_00`. EBOOT/SPUJOBS are NPDRM SELFs (license type 2, need the RAP).
- Surveyed ~85 GitHub repos built on ps3recomp: Drakengard 3 (soyjxck/dod3-recomp) is the
  only UE3 port and is playable; documented in `docs/reference-ports.md`.
