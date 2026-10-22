# Subsystems — what each area needs for SARPBC

One section per area: what the game uses, what ps3recomp provides, and the expected
work. Update the **Status** line of a section when you change it.

## File system

- Game installs as an HDD title: guest paths are `/dev_hdd0/game/NPUB30035/USRDIR/SARB/...`.
  Map with `PS3_HDD0_ROOT=<dir containing game/>` (`runtime/ppu/ppu_fs.cpp`). `PS3_VFS_ROOT`
  covers `/dev_bdvd` — not used by this title unless it probes for a disc.
- **Case sensitivity: no problem.** The engine opens upper-case paths itself
  (`/dev_hdd0/game/NPUB30035/USRDIR/SARB/TAGAME/COOKEDPS3/CORE.XXX`), so they match the
  extracted tree as is (verified with `PS3_FSLOG=1`, 2026-10-18).
- Observed file order at boot: `PS3TOC.TXT`, `___LOCK` (created), `BINARIES/EPICINTERNAL.TXT`
  (ENOENT, fine), `COALESCED.INI`, `COALESCED.INT`, `SPLASH.BMP`, `LOADING.BMP`,
  `LOADSCREEN.VPO/FPO`, `GLOBALSHADERCACHE-PS3.BIN`, then packages `CORE`, `PSYUI`,
  `MAINMENU`, `STARTUP_INT`, `TASTATS`, `TAGAME`, `ONLINESUBSYSTEMGAMESPY(_LOC_INT)`,
  `IPDRV`, `ENGINE`, ...
- `cellGame` is used after all (`HddGameCheck` on `NPUB30035`), through the cellSysutil
  library rather than as its own import.
