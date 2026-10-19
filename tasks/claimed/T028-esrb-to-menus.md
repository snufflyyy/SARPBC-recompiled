# T028: 01.09: from the ESRB screen to the intro movies and main menu

Status: claimed
Owner: agent-frontier3
Touches: src/overrides/frontier_*.cpp (new), patches/ps3recomp/T028-*.patch (libs/spurs/**, libs/sysutil/**, libs/codec/** or other HLE modules no other claimed task touches; not libs/gcm, libs/video, runtime/spu, runtime/ppu, runtime/platform), docs/debugging.md, docs/unreal-engine-3.md
Reads: tasks/done/T022*, patches/experimental/T022-esrb-experiment.diff, tasks/open|claimed/T024*, T025*, T027*, docs/dod3-reuse.md

## Goal
**User priority: menus.** T022 reached the legal/ESRB screen with a 3D car on 01.09 by combining
three fixes. Two are merged (gcm_inject_base override, SPURS chain patch 0024); the third (GCM park
handling + Linux writer-preferring rwlock) is being finished by T024 and T027 in parallel. Do not
wait for them: apply `patches/experimental/T022-esrb-experiment.diff` locally (never commit it) or
run with `GCM_INTR_THREAD=1`, reach ESRB, and find what blocks the next step: intro movies (Bink),
then the main menu. Open leads from T022: PhysX `HALT-ASSERT heqi pc=0x24884` and an SPU spinning on
`GETLLAR 0x0133B880` (read-only for you: SPU runtime fixes belong to T025, so write a note there);
Bink/movie playback HLE; sysutil/save-data checks at the title screen; NP sign-in when offline.

## Done when
A boot_check line past ESRB (new package opens / movie or menu drawn, `captures/`), each blocker
documented with address and evidence, and fixes in your Touches either committed or handed to the
owning task as a note.

## Log
- 2026-10-19 10:04 agent-frontier3: claimed
