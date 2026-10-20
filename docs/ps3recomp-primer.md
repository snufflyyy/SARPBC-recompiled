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

## Guest callbacks: `ppu_guest_call` and its stacks (T026)

The HLE runtime calls back into lifted code (sysutil callbacks, GCM vblank/flip/user
handlers, NP trophy status callbacks, PRX `start_module`, `sys_ppu_thread_once` inits)
through `ppu_guest_call(opd, a0..a7)` or `ppu_guest_call_ct(code, toc, ...)` in
`runtime/ppu/ppu_loader.cpp`. Each call builds a fresh `ppu_context` and needs an r1.

**Before T026** that r1 was the fixed address `0xCFFE0000` on every host thread and at
every nesting depth (the Drakengard 3 fork has the same code). That address is inside RSX
local memory (`0xC0000000`, `localSize` 256 MB in cellGcmSys), and two callbacks built
their frames on the same bytes whenever they overlapped. The lifted code saves r14-r31 and
locals in those guest frames, so the outer callback carried on with whatever the inner
one left there. On 01.09 this happens all the time (boot of 2026-10-19 with
`GCM_INTR_THREAD=1`, from the slot log below):
- the **flip handler `0x000DC144`** (OPD `0x012025A0`) runs **inside the GCM user handler
  `0x000DC390`** (OPD `0x012025B0`) at depth 1: on the main thread (tid 1), on
  RenderingThread (tid 2) and on the host-only GCM interrupt thread (tid `0x7FFF0000`);
- the **vblank handler `0x000DC2DC`** (OPD `0x012025A8`) runs at depth 0 on four other
  threads (tids 0/4/6/8), at the same time as the above;
- also seen: `0x00049D20` (trophy status callback, OPD `0x01201F38`) on tid 5,
  `0x00B62784` (`sys_ppu_thread_once` init, OPD `0x01234598`) on tid 1, `0x000BC6F0`
  (cellSaveData `funcStat`, OPD `0x01201DE0`, AutoLoad2 of `NPUB30035-PROFILE`) on
  SaveData (tid 9).

**Now (patch `0030-ppu-guest-call-stacks.patch`)** every (host thread, nesting depth)
pair has its own stack:
- Carved from the **top of the PPU stack region** (0xD0000000-0xE0000000) by moving
  `g_vm_stack_alloc.region_end` down; thread stacks keep growing up from `VM_STACK_BASE`, so
  the two never meet and no address is hard-coded. A carve keeps 16 MB of headroom above
  the thread stacks. The first stack is `0xDFFC0000..0xE0000000`.
- Default 256 KB each (`PPU_CB_STACK_SIZE=<bytes>` to change, read once), with a no-access
  guard page at the bottom: an overflow faults instead of corrupting the next stack.
- A thread-local `PpuCbStacks` (C++ `thread_local`, for its destructor) holds one stack
  per depth (max 32) and the depth counter, which `ppu_guest_call_run` pushes and pops
  around the call. When the host thread ends, its stacks go to a pool (512) that the
  next thread takes from. 64 short-lived threads use one stack, not 64.
- Log: the first 32 slot assignments print
  `[ppu] guest_call: tid 0x.. depth N -> stack 0x..-0x.. for code 0x.. (inside 0x..)`.
  A depth > 0 line is a nested callback; `inside` is the callback it runs in.
- Locking caveat: the table lock that `sys_ppu_thread_create` holds around
  `vm_stack_allocate` is static in `runtime/syscalls/sys_ppu_thread.c`, outside T026's
  scope. A carve stores `region_end` as one aligned 32-bit word that only moves down, and
  the headroom keeps a thread stack allocated at the same moment far below it. A
  `ppu_stack_carve()` exported from sys_ppu_thread.c under its lock would be cleaner.
- Effect on the 01.09 boot (`GCM_INTR_THREAD=1`, 60 s, 2026-10-19): **no visible change
  yet.** Old code 3 runs: flips 53/56/66, ESRB screen in 2 of 3 (the miss loaded slowly:
  TEXTURES.TFC opened at 26.6 s instead of ~6 s). New code 3 runs: flips 30/66/57, ESRB in
  2 of 3 (the miss ran before the shared boot lock, under host load ~160: TEXTURES.TFC at
  15.8 s). Every run stops presenting within ~8 s of the ESRB
  screen (the rwlock stall, T027). The nested frames were being overwritten all along;
  removing that is a correctness fix that this stage of the boot does not show.
- Not changed: the callback still gets `r13 = PPU_TLS_TP` (the shared TLS block), not the
  calling guest thread's r13. On the console, sysutil callbacks run on the calling thread
  with its TLS. That is a separate fix if it ever matters.

Test: `external/ps3recomp/tools/test_ppu_guest_call_stacks.py` builds the real
`ppu_loader.cpp` with `runtime/ppu/tests/test_ppu_guest_call_stacks.cpp`: two host
threads inside a callback at once, a nested callback, where the stacks are placed, and
reuse after threads end. The old code fails 6 checks (both threads' frames at
`0xCFFDFC00`, outer and inner frames identical, sp inside RSX memory); the new code
passes all of them.

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
| [sp00nznet/simpsonsarcade-ps3](https://github.com/sp00nznet/simpsonsarcade-ps3) | PSN title (`NPUB`), playable; `tools/relift.sh`, SPU job capture flow, `simpsonsarcade-ps3/src/spu_workloads.c` |
| [sp00nznet/tornado](https://github.com/sp00nznet/tornado) | In-game with no per-title overrides; SPURS + Bink intro |
| [sp00nznet/twistedmetal](https://github.com/sp00nznet/twistedmetal) | Closest to Linux/Vulkan bring-up |
| [sp00nznet/flow](https://github.com/sp00nznet/flow) | The porting guide's case study |

**The one UE3 title on ps3recomp is Drakengard 3** (soyjxck/dod3-recomp, playable,
on its own diverged fork of the toolkit). See [reference-ports.md](reference-ports.md)
before solving any UE3-shaped problem.
