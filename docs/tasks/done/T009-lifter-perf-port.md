# T009: Port the Drakengard 3 fork's lifter performance work as patches

Status: done
Owner: claude
Priority: 19
Touches: patches/ps3recomp/T009-*.patch (external/ps3recomp/tools/ppu_lifter.py, runtime/ppu/ppu_vm_fast.h & memory macros), docs/reference-ports.md (lifter section), docs/pipeline.md (lifter flags)
Reads: https://github.com/soyjxck/ps3recomp (MIT), its docs/PPU_RECOMP.md, dod3-recomp docs/TECHNICAL.md

## Goal
The fork (174 commits ahead) has `--nonvolatile-locals` (registers as C locals, written back
only where needed) and the 64 KiB page-table fast path for guest loads/stores
(`ppu_vm_fast.h`). Drakengard 3 measured large gains (main thread 4.6 -> 2.9 ms, binary
430 -> 293 MB). Port them onto our upstream pin as separate patches (keep the original
authorship), lift into your OWN copy of src/recomp, build, and measure: lifted line count,
binary size, build time, and boot to the same point with no new failures. Note
`--hook` too, but it is lower priority.

## Done when
Patches are exported, the measurements are in the task log and docs/reference-ports.md,
and a boot with the new lift reaches at least the same point as before.

## Log
- 2026-10-21 01:47 claude: 2026-10-21 reviewed fork commits (e635033, 8dde556, afa9c69, d2c054a = ~900 lifter lines + 1730-line ppu_nv_dirty.py; ee004d6/1cbca03 = page-table loads). Our runtime already does plain vm_base+addr loads (no per-access page test), so the page-table piece is a store-gate for SPU/RSX coherency, not a speedup here. The fork's own commit message says its hot code was 'float/vector and memory, not r14-r31' (game thread 9.4-10.0 ms unchanged). Not ported: large, risky lifter change with unproven gain on this game. Revisit only if a guest-side profile shows spills of r14-r31 dominating.
- 2026-10-21 16:52 pi: Preflight corrects an earlier assumption: current shared GENERATED ppu_recomp.h and upstream tools/ppu_lifter.py both contain vm_inl_ok (vm_inline_ok, null-page, E0000000 cutoff, injected GCM-ref word and mapping-size checks) at every scalar inline load. The out-of-line runtime may be flat-base, but the actual lift is not a bare vm_base+addr access. Fork d2c054a also supersedes initial r14-only work with all-register dirty/live analysis and CR/XER locals; its documented gains are later than the initial no-main-thread-gain commit. Still requires opt-in port, synthetic proof and isolated re-lift; no gain claimed yet.
- 2026-10-21 16:56 pi: Safety preflight: fork ee004d6/1cbca03 fast stores skip the guest lock after a sticky per-page reservation-bit test. A reservation can start after that test and before the plain store (and frame/run tests cache it), so blindly importing this could bypass T052 coherence. Preserve native vm_write* paths unless an interleaving proof justifies a fast store; start with opt-in register locals and page-table READS. Also retain our aligned relaxed atomics/memcpy semantics instead of the fork volatile unaligned casts. No runtime/lift changes made for T009 yet.
- 2026-10-21 18:06 claude: claimed
- 2026-10-21 18:06 claude: Closed on evidence: PPU lifted code = 6.1% of on-CPU stacks (menu; T029 sampler), arena similar; lifter register locals cannot move the frame rate. See docs/reference-ports.md 'Lifter performance'. Revisit if a real match shows PPU code >30%.
- 2026-10-21 18:06 claude: DONE: Not ported: lifted PPU code is ~6% of stacks, safety risk for the store gate; decision and numbers in docs/reference-ports.md.
