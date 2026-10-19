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
- 2026-10-19 10:22 agent-frontier3: Setup: build-0109 on main 171c84d (0001-0028) + experiment hunk 2 (writer-preferring rwlock) applied locally, uncommitted; env GCM_INTR_THREAD=1 GCM_PARK_GRACE_MS=100000000. boot_check 2026-10-19 10:13 v01.09 171c84d 90s: PROGRESSING | last open TEXTURES.TFC@15.8s | pkgs 13 (GUIDCACHE last) | zlib 3279 | dumps 10 lit 10 distinct 3 | flips 58 | threads 13/8 alive | unresolved 0 | alerts assert,blocked. Frames: Loading -> ESRB -> 'Powered by Unreal' at ~38-46 s. No Bink movies exist in 01.09 (no .bik files in the install; only BINKPS3_*.BIN shaders), so the intro 'movies' are the MAINMENU map's logo screens, no Bink HLE needed. Lead: after ~20 s, ShaderPatching job throughput collapses from ~680/s to ~20-30/s and flips to ~1 per 10 s. gdb at 45 s: RenderingThread in func_000DD014 (label-255 fence wait); 93 host threads of PhysX image 5af85a31 sit in spu_func_00032B44 -> spu_wrch -> spu_lockline_lock (GETLLAR spin on 0x0133B880) and 30 of image 7bde2a3f in spu_func_000068E0/6ACC, also lockline spinning; the ShaderPatching jc_thread waits in pthread_rwlock_wrlock in spu_mfc_release. So host-CPU starvation by ever-accumulating spinning PhysX task threads (CreateTask continues each frame, the old tasks never exit) is the current suspect for the slow frames. HALT-ASSERT heqi pc=0x24884 (Dynamics .text): halts if a memalign(128, 2*n+2) LS result at 0x34258 is not 16-byte aligned (or EA word at struct+0x10); investigating values.
