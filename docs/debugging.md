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

## Hangs found so far, and their causes

| Symptom | Cause | Fix |
|---|---|---|
| Allocator loops: `sys_memory allocate(...)` with no `-> addr`, NULL writes/calls | Guest VM from `calloc` is not page-aligned on Linux, so `vm_commit` mprotect fails | 4 GB-aligned `mmap` in `src/main.cpp` |
| "Registering Trophy Information" stuck at 0% (intermittent) | Deferred `PROCESSING_COMPLETE` overwrote the game's -1 "done" marker | patch 0001 |
| PoolThread `EventFlagWait BLOCKED ... flagEA=0x01DC8E00` after opening `CORE.XXX` | `_cellSpursLFQueuePushBody` missing, so Edge zlib never got work | `src/overrides/edgezlib.cpp` |
| `[spu_workload] async dispatch MISS fp=0x4100F6EDD2441719` | SPU images not lifted | SPU step in `tools/relift.sh` |
| After `ENGINE.XXX`: last `sys_memory allocate` near `0x4FFF0000` gets no `-> addr`, then `[null-write] guest wrote16 0x4F to 0x00000000 by guest-fn=0x005F8E38` (the UTF-16 text "OOM 4064...", UE3's out-of-memory message formatted into a NULL buffer) and `IO Failure detected` | ps3recomp's `sys_memory_allocate` was a one-way bump pointer over `0x40000000`–`0x50000000`; `sys_memory_free` never gave the range back. UE3 frees and re-asks for 64 KB pages all through loading (641 allocations, ~261 MB requested in total, while ~69 MB is live) | `patches/ps3recomp/T001-sys-memory-reuse-freed-ranges.patch` (range table, first fit). Runtime-level, no guest addresses: carries over to 01.09 |
| After `MAINMENU.XXX`: `PhysX: Cannot load SPURS programs. ... Error allocating memory for overlay table: 0 1 ... Cannot run without SPURS.`, then `sys_prx_exitspawn_with_level() - no-op` (the game is quitting) and NULL reads in `0x006E73E0`/`0x006D3A88` during teardown | `cellOvisGetOverlayTableSize` HLE returns `CELL_OVIS_ERROR_NOT_INITIALIZED` (0x80410701); the game uses the result as a size, hence `allocate(size=0x80420000)` twice just before the message | Owned by T003 (cellOvis / PhysX SPU image #7). Open as of 2026-10-18 |
