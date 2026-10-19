# T027: Linux rwlock writer preference (SPU DMA lock mfc_for starves ShaderPatching)

Status: open
Owner: -
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
