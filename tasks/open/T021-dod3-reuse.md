# T021: Reuse Drakengard 3's port — inventory, then port the generic pieces

Status: open
Owner: -
Touches: docs/dod3-reuse.md (new), docs/reference-ports.md, patches/ps3recomp/T021-*.patch (runtime/** and libs/** pieces NOT owned by an active task: see "Exclusions"), src/overrides/dod3_*.cpp (new)
Reads: https://github.com/soyjxck/dod3-recomp and https://github.com/soyjxck/ps3recomp (both MIT), docs/reference-ports.md, tasks/claimed/*

## Goal
**User directive (2026-10-18): reuse as much as possible from the other UE3 ps3recomp port.**
1. Inventory every dod3-recomp component and every fork commit on soyjxck/ps3recomp
   (174 ahead of the upstream pin's base). For each, record what it does, whether it is
   generic (runtime/HLE), UE3-generic (needs address re-finding: dod3 is UE3 v860, ours is v539
   (01.02) / 01.09), or Drakengard-specific, plus its applicability here, the effort, and which
   task owns that area. Write this up as docs/dod3-reuse.md: a ranked table with links to the source.
2. Port the generic runtime/HLE fixes that no active task owns, as patches with original
   authorship kept (`git format-patch` from the fork where it applies; otherwise a port with
   "Ported from soyjxck/ps3recomp <sha>" in the message). Likely candidates: user-mode
   sys_lwmutex, sys_lwcond wakeups, the guest memory page-table fast path, SPU task thread
   pooling, MFC/reservation per context, frozen guest clocks, RSX texture write-watching, and
   occlusion-query sync.
3. For each UE3-generic piece (frame clock, GetMaxTickRate, load_idle, native GC, Bink tick rate,
   prompts, camera), write how to find the corresponding addresses in our EBOOT (strings,
   patterns, call sites) and propose follow-up tasks.

## Exclusions (owned by active tasks, so only inventory these and tell the coordinator)
SPURS queue/LFQueue (T019), MultiStream/MP3/audio (T007), input incl. kbm/camera (T008),
HLE wait gaps (T020), lifter perf `--nonvolatile-locals`/`--hook` (T009, open).

## Done when
docs/dod3-reuse.md is complete; generic ports are exported as patches with tests or boot evidence;
follow-up tasks are proposed.

## Log