- `..\` relative paths and backslashes are resolved by the game against its own base
  dir; watch the first opens to see what reaches cellFs.
- Save data (01.09; 01.02 imports no cellSaveData/cellGame): the title boots through cellGame
  (`BootCheck`, `GetParamString(100)`, `ContentPermit`, `DataCheck`, `GetSizeKB`; type 2 from
  PARAM.SFO CATEGORY `HG`), then a "SaveData" guest thread calls `cellSaveDataAutoLoad2` and
  `AutoSave2` for the one directory `NPUB30035-PROFILE`. Round trip verified 2026-10-21
  (T017): with the directory removed, boot 1 shows `LOAD (new=1)`, funcStat result 1, then
  `SAVE (new=1)` writing ICON0 (207830 B), PIC1 (562000 B) and `PAYLOAD` (3335 B); boot 2
  shows `LOAD (new=0)` reading the same 3335-byte PAYLOAD (byte-identical to the older
  save). It lands in `gamedata/dev_hdd0/home/00000001/savedata/NPUB30035-PROFILE/` with
  PARAM.SFO (2736 B), ICON0.PNG, PIC1.PNG, PAYLOAD and an 8-byte PARAM.PFD. Not exercised:
  `FixedSave2`/`ListLoad2` (the imports exist; no boot path reached them, they belong to
  user-triggered saves) and a second save after game progress.

## Graphics (RSX → Vulkan)

- Game uses libgcm directly (UE3 PS3RHI). ps3recomp: cellGcmSys + FIFO walker + NV4097
  draw engine + Vulkan backend running guest programs.
- Expected issues: flip/vblank pacing (the game is capped at 30 fps, user 2026-10-20; vsync on), labels/reports
  used as render-thread fences, tiled surfaces, zcull, post-FX render-to-texture, DXT
  textures from TFC, Bink YCrCb shaders.
- First milestone: `LOADSCREEN` program draws the splash/loading screen.
- **FIFO parks (T024, 2026-10-19).** The RHI ends command segments with a JUMP-to-self
  ("park") and patches it later. Two writers, seen with `GCM_PARK_LOG=1` (01.09,
  `SPU_INTERP_UNLIFTED=1`, run `20261019-093854`):
  1. **The flip handler.** Before the park the FIFO has `GCM_SET_USER_COMMAND` (0xEB00).
     The walker queues it, the user handler (OPD `0x012025B0`, code `0xDC390`) calls
     `cellGcmSetFlipImmediate`, and the flip handler `func_000DC144` rewrites the park as
     JUMP park+4. This takes about 5 ms once the handler is delivered (T022 found the chain).
  2. **The ShaderPatching SPURS chain `0x012B6F00`.** It rewrites the park word to `0`
     (a NOP). This takes 12-21 ms, and each time the log shows `chain 0x012B6F00: END after N job(s)`.
  The park at io `0x8B144` from T023 is one of these. With the pin's code, the stuck-get
  watchdog resynced ~30 ms after a park, before either writer ran. It also pumped handlers
  only at HLE imports, but the render thread polls in `sys_timer_usleep` (an lv2 call).
  T024 patches: fork 0018 (user-command queue) + 0139, `GCM_INTR_THREAD=1` (handlers on a
  host interrupt thread), the stuck-get watchdog skips self-JUMP parks, `GCM_PARK_GRACE_MS`,
  and `GCM_PARK_LOG`. With these, every park up to io `0xD3C64` is patched and nothing is
  dropped (`ref` reaches `0x417C8`). The park at io `0xD494C` (after vertex arrays
  0x1740/0x1680/0x1FC0) is never patched. The chain ran 227 jobs after it was set but did
  not patch it, so the jump-park grace resyncs past it. That is T022's cause 2 (a `Run`
  during an in-flight walk is dropped; libs/spurs). Without `SPU_INTERP_UNLIFTED`
  (after T007), PhysX stalls first (`cellSpursQueuePopBody`, T025): the FIFO goes idle at
  get==put≈`0x6FF0C` and never gets that far.
  *Update 2026-10-19 (T024, second session):* the `0xD494C` park was cause 2; with 0022
  (chain re-walk) and the relift (0026) no park goes unpatched. Park addresses move from
  run to run, so do not key anything on them.
- **Park grace: how long parks really take (T024, 2026-10-19).** `GCM_PARK_LOG=1` times
  every release. Flip-handler (JUMP) parks: 4-40 ms, up to 192 ms when the host is loaded
  and handlers are only pumped at HLE calls (28 ms with `GCM_INTR_THREAD=1`). Chain (NOP)
  parks: average 8-45 ms, worst 300-950 ms (one frame has ~25 of them, so they set the
  frame rate: ~1 flip/s at the screen-adjust prompt). The pin's 50 ms grace therefore
  resyncs past a park in nearly every boot (even unloaded: boot `20261019-102519`, park
  io `0x134F04`), drops the frame's fence write, and the render thread waits forever:
  the boot stops on "Loading..." or the legal/ESRB screen. With a grace of 5 s or longer
  there were 0 resyncs in every boot. Boots (01.09, 90-150 s, `GCM_PARK_LOG=1`):

  | Setup | Result |
  |---|---|
  | grace 50 ms (pin), no intr thread | ESRB screen, then stuck (36-83 flips, 1-2 jump-park resyncs) |
  | grace 50 ms, `GCM_INTR_THREAD=1` | stuck (84 flips; a chain park not patched within 50 ms) |
  | grace 1e8 / 5000 ms, with or without intr thread | past ESRB to the Psyonix logo (63-119 flips), 0 resyncs |
  | + PrepareFlip fix + ring-recycle fix (below), grace 5000, intr on or off | **screen-adjust prompt** ("Use the Left Stick ... press X"), 109-112 flips in 120 s, 0 resyncs |

  The first three rows ran at host load ~150 (5 agents booting at once), the last under the
  shared boot lock. The intr thread mattered under load (flip-handler parks 28 ms vs 192 ms)
  and made no difference unloaded. **SARPBC default** (`src/overrides/gcm_config.cpp`,
  setenv before init; values already in the environment win): `GCM_PARK_GRACE_MS=5000`,
  `GCM_INTR_THREAD=1`. Caveat: guest callbacks still share one stack at `0xCFFE0000` on every
  thread (T026), so the interrupt thread's handlers can collide with another thread's
  callback; `GCM_INTR_THREAD=0` turns it off.
- **PrepareFlip returns the buffer id (T024, patch 0032).** The user handler
  `func_000DC390` takes the flip id from the low 16 bits of the 0xEB00 user command's data
  (stored at `0x0123CDB0`; `0xFF` = none) and calls `cellGcmSetFlipImmediate` with it. That
  data is the return value of `cellGcmSetPrepareFlip`, which the RHI writes into its command
  stream. The pin returned `CELL_OK` (0) and flipped on the spot, so the game prepared 0/1
  alternately but every flip showed buffer 0 (108 of 108). T024 corrected the return id.
  T058 now queues the preparation at its FIFO position; Immediate acknowledges it without
  another flip. The legacy optional early callback stays on that successful PPU ack for
  park release, never on the locked GPU drain. `GCM_PREPARE_FLIPS_NOW` is removed; the
  current implementation and validation are in docs/dod3-reuse.md, item 5.
  The native clock's post-drain counter fallback must also require and consume
  the existing pending-frame flag: leaving it set presents again next iteration;
  ignoring a failed claim presents ordinary queued markers before execution.
  `tools/test_frame_clock.py` compiles the real loop with deterministic hooks:
  fourteen uncapped/capped cases cover exact presentation counts, queued markers,
  catch-up ticks and the pre-first-flip fallback. No new backend policy or cap.
- **Flip handler `func_000DC144` (01.09).** Bumps a counter at `0x01295428`; if the pending
  count at `0x01295460` is non-zero it decrements it, takes the park slot from a 2-entry table
  at `0x01295430` (index `0x01295458`, toggled each time; it waits for the slot with
  `sys_timer_usleep` while it is empty), converts it with `func_00F8C340` and writes
  `JUMP (park+4)` there. So each delivered flip releases at most one park, and extra calls
  with nothing pending are harmless.
- **Ring recycle (T024, patch 0033).** The RHI's command buffer is ctx `0x0F800000`,
  `begin 0x40000000`, `end 0x402FF000` (3 MB), with the runtime's buffer-full callback (OPD
  `0x0F800010`). The game fills it to exactly `end` once per lap, then calls that callback
  (`cellGcm_fifo_recycle`). The drain thread took `current == end` for an overrun and recycled
  first ("recycled the title's own ring"), racing the callback; one boot (`20261019-110645`,
  intr thread off) then never submitted again and stayed on "Loading...". Patch 0034: no
  drain-side recycle while the callback is the runtime's (boot `20261019-111716`: 0 such
  recycles, PROGRESSING). Before that, patch 0033: the drain-side recycle teleported `get`
  to `begin`, dropping whatever the walker had not read yet: when the walker was parked in
  the tail that was ~31 KB including the frame's fence (boot `20261019-101911`: stuck at 50 s).
  Now `get` is left alone while it is still in the tail; the log says "walker drains the tail
  first". `fifo recycle: drain stalled` (the runtime callback waited 2 s for the walker) also
  appears with long parks; it rewinds `current` anyway, which is safe here because the head
  of the ring has long been read.
- **Next bottleneck: chain-park latency.** At the screen-adjust prompt the FIFO spends most
  of its time on ShaderPatching chain parks (30-40 ms average each). That is SPURS job-chain
  turnaround (libs/spurs), not GCM.
- Status: 01.09 draws the legal/ESRB screen, the Psyonix logo and the screen-adjust prompt
  through Vulkan. Linux/Vulkan is the least-proven upstream path.

### Menu frame rate: Vulkan batching and the PCIe bus (T040, 2026-10-20, in progress)

Goal (user): a steady 30 fps in the main menu, the game's own cap (60 until 2026-10-20). After T033 the game uses about one core, so the limit is
the frame-clock thread (`frame_clock` in src/main.cpp), which drains the GCM FIFO into the
Vulkan backend. **This machine's GPU link is PCIe 2.0 x4** (`nvidia-smi` under load; Gen1 x4
idle), about 2 GB/s, so every byte or GPU round trip per frame is expensive.

How it was measured (perf is denied in this container):
- **gdb stack sampling** of the running game (`gdb -p PID -batch -ex "thread apply all bt 24"`,
  ~25-60 samples, aggregated per thread). Before: the frame clock was in `vk_submit_and_wait`
  in 15 of 15 samples. Every engine draw submitted and waited on its own command buffer,
  because all draws shared one vertex buffer, constant buffer and descriptor set.
- `FRAME_CLOCK_STATS=1` (src/main.cpp): ms per 5 s in sleep / FIFO drain / present.
- `PS3RECOMP_VK_BATCH_STATS=1`: draws per batch, submits and total GPU wait.
- `PS3RECOMP_VK_DRAW_TIMES=1`: GPU timestamps per draw, per pipeline, slowest draws. Draws
  with geometry in host memory cost 30-70 us each, and a 7,772-vertex/21,696-index draw
  (pipeline 67) 1.2 ms.
- Menus pass **~38 KB of vertices+indices and 8.2 KB of vertex constants per draw** (~150-190
  draws a frame); 69% of constant binds are unchanged.
- `SARPBC_FRAME_STATS=1` (T029, src/overrides/frame_stats.cpp) counts guest frames per second.
  Don't use `frames.jsonl` gaps for fps: its timestamps have a 0.5 s grain (the 120/N "steps"
  seen first were that grain).
- boot_check redirects stderr, which turns verbose logging on (`ps3_log.h`). Measure with
  `PS3_VERBOSE=0` (verbose costs ~5% here).

Changes (patches 0037 by pi, 0038):
- T024: present reads back a 1x1 centre texel instead of the whole frame, unless a dump is due.
- T040: engine draws record into one command buffer (per-draw slices of per-batch arenas and
  per-draw descriptor sets). Anything else that touches the GPU flushes the batch first. Vertex
  and index data go through a 64 MB content-hash cache in device-local host-visible (BAR)
  memory. Unchanged constants are reused. On the engine path, present reads nothing back.
- Dead end: putting the per-draw arenas in BAR memory *without* the cache was slower (23 fps):
  the CPU then pushes ~9 MB a frame across the bus. Removing the per-draw barriers changed
  little (30.9 vs 29.9 fps), so they are not the GPU cost.

Numbers (01.09, `PS3_VERBOSE=0`, boot lock, this machine):

| build | screen | fps |
|---|---|---|
| main after 0036 (pi's baseline, dumps on, verbose) | main menu | 19.8 |
| before T040 | Choose Profile | ~23 |
| + batching | Choose Profile | 27.2 |
| + no present readback, `PS3_VERBOSE=0` | Choose Profile | ~30 |
| + geometry cache + constant reuse | Choose Profile | 32.5 |
| merged with T024/T029/T041 | **main menu** | **29.2** (1 s windows 26-32) |
| main at 1f58db1 (new measurement) | Single Player (heavier: blurred backdrop) | 19.5 |
| + shared render pass (0053) | Single Player | **~32** (windows 29.7-34.8) |
| + shared render pass (0053) | arena (rendering checked by capture) | 29-33 after load |
| + inlined vertex decode (0054, bit-exact) | Single Player | ~37 (31-42), frame clock idle ~25% |
| + 0054 | arena after load | 29.8-33 (frame clock idle in 1/3 of samples: guest/cap-bound) |
| frame clock Sleep(4) -> Sleep(1) | Single Player / arena | 53 (min 48) / 33-36 |
| + clears and colour snapshots in the batch (0055) | Single Player / arena | 54 / 36-39 |
| + attribute-major vertex fetch (0056) | arena | ~38 |

Main menu recipe: `PAD_FILE` with CROSS for 3 polls at 45 s and at 50 s; measure from ~75 s.
Where the frame goes now (Choose Profile, ~31 ms): ~18 ms CPU in the FIFO drain (vertex
fetch/decode `rsx_vertex_fetch_one`, `eng_texture_content_hash` on texture binds, `sink_end`),
~8 ms waiting on the GPU (batch flushes forced by depth/stencil clears and present), ~4.6 ms
idle in `Sleep(4)`. Next: record clears into the batch, overlap GPU with CPU (double-buffered
submissions instead of waiting), and cut the per-draw CPU work in the draw engine.

Render pass per draw was the largest GPU cost (2026-10-20, patch 0053): `PS3RECOMP_VK_DRAW_TIMES`
showed 32-35 us for even a 4-vertex quad, ~400 draws a menu frame (13 ms), because every draw
began and ended its own pass, loading and storing each attachment. Draws into the same
framebuffer now share a pass (`s_batch.pass_fb`, closed by `vk_batch_flush`); a draw that
samples one of its own attachments still starts a new pass. Single Player went 19.5 to ~32 fps.
Where the frame went before (5 s of `FRAME_CLOCK_STATS`): fifo 2.95 s, present 1.44 s, sleep
0.6 s; GPU waits were ~22 ms per frame. Next: vertex decode (`rsx_vertex_decode_element`, ~40%
of FIFO samples), then overlapping GPU and CPU.

SPU threads are not the limit any more (2026-10-20, `/proc/<pid>/task/*/stat` over 20 s on the
Single Player screen, 0053 applied): the game uses ~190% CPU in total, three threads at 74%,
59% and 43%, the rest under 10%. The 90% lock/spin share seen on 2026-10-19 was T033's
double-started tasks. T029/T031/T032 (SPU speed) stay open for an SPU-heavy scene.

### Async batches: CPU and GPU overlap (T060, 2026-10-22, patch 0074)

After 0056 the arena ran at 38-40 guest fps with the frame clock thread 78% busy in the FIFO drain
(`FRAME_CLOCK_STATS`: fifo 3.9 s of 5 s). gdb stack samples (40 samples of a 130 s arena run, `bt 30`,
frame-clock thread only) put **46% of that thread in `vk_submit_and_wait`**: every batch was submitted
and waited for, so recording (CPU) and execution (GPU) ran in series. `PS3RECOMP_VK_BATCH_STATS=1`
said 41 s of 130 s in GPU waits, from two call sites: the present's flush (4955, 2.7 ms each) and
`vk_eng_release` (7370, 2.9 ms each: every released image flushed and waited).

What changed, in `rsx_vulkan_backend.c` (all of it behind `PS3RECOMP_VK_ASYNC=0` for the old
behaviour):
- **Deferred destroy**: an image or framebuffer released while a batch is open, or another is in
  flight, goes to the live context's graveyard and is destroyed once that context has completed.
  Alone it moved the wait (41 to 36 s) and gained ~1 fps: the work still ran in series.
- **Two contexts** (`s_bc[2]`: command buffer, fence, vertex/index/constant arenas, descriptor pool,
  graveyard). `vk_batch_flush_async()` submits and switches to the other context, waiting for it only
  when it comes round (one batch behind). The present and a full batch flush asynchronously;
  `vk_batch_flush()` keeps the old contract (everything complete on return) for every other caller.
  Every command buffer begun while the other context is in flight starts with a full barrier, so
  batches and the one-shot copies/uploads run in submission order. The geometry cache is append-only
  between full flushes, so an in-flight batch's vertices are never overwritten.
- **Depth snapshot** (the shadow map's copy, `vk_eng_depth_snapshot`) recorded in the batch through one
  persistent staging buffer (VRAM via the BAR window when available) instead of a host buffer and a
  submit-and-wait. After the contexts it was the stall: 9 of 33 samples.

| 130 s arena run (`PS3_VERBOSE=0`) | guest fps (steady) | GPU waits |
|---|---|---|
| before (main 00092fb) | 38-40 | 41.2 s |
| deferred destroy | ~40 | 36.4 s |
| + two contexts | ~40 | 13.6 s |
| + snapshot in the batch | **47-48** | **1.4 s** |

Menus ran 55-60 fps in the same run. Captures (menu and arena, shadow under the car) are unchanged.
Remaining waits: texture creation and uploads (`vk_begin` + `vk_submit_and_wait`).

**The present was the next stall (patch 0075 + `src/main.cpp`).** With the GPU waits gone, gdb samples
put 15 of 40 frame-clock samples in `vk_present_complete_locked`: `rsx_vulkan_backend_present()` is
`_present_begin()` + `_present_finish()`, so the clock waited for the batch and copy it had just
submitted, in series with the next drain. `PS3RECOMP_VK_GPU_TIMES=1` (with `PS3RECOMP_VK_BATCH_STATS=1`)
showed why that was not the GPU's fault: **GPU busy 5.0 ms per batch (~5.5 ms a frame), idle 99 s of
130 s**. The frame clock now calls `_present_begin()` at the flip and finishes the present after a later
drain, only once `rsx_vulkan_backend_present_ready()` (a zero-timeout fence poll) says the copy is done;
the next flip finishes a still-open present first. A blocking finish right after the flip does not
help: the drain there is short (the guest queues the next frame only once the flip is serviced), so it
waited the GPU's whole frame time. `SARPBC_SPLIT_PRESENT=0` presents whole again.

| 130 s arena run (`PS3_VERBOSE=0`) | guest fps (steady) | frame clock per 5 s: fifo / present |
|---|---|---|
| after async batches | 47-50 | 3.2 s / 1.56 s (finish waiting) |
| + split present, polled finish | **55-60** (the 60 Hz clock) | 4.2 s / 0.13 s |

**GPU power state (this machine, not fixed here).** `nvidia-smi` during the arena run: P8, SM 405 MHz
of 2115, memory 405 MHz of 7001, PCIe Gen 1 x4, 32% utilisation: the driver does not leave its idle
state for this bursty load, so every GPU job runs at a fifth of the clock. `nvidia-smi -lgc` is denied
(no permission) and not ours to change; if the user wants the headroom, "prefer maximum performance"
(PowerMizer / `nvidia-smi -pm 1` with locked clocks) on their side would make the GPU part cheaper still.

### Draw-engine CPU: decoded-vertex cache and geometry ids (T061, 2026-10-22, patch 0076)

With the GPU waits gone (T060) the arena was bound by the FIFO drain: ~15 ms of every frame on the clock
thread. gdb samples of that thread (70 drain samples): `vk_geo_get` 17%, vertex fetch/decode 26%, remap
build 13%, texture hashing ~7%, the rest `sink_end` itself. Where it went per draw is now measurable:
`RSX_DRAW_CACHE_STATS=1` prints microseconds per draw (refs / key / decode on a miss / textures / indices /
backend draw).

- **Decoded-vertex cache** (`rsx_draw_engine.c`, `vc_*`). UE3 draws the same static meshes every frame and the
  decode is a pure function of the reference list, the attribute formats and the bytes of each attribute's
  span (the fetch plan's `stable_base`..`stable_last`). The key is a 128-bit hash of exactly those (interleaved
  attributes share one hashed span), so a hit returns the decoded vertices and the occurrence map without the
  remap or the fetch, and no write-watch (mprotect) is needed: the bytes themselves are hashed, at memory
  speed instead of decode speed. Not cached: inline/immediate vertices, frequency-divided attributes, an
  attribute without one contiguous span, draws of 8 refs or fewer (~35% of draws in the arena; they are
  cheap). 96 MB arena, 8192 slots, reset when full. Arena run: 1.05M hits, 29K misses, **0 mismatches**
  with `RSX_DRAW_CACHE_CHECK=1` (decodes anyway on every hit and compares). `RSX_DRAW_CACHE=0` turns it off.
- **Geometry ids**: a hit gives the backend an id for the immutable entry (new optional
  `rsx_draw_backend.geometry_hint`; the rebuilt index list gets one too when no restart cut split it), and the
  Vulkan backend finds its VRAM copy by id (`s_geo_id`) instead of hashing the vertices and indices again
  (`PS3RECOMP_VK_GEO_CHECK=1` re-hashes and compares: 0 mismatches). Backend draw 9.4 to 3.8 us per draw.
- **Texture binds**: a hashed index over `g.textures[]` replaces a linear scan of up to 1024 entries per bind
  (nine field compares each), and the full content hash runs four independent lanes instead of one FNV chain
  (~2 GB/s). Textures 5.6 to 4.5 us per draw; what is left there is the sparse per-frame check and the
  sampler/descriptor work.

| 130 s arena run | drain per frame (clock thread) | clock idle | guest fps |
|---|---|---|---|
| after T060 | ~15 ms | 6% | 55-60 |
| + vertex cache | 9.6 ms | 40% | 60 (cap) |
| + ids, texture index | **7.4 ms** | 53% | 60 (cap) |

Per draw now (all draws, ~280 a frame): refs 5.5 us (the index scan: `dc_push_ref` per index), key 3.4,
textures 4.5, indices 0.8, backend 3.8. Ideas not done: hash the raw index bytes and take min/max from them to
skip building the ref list on a hit; a cached rebuilt index buffer; texture write-watch (needs a safe
`mprotect` story, see Port next 9). The arena is clock-capped at 60 here, so the next fps gain is T062.

### Arena flip-callback stall (T044, 2026-10-20)

After the slab-service repair lets the challenge package load, a 140 s boot
stops presenting near 77 s. The render thread is inside flip handler
`func_000DC144`, reached from `ppu_gcm_pump` at an HLE boundary in
`func_000DD214` / `func_000EE334`. The handler polls a render-owned park slot;
its suspended render caller cannot publish further state. A dedicated
interrupt thread existed, but other HLE callers could still steal its work.
Evidence: pi worktree `analysis/boot_check/20261020-093821-685745/gdb.txt`.

The runtime now leaves pending ticks and user commands untouched on foreign
threads while a GCM interrupt worker is published. The worker alone pumps
callbacks. With no worker, manual/HLE delivery still works. Failed thread
startup closes and clears the event so it cannot disable that fallback.
The fixture checks FIFO ordering, exactly-once delivery, tick retention and
mocked CreateThread failure under GCC and Clang. No fences are skipped and
no flips are fabricated. Verified 2026-10-20 (claude, 120 s boot with `--pad`):
frames are presented to the end of the run (6025 flips); the frame was black
until T045's depth-clear fix below.

### Arena renders black: reversed-Z depth clear (T045, 2026-10-20)

The arena frame was black except for a few corrupt HUD rectangles. The per-pass
capture showed why (`RSX_ENGINE_PASS_DUMP=<dir> RSX_ENGINE_PASS_DUMP_AFTER=85
RSX_ENGINE_PASS_DUMP_DRAWS=1`, 105 s boot with
`--pad 'cross@40*4/5,cross@70,r2:120@90,cross@100'`):
- The scene goes into an FP16 target `0x0A130000` (cfmt 11) with zeta
  `0x09570000` (Z24S8). Each frame starts with a depth-only pre-pass into it
  (10 draws, colour mask 0, depth func `0x206` GEQUAL, depth write on).
- **UE3 here uses reversed-Z**: every clear sets `ZSTENCIL_CLEAR_VALUE = 0`
  (21 of 21 clears; passes.txt now logs `color`/`zs` per clear).
- `sink_clear` in `libs/video/rsx_draw_engine.c` mapped `zs == 0` to depth 1.0
  (upstream `4df0909`, still in v0.16.0). With depth 1.0 and GEQUAL nothing
  passes: the depth buffer stayed uniformly 1.0 and the scene black.
- Patch `0044-zstencil-clear-zero`: a zero clear value clears to 0. The nv40
  reset `0xFFFFFF00` that `rsx_dispatch_init` seeds still gives 1.0 to titles
  that never set the register. After it the pre-pass writes depth (0..0.017)
  and the arena draws (stadium, floor, walls). The D3D12 path,
  `rsx_live_draw.c:7591`, has the same `!zs ? 1.0f` and is not patched yet.

What was still wrong after this fix (noisy surfaces, garbage HUD) was the
next section.

### Arena textures: NV0039 copies on subchannel 1 (T045, 2026-10-20)

After the depth fix the arena drew, but the floor grate, the city windows and
the HUD sampled noise. `RSX_ENGINE_PASS_DUMP_TEX=1` (patch 0045) dumped every
decoded texture: the DXT ones were right, but the swizzled A8R8G8B8/B8 ones in
local memory (HUD atlas `0x03B38B80` 1024x1024 f85, `0x008D8600` 512x512 f81,
the 64x64 icons) were blocks of *other* textures in Morton-shaped staircases:
stale VRAM, not a decode bug. A one-off histogram of non-zero subchannels
showed why: the game sends **NV0039** (memory-to-memory copy, libgcm's default
binding on subchannel 1) `0x0184` x2 (DMA in/out) and `0x030C` x8 (offset
in/out, pitch in/out, line length, line count, format `0x101`, BUFFER_NOTIFY).
The pin treated subchannel 1 as NV4097 (for Twisted Metal), so no copy ran and
the words landed on NV4097 `0x030C..0x0328` (blend enable/factors/colour mask).
The draw engine also got NV3062 (subchannel 3) and NV3089 (6) methods with the
subchannel masked off, i.e. on the alpha-test and blend registers.

Patch `0046-nv0039-copy-engine`: NV0039 copies (local/main, signed pitches,
element increments; the report area `0x66626660` as a source, which the game
uses to copy 32-304 bytes of reports to main IO `0x300000`); subchannel 1 is
NV0039 until it carries a method NV0039 lacks; only 3D-routed methods reach the
draw engine. Copies seen in the arena: VRAM to VRAM, e.g. 2048 B
`0x740CF00 -> 0x7437D00`. Test: `tools/test_gcm_nv0039.py`.

After it (run `20261020-170312`, 130 s, `--pad 'cross@40*4/5,cross@70,r2:200@90,r2:200@105,cross@100'`):
the floor, walls and windows are clean, the HUD is right (timer, score, stars,
boost meter), and the car is drawn and drives into the goal tunnel on throttle.
The car's shadow was then a dark square on the floor (next section). **Still
wrong:** the scene fills only the
middle 1088x612 (85%) of the 1280x720 frame with a black border. The menus
(Choose Profile) and dialogs have the same box, UI and 3D alike, so it is the
game's screen-size setting from its safe-area screen, not a renderer bug (not
checked against hardware); D3D12 (`rsx_live_draw.c`) still gets every subchannel's methods and
has the `!zs ? 1.0f` clear (T011).

### Car shadow: depth-compare direction (T045, 2026-10-20)

The car's shadow map is pass 003 of a frame: a 512x512 Z24S8 zeta at
`0x0AC00000` (pitch 2048), cleared to 1.0 (`zs FFFFFF00`, normal-Z unlike the
scene), scissor 320x320, LEQUAL. The next pass multiplies the scene (blend
DST_COLOR x ZERO) by a lookup into it as DEPTH24_D8 (`fB0`), wrap
`0x60010303`: zfunc 6, GEQUAL. Upstream's helper (4033da8, from ARB_shadow and
synthetic tests) computed `reference >= depth`: any floor fragment in front of
the far plane failed, so the whole frustum was dark. RSX compares the other way
round, `depth >= reference` (A/B in the same kickoff scene with a temporary
switch: the square goes, nothing else changes). Patch
`0047-shadow-compare-direction`. If another title's shadows invert after this,
suspect this patch first.

### Car shadow: where it landed (T054, 2026-10-21)

After 0047 the dark square was gone but the shadow was a hard-edged patch beside
the car that moved around when driving (user, 2026-10-21: "wrong place, swims,
looks like a matrix problem"). Not a matrix: the constants were right (the
shadow draw's `fp10`, the car origin, equals the map pass's `vp4` every frame,
so nothing lags). Cause: **the depth snapshot of the shadow map was the whole
zeta.** `eng_zdepth_get` makes every zeta canvas-sized (1280x720), the game's
shadow map is a 512x512 texture in its top-left corner, and the snapshot copy
was 1280x720. The shader samples with normalised coordinates, so every lookup
was scaled by 512/1280 and 512/720 and landed elsewhere in the zeta, moving
with the car. Patch `0064-depth-snapshot-crop` crops the snapshot to the
sampling texture (cache keyed on size); the shadow now sits under/behind the car.

How it was found (reusable): the shadow is a **screen-space multiply** (pass
draw 3: pipe with fp `0c7d45f5d23f4dc7`, 34 constants, blend DST_COLOR x ZERO) that
reads scene depth from the **alpha of the FP16 HDR target** (`0x0A130000`) and
projects it through the light matrix into the map; 4 bilinear taps 0.7 texel
apart, squared, distance fade. The light has the camera's orientation, so the
real shadow is mostly hidden behind the car. `RSX_ENGINE_SKIP_FP=0c7d45f5d23f4dc7`
removes it. A numpy re-run of that shader on dumped alpha, map and constants
disagreed with the GPU image, which pointed at the texture, not the math.
`RSX_ENGINE_PASS_DUMP_ALPHA=1` (patch 0063) writes the alpha of FP16 targets
(`.a.pgm`, raw `.a.f32`) and the raw depth floats (`_z.pgm.f32`).

### Anisotropic filtering (T021 Port next 10, 2026-10-21)

Patch `0066-vulkan-anisotropic`: a sampler gets anisotropy (default 16x, `RSX_ANISO=<n>`,
`1` = off, clamped to the device limit) only when the bound object is a guest texture with
more than one mip level, not a cube, and the title asked for linear min/mag/mip filtering.
Render targets, their views and depth/colour snapshots keep the title's filter: the Drakengard
fork found 16x over those (shadow maps, packed depth, post inputs) puts speckle on floors.
Arena run: floors visibly sharper at a glancing angle, no artefacts, guest fps 36.9 vs ~35.

### Loading / splash screen orientation (T038/T050/T051, 2026-10-20)

The root cause was **PNG scanline order, not shader projection**. A fresh 01.09 boot
opens `LOADING.PNG`; both splash PNG decodes request ARGB (`outputColorSpace=20`)
and bottom-to-top rows (`outputMode=1`). The HLE read that mode but always reported
0 and copied rows top-to-bottom. This supplied the wrong texture layout.

The captured loading draw honours `first=4`, with zero vertex base offset/index.
Its viewport has scale Y=-360 and translate Y=360; the quad has `v=0` at position
Y=-1 and `v=1` at Y=+1. The window formula maps Y=-1 to 720 (the **bottom** edge),
so v=0 must sample the bottom source row, exactly as the requested decoder mode
specifies. No special handling of `LOADSCREEN.VPO` is needed.

Patch `0051-pngdec-output-mode` validates/reports output mode and selects source
rows per decoder without changing stb global state. Channel swizzles and padded
pitch are preserved. Patch `0052-shader-independent-viewports` fully removes
0050's unsafe two-instruction Y-flip heuristic. The existing viewport formulas and
compiler are unchanged: glslang's `setInvertY(true)` applies to **all** vertex
stages, not just projection-matrix shaders.

Synthetic regressions cover both row orders, grayscale/RGB/RGBA/ARGB, heights
1/2/3, packed/padded/no-control pitch, invalid-mode atomicity, and viewport
independence from shader instructions, NOP padding, constants and arithmetic.
Both native fixtures pass ASan+UBSan. A 120 s Linux/Vulkan boot shows upright
Loading and arena/HUD (3729 zlib requests, 2575 flips, unresolved 0). Full review,
public ABI references and evidence: [t038-review.md](t038-review.md). Other backends
are not visually verified.

## Audio

- `PS3Drv.PS3AudioDevice`, 32 voices, LPCM up to 7.1 + Dolby Digital per PARAM.SFO.
- **Confirmed: MultiStream** (statically linked `cellMS*`, incl. MP3 stream functions)
  on SPU, with DSP effects as embedded SPU ELFs (`mstream_dsp_i3dl2/filter/para_eq`),
  outputting through cellAudio (10 imports). `cellMusicUtility` = custom soundtrack.
- **01.09 boot, 2026-10-19 (T007):** `cellAudio` Init / PortOpen(8 ch, 8 blocks, buffer
  `0x58000000`, read index `0x58100000`) / PortStart all succeed. The MultiStream mixer is
  **SPU image 0** (sha `e33837bb...`, fp `C1759183E2FF7448`, task ELF at EA `0x010AF300`),
  started as taskset `0x01370680` task 0. Its "MultiStream Update Thread" (entry OPD
  `0x01225628`) waits on SPURS event flag `0x01372000` bit 1, which the mixer sets.
- **Blocker 1: the DSP plugin block (FIXED 2026-10-19, `tools/make_spu_overlays.py`).** The
  mixer copies the DSP plugins' text into one heap block, GETs it to **LS 0x37000** and calls
  into it (0x37018, 0x37010, 0x37C20, then 0x39818/0x39810/0x39B50; return addresses
  0x03930/0x03AE0/0x04130). Nothing was lifted there, so the task ended with "branched into
  unlifted LS 0x37018" and flag `0x01372000` never got set (`EventFlagWait BLOCKED ...
  flagEA=0x01372000`). Layout, from `SPU_DUMP_OVL=<dir>,0x37000` on 01.09: one 0x2E90-byte
  block, **`mstream_dsp_i3dl2.pic` text at +0x0000 (0x27C0 bytes) and
  `mstream_dsp_para_eq.pic` at +0x2800 (0x690)**, byte for byte the ELFs' executable PT_LOADs
  (va 0x80 = block +0; no relocation applied). `mstream_dsp_filter.pic` is not loaded. dod3's
  2013 MultiStream packs three plugins at 0x0/0x2000/0x2900, so the table is per title.
  `tools/make_spu_overlays.py --spu <SPU_DIR>` (ported from dod3, MIT; `tools/relift.sh`
  runs it after `build_spu_workloads.py`) finds the plugins among the lifted images by their
  SPUNAME string, rebuilds the block, wraps it at 0x37000, lifts it as
  `<SPU_DIR>/spu_ovl_msdsp_37000/` (94 functions; seeds: entries, +0x10 of each plugin, the
  instruction after each `bi $r0`), and appends a constructor that registers it under image
  id `0x4D534401` with `spu_overlay_register_sig_region(first 16 bytes, 0x2E90)`; CMake's
  `*/spu_recomp.c` glob picks it up with no other change. Verified on 01.09 without
  `SPU_INTERP_UNLIFTED`: no "unlifted LS 0x37..." and no BLOCKED on `0x01372000`; perf shows
  the `spu_ovl_msdsp_37000_*` functions running. **01.02:** its plugins are different builds
  (i3dl2 0x2800, para_eq 0x680 bytes), so the tool lays para_eq at +0x2800 there too, but
  that layout is a guess (no 01.02 dump yet; check with `SPU_DUMP_OVL`).
- **Fixed (T053, 2026-10-21): the mixer was too slow for real time, which is the crackle.** See
  "Audio crackle" below; the numbers that were here (75 cycles/s, 27% of real time) are the
  starting point of that section.
- **Blocker 2: `flashMP3.pic` (FIXED; stream path verified 2026-10-20).** The PPU (01.09 `func_0082E690`)
  reads `/dev_flash/sys/external/flashMP3.pic` into a buffer and `func_00835588` parses its
  SPU ELF section table into a descriptor {+0 file EA, +4 body EA, +8 lowest sh_addr,
  +C size, +10 e_entry}. Without it: "Multistream: mp3 failed to load MP3 codec".
  `src/overrides/audio_mp3.cpp` (ported from dod3 `mp3_native.c`, MIT) writes a stand-in
  ELF of our own to `<exe dir>/dev_flash/` at start-up and sets `PS3_DEV_FLASH` (unless the
  user set it), registers a native `decodeFrame` at **LS 0x1A910** (body at 0x1A900, as in
  dod3; the mixer's descriptor sits at LS 0x1A880 and it calls decodeFrame at SPU 0x6E2C
  through the word at LS 0x3C4B0) and decodes with dod3's decoder
  (`audio_mp3dec.cpp`). The file opens and the error is gone. Stream decoding
  was initially untested because no MP3 stream started before the Loading stall.
  Update 2026-10-20: real 44.1 kHz stereo streams decode, and the filter-bank repair below
  lets the mixer keep running. `SARPBC_MP3_TRACE=<n>` logs the first n calls;
  `SARPBC_MP3_NATIVE=0` turns it off.
- **cellAudio on Linux (patch `0021-audio-pacing-devflash-sig-region`):** the POSIX mixing
  loop now paces to the SDL queue (it used fixed 2/5 ms sleeps), and
  `AUDIO_RATE=1` / `AUDIO_PEAK=1` / `AUDIO_WAV=<file>` work on Linux. With PipeWire
  (`SDL_AUDIODRIVER=pulseaudio`): `[audio-rate] 187.5 blocks/s (real time 187.5), silent
  100.0%, dropped 0 frames/s, underruns 0`: the port runs at real time on a real device,
  but every block is silent (nothing reaches the port yet).
  The same patch moves the `/dev_flash` default off a Windows path
  (`$XDG_DATA_HOME/ps3recomp/dev_flash`) and adds `spu_overlay_register_sig_region()`.
- Still seen: `[mfc] REJECTED malformed transfer ... pc=0x0B1C8 lsa=0x30B60 size=0` from
  the mixer, a size-0 GET (a no-op on hardware too; probably an empty stream list).
- ps3recomp: cellAudio over SDL2 on Linux (`SDL_AUDIODRIVER=dummy` for silent runs,
  `PS3_NO_AUDIO` to disable).
- `cellMic` (15 imports) for voice chat — stub "no mic attached" first.
- Status (2026-10-20, T007): both DSP banks are lifted; real MP3 streams decode and
  non-silent audio reaches PulseAudio/PipeWire. A 149.685 s f32 stereo capture has
  2,547,400 nonzero samples, peak 0.955703 and no nonfinite values. Output quality at real
  time: see "Audio crackle" below (T053). The older speed measurements above predate it.

### Sound after the menu became reachable (T007, 2026-10-20)

A 115-second 01.09 boot on `87b64cb` reached `MP_SOCCARARENA.XXX` at
65.2 s, then stalled at 65.7 s (T037). PulseAudio/PipeWire consumed 187.5
blocks/s with zero device underruns, but the output was 100% silent. This
is not evidence that the host audio device failed.

With `SARPBC_MP3_TRACE=30`, the native decoder consumed three valid 44.1 kHz
stereo frames (261, 182, 261 bytes; 2304 output bytes/channel each). The
next line was `img=506692475 branched into unlifted LS 0x37010
(lr=0x03930) -- ending the job`. The DSP entry is present in the generated
lift, but belongs to a different plugin bank from the one now in local
store. The update thread then waits forever on event flag `0x01372000`.

A temporary GET trace found the missing bank: the mixer loads 12 KiB banks
at LS `0x37000`. After MP3 starts, it replaces the initial i3dl2/parametric
EQ bank with the next bank. Its signature matches the embedded
`mstream_dsp_filter.pic` text (0x500 bytes), which the overlay tool does not
yet lift at that address. This contradicts the earlier boot-only finding
that the filter plugin was not loaded. The generic eviction of the old bank
is correct. The overlay tool now emits a second bank under image id
`0x4D534402`, distinct from the original bank's `0x4D534401`. A subsequent
150 s real-device boot has no unlifted branches, the mixer remains alive,
and non-silent output reaches the device. This verifies the missing-bank
repair, not real-time audio quality. Trace: pi worktree
`analysis/boot_check/20261020-090756-641267/run.log`.

Evidence: pi worktree `analysis/boot_check/20261020-090055-586602/run.log`,
lines 12833–12837. Command: `SDL_AUDIODRIVER=pulseaudio PAD_NO_HOST=1
AUDIO_RATE=1 AUDIO_PEAK=1 SARPBC_MP3_TRACE=30 SPURS_EF_STATS=1
SPU_DMA_RANGE=58000000-58200000 PS3_VERBOSE=0`, a locked 115 s boot with
three-poll CROSS presses at 40/45/50/65/80/95 s.

`tools/test_audio_mp3.py` tests the native SPU ABI without firmware or game
data. It covers metadata skips, bad/truncated headers, planar big-endian
PCM, byte counts, return registers and independent stream histories. A
synthetic tone requires ffmpeg/libmp3lame. A separate 48 kHz tone comparison
against ffmpeg gave correlation 0.999999999868 and RMS ratio 0.999999682.
These tests do not prove the game's stream ABI or audible output.

The guard-page test exposed an unrelated host crash: a four-byte ID3v2
prefix at LS end passed the frame-header check, then read its size field
outside local store (SIGSEGV, exit -11). The native override now checks that
the ten-byte ID3v2 header fits and returns the existing decode-error result
when it does not.

### Audio crackle (T053, 2026-10-21)

**Symptom:** the music crackled. `AUDIO_WAV` captured on the 01.09 menu showed no device
trouble (`underruns 0`, 187.5 blocks/s consumed) but **66% of the blocks were all zero** and 860
block-edge discontinuities in 42 s: a block of sound, then 8 silent ones, over and over.

**Cause.** The guest's "MultiStream Update Thread" (tid 8, entry OPD `0x01225628`, loop
`func_0077CEB0` in 01.09) runs one update round, then `Sleep(obj+0x1EC)` (a float, 5 ms), then
polls the port's read index inside `func_0082EA64` (two `usleep`s of ~0.86 ms at `0x0077CEF0`).
A round writes **one** 256-sample block at `read index + lead`. On the PS3 the SPU mixer takes
~0.3 ms per block, so a round is ~5.3 ms: one block per block time. Here the same SPU code cost
3.4 ms (after the fixes below; 7+ ms before), so nap + work = 8-15 ms = two or three block
times, and the game wrote only every 2nd or 3rd ring slot. `AUDIO_GAPS=1` shows it:
`ridx=1478 ring=[#.#.#.>.]`. The reader plays the empty slots as silence. (It is not the host
device, the MP3 decoder - 75 us per frame - or the cellAudio pacing.)

