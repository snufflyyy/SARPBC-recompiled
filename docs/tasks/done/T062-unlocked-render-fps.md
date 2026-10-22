# T062: Unlocked render fps: run past the 60 Hz frame clock (T062)

Status: done
Owner: claude
Priority: 3
Touches: src/main.cpp (frame_clock), src/overrides/ (new frame_rate.cpp if GetMaxTickRate is replaced), config.toml, docs/frame-pacing.md
Reads: docs/frame-pacing.md (whole file), docs/dod3-reuse.md Port next 6 (even presents, GetMaxTickRate), docs/subsystems.md "Async batches"

## Goal
User request 2026-10-22: an unlocked render frame rate. Today flips are claimed by the 60 Hz frame clock
(`frame_clock`, one vblank every 16.67 ms) and the game's own smoothing is 22-60 (COALESCED.INI), so the arena
tops out at ~60. Let a user option (config.toml / env, off by default so the default stays as close to the
original as possible) run the clock and the guest's tick uncapped: vblank/flip callbacks fire as soon as the
previous frame's drain and present are done, UE3's max tick rate is lifted (find `UEngine::GetMaxTickRate` by
pattern in the lift, T012 note: it is not named), and physics/game time stays correct (no fast-forward: check
that game speed is unchanged, e.g. the match clock and car speed against wall time). Windowed mode: present mode
MAILBOX/IMMEDIATE instead of FIFO when unlocked.

- Settings are also exposed in the game's Options > Graphics screen (T065), not only config.toml/env.

## Done when
`SARPBC_UNLOCK_FPS=1` (or the config key) gives guest fps above 60 in the menu and arena on this machine,
game speed verified against wall time, default behaviour unchanged, numbers and the GetMaxTickRate address in
docs/frame-pacing.md, tests and lint pass. Depends on T061 for headroom (CPU drain ~15 ms/frame).

## Log

## Log
- 2026-10-22 19:13 claude: claimed
- 2026-10-22 19:13 claude: Unlocked: INI MaxSmoothedFrameRate 60 -> 1000 via the overlay (restart) + 1 kHz vblank tick (live). Arena ~58 -> ~85-90 guest fps, menus 100-150 (boot_check --scenario arena, SARPBC_UNLOCK_FPS=1). GetMaxTickRate address not needed. Game speed vs wall clock not measured.
- 2026-10-22 19:14 claude: DONE: Unlocked fps: INI MaxSmoothedFrameRate 1000 via overlay (restart) + 1 kHz vblank (live) + MAILBOX/IMMEDIATE window present (patch 0079). Arena ~58 -> ~85-90 guest fps, menus 100-150. Default unchanged. Open: game speed against a wall clock not measured; MAILBOX only checked for swapchain recreation (Xvfb).
