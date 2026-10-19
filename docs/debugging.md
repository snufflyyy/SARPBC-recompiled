# Debugging and triage

How to find out why the recompiled game hangs, crashes or draws wrong. The complete list
of runtime env vars is generated upstream in `external/ps3recomp/docs/DIAGNOSTICS.md`
(several hundred, many title-specific); this page lists the ones that pay off first.

## Common first-boot failures

| Symptom | Likely cause | Action |
|---|---|---|
| `[ppu] unresolved indirect call -> 0x39800000` | Import trampoline executed raw: lift lacked `--hle-stubs`, or `ppu_hle_nids.cpp` not built | Relift with `--hle-stubs`; regenerate NID table; reconfigure CMake |
| `unresolved indirect call -> <other addr>` | Function missing from function list, or a corrupt pointer (often an HLE returned a bad value) | Check if addr is inside `.text` → add as seed; else `PS3_HLE_PTRCHECK=1` |
| `Unimplemented NID 0x... in module ...` | HLE missing | `nid_database.py --lookup`; add a bridge in `src/stubs.cpp` or patch upstream module |
| `[HOTREAD] spinning on 0xADDR` | Guest polling memory nobody writes: SPU job, GCM label, lock | Find the writer (SPU job? RSX report? another thread?) |
| Hang with no output | Thread waiting on event flag/queue/cond that never signals | `PS3_EVQSTAT`, `PS3_HLE_TRACE`, debug console; check SPURS/GCM first |
| Crash in game code right after an HLE call | Wrong struct layout / endianness in an HLE return | Compare against SDK docs/RPCS3 behaviour; check `be_t<>` use |
| Assert text from engine then halt | UE3 `appErrorf`/check failure | Read the message (log it), work back from the asserted condition |

## Env vars worth knowing

| Var | Use |
|---|---|
| `PS3_VERBOSE=0` | Quiet logging. Verbose logging with stderr redirected can slow the game massively |
| `PS3_HLE_TRACE`, `PS3_HLE_ARGS`, `PS3_HLE_UNRESOLVED` | Trace HLE calls / arguments / unresolved NIDs |
| `PS3_HLE_PTRCHECK=1` | Catch HLE returning host pointers into guest |
| `PS3_FSLOG=1` (+ `_READS`, `_BT`) | Log every file open/read — first thing to run on this title |
| `PS3_HDD0_ROOT` / `PS3_VFS_ROOT` | Host dirs for `/dev_hdd0` / `/dev_bdvd` |
| `PS3_CALLTRACE*`, `PPU_SPINBT`, `PPU_VCALL_BT` | Call tracing, spin backtraces, bad virtual-call backtraces |
| `PPU_RWATCH` / `PPU_WWATCH` (+ `_LEN`) | Watch guest reads/writes of an address — find who writes a hot-read word |
| `PS3_EVQSTAT`, `PS3_LWMUTEX_TRACE` | Event-queue and lwmutex state |
| `SPU_DUMP_MISS=<dir>` | Dump SPU images that have no lifted match |
| `PS3_NO_AUDIO`, `SDL_AUDIODRIVER=dummy` | Remove audio from the equation |
| `PAD_SCRIPT="frame:mask,..."` | Scripted input for unattended runs |
| `PS3RECOMP_VK_DUMP=<path>` + `_EVERY` | Save presented frames to check rendering headlessly |

Verify a variable still exists in the pinned `DIAGNOSTICS.md` before relying on it.

## Tools

- `tools/show_func.py`, `callgraph.py` (upstream): view a lifted function / call graph
  for a guest address.
- Ghidra with the PS3 loader on `game/EBOOT.elf` (`tools/ghidra_analyze.py`,
  `ghidra_names.py` upstream) — names you assign can be fed back to the lifter via
  `--names`. Keep our Ghidra project out of git (it contains game code).
