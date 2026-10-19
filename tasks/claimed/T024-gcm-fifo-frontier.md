# T024: 01.09 menus: GCM FIFO jump-to-self at io 0x8B144 + fork GCM flip/FIFO fixes

Status: claimed
Owner: agent-gcm
Touches: patches/ps3recomp/T024-*.patch (libs/gcm/**, runtime/rsx/**, libs/video/** only), src/overrides/gcm_*.cpp (new), docs/subsystems.md (Graphics section only)
Reads: docs/dod3-reuse.md (T023's ranked GCM list), docs/debugging.md, tasks/done/T023*

## Goal
**User priority (2026-10-19): get 01.09 into the menus.** T023 found that during loading the GCM
FIFO walker does 3 "stuck-get" resyncs (~120 KB of commands dropped). With fork commit 0014 plus
`GCM_FIFO_NO_RESYNC=1`, the FIFO parks on a jump-to-self at io `0x0008B144` (word `0x2008B144`)
right after vertex-array setup, and nothing overwrites it. Find out who is supposed to write it
(an SPU job such as Edge Geometry? a PPU thread waiting on a label / flip?) and make the boot
progress. Port the fork's GCM fixes in T023's ranked order when they help: 0049 (prepared flips
in FIFO order), 0018 (user-command queue), 0014/0024 (jump-to-self waits), then 0112, 0059/0062,
0096/0111, 0139. agent-frontier2 (T022) owns libs/spurs and the job guard 0x0133AA80; coordinate
through task notes if the two turn out to be the same stall.

## Done when
The boot gets measurably further toward the menus (boot_check summary before/after, frames
drawn), causes written in docs/subsystems.md Graphics.

## Log
- 2026-10-19 09:29 agent-gcm: claimed
- 2026-10-19 09:30 agent-gcm: baseline: boot_check 2026-10-19 09:30 v01.09 1e5406b 60s: STALLED since 21.6s | last open GUIDCACHE.XXX@4.1s | pkgs 13 (GUIDCACHE last) | zlib 3147 | dumps 5 lit 5 distinct 2 | flips 7 | threads 13/8 alive | unresolved 0 | alerts open-fail,assert (SPU_INTERP_UNLIFTED=1 BUILD_DIR=build-0109)
- 2026-10-19 09:32 agent-gcm: T022 (agent-frontier2 note 09:27) already found who releases the park: FIFO user command 0xEB00 -> user handler 0xDC390 -> cellGcmSetFlipImmediate -> flip handler func_000DC144 patches the park. Not a SPURS job. The pump only runs at HLE imports, the RenderingThread sleeps in sys_timer_usleep (a syscall), so delivery is late and stuck-get resyncs past the park after 8 drains. Plan: port fork 0018+0139, keep self-JUMP parks (no resync), deliver user commands on a GCM interrupt thread.
- 2026-10-19 09:41 agent-gcm: Findings with GCM_PARK_LOG=1 SPU_INTERP_UNLIFTED=1 GCM_INTR_THREAD=1: two park writers. a) flip handler via user cmd 0xEB00 -> handler 0xDC390 -> SetFlipImmediate -> func_000DC144, patches park to JUMP+4 in ~5 ms. b) ShaderPatching chain 0x012B6F00 writes 0 over the park in 12-21 ms, each followed by chain END. Every park through io 0xD3C64 is now patched, ref reaches 0x417C8. Park at io 0xD494C never patched though the chain ran 227 jobs after it; jump-park grace resyncs past it = T022 cause 2. Without SPU_INTERP_UNLIFTED the FIFO idles at get==put ~0x6FF0C: PhysX thread blocked in cellSpursQueuePopBody func_008482B8, main in sys_cond_wait func_008FB230 = T025 area. Last: boot_check 2026-10-19 09:40 v01.09 938edec 60s: STALLED since 21.6s | last open GUIDCACHE.XXX@3.6s | pkgs 13 | zlib 3147 | dumps 4 lit 4 distinct 1 | flips 8 | threads 13/9 alive | unresolved 0 | alerts assert
- 2026-10-19 09:41 agent-gcm: HANDOFF: done=T024-1 fork 0018 user-command queue, T024-2 fork 0139 pump fast exit, T024-3 GCM_INTR_THREAD=1 interrupt thread + stuck-get skips self-JUMP parks + GCM_PARK_GRACE_MS + GCM_PARK_LOG, docs/subsystems.md Graphics; state=builds build-0109, 44 patches apply clean, GCM_INTR_THREAD not yet defaulted for SARPBC, frontier unchanged STALLED 21.6s because the remaining park waits on T022 SPURS chain fix and PhysX T025; next=after T022 merges chain fix + gcm_inject_base retest with GCM_INTR_THREAD=1 vs T022 lv2_syscall pump experiment which reached ESRB, then default it via new src/overrides/gcm_config.cpp setenv, then fork 0049 PrepareFlip in FIFO order. Caveat: ppu_guest_call uses fixed callback stack 0xCFFE0000 on every thread so concurrent or nested callbacks share a stack, runtime/ppu bug, propose a task; branch=worktree-agent-a7b0200633f5a06f1
- 2026-10-19 09:41 agent-gcm: RELEASED: paused; see HANDOFF
- 2026-10-19 10:04 agent-gcm: claimed
- 2026-10-19 10:10 agent-gcm: resumed on main 171c84d (relifted, 0028) + experiment rwlock hunk (2) applied locally. Default (grace 50, no intr thread) now reaches ESRB screen with car: boot_check 2026-10-19 10:08 v01.09 171c84d 90s: STALLED since 37.7s | last open TEXTURES.TFC@8.6s | zlib 3279 | flips 36 | alerts assert (no SPU_INTERP_UNLIFTED). Stops because jump-park grace resyncs past park io 0x2D269C (after user cmd 0xEB00); SetFlipImmediate arrives right after the resync. Comparing intr thread / large grace next.
