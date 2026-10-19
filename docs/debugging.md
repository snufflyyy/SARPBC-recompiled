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
