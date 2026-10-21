# T052: Crash when a mini-game round ends (timer reaches 0:00): null-page reads, then SIGSEGV at ~193 s

Status: claimed
Owner: pi
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
- 2026-10-20 23:37 claude: DECODED the assert: func_00B5F8EC is called with fmt="MULTISTREAM ASSERT : %s was called but MultiStream hasn't been initialised.\n", %s="cellMSSystemSignalSPU" (strings read from game/EBOOT.elf at TOC(0x0123C6D0)-0x7D14 and -0x7DF4+0x68). The crashing thread tid=8 is the "MultiStream Update Thread" (created at boot, entry OPD 0x01225628, arg 0x40BA53B0). So at round end the update thread calls cellMSSystemSignalSPU while the MultiStream 'initialised' flag (byte at [TOC-0x7EA8]+0x30) reads 0: either MS was shut down without joining the update thread (no thread create/exit appears in the log after boot except Rendering/PhysX threads), or the flag/heap memory was overwritten (the null array entry, the zero OPD code word and the null vtable slots on tid 2 all look like freed or clobbered objects). Check first: does the guest call cellMSSystemShutdown/Init around the round end, and what does our sys_memory_free/lwcond/event-flag path do for the memory it frees?
- 2026-10-21 01:32 pi: claimed
- 2026-10-21 01:32 pi: Resuming after Claude: T048/T049 and performance/audit/CI work are already implemented and will not be repeated. Taking Claude decoded MultiStream not-initialised assert as starting evidence. Inspect existing soak logs and guest shutdown/lifetime paths first; do not rerun intentional crash repros. Work isolated in pi/work.
- 2026-10-21 01:34 pi: User says Claude is active again. pi owns T052 and is doing static investigation in .worktrees/pi; no new crash reproduction or main-runtime edits. Please avoid overlapping T052 overrides/runtime lifetime fixes until coordinated through the board. Completed Claude T048/T049/performance changes are preserved.
- 2026-10-21 01:37 pi: Static follow-up from existing 23:33 soak, no rerun: timeline already contains host crash at t=163.54; reported 193.2 includes ~30 s core dumping, not delayed audio failure. First null-write stack has r15(start index)=15, r21(count)=-15, so B05D18 is processing a negative range, not just a null pointer in a valid range. MultiStream assert is likely secondary: crash r30=0 after loading TOC[-0x7EA8], whose ELF value is 0x01334680; OPD 0x012025A8 originally contains 0x000DC2DC, not zero. Thus evidence suggests corruption reaches static TOC/OPD data, not merely normal audio shutdown. Following negative-count producer before changing audio.
- 2026-10-21 01:38 pi: HANDOFF: static investigation only; pi/work is synced to bea2f06, no source edits/builds/boots yet. Claude is active on T018 (clean exit); no overlap so far. More precise next lead: B16DAC+0x168 (B16F14) reads packed halfword start/end, computes count=end-start, then calls B05D18. First-fault saved registers show start=15/count=-15 => decoded end=0. B05D18 calls AFCBB0 reserve(count+1), which computes 112*(-14)+20=-1548, matching fault r5=FFFFF9F4. Trace the producer/validity of that packed range and its SPURS-enabled gate before proposing any null/audio guard; negative-count origin remains unverified. Existing evidence is analysis/boot_check/20261020-233343-2212622/run.log and timeline.jsonl. No fix claimed and no new tests run. T051 lingering claim was closed administratively; board changes are not committed/merged while Claude has active main edits.
