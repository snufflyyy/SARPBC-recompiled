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
- Save data: the EBOOT imports **no** cellSaveData or cellGame — saves likely go through
  raw `sys_fs` into a path the engine builds (verify with `PS3_FSLOG`). Save icons ship in
  `SARB/BINARIES/PS3/SAVE/`. Status: not started.

## Graphics (RSX → Vulkan)

- Game uses libgcm directly (UE3 PS3RHI). ps3recomp: cellGcmSys + FIFO walker + NV4097
  draw engine + Vulkan backend running guest programs.
- Expected issues: flip/vblank pacing (game smooths to 60 fps, vsync on), labels/reports
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
  *Update 2026-10-19 (T024, second session):* the `0xD494C` park was cause 2; with 0024
  (chain re-walk) and the relift (0028) no park goes unpatched. Park addresses move from
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
- **PrepareFlip returns the buffer id (T024, patch 0034).** The user handler
  `func_000DC390` takes the flip id from the low 16 bits of the 0xEB00 user command's data
  (stored at `0x0123CDB0`; `0xFF` = none) and calls `cellGcmSetFlipImmediate` with it. That
  data is the return value of `cellGcmSetPrepareFlip`, which the RHI writes into its command
  stream. The pin returned `CELL_OK` (0) and flipped on the spot, so the game prepared 0/1
  alternately but every flip showed buffer 0 (108 of 108). Now PrepareFlip returns the id and
  does not flip; FlipImmediate alternates 0/1. Part of fork 0049 (6eb35c0); its FIFO marker
  and no-op FlipImmediate are not ported, because the park release needs FlipImmediate to
  call the flip handler. `GCM_PREPARE_FLIPS_NOW=1` restores the old behaviour.
- **Flip handler `func_000DC144` (01.09).** Bumps a counter at `0x01295428`; if the pending
  count at `0x01295460` is non-zero it decrements it, takes the park slot from a 2-entry table
  at `0x01295430` (index `0x01295458`, toggled each time; it waits for the slot with
  `sys_timer_usleep` while it is empty), converts it with `func_00F8C340` and writes
  `JUMP (park+4)` there. So each delivered flip releases at most one park, and extra calls
  with nothing pending are harmless.
- **Ring recycle (T024, patch 0035).** The RHI's command buffer is ctx `0x0F800000`,
  `begin 0x40000000`, `end 0x402FF000` (3 MB), with the runtime's buffer-full callback (OPD
  `0x0F800010`). The game fills it to exactly `end` once per lap, then calls that callback
  (`cellGcm_fifo_recycle`). The drain thread took `current == end` for an overrun and recycled
  first ("recycled the title's own ring"), racing the callback; one boot (`20261019-110645`,
  intr thread off) then never submitted again and stayed on "Loading...". Patch 0036: no
  drain-side recycle while the callback is the runtime's (boot `20261019-111716`: 0 such
  recycles, PROGRESSING). Before that, patch 0035: the drain-side recycle teleported `get`
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

Goal (user): 60 fps in the main menu. After T033 the game uses about one core, so the limit is
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

