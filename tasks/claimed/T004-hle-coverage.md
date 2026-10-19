# T004: HLE coverage audit for all 274 imports + name the 17 unknown NIDs

Status: claimed
Owner: agent-hle
Touches: docs/hle-coverage.md (new), tools/hle_coverage.py (new), patches/ps3recomp/T004-*.patch (trivial missing handlers only; NOT cellOvis, which is T003)
Reads: analysis/imports_named.json, src/recomp/ppu_hle_nids.cpp, external/ps3recomp/libs/**, tools/nid_database.py

## Goal
Produce a script and a doc table: for every import of the EBOOT (274: library, NID, name)
— is there an HLE handler, is it a real implementation or a stub, and which ones the boot
has hit so far (cross-check a run log with PS3_HLE_TRACE). Name the 17 NIDs the database
cannot (e.g. cellSysutil 0xA9B0C1D9, 0x9949BF82; sys_net 0x3F09E20A, 0xF7AC8941; cellMic
×5; sceNp 0x7DEB244C, 0x7E2FEF28; cellVideoExportUtility ×3; cellVideoUpload; cellMusicUtility ×2)
by computing NIDs (SHA-1 of name + suffix) from candidate SDK names. Add trivial handlers
that are obviously right (return CELL_OK / "not available") as one ps3recomp patch; list
the non-trivial gaps as candidate tasks in the doc.

## Done when
docs/hle-coverage.md exists with the full table and gap list, linked from the AGENTS.md
docs index via a note to the coordinator (do not edit AGENTS.md yourself).

## Log
- 2026-10-18 23:12 agent-hle: claimed
- 2026-10-18 23:13 agent-hle: claimed; worktree set up; parsing registry (ppu_hle_nids.cpp + ps3_hle_register_ctx sites), building for a trace run
- 2026-10-18 23:16 agent-hle: all 17 unknown NIDs named by computed SHA-1 match: cellSysutil A9B0C1D9=cellGameDataGetSizeKB 9949BF82=cellGameDataExitBroken; sys_net 3F09E20A=socketselect F7AC8941=gethostbyaddr; cellMic 05709BBF=cellMicOpenEx 65336418=cellMicRemoveNotifyEventQueue 6BC46AAB=cellMicReset 7903400E=cellMicSetNotifyEventQueue B2C16321=cellMicSetDeviceAttr; sceNp 7DEB244C=sceNpScoreCensorComment 7E2FEF28=sceNpManagerRequestTicket; cellVideoExport 2F457571=cellVideoExportInitialize2 81296524=cellVideoExportFromFile C15BE817=cellVideoExportFinalize; cellVideoUpload 122E0D0F=cellVideoUploadInitialize; cellMusic 8793EF97=cellMusicGetSelectionContext2 AD04CDDD=cellMusicSelectContents2
- 2026-10-18 23:19 agent-hle: retargeted by coordinator: primary audit is now 01.09 (versions/0109: 288 imports/21 libs, 20 unnamed); 01.02 kept as a secondary column
- 2026-10-18 23:19 agent-hle: 01.02 boot finding: cellGameDataExitBroken (0x9949BF82, unregistered -> faked CELL_OK) is the LAST new HLE call at boot, lr=0x683F2C, after STARTUP_INT.XXX opens; frames keep flipping afterwards. Also cellGameDataGetSizeKB (0xA9B0C1D9) unresolved early. Likely UE3 IO-failure/broken-data path -> relevant to T001 stall
