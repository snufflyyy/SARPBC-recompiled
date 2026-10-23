# Status

Living document. Update "Resume here", the phase table and the log at the end of each
work session. Newest log entry first. Use absolute dates.

## Resume here (updated 2026-10-23)

**Mini-Games fps dip fixed (user, 2026-10-23: "fix the fps slowdown when images appear in the main menu, specifically when selecting a
minigame"; T075, patches 0085-0088).** Mini-Games was a steady 15 fps, now ~38; Single Player 35 -> ~59; arena 59 steady; menus 59.
Cause: the ShaderPatching SPURS job chain (one job per draw, ~1000 a frame on that screen) was a one-core ceiling of 14,600 jobs/s
at 67 us a job, and the render thread waits for it. Per job: 46 us image hash, 19 us context memset, copies, then a host thread per
Run, then the PPU debug-store-watch hook. Method, numbers and the correction to T055: subsystems.md "ShaderPatching job chain".
**Second round (user: "fix the remaining Mini-Games fps from the FIFO drain"; T076, patch 0090): the drain was not the main limit.**
Skipping every draw bought only 6 fps; the RenderingThread was ~84% busy and a third of that was the guest's stores, still a call
into the loader's `vm_write*` (+ an out-of-line reservation check) while loads were already inline. Stores inline in the lifted header
now: **Mini-Games 31 -> 44 fps** (interleaved A/B, same binary, `PPU_SLOW_STORES=1` for the old path), arena 59.8. Needs a re-lift
(done for 01.09; the 01.02 tree at the repo root is not). New tool `tools/cpu_profile.sh`. Method, numbers, what is next (the 3 MB ring
wrap wait, `ps3_indirect_call_impl`): subsystems.md "Mini-Games, second round".

**Multiplayer is POSTPONED (user, 2026-10-23: "the server isn't open source like i assumed. just postpone the multiplayer plan"); T015 and T066-T074 are all `blocked`, nothing to do until the user provides a server.** Research below stays valid.

**Multiplayer (user, 2026-10-23: "port the custom multiplayer to our 1.09 recomp", community server unmodified, hosted
locally; permission given because the server is local):** research and plan are in [docs/multiplayer.md](docs/multiplayer.md),
tasks T066-T074 on the board under the umbrella T015. Key finding (run on 2026-10-23, sandboxed): the 01.09 client's
matchmaking is **a plain-HTTP stored-procedure web service**, `POST http://sarb.psyonix.com:80/v001/callproc.php`,
body `DB=SARPBC_Prod&Proc[]=GetOnlineVariables()&VersionCheck=ValidateVersion('00.00.0006')`, sent at boot and on Play
Online (the game then waits at "Logging in..."); the game imports no `sceNpMatching2`, so NP is only identity, friends,
presence and signaling, and RPCN may or may not be needed (decision D1, T068). The mod's `.pkg` files and the server are
not on this machine: T068 starts with asking the user. Start with **T066** (read the protocol out of the client, probe
tool) and **T067** (config-driven local redirect, two instances); they need nothing from the user.

### Earlier "Resume here" (2026-10-22)


**Graphics menu and options (user, 2026-10-22; T062-T065 done):** the Options screen has native-looking **Graphics**
(Resolution = window size, Render Scale 50-300 %, Fullscreen, VSync, Frame Rate, FPS Counter) and **Picture**
(Texture Quality, Texture Filtering, Brightness) pages, and Skip Intro on System. **Every row applies at once, no
restart** (user's standing rule, docs/graphics-menu.md "Convention: settings are live"); Skip Intro is the one
that can only act at the next launch. Built by patching the menu scripts in the player's own `TAGAME.XXX` through an
overlay (`tools/graphics_menu_patch.py`, `tools/ue3/`, `PS3_VFS_OVERLAY`, patch 0077); `docs/graphics-menu.md` has the
package format, the bridge and every address. Backend patches 0078-0084; the engine's own native values (brightness,
frame-rate cap) are written into the running game by `src/overrides/live_engine.cpp`. Unlocked fps: arena ~58 ->
~85-90, game speed verified against the match clock (docs/frame-pacing.md). Ideas not yet done:
docs/enhancements.md (safe area, language row, frame-cap choices, FXAA).

**Performance (user, 2026-10-22: "focus on performance"; T060, patches 0074/0075 + `src/main.cpp`):**
the arena went from 38-40 to **55-60 guest fps** (the 60 Hz clock), menus 55-60. Three things
overlapped the CPU and the GPU: double-buffered engine batches that submit without waiting, deferred
destruction of released images/framebuffers, the depth snapshot recorded in the batch, and a split
present polled with `rsx_vulkan_backend_present_ready()` (details and numbers: subsystems.md "Async
batches"). The GPU was busy only ~5 ms a frame; on this machine it also sits at P8/405 MHz (not
ours to change). The 30 fps goal is met with room; what is left on the CPU side is the draw
engine's vertex fetch/remap and texture hashing (dod3-reuse "Port next" 9). Verified: 330 s with
pad input through the round end and the results screen, no alerts; `tools/verify.sh` OK.

**T061 (same day, patch 0076): the FIFO drain went from ~15 to 7.4 ms a frame** with a decoded-vertex cache
(keyed by the bytes of each attribute span; 0 mismatches over 2.3M hits in `RSX_DRAW_CACHE_CHECK`), geometry ids
so the Vulkan backend skips re-hashing, and a hashed texture lookup (subsystems.md "Draw-engine CPU"). The arena
is now clock-capped at 60 fps with the clock idle over half the time. **Queue (user, 2026-10-22):** T062
unlocked render fps, T063 resolution/render scale, T064 FPS overlay (top left), T065 a native-looking
"Graphics" screen in the game's Options menu (next to System, Profile) exposing them; T015 stays blocked.


**Current work (user, 2026-10-21):** T058 is merged and verified; pi stopped
at the user's request. Prepared flips execute at their FIFO
position; the native clock claims each completed-frame flag once, rather than
count queued requests or present a pending marker twice. Both callback modes,
fourteen native-clock cases and ASan/UBSan pass. Final 300 s: results then main
menu, 4811 zlib, 12935 acknowledged flips, unresolved 0, no null-access alerts
or SIGSEGV; sampled menu/arena/results captures are intact.

T052 round-end repair and Claude's T053 audio work are integrated and verified
through results and back to the menu; the user confirms the audio sounds good.
Audio patches remain 0060–0062, lifecycle repair 0067. T032/T056 are also done:
ordinary 300 s through results/menu, full DMA PUT cost 233 ns (~7% above the
historical hook-skipped 218 ns reference). Opus-2's authored patch and clean
worktree were preserved.

Claude completed T005's loader fix (`0071-loader-toc-stubs.patch`), matching the
01.02 workaround exactly and leaving 01.09 unchanged. T009 is closed without a
lifter port: PPU code was ~6% of sampled CPU stacks, and the fork's inline-store
gate raises coherence concerns. T059 has a measured diagnostic, not a cache port:
`0070-pipe-times.patch`, 189 arena pipelines / 1.8 s total / 65 ms maximum, mostly
hidden by load screens. See subsystems.md "Pipeline build cost" before adding
async builds or `VkPipelineCache`.

**User priorities (2026-10-20):** performance and stability, in that order of work: done so
far, the pin bump (T043), the visual fixes (T051 and earlier), a steady 30+ fps (T040: Single
Player 19.5 to ~54 fps, arena ~30 to ~38, see subsystems.md "Menu frame rate") and the audit
cleanups (T047-T049, A06/A07/A11 pieces). Next: the T021 "Port next" list in docs/dod3-reuse.md
(5 prepared flips at their FIFO position, 7 scissored depth clears and cropped depth copies for
shadows, 8 fragment decompiler DDX/DDY/NRM/precision, 10 anisotropic filtering), a real match
(phase 8), frame pacing to a cap (T012), clean exit (T018, the `null-read` alerts in boot_report
come from guest teardown after SIGTERM), glass-canister shards drawing opaque white (unverified).

**To restart, start an agent (Claude Code, pi, Antigravity, ...) in the main checkout and say:**
> Read AGENTS.md, docs/status.md "Resume here" and docs/workflow.md, then take the next task
> from `tools/task.sh next`.

**No agent spawns subagents** (user, 2026-10-19). Since 2026-10-20 the user has one agent working
directly in the main checkout (`./build.sh`, `./run.sh`, commits on `main`); with several agents,
go back to one worktree each (docs/workflow.md). Paused tasks carry a `HANDOFF:` note
(`tools/task.sh show <ID>`). Before committing, run `tools/lint.py` (`--tests` when a patch or a
tool changed).

**Headline: 01.09 reaches the main menu at ~30 fps; the goal is a steady 30 fps** (user, 2026-10-20:
the game is capped at 30 fps on PS3, so the earlier 60 fps goal is dropped). The
intro is Loading, ESRB with the car, Powered by Unreal, the Psyonix logo, the safe-area screen
(needs X), then the menu: CROSS at 45 s and again at 50 s by `PAD_FILE` (T036 will make that
`boot_check --pad`). New Game now loads MP_SOCCARARENA + PYRAMID_COLLECTBOOST and keeps presenting (T037, T044),
and **the arena renders and plays** (T045: reversed-Z depth clear, then NV0039 texture copies):
clean textures, a working HUD, the car drives on throttle, its shadow is right (depth-compare
direction, and T054: the shadow map snapshot is cropped to the 512x512 texture, patch 0064). T045 is done; the 85% black border is the game's own safe-area setting (menus have it too). Real MP3 audio
plays (T007) without crackle (T053, 2026-10-21). `boot_check --pad` scripts the presses (T036). There's no Bink in 01.09.

**Last verified on `main` (9844b8e, 2026-10-21, under the boot lock):** rebuilt
01.09 Linux/Vulkan, 60 s menu smoke: 3285 zlib, 2500 acknowledged flips,
unresolved 0, no null-access alerts/SIGSEGV. The final capture is the Single
Player menu. Root `analysis/boot_check/20261021-200728-2049532/`. The preceding
300 s arena/results/return-menu verification is logged below. Frame-time
breakdowns and historical measurements: subsystems.md "Menu frame rate".

**Integrated patch stack:** 90 patch files on upstream `749182e`
(v0.16.0, T043), including T052 and Claude's later audio/shadow/port work.
Current full gate: 102 scripts, 98 passed / 4 explicit skips / 0 failures/timeouts;
the nested SDL/Vulkan suites are included (T048).
The upstream lifter did not
change, so the lifts were kept. The big fixes of the last two days: the SPURS CreateTask race that started tasks twice
(0036, T033: ~1500% CPU to ~100%) and Vulkan draw batching with a VRAM geometry cache (0038, T040:
menu 19.8 to 29.5 fps).

**This machine (since 2026-10-19 evening):** Debian 13 container, 16 threads, 15 GB RAM, ~14 GB
free disk, RTX 2070 SUPER in a bottom slot that runs at **PCIe 2.0 x4** (~2 GB/s: per-frame
uploads and GPU round trips cost far more than usual). perf is blocked (use gdb stack sampling).
Only 01.09 is built (`versions/0109/build`, ccache off for disk space). Setup notes: T033's log.

**User plan:** 1. ~~menus~~ reached. 2. **Now: performance, a steady 30 fps in the main menu** (the game's own cap; T040, then
T043's upstream perf work). 3. The project audit (T039) was run on 2026-10-20 at the user's request.

**Desktop launch (surface-format patch, task T042-wayland):** native Wayland now works on the Fedora / RX 7800 XT
host. The patch removes a 64-format limit (RADV reports 99). `./run.sh` needs no
X11 override; `SDL_VIDEODRIVER=wayland ./run.sh` explicitly selects Wayland. A
45-second window test presented 3,581 guest frames without a headless fallback;
this is not a main-menu FPS measurement. See build-linux.md "Desktop launch".

**Queue:** use the live board (`tools/task.sh next`). T058 is done. T059 was
released with a HANDOFF and has a measured non-port assessment in subsystems.md. T005 is done and T009 closed without a port. T015 (multiplayer) remains
**blocked** until the user has permission. Phase 8 still needs a real exhibition
match with input over time, arena audio and frame-rate measurement.

## Phases

| # | Phase | State |
|---|---|---|
| 0 | Docs, git, submodule, `.gitignore` | done 2026-10-18 |
| 1 | Extract PKG to `vfs/` (`tools/extract.sh`) | done 2026-10-18 |
| 2 | Decrypt EBOOT.BIN + SPUJOBS.SPRX (`tools/decrypt.sh`) | done 2026-10-18 |
| 3 | Load + triage ELF, record imports/SPU/NP facts | done 2026-10-18 (see game-profile.md) |
| 4 | Project skeleton from the template, first lift + build on Linux | done 2026-10-18 |
| 5 | Boot to first file opens / first HLE gaps | done 2026-10-18 |
| 6 | Loading screen draws (`LOADSCREEN` FPO/VPO) | done 2026-10-18 — "Loading..." through Vulkan |
| 7 | Intro movies / main menu | **reached 2026-10-19** on 01.09 (T028; X presses via PAD_FILE); 30+ fps on 2026-10-20 (T033, T040) |
| 8 | Offline match in an arena, with input and audio | — |
| 9 | Polish: saves, trophies, perf, split-screen; online later | — |

## Decisions

- **2026-10-18 — toolkit: middle path.** Pin upstream `sp00nznet/ps3recomp`; port features
  from the Drakengard 3 fork (`soyjxck/ps3recomp`) as patches when needed. See
  `patches/ps3recomp/README.md`.
- **2026-10-18 — decryption via RPCS3 CLI**, isolated config, scripted in `tools/decrypt.sh`.
- **2026-10-18 — target version: official update 01.09** (3 extra arenas, replays,
  fixes; Sony CDN, verified). Staged in `versions/0109/` while the first agent wave
  finishes on 01.02, then swapped in. HLE/NID-level fixes carry over; anything
  address-specific is redone. See game-profile.md "Versions and updates".
- **2026-10-18 — offline play first; multiplayer last and blocked** until the user has
  permission from the community server operators (T015).
- **2026-10-18 — platforms: Linux primary with Vulkan; Windows later with D3D12.** CMake
  turns `PS3RECOMP_RSX_VULKAN` on for Linux; `src/main.cpp` selects Vulkan → D3D12 →
  Metal → null. Linux-only conveniences need a Windows branch.

## Open questions

- What are SPU images 0, 3-5, 8-10 (unidentified by strings)? (T010)
- Does the game block on `sceNpDrmIsAvailable` or NP sign-in when offline? So far
  `sceNpDrmIsAvailable` on SPUJOBS.SPRX passes and the menus come up offline (T014).
- How does 01.09 save (cellSaveData `FixedSave2`/`ListLoad2`)? Untested end to end (T017).
- Answered: MultiStream needs a `flashMP3.pic` (served natively, subsystems.md Audio); the
  POSIX boot scaffold gets this UE3 title to the menus on Linux.

## Log

### 2026-10-23: Mini-Games, the render thread (T076, claude)

- Skip-all-draws A/B: 35 -> ~41 fps, so the drain is ~15% of the frame. `tools/cpu_profile.sh` (new, no perf needed) and `PS3_FTRACE`:
  RenderingThread 84% busy, main blocked on it, drain 16.5 ms of a 21 ms frame. 33% of the render thread was `vm_write32/64` +
  `spu_coh_is_reserved`. Patch 0090: inline stores in the lifter's header (`vm_store_span`, `spu_coh_bitmap`), relift + rebuild.
- Interleaved A/B x3: 31.1/31.4/30.9 (`PPU_SLOW_STORES=1`) vs 43.8/44.1/43.7 fps. Arena 130 s: 59.8 fps, no alerts, picture intact.
  `tools/test_ppu_inline_stores.py` (3 mutants fail it). Left: ring-wrap `Sleep(1)` x11, `ps3_indirect_call_impl`, `-O1`.

### 2026-10-23: Mini-Games fps dip (T075, claude)

- Reproduced with `boot_check --scenario single` (+ `SARPBC_FRAME_STATS`): 59 fps main menu, ~35 Single Player, 15 on Mini-Games.
  `FRAME_CLOCK_STATS` said the drain was idle (sleep 3.7 s of 5), so the guest was waiting: gdb/eu-stack on the render thread
  put it in the `appSleep` poll `func_000E2660` (waits for the RHI's SPURS job chain, docs/unreal-engine-3.md). `PS3_POLLTOP=5`
  names the poll sites; `PS3_USLEEP_SCALE=RenderingThread:0` and `FRAME_CLOCK_SLEEP_MS=0` changed nothing.
- Timers around `jc_run_one_job` showed the ShaderPatching chain at 14,600 jobs/s x 67 us = one core; jobs per frame went
  160 -> 420 -> 975 as fps went 59 -> 35 -> 15. Phase timers in `spu_run_spurs_job` and `spu_workload_dispatch_job` split the 67 us.
- Four generic patches, each measured: 0085 fingerprint memo (46 us), 0086 pooled job contexts (19 + 3 + 4 + 5 us), 0087 walker
  lingers 1 ms (17,000 thread starts a second), 0088 PPU debug-store-watch gate (21% of the render thread). Mini-Games 15 -> 18
  (after 0085/0086) -> 28 (0087) -> 33/38 (0088), Single Player 35 -> 59. `tools/test_spu_job_hotpath.py`; lint --tests green.
- Verified: single route 38 fps; 130 s arena 59 fps steady, no SIGSEGV/null alerts, final capture (Scavenger mini-game: HUD,
  boost pickups, car, shadow) intact.

### 2026-10-23: multiplayer research and plan (T015, T066-T074, claude)

- Read the mod's public setup guide, RPCN's source (v1.12.1: TLS :31313, UDP :3657, protocol 34, no per-game code,
  `CreateMissing=true`), and the 01.09 client: EBOOT strings (`https://sarb.psyonix.com/v001/callproc.php`, request
  templates, native `PsyWebServer_X`), packages (`PsyNet`, `OnlineSubsystemPS3`, `ProjectX` online classes, version
  strings `00.00.0006`/`00.01.0004`, so the mod's "1.04" is probably our 01.09), imports (no Matching2/cellHttp/cellSsl).
- Two sandboxed boots with `PS3_NET_ONLINE=1 PS3_NET_SANDBOX=1 PS3_NET_TRACE=1` (listener on 127.0.0.1:80): the exact
  request, plain HTTP on port 80, sent at boot and on Play Online; empty 200 leaves "Logging in...". Details and
  commands: docs/multiplayer.md 4.3 and 11.
- T015 became the umbrella (renamed, `blocked`, do not claim); docs/workflow.md's rule now allows servers the user hosts
  locally. New docs: multiplayer.md, multiplayer-protocol.md, multiplayer-mod.md. No code changed.

### 2026-10-22: settings go live; project audit (claude)

Frame Rate applies instantly (the cap is written into the running game, `live_engine.cpp`); every settings row is live.
Audit: pyflakes now also covers `tools/ue3/` (unused imports/variables and two dead helpers removed), stale tracked
files removed (`specs/IMPACT_LATEST.md`, `patches/experimental/`: every hunk had landed or been dropped), stale
comments and this file's top section brought up to date. Not done: the idle agent worktrees under `.worktrees/`
(4.1 GB, all merged and clean) were left for the user (they are other agents' directories).

### 2026-10-22: draw-engine CPU: vertex cache, geometry ids (T061, claude)

- Drain per frame 15 to 7.4 ms (arena 130 s): decoded-vertex cache in `rsx_draw_engine.c` (0076), `geometry_hint`
  so the Vulkan backend finds geometry by id, texture lookup index, 4-lane content hash. Verified with
  `RSX_DRAW_CACHE_CHECK` / `PS3RECOMP_VK_GEO_CHECK` (0 mismatches), a new `test_vertex_cache`, lint --tests 98/0,
  330 s through the results screen. Added tasks T062-T065 (unlocked fps, resolution, FPS overlay, Options > Graphics).

### 2026-10-22: async Vulkan batches and split present (T060, claude)

- Arena 38-40 to 55-60 fps (menus 55-60). Stack sampling (gdb, `bt 30`) showed the frame-clock thread
  46% in `vk_submit_and_wait`; `PS3RECOMP_VK_BATCH_STATS` 41 s of GPU waits per 130 s. Patch 0074: two
  batch contexts (submit without waiting), graveyard for released images/framebuffers, depth snapshot
  recorded in the batch (waits 41 s to 1.4 s, 39 to 48 fps). Patch 0075 + `src/main.cpp`: split present
  polled for completion (present time 1.5 s to 0.13 s per 5 s, 48 to 57 fps), and `PS3RECOMP_VK_GPU_TIMES`
  (GPU busy 5 ms/frame, idle 77%). `SARPBC_SPLIT_PRESENT=0`, `PS3RECOMP_VK_ASYNC=0` restore the old paths.
- Also committed pi's pending 0073 (`PS3_NET_HOSTMAP`/`PS3_NET_SANDBOX`, T015 groundwork; T015 stays blocked).
- Environment finding: the GPU stays at P8, SM/memory 405 MHz, PCIe Gen 1 x4 during the run; `nvidia-smi -lgc` is
  not permitted. Documented in subsystems.md, nothing changed.

### 2026-10-21: shadow fix, ports, queue emptied (T054/T021/T005/T009/T031/T055/T057/T059, claude)

- Car shadow fixed (0064): the shadow-map depth snapshot is cropped to the 512x512 texture instead of the canvas-sized zeta. Ported fp DDX/DDY/NRM (0065), Vulkan anisotropic filtering (0066), `ppu_loader` TOC-stub split (0071, relift.sh uses it), diagnostics 0063 (pass-dump alpha) and 0070 (pipeline build times).
- No frame cap by default (no source confirms 30 fps; COALESCED.INI says smoothing 22-60 with vsync): `SARPBC_FPS_CAP=<n>` opts in (docs/frame-pacing.md).
- Closed on measurements, no code: T009 (PPU lifted code ~6% of stacks), T031, T055 (hash memo gave no fps), T057 (already in the pin), T059 (pipelines 1.8 s total).
- Main (7e79f3c+) verified after merging pi's T052/T056/T058 and opus's T029/T032: arena 130 s, 35.4 fps, car and HUD fine. The board has only T015 (blocked: multiplayer needs the user's permission). Next ideas: a real match (phase 8), the audio mixer thread at ~85% of a core in the arena (T029 finding), safe-area black border.

### 2026-10-21: FIFO prepared flips and exactly-once presents (T058, pi)

Adapted MIT fork `6eb35c0` / `6cba82c`, preserving authorship, as
`0072-flip-at-fifo-position.patch`. Marker/cursor execution records the flip;
Immediate acknowledges once and retains the optional PPU-side park callback.
No guest callbacks from the locked drain, no new backend policy or frame cap.
The native clock also requires and consumes its completed-frame flag after a
drain: request counts alone can present early, and leaving the flag set presents
again. Fourteen deterministic native-clock cases plus FIFO/ack/position/resync
checks pass, including both callback modes and ASan/UBSan. Full gate: 102 scripts,
98 passed / 4 explicit skips / 0 failures/timeouts.

Final source `f693403`, pi `analysis/boot_check/20261021-195941-1970586/`, 300 s:
results then main menu at 205.2 s, 4811 zlib, 12935 acknowledged flips, unresolved
0, no null-read/null-write/SIGSEGV. Sampled logos/menu/arena/HUD/shadow/results
are intact. The unfixed clock accumulated thousands of duplicate presents;
the final steady span has 10620 presents / 10621 acks (one in flight), not an
accumulating excess. No FPS gain claimed. Latest-main diagnostic/loader work
and the T009 measured non-port decision were merged normally, not overwritten.

Integrated/pushed as `9844b8e` with numbered patch
`0072-flip-at-fifo-position.patch`; main was rebuilt and passed the 60 s Single
Player menu smoke (3285 zlib, 2500 flips, unresolved 0, no NULL/SIGSEGV), root
`analysis/boot_check/20261021-200728-2049532/`. T059 released with a handoff to
preserve its existing diagnostic and measured assessment. Pi stops here as asked.

### 2026-10-21: DMA/GCM optimizations combined and verified (T032/T056, pi)

Merged opus-2's clean, verified `e79f8e0` normally; no changes to that worktree or
its DMA implementation. Added a conservative GCM EA-region mask and mapping
allocation high-water mark. All 100 scripts: 96 passed, 4 explicit skips. The
ordinary `f66a315` release completed 300 s through round end/results/menu (4810
zlib, 10904 flips, unresolved 0, no null-access alerts/SIGSEGV).

Actual sampled GCM hook: ~257 to ~21.6 ns. Separate full-DMA native-boundary
probe, arena seconds 105–125: **233.16 ns/PUT**, 10,864 samples, versus T032's
517 ns before T056. This is ~7% above the earlier hook-disabled 218 ns
reference, not a new reference measurement. No FPS improvement claimed.
See docs/subsystems.md "Unmapped SPU PUT lookup" for method and evidence.

### 2026-10-21: round-end repair integrated with latest main (T052, pi)

Patch `0067-coherent-taskset-lifecycle.patch` makes both SPURS task-exit bitsets and PPU bitset read/modify/write
coherent. Old shared bits could resurrect completed island tasks, creating extra
queue completions; the PPU then consumed an older range count while a newer job
rewrote its table. The malformed negative range caused the later NULL reads and
MultiStream assert. Baseline: 11942 task creations but 11944 dispatches; ordinary
fixed release: exactly 23405 creations/dispatches/returns. No title-specific
scheduler policy or audio/NULL workaround was added.

The ordinary Linux/Vulkan 01.09 build passes 300 s through Scavenger Failed and
back to the main menu: pi `analysis/boot_check/20261021-025732-3095073/`, 4811
zlib, 10939 flips, unresolved 0, no null-read/null-write/SIGSEGV, including exit.
The guarded build independently passes another 300 s. Synthetic regression:
419 checks, also ASan/UBSan; full gate: 97 scripts, 93 passed, 4 explicitly report
skips, no failures/timeouts. See debugging.md for the failed exit-only experiment
and the two-race proof. GitHub audio commit `c9d339d` is now merged into
`pi/work`, with audio code and patches unchanged. The combined ordinary build
also passes 300 s (`analysis/boot_check/20261021-035615-3491134/`): 4811 zlib,
11033 flips, unresolved 0, no null-read/null-write/SIGSEGV, exact task counts.
Two steady 40 s AUDIO_WAV windows have zero silent blocks, gaps and block-edge
clicks. Combined gate: 98 scripts, 94 passed, 4 explicit skips; 419 lifecycle
checks under sanitizers plus Claude's qbyte/fast-float regressions pass.
The user confirms the audio works well. After Claude exhausted usage, pi also
merged latest main `37f8f00` (shadow crop, aniso, decompiler, profiling and opt-in
frame cap preserved) and verified another ordinary 300 s round-end/menu run:
`analysis/boot_check/20261021-154006-1336355/`, 4810 zlib, 11062 flips, unresolved 0,
no null-access alerts or SIGSEGV. The merge helper numbers the lifecycle patch.

### 2026-10-21: SPU DMA fast paths (T032, opus-2)
- In the arena one SPU issues all MFC DMA: the MultiStream mixer, ~168k GETs + ~65k PUTs/s. A PUT cost 853 ns (per-line reserved scans, an always-on POISON-DMA payload scan, a shared repeat-detector line); patch 0068-spu-dma-put-fast-paths makes it 517 ns, mixer DMA time 84 -> 62 ms/s, bytes identical (`tools/test_spu_dma_hotpath.py`). Most of what is left is the GCM pushbuffer hook's 512-slot walk: follow-up T056. Numbers: subsystems.md "MFC DMA fast paths".

### 2026-10-21: SPU profiler works without perf (T029, opus-1)
- `tools/spu_profile.sh` falls back to per-thread `eu-stack` samples when perf cannot record (this container), adds `--scenario/--pad/--sampler/--interval` and a mixer PUT rate restricted to the sample window. No measurable cost (56.25 vs 56.58 fps). Single Player: lifted SPU 30%, SPU runtime 46% (28% is a per-job FNV hash of the whole job image: new T055); arena: lifted SPU 53%, the audio SPU thread (MultiStream DSP overlay + `e33837bb`) at 84% of a core. Numbers: subsystems.md "SPU time by category (T029)".

### 2026-10-21: audio crackle fixed (T053, claude)
- The crackle was 66% silent blocks (the game wrote every 2nd-3rd ring slot because its mixer round ran 8-15 ms instead of 5.3 ms). Fixed by a faster audio SPU path (native float, lean LS, x86 `rotqby` family: patch 0060), the update thread's 5 ms nap scaled to 0 (patch 0061 + `src/overrides/audio_pacing.cpp`): 0.0% silent blocks and 0-1 block-edge clicks over 42-65 s menu/arena windows, was 860 clicks. Menu 55 fps, arena 38 fps. Details, numbers and `tools/audio_wav_report.py`: subsystems.md "Audio crackle". Not heard by an agent (no sound device here): the user should confirm by ear.

### 2026-10-20: attribute-major vertex fetch (0056, claude)
- `rsx_vertex_fetch_all` replaces the per-vertex `fetch_one` loop in the draw engine; byte-identical on 6000 random plans (test_vertex_fetch_plan). Arena 36-39 -> ~38 (small: the arena's next costs are texture hashing and the remap build). Optimization series total (01.09, this machine, 2026-10-20): Single Player 19.5 -> ~54 fps, arena ~30 -> ~38.

### 2026-10-20: clears and snapshots join the batch (0055, claude)
- Counting `vk_submit_and_wait` call sites over 100 s of menus: batch flushes 9.9k, depth clears 6.0k, colour snapshots 3.0k, uploads 0.7k. Clears and colour snapshots now record into the open batch (`vk_batch_begin_cmds`). Arena 34 -> ~37 fps, menus 53 -> 54; arena capture correct.

### 2026-10-20: frame clock drains every 1 ms (claude)
- `frame_clock`'s outer `Sleep(4)` became `Sleep(1)` (src/main.cpp, `FRAME_CLOCK_SLEEP_MS`). The guest waits on labels the drain writes, so the 4 ms grain was latency: Single Player 36.8 -> 53.1 fps (min 48), arena 31 -> 33-36. The game is not capped at 30 by itself here, it runs as fast as the drain lets it; pacing to a cap is T012.

### 2026-10-20: vertex decode inlined (0054, claude)
- `rsx_vertex_decode_element` with the type switch hoisted and inlined into `rsx_vertex_fetch_one`, bit-identical on 2M random cases. Single Player ~32 -> ~37 fps, arena ~31. The frame-clock thread now idles in a third of samples, so the remaining limit is the guest side and the game's own 30 fps cap.

### 2026-10-20: shared render pass, 30 fps in menus and arena (T040, claude)
- Patch 0053: consecutive draws into one framebuffer share a Vulkan render pass (a pass per draw cost ~33 us, 400 draws a frame). Single Player 19.5 -> ~32 fps, arena ~30; captures render identically. After it the frame-clock thread idles ~30% of samples, so the remaining dips are guest-side or GPU/CPU overlap; vertex decode is the next CPU cost. Details in subsystems.md "Menu frame rate".

### 2026-10-20: reliable verification (T048, claude)
- `tools/lint.py --tests` now includes the 3 nested SDL/Vulkan suites, keeps per-script logs in `.cache/lint-tests/`, reports skips/timeouts, no longer uses `git checkout` to undo test side effects (saves/restores the one known fixture's bytes; reports anything else), and `--strict` fails on skips or missing tools. Doc lint works on a clean clone (git-ignored paths accepted). `tools/test_lint.py` proves it. 94 scripts: 90 pass, 4 skip (Metal, MP3 encoder, PPU lift tool) on this host.

### 2026-10-20: predictable tooling (T049, claude)
- `apply_patches.sh --ensure` verifies tree identity in a scratch worktree, refuses a dirty runtime, and `build.sh` holds a per-checkout lock; `task.sh` serializes board writes and checks owners. Fixtures: `tools/test_build.py`, `tools/test_task.py`. Real submodule verified in 0.45 s, no rewrite. Note: `build.sh` now fails on a dirty `external/ps3recomp` (override `SARPBC_ALLOW_DIRTY_RUNTIME=1`).

### 2026-10-20: loading-screen root cause fixed (T051, pi)
- The game selects PNG, not BMP, and requests `outputMode=1` (bottom-to-top).
  `cellPngDec` ignored it. The decoder now validates/reports row order and selects
  source rows per handle, preserving ARGB swizzle and padded pitch without global stb
  flip state. The entire shader-length viewport heuristic is removed; no replacement
  classifier or backend special case is needed. Corrected rationale and evidence:
  [t038-review.md](t038-review.md), subsystems.md Graphics.
- Exported separate codec and viewport-regression patches; historical 0050 is fully
  undone and must not be offered upstream. All 88 discovered scripts and three explicit
  nested suites return zero. Synthetic PNG coverage: 72 color/order/pitch cases plus
  invalid-mode atomicity at heights 1/2/3. Both PNG and renderer fixtures pass ASan+UBSan;
  the renderer regression covers NOP equivalence, unrelated two-instruction programs,
  fixed/guest paths, both scale signs and non-centered offsets.
- Corrected-stack Release boot, 120 s: upright Loading and tutorial arena/car/HUD,
  3729 zlib requests, 2575 flips, unresolved 0. An additional 55 s staged capture verifies
  upright ESRB/car, Psyonix/Unreal logos, profile screen, main and Single Player menus.
  Main checkout also rebuilt successfully through `./build.sh`; its fresh 20 s smoke
  is PROGRESSING (3279 zlib requests, 442 flips, unresolved 0). No new FPS or
  Windows/macOS claim. No game data or generated lift is committed.

### 2026-10-20: Antigravity loading-screen fix reviewed (T050, pi)
- T038 was already merged as `ba70ca3`; no second implementation merge is needed.
  A fresh 120 s combined-stack boot confirms upright Loading text and tutorial arena/HUD:
  3726 zlib requests, 2630 flips, unresolved 0. Four distinct dumps in the final 10 s
  show that the report's STALLED label is not a rendering freeze in this run.
- The source-only neutral-backend probe exposes a generic correctness issue: adding a NOP
  to an otherwise identical VP changes the bound Y transform despite byte-identical HLSL.
  T051 tracks replacement of the length-only predicate, regression coverage and correction
  of the projection-dependent compiler explanation. Implementation is retained unchanged;
  Linux/Vulkan symptom verified, general upstream acceptance not recommended yet.
  Evidence and reproduction: [t038-review.md](t038-review.md). No new FPS/platform claim.

### 2026-10-20: critical native boundary fixes (T047, pi)
- Native Edge-zlib now checks full guest spans, decoded-size arithmetic and counter
  alignment; rejects unfinished/incorrect-length streams without publishing completion;
  streams skipped bytes through fixed scratch space; and propagates event-delivery errors.
  VFS setup uses allocated canonical paths and owned strings, preserving long overrides
  without truncation. Audit A01/A02 remediation: [project-audit.md](project-audit.md).
- Private 01.09 Release build passes. All 87 discovered scripts and three explicit nested
  SDL/Vulkan suites return zero; 16 zlib + 5 VFS tests also pass under ASan/UBSan. A 120 s
  boot renders the tutorial arena (3717 zlib requests, none rejected; 2463 flips, unresolved
  0). Antigravity's independently completed patch 0050 is retained unchanged and integrated
  into the private build; the combined stack passes all 87 scripts again and a 30 s smoke
  (3279 zlib requests, 717 flips, unresolved 0). No FPS or Windows claim is made.

### 2026-10-20: Loading screen orientation fixed (T038, antigravity)
- Fixed the "Loading..." splash screen rendering upside down. UE3's `LOADSCREEN.VPO` is an unprojected 2-instruction passthrough shader (`MOV HPOS, v0; MOV TEX0, v8`) with 0 constants. On RSX with negative viewport scale (`scale[1] = -360`), `pos.y = -1` mapped to top (`yw = 720`, row 0 of texture) and `pos.y = +1` to bottom (`yw = 0`). In Vulkan, glslang's `shader.setInvertY(true)` inverted this unprojected quad vertically, drawing "Loading..." upside down.
- Patch `0050-loadscreen-passthrough-orientation`: `rsx_draw_engine.c` flips `xf[1]` and `xf[5]` for 2-instruction passthrough vertex programs without projection matrices. Verified: `frame_first_lit.png` shows upright "Loading...", while all subsequent passes (ESRB car, Psyonix logo, safe-area screen, menus, HUD, and 3D arena) remain 100% upright without regression. All 85 lint tests pass.

### 2026-10-20: maintainability audit (T046, pi)
- Read-only implementation review: keep generated lifts / title overrides / exported runtime
  patches as the architecture. Findings and cleanup sequence: [project-audit.md](project-audit.md).
  Priorities: native zlib/VFS boundary checks, complete and non-mutating test discovery,
  reliable patch/build provenance, then explicit startup/configuration. Main fast lint passes;
  all 85 discovered test scripts return zero, as do three nested SDL/Vulkan scripts omitted
  by the current runner. Private-worktree lint initially reports 10 missing local-data paths
  (not source failures); clean-clone verification needs to stop requiring ignored game trees.
  No runtime code changed, no new boot/FPS claim, and T038 graphics work was left alone.

### 2026-10-20 (session 10): pin bumped to v0.16.0 (T043); two Sonnet subagents (T010, T021)
- claude: T043: the patch stack rebased onto upstream v0.16.0 (`749182e`): 65 commits in 47
  files, renumbered (old -> new table and what was merged or dropped: patches README). A/B on
  the same pad script and screen (Single Player, 110 s, `PS3_VERBOSE=0`): old stack 18.6 fps
  median (min 17.7), new 19.6 (min 18.2): no regression. (T040's 29.5 was the main menu; this
  recipe now lands one screen further.) Frame clock per 5 s: FIFO drain ~2.8 s, present ~1.5 s
  (mostly the batch flush waiting for the GPU), sleep ~0.7 s.
- At the user's request two Sonnet 5.5 subagents ran research-only tasks: T010 (every SPU image
  identified, coverage gaps classified, `tools/spu_coverage.py`) and T021 (the full dod3/fork
  inventory against v0.16.0, ranked "Port next" list in dod3-reuse.md).

### 2026-10-20 (session 10): arena textures and HUD fixed (NV0039); target is 30 fps, not 60
- claude: T045: the arena's noisy textures and garbage HUD were stale VRAM. The game streams
  textures into local memory with NV0039 copies on subchannel 1 (libgcm's default binding), which
  the pin routed to NV4097: no copy ran and the words hit the blend registers. Patch
  `0046-nv0039-copy-engine` (+ test) performs the copies and keeps 2D-engine methods out of the
  draw engine's 3D state; `0045-pass-dump-textures` dumps decoded textures (how it was found).
  The arena now has clean textures, the right HUD, and the car drives. subsystems.md "Arena
  textures: NV0039 copies on subchannel 1".
- claude: T045: the car's shadow was a dark square: RSX compares depth textures `depth OP
  reference`, upstream used ARB_shadow's `reference OP depth`. Patch `0047-shadow-compare-direction`.
- User: the game is limited to 30 fps normally; the menu goal becomes a steady 30 fps (AGENTS.md,
  T040, subsystems.md updated). The menu is already at ~29.5 fps, so T040 is now about the dips
  (1 s windows down to 26) rather than throughput.

### 2026-10-20 (session 9, cont.): New Game loads and renders the arena; audio plays
- pi (merged by claude after pi ran out of usage): T037: the arena hang had two SPURS causes.
  The taskset attribute dropped its 64-bit argument (collision tasks polled EA 0), and the HLE's
  synthetic job-chain completion broadcast (`data2=0`) told the slab service thread
  (`func_008FFCB8`) to exit, so collision tasks waited forever for slabs. Patches T037-1/2/3
  (+ `src/overrides/spurs_config.cpp`: `SPURS_JC_DONE_EVENTS=0`). T044: GCM callbacks stay on
  the interrupt worker (the render thread had run the flip handler on itself and deadlocked).
  T007: MultiStream's second DSP bank (filter) is now lifted too; real MP3 audio reaches
  PulseAudio. T036: `boot_check --pad`. Verified (claude, 120 s, `--pad
  'cross@40*4/5,cross@70,r2:120@90,cross@100'`): MP_SOCCARARENA + PYRAMID_COLLECTBOOST load,
  6025 flips, frames presented to the end, unresolved 0. The arena frame was black.
- claude: T045: the arena was black because UE3 here uses reversed-Z (clears depth with
  `ZSTENCIL_CLEAR_VALUE=0`, draws GEQUAL) and the draw engine read a zero clear value as 1.0.
  Patch `0044-zstencil-clear-zero`; the arena now draws (subsystems.md "Arena renders black").
  Still wrong: noisy textures on some surfaces, HUD garbage, no car in view (T045 HANDOFF).

### 2026-10-20 (session 9, cont.): project audit (T039)
- User asked for an audit of the whole project, to keep it clean and uniform as it grows.
  Found and fixed: `tools/hle_coverage.py` crashed with its defaults (the NID table moved to the
  build dir); 4 upstream tests no longer built on our stack (0004, 0015, 0019 and our own 0038
  changed what they extract or link: each fixed inside its patch, 73/73 test scripts pass); ~25
  stale `T###` patch names in docs; the patch README (stale candidate list, a row out of order);
  shellcheck warnings; 5 scripts not executable; a stamp-read error in `build.sh`; "Resume here"
  out of date. No game data in git or its history. Closed T024, T025, T035, T041 (done-when met);
  new T043: upstream is at v0.16.0 (117 commits; 32 of our 40 files replay cleanly).
- New `tools/lint.py` (`--tests`) runs these checks in seconds; `merge_to_main.sh` runs it and
  now renames merged patches in the docs as well as the README.

### 2026-10-20 (session 9, cont.): menu fps 19.8 -> 29.2
- T042 (pi, user-requested Wayland fix): patch 0041 dynamically enumerates surface
  formats and bounds retries on `VK_INCOMPLETE`. The desktop's RADV Wayland list
  has 99 entries; the old 64-entry cap silently dropped the window. GCC/Clang
  regressions, Valgrind and the full patch stack pass; 01.09 rebuilt and native
  Wayland presented 3,581 guest frames in 45 s; X11 passed with 2,074 in 30 s.
  Captured Guest1 profile screen and compositor buffer attachments confirm
  presentation. Both test games were stopped. Sanitizer runtimes are missing
  locally. Details and commands: build-linux.md "Desktop launch".
- T040 (claude): Vulkan draw batching, geometry content cache in BAR memory, constant reuse, no
  per-frame readback on the engine path (patch T040). Merged with pi's uncommitted work (pi out of
  usage): T024 centre-texel present readback (claude finished its test runner), T029 frame telemetry,
  T041 desktop launcher. From now on the user wants work done in the main checkout.

### 2026-10-19 (session 9): new machine; SPURS tasks ran twice
- New machine, fresh clone (claude): base PKG extracted, 01.09 downloaded from Sony and verified,
  decrypted (hashes as in game-profile.md), both versions relifted. Debian needed gawk,
  libopengl0, libsdl2-dev, glslang-dev, ccache and gdb (T033 log).
- T033 (claude): the PhysX pile-up was a CreateTask race (duplicate task starts). Patch
  `T033-spurs-task-runs-once`; numbers in subsystems.md "SPURS tasks started twice". The worker
  pool isn't needed for this. User goal: 60 fps in the main menu.

### 2026-10-19 (session 8): agents the user starts, no subagents
- T030 follow-up: private index for reservation-holder lookup, with no context ABI or guest
  semantic changes. Clang/GCC registry tests and ASan/UBSan pass. Four controlled 01.09 boots
  on the new Ryzen 7 3700X/RTX 2070 SUPER host produced 588–589 versus 320–374 flips in 60 s.
  CPU and mixer throughput did not improve. Faster progress also increased host threads to
  961–997 versus 263–270, so T033's worker pool remains critical. See subsystems.md.
- T029 fallback fix: containers can deny perf counters even with paranoid=2. The profiler now
  keeps /proc samples 57 s apart for a 60 s run, even after immediate or partial recorder
  failure. Two mocked regressions fail on the old code and pass on the fix. Four real runs
  validate the fallback. The remaining T029 work is a mixer metric in the report.
- User: running many subagents used too much usage. The user now starts each agent themselves
  (Claude Code, pi, Antigravity), one or several, and they share the task board; no agent
  spawns subagents and there is no coordinator. `docs/agents-workflow.md` became
  [workflow.md](workflow.md) (harness-neutral procedure, merging, pause/resume, history);
  `docs/agent-brief.md` was removed. `tools/task.sh` gained `Priority:` lines and `next`, and
  `list` shows claim owners and last activity. `tools/agent_setup.sh <agent>` creates
  `.worktrees/<agent>`. The new `tools/merge_to_main.sh` lets each agent merge its own work
  (merge lock, patch renumbering, board commit; tested in a throwaway clone). `Model:` lines
  dropped; the audit is task T039. GEMINI.md points other harnesses at AGENTS.md.
- The repo is on GitHub: `origin` = https://github.com/snufflyyy/SARPBC-recompiled (history checked
  first: no game data, binaries or keys). The task board moved from `tasks/` to `docs/tasks/`.
  `merge_to_main.sh` now pushes `main` to `origin` after each merge; agent branches stay local.
- Root `./build.sh` / `./run.sh` (01.09 default, `--version 0102`). Verified: both versions build
  and link, a no-op 01.09 build takes ~1 s, a submodule reset to the bare pin is detected and
  re-patched, and `./run.sh` boots 01.09 headless (20 s smoke run). A first draft ran
  `git submodule update`, which detached the submodule at the pin and broke the link: see
  pipeline.md "Build and run".
- Checked before cleanup: all 24 worktree branches have 0 commits beyond `main`, and every
  ps3recomp commit in them is in the 36-patch stack (T003's overlay lift landed rebased, as 0008).
  T028 closed (menus reached; follow-up is T037), and its main-menu capture was copied to
  `captures/boot_check/20261019-111110-397302-T028-main-menu/`. The worktrees under
  `.claude/worktrees/` (~22 GB of build trees and run logs) are safe to delete:
  `git worktree remove --force --force <dir>` then `git branch -d worktree-agent-*`.

### 2026-10-19 (session 7): main menu reached; SPU bottleneck located
- Resumed with 5 agents (limit raised from 3). Merged T025 (0028/0031/0032 + SPU `-march`), T027
  (0029), T026 (0030), T030 (0033), T024 (0034-0036 + gcm_config.cpp), T028 (docs), T029 (profiler).
- **01.09 reached the main menu** (T028, PAD_FILE X presses). Boots now run one at a time
  (`lock boot`): five parallel boots put the 16-core host at load ~160 and skewed every timing.
- Profiler: `spu_lockline_lock` is 83% of samples. PhysX tasks pile up as host threads (T033).
- User decisions: SPU perf (easy wins) after the menus, then an audit; Sonnet 5.5 for scoped
  tasks and Haiku 5.5 for read-only searches (AGENTS.md).

### 2026-10-18 (session 5, later) — first wave merged
- Merged: **T001** (patch 0005: sys_memory reuses freed ranges; UE3 ran the bump allocator
  out → OOM on 01.02 and NULL-buffer zlib loops on 01.09), **T002** (0004: general
  `sys_prx_load_module`; SPUJOBS loads; its 2 SPURS jobs lifted by `tools/lift_prx_jobs.py`),
  **T003** (0007/0008: real cellOvis overlay table; SPU pipeline lifts overlay images),
  **T004** (0003 + docs/hle-coverage.md: every import named and graded), **T016** (0006:
  SPU function finder stops lifting .rodata of section-stripped images). The coordinator
  rebased 0008 onto 0006 (merged seed filter).
- HLE NID table is now generated per build dir (no shared ppu_hle_nids.cpp), so worktrees
  with different patch sets link.
- **SPU: 15/15 images + 2 SPUJOBS jobs registered on both versions.**
- **01.09 boot now:** past PhysX init (no overlay-table error). Stalls at 4–5 s on three owned
  gaps: `cellSpursQueuePopBody` (T019), MultiStream's firmware `flashMP3.pic` → event flag
  `0x01372000` (T007), cellVoice InitEx/CreateNotifyEventQueue/SetNotifyEventQueue (T020).
- User directive: reuse Drakengard 3's port as much as possible → T021 (inventory + generic
  ports); running agents told to start from dod3's code in their areas.

### 2026-10-18 (session 5) — parallel agents, 01.09
- First agent wave started: T001, T002, T003, T004, T006. **T006 done and merged**:
  `tools/boot_check.sh` (headless boot report, version aware, kills only its own game).
- Target switched to **01.09** (user decision): downloaded from Sony's update server
  (verified), overlaid on the base, decrypted with the RAP, lifted (5.79M lines) and built
  in `versions/0109/`. Scripts take version dirs (VFS_DIR, GAME_DIR, OUT_DIR, BUILD_DIR).
- **01.09 first boot:** it asks cellGame for its install and was told "disc game
  BLES00000". Patch 0002 (game type from PARAM.SFO CATEGORY) plus `main.cpp` calling
  `cellGame_init_from_paramsfo()` fix that. It now opens 12 packages through
  MAINMENU.XXX at 1.6 s, then re-issues the same 8 Edge zlib requests ~9,000 times each
  into NULL+offset buffers (0x00010000...). Most likely the sys_memory "never reuses
  freed ranges" bug T001 found and patched (T001 is verifying on 01.09).
- Boot is not deterministic on 01.02 (1 run in 6 went white and hit FATAL 0x373), and
  the runtime ignores SIGTERM (boot_check escalates to SIGKILL).

### 2026-10-18 (session 4) — first boot
- Build deps installed by the user (SDL2-devel, vulkan-headers, glslang-devel); `/home`
  now has 173 GB free. `ps3recomp_host` passes every Vulkan scene (draw, tex, shader, rtt,
  mrt, depthtex, cube) on RADV / RX 7800 XT with guest programs on.
- **Lift bloat found and fixed:** linker TOC-switch stubs (4,242 of them in two runs) were
  folded into the preceding function, so each was lifted as a tail-entry wrapper
  running to the end of the run. `tools/split_toc_stubs.py` gives each stub its own
  function: 27.2M → 7.57M lines, 1.6 GB → 442 MB, lift 45 s. Full build 8 min 38 s, binary 385 MB.
- **Linux VM bug fixed in `src/main.cpp`:** the template's `calloc` guest memory is not
  page-aligned, so every `vm_commit` mprotect failed and `sys_memory_allocate` returned
  ENOMEM (allocator spun on NULL). Now a 4 GB-aligned `mmap` (upstream template and
  boot_main have the same bug — upstream candidate).
- First boot gets through CRT/TLS, sysmodules, GCM/videoout, SPURS, NP, trophies,
  PS3TOC/INI/INT, splash BMPs, global shader cache, RenderingThread, and **draws the
  game's own "Loading..." screen** (captured to `captures/`).
- SPU: 14/15 embedded images lifted and registered (`--allow-partial`). The Edge zlib task
  is dispatched and runs.
- **`_cellSpursLFQueuePushBody` (0x8A85674D) has no HLE upstream** → `src/overrides/edgezlib.cpp`
  services Edge zlib requests natively (inflate + event flag). This title passes no
  work-to-do counter, so each request sets the flag itself. Packages now load.
- **Trophy race fixed (patch 0001):** upstream delivered `PROCESSING_COMPLETE` through
  the sysutil poll, which raced the game's "-1 = done" write and hung "Registering Trophy
  Information" at 0% in ~2 of 3 runs. Now synchronous, as on firmware.
- Set up parallel work: task board + claims (`tools/task.sh`), per-agent worktrees
  (`tools/agent_setup.sh`), shared ccache, flock locks; docs/agents-workflow.md.

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