**What was measured, in the order it was found** (01.09 menu, `SPURS_EF_STATS=1`, flag
`0x01372000` waits/s = mixer cycles; the mixer thread was ~70% busy and ~30% parked in
`spu_taskset_wait_signal` while the PPU thread slept):

| Step | Cycles/s | Silent blocks | Block-edge clicks |
|---|---|---|---|
| start | 106 | 66% | 860 / 42 s |
| `SPU_FAST_FLOAT` on the audio images | 166 | 44% | |
| + `SPU_LEAN_LS` | 180 | 39% | 608 |
| + x86 `rotqby` family | 209 | 30% | 673 |
| + no nap (`PS3_USLEEP_SCALE`) | ~300 | **0.0%** | **0-1 / 42 s** |

**Fixes** (all generic except the last, which is a title setting):
1. `SPU_FAST_FLOAT` (patch 0060): the SPU float helpers reproduce truncation, extended range and
   no-NaN bit for bit at ~40 instructions per op. The MultiStream mixer and DSP banks use native
   SSE singles instead (denormals flushed as on the SPU, round to nearest instead of toward
   zero, `runtime/spu/tests/test_spu_fast_float.c`). `CMakeLists.txt` defines it only for the mixer image
   (`spu_e33837bb*`) and the overlays (`spu_ovl_ms*`); option `SARPBC_SPU_FAST_AUDIO_FLOAT`.
