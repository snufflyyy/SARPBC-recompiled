# T017: Save data in 01.09 — cellSaveData FixedSave2 / ListLoad2 and cellGame

Status: done
Owner: claude
Priority: 16
Touches: patches/ps3recomp/T017-*.patch (libs/filesystem/cellSaveData*.c, libs/system/cellGame*.c), src/overrides/save_*.cpp (new), docs/subsystems.md (Save data bullet only)
Reads: versions/0109/analysis/imports_named.json, external/ps3recomp/libs/filesystem/, docs/game-profile.md

## Goal
01.09 saves through cellSaveData (`cellSaveDataFixedSave2`, `cellSaveDataListLoad2`) and
checks its install with cellGame (`BootCheck`, `DataCheck`, `ContentPermit`,
`CreateGameData`, `GetParamString`, `GetSizeKB`). 01.02 used neither. Make sure that,
on a fresh vfs, the first boot creates its save and later boots load it. Check the
callback sequence (stat/file callbacks run as guest callbacks), where the save lands on
disk (dev_hdd0/home/00000001/savedata/...), PARAM.SFO contents, and the icons from
SARB/BINARIES/PS3/SAVE/. Starts from code reading; becomes testable once the 01.09 boot
reaches the save code (coordinate via the board).

## Done when
A documented save round-trip (save, quit, reload) on 01.09, or a precise list of what
blocks it, with evidence.

## Log
- 2026-10-21 01:57 claude: claimed
- 2026-10-21 01:57 claude: verified save round trip on 01.09 (fresh dir: LOAD new=1 -> AutoSave2 creates; next boot LOAD new=0 reads the same 3335-byte PAYLOAD, identical to the previous save). Details in docs/subsystems.md. FixedSave2/ListLoad2 not reached by any boot path (user-triggered); left unverified.
- 2026-10-21 01:57 claude: DONE: 
