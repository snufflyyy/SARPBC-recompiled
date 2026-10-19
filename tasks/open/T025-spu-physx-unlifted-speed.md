# T025: PhysX unlifted LS 0x20180 + SPU x86 speed (SSE4.1 shufb, SIMD float helpers)

Status: open
Owner: -
Touches: CMakeLists.txt (compile flags only), patches/ps3recomp/T025-*.patch (runtime/spu/**, tools/build_spu_workloads.py / find_spu_functions.py only), tools/make_spu_overlays.py (only to add a PhysX overlay case), docs/subsystems.md (SPU/SPURS section only)
Reads: tasks/done/T007*, tasks/done/T003*, docs/dod3-reuse.md

## Goal
**User priority: menus first.** After T007 the only unlifted SPU branch left in a 01.09 boot is in
PhysX (image 363824547, branch to LS 0x20180). Find out what lives at 0x20180 (a second PhysX
overlay? a DMA'd code block like MultiStream's?) and lift + register it the way T003/T007 did, so
the boot never falls into the interpreter. Second: SPU code is too slow on x86. T007 measured the
MultiStream mixer at 27% of real time (43% with -msse4.1); perf puts 37% in the byte-loop `shufb`
helper (no SSE4.1 path compiled) and ~17% in scalar `spu_fa/fs/fm/fma`. Build with
`-march=x86-64-v2` (or -msse4.1 on SPU sources) and add x86 SIMD paths in
`runtime/spu/spu_helpers.h` (upstream vectorises only for ARM). This speeds up PhysX and Edge too,
which loading depends on.

## Done when
No "unlifted LS" line in a 60 s 01.09 boot_check; mixer throughput (AUDIO_RATE=1) and a
boot_check summary before/after; numbers in docs/subsystems.md.

## Log
