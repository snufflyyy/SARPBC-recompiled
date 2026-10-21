# Reference ports — Drakengard 3 (UE3) and others

Researched 2026-10-18 by scanning every public GitHub repo that references ps3recomp
(~85 repos) plus web search. **Only one Unreal Engine 3 title was found on ps3recomp:
Drakengard 3.** It is a finished, released port and our most important reference.
Re-check for new UE3 ports when this doc gets old (search GitHub for `ps3recomp`, then
look for `.XXX`/`Coalesced`/`UObject`/`GNatives` in the repos).

## Drakengard 3 — [soyjxck/dod3-recomp](https://github.com/soyjxck/dod3-recomp)

| | |
|---|---|
| Game | Drakengard 3 (BLUS31197, disc + 1.01 update + DLC), Access Games / Square Enix, 2013 |
| Engine | UE3, package version **860** (ours is **539** — five years older) |
| Status | Playable start to finish; releases for Windows (D3D12) and macOS (Metal); Vulkan engine exists, Linux not a shipped target |
| Scale | 30,134 PPU functions (ours should be similar: both EBOOTs ≈ 30 MB), 40 SPU programs + 2 raw SPURS jobs, ~550 MB lifted C++, clean build ~15 min |
| License | MIT — code can be reused with attribution (keep their copyright notice) |
| Toolkit | Submodule of its own fork **[soyjxck/ps3recomp](https://github.com/soyjxck/ps3recomp)**: 208 non-merge commits not in upstream `sp00nznet/ps3recomp` v0.16.0 (`749182e`) as of 2026-10-20 (it was 174 ahead of v0.13.0 on 2026-10-18). The port itself is at `f6c24bf` "0.3.0 alpha". Full commit-by-commit inventory: [dod3-reuse.md](dod3-reuse.md) |
| Read first | `docs/TECHNICAL.md` (how it works), `docs/DEBUGGING.md`, `CONTRIBUTING.md` (tree layout) |

### What their fork has that upstream (v0.16.0) lacks

- **Lifter**: `--nonvolatile-locals` (registers as C locals, written back only where
  needed) and `--hook <addr>` (call a native replacement first). Upstream has `--chunks`,
  which the fork does not. Big performance difference: their lifted executable went 430 →
  293 MB and frame times dropped by a third.
- **`rsx_vulkan_engine.c`** — a full Vulkan engine on the shared draw engine (upstream
  has `rsx_vulkan_backend.c` only), plus `rsx_host_mouse.c`, MSAA/FXAA/internal-resolution
  passes, texture write-watching, occlusion queries with GPU round trip, snapshots of
  targets read while drawn.
- Runtime: guest memory through a 64 KiB page table (`ppu_vm_fast.h`), user-mode
  `sys_lwmutex`, `sys_lwcond` wakeups, pooled SPU task threads, frozen guest clocks.
- Frame pacing: `rsx_present_pace` (even presents under a frame cap), a walker kick on
  every guest `usleep`, vertex fetch by attribute, a vertex cache.
- Landed upstream since v0.15.0 (so no longer a difference): SSE2/AVX2 SPU float paths,
  GCM callbacks at `usleep`, the `cellFsOpen` flag values, the spinlock width, vertex-span-once.
  What is ported to us and what is still open: [dod3-reuse.md](dod3-reuse.md).

### UE3 lessons that should transfer to SARPBC

| Problem they hit | Their fix | Where |
|---|---|---|
| No vblank interrupt; render thread waits on GCM labels | Host "frame clock" thread ticks vblank, drains the GCM FIFO each tick (labels get written by the drain), kicks the walker on guest `usleep`; render thread's fence poll replaced natively | `src/main.cpp`, frame clock |
| Frame rate locked/smoothed | Replace `UEngine::GetMaxTickRate` (a `GEngine` virtual, through the function registry) to return the cap, or follow the scene on a ladder of caps (`DOD3_FPS=adaptive`); run vblank at 8×; `rsx_present_pace` spaces presents evenly | `DOD3_FPS`, `rsx_present_pace.h` |
| Bink movies judder | Render thread ticks Bink at `GRenderingThreadMaxIdleTickFrequency`; raise it to 1000 while a movie plays | `DOD3_RENDER_TICK_HZ` |
| Slow loading screens | UE3 async loader runs 5 ms/frame; spend the limiter's sleep in the loader while packages are pending | `src/patches/load_idle.cpp` |
| UE3 garbage collector hitches | Reachability pass translated natively, multithreaded, purge deferred into the limiter sleep | `src/patches/gc*.cpp` |
| Package decompression on SPU (Edge zlib via SPURS LFQueue) | Native inflate, verified by Adler-32 | `src/patches/edgezlib.cpp` |
| HLE SPURS queue/LFQueue not good enough | Lift Sony's own `libsre` paths at build time | `src/kernel/spurs_*.cpp`, `tools/gen_libsre.py` |
| Audio: MultiStream on SPU loads an **MP3 decoder from console firmware** | Native MP3 decoder behind a stand-in SPU image; DSP biquads native | `src/apu/` |
| ShaderPatching LZF SPU job ~200×/frame | Native copy loops + memo | `src/patches/spu_hooks.c` |
| PhysX on SPU slow | PhysX taskset at hardware contention 3 | title defaults in `main()` |
| Game maps memory over the default GCM IO window | Move GCM window to `0x8F000000`, FIFO resync off, NV0039 on subchannel 1, SPURS job chains synchronous | title defaults in `main()` |
| Camera speed tied to frame time | Scale stick input above 30 fps | `src/input/camera.cpp` |
| Engine verifies packages against a hash table in the EBOOT | When patching a package, rewrite its hash in the EBOOT's table and its `PS3TOC.TXT` line; serve via an overlay dir | `src/patches/menu_patch.cpp`, `tools/ue3/pkgpatch.py` |

Each native replacement has a **check mode** that runs lifted and native side by side
and compares — copy that discipline.

### Tools worth adapting

- `tools/ue3/` — UE3 package reader (`upk.py`: decompress, name/import/export tables),
  UnrealScript disassembler (`dis.py`), bytecode tree editor (`script.py`), package
  patcher (`pkgpatch.py`), cross-build script diff (`diff.py`). Written for **v860**;
  v539 differs in the package summary/export-table layout and some bytecode, so expect
  to adapt field offsets, not rewrite.
- `src/cpu/uscript.h` — calling into the UnrealScript VM from native code (`GNatives`,
  `FFrame` with Object at +0x14, Code at +0x18 in v860 — verify for v539).
- `tools/eboot_diff.py`, `addr_map.py`, `data_map.py` — map addresses across EBOOT builds.
- `tools/replay_regress.sh` + `RSX_CAPTURE` / `rsx_replay` — headless rendering regression.
- `tools/autoplay.sh`, `live_bench.sh` — unattended runs and benchmarks.
- `src/install/self.cpp` — SELF → ELF; handles disc SELFs and **free-license** NPDRM
  only. SARPBC's EBOOT is license type 2 (RAP-bound), so it does not cover us as-is.

### Differences to keep in mind

- v539 (2008) vs v860 (2013): different engine generation — function addresses, struct
  offsets, and which systems run on SPU will differ. Treat their addresses as hints for
  *what* to look for, never as values.
- Disc title (`/dev_bdvd`, `PS3_GAME`) vs our HDD/PSN title (`/dev_hdd0/game/NPUB30035`).
- They target Windows/macOS; we target Linux. Their Vulkan *engine* is `_WIN32`-only and a
  different design from upstream's `rsx_vulkan_backend.c`, which is what we run and patch: lean
  on their draw-engine and decompiler fixes and their pacing code, not on that engine
  (details in [dod3-reuse.md](dod3-reuse.md)).

## Other ps3recomp ports worth knowing

| Port | Relevance |
|---|---|
| [sp00nznet/simpsonsarcade-ps3](https://github.com/sp00nznet/simpsonsarcade-ps3) | PSN (`NPUB`) title, playable; relift script, SPU job capture |
| [sp00nznet/tornado](https://github.com/sp00nznet/tornado) | In-game with no per-title overrides; Bink intro |
| [sp00nznet/twistedmetal](https://github.com/sp00nznet/twistedmetal) | Car combat; Linux/Vulkan menus reached downstream |
| [sp00nznet/crazytaxi-ps3](https://github.com/sp00nznet/crazytaxi-ps3) | PSN driving game, boots to attract demo |
| [YYOzcan/tokisaki-port](https://github.com/YYOzcan/tokisaki-port) (Killzone 2), [canersaka/Yakuza-Dead-Souls-Recompiled](https://github.com/canersaka/Yakuza-Dead-Souls-Recompiled), [benjidotsh/LittleBigRecomp](https://github.com/benjidotsh/LittleBigRecomp) | Large SPURS-heavy titles, not UE3 |

Not a ps3recomp port despite turning up in searches: Splatterhouse-PC (Xbox 360 recomp).
No other port's README or code mentions Unreal.

## Lifter performance (`--nonvolatile-locals`, T009 decision, 2026-10-21)

Not ported. Measured instead of guessed: T029's stack sampler (docs/subsystems.md "SPU time by
category") puts **PPU lifted code at 6.1% of on-CPU stacks** on the Single Player screen, with
GCM/Vulkan at 18% and SPU code at 40-53%; the guest main/render threads are bound by the drain and
the RSX thread, not by the lifted PPU code. The fork's own message says its hot code was
float/vector and memory work, not r14-r31 spills, and the 64 KiB page-table store path would skip
the guest lock that T052's reservation coherence relies on (pi's review). A relift of 7.5M lines
plus a large lifter change cannot pay back a 6% share. Revisit if a PPU-heavy scene (a real match
with game logic) shows lifted PPU code above ~30% of stacks.
