# Status

Living document. Update "Resume here", the phase table and the log at the end of each
work session. Newest log entry first. Use absolute dates.

## Resume here (updated 2026-10-20)

**User priorities (2026-10-20, in order):** 1. ~~move ps3recomp to v0.16.0~~ (T043 done);
2. **now: visual glitches and bugs**; 3. then a steady 30 fps in game (the game's own cap).
Next steps for 2: the T021 "Port next" list at the top of docs/dod3-reuse.md (items 1-2 are
ported as 0048/0049; next: 5 prepared flips at their FIFO position, 7 scissored depth clears
and cropped depth copies for shadows, 8 fragment decompiler DDX/DDY/NRM/precision, 10
anisotropic filtering); ~~T038 (upside-down Loading screen)~~ (done); the `null-read,null-write` alerts a
165 s arena survey raised (boot_report, not yet looked at); the glass canisters' shards draw
opaque white (maybe correct, unverified). For 3: T040, and the dod3 pacing recipe in
dod3-reuse.md (FIFO wake on guest usleep, `GetMaxTickRate`).

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
direction). T045 is done; the 85% black border is the game's own safe-area setting (menus have it too). Real MP3 audio
plays (T007). `boot_check --pad` scripts the presses (T036). There's no Bink in 01.09.

**Last verified on `main` (fc9cdf4, 2026-10-20, `PS3_VERBOSE=0`, under the boot lock):** a 120 s
boot_check is PROGRESSING with 3513 flips; the main menu runs at **29.5 fps** (1 s windows
26.3-32.3), ~130% CPU, 28 threads. Where a menu frame's ~31 ms go, and what to try next:
subsystems.md "Menu frame rate".

**State of `main`:** 50 patch files (68 commits) on upstream `749182e` (v0.16.0, T043); every one of the
85 test scripts (ours and ps3recomp's) passes on that stack (2026-10-20, `tools/lint.py --tests`). The upstream lifter did not
change, so the lifts were kept. The big fixes of the last two days: the SPURS CreateTask race that started tasks twice
(0036, T033: ~1500% CPU to ~100%) and Vulkan draw batching with a VRAM geometry cache (0038, T040:
menu 19.8 to 29.5 fps).

**This machine (since 2026-10-19 evening):** Debian 13 container, 16 threads, 15 GB RAM, ~14 GB
free disk, RTX 2070 SUPER in a bottom slot that runs at **PCIe 2.0 x4** (~2 GB/s: per-frame
uploads and GPU round trips cost far more than usual). perf is blocked (use gdb stack sampling).
Only 01.09 is built (`versions/0109/build`, ccache off for disk space). Setup notes: T033's log.

**User plan:** 1. ~~menus~~ reached. 2. **Now: performance, a steady 30 fps in the main menu** (the game's own cap; T040, then
T043's upstream perf work). 3. The project audit (T039) was run on 2026-10-20 at the user's request.

**Desktop launch (patch 0041, task T042-wayland):** native Wayland now works on the Fedora / RX 7800 XT
host. Patch 0041 removes a 64-format limit (RADV reports 99). `./run.sh` needs no
X11 override; `SDL_VIDEODRIVER=wayland ./run.sh` explicitly selects Wayland. A
45-second window test presented 3,581 guest frames without a headless fallback;
this is not a main-menu FPS measurement. See build-linux.md "Desktop launch".

**Queue:** the board's `Priority:` lines (`tools/task.sh next`): **T040 (steady 30 fps), T043 (pin bump), T029 (profiler mixer metric), T032/T031 (SPU
DMA, codegen), T034 (callback stacks), T038 (upside-down Loading), then T020, T017, T021, T012, T009,
T018, T005, T010, T011, T013, T014. T015 (multiplayer) is **blocked** until the user has permission.
T007, T036, T037, T044 and T045 were closed on 2026-10-20. Next up for the arena: a real match
(phase 8: an exhibition with input over time, audio in the arena, frame rate there).

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
| 7 | Intro movies / main menu | **reached 2026-10-19** on 01.09 (T028; X presses via PAD_FILE); ~30 fps on 2026-10-20 (T033, T040), goal 60 |
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
