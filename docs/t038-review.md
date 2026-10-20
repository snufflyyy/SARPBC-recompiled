# T038 review — loading-screen orientation

Reviewed by pi on 2026-10-20 (T050), against main `9c72623`.

## Resolution — T051 (2026-10-20)

A fresh 01.09 boot selects **LOADING.PNG**, not the BMP assumed by T038. Both splash
PNG decodes request `outputColorSpace=20, outputMode=1` (ARGB, bottom-to-top).
`cellPngDec` reads that mode but reports mode 0 and always writes top-to-bottom rows.
The loading quad therefore samples the wrong row layout. The generic correction
belongs in the decoder, not in a shader classifier or backend viewport special case.

The public [PSL1GHT PNG interface](https://github.com/ps3dev/PSL1GHT/blob/master/ppu/include/pngdec/pngdec.h)
defines TOP_TO_BOTTOM=0 and BOTTOM_TO_TOP=1. Its
[viewport documentation](https://github.com/ps3dev/PSL1GHT/blob/master/ppu/include/rsx/commands_inc.h)
also agrees with the pre-workaround viewport math. Temporary draw instrumentation
confirmed first=4 is honoured, base offset/index are zero, scale Y=-360 and translate
Y=360, with v=0 at position Y=-1. No projection-dependent compiler behavior is needed
to explain the failure. Evidence: pi worktree `analysis/t051-mode-boot.log` and its
2026-10-20 20:30 boot log.

**F01 and F02 are resolved:**
- `patches/ps3recomp/0051-pngdec-output-mode.patch` validates and reports the requested
  scanline order and selects source rows locally while preserving channel order and pitch.
  It does not change stb's global flip state.
- `patches/ps3recomp/0052-shader-independent-viewports.patch` removes the entire
  instruction-count workaround. The original viewport formulas, shader compiler,
  culling and scissor conventions remain unchanged for every backend and program.
- The new PNG guest-ABI fixture covers 72 row-order/channel/pitch combinations across
  heights 1/2/3, plus invalid-mode rejection without changing accepted parameters.
  It fails against the old codec and passes against the fix. The neutral draw fixture
  now covers fixed/guest programs, MOV/MOV versus MOV/MOV/NOP, unrelated two-instruction
  constant/arithmetic programs, both scale signs and non-centered offsets. Six cases
  failed with patch 0050; all pass after removing it.
- Both fixtures pass ASan+UBSan. All 88 discovered test scripts return zero; the three
  nested SDL/Vulkan suites omitted by discovery also pass explicitly. Existing skip
  visibility limitations remain T048, not a claim that every optional tool was present.
- The fixed Release executable completes a 120 s 01.09 run with upright Loading text
  and arena/car/HUD: 3729 zlib requests, 2575 flips, unresolved 0. Capture directory:
  `captures/boot_check/20261020-203420-1327469/` in the pi worktree. The report says
  `STALLED since 102.4s (frames still presented)`; this heuristic is not a render freeze.
- An additional 55 s boot with timed snapshots confirms upright ESRB/car, Psyonix and
  Unreal logos, profile selection, main menu and Single Player menu. Local contact sheet:
  `analysis/t051-orientation-stages.png`; run log: `analysis/t051-stages-boot.log`.

PNG row order is a portable HLE contract, not a backend workaround. Linux/Vulkan is
visually verified; Windows/macOS are not claimed as tested. No new FPS claim is made.
Patch 0050 stays in historical stack order but is fully undone by T051's video patch;
do not offer 0050 upstream. The codec correction can be offered independently.

## Original review decision (T050, before T051)

Antigravity's implementation is **already merged** as `ba70ca3`, including patch
`0050-loadscreen-passthrough-orientation.patch`. No branch remains to merge, and no
second application is needed. This review leaves the implementation unchanged.

The Linux/Vulkan symptom fix is verified: loading text and the tutorial arena/HUD
are upright. **The shared-runtime fix is not ready for general upstream acceptance:**
F01 demonstrates that shader length changes rendering independently of shader
semantics. T051 tracks correction and permanent regressions. This is not evidence
of a new visual regression in the tested SARPBC sequence.

## Original findings, by priority (both resolved by T051)

### F01 — P1: instruction count is not a passthrough-program predicate

Location: patch 0050, added lines 37–40; applied source
`external/ps3recomp/libs/video/rsx_draw_engine.c:2711-2714`.

The condition is only `eng_guest_programs(...) && cur_vp_instrs == 2`. It does not
check position/UV instructions, constant use, projection, viewport sign or backend.
It therefore flips **every** resident two-instruction VP, not just the program
described by the comment. Conversely, equivalent longer passthrough programs do
not receive the same transform.

A source-only probe against the actual draw engine and its stub backend confirms:

```text
decompile instructions=2/3 identical_HLSL=1 draws=1/1
two-instruction viewport y_scale=-1 y_offset=-0.5
same shader plus NOP viewport y_scale=1 y_offset=0.5
```

The programs are `MOV HPOS,v0; MOV TEX0,v8` and the same program with a terminating
NOP. Their generated HLSL is byte-identical. Each issues one draw with identical
surface, viewport, FP and vertex state. Only the VP length changes. The differing
constants feed the same `Out.pos` expression, so this is a rendering-contract
violation, independent of which orientation is correct on real hardware.

**Required correction (T051):** establish the RSX/host viewport contract and use a
title-agnostic semantic rule, not a magic instruction count. A temporary title
workaround belongs on the port side, not in the generic draw engine. Add public-
interface regressions for the NOP counterexample, unrelated two-instruction VPs,
both viewport signs, non-centered offsets and fixed/guest pipelines. A narrower
length check alone does not resolve this finding.

### F02 — P2: the projection-dependent compiler explanation is unsupported

Location: patch 0050's commit message and inline comment; Graphics orientation
notes in `docs/subsystems.md`; historical T038 entry in `docs/status.md`.

The explanation says `setInvertY` is active for projection-matrix shaders. In
`external/ps3recomp/libs/video/rsx_shader_spirv.cpp`, the actual condition is only
`if (lang == EShLangVertex) shader.setInvertY(true)`. There is no projection-matrix detection.
The patched draw-engine block is also backend-neutral rather than Vulkan-only.

The captures establish the visual improvement, not this proposed cause or safety
on Metal/D3D12. Treat the cause as a hypothesis until the viewport/clip-space
contract is demonstrated. T051 must correct the explanation along with the rule;
this review does not rewrite historical claims as though they had been validated.

## Original verification (T050)

- **Fresh 120-second Linux/Vulkan boot on the combined stack**, using the already
  rebuilt private 01.09 executable containing patch 0050:

  ```bash
  tools/task.sh lock boot env BUILD_DIR="$PWD/build-0109" PS3_VERBOSE=0 \
    tools/boot_check.sh 120 --version 0109 --quiet \
    --pad 'cross@40*4/5,cross@70,r2:120@90,cross@100'
  ```

  ```text
  boot_check 2026-10-20 20:04 v01.09 9c72623 120s: STALLED since 100.4s (frames still presented) | last open PYRAMID_COLLECTBOOST.XXX@56.2s | pkgs 15 (PYRAMID_COLLECTBOOST last) | zlib 3726 | dumps 49 lit 49 distinct 45 | flips 2630 | threads 19/9 alive | unresolved 0
  ```

  Capture directory: `captures/boot_check/20261020-200217-1296812/` in the pi
  worktree. `frame_first_lit.png` shows upright Loading text; `frame_last.png`
  shows the tutorial car against the arena wall and upright HUD. The final ten
  seconds contain four distinct frame dumps: the report's STALLED classification
  means no new log shapes/resources, **not** a rendering freeze in this run.
- **Existing neutral renderer suite**, under the CPU lock:
  `python3 external/ps3recomp/tools/test_rsx_immediate_vertices.py` reports
  `all checks passed`. It has no dedicated orientation regression; its success
  does not invalidate F01.
- **Synthetic equivalence probe**, also compiled/run under the CPU lock, exits
  zero after confirming the differing transforms above. Local source/log:
  `analysis/t050-counterexample.c` and `analysis/t050-counterexample.log` in the
  pi worktree. These are ignored review artifacts, not committed test coverage.
- T047 had already rerun all 87 discovered scripts on the combined stack, plus a
  30-second smoke. This review does not claim to have rerun that entire gate.
- No new dependencies, game-derived source, allocation or guest-memory write path
  are introduced by the reviewed patch. Static review found no new security issue
  in its added scalar/selector operations; this is not a whole-renderer safety audit.
- No FPS measurement or Windows/macOS/backend validation is claimed. The extra
  resident-program lookup per draw was not separately benchmarked.

## Recreating the counterexample without game data

Use the existing stub backend and setup/teardown helpers in
`external/ps3recomp/libs/video/tests/test_rsx_draw_engine.c`. Include that fixture
in a scratch translation unit with its `main` renamed, then add a separate driver.
All words below are hand-constructed from the documented NV40 fields, not lifted
from a game binary. Words are host little-endian on the tested Linux machine:

```c
u32 two[] = {
    0x401f8000, 0x0040000d, 0x81000000, 0x0001e000, /* MOV HPOS,v0 */
    0x401f8000, 0x0040080d, 0x81000000, 0x0001e01d  /* MOV TEX0,v8; END */
};
u32 three[12] = {0};
memcpy(three, two, sizeof two);
three[7] &= ~1u;
three[8] = 63u << 15;
three[11] = 1; /* NOP; END */
```

1. Decompile each through `rsx_vp_decompile`: counts must be 2/3 and generated
   HLSL must compare equal. Allocate the fixture's 16 MiB synthetic memory and
   initialize its three readable float4 positions as in the fixture's main.
2. At main-memory offset `0x30000`, encode a terminating `MOV r0,COL0` FP using
   the word-order and operand helpers in
   `external/ps3recomp/libs/video/tests/test_fp_decompiler.c`. Select it with
   method `0x08E4 = 0x30002` and `0x1D60 = 0x40`.
3. For each program, call `engine_up()` (256×256 surface). Write viewport
   translate X/Y = 128/64 to `0x0A20/0x0A24`, scale X/Y = 128/-128 to
   `0x0A30/0x0A34`. Set VP upload/start slots to zero (`0x1E9C/0x1EA0`), upload
   words through `0x0B80 + (word_index % 4)*4`, select the same FP, and call
   `draw_triangle()`. Record `stub.vp_xf[1]` and `[5]` before `engine_down()`.
4. Build with the same six engine/dispatcher/decompiler source files and include
   directories used by `external/ps3recomp/tools/test_rsx_immediate_vertices.py`.
   Require one draw in each case. The pre-T051 patch produced the opposite Y
   pairs recorded above; the permanent T051 regression instead requires
   semantically equivalent programs to retain the same transform.

## Original review checklist (T050)

| Area | Result |
|---|---|
| Scope, patch provenance, no duplicate merge | Pass |
| Observed Linux/Vulkan loading and arena orientation | Pass |
| Generic rendering correctness | **Fail — F01 / T051** |
| Focused regression coverage | **Missing — required by T051** |
| Explanation matches implementation | **Fail — F02 / T051** |
| New dependency/secret or obvious new security exposure | None found in added code |
| Performance and other backends | Not measured/tested; no acceptance claim |

Do not equate a small diff, broad passing test count, or one title's upright
captures with a validated generic shader predicate.
