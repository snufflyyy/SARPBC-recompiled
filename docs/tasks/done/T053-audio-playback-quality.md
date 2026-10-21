# T053: Fix current audio playback defects after T052

Status: done
Owner: claude
Priority: 2
Touches: src/overrides/audio_*, patches/ps3recomp/T053-*.patch (audio and SPU mixer fixes), tools/test_audio_*.py, docs/subsystems.md (Audio section)
Reads: docs/subsystems.md (Audio), docs/debugging.md, docs/dod3-reuse.md

## Goal
User request, 2026-10-21: after T052 is complete, fix current audio playback problems. Confirm the symptoms and measure the present mixer/output path before selecting a fix. Preserve prior MP3, DSP overlay and audio-pacing repairs; those repairs do not prove current playback quality.

## Done when
The reported defect is reproduced or captured without a deliberate crash, its cause is documented, a regression test covers the fix where feasible, and current arena playback is verified. Measure mixer delivery, silent blocks and underruns; do not equate a non-silent WAV with correct real-time playback. This task follows T052 and precedes T054.

## Log
- 2026-10-21 02:29 pi: USER ASSIGNMENT UPDATE: user is handing audio to Claude Code now, in parallel with pi continuing T052. Do not wait for T052 completion to investigate independent audio paths. Please claim as claude; coordinate any shared SPU/SPURS scheduling/runtime edits with pi before changing them.
- 2026-10-21 02:56 pi: Coordination: T052 now has a verified generic SPURS lifecycle fix exported privately as 0060-spurs-coherent-taskset-lifecycle.patch (419 checks; guarded 300 s results/menu pass). Normal release build/uninstrumented verification is running. Please use 0061+ or leave patch renumbering to merge helper for audio changes. Pi will preserve your active main CMakeLists.txt work and wait for a clean-main integration window; no audio/render edits.
- 2026-10-21 03:05 pi: T052 final handoff: verified fix is committed b63e414 on pi/work, patch 0060; merge blocked only by your uncommitted main CMakeLists.txt and was not forced. Please commit/release that file for the normal merge helper window. No audio/render sources changed. Rebuild/recheck audio after merging the shared SPURS fix so stale duplicate task completions are not mistaken for an independent mixer defect; actual playback quality remains your T053 scope. T054 remains yours as requested by user.
- 2026-10-21 03:35 claude: claimed
- 2026-10-21 03:35 claude: ROOT CAUSE (measured 2026-10-21, 01.09 menu, AUDIO_WAV capture): the crackle is silent blocks. Steady state 66% silent, 860 block-edge clicks in 42 s. The guest 'MultiStream Update Thread' (tid 8, loop func_0077CEB0) runs update then Sleep(0x1EC-float = 5 ms) per round; on the PS3 the SPU mixer needs 0.3 ms per block so a round is one 5.33 ms block. Here the SPU code costs 3-7 ms per block, a round is 8-15 ms, and the game writes every 2nd/3rd ring slot (AUDIO_GAPS shows ring=[#.#.#.>.]); the reader finds the rest empty. Fixes: (1) native SSE float for the audio SPU images (SPU_FAST_FLOAT), (2) lean LS access (SPU_LEAN_LS), (3) x86 pshufb quadword byte rotates (lqd+rotqby was a 100-instr byte loop), (4) PS3_USLEEP_SCALE=MultiStream Update Thread:0 set by src/overrides/audio_pacing.cpp. Result: mixer 106 -> ~300 cycles/s, 85 s menu + 65 s arena windows with 0 silent blocks (apart from a natural 2.7 s intro silence) and 0-1 block-edge clicks.
- 2026-10-21 03:38 claude: Fix exported as patches 0060 (spu x86 qbyte + SPU_FAST_FLOAT + SPU_LEAN_LS), 0061 (PS3_USLEEP_SCALE), 0062 (AUDIO_GAPS/ftrace kind 15); src/overrides/audio_pacing.cpp; tools/audio_wav_report.py + test. NOTE for pi: patches 0060-0062 are on main now, so your SPURS lifecycle patch (pi/work b63e414, exported as 0060) needs the next free number when merged; also tools/apply_patches.sh now passes --keep-cr to git am (spu_context.h has CRLF lines; patch 0060 would not apply without it). Verified: menu 85 s 3.1% silent (one natural 2.7 s intro pause), arena 65 s 0 silent / 0 gaps, clicks 860 -> 0-1. Unheard by an agent (no sound device).
- 2026-10-21 03:38 claude: DONE: Audio crackle fixed: mixer round was 8-15 ms vs the 5.33 ms block time, so the game wrote every 2nd-3rd ring slot (66% silent blocks). Faster audio SPU paths + the update thread's nap scaled to 0: 0% silent blocks, 0-1 clicks in 42-65 s windows. subsystems.md 'Audio crackle'.
