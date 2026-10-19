# ps3recomp primer

What the toolkit gives us, where to look inside it, and what it cannot do yet.
Written against **v0.15.0, commit `39a3629` (2026-10-16)**. When the pin moves, re-check
the "limits" section and the CLI flags in [pipeline.md](pipeline.md).

Upstream's own docs are good and long; this page tells you which one to open.

## Model

```
EBOOT.elf ──ppu_loader.py──► functions/imports/image/loader JSON
          ──ppu_lifter.py──► ppu_recomp.h + ppu_recomp_NNN.cpp   (one C++ fn per guest fn)
gen_hle_nids.py ───────────► ppu_hle_nids.cpp                    (NID -> HLE handler table)
SPU images ──spu_lifter.py─► spu_recomp.c + registration by content fingerprint
all of it + libps3recomp_runtime + per-game boot scaffold ──► native executable
```

- Guest memory is a flat 4 GB-reserved region (`vm_base`); guest addresses are 32-bit,
  big-endian data is byte-swapped on every load/store by the lifted code.
- Each guest function becomes a host function taking the PPU context (GPRs, FPRs, VRs,
  CR, LR, CTR, XER). Indirect calls go through a guest-address → host-function table;
  a miss logs `[ppu] unresolved indirect call -> 0x...`.
- Firmware imports are resolved by **NID** (32-bit hash of the symbol). The lifter
  rewrites each import trampoline to `ps3_hle_call(nid)`; the handler table routes it to
  an HLE implementation in `libs/`.
- PPU threads are host threads. LV2 syscalls are implemented in `runtime/syscalls/`.
- SPU programs are lifted separately; local store is a 256 KB array; DMA is memcpy;
  SPURS workloads/tasks/jobs are matched to lifted code by FNV-1a-64 fingerprint of the
  image the game hands to cellSpurs.
- RSX: cellGcm's command buffer is walked by a FIFO processor that decodes NV47xx
  methods and drives a backend (D3D12 / Metal / Vulkan / null). With guest programs on,
  the game's own NV40 vertex/fragment microcode is translated at run time.

## Where things live (upstream tree)

| Path | What |
|---|---|
| `tools/` | Python pipeline (~140 scripts): `pkg_extract.py`, `unfself.py`, `ppu_loader.py`, `ppu_lifter.py`, `find_functions.py`, `gen_hle_nids.py`, `gen_imports.py`, `triage_elf.py`, `extract_spu_images.py`, `find_spu_functions.py`, `spu_lifter.py`, `build_spu_workloads.py`, `lift_prx.py`, `nid_database.py`, `show_func.py`, `callgraph.py`, Ghidra/IDA helpers |
| `runtime/ppu/` | PPU context, memory macros, HLE dispatch, loader + `boot_main.cpp` scaffold (compiled **per game**, not in the lib) |
| `runtime/spu/` | SPU context, channels, MFC/DMA, workload registry, interpreter fallback |
| `runtime/syscalls/` | LV2 syscalls (threads, sync, events, timers, memory, fs, ...) |
| `libs/<area>/` | HLE modules: audio, video (cellGcmSys, RSX, backends), input, filesystem (cellFs, cellGame, cellSaveData, EDAT), system, network (incl. sceNp*), spurs, sync, codec, font, misc |
| `include/ps3emu/` | Public headers: `ps3types.h` (`be_t<>`), `endian.h`, `nid.h`, `module.h`, `error_codes.h` |
| `templates/project/` | Starter port: `CMakeLists.txt`, `main.cpp`, `stubs.cpp`, `config.toml` |
| `tests/`, `tools/test_*.py` | Lifter/runtime tests; `tools/regress.py` = cross-port regression gate |

## Upstream docs worth opening (in `external/ps3recomp/docs/`)

| Doc | For |
|---|---|
| `GETTING_STARTED.md` | The 4-command pipeline and the classic first-boot failures |
| `GAME_PORTING_GUIDE.md` | 12-phase porting walkthrough (flOw case study) |
| `PPU_RECOMP.md`, `TOOLS.md` | Lifter internals and every tool's flags |
| `RUNTIME.md`, `SYSCALLS.md`, `NID_SYSTEM.md` | Runtime model, syscalls, NIDs |
| `CUSTOM_MODULES.md` | Writing/overriding an HLE function |
| `MODULE_STATUS.md`, `MODULES_REFERENCE.md` | What each HLE module does and how complete it is |
| `RSX_GRAPHICS.md`, `RSX_FRAGMENT_PROGRAM.md` | Graphics pipeline, shader translation |
| `SPU_LIFTER.md`, `SPU_FALLBACK.md`, `SPURS_SCHEDULING.md` | SPU and SPURS |
| `BUILDING.md` | CMake options incl. the Linux Vulkan backend |
| `DIAGNOSTICS.md` | Generated index of every diagnostic env var |
| `DEBUG_CONSOLE.md` | Querying a running title without rebuilding |
| `FIRMWARE_LLE.md` | Running real firmware PRXs (LLE) when HLE isn't enough |
| `ONLINE.md` | psnr (PSN stand-in) — note our title uses GameSpy, not NP matching |

## Limits that matter to us

- **Linux has never booted a title in the upstream tree.** The runtime builds and tests
  on Linux, the scaffold compiles on POSIX, and Vulkan runs guest shaders in
  `ps3recomp_host`, but booting to gameplay has only been done downstream (Twisted Metal
  menus on Linux/Vulkan) with unmerged patches. Expect to be a pioneer here.
- Windows (D3D12, clang-cl) is the only platform with in-tree playable titles.
- Media: `cellAdec` has callbacks but no decode; `cellVdec` uses FFmpeg loaded at run
  time (opt-in). Bink is *not* a Sony library — it is linked into the EBOOT and runs as
  game code (plus its own SPU code), so it gets lifted, not HLE'd.
- SPURS: management, job queues, policy scheduling exist; edge cases still turn up per
  title. Unrecognised SPU images can be dumped with `SPU_DUMP_MISS=<dir>`.
- No NPDRM decryption of SELFs: ps3recomp ships no keys and does no retail decryption.
  It *does* decrypt EDAT/SDAT data files at run time given a klicensee (`libs/filesystem/edat.c`).

## Reference ports (good code to read)

| Port | Why it's relevant |
|---|---|
| [sp00nznet/simpsonsarcade-ps3](https://github.com/sp00nznet/simpsonsarcade-ps3) | PSN title (`NPUB`), playable; `tools/relift.sh`, SPU job capture flow, `src/spu_workloads.c` |
| [sp00nznet/tornado](https://github.com/sp00nznet/tornado) | In-game with no per-title overrides; SPURS + Bink intro |
| [sp00nznet/twistedmetal](https://github.com/sp00nznet/twistedmetal) | Closest to Linux/Vulkan bring-up |
| [sp00nznet/flow](https://github.com/sp00nznet/flow) | The porting guide's case study |

**The one UE3 title on ps3recomp is Drakengard 3** (soyjxck/dod3-recomp, playable,
on its own diverged fork of the toolkit). See [reference-ports.md](reference-ports.md)
before solving any UE3-shaped problem.
