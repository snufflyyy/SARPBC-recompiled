# Experimental diffs (not applied by tools/apply_patches.sh)

Uncommitted experiments kept so a later agent can turn them into real patches. Apply by hand,
in `external/ps3recomp`, after `tools/apply_patches.sh`, for local tests only.

| Diff | From | What it did | Status |
|---|---|---|---|
| `T022-esrb-experiment.diff` | T022, 2026-10-19, against the stack before 0024-0027 | (1) `libs/video/cellGcmSys.c`: never skip past a jump-to-itself park; (2) `runtime/platform/win32_compat.h`: writer-preferring rwlocks on Linux; (3) `runtime/ppu/ppu_loader.cpp`: pump GCM handlers on every lv2 syscall (turned out not to be needed). With 0024 and the `gcm_inject_base.cpp` override, 01.09 reached the **legal/ESRB screen with a 3D car** (`PROGRESSING`, flips 106, `SPU_INTERP_UNLIFTED=1`) | (1) overlaps patch 0027 and no longer applies: reconcile in T024. (2) is T027. (3) dropped |