2. `SPU_LEAN_LS` (patch 0060): `spu_ls_read128/write128` carry a probe, a watchpoint and an
   SMC-watch check (a load and a branch each, not hoistable); ~70 per DSP loop pass. The same
   audio sources drop them.
3. `rotqby`, `rotqbyi`, `shlqby`, `shlqbyi`, `shlqbybi`, `rotqbybi`, `rotqmby`, `rotqmbybi`,
   `rotqmbyi` (patch 0060): only NEON had a vector form; on x86 each was a 16-iteration byte loop
   (~100 instructions), and `lqd` + `rotqby` is how SPU code loads an unaligned scalar - the
   hottest DSP function's first screen of assembly was all of them. SSSE3 `pshufb` forms,
   checked against the byte loops for every shift amount (`runtime/spu/tests/test_spu_qbyte.c`). Helps every
   title on x86.
4. `PS3_USLEEP_SCALE` (patch 0061) + `src/overrides/audio_pacing.cpp`: the update thread's nap
   is scaled to 0. The loop still waits for the read index to move, so it starts a round as soon
   as a block is free. With the nap kept, even the faster mixer leaves 30% silent blocks.

**Verified** (no audio device in this container; `AUDIO_WAV` + `tools/audio_wav_report.py`):
85 s of menu: 3.1% silent, all of it one 2.7 s pause at an intro screen change (also in the
baseline, the game is silent there), 1 gap, 1 click. 65 s of arena (New Game, driving): 0 silent
blocks, 0 gaps, 1 click. `underruns 0`. Mixer ~2.8 ms per cycle (max ~14 ms, a hiccup the 8-block
ring absorbs). Menu frame rate unchanged (~38 fps in the arena run).

**Not done / ideas:** the mixer still costs ~2.8 ms per 5.33 ms block (one core ~50% busy); the
i3dl2 reverb (`0x37198`, `0x37614`, ~50% of it) and `ctx->gpr[]` memory traffic are the rest.
A native i3dl2 loop or a register-promoting lifter would give margin for slow hosts. The
mixer's exactness is gone by design (float rounding); nothing audible was found. Real playback
through an audio device has not been listened to by an agent: the user should confirm by ear.

## Input

- Imports (sys_io): `cellPadInit/GetData/GetInfo2/ClearBuf/SetPortSetting/SetActDirect`
  (rumble), `cellKbRead`, `cellMouseGetDataList` — the game reads keyboard and mouse too.
  ps3recomp: cellPad over SDL2 (keyboard + gamepads).
- Rocket-car controls want analog sticks and triggers (L2/R2 likely throttle/brake) —
  verify SDL trigger mapping to the analog pressure values the game reads.
- `PAD_SCRIPT` lets automated runs press buttons at given frames.
- **What the game reads (01.09, from the lift):** `func_000D101C` calls cellPadGetData into
  a stack buffer at r1+0x80. Sticks are `(v - 127) * 1/127` (constant at `0x000D0FF4`),
  so the centre is 127/128. L2/R2 are the press-mode words button[18]/[19] (guest
  +0xA8/+0xAA) times 1/255 (`0x000D0FF8`): analog throttle and brake. SIXAXIS words
  (+0xAC..+0xB2) are read only under per-object flags. When `len == 0` it keeps the last
  values, and on an error with `len != 0` it calls ClearBuf. `func_000D1AF4` calls
  GetInfo2 and then `SetPortSetting(port, 2)` only if the port is connected and
  advertises PRESS_MODE. Rumble (`func_000D35D8` -> SetActDirect) sets the small motor
  to 0/1, switched on and off per frame for intensity, and the large motor to 0-255.
  `cellKbRead`/`cellMouseGetDataList` have **no callers**, and cellKbInit/cellMouseInit
  are not imported, so keyboard play must go through the virtual pad.
