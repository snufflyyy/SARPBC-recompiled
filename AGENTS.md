# AGENTS.md — SARPBC-recomp

Static recompilation of **Supersonic Acrobatic Rocket-Powered Battle-Cars** (PS3 / PSN,
`NPUB30035`, Psyonix, 2008, Unreal Engine 3) into a native PC executable, built on
[ps3recomp](https://github.com/sp00nznet/ps3recomp). No emulator at run time: PPU (and SPU)
machine code is lifted ahead of time to C/C++ and linked against ps3recomp's runtime and
HLE system libraries.

This file is the **core**: read it every session. Read the `docs/` file for whatever area
you are touching instead of re-scanning the tree or the game files.

## Current state (keep this line true)

**Phase 7 done: 01.09 reaches the main menu (2026-10-19); now SPU performance, then a project audit.**
The PPU lift, all 15 SPU images, the 2 SPUJOBS jobs and the MultiStream overlay build on 01.02 and
01.09, with 41 ps3recomp patches. The PhysX task pile-up (~1500% CPU) was a SPURS CreateTask race
and is fixed (T033). **Goal: 60 fps in the main menu** (user, 2026-10-19): it is at 29.2 fps after
Vulkan draw batching and a VRAM geometry cache (T040, in progress; the GPU is on PCIe 2.0 x4). Agents the user starts (Claude Code,
pi, Antigravity) take tasks from the board by priority ([docs/workflow.md](docs/workflow.md));
**resume from [docs/status.md](docs/status.md) "Resume here"**.

## Key facts

| | |
|---|---|
| Title / ID | Supersonic Acrobatic Rocket-Powered Battle-Cars — `NPUB30035` (PSN, USA) |
| Content ID | `UP2002-NPUB30035_00-SARBATTLECARS001` |
| Version | APP_VER `01.02`, built for firmware 2.40 |
| Engine | Unreal Engine 3, package version 539 (`0x21B`), game module `TAGame` |
| Executable | NPDRM SELF → `game/EBOOT.elf`: stripped PPC64, 47,602 functions, 274 imports from 20 libraries |
| SPU code | 15 SPU ELFs in the EBOOT (Edge zlib, PhysX, MultiStream DSP) + Edge Geometry jobs in `game/SPUJOBS.prx` |
| Platforms | **Linux is primary** (Fedora, clang + CMake + Ninja), rendering through **Vulkan**. Windows comes later on ps3recomp's D3D12 backend — keep code portable (`#ifdef _WIN32` for POSIX-only calls) |
| Toolkit | `external/ps3recomp` = upstream `sp00nznet/ps3recomp` v0.15.0 (`39a3629`), pinned. Features from the Drakengard 3 fork are brought over as patches ("middle path", see `patches/ps3recomp/README.md`) |
| Closest reference | Drakengard 3 ([soyjxck/dod3-recomp](https://github.com/soyjxck/dod3-recomp)), a playable UE3 port on ps3recomp |

## Hard rules

1. **Never commit or publish game data**: the PKG, RAP, EBOOT (encrypted or decrypted),
   SPRX, extracted assets, lifted C/C++ from the game, or SPU dumps. They are all
   derived from copyrighted code. Only our own sources, configs, scripts and notes go
   into git. Keys/klicensees never go anywhere.
2. **The superproject never records a patched ps3recomp.** `external/ps3recomp` is pinned
   to an upstream commit (`.gitmodules` has `ignore = all`, so its local branch is never
   staged by accident). Every change to it is a commit on its local `sarpbc-patches`
   branch, exported to `patches/ps3recomp/` (see its README) and offered upstream.
   `tools/apply_patches.sh` rebuilds that branch from the pin. Shared runtime code must
   stay title-agnostic (upstream ratchets this with `tools/title_hacks.py`).
3. **Generated code is never hand-edited.** `src/recomp/` and `src/spu_gen/` are
   rebuilt by `tools/relift.sh`. Game-specific behaviour goes in `src/overrides/` or
   `src/stubs.cpp`, keyed by guest address or NID.
4. **Document as you work, not afterwards.** These docs exist so the next agent does not
   have to rediscover anything. Whenever you learn something that cost effort (an
   address and what it does, a hang and its cause, a tool quirk, a dead end, a number),
   write it into the matching `docs/*.md` **in the same change** as the code, and log it
   on your task (`tools/task.sh note`). A new topic gets a new doc plus a row in the index
   below. Mark guesses as guesses and give the evidence (log line, address, command). Keep
   [docs/status.md](docs/status.md) and the current-state paragraph above up to date.
5. **Every agent follows [docs/workflow.md](docs/workflow.md)**, whatever its harness: take a
   task with `tools/task.sh next` and claim it; work in your own worktree (`tools/agent_setup.sh
   <agent>`) inside the task's *Touches*; builds under `tools/task.sh lock cpu`, boots under
   `lock boot`; never `pkill` the game by name; merge your own verified work with
   `tools/merge_to_main.sh`; leave a HANDOFF note before stopping. **Don't spawn subagents**:
   the user starts every agent.
6. Linux is not yet a proven boot platform upstream (see
   [docs/build-linux.md](docs/build-linux.md)); expect to fix POSIX/Vulkan gaps and keep
   those fixes upstreamable.

## Repo layout (planned — create as you go, update here if it changes)

```
AGENTS.md  CLAUDE.md GEMINI.md   agent entry points (CLAUDE.md and GEMINI.md just import this file)
build.sh  run.sh             build / play in one command (01.09 default, --version 0102)
docs/                        technical docs, one topic per file (index below)
Supersonic Acrobatic ... (USA)/   original .pkg + .rap — read-only, git-ignored
external/ps3recomp/          git submodule, pinned; override with $PS3RECOMP
patches/ps3recomp/           our patches against the pinned upstream (+ README: how/why)
docs/tasks/{open,claimed,done}/  the task board (tools/task.sh); live copy is in the main checkout
.worktrees/<agent>/          one git worktree per agent (tools/agent_setup.sh) — git-ignored
vfs/dev_hdd0/game/NPUB30035/ extracted install (PARAM.SFO, USRDIR/...) — git-ignored
game/                        decrypted EBOOT.elf, SPUJOBS.prx — git-ignored
analysis/                    ppu_loader / imports / SPU image output — git-ignored
tools/rpcs3/                 RPCS3 AppImage + isolated config, used only by decrypt.sh — git-ignored
.venv/                       Python venv for ps3recomp tools — git-ignored
src/main.cpp src/stubs.cpp   from the ps3recomp project template
src/overrides/               native replacements / per-NID fixes (edgezlib.cpp, ...)
src/recomp/ src/spu_gen/     GENERATED (lift, NID table, SPU) — git-ignored
tools/                       extract.sh decrypt.sh relift.sh run.sh apply_patches.sh
                             split_toc_stubs.py task.sh agent_setup.sh merge_to_main.sh boot_check.sh
CMakeLists.txt  config.toml
```

## Pipeline in one screen

Day to day, once the game files are in place: **`./build.sh`** then **`./run.sh`** (01.09; add
`--version 0102` for the base game). `build.sh` re-applies the patch stack only when it changed,
configures if needed, and builds under the `cpu` lock. From scratch:

```bash
tools/apply_patches.sh # submodule at the pin + patches/ps3recomp/*.patch (branch sarpbc-patches)
tools/extract.sh      # PKG -> vfs/dev_hdd0/game/NPUB30035/   (ps3recomp tools/pkg_extract.py)
tools/decrypt.sh      # RAP + RPCS3 --decrypt (headless) -> game/EBOOT.elf, game/SPUJOBS.prx
tools/relift.sh       # loader, TOC-stub split, PPU lift, NID table, SPU lift (~1 min)
cmake -S . -B build -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build   # Release + Vulkan are the defaults on Linux -> build/sarpbc
tools/run.sh          # build/sarpbc game/EBOOT.elf vfs (main.cpp maps /dev_hdd0 itself)
tools/boot_check.sh 60 [--gdb] [--version 0109]   # headless boot report; stops only its own game
```
Details and every flag: [docs/pipeline.md](docs/pipeline.md).

## Docs index — read the one you need

| Doc | Read it when |
|---|---|
| [docs/status.md](docs/status.md) | Always, at session start: where things stand, what is next, open problems |
| [docs/game-profile.md](docs/game-profile.md) | You need facts about the game files, PKG contents, PARAM.SFO, configs |
| [docs/ps3recomp-primer.md](docs/ps3recomp-primer.md) | You need to know what ps3recomp provides, where things live in it, its limits |
| [docs/pipeline.md](docs/pipeline.md) | Extracting, decrypting, lifting, regenerating, or building |
| [docs/build-linux.md](docs/build-linux.md) | Toolchain, CMake options, Vulkan, Linux-specific gaps |
| [docs/unreal-engine-3.md](docs/unreal-engine-3.md) | Reasoning about the game's own code: threads, file I/O, renderer, UnrealScript |
| [docs/reference-ports.md](docs/reference-ports.md) | Before solving a UE3 problem: Drakengard 3 (dod3-recomp) is a finished UE3 port on ps3recomp |
| [docs/dod3-reuse.md](docs/dod3-reuse.md) | Before writing anything new: what Drakengard 3's port / fork already has, what's ported, what's next (partial inventory) |
| [docs/subsystems.md](docs/subsystems.md) | Working on graphics, audio, input, SPU/SPURS, saves, video, network, trophies |
| [docs/debugging.md](docs/debugging.md) | Something hangs, crashes or draws wrong; `tools/boot_check.sh` (paste the first line of `analysis/boot_report.txt` into task notes), env vars, triage recipes |
| [docs/workflow.md](docs/workflow.md) | Before any work: task board, claiming, worktrees, locks, merging, **pausing and resuming** |
| [docs/hle-coverage.md](docs/hle-coverage.md) | Which firmware imports have HLE handlers (stub/impl), named NIDs, ranked gaps (`tools/hle_coverage.py`) |

## Working conventions

- Match ps3recomp's style in code we write (C17 for runtime-style code, C++20 for the
  boot scaffold); keep comments explaining *why*, with guest addresses in hex.
- Prefer a general fix in an HLE module (as an upstreamable patch) over a per-title hack;
  if a hack is unavoidable, put it in `src/overrides/` with the reason and the address.
- RPCS3 is a behavioural reference only — never copy its (GPL) code into this tree.
- Long-running steps (full PKG extract, a full lift, a full build) take minutes; run them
  in the background and do not repeat them without cause.
- **No subagents.** Don't spawn subagents (Claude Code's Agent tool, workflows, or another
  harness's equivalent) unless the user asks: they used too much usage (user, 2026-10-19). The
  user runs more agents in parallel by starting them, and they coordinate through the board.
