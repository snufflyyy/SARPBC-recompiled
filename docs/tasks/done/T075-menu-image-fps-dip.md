# T075: Fix the fps dip when images appear in the main menu (minigame select)

Status: done
Owner: claude
Priority: 1
Touches: patches/ps3recomp/0085-0088 (runtime/spu/spu_workload.c, spurs_job.c, libs/spurs/cellSpurs.c, runtime/ppu/ppu_loader.cpp), docs/subsystems.md, docs/status.md
Reads: docs/subsystems.md "Menu frame rate" and "SPU job fingerprint memo", docs/dod3-reuse.md

## Goal
User, 2026-10-23: "fix the fps slowdown when images appear in the main menu, specifically when selecting a minigame."
Reproduced with `tools/boot_check.sh --scenario single`: main menu ~59 fps, Single Player ~35, Mini-Games a steady **15**.

## Done when
The Mini-Games screen runs well above 15 fps with the arena and menus unchanged (verified: ~38 fps, Single Player ~59,
arena ~59, no alerts), the patches are exported and the test passes.

## Log
- 2026-10-23 16:18 claude: claimed
- 2026-10-23 17:20 claude: Cause: the ShaderPatching job chain. The game appends one job per draw and Runs the chain; the Mini-Games screen has ~1000 draws a frame. Measured (temporary timers): 14,600 jobs/s at 67 us each = one core, and the render thread waits for them. Per job: 46 us byte-wise FNV of the 48,512-byte image, 19 us spu_context_init memset (268,864 bytes), 3 us calloc, ~5 us copy-out of the store, 4 us the job itself. After that, 17,000 Runs/s each started a host thread (1.1 jobs per walk). Then 21% of the render thread in barrier_watch_hit (debug store watches, every guest store).
- 2026-10-23 17:20 claude: Fixes (patches 0085-0088): fingerprint memo (content-verified), pooled job contexts + lazy store copy, walker lingers 1 ms (SPURS_JC_LINGER_US), PPU store watch gate. Mini-Games 15 -> 38 fps, Single Player 35 -> 59, arena 59 steady, menu 59. The rest on Mini-Games is the FIFO drain: ~1000 draws a frame at ~6 us each (frame clock 61% busy).
- 2026-10-23 17:24 claude: DONE: Mini-Games 15 -> ~38 fps, Single Player 35 -> ~59, arena 59 steady: ShaderPatching job chain made cheap (patches 0085-0088: fingerprint memo, pooled job contexts, walker linger, PPU store-watch gate). Remaining limit there is the FIFO drain (~1000 draws a frame). subsystems.md 'ShaderPatching job chain'.
