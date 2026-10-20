# T052: Crash when a mini-game round ends (timer reaches 0:00): null-page reads, then SIGSEGV at ~193 s

Status: open
Owner: -
Priority: 2
Touches: docs/debugging.md (a short section), src/overrides/ (a fix keyed by guest address), patches/ps3recomp/T052-*.patch (runtime)
Reads: docs/debugging.md, docs/subsystems.md (SPURS), docs/unreal-engine-3.md

## Goal
Found by the 2026-10-20 stability audit: the arena runs well until the round timer hits 0:00, then the game goes unstable and crashes. Make a round end (and what follows: results screen, back to menu) survive.

Repro (01.09, ~200 s, boot lock): `PS3_NULL_READ_STACK=1 PS3_VERBOSE=0 tools/task.sh lock boot tools/boot_check.sh 215 --version 0109 --pad 'cross@40*4/5,cross@70,r2:120@90,cross@100'`. The timer shows 0:02 in the last captured frame; null reads start at ~163 s; `CRASHED at 193-196 s (signal SIGSEGV)`, 3 of 3 runs. A 160 s run only sees the alerts during teardown.

Evidence so far:
- First fault: `[null-read] guest read32 from 0x10 (NULL+0x10) by guest-fn=0x00B02878` (a vector/physics helper, r4 = NULL). Guest chain: func_00B05D18+0x8C -> func_00F64A38 -> func_00BFFFE4 -> func_00B16DAC -> func_00B06678 -> ... on tid 10. func_00B05D18 loops over an array of pointers at [r26+0x4C], count in r15, calling B02878 per element; one element is NULL.
- Later, `[ppu] guest_call: OPD 0x012025A8 -> code 0x00000000 not registered (opd: 00000000 0123C6D0 ...)`: a callback descriptor whose code word is zero (clobbered, compare ppu_register_opd_fixup in ppu_loader.cpp).
- SIGSEGV (gdb attached at 150 s, `handle SIGSEGV stop nopass`): rip = 0, caller func_0082EA64, thread entry func_0077CEB0 (a worker thread). A call through a null host function pointer.
- Hypotheses (not verified): objects freed by the level teardown while worker/SPURS threads still run (our async SPURS tasks do not wait the way the console does); or an array filled by a task that never completed.
- Vulkan validation layer run (arena, 160 s): only `Undefined-Value-ShaderOutputNotConsumed` warnings, so this is not the renderer.

Next: find which array/object is NULL at 0x00B05DC0 and who last wrote it (watchpoint on the element via `barrier_watch` or a gdb hardware watchpoint on the host address), and what the round-end code (UnrealScript game-over) waits on.

## Done when
A 300 s arena run through the end of a round does not crash and boot_report shows no null-read/null-write alerts before the next screen appears; the cause is written up in docs/debugging.md.

## Log
- 2026-10-20 23:37 claude: With the new crash handler (src/overrides/crash_report.cpp) the SIGSEGV report shows: crashing thread tid=8 (entry func_0077CEB0 -> func_0082EA64), lr=0x0082EB18 = the call to func_00B5F8EC right before an infinite self-loop (loc_0082EB1C): that is the game's own assert/fatal path, not a null dereference; cia=0x01225628 is data. Meanwhile tid=2 logs '[ppu] bctr to NULL from func_0022DC88+0xDC5 / +0x11B5 r12(opd)=0x4' repeatedly (a virtual call through a NULL method slot on objects 0x4066E0E0, 0x4055B850, 0x4055B340). So at round end the game's object state is corrupt or incomplete first (null array entry at B05DC0, null virtual methods), then an assert fires. Look at func_00B5F8EC's arguments (r3/r4 at the call) for the assert text.
