# T044: Arena renders corrupt frame then stalls in flip callback after loading challenge

Status: claimed
Owner: pi
Priority: 1
Touches: patches/ps3recomp/T044-*.patch (libs/video/cellGcmSys.c, runtime/ppu/ppu_hle.cpp only if needed), src/overrides/gcm_*.cpp, docs/subsystems.md (Graphics), docs/debugging.md (arena frontier)
Reads: docs/tasks/claimed/T037-arena-hang-after-new-game.md, docs/subsystems.md (Graphics), docs/debugging.md

## Goal
After T037's attribute argument + slab service repairs, the game loads both MP_SOCCARARENA and PYRAMID_COLLECTBOOST, then stops presenting at ~77s. RenderingThread is inside flip handler func_000DC144 polling a park-table slot. The last frame is corrupt. Establish the callback/presentation root cause and reach an interactive arena; do not fake physics or skip fences.

## Done when
Cause identified with evidence and a boot gets further, with rendered frames checked. Offline driving is verified if possible; remaining blockers are explicitly recorded rather than called playable.

## Log
- 2026-10-20 pi: Spawned from T037 verification. Evidence in .worktrees/pi/analysis/boot_check/20261020-093821-685745/ and captures of that id. Old slab-service hang is cleared; frame capture is mostly black with corrupt small rectangles. No unresolved imports, no unlifted SPU branches.
- 2026-10-20 09:42 pi: claimed
- 2026-10-20 09:44 pi: Backtrace proves callback affinity issue: RenderingThread LWP698717 is func0x000DC144 -> ppu_guest_call -> ppu_gcm_pump -> ps3_hle_call -> func0x000DD214/0x000EE334 (run20261020-093821). Pump may steal callbacks on any HLE caller even with GCM_INTR_THREAD=1. Flip handler polls the render-owned park slot, so executing it on RenderingThread can wait for its own suspended caller. Plan: when dedicated interrupt thread is active, only it may pump; retain legacy/manual fallback when no worker started. Do not bypass parks or synthesize flips. Wait for current normal-build verification to finish before editing shared GCM source in worktree.
- 2026-10-20 09:47 pi: Standalone real-production pump regression failed on old code: foreign HLE caller stole callbacks while an interrupt worker was published. New worker-affinity gate leaves notifications pending on foreign threads; worker drains commands in FIFO order; no-worker/startup-failure fallback still pumps. GCC/Clang regression and PrepareFlip tests pass. Building before next arena boot.
- 2026-10-20 09:51 pi: Affinity patch now includes actual mocked CreateThread failure: the event is closed/cleared and manual HLE delivery remains usable. Both compilers pass; old production pump failed ownership regression. Ported neither shader code nor game code. Full runtime patch exported as T044-gcm-interrupt-affinity; arena boot with R2/jump/boost inputs is running.
- 2026-10-20 09:55 pi: 150s affinity boot verifies deadlock cleared: final10s dumps5 distinct5, total67 dumps66distinct, flips7755 (vs3316 then no presents previously), zlib3714, no unresolved imports, slab+mixer alive. End RenderingThread in idle sleep, not flip handler. R2/jump/boost PAD_FILE delivered; rumble observed. However arena frame remains mostly black/corrupt, so offline driving is not visually verified. Evidence run20261020-094804-706462 and .worktrees/pi/analysis/affinity-boot-report.txt. Next isolate rendering corruption with VK_BATCH=0/GEO_CACHE=0; no fake fences/completions were introduced.
