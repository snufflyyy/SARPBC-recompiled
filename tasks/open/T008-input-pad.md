# T008: Controls — gamepad and keyboard into cellPad for a car game

Status: open
Owner: -
Touches: src/overrides/input_*.cpp (new), patches/ps3recomp/T008-*.patch (libs/input/** only), docs/subsystems.md (Input section only), config.toml ([input] section)
Reads: external/ps3recomp/libs/input/cellPad*.c, docs/game-profile.md

## Goal
The game reads cellPad (GetData, GetInfo2, SetPortSetting 0x2 = press mode, SetActDirect
= rumble), cellKbRead and cellMouseGetDataList. Make sure ps3recomp's SDL2 pad backend
delivers what a Rocket-League-style game needs: both sticks, analog L2/R2 (throttle/brake)
including pressure-sensitive values when press mode is on, rumble through SDL, and a
sensible keyboard default (WASD/arrows, space = jump, shift = boost, ...). Verify with
PAD_SCRIPT where possible and document the default bindings.

## Done when
A documented, verified mapping (log evidence of pressure/analog values reaching the
game), rumble wired, defaults in config.toml or code, notes in docs/subsystems.md.

## Log
- 2026-10-18 23:50 agent-input: claimed
- 2026-10-19 00:05 agent-input: Ported soyjxck/ps3recomp's 13 libs/input commits (SDL pad thread, pads by instance id, rumble held, cellPad_set_host_input, host kind) as patches/ps3recomp/T008-1-dod3-cellpad-sdl2-port.patch, authorship kept, libs/input part only (all applied cleanly: upstream libs/input unchanged since fork base 5244db9). T008-2-cellpad-racing-fixes.patch: (1) press mode topped any set digital bit to 255 -> half-pulled R2 read 255 (verified: fork code R2=255, fixed R2=127 for a half pull); (2) small motor is on/off, was x257 = imperceptible -> 0xFFFF; (3) empty SDL port sticks were 0 (port 0 always present -> stick held up-left) -> 128; + PAD_TRIGGERS, PAD_TRACE. Test libs/input/tests/test_cellpad_sdl.py (SDL virtual gamepad) PASS 36 checks. Game facts (01.09): GetData buffer at caller r1+0x80 in func_000D101C; sticks (v-127)/127, L2/R2 = press words 0xA8/0xAA * 1/255, sensors read only under flags; SetPortSetting(port,2) only if GetInfo2 capability has PRESS_MODE (func_000D1AF4); rumble func_000D35D8: small motor 0/1 duty-cycled, large 0-255; cellKbRead/cellMouseGetDataList have NO callers and no Init imports. Note for coordinator: the patches/ps3recomp/README.md table needs two rows (not in my Touches).
- 2026-10-19 00:06 agent-input: HANDOFF: done=T008-1 (dod3 cellPad port, 13 commits, authors kept) + T008-2 (racing fixes: trigger pressure, small motor on/off, centred empty ports, PAD_TRIGGERS, PAD_TRACE; test libs/input/tests/test_cellpad_sdl.py PASS 36 checks, negative-checked against fork code) exported and apply cleanly from the pin (22 patches); src/overrides/input_config.cpp (config.toml [input] UPPER-CASE keys -> env, syntax-checked, NOT built or run); docs/subsystems.md Input updated. state=no in-game run with the new patches yet (build-0109 was built before the port); no keyboard on Linux yet. next=(1) write src/overrides/input_kbm.cpp: port dod3 src/input/kbm.cpp (in the scratchpad clone, or github soyjxck/dod3-recomp) with an SDL key source (SDL_GetKeyboardState by scancode, SDL_GetMouseState buttons, wheel via SDL_AddEventWatch, focus = SDL_GetKeyboardFocus()!=NULL), register it with cellPad_set_host_input from a static constructor that first calls sarpbc_input_config(), and lazily SDL_SetEventFilter to drop the Esc KEYDOWN so Esc can be START; car defaults KEY_R2=W KEY_L2=S KEY_MOVE_*=WASD KEY_CROSS='Space Mouse2' KEY_CIRCLE='Shift Mouse1 Backspace' KEY_SQUARE=Ctrl KEY_TRIANGLE=R KEY_L1=Q KEY_R1=E KEY_L3=C KEY_R3=V KEY_START='Esc Enter' KEY_SELECT=Tab KEY_UP..RIGHT=arrows KEY_LOOK_*=IKJL; (2) add these as KEY_* lines to config.toml [input] and a bindings table to docs/subsystems.md; (3) rebuild build-0109 under the lock, then run 'PAD_TRACE=1 PAD_TRIGGERS=0,128,5 BUILD_DIR=build-0109 tools/boot_check.sh 60 --version 0109' and grep '[cellPad] trace' to show R2=128 reaching the game's buffer (if the boot gets that far: baseline exits at PhysX/GUIDCACHE before menus); (4) coordinator: add the two T008 rows to patches/ps3recomp/README.md (not in my Touches). Follow-ups: mouse camera (dod3 camera.cpp, address-specific), button prompts by host kind. branch=worktree-agent-ab345549dd2d5074c
- 2026-10-19 00:06 agent-input: RELEASED: paused for usage; see HANDOFF note
