# Status

Living document. Update the phase table, "Next steps" and the log at the end of each
work session. Newest log entry first. Use absolute dates.

## Resume here (paused 2026-10-19 for usage)

**Priority (user): get 01.09 into the menus.** Every agent slot goes to the boot until then.
At most **5** agents (raised from 3 on 2026-10-19).

**Headline:** T022 reached the **legal/ESRB screen with a 3D car rendered** on 01.09 by
combining three fixes (`PROGRESSING | last open TEXTURES.TFC@6.1s | flips 106`, 90 s,
`SPU_INTERP_UNLIFTED=1`). Two of them are merged; the third (GCM) exists in two overlapping
forms that still need reconciling. Nobody has booted `main` as merged yet.

**State of `main`:** 27 ps3recomp patches (`tools/apply_patches.sh` -> 45 commits on 39a3629).
- 0024 (T022): SPURS job chains re-walk and resume, and a never-notified guard waits 200 ms.
  Guard 0x0133AA80 itself was a red herring (an idle service chain on its own thread).
- `src/overrides/gcm_inject_base.cpp` (T022): moves the GCM window to 0x1FF00000. The game's
  256 MB raw reservation at 0x000DFA68 lands at 0x20000000, on top of the GCM labels.
- 0025-0027 (T024): GCM user-command queue, pump fast exit, and the watchdog no longer
  skipping jump-to-itself parks (`GCM_PARK_GRACE_MS`, `GCM_PARK_LOG`, opt-in `GCM_INTR_THREAD`).
- 0023 (T007): MultiStream DSP overlay; audio no longer blocks the boot.
- Also merged today: 0016-0017 (controls), 0018-0022 (fork generic fixes).

**Resume plan (in this order):**
1. **T025, merge + relift:** merge branch `worktree-agent-a4cc29237e98a2e6f`. It patches the SPU
   finder so it seeds `.ctors/.dtors`; PhysX's "unlifted LS 0x20180" is a static constructor.
   Renumber its patch to 0028, `tools/apply_patches.sh`, then relift both versions
   (`tools/relift.sh`, and with `GAME_DIR=versions/0109/game OUT_DIR=versions/0109`). Boot
   without `SPU_INTERP_UNLIFTED`. Its other half (x86 SIMD speed) is still open.
2. **T024, resume:** reconcile `patches/experimental/T022-esrb-experiment.diff` hunk (1)
   ("never skip a park") with patch 0027's 50 ms grace. T022 saw the flip-handler park released
   only at the next HLE call, which comes after the grace. Try `GCM_INTR_THREAD=1` or
   `GCM_PARK_GRACE_MS` large. Default whatever works for SARPBC in `src/overrides/gcm_config.cpp`.
3. **T027:** writer-preferring rwlocks on Linux (experiment hunk 2). Without it the ESRB screen
   stops after 8-25 s.
4. Then: get from ESRB to the intro movies and main menu (new task). Open leads: PhysX
   `HALT-ASSERT heqi pc=0x24884` and spinning on `GETLLAR 0x0133B880` (T022 notes); T026
   (per-thread guest callback stacks: all callbacks share 0xCFFE0000, unsafe with
   `GCM_INTR_THREAD`).

Steps 1-3 can run as 3 parallel agents (Touches don't overlap). A boot check after merging all
three is the coordinator's job.

**Branches not merged:** `worktree-agent-a4cc29237e98a2e6f` (T025 WIP, see step 1). All other
agent branches are merged; their worktrees under `.claude/worktrees/` can be deleted.

**After the menus, by priority:** T007 rest (silent audio, mixer at 27% of real time), T008
follow-ups (windowed key/rumble check), T020 rest, T017 (saves), T021 rest, T012, T009, T018,
T005, T010, T011, T013, T014. T015 multiplayer stays **blocked** (user permission needed).

**To restart:** see docs/agents-workflow.md "Pausing and resuming"; spawn agents with
docs/agent-brief.md. Before building `main`: `tools/apply_patches.sh`, then reconfigure CMake.

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
| 7 | Intro movies / main menu | in progress: packages load, then a stall (T001) |
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

## Next steps

The work is split into tasks on the board: `tools/task.sh list` (protocol:
[agents-workflow.md](agents-workflow.md)). Highest value first:

1. **T001** — find and fix the stall after package loading (the boot frontier).
2. **T002** — `sys_prx_load_module`/`start_module` are unresolved: SPUJOBS.SPRX (Edge
   Geometry jobs) never loads.
3. **T003** — PhysX: `cellOvis` overlay table ("PhysX: Error allocating memory for overlay
   table: 0 0") and SPU image #7 (overlapping PT_LOADs, not lifted).
4. **T004** — HLE coverage audit: which of the 274 imports have no handler, plus the 17 NIDs
   the database cannot name.
5. **T005** — upstream the TOC-stub split into ps3recomp's loader (a patch).

## Open questions

- What are SPU images 0, 3–5, 8–10 (unidentified by strings)?
- Does MultiStream need the firmware MP3 decoder like Drakengard 3 did?
- Does the game block on `sceNpDrmIsAvailable` or NP sign-in when offline? (So far
  `sceNpDrmIsAvailable` on SPUJOBS.SPRX passes; `sceNpManager` status unknown.)
- How are saves written (no cellSaveData import — raw sys_fs?)
- Does the upstream POSIX boot scaffold get a UE3-sized title to `main` on Linux?

## Log

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
