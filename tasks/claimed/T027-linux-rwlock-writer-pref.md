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
