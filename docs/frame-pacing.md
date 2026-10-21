# Frame clock and pacing (T012)

What the port's frame clock does, what it costs on this title, and which of Drakengard 3's
(dod3) pacing changes are worth taking. Measured 2026-10-21 on 01.09, RTX 2070 SUPER, headless
(`PS3RECOMP_VK_WINDOW=0`), with `tools/boot_check.sh --scenario arena` and
`FRAME_CLOCK_STATS=1 SARPBC_FRAME_STATS=1`.

## How it works today (`src/main.cpp`, `frame_clock`)

One host thread ticks a fractional 60 Hz deadline on the monotonic clock. Each pass it
(1) sleeps `outer_ms` (default 1; `FRAME_CLOCK_SLEEP_MS`, 0-100), (2) drains the GCM FIFO into
the Vulkan backend (`fifo`), (3) on each due vblank fires the vblank/flip callbacks and
presents (`present`). The guest's render thread and game thread run on their own host threads
and wait on GCM labels/flips the clock services. `g_frames_presented` counts presents;
`sarpbc_frame_stats_tick` logs guest frames once a second.

## Measurements

| Screen | Guest frames/s | Frame clock per 5 s |
|---|---|---|
| Main menu / Single Player | ~54 | idle about a third of gdb samples (T040 session); not re-measured with the counters |
| Arena (New Game) | 36-38 | sleep 0.3 s, **fifo 4.3 s**, present 0.1-0.8 s |

- In the arena the clock thread is **87% busy draining the FIFO** (decoding draws, uploads,
  Vulkan recording). Pacing is not the limit there: the RSX-to-Vulkan work is. A cap at 30
  would be reached with headroom only if the drain gets about 20% cheaper.
- At the menus the clock idles about a third of the time, so a frame cap there is free.
- Changing the sleep from 4 ms to 1 ms was worth +16 fps on Single Player (the guest waits
  for flips the clock only services every 4 ms) and +3 in the arena.

## What the game itself asks for

`COALESCED.INI` (`CONFIG/BATTLEBALL/PS3/COOKED/`): `bSmoothFrameRate=TRUE`,
`MinSmoothedFrameRate=22`, `MaxSmoothedFrameRate=60`, `MinDesiredFrameRate=35`,
`UseVsync=true`, `NetServerMaxTickRate=30`. So UE3 smooths between 22 and 60 fps and flips on
vsync; the 30 fps the user saw on the console comes from vsync with two vblanks per flip when
the frame misses 16.7 ms. `GetMaxTickRate` is not named in the stripped EBOOT (no string);
finding it would need a pattern search of the lift, not done.

## dod3's changes and whether they apply here

| dod3 change | Applies? | Verdict |
|---|---|---|
| Drain on every guest `usleep` kick, not only on the clock tick | Partly: the guest waits on flips and labels, which the 1 ms clock already services | Skip; re-measure if the Sleep(1) gain proves to be a latency issue again |
| Native replacement for the render thread's fence poll | Unknown here: not measured | Measure first (`HLE_BT_EVERY`, gdb samples of the render thread) |
| `UEngine::GetMaxTickRate` replaced (uncapped or fixed) | Not needed: the smoothing range 22-60 already exceeds what we reach | Only for a deliberate 30 or 60 cap, later |
| Bink ticked faster during movies | The intro movies are skipped/not on the critical path | Skip |
| Loading-screen idle spent in the async loader | Loads take ~6 s to the first textures and ~45 s to a usable menu, I/O and zlib bound | Candidate, but SPU/zlib work is where the time goes (T029) |

## Ranked changes

1. **Make the FIFO drain cheaper in the arena** (biggest lever, 87% of the clock thread):
   per-draw CPU costs in `rsx_draw_engine.c` / `rsx_vulkan_backend.c` (patches 0053-0056 took
   the obvious ones). Next suspects: descriptor writes per draw, shader/pipeline lookups,
   the texture upload path. Profile with `PS3RECOMP_VK_DRAW_TIMES=1`.
2. **Split drain and present onto two threads** if (1) stalls: the drain is not tied to the
   vblank deadline, and `vk_batch_flush` waits on the GPU while the clock cannot tick.
3. **Frame cap (30/60)** as an option (`config.toml`), implemented in the clock by letting
   `present` skip ticks, not by touching the guest's tick rate: nothing to do until the arena
   keeps up with it.
4. Re-measure `FRAME_CLOCK_SLEEP_MS` against a real window (the numbers above are headless).

Proposed follow-ups are items 1-3; none is started.

## Frame cap: opt-in, off by default (2026-10-21)

Is the original capped at 30 fps? Not established. The game's own `COALESCED.INI` asks for UE3
smoothing between 22 and 60 fps with `UseVsync=true` (no 30 cap), and a web search (GameSpot
review, Wikipedia, RPCS3 forum threads) found no frame-rate figure for the PS3 game, only a
2008 remark that split screen struggles. The earlier "30 fps cap" came from the user's memory
(2026-10-20); the user then asked for the game to be as close to the original as possible
(2026-10-21), so the default is **no cap**.

`SARPBC_FPS_CAP=<n>` (src/main.cpp `flip_cap_wait`) holds each guest flip's present back to a
deadline of whole 1/n s intervals, on the drain thread (completing flips on the vblank tick does
NOT slow the guest: it is bound by the drain, not by vsync). Arena, cap 30: 27.6 guest fps
(under the cap: the deadline wait stalls the drain, so work does not overlap); no cap: 34.1.
