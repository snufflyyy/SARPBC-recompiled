# SARPBC-recomp

A static recompilation of *Supersonic Acrobatic Rocket-Powered Battle-Cars* (PS3, PSN
`NPUB30035`, Psyonix, 2008) into a native Linux executable, built on
[ps3recomp](https://github.com/sp00nznet/ps3recomp). The PowerPC and SPU machine code is lifted to
C++ ahead of time and linked against ps3recomp's runtime and HLE system libraries: there is no
emulator at run time. Rendering goes through Vulkan.

**State:** version 01.09 boots to the menus and plays an offline match in the arena at 35+ fps on
Linux. Online play is out of scope. Windows (D3D12) and macOS are future targets, not verified.

## You need to bring the game

This repository contains no game data and never will. You need your own copy of the game's PKG
and RAP; `tools/extract.sh`, `tools/decrypt.sh` and `tools/relift.sh` turn them into the
(git-ignored) lifted sources. See [docs/pipeline.md](docs/pipeline.md).

## Build and run

```bash
./build.sh      # patches the pinned ps3recomp, configures, builds (clang + Ninja)
./run.sh        # starts the game
tools/boot_check.sh 60 --version 0109   # headless boot report, for testing
tools/lint.py --tests                   # repository checks and every test script
```

## Where things are

| | |
|---|---|
| [AGENTS.md](AGENTS.md) | project rules and the current state; start here |
| [docs/status.md](docs/status.md) | where things stand and what is next |
| [docs/build-linux.md](docs/build-linux.md) | toolchain and Vulkan notes |
| [docs/subsystems.md](docs/subsystems.md) | graphics, audio, input, SPU, how each was made to work |
| [docs/workflow.md](docs/workflow.md) | the task board used by the people and agents working on it |
| `src/overrides/` | port-side replacements, keyed by guest address or NID |
| `patches/ps3recomp/` | our patches on the pinned upstream runtime |

## License

The original code in this repository has no license chosen yet (the owner has to pick one).
Third-party code keeps its own notices: ps3recomp (MIT) and the Drakengard 3 port's
keyboard/MP3 code (MIT).
