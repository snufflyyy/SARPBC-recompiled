# T008: Controls — gamepad and keyboard into cellPad for a car game

Status: claimed
Owner: agent-input
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
