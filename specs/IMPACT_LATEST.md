---
type: impact-analysis
context: T007 audio plus preserved Claude T036/T037 gameplay changes on 16b0488
---

# Combined offline-gameplay changes

## Targets and dependents
- `tools/make_spu_overlays.py`: called by `tools/relift.sh`; emit a second,
  independently registered filter bank at the same LS base. Existing bank name,
  image id and placement remain unchanged. Both game versions use this tool.
- `src/overrides/audio_mp3.cpp`: one internal `standin_entry` caller. Reject a
  truncated ID3v2 header without reading beyond local store. No ABI change.
- Claude's `tools/boot_check.sh --pad`: preserve and validate scheduled input.
  Existing runs without `--pad` are unchanged. Only trusted local specs are parsed;
  no shell evaluation of button names or schedule text.
- Claude's SPURS attribute patch: shared `cellSpursCreateTasksetWithAttribute`
  creation path now preserves the full taskset argument passed to tasks in r4.
  Priority bytes are retained; scheduling priorities remain otherwise unchanged.
  No title-specific runtime conditions, registry changes or instruction changes.

## Affected stories/tasks
No release plan exists. Board tasks T007 (sound), T036 (scripted input), T037
(arena load). User requested preserving Claude's local changes and verifying them
with pi's changes, using Claude's updated main 16b0488 as the base.

## Evidence and coverage
- 115 s real PulseAudio boot: arena package opens at 65.2 s, then stalls.
  Three MP3 frames decode; a missing DSP-bank lift ends the mixer at LS0x37010.
- A temporary DMA trace identifies the next 12 KiB DSP bank as the filter plugin.
  Generic eviction is correct. No runtime overlay change is required.
- Synthetic overlay tests cover both bank layouts, same-base/distinct-image
  registration inputs, seeds, source discovery, missing modules and overlap.
- Firmware-free MP3/SPU tests cover metadata, planar BE PCM, state, counts and
  return registers. Guard pages reproduce the ID3v2 boundary SIGSEGV (-11).
- Game-free pad tests exercise the production parser and timed writer.
- Clang/GCC SPURS tests cover full 64-bit args, priority byte order and the
  pre-existing size/alignment/backing/canary checks.
- Required integration gates: full lint/tests, clean patch replay, 01.09 build,
  real-device audio capture, scripted offline arena boot and desktop smoke.

## Risk: Medium
SPURS is shared runtime code and DSP banks deliberately overlap in LS. Keep exact
signature ownership and run both regressions and a real boot; do not infer arena
playability or audible output from synthetic tests alone. No firmware/game data
will be published. Generated test lifts stay private under the pi analysis tree.