Changes (patches 0039 by pi, 0040):
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
| main after 0038 (pi's baseline, dumps on, verbose) | main menu | 19.8 |
| before T040 | Choose Profile | ~23 |
| + batching | Choose Profile | 27.2 |
| + no present readback, `PS3_VERBOSE=0` | Choose Profile | ~30 |
| + geometry cache + constant reuse | Choose Profile | 32.5 |
| merged with T024/T029/T041 | **main menu** | **29.2** (1 s windows 26-32) |

Main menu recipe: `PAD_FILE` with CROSS for 3 polls at 45 s and at 50 s; measure from ~75 s.
Where the frame goes now (Choose Profile, ~31 ms): ~18 ms CPU in the FIFO drain (vertex
fetch/decode `rsx_vertex_fetch_one`, `eng_texture_content_hash` on texture binds, `sink_end`),
~8 ms waiting on the GPU (batch flushes forced by depth/stencil clears and present), ~4.6 ms
idle in `Sleep(4)`. Next: record clears into the batch, overlap GPU with CPU (double-buffered
submissions instead of waiting), and cut the per-draw CPU work in the draw engine.

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
- Patch `0046-zstencil-clear-zero`: a zero clear value clears to 0. The nv40
  reset `0xFFFFFF00` that `rsx_dispatch_init` seeds still gives 1.0 to titles
  that never set the register. After it the pre-pass writes depth (0..0.017)
  and the arena draws (stadium, floor, walls). The D3D12 path,
  `rsx_live_draw.c:7591`, has the same `!zs ? 1.0f` and is not patched yet.

**Still wrong after the fix** (what T045 has left): some surfaces sample noisy
textures (the yellow wall panels, the floor grid band: maybe a texture format,
swizzle or mip issue, not investigated). The HUD rectangles (top centre, top
right, boost meter bottom right) are still garbage. The frame has a black
border (maybe the safe-area setting). No car is visible from the camera.

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
- **Open: the mixer is too slow for real time.** One mixer cycle = one wait on `0x01372000`;
  each full cycle PUTs one 8 KB block (8 ch x 256 x float) into the cellAudio port
  (`SPU_DMA_RANGE=58000000-58200000`, PUT from SPU pc 0x095D0). Real time is 187.5 blocks/s
  = 1.536 MB/s. Measured (01.09, Ryzen 7 5700X, `SPURS_EF_STATS=1`): **75 cycles/s, 410 KB/s
  (27% of real time)**; built with `-DCMAKE_C_FLAGS=-msse4.1`: 120 cycles/s, 660 KB/s (43%).
  `perf` (default build): 37% of all samples in the out-of-line `spu_shufb` byte loop (the
  pshufb path needs `__SSE4_1__`, which our default x86-64 build does not define), ~17% in
  the scalar SPU float helpers (`spu_fa`/`spu_fs`/`spu__fma_any`; upstream vectorises them
  for NEON only), 28% in the lifted i3dl2/para_eq code (0x37614, 0x37198, 0x39A18, 0x37B20),
  16% in the mixer itself. The i3dl2 hot loop (0x37478-0x37974) is optimised SPU code (comb/
  allpass delay taps), not dod3's -O0 biquads, so dod3's `msdsp_hooks.c` addresses do not
  apply. Cheapest wins, both generic: build the SPU sources with SSE4.1 (or
  `-march=x86-64-v2`), and an SSE2/AVX version of the NEON float fast path in
  `runtime/spu/spu_helpers.h`. Until then real audio would stutter.
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
- **cellAudio on Linux (patch `0023-audio-pacing-devflash-sig-region`):** the POSIX mixing
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
  2,547,400 nonzero samples, peak 0.955703 and no nonfinite values. Output quality is
  not yet verified at real time: observed silent blocks and underruns need a quiet
  gameplay measurement. The older speed measurements above predate later SPURS fixes.

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
- **ps3recomp patches:** `0016-dod3-cellpad-sdl2-port.patch` contains Drakengard 3's
  13 libs/input commits (soyjxck, MIT, authors kept): an SDL pad thread, pads by instance
  id, rumble held, `cellPad_set_host_input`, host kind, PAD_NO_HOST.
  `0017-cellpad-racing-fixes.patch` adds our fixes: a half-pulled trigger no longer
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
  `cellPad_set_host_input` (patch 0016) and is merged with any real pad. The run
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
  - Rumble: `SetActDirect` goes to `SDL_GameControllerRumble` (patches 0016/0017; the
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
  start of their data segment). Patch `0028-spu-seed-ctors-dtors` seeds every
  `.ctors/.dtors/.init_array/.fini_array` word, and for stripped images finds lists by their
  `-1 ... 0` framing. A relift of 01.09 with it: 15/15 registered, complete, every ctor/dtor
  entry lifted (checked against functions.json). Merged as patch 0028; **verified at run time**
  on main 171c84d (01.09 relifted, no `SPU_INTERP_UNLIFTED`): 0 "unlifted" lines in a 60 s
  boot_check. Unit test: `tools/test_spu_find_functions_ctors.py` (patch
  `0031-spu-ctor-dtor-seed-test`). PhysX still logs `HALT-ASSERT heqi pc=0x24884
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
  - `spu_fa/fs/fm/fma/fms/fnms` got an SSE2 fast path (patch `0032-spu-sse2-float-helpers`, a
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
- **SPUJOBS.SPRX loads (T002, 2026-10-18).** ps3recomp patch `0004-sys-prx-load-module`
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
    Patch `0007-cellovis-overlay-table.patch` implements both real functions: size = highest
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
  - **Lifting it** (patch `0008-spu-overlay-lift.patch`): only one overlay holds code, so the
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
- **SPURS Queue (T019, patch `0015-spurs-queue-ppu.patch`, `libs/spurs/cellSpursQueue.c`).**
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
- **Fix** (patch `0038-spurs-task-runs-once`): CreateTask marks the task running
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
  `spurs_line_committed` calls `spurs_queue_line_committed`, which patch 0015 added
  to libs/spurs/cellSpursQueue.c, and the test does not compile that file. All 9 ctest tests
  (`-DPS3RECOMP_BUILD_TESTS=ON`) and `tools/test_spu_context_registries.py` pass.

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
