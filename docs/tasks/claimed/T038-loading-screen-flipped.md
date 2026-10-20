# T038: The 'Loading...' screen is drawn upside down (render-target orientation)

Status: claimed
Owner: antigravity
Priority: 13
Touches: patches/ps3recomp/T038-*.patch (runtime/rsx/** orientation only), docs/subsystems.md (Graphics)
Reads: docs/subsystems.md

## Goal
From T028: the "Loading..." screen is drawn upside down. This is probably a render-target or present Y-flip mismatch between RSX surface origin and Vulkan. Check whether other screens are right (ESRB, menu look right), find the case that differs (window origin / surface clip / shader viewport), and fix it generally.

## What is known (claude, 2026-10-20)
- The screen is ONE draw per frame, the same every frame (pass dump `RSX_ENGINE_PASS_DUMP_AFTER=3`):
  a clear to 0, then `DRAW_ARRAYS prim=8 (QUADS) first=4 count=4` into the display buffer
  (`0x004A0000` / `0x00100000`, A8R8G8B8 1280x720). It runs the game's own programs (log:
  `pipeline 933ade52...: guest vp 2, fp 1, 0 constants -> ok`), not the engine's built-in pair.
- It samples ONE texture: `t0 1:0x00789E80 fA5 1280x720 p5120` = A8R8G8B8 with the LN (linear)
  bit, in MAIN memory, filter `0x02022000` (bilinear, no mips), control0 `0x80000000`,
  wrap `0x10030303` (clamp). Probably the game's decoded `LOADING.BMP` (subsystems.md file
  list); BMP files store rows bottom-up.
- The result is mirrored vertically only (not horizontally): "Loading..." reads upside down.
- Every later screen (ESRB car, Psyonix logo, menus, arena, HUD) is upright.
- **Dead end:** honouring `NV4097_SET_SHADER_WINDOW` (0x1D88) bottom-left origin (bits 12-15 = 1)
  in the draw engine's viewport epilogue (`rsx_draw_engine.c`, the `xf[1]`/`xf[5]` y terms),
  plus front-face swap and scissor mirror, made Loading upright but turned the arena's final
  composite + HUD upside down. So that pass also has origin = bottom and was already right.
  Not committed.

## Hypotheses, most likely first
1. **`first=4` on a QUADS draw.** The game draws vertices 4..7 of its vertex buffer. If the
   engine's quad -> triangle conversion (`rsx_draw_engine_write_topology_indices`, the QUADS
   path in `sink_end`, `dc.idx`/`dc.arr` ranges) or the vertex fetch base ignores `first`, it
   draws vertices 0..3 instead: very possibly the same quad with the V coordinates the other
   way round (UE3's screen-quad helpers keep a flipped and an unflipped set). Check: log the
   fetched positions/UVs for this draw (decoded vertices 0..3 vs 4..7 of the stream), or force
   first=0 / first=4 and see which one draws upright. Cheap and the best lead.
2. **Viewport sign.** Compare `SET_VIEWPORT_SCALE/OFFSET` y (vp.scale[1], vp.translate[1]) and 0x1D88
   for this draw vs the arena composite draw. If Loading has origin bottom with a POSITIVE y
   scale and the composite has origin bottom with a NEGATIVE one, the correct rule is
   "flip when origin is bottom" AND the composite is wrong for another reason (or vice versa).
   The window-origin experiment proves the two draws differ in something else.
3. **Texture rows.** A linear (LN) texture's row 0 is at the lowest address on RSX; the decoder
   (`rsx_texture_layout.c` linear path) agrees. If the game really uploads the BMP bottom-up and
   relies on the UVs (v from 1 to 0) to flip it, then the UVs are being lost (back to 1).
   Dump the texture with `RSX_ENGINE_PASS_DUMP_TEX=1`: if the dumped texture is upside down too,
   the draw is right and the texture is stored flipped, so the bug is in which UVs reach the
   shader.
4. **Vertex program input / constants.** vp 2 has 0 constants. Check which attribute carries
   the UV and whether its type is decoded right (e.g. a signed/unsigned normalised type, or a
   half type read wrongly, turning v=1 into 0). Also whether position.y comes from a
   different stream offset than the UV.
5. **Surface/target orientation.** This draw goes straight into the display buffer; later screens
   draw into an offscreen target and composite. If the display-buffer path (present blit in
   `rsx_vulkan_backend.c` `vk_eng_present`) or `SET_SURFACE_FORMAT`'s origin bits differ between
   "drawn into the display buffer" and "copied into it", one of the two is flipped. Check the
   surface format register's origin field for this draw vs a menu draw.
6. **Inline / immediate vertex data.** If the quad's vertices come from inline arrays
   (`INLINE_ARRAY`) or immediate `VERTEX_DATA` methods rather than a vertex buffer, check that
   path's attribute order (`rsx_vertex_compact.c` inline branch).

## Recipe
`RSX_ENGINE_PASS_DUMP=<dir> RSX_ENGINE_PASS_DUMP_AFTER=3 RSX_ENGINE_PASS_DUMP_DRAWS=1
RSX_ENGINE_PASS_DUMP_TEX=1 RSX_ENGINE_PASS_DUMP_MAX=6 tools/boot_check.sh 14 --version 0109`
(under `tools/task.sh lock boot`); `presentNNN.ppm` shows the frame, `tex_00789E80_*` the texture.
Any fix must leave the arena composite/HUD upright: check with a 105 s run
`--pad 'cross@40*4/5,cross@70,r2:120@85'` and look at `frame_last.png`.

## Done when
Loading screen upright in a capture, other screens unchanged.

## Log
- 2026-10-20 18:31 claude: claimed
- 2026-10-20 18:37 claude: Findings 2026-10-20: the Loading screen is one draw (pipe 1) sampling a linear A8R8G8B8 1280x720 texture in MAIN memory (1:0x00789E80, pitch 5120; presumably the decoded LOADING.BMP, which is stored bottom-up) into the display buffer. Tried: honour NV4097_SET_SHADER_WINDOW (0x1D88) origin bits 12-15 = 1 (bottom-left) in the draw engine (y mapping in the viewport epilogue, front-face swap, scissor mirror). The Loading screen came out upright, BUT the arena's final composite/HUD pass came out upside down, so that pass also has the bottom-left origin and was correct before: the window origin alone is not the difference. Reverted, not committed. Next: log 0x1D88, the viewport scale/translate and the draw's UVs/vertex positions for the Loading draw vs the arena composite draw (pass dump first-draw line), and check whether the game expects the BMP rows flipped (a texture-orientation issue rather than a window one).
- 2026-10-20 18:37 claude: RELEASED: HANDOFF: window-origin fix tried and reverted (breaks the arena composite); see the findings note above. state=no code change; next=compare 0x1D88/viewport/UVs between the Loading draw and the arena composite draw.
- 2026-10-20 18:42 claude: claimed
- 2026-10-20 19:03 claude: RELEASED: overtaken by antigravity
- 2026-10-20 19:03 antigravity: claimed
