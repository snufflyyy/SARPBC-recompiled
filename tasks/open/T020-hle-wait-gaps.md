# T020: HLE gaps that can cause infinite waits (dialogs, music, voice, unresolved reporting)

Status: open
Owner: -
Priority: 15
Touches: patches/ps3recomp/T020-*.patch (libs/system/cellMsgDialog*, libs/misc/cellMusic*, libs/audio/cellVoice*, runtime/ppu/ppu_hle.cpp unresolved reporting, libs/misc/cellVideoExport*/cellVideoUpload*/cellGameRecording* names), docs/hle-coverage.md
Reads: docs/hle-coverage.md (T004's ranked gaps), analysis/imports_named.json (both versions)

## Goal
From T004's audit, the gaps most likely to hang a game that waits on a callback:
1. `cellMsgDialogOpenErrorCode`: show/log the error and fire the close callback.
2. cellMusicUtility (7 imports, no module upstream): an offline "unavailable" implementation
   that still delivers the init/finalize callbacks the game waits for.
3. cellVoice `InitEx`, `StartEx`, `CreateNotifyEventQueue` (write the queue id; create a real lv2
   event queue), `SetNotifyEventQueue`.
4. `PS3_HLE_UNRESOLVED=fail` is dead code: make the dispatcher call `ps3_hle_unresolved()` and
   report each unresolved NID once, without the 40-NID cap.
5. Upstream's cellVideoExport/cellVideoUpload/cellGameRecording use made-up function names:
   give them the real SDK names (computed NIDs must match) so the game's imports resolve.
Generic and title-agnostic; each with a test where the area has one.

## Done when
All five done or precisely documented; patches exported; docs/hle-coverage.md updated.

## Log
- 2026-10-18 23:48 agent-hlegaps: claimed
- 2026-10-19 00:00 agent-hlegaps: Coordinator: cellVoice now on 01.09 boot path -> prioritised. dod3 fork (soyjxck/ps3recomp master) checked: cellVoice/VideoExport/VideoUpload/GameRecording identical to upstream, cellMsgDialog has no OpenErrorCode, ppu_hle.cpp has the same dead ps3_hle_unresolved -> nothing to port. Done so far: T020-1 cellMsgDialogOpenErrorCode (OK callback on next poll, test). cellVoice InitEx/StartEx/Create+Set+RemoveNotifyEventQueue with a real lv2 queue + SERVICE_ATTACHED(8)/DETACHED(0x10) events; GetPortInfo fixed (wrote param struct, game reads state@+4, overran 24-byte block). Evidence from 01.09 lift: InitEx param {0,100,0x20000000} @0xBEF958, SetNotifyEventQueue(key,0x3039), voice thread 0xBEFB2C receives with 30us timeout and compares data1 to 8/0x10. Test test_voice_notify passes. Building own 01.09 (build-0109) to boot-check.
- 2026-10-19 00:03 agent-hlegaps: cellVoice verified on 01.09 (own build-0109 + scratch vfs copy, boot_check 60s): InitEx(eventMask=0x0, version=100, appType=0x20000000), CreateNotifyEventQueue -> id=6 key=0x8000564F00000001, SetNotifyEventQueue(source=0x3039), StartEx() all resolved at 4.1s; unresolved now only 0x91066667 cellSpursQueuePopBody (T019); the stall is SPURS EventFlagWait + flashMP3.pic (T019/T007), not voice. Patch T020-2 exported (commit on branch).
- 2026-10-19 00:06 agent-hlegaps: HANDOFF: done=items 1,2,3,5 as patches T020-1 (cellMsgDialogOpenErrorCode), T020-2 (cellVoice InitEx/StartEx/Create+Set+RemoveNotifyEventQueue, real lv2 queue, SERVICE_ATTACHED 8/DETACHED 0x10, GetPortInfo fix), T020-3 (new libs/misc/cellMusic.c: all 13 01.09+01.02 cellMusicUtility imports, results via sysutil callback), T020-4 (cellRec/cellVideoExport/cellVideoUpload SDK names in cellGameRecording.c/cellVideoExport.c/cellVideoUpload.c); 6 unit tests pass on Linux (incl. 3 new + 1 new voice); all 12 patches apply from the pin. Verified voice on 01.09 boot (own build-0109, scratch vfs): InitEx/Create/Set/StartEx resolved at 4.1s, unresolved only cellSpursQueuePopBody. state=item 4 (ppu_hle.cpp unresolved reporting) NOT started; docs/hle-coverage.md NOT updated; music/rec/export not boot-verified (user-triggered paths). Dod3 fork has nothing to port for these. next=(1) ppu_hle.cpp: replace the 'logged<40' print with ps3_hle_unresolved(nid, ctx) (it sets r3; drop the final ctx->gpr[3]=0; add lr to the first report; make its seen-table thread-safe), commit, export T020-5; (2) regen docs/hle-coverage.md with tools/hle_coverage.py --set 01.09 ... regen (36 missing should drop by 20: msgdialog 1, voice 4, music 7, rec 5, export 3, upload 1); (3) coordinator: debugging.md PS3_HLE_UNRESOLVED note, upstream docs (MODULES_REFERENCE/MODULE_STATUS) still name cellGameRecording*. branch=worktree-agent-a9a32fe5a64dad8ef
- 2026-10-19 00:06 agent-hlegaps: RELEASED: paused for usage; see HANDOFF note