- RPCS3 (user's machine) as an oracle: same title, compare logs of HLE calls, thread
  creation, file opens. `tools/rpcs3_probe/` upstream automates some of this.
- Debug console (`DEBUG_CONSOLE.md` upstream) to query a running instance.
- `gdb`/`lldb` on a RelWithDebInfo build: lifted functions are named by guest address,
  so a host backtrace maps straight back to the EBOOT.

## Workflow

1. Reproduce with the shortest command; save the exact env + command in the finding.
2. Narrow to the first wrong thing (first unresolved call, first missing file, first
   spinning thread) — later errors are usually consequences.
3. Fix at the right layer: lifter bug → upstream patch; HLE gap → upstream module patch;
   true game quirk → `src/overrides/`.
4. Write down the cause and the fix in the relevant doc and in [status.md](status.md).

## Recipes that worked on this title (2026-10-18)

**Headless run with a frame capture** (no window opens on the desktop):
```bash
PS3RECOMP_VK_WINDOW=0 SDL_AUDIODRIVER=dummy PS3_FSLOG=1 \
PS3RECOMP_VK_DUMP=captures/frame.ppm PS3RECOMP_VK_DUMP_EVERY=120 \
timeout -k 5 -s TERM 60 tools/run.sh > analysis/run.log 2>&1
```
- The runtime catches SIGINT once the game is running, so use `timeout -s TERM -k 5`.
- **Never `pkill -f build/sarpbc`.** It matches the invoking shell's own command line and
  kills it (exit 144). `pkill -x sarpbc` works but kills every agent's instance, so in
  parallel work only kill the PID your own `timeout` started.
- View a dump: `python3 tools/ppm2png.py captures/frame.ppm`, then open the PNG with the
  Read tool. It also prints how many sampled pixels are non-black.

**Filter the log.** A run writes 15–20k lines. Drop the per-frame noise first:
```bash
grep -v -E '^\s+(r[0-9]|rawstk|ARG)|timer_usleep\(30 us\)|opendir|CLEAR_SURFACE|SetFlipImmediate|SetPrepareFlip|GET_REPORT|label write|usercmd|sys_memory\] allocate|LWM-|DRAW_ARRAYS|port_send' analysis/run.log
```

**Count what a log line hides.** Several runtime messages print only their first few
occurrences: `[edgezlib] #n` shows requests 0–3 only (the total is in the atexit
`[edgezlib] N requests` line, which a TERM kill skips), and `[null-read]` stops after a
handful. "Only 4 zlib requests" was this limit, not a stall. For memory, count
`grep -c 'sys_memory\] allocate('` against `grep -c 'sys_memory\] free('`; a failed
allocation prints `allocate -> ENOMEM (<KB> in use)` (with the T001 patch).

**Every thread's guest stack** (lifted functions are named `func_<guest addr>`):
```bash
timeout 120 gdb -p <pid> -batch -ex 'set pagination off' -ex 'thread apply all bt 14' > analysis/stacks.txt
```
`ptrace_scope` is 0 here, so attaching works without sudo.

**Which HLE calls a stuck loop makes:** `PS3_HLE_TRACE=<N>` logs the first N calls as
`[HLETRACE] nid=... lr=...`. Name the NIDs from `analysis/imports_named.json`, then read
the lifted loop around the `lr` (`grep -n 'ctx->lr = 0x<lr>' src/recomp/*.cpp`).

**Read a guest function:** `awk '/^void func_<ADDR>\(/,/^}/' src/recomp/ppu_recomp_*.cpp`.
Resolve an OPD (callbacks, thread entries) to its code address by reading the first word
at the OPD in `game/EBOOT.elf`.

## boot_check: how far did the boot get?

One command instead of the recipes above. It runs the game headless, samples it while
it runs, stops **only the game it started**, and prints a report whose first line is a
summary you can paste into a task note:
```bash
tools/boot_check.sh 60                 # 60 s run, full report (~70 lines)
tools/boot_check.sh 60 --quiet         # just the summary line
tools/boot_check.sh 60 --gdb           # + every guest thread's stack at the end
tools/boot_check.sh 60 --version 0109  # the staged 01.09 build (versions/0109/{build,game,vfs})
BUILD_DIR=... GAME_DIR=... VFS_DIR=... tools/boot_check.sh 60   # same variables as tools/run.sh
tools/boot_report.py report analysis/run9.log       # report on any old log (no times/frames)
grep -v -E "$(tools/boot_report.py noise)" run.log  # the noise filter it uses
```
Example summary (01.02, 2026-10-18):
`boot_check 2026-10-18 23:19 v01.02 ccee305 60s: STALLED since 5.1s (frames still presented) | last open STARTUP_INT.XXX@3.6s | pkgs 10 (ENGINE last) | zlib 4 | dumps 47 lit 47 distinct 1 | flips 1460 | threads 8/5 alive | unresolved 4 | alerts physx-error,null-write,null-read,io-failure`

- **Verdict:** `PROGRESSING` if the last 10 s before the stop had a new file open, Edge
  zlib request, thread, unresolved NID or a never-seen log line (digits folded, so a
  repeat with new numbers is not new); `STALLED since Ns` otherwise (N = last new
  activity); `HUNG` if the log did not grow at all; `EXITED`/`CRASHED at Ns` if the game
  ended on its own. Periodic housekeeping (`recycled the title's own ring`, SPU task
  `sleeping Ns`) does not count as progress.
- **Report sections:** final-10 s deltas, packages in first-open order with times, last
  file opened, Edge zlib count, missing files (`open FAIL` / `stat ENOENT`), frames
  (dumps, non-black by the `ppm2png.py` rule, distinct images, when the image changed),
  threads (created/returned), unresolved NIDs named from `analysis/imports_named.json`
  (for a staged version, `versions/V/analysis/imports_named.json`),
  first occurrence of each alert (null read/write, IO Failure, HOTREAD, PhysX error,
  unresolved call, ...), the last 20 distinct non-noise lines, and with `--gdb` one line
  per guest thread: guest name (log `hosttid=` matched to the gdb LWP), innermost
  `func_` frames, and the host function it waits in.
- **Files:** `analysis/boot_check/<id>/` (run.log, timeline.jsonl, frames.jsonl, meta.txt,
  gdb.txt, report.txt), `captures/boot_check/<id>/frame_{first_lit,last_lit,last}.png`, and
  a copy of the latest report at `analysis/boot_report.txt` (with two runs in one worktree
  the later finisher wins; each run's own copy is in its directory). The last 5 runs are
  kept (`--keep N`).
- **Defaults:** `PS3RECOMP_VK_WINDOW=0 SDL_AUDIODRIVER=dummy PS3_FSLOG=1 SARPBC_ZLIB_TRACE=1`,
  a dump every 60th presented frame (`--every N`), plus run.sh's
  `PS3RECOMP_VK_GUEST_PROGRAMS=1`. Anything set in the environment wins.
  `SARPBC_ZLIB_TRACE=1` matters: without it `src/overrides/edgezlib.cpp` logs only
  requests #0-3 and prints its total only at a clean exit. A plain `tools/run.sh` log
  therefore shows "4 zlib requests" while ~1,500 are serviced in the first 10 s. Relative `BUILD_DIR`/`GAME_DIR`/`VFS_DIR` that do not exist
  from the current directory resolve against the main checkout, where `versions/` lives.
- **Killing:** it starts `timeout -k 5 -s TERM <secs+30> build/sarpbc ...` and records the
  child PID; it signals that PID only while `/proc/<pid>/stat` still names its own
  `timeout` as parent (so PID reuse can't hit another agent's game). Verified by running two
  boot_checks and a separately started game at once (2026-10-18): each stopped only its
  own game.
- **The runtime ignores SIGTERM, not just SIGINT:** the log keeps growing for the whole
  grace period after a TERM. boot_check therefore sends SIGKILL after 3 s and measures the
  final window up to the TERM, not the KILL.
- **Run-to-run variance:** the first-open order of the `COOKEDPS3/*.XXX` packages changes
  between runs (CORE is always first; ENGINE was 2nd in one run, 10th in another), and the
  timings stretch about 2x when two games run at once. Compare the set and the stall, not
  the order.
- **What it shows on 01.02 (2026-10-18, 6 runs):** the boot is **not deterministic**.
  - Usual outcome (5 of 6): all packages open by ~2 s, ~1,500 zlib requests, the second
    round of opens ends with STARTUP_INT at ~4-10 s. Then come `null-write`/`null-read`
    from `func_005F8E38`/`func_006C78F0` and `IO Failure detected`, and nothing new after
    that. The "Loading..." frame stays static (1 distinct image). With `--gdb`, main,
    PoolThread, AsyncIOSystem and RenderingThread all sit in `func_006C61F0` ->
    `sys_timer_usleep` (polling loops); both spu_printf_handlers sit in
    `sys_event_queue_receive`.
  - Once (1 of 6): the screen went white at ~15 s (1,568 zlib requests). The game then
    aborted at 36 s with `[ppu] FATAL: stuck calling 0x00000373 (2000 times)` (exit
    code 3). That is a virtual call on a bogus object: the log's `CHAIN` line shows
    obj=0x00030004 with a NULL vtable pointer, so the "method" is the word at guest
    address 0 (0x373). Callers were `func_010F64A0`/`func_010E7E90`, and the main thread
    was the caller.
- **First 01.09 run (`--version 0109`, build of 2026-10-18 23:27):** stalls at ~1 s with a
  black screen. It looks for its files under `/dev_hdd0/game/BLES00000/USRDIR/UNREALENGINE3/`
  (`open FAIL .../TAGAME/PS3TOC.TXT`) instead of `NPUB30035/USRDIR/SARB/`, then hits
  null reads/writes in `func_000FF944`. There is one SPU dispatch MISS
  (fp=0x00E729804474449A), and `_sys_spu_printf_initialize` (0x45FE2FCE) is unresolved.

## Hangs found so far, and their causes

| Symptom | Cause | Fix |
|---|---|---|
| Allocator loops: `sys_memory allocate(...)` with no `-> addr`, NULL writes/calls | Guest VM from `calloc` is not page-aligned on Linux, so `vm_commit` mprotect fails | 4 GB-aligned `mmap` in `src/main.cpp` |
| "Registering Trophy Information" stuck at 0% (intermittent) | Deferred `PROCESSING_COMPLETE` overwrote the game's -1 "done" marker | patch 0001 |
| PoolThread `EventFlagWait BLOCKED ... flagEA=0x01DC8E00` after opening `CORE.XXX` | `_cellSpursLFQueuePushBody` missing, so Edge zlib never got work | `src/overrides/edgezlib.cpp` |
| `[spu_workload] async dispatch MISS fp=0x4100F6EDD2441719` | SPU images not lifted | SPU step in `tools/relift.sh` |
| After `ENGINE.XXX`: last `sys_memory allocate` near `0x4FFF0000` gets no `-> addr`, then `[null-write] guest wrote16 0x4F to 0x00000000 by guest-fn=0x005F8E38` (the UTF-16 text "OOM 4064...", UE3's out-of-memory message formatted into a NULL buffer) and `IO Failure detected` | ps3recomp's `sys_memory_allocate` was a one-way bump pointer over `0x40000000`–`0x50000000`; `sys_memory_free` never gave the range back. UE3 frees and re-asks for 64 KB pages all through loading (641 allocations, ~261 MB requested in total, while ~69 MB is live) | `patches/ps3recomp/T001-sys-memory-reuse-freed-ranges.patch` (range table, first fit). Runtime-level, no guest addresses |
| **01.09**, same cause: after MAINMENU, Edge zlib spins (295,228 requests in 45 s, the same 8 repeated) with output EAs `0x00010000`, `0x00030000`, ... (NULL + offset: the destination buffers' allocation failed), then null reads in `func_00B585F0` | as above | the T001 patch. Verified 2026-10-18: 3,147 zlib requests, none below `0x01000000`, 838 allocations / 324 frees, boot reaches `GUIDCACHE.XXX`, MultiStream, SaveData and PhysX threads |
| After `MAINMENU.XXX` (01.02 and 01.09): `PhysX: Cannot load SPURS programs. ... Error allocating memory for overlay table: 0 1 ... Cannot run without SPURS.`, then `sys_prx_exitspawn_with_level() - no-op` (the game is quitting) and NULL reads in `0x006E73E0`/`0x006D3A88` (01.02) during teardown | `cellOvisGetOverlayTableSize` HLE returns `CELL_OVIS_ERROR_NOT_INITIALIZED` (0x80410701); the game uses the result as a size, hence `allocate(size=0x80420000)` twice just before the message. Caller (01.02, around `0x00224F94`–`0x00225010`): loops over 10 SPU ELFs, skips an ELF whose size is 0 or `0x80410402`, else allocates size+0x84 and calls `cellOvisInitializeOverlayTable` | T003 (cellOvis). A local test that returned `0x80410402` for every ELF got PhysX through init on both versions (next row) |
| Past PhysX (reached only with that local cellOvis test, 2026-10-18): frames stop; the game thread loops on a 100 ms event wait (01.02: q=7, `func_000D6300` lr `0x000D66EC`; 01.09: q=8, lr `0x000ABA24`), the rendering thread sleeps in a poll, the presented frame stays "Loading..." | The RHI's SPURS job chain (01.02 `jc=0x01D53900`, 01.09 chain `0x012B6F00`) has jobs with `eaBinary=0 size=0`, which cellSpurs skips as "implausible binary". 01.02: the rendering thread (`func_006DDFF0`) calls `cellSpursRunJobChain(obj+0x21200)` and then sleep-polls until u32 `[obj+0x21180]` reaches its fence, which only the jobs advance. The FIFO also holds an old-style JUMP to itself (`w=0x20104708` at io `0x00104708`), a placeholder the jobs overwrite; cellGcmSys "resyncs" past it. 01.09 also logs `guard 0x0133AA80 still closed after 20 s -- chain gives up` and unresolved `cellSpursQueuePopBody` | The job binaries are presumably SPUJOBS.SPRX's (Edge Geometry), which is not loaded: T002. Find the poll in a new build from the callers of the `cellSpursRunJobChain` stub (01.02 `0x0194EC60`, 01.09 `0x00F8D4C0`) and the RenderingThread stack |
