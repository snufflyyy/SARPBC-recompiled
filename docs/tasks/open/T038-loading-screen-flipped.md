# T038: The 'Loading...' screen is drawn upside down (render-target orientation)

Status: open
Owner: -
Priority: 13
Touches: patches/ps3recomp/T038-*.patch (runtime/rsx/** orientation only), docs/subsystems.md (Graphics)
Reads: docs/subsystems.md

## Goal
From T028: the "Loading..." screen is drawn upside down. This is probably a render-target or present Y-flip mismatch between RSX surface origin and Vulkan. Check whether other screens are right (ESRB, menu look right), find the case that differs (window origin / surface clip / shader viewport), and fix it generally.

## Done when
Loading screen upright in a capture, other screens unchanged.

## Log
- 2026-10-20 18:31 claude: claimed
- 2026-10-20 18:37 claude: Findings 2026-10-20: the Loading screen is one draw (pipe 1) sampling a linear A8R8G8B8 1280x720 texture in MAIN memory (1:0x00789E80, pitch 5120; presumably the decoded LOADING.BMP, which is stored bottom-up) into the display buffer. Tried: honour NV4097_SET_SHADER_WINDOW (0x1D88) origin bits 12-15 = 1 (bottom-left) in the draw engine (y mapping in the viewport epilogue, front-face swap, scissor mirror). The Loading screen came out upright, BUT the arena's final composite/HUD pass came out upside down, so that pass also has the bottom-left origin and was correct before: the window origin alone is not the difference. Reverted, not committed. Next: log 0x1D88, the viewport scale/translate and the draw's UVs/vertex positions for the Loading draw vs the arena composite draw (pass dump first-draw line), and check whether the game expects the BMP rows flipped (a texture-orientation issue rather than a window one).
- 2026-10-20 18:37 claude: RELEASED: HANDOFF: window-origin fix tried and reverted (breaks the arena composite); see the findings note above. state=no code change; next=compare 0x1D88/viewport/UVs between the Loading draw and the arena composite draw.
