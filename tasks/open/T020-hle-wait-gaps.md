# T020: HLE gaps that can cause infinite waits (dialogs, music, voice, unresolved reporting)

Status: open
Owner: -
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
