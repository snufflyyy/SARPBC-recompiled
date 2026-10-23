# T073: Multiplayer edges: voice, stats, leave/abandon, known mod crashes

Status: open
Owner: -
Priority: 17
Touches: src/overrides/online_*.cpp, patches/ps3recomp/NNNN-voice-*.patch (libs/audio or libs/misc cellVoice), docs/multiplayer.md, docs/online.md
Reads: docs/multiplayer.md (sections 4, 9), docs/multiplayer-protocol.md, tasks T070, T071

## Goal
Part of the multiplayer port (umbrella T015). The match works (T071); make the rest not hurt:

1. **cellVoice** (10 imports, replaced cellMic in 01.09): init/ports/`WriteToIPort`/`ReadFromOPort` must not fail;
   no audio capture is required (the port has no microphone path). Headset-present reports false. Check the
   game's `OnlineVoiceInterfaceImpl_PS3` functions do not block.
2. **Stats and leaderboards**: `ClientWriteOnlineStats*`, `TAStats`, the end-of-match stats write and any read:
   what the server returns, what the client shows; Score library context calls (only ctx create/destroy are
   imported) must return success.
3. **Leave/abandon/disconnect**: `TrackPlayerAbandon`, `TrackPlayerTimePlayed`, host quits mid-match, client
   unplugs (kill -STOP one instance), server disappears during a match; timeouts and messages.
4. The mod's known issues (docs/multiplayer.md section 2): scoring a goal on **Galleon** crashes, saving a
   **replay** crashes ("fails to allocate memory" under RPCS3). Test each on the recomp offline and in a match;
   fix or document as non-goal with evidence.
5. Input: if the mod changes input handling (deadzones), mirror it in the overlay or document the difference.
6. NAT-type edge cases, four-player lobbies, wrong-region `LocationUrl` (`bbUS`/`bbJP`).

## Done when
Each item has a test (a boot_check scenario or a unit test) or a written non-goal with the evidence. No stall
or alert in a 10-minute two-instance session.

## Log
- 2026-10-23 claude: created from the multiplayer research.