- **ps3recomp patches:** `0014-dod3-cellpad-sdl2-port.patch` contains Drakengard 3's
  13 libs/input commits (soyjxck, MIT, authors kept): an SDL pad thread, pads by instance
  id, rumble held, `cellPad_set_host_input`, host kind, PAD_NO_HOST.
  `0015-cellpad-racing-fixes.patch` adds our fixes: a half-pulled trigger no longer
  reads as 255 in press mode, the small motor is on/off (0xFFFF), an empty SDL port's
  sticks are 128 (was 0 = held up-left), `PAD_TRIGGERS="l2,r2[,from,until]"`, and
  `PAD_TRACE=1` (logs what reached the guest buffer). Test:
  `CC=clang python3 external/ps3recomp/libs/input/tests/test_cellpad_sdl.py` (SDL virtual
  gamepad, 36 checks).
- **Desk pads:** the SDL thread reads pads even without window focus, so a pad on the desk
  feeds headless runs. Use `PAD_NO_HOST=1` for hands-off runs.
- **Esc** closes the Vulkan window in `rsx_vulkan_backend_pump_messages`. While Esc is
  bound (it is START by default), `input_kbm.cpp` installs an `SDL_SetEventFilter` that
  drops the Esc key-down before the pump sees it. SDL updates its key state before it
  filters, so the key still reads as held. The window's close button still quits.
- `src/overrides/input_config.cpp`: UPPER-CASE keys in config.toml `[input]` become
  environment variables, and the environment wins (`KEY_R2=F tools/run.sh`). The file
  is `$SARPBC_CONFIG`, else `config.toml` beside the executable or one folder up
  (`build-0109/../config.toml`), else `./config.toml`. It runs from a static
  constructor, before main, so `PAD_*` switches can also live there. The run log
  prints `[input] <path>: N control setting(s)`.
- `src/overrides/input_kbm.cpp`: keyboard and mouse into pad port 0. Ported from
  dod3-recomp `96df4c3 src/input/kbm.cpp` (MIT): the binding table, the key parser and
  the 4-way sticks come from there. The key source is new: SDL2 `SDL_GetKeyboardState`
  by **scancode** (a physical key position, so WASD stays WASD on AZERTY),
  `SDL_GetMouseState` for the buttons, and the wheel counted in the event filter. It
  only acts while an SDL window has keyboard focus. It registers through
  `cellPad_set_host_input` (patch 0014) and is merged with any real pad. The run
  log prints `[keyboard] keyboard and mouse on pad port 0`. `SARPBC_KEYBOARD=0` turns
  it off, and `SARPBC_KBM_LOG=1` logs every change. Not built on Windows or macOS (no
  SDL window there), where ps3recomp's own keyboard fallback stays. Mouse look (dod3
  `camera.cpp`) is not ported, because it patches Drakengard 3's own camera addresses.
- **sdl2-compat quirk (measured):** Fedora's SDL2 is sdl2-compat 2.32.74 on top of SDL3.
  A wheel notch reaches an SDL2 event filter as `wheel.y = 0, preciseY = 1.0`, so the
  filter also reads `preciseY`.

**Default bindings** (config.toml `[input]`; each value is a list of keys, `none` = unbound):

| PS3 | Car action (guess from RL conventions) | Gamepad (SDL, by position) | Keyboard / mouse | Setting |
|---|---|---|---|---|
| R2 (analog) | throttle | right trigger (0-255 pressure) | W (full pull) | `KEY_R2` |
| L2 (analog) | brake / reverse | left trigger | S | `KEY_L2` |
| left stick | steer, air pitch/yaw | left stick | W A S D | `KEY_MOVE_UP/_DOWN/_LEFT/_RIGHT` |
| right stick | camera | right stick | I K J L | `KEY_LOOK_UP/_DOWN/_LEFT/_RIGHT` |
| CROSS | jump | bottom face (A / Cross) | Space, right mouse | `KEY_CROSS` |
| CIRCLE | boost | right face (B / Circle) | Shift, left mouse, Backspace | `KEY_CIRCLE` |
| SQUARE | powerslide | left face (X / Square) | Ctrl | `KEY_SQUARE` |
| TRIANGLE | (ball cam?) | top face (Y / Triangle) | R | `KEY_TRIANGLE` |
| L1 / R1 | | shoulders | Q / E | `KEY_L1` / `KEY_R1` |
| L3 / R3 | | stick clicks | C / V | `KEY_L3` / `KEY_R3` |
| START | pause | Start / Options | Esc, Enter | `KEY_START` |
| SELECT | | Back / Share | Tab | `KEY_SELECT` |
| d-pad | menus | d-pad | arrow keys | `KEY_UP/_DOWN/_LEFT/_RIGHT` |

Key names: A-Z 0-9 F1-F12 Space Enter Tab Esc Backspace Shift Ctrl Alt LShift RShift
LCtrl RCtrl LAlt RAlt Up Down Left Right Insert Delete Home End PageUp PageDown CapsLock
Minus Equals LBracket RBracket Semicolon Quote Comma Period Slash Backslash Grave Num0-Num9
Mouse1 (left) Mouse2 (right) Mouse3 (middle) Mouse4 Mouse5 WheelUp WheelDown. The "car
action" column is a guess until menus and a match run; check it against the game's own
controls screen.

- **Verified (01.09, build-0109, 2026-10-19):**
  - The default command `PAD_TRACE=1 PAD_TRIGGERS=0,128,5 SPU_INTERP_UNLIFTED=1
    BUILD_DIR=build-0109 tools/boot_check.sh 60 --version 0109` reaches
    `SetPortSetting(port=0, setting=0x2)` (press mode) and the first `GetData` at about
    4.0 s, just before `RenderingThread` is created. `PAD_TRIGGERS` counts its `from`
    from the first GetData, though, so a 5 s start never meets a poll.
  - With `PAD_NO_HOST=1 PAD_TRACE=1 PAD_TRIGGERS=0,128,0,1` the game's own buffer shows
    the analog value:
    `[cellPad] trace port 0 @0FEFF360 len=24 btn=0200 L=(128,128) R=(128,128) L2=0 R2=128`.
    That is the R2 digital bit plus pressure word button[19] = 128, which the game
    scales by 1/255 to a half throttle. About 1.7 s later (~5.7 s) a second poll reads
    `R2=0`.
  - With the window at 15-16 s after the first poll (`PAD_TRIGGERS=0,200,15,16`) there
    is no trace line. The game stops polling once the main thread blocks in the
    loading stall (`STALLED since 21.6s | last open GUIDCACHE.XXX`, 8 flips), so in-game
    controls cannot be tested until that stall is fixed.
  - Keyboard path: a scratch harness (SDL `offscreen` driver, which gives the window
    keyboard focus) ran `input_kbm.cpp` and `input_config.cpp` with a fake
    `cellPad_set_host_input`. All 9 checks passed: registration before main, config
    file to env, env over file, lower-case keys ignored, nothing before SDL video,
    neutral with no key, Esc key-down dropped while Q passes, a wheel notch giving a
    70 ms stick press that then releases. A real key press cannot be injected
    headless (no xdotool/ydotool here), so held keys still need a manual check in a
    windowed run (`SARPBC_KBM_LOG=1`). boot_check runs with `PS3RECOMP_VK_WINDOW=0`,
    so SDL video is never started and the keyboard reports nothing there.
  - Rumble: `SetActDirect` goes to `SDL_GameControllerRumble` (patches 0014/0015; the
    small motor is on/off at 0xFFFF, the large one 0-255 scaled). It is covered by the
    patch's test only. The game has not rumbled in a run yet because it does not reach
    gameplay.
- Status: T008 done for what the boot allows. Open: in-game check of the bindings and
  rumble once menus run; mouse camera; button prompts by host kind
  (`cellPad_host_kind`).

## SPU / SPURS

- **Status (2026-10-18):** 14 of 15 embedded images are lifted and registered
  (`build_spu_workloads.py --input --allow-partial` in `tools/relift.sh`). Image #7 (324 KB,
  PhysX Dynamics, an overlay image) lifts too once the T003 pipeline patch is in (see PhysX
  below). The Edge zlib task (image 1, fp
  `4100F6EDD2441719`) is dispatched, runs, and then idles in `WAIT_SIGNAL`, because Edge
  zlib requests are now serviced natively on the PPU (`src/overrides/edgezlib.cpp`).
- **PhysX "unlifted LS 0x20180" = an unseeded static constructor (T025, 2026-10-19).**
  01.09 boots logged `[spu] img=363824547 branched into unlifted LS 0x20180 (lr=0x20148) --
  ending the job` (image 7, `spu_5af85a31...`, SPU_DynamicsRelease.elf). Its `.ctors` at LS
  0x36E70 is `{-1, 0x20180, 0}`; crt0's loop at 0x20140 loads each entry and calls it with
  `bisl $r0` (the constructor itself is a bare `bi $r0`). Nothing branches to it by address
  and the list is shorter than the data fn-pointer-table scan's minimum run of 3, so
  `find_spu_functions.py` never seeded it. 9 of the 13 sectioned images had unseeded
  `.ctors`/`.dtors` entries (e.g. 0x31D8/0x31C8 in several PhysX images); the two
  section-stripped images (`d08b1ad8`, `e33837bb`) have empty lists (`-1, 0, -1, 0` at the
  start of their data segment). Patch `0026-spu-seed-ctors-dtors` seeds every
  `.ctors/.dtors/.init_array/.fini_array` word, and for stripped images finds lists by their
  `-1 ... 0` framing. A relift of 01.09 with it: 15/15 registered, complete, every ctor/dtor
  entry lifted (checked against functions.json). Merged as patch 0026; **verified at run time**
  on main 171c84d (01.09 relifted, no `SPU_INTERP_UNLIFTED`): 0 "unlifted" lines in a 60 s
  boot_check. Unit test: `tools/test_spu_find_functions_ctors.py` (patch
  `0029-spu-ctor-dtor-seed-test`). PhysX still logs `HALT-ASSERT heqi pc=0x24884
  img=363824547` (~50 per 60 s boot), a separate problem.
