# T053: Fix current audio playback defects after T052

Status: open
Owner: -
Priority: 2
Touches: src/overrides/audio_*, patches/ps3recomp/T053-*.patch (audio and SPU mixer fixes), tools/test_audio_*.py, docs/subsystems.md (Audio section)
Reads: docs/subsystems.md (Audio), docs/debugging.md, docs/dod3-reuse.md

## Goal
User request, 2026-10-21: after T052 is complete, fix current audio playback problems. Confirm the symptoms and measure the present mixer/output path before selecting a fix. Preserve prior MP3, DSP overlay and audio-pacing repairs; those repairs do not prove current playback quality.

## Done when
The reported defect is reproduced or captured without a deliberate crash, its cause is documented, a regression test covers the fix where feasible, and current arena playback is verified. Measure mixer delivery, silent blocks and underruns; do not equate a non-silent WAV with correct real-time playback. This task follows T052 and precedes T054.

## Log
