# T012: Frame clock and pacing for UE3 — design from Drakengard 3, measured here

Status: done
Owner: claude
Priority: 18
Touches: docs/frame-pacing.md (new); src/overrides/frame_*.cpp (new) only after T001 is done
Reads: src/main.cpp (frame_clock), dod3-recomp src/main.cpp + docs/TECHNICAL.md, external/ps3recomp/libs/video/cellGcmSys.c

## Goal
Our frame clock is the template's: a host thread ticks vblank/flip at ~60 Hz on a 4 ms
sleep and drains the GCM FIFO. Drakengard 3 needed more for UE3: draining on every
guest usleep kick, a native replacement for the render thread's fence poll,
`UEngine::GetMaxTickRate` replaced for an uncapped/fixed rate, Bink ticked faster while
movies play, and loading-screen idle spent in the async loader. Measure what this title
does now (vblank/flip rates, render-thread fence waits, `[HOTREAD]`/usleep spin sites,
GCM label waits) and write a concrete design: which of dod3's changes apply, the guest
addresses here (find `GetMaxTickRate` etc. by pattern/strings), and expected effects.
Implement only once T001 has merged (it owns src/main.cpp).

## Done when
docs/frame-pacing.md has measurements and a ranked change list with addresses; follow-up
implementation tasks are proposed.

## Log
- 2026-10-21 02:00 claude: claimed
- 2026-10-21 02:00 claude: docs/frame-pacing.md written: measurements (arena frame clock 87% busy in FIFO drain), game's INI frame settings, dod3 change table, ranked follow-ups.
- 2026-10-21 02:00 claude: DONE: 