- **SPU speed on x86 (T025, 2026-10-19).** Measure with `SPURS_EF_STATS=1
  SPU_DMA_RANGE=58000000-58200000` (flag `0x01372000` waits/s = mixer cycles; PUT B/s into the
  cellAudio port, real time = 1.536 MB/s). `AUDIO_RATE=1` with the dummy driver measures the
  port's consumption, not the mixer. **Run it under `tools/task.sh lock boot`**, and still
  expect noise: other agents' builds put the host at load 40-130, and the same binary moved
  between 75 and 9 waits/s on different days/loads. Two changes:
  - `spu_shufb` already had an SSE4.1 path, and the runtime library builds with `-msse4.1`,
    but the lifted SPU TUs are compiled by our CMakeLists and got no ISA flag, so their
    (out-of-line) `spu_shufb` was the byte loop. CMakeLists now adds
    `-march=${SARPBC_SPU_X86_ARCH}` (default `x86-64-v2`, `-msse4.2` under clang-cl, probed,
    x86 only, empty disables) to `SPU_SOURCES` only; the PPU lift is untouched (no rebuild).
  - `spu_fa/fs/fm/fma/fms/fnms` got an SSE2 fast path (patch `0030-spu-sse2-float-helpers`, a
    port of upstream's NEON one; SSE2 is baseline x86-64, no flag needed).
    `runtime/spu/tests/test_spu_float_sse.c` checks it bit for bit against the exact path
    (clang and gcc, -O2 / x86-64-v2 / x86-64-v3); fma+fm pair 12 ns vs 33 ns scalar.
  - A/B on 01.09, same lift, 60 s boot_check under the boot lock, mixer PUT averaged over the
    run (Ryzen 7 5700X, 1-min load in brackets):

    | build | waits/s | PUT | of real time |
    |---|---|---|---|
    | before (main 171c84d) | 40.2 / 39.4 | 231 / 226 KB/s | 15.0% / 14.7% (load 46) |
    | + x86-64-v2 on SPU TUs (shufb) | 121.1 / 61.7 | 694 / 355 KB/s | 45.2% (load 39) / 23.1% (load 134) |
    | + SSE2 float helpers | 141.3 | 810 KB/s | 52.7% (load 45) |

    So about 3.5x at comparable load; the mixer is still at ~half of real time. Missing: a
    second "full" run and a perf profile of the full build (next hotspots). Boot summaries did
    not change (STALLED, last open TEXTURES.TFC@6.1s, pkgs 13, zlib 3279, unresolved 0).
- **`_cellSpursLFQueuePushBody` (NID `0x8A85674D`) has no HLE upstream.** The override
  handles only 32-byte (Edge zlib) queues and refuses others loudly.
  Request layout: in/out EA, in/out size, counter EA|inflate bit, flag EA, flag bits,
  skips. This title passes counter 0 and flag `0x01DC8E00` bits `0x0001`.
- **SPUJOBS.SPRX loads (T002, 2026-10-18).** ps3recomp patch `0003-sys-prx-load-module`
  adds general `sys_prx_load_module` / `_on_memcontainer` / `start` / `stop` /
  `unload` (`runtime/prx/prx_runtime.c` + handlers in `runtime/ppu/ppu_sysprx.cpp`):
  - The guest file is an NPDRM SELF the runtime cannot decrypt, so the loader looks
    for a decrypted copy beside the booted ELF (`game/SPUJOBS.prx` next to
    `game/EBOOT.elf`; tries `FOO.prx`, `foo.prx`, `FOO.PRX`, `FOO.elf`) or in
    `$PS3_PRX_DIR`. No per-title table: everything comes from the module file.
  - Segments go into a bump window at `0x0C000000..0x0D000000`
    (`prx_runtime_window_base/end`, or `PS3_PRX_LOAD_BASE`). It must stay below
    `0x10000000`: the job-chain walker skips binaries at or above it as implausible.
  - module_start runs as lifted code if there is any at its address; otherwise a
    strict leaf evaluator (loads, stores, immediates, `mr`, `blr`; nothing else)
    runs it. That covers SPUJobs, whose module_start only copies four TOC words.
  - Log of a run: `[prx] loaded 'SPUJobs' ... id=0x23001001 at 0x0C000000 size
    0xFF20: 2 segment(s), 16 relocation(s), toc 0x0C017F10` then
    `sys_prx_start_module(0x23001001 'SPUJobs') -> CELL_OK, modres=0, argp ...:
    0C000100 0000FC00 0C00FD80 00000108`.
- **Edge Geometry / ShaderPatching job binaries:** `tools/lift_prx_jobs.py <prx>
  --lifted <SPU_DIR> --register <SPU_DIR>/jobmods_register.c` finds them by
  evaluating module_start offline, lifts each at LS 0 (01.02: A 677 functions, 86
  `.word`; B 6 functions; 01.09: A 714 / 143 `.word`, B 6), and writes a constructor
  that registers them by fingerprint. `jobmods_register.c` is a name the
  CMakeLists already compiles from `SPU_DIR` if present, so no CMake change is
  needed. Verified with gdb on a running build: `spu_workload_fingerprint` of the
  bytes at `0x0C000100` (0xFC00) and `0x0C00FD80` (0x110) both resolve through
  `spu_workload_find`, and the game's globals at `0x01D32690` hold the four argp
  words. Not yet seen dispatched: no job chain runs before the current boot stall.
  Details of the module: [game-profile.md](game-profile.md#spu-code).
- **PhysX on SPU (T003, 2026-10-18).**
  - Ten PhysX SPU programs, listed by a table at `0x1CCB8E0` of `{name EA, ELF EA, overlay
    table EA}` x 10 (accessors `0x2245C8` = ELF, `0x224610` = table). ELF EA minus `0x10000`
    is the EBOOT file offset, i.e. the image number in [game-profile.md](game-profile.md#spu-code):
    11 `SPU_IslandGenerationRelease.elf`, **7 `SPU_DynamicsRelease.elf`**, 10/9/8
    `SPU_NarrowPhase1/2/3Release.elf`, 6 `Cloth`, 5 `HeightField`, 4 `Raycast`,
    2 `FluidSpatialHash`, 3 `FluidCollision`.
  - **cellOvis (libovis)** builds the main-memory image an SPU overlay manager DMAs from.
    Init loop `0x224F94` (function `0x224E58`, TOC `0x1C9E6CC`), right after
    `cellSysmoduleLoadModule(CELL_SYSMODULE_OVIS)`: for each program,
    `size = cellOvisGetOverlayTableSize(elf EA)`; skip on 0 or `0x80410402` (INVAL); else
    allocate `size + 0x84` and align to 128 (original pointer at `t - 4`), then
    `cellOvisInitializeOverlayTable(t, elf)`, and any non-zero result is fatal ("PhysX: Error
    initializing overlay table: %i %i"). The table pointer goes verbatim into the SPU task
    context: `struct + 0x4B4` at `0x5793C4`, i.e. offset `0x34` of the context at
    `struct + 0x480`. The SPU checks it is 128-aligned (`0x80410410` = ALIGN otherwise).
  - **Before T003** upstream's cellOvis was invented API: `GetOverlayTableSize(path, u32*)`
    returned NOT_INITIALIZED (`0x80410701`, nothing calls its fake `cellOvisInit`), the
    game asked the allocator for ~2 GB and printed "Error allocating memory for overlay
    table: 0 0"; `cellOvisInitializeOverlayTable` (`0xA876C911`) was not registered at all.
    Patch `0006-cellovis-overlay-table.patch` implements both real functions: size = highest
    overlay `p_paddr + p_memsz` rounded to 128 (`0x77480` for image 7), INVAL for an ELF with
    no overlay; init zeroes the table and copies each overlay to `t + p_paddr`. Overlay =
    PT_LOAD with `p_paddr` >= 256 KiB and != `p_vaddr`. Boot now logs
    `GetOverlayTableSize(elf=0x01A7F000) -> 0x77480` and `InitializeOverlayTable(table=0x40EF0080, ...)`
    and no PhysX error; the other nine programs have no overlays and are skipped.
    `cellOvisFixSpuSegments` / `InvalidateOverlappedSegments` are still missing (not imported).
  - **Image 7 overlays.** PT_LOADs: `.SpuGUID` (16 B at `0x3000`), `.text`+`.rodata` at
    `0x20080`, `.data`/`.bss` at `0x36C80`, and two overlays at VMA `0x3080`:
    `OverlaySmallIsland` (code + inline strings, LMA `0x40000`, `0x1A470` B) and
    `OverlayLargeIsland` (LMA `0x5A480`, `0x1D000` B, all zero: a scratch buffer). The SPU
    manager (`0x33C00`, load-and-mark `0x33DC0`) walks `{vma, size, lma, loaded}` x 3 at LS
    `0x36C80` (count at `0x36CB0`) and DMA-GETs `size` bytes from `table + lma`, clearing
    `loaded` on overlays it overwrites. `0x20188` brings in LargeIsland, after which a stack
    allocator (`0x37120` cursor, `0x37130` end) hands out `0x3080..0x20080` as scratch;
    `0x20338` brings SmallIsland back and resets the allocator to `0x164F0..0x1D4F0`
    (the free tail of the code overlay). `.text` then calls straight into it (`brsl 0x9170`
    at `0x236CC`, `0x23DC4`).
  - **Lifting it** (patch `0007-spu-overlay-lift.patch`): only one overlay holds code, so the
    pipeline lifts `.text` and SmallIsland together as one image (one LS image spanning both,
    each at its own address; 1,463 functions, 495 in the overlay) and registers it by full-ELF
    fingerprint `39119073A3F69512`. Same-address code overlays would need separate lifts and
    are still refused. Ranges holding an undecodable word (inline strings seeded by `ila`) are
    dropped as data; that also fixes the 01.09 images `e33837bb55e5` and `d08b1ad818d0`.
  - **Not yet seen running:** the PhysX taskset is created (`CreateTaskset() ea=0x01CEE680`)
    but no PhysX task starts before the boot stall, so image 7 has not been HIT at run time.
- Confirmed sources ([game-profile.md](game-profile.md#spu-code)): 15 SPU ELFs embedded
  in the EBOOT — **Edge zlib** (package inflate), **PhysX** tasks, **MultiStream** DSP,
  several unidentified — and **Edge Geometry** job images inside `SPUJOBS.prx`
  (a PPU PRX loaded with `sys_prx_load_module`).
- SPURS features used: tasksets, tasks, job chains, event flags, job guards, **Queue
  and LFQueue**. Drakengard 3 lifted Sony's libsre for Queue/LFQueue; we cannot ship
  firmware, so T019 wrote the PPU side from the task-side code instead.
- **SPURS Queue (T019, patch `0013-spurs-queue-ppu.patch`, `libs/spurs/cellSpursQueue.c`).**
  PhysX tasks report to the PPU through SPU2PPU queues (task helper "sendResponseToPPUAndExit":
  non-blocking push retried on AGAIN/BUSY, then push end). Line layout, derived from the
  task-side push in the PhysX images (image `7bde2a3f`: begin LS `0x6990`, end `0x6E88`,
  event throw `0x7608`, task signal `0x7238`): pop index `+0x00`, push index `+0x04` (both in
  `[0, 2*depth)`, stored as `~index` while that side is in progress), size `+0x08`, depth
  `+0x0C`, buffer u64 `+0x10`, SPU port `+0x18` (-1 = none), direction `+0x1C`, waiter lists
  `+0x20` pop / `+0x30` push (u8 count + task ids; workload ids at `+0x40`/`+0x50`), taskset
  u64 `+0x60`. Upstream's old init put size/buffer at `+0x10`/`+0x18` (wrong).
  - Game calls (01.09): `_cellSpursQueueInitialize(0, taskset, q, buf, 16, 128, SPU2PPU)` at
    `0x008496B0`, then `cellSpursQueueAttachLv2EventQueue(q)`; `cellSpursQueuePopBody(q, buf,
    isPeek=0, isBlocking=1)` at `0x008482EC` (any error is fatal) and `(…, 0, 0)` at
    `0x00848394`, which treats `0x80410901` (AGAIN) as "empty". Elements are 16 bytes; the PPU
    reads words `+8` and `+0xC`. Note `cellSpurs.h`'s `CELL_SPURS_TASK_ERROR_*` macros are
    `0x804107xx`; the real values are `0x804109xx` (the queue code spells its own).
  - Blocking pop/push = retried non-blocking tries that sleep until an SPU commits the queue
    line (SPU line-commit hook) or 1 ms (dod3's design). The PPU never parks holding the pop
    side, so the task never needs to throw the `+0x18` event.
  - Verified: `test_spurs_queue` (ctest `spurs_queue`) and a 01.09 boot: six queues init and
    attach (ports 17-22), three blocking pops return real task results, no "Error writing to
    SPURS queue". The boot then stalls elsewhere (EventFlagWait on `0x01372000`, job guard
    `0x0133AA80` closed 20 s).
  - LFQueue: init now writes libsre's CellSyncLFQueue line (from dod3); a general
    `_cellSpursLFQueuePushBody` is still missing (Edge zlib is serviced natively).
- Bink: no Bink SPU image identified yet; may decode on PPU.
- ps3recomp: SPU lifter, workload registry by fingerprint, SPURS (tasks, job chains, job
  queues, policy modules), interpreter fallback, `SPU_DUMP_MISS` capture.
- Typical failure: a PPU thread waiting forever on an event flag / sync word an SPU job
  never set — see [debugging.md](debugging.md).
- Status: in progress (T002 done: SPUJOBS loads; job binaries lifted and registered).

### SPU busy-waits and host CPU (T030, 2026-10-19, paused)

- **Cause found (T033, below):** the PhysX tasks did not pile up because of thread-per-task
  scheduling. A race started ~540 created tasks a second time, and those copies never returned.
  The notes below describe the symptoms; the halt at `0x24884` came from the copies too.
- **What spins.** PhysX tasks (image `363824547` = `spu_5af85a31…`, fingerprint
  `39119073A3F69512`, task entry EA `0x01130600`) get `arg = 0x0133B880` from `CreateTask`.
  That 128-byte line is a task-side sync object of taskset `0x01335080` (word 25 of the line).
  Word 1 is a lock word: the task's acquire at LS `0x32B44` (lr `0x2577C`) does
  GETLLAR, stores `~w1` (negative = held) and PUTLLCs; its release at LS `0x32FA4`
  (lr `0x257B4`) stores `-w1` (positive, sequence +1). Word 0 counts up between the two.
  Words 2-5: `0x10`, `0x80`, buffer EA `0x0133B900`. Error returns `0x804109xx` are
  `CELL_SPURS_TASK_ERROR_*`, so this is a libspurs task-side primitive. The writers are the
  other PhysX tasks (their release); nothing on the PPU. Evidence: `SPU_ATOM_EA=0133B880
  SPU_ATOM_FULL=2` trace, and the lift at `0x32B44`/`0x32D2C` (GETLLAR `0xD0`, PUTLLC `0xB4`).
  A second family (image `7bde2a3f`, entry `0x011E3300`, arg `0x0133AF00`) does the same at
  LS `0x6ACC`.
- **Why it eats the host.** `CreateTask` keeps creating these tasks (ids past 1000 in 90 s)
  and every task gets its own host thread, so 140-220 threads run at once (real SPURS runs at
  most 6). All of them serialize on the single process-wide lock-line spinlock
  (`spu_lockline_lock`, runtime/spu/spu_coherency.c). gdb at 90 s: 142 threads in
  `spu_lockline_lock < spu_wrch < spu_func_00032B44`, 21 in `…00006ACC`. T029's profiler
  (60 s): `spu_lockline_lock` 83% of samples, rwlock 6.8%, `mfc_for` 4.1%, lifted SPU code 0.8%.
- **`HALT-ASSERT heqi pc=0x24884`** (~92 per 90 s) is in the same image but on a different
  path: T028 found it guards a `memalign(128, 2n+2)` result at LS `0x34258` (16-byte alignment).
  Not caused by the lock-line spin; whether it causes more task re-creation is open.
- **Patch T030-spu-mfc-cache-lockline-ttas** (1) `mfc_for` looks up the engine only for
  `MFC_Cmd`, `WrTagUpdate`, `WrListStallAck` (staging writes and all MFC reads are context
  state). The lookup is served from `spu_context.mfc_cache`, which a registry generation
  validates (every free bumps it) plus an owner check (struct copies). (2) The POSIX lock-line
  lock is now test-and-test-and-set with `_mm_pause` and `sched_yield` every 256 spins, like the
  MSVC path. Semantics unchanged; the registry and coherence tests pass
  (`tools/test_spu_context_registries.py`: 558/634/195/51 passed).
- **Numbers** (01.09, 90 s, `GCM_INTR_THREAD=1 GCM_PARK_GRACE_MS=600000`, boot lock, `--gdb`,
  `/proc/<pid>/stat` sampled every 2 s; host load from other agents 40-220):

  | | host CPU 10 s-end | threads | flips | frame dumps (distinct) | last image change |
  |---|---|---|---|---|---|
  | before (8ad1fb8) | 1563% | 202 | 100 | 7 (3) | 41.2 s |
  | after (patch) | 1568% | 218 | 514 | 20 (15) | 24.7 s |

  CPU does not drop, because the threads still spin, now in `sched_yield` (gdb: 144 of them).
  But useful work gets the cores: 5x the flips and 15 distinct frames. One run each, on a
  loaded host, so treat it as a strong hint, not a measurement.
- **Next.** (a) Bound the host threads: run SPURS tasks on at most N (6) host workers instead
  of one thread per task. This is the real fix and touches spu_workload.c/libs/spurs (T028's
  area). (b) Park a reservation spinner: a GETLLAR on a line the context still holds unchanged
  should back off and then wait on `ch_wait_cv` with a ~1 ms timeout. Every writer already calls
  `spu_coh_notify_write` → `spu_ch_wake`. (c) `spu_coh_reserve`/`notify_write` walk every
  registered context under the lock (O(n) with 200 contexts). Index them by line.
  (d) Contention-aware PUTLLC retry backoff.

### Reservation registry lookup (T030, 2026-10-19)

Every GETLLAR calls `spu_coh_reserve` under the global lock-line lock. The old
membership lookup scans every registered virtual context. This adds work inside
the critical section even when the reservation line does not change.

The T030 follow-up adds a private pointer index with 256 buckets and chained
collisions. The index does not limit the number of contexts. The existing list
still controls notification order and reads the current reservation state.
Both cleanup paths remove the index entry before they free the list node.
There are no changes to the context ABI, guest values, reservation events, or
wait timing. The index adds 2 KiB on a 64-bit host and one pointer per holder.

Prior art: `soyjxck/ps3recomp` master `runtime/spu/spu_coherency.c`, checked on
2026-10-19, still uses an eight-slot registry. That fixed limit cannot replace
our registry of virtual contexts.

The standalone benchmark calls the real locked `spu_coh_reserve` round-robin
across contexts. Command from the toolkit root:

```bash
clang -O2 -std=gnu17 -Iinclude -Iruntime/spu \
  runtime/spu/tests/bench_spu_coh_reserve.c -o /tmp/bench_spu_coh_reserve
/tmp/bench_spu_coh_reserve
```

Measurements (CPU ns per call, median of three alternating pairs, Ryzen 7
3700X, clang 19, `-O2`, under the CPU lock):

| Registered contexts | List scan | Pointer index |
|---|---:|---:|
| 6 | 5.62 | 5.90 |
| 64 | 34.87 | 5.93 |
| 256 | 135.45 | 5.94 |

This benchmark isolates membership lookup, not game throughput. The small
registry regresses by 0.28 ns. Large registries improve by 6–23x.

Four 60-second boots used 01.09 and an RTX 2070 SUPER. Both locks remained held
during each measurement to exclude concurrent builds and games. The order was
list, index, index, list. The first pair had another agent's boot between runs.

| Run | Host CPU over 57 s | Threads at 57 s | Flips | Distinct dumps | Logged mixer PUT window |
|---|---:|---:|---:|---:|---:|
| List A1 | 1247% | 263 | 374 | 8 | 686 KB/s |
| Index B1 | 1284% | 961 | 589 | 11 | 663 KB/s |
| Index B2 | 1278% | 997 | 588 | 11 | 656 KB/s |
| List A2 | 1288% | 270 | 320 | 7 | 641 KB/s |

The index produced 57–84% more flips (about 1.7x on average). There is no CPU
or mixer improvement. The mixer windows are event-driven, not whole-run averages.
Faster progress also exposes the existing task accumulation sooner. The worker
pool (T033) remains necessary. All runs opened 13 packages, completed 3285 zlib
requests, and reported zero unresolved calls. The existing assert/blocked alerts
remained.

Command from the project worktree (hold `cpu` around the command as well):

```bash
tools/spu_profile.sh 60 --version 0109 --build-dir build-0109 -- \
  GCM_INTR_THREAD=1 GCM_PARK_GRACE_MS=600000 PAD_NO_HOST=1 \
  SPURS_EF_STATS=1 SPU_DMA_RANGE=58000000-58200000
```

The baseline used a saved binary from `70d7773`, before the index change. Reports:
`spu_profile_20261019-{232023,232304,232505,232611}` in the pi worktree's `analysis/`.
This container denies perf counters. The corrected T029 fallback measured /proc
CPU over the full 57 seconds, but symbol percentages are unavailable.

Tests: `tools/test_spu_context_registries.py` with clang and GCC passes
558/634/2456/51 checks and both allocation-failure cases. The coherence fixture
also passes AddressSanitizer and UndefinedBehaviorSanitizer. New cases cover
300 contexts, repeated registration, collisions, exclusion of the writer,
range cleanup, reverse-order removal, and reuse of the same addresses.

### SPURS tasks started twice (T033, 2026-10-19)

- **The race.** `cellSpursCreateTask` (libs/spurs/cellSpurs.c) sets the new task's enabled and
  ready bits in the guest taskset (`spurs_taskset_add_task`), then spawns its host thread
  (`spu_workload_dispatch_async`). The task was marked running in the runtime's run map
  (`s_ts_run`, runtime/spu/spu_workload.c) only once that thread started. When any task of the
  taskset returns, `spu_taskset_task_exited` starts every enabled task that is ready or pending
  and not marked running. So an exit inside that window started the same task a second time.
  The task id also came through the `g_ydkj_real_taskset_ea`/`g_ydkj_real_taskid` globals,
  which the PPU (CreateTask) and SPU threads (the exit scan) both write before dispatching.
- **Evidence** (01.09, 90 s boot, before the fix): 4390 `CreateTask` lines, 542
  `[taskset] start task N of taskset 0x01335080 ... (after task M exited)` lines, and dispatches
  = creates + restarts for both PhysX families (Dynamics entry `0x01130600`: 2193 + 456 = 2649;
  `0x011E3300`: 2195 + 86 = 2281). All 2281 of the second family returned. Only 2362 of 2649
  Dynamics runs returned, so 287 spun forever on the step's sync line `0x0133B880` (T030's
  "What spins"), and there were 41 `HALT-ASSERT heqi pc=0x24884` (the copies share the task's
  context). Count these with
  `grep -o "async image=[0-9-]* RETURNED" run.log | sort | uniq -c` against
  `grep -o "dispatch HIT (async) fp=0x[0-9A-F]*" run.log | sort | uniq -c`.
- **Fix** (patch `0036-spurs-task-runs-once`): CreateTask marks the task running
  (`spu_taskset_mark`, now exported) before `add_task` publishes it, and unmarks it if no thread
  was started. Both dispatch sites pass the task explicitly (`spu_workload_dispatch_task_async`).
- **Numbers.** 01.09, 90 s `boot_check`, same machine (16 threads, RTX 2070 SUPER), boot lock,
  no env overrides. CPU = `/proc/<pid>/stat` utime+stime over a 20 s window after 40 s:

  | | flips | dumps (distinct) | Dynamics dispatched / returned | restarts | halt-asserts | CPU | host threads |
  |---|---|---|---|---|---|---|---|
  | before (main 70d7773) | 404 | 12 (8) | 2649 / 2362 | 542 | 41 | 1532% | 253 at 62 s, 306 at 90 s |
  | after | 1920 | 37 (33) | 5899 / 5899 | 1 | 0 | 96% | 28 at 65 s, 19 at 90 s |

  Frame rate from `frames.jsonl` (one dump per 60 presented frames): before, 59 fps on Loading,
  then 13-17 fps, then almost nothing after ~25 s. After, a steady 17-24 fps through the
  intro and the safe-area screen. The values sit on 120/N (24, 20, 17.1). That looks like a
  pacing quantum, not SPU work: the process now uses about one core.
- **Not needed now:** the ~6-thread SPURS worker pool. Host threads stay at ~20, because tasks
  return. Revisit it only if a title keeps more than a handful of tasks running at once.
- Unrelated, found here: `tools/test_spurs_scheduler.py` no longer links. Its copy of
  `spurs_line_committed` calls `spurs_queue_line_committed`, which patch 0013 added
  to libs/spurs/cellSpursQueue.c, and the test does not compile that file. All 9 ctest tests
  (`-DPS3RECOMP_BUILD_TESTS=ON`) and `tools/test_spu_context_registries.py` pass.

### MFC DMA fast paths (T032, 2026-10-21)

- **Who does DMA now.** In the arena (01.09, `boot_check --scenario arena`, window 105-125 s)
  exactly one host thread issues MFC commands: the SPU running the MultiStream mixer (lifted
  functions `spu_ovl_msdsp_37000_*` on top of image `e33837bb...`, found with `eu-stack -p
  <pid>`). It is also the busiest thread of the process (~85% of a core; the RSX/frame-clock
  thread is next at ~57%). Per second it issues ~168k GETs (287 MB/s, ~1.75 KB each), ~65k
  PUTs (164 MB/s, ~2.6 KB) and ~600 atomics (GETLLAR/PUTLLC). No lists. Measured with a
  throwaway rdtsc wrapper around `spu_wrch(MFC_Cmd)` (not committed); the byte rates agree with
  `SPU_DMA_RANGE=00010000-FFFFFFFF`'s `[dma-range] ... B/s` lines.
- **What a PUT cost** beyond its copy: two `spu_coh_is_reserved` calls per 128-byte line (the
  reserved-line scan before and after the copy), a POISON-DMA payload scan that read every PUT
  a second time (a print-only detector for another title: here it only ever reported 12
  ordinary PUTs into 0x40003000-0x40005000), and the GCM pushbuffer hook (below).
  Every DMA also wrote the repeat detector's shared statics (`SPU_DMA_REPEAT_LIMIT`), one cache
  line all SPU threads wrote.
- **Change** (patch `0068-spu-dma-put-fast-paths`): `spu_coh_span_reserved(ea, size)` answers the
  scan from the bitmap a byte at a time, and the line walk runs only if a line in the span is
  marked. POISON-DMA needs `SPU_POISON_DMA=1`. The repeat detector keeps its state per context in
  `mfc_engine` (a thread-local version cost ~4 ns per DMA on one thread; this costs nothing). The
  bytes moved are identical: `tools/test_spu_dma_hotpath.py` runs the real `spu_dma.h` and
  `spu_coherency.c` against a byte model and pins a digest (`86102f76477d0bbe` for the
  pre-existing script, the same before and after the change).
- **Bench** (`runtime/spu/tests/bench_spu_dma.c bench`, same host, ns per command through
  `mfc_channel_write`, coherency armed):

  | | GET 128 B | PUT 128 B | PUT 1 KiB | PUT 4 KiB | PUT 16 KiB | GET 16 KiB | GETL/PUTL 16x1 KiB | 8 threads x 128 B (aggregate) |
  |---|---|---|---|---|---|---|---|---|
  | before | 48 | 60 | 167 | 518 | 1961 | 316 | 1427 | 35.6 |
  | after | 47 | 50 | 55 | 116 | 335 | 320 | 546 | 9.7 |

- **In the game** (mixer thread, ms per second of wall time spent in MFC commands, 14 windows
  of 5 s each, rdtsc build):

  | | GET | PUT (ns each) | atomics | all DMA | mixer thread CPU |
  |---|---|---|---|---|---|
  | before | 27.1 | 55.8 (853) | 0.7 | 83.7 | 85.6%, 86.9% |
  | after | 27.5 | 33.7 (517) | 0.8 | 61.9 | 82.3%, 83.7% |
  | after, GCM hook skipped (experiment only) | 27.6 | 14.2 (218) | 0.7 | 42.5 | 83.6% |

  So about 2% of a core is saved, on the busiest thread. Arena fps (~37 in this window) and
  whole-process CPU (~211%) do not move, because the mixer paces itself to real time. No
  `identical transfers -- halting` line in any run before or after.
- **Not done, and why:**
  - **The GCM pushbuffer hook** (`gcm_note_spu_put`, libs/video/cellGcmSys.c) is now most of
    a PUT: `gcm_ea2io_range` walks the 512 `s_io_mappings` slots on every SPU PUT until a hit,
    ~300 ns per PUT, 19 ms/s on the mixer (guess: every mixer PUT misses, a full walk). It is
    outside this task's files. Follow-up task T056.
  - **Lock granularity.** `mfc_for` already skips the registry lock on its hot path (a per-context
    cached slot checked against a generation), so T027's rwlock is off the DMA path. The
    lock-line spinlock is taken only by atomics, ~600/s at ~1.2 us each: there is no contention
    to split per line.
  - **Diagnostics on the hot path.** Each DMA still tests ~25 cached `getenv` flags. A
    no-diagnostics build would save at most ~30 ns per small DMA (~0.5% of the mixer). Not worth
    restructuring every probe.
  - The legacy `runtime/spu/tests/run_tests.sh` suite does not build on Linux at the pin: compile
    errors in `runtime/platform/win32_compat.h` (no `clock_gettime`/`pthread_rwlockattr_t` without
    POSIX feature macros), and it rewrites its tracked `out_*` files. Restore them with
    `git checkout runtime/spu/tests/out_*` after a run.

### SPU codegen wins: not needed (T031, 2026-10-21)

Measured in the arena (`boot_check --scenario arena`, 20 s of `/proc/<pid>/task/*/stat`
at 100-120 s, guest ~35 fps): the whole game uses ~82% of one core; the busiest
threads are 46% and 31%, the rest under 4%. Nothing SPU-shaped is near 100%, so
lifter codegen changes (always_inline `spu_shufb`, direct calls, constant folding)
would buy nothing measurable and risk bit-exactness. Revisit when an SPU-heavy
scene (a real match with physics and audio, phase 8) puts an SPU thread near 100%.

### SPU time by category (T029, 2026-10-21)

`tools/spu_profile.sh` with the per-thread `eu-stack` sampler (perf is denied here; method in
debugging.md "Profiling"). 01.09 at `c9d339d`, the main checkout's `versions/0109/build`, boot
lock held, 27 s windows. The sampler costs nothing measurable: Single Player screen 56.25 FPS
sampled vs 56.58 unsampled (`--sampler none`), 317% host CPU in both.

| Category (share of on-CPU stacks) | Before T033 (perf, 2026-10-19, intro) | Single Player screen (`--scenario menu --warmup 75`) | Arena, driving (`--scenario arena --warmup 100`) |
|---|---:|---:|---:|
| samples | 375k | 190 | 127 |
| lifted SPU code | 0.8% | 29.5% | 52.8% |
| SPU runtime helpers | 6.6% | 46.3% | 9.4% |
| locks / spin / yield | 90.1% | 0.0% | 0.0% |
| PPU lifted | 0.2% | 4.2% | 3.1% |
| GCM / Vulkan | 0.2% | 7.4% | 20.5% |
| other | ~2% | 12.6% | 14.2% |
| host CPU | 1331% | 317% | 243% |
| guest FPS | | 56.3 | 35.4 |
| mixer PUT in window | | 1620 KB/s (105.5% of 8 ch x 48 kHz x f32) | 1620 KB/s (105.5%) |

- **The SPU thread that matters is the audio one.** One host thread runs the MultiStream DSP
  overlay (`spu_ovl_msdsp_37000`) and image `e33837bb` (it calls the overlay): 80% of a core on
  the Single Player screen, 84% in the arena, the busiest thread of the process in both. In the
  arena these two images are 63% of all on-CPU stacks (32% and 31%, inclusive). It keeps the mixer
  at real time, so it is not yet a limit, but at ~84% it is the first SPU thread that would
  become one (claude's T032 note asked to revisit at "near 100%"). Top functions: msdsp
  `0x37614`, `0x39A18`, `0x37B20`, `0x37198`; e33837bb `0x4DB0`, `0x53B8`. Candidates if T031
  (codegen, closed) is reopened.
- **Per-job image hash (new T055).** On the Single Player screen `spu_workload_dispatch_job` is
  the leaf of 28% of all on-CPU stacks (54 of 190), each on a short-lived `jc_thread`: the inlined
  `spu_workload_fingerprint` runs a byte-wise FNV-1a over the whole job image on every dispatch.
  Not seen in the arena run.
- **Differs from T031's arena measurement above** (~82% of one core in total, busiest thread
  46%). This run, on `c9d339d` (after T053's patches 0060/0061 removed the audio update thread's
  5 ms nap), shows 243% and the audio SPU thread at 84%. The stacks put that thread in lifted
  msdsp/`e33837bb` code, not in a lock or yield, but whether that code is mixing or polling a
  channel in a loop is not established (guess to check before any T031-style codegen work).
- The other busy threads are the RSX/FIFO thread (`frame_clock` -> `cellGcm_rsx_process_fifo`,
  53-54%: `rsx_vertex_remap_build`, `rsx_vertex_fetch_all`) and PPU threads (21-47%).
- Reports: `analysis/spu_profile_20261021-{135900,140513,141126}.txt` in the opus-1 worktree.
  Shares within ~5 points are sampling noise at these counts.

### SPU job fingerprint memo: no gain (T055, 2026-10-21)

T029's stack sampler showed 28% of on-CPU stacks on the Single Player screen in the inlined
byte-at-a-time FNV of `spu_workload_dispatch_job`. A memcmp-verified memo of (image, fingerprint)
removed it from the profile (SPU runtime helpers 46% to 8% of stacks) but **did not raise
fps**: 6 menu runs (`spu_profile.sh 30 --warmup 75 --scenario menu --sampler none`, memo
switchable by `SPU_FP_MEMO=0/1`) gave memo on 49.0/48.2/48.1 fps, memo off 56.2/56.3/47.6 fps
(machine shared with another agent's builds, so noisy, but never better with the memo). The
hash cost is spent on short-lived job threads that are not on the critical path; the guest
frame rate is bound by the drain/render side (GCM/VK 18%, RSX thread 63%). Patch dropped, not
merged. Lesson: a share of on-CPU stacks is not a share of the frame time.

### Unmapped SPU PUT lookup (T056, 2026-10-21)

`gcm_note_spu_put` must remain enabled: it discovers SPU-built RSX command blocks.
Previously every unmapped mixer write scanned all 512 IO mapping slots. The fix
uses two small atomic summaries, not an active-count shortcut:

- An allocation high-water mark bounds the fallback scan. It grows before a
  free slot is returned, never shrinks on unmap, and resets only when the whole
  mapping table is cleared. Init's directly assigned slot zero is included.
- A 64-bit mask covers occupied 64 MiB EA regions. Every mapping-add path
  publishes its range; unmaps may leave conservative false positives. A clear
  bit proves a miss, including for unaligned ranges and overlaps. Overflowing
  ranges keep the existing full-scan semantics, rather than gaining new matches.

The real lookup and block tracker pass 50,000 randomized comparisons against a
full-table oracle, sparse/reused/full-table cases, region edges, wide ranges and
ASan/UBSan. Both efficiency assertions fail before the fix. The source-extraction
benchmark (`external/ps3recomp/tools/test_gcm_spu_put_lookup.py --benchmark`) gave
209.6 to 2.08 ns for an eight-slot unmapped lookup on this host.

Private relinks changed only a runtime C object, not generated code. Sampled
serial-clock probes in 130 s arena runs gave hook cost ~257 ns baseline, ~33.5 ns
with the high-water mark alone, and ~21.6 ns with both summaries. Samples that
migrated CPUs or exceeded 50,000 cycles were excluded; empty clock overhead was
subtracted. At T032's ~65k PUT/s this saves about 15 ms of CPU per second, not a
measured FPS gain. Evidence: pi worktree `analysis/t056-*-boot2.log` and
`analysis/t056-regions-boot.log`; the latter reached the arena, 3721 zlib, 4488
flips, unresolved 0. With T032 also integrated, an ordinary 300 s run returned
from round end to the main menu (4810 zlib, 10904 flips, unresolved 0), without
null-read/null-write/SIGSEGV. The full gate is 100 scripts: 96 pass / 4 explicit
skips. A separate native `spu_wrch(MFC_Cmd)` timing wrapper, sampled during arena
seconds 105–125, measured **233.16 ns/PUT** (10,864 samples, 26,822,176 sampled
bytes). This is about 7% above T032's earlier hook-skipped reference of 218 ns;
that reference was not remeasured. Current hook-enabled cost was 517 ns after
T032 alone. No generated code was edited and no hooks were disabled for the
new measurement. Evidence: `analysis/t056-dma-boot.log`,
`analysis/boot_check/20261021-162115-1654613/run.log` in the pi worktree.

### Pipeline build cost: async builds not worth it (T059, 2026-10-21)

`RSX_ENGINE_PIPE_TIMES=1` (patch `pipe-times`) logs each new pipeline's translate + compile time on
the walker. Arena run (130 s, 189 pipelines): **1.8 s in total**, 10 ms on average, 65 ms at most;
the slow ones come in bursts at the loads (frames ~381 and ~2652: 30-65 ms each, the load screens
hide them) and one 25 ms build during play. Drakengard 3's off-walker builds fixed 200-450 ms
Metal compiles; Vulkan here is 10x cheaper, so the fork's async build and `VkPipelineCache` are not
taken. Revisit if a later scene shows a hitch in `[pipe-time]`.

## Video (Bink)

- BinkPS3 is statically linked game code; the three `BINKPS3_*.BIN` files are its RSX
  shaders. No HLE module involved — it works when PPU lifting, SPU jobs and RSX do.
- If intros block progress early, consider skipping them (find the movie-play call)
  rather than debugging Bink first; record any such override in `src/overrides/`.

## Network and online

- The game uses **GameSpy** (`OnlineSubsystemGameSpy`, peerchat.gamespy.com) over
  `IpDrv.TcpNetDriver`. GameSpy died in 2014, so official online is gone.
- NP imports (43): `sceNpDrmIsAvailable` (license check — must return OK),
  Manager (NP ID, online name, ticket), Basic (friends), Lookup, **Score**
  (leaderboards — psnr implements Score), **Signaling** (P2P). sys_net 22, cellNetCtl 8.
- `cellRec`, `cellVideoUpload`, `cellVideoExportUtility`: replay recording/upload —
  stub as unavailable.
- Plan: boot **offline** first — sceNp reports signed-out, sys_net with
  `PS3_NET_ONLINE` unset. Make sure the "can't connect" paths don't block menus.
- Later options: OpenSpy-style GameSpy replacement via DNS/host redirect, or LAN/direct
  IP if the engine exposes it. ps3recomp's psnr only covers NP matching, not GameSpy.
- Local split-screen (up to 4 pads) is the more valuable multiplayer goal.
- Status: not started.

## Trophies, system UI, misc

- Trophy set `NPWR00406_00`: registration works (status callback `0x683B48` stores
  `completed` at arg+4; the registration thread `0x684788` writes -1 there when done). It
  needs patch 0001: upstream's deferred completion raced that -1.
- System dialogs (cellMsgDialog, cellOskDialog for names), cellSysutil callbacks (XMB
  exit, game-exit request) — implemented upstream; watch for an unhandled callback stall.
- `PS3LOGO.DAT`, `ICON1.PAM` are XMB assets the game never reads.

## Render scale (T063)

Internal resolution is a backend feature, not an engine one: see docs/graphics-menu.md "Render scale" (patch 0081).
