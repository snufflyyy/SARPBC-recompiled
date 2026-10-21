# T054: Correct the shadow beneath the car after the audio fix

Status: open
Owner: -
Priority: 2
Touches: patches/ps3recomp/T054-*.patch (shadow-related rendering), src/overrides/ (only if evidence requires a title fix), docs/subsystems.md (Graphics), docs/debugging.md (shadow findings)
Reads: docs/subsystems.md (Graphics), docs/debugging.md, docs/dod3-reuse.md, docs/t038-review.md

## Goal
User request, 2026-10-21: after T052 and the audio task T053, correct the incorrect shadow beneath the car. Inspect current captures and obtain a visual reference or symptom detail before choosing a repair. Earlier notes calling the shadow correct do not supersede this report. Check shadow-map clear/copy bounds, compare direction and pass state without adding a global orientation workaround.

## Done when
The reported defect is identified, its root cause is documented, relevant synthetic rendering tests pass, and current gameplay captures show the corrected car shadow without regressions in the HUD, menu or other shadows. This task starts after T053.

## Log
