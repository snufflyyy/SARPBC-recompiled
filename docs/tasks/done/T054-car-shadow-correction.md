# T054: Correct the shadow beneath the car after the audio fix

Status: done
Owner: claude
Priority: 2
Touches: patches/ps3recomp/T054-*.patch (shadow-related rendering), src/overrides/ (only if evidence requires a title fix), docs/subsystems.md (Graphics), docs/debugging.md (shadow findings)
Reads: docs/subsystems.md (Graphics), docs/debugging.md, docs/dod3-reuse.md, docs/t038-review.md

## Goal
User request, 2026-10-21: after T052 and the audio task T053, correct the incorrect shadow beneath the car. Inspect current captures and obtain a visual reference or symptom detail before choosing a repair. Earlier notes calling the shadow correct do not supersede this report. Check shadow-map clear/copy bounds, compare direction and pass state without adding a global orientation workaround.

## Done when
The reported defect is identified, its root cause is documented, relevant synthetic rendering tests pass, and current gameplay captures show the corrected car shadow without regressions in the HUD, menu or other shadows. This task starts after T053.

## Log
- 2026-10-21 02:29 pi: USER ASSIGNMENT UPDATE: user is handing shadow correction to Claude Code alongside audio, while pi continues T052. Please claim as claude. pi will not edit rendering or audio sources for these follow-ups.
- 2026-10-21 04:16 claude: claimed
- 2026-10-21 13:45 claude: FIXED (patch 0064): car shadow was sampled from a 1280x720 depth snapshot of a 512x512 map (zetas are canvas-sized), so lookups were scaled/offset and moved with the car; fp constants verified fresh per frame (fp10 == map vp4). Snapshot now cropped to the sampling texture. Evidence: GPU shadow factor (post/pre of the multiply draw) before = detached blob up-left of car, after = under/behind car, matches numpy emulation; arena capture captures/boot_check/20261021-134239-541 clean, HUD intact; lint --tests 98 scripts 0 failed; test_color_feedback_engine +4 checks. Also 0063 RSX_ENGINE_PASS_DUMP_ALPHA diag.
- 2026-10-21 13:45 claude: DONE: Car shadow fixed: depth snapshot cropped to the shadow-map texture (0064); diag 0063. Verified by GPU-vs-emulation shadow factor, arena capture, lint --tests.
