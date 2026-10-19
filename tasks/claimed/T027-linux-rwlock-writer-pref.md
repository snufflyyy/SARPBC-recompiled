# T027: Linux rwlock writer preference (SPU DMA lock mfc_for starves ShaderPatching)

Status: claimed
Owner: agent-rwlock
Touches: patches/ps3recomp/T027-*.patch (runtime/platform/** only), docs/build-linux.md
Reads: patches/experimental/T022-esrb-experiment.diff (its win32_compat.h hunk), tasks/open/T022*

## Goal
**Menus-first.** Found by T022: on Linux the shared SPU DMA lock (`mfc_for`) starves its writer:
dozens of spinning PhysX SPU threads keep taking the read lock, so the ShaderPatching job can't
take the write lock and the ESRB screen stops after 8-25 s. In T022's experiment, writer-preferring
locks (`pthread_rwlockattr_setkind_np(PTHREAD_RWLOCK_PREFER_WRITER_NONRECURSIVE_NP)`, glibc) fixed
it. Turn the experiment's `runtime/platform/win32_compat.h` hunk into a clean, portable patch
(Windows SRWLOCK is unaffected; macOS has no setkind, so keep it `#ifdef __GLIBC__`). Add a test
if one can show starvation.

## Done when
The patch applies in the stack. Show a boot_check line from a run that also has the T024 GCM park
fix, where the ESRB screen keeps going past 25 s.

## Log
- 2026-10-19 10:04 agent-rwlock: claimed
- 2026-10-19 10:09 agent-rwlock: Patch T027-win32-compat-srw-writer-preference.patch: ps3__rwl_init uses PREFER_WRITER_NONRECURSIVE_NP on glibc. Audited every shared-side user (mfc_for spu_channels.c:295, spurs_port_queue cellSpurs.c:774, sq_spurs_of cellSpursQueue.c:312, lv2_register.c:1642 SPU port lookup, SleepConditionVariableSRW shared mode): all leaf lookups, no recursion, no waits while held. sys_rwlock (guest) uses raw pthread_rwlock on POSIX, unaffected. New test test_srw_writer_progress in test_win32_compat.c: before fix 0/20 writes in 3 s, after 343/343 pass (clang+gcc, taskset 1/2/4 cores).
- 2026-10-19 10:12 agent-rwlock: Run 1 (patch + GCM_INTR_THREAD=1, 90 s, load avg 107 from other agents): boot_check 2026-10-19 10:12 v01.09 e305d1b+dirty 90s: STALLED since 34.8s | last open TEXTURES.TFC@33.8s | pkgs 13 (GUIDCACHE last) | zlib 3259 | dumps 25 lit 25 distinct 1 | flips 19 | threads 13/8 alive | unresolved 0 | alerts assert. Still 'Loading...': one 'FIFO resync (jump-park) 0x424' at 34.8s (50 ms grace too short under load) dropped the fence. Not the rwlock. Rerunning with GCM_PARK_GRACE_MS=600000 (= experiment hunk 1, never skip a park).
- 2026-10-19 10:15 agent-rwlock: Run 2 (patch + GCM_INTR_THREAD=1 GCM_PARK_GRACE_MS=600000 GCM_PARK_LOG=1, 90 s, load avg ~119): boot_check 2026-10-19 10:14 v01.09 e305d1b+dirty 90s: STALLED since 61.6s | last open TEXTURES.TFC@34.5s | pkgs 13 (GUIDCACHE last) | zlib 3279 | dumps 29 lit 28 distinct 5 | flips 122 | threads 13/8 alive | unresolved 0 | alerts assert,blocked. Image changes 35.5/37.5/76.2 s; last frame @76.2s is the SAFE-AREA screen (Use the Left Stick to adjust the screen, press X), i.e. past legal/ESRB. Flips per 10 s: 0-10:20, 30-40:76, 40-50:13, 50-60:7, 60:3, 70:1, 80:1, 90:1 (last ~93.9s); parks still patched at 94.9s. STALLED verdict = no new log shapes, not no frames. Everything ~30 s late vs T022 (GUIDCACHE 21.6s vs 3.6s) from machine load. Next: control run, same binary, LD_PRELOAD no-op setkind.
- 2026-10-19 10:17 agent-rwlock: Run 3 CONTROL (same binary + env as run 2, LD_PRELOAD scratch nosetkind.so making pthread_rwlockattr_setkind_np a no-op, --gdb, load ~147): boot_check 2026-10-19 10:16 v01.09 e305d1b+dirty 90s: PROGRESSING | last open TEXTURES.TFC@37.8s | pkgs 13 (GUIDCACHE last) | zlib 3279 | dumps 23 lit 23 distinct 2 | flips 59 | threads 13/8 alive | unresolved 0 | alerts assert,blocked. Image changes only 2.5s and 42.3s (ESRB), never the safe-area screen. gdb at 90 s: jc_thread -> spu_run_spurs_job -> spu_prxjob_0caea65cafc25798 func_0000AB6C -> spu_wrch -> mfc_for -> AcquireSRWLockExclusive -> pthread_rwlock_wrlock (futex wait); 9 more threads inside mfc_for/rdlock. Starvation reproduced.
