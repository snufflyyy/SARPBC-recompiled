# T023: Port the next generic fork fixes (from docs/dod3-reuse.md)

Status: open
Owner: -
Touches: patches/ps3recomp/T023-*.patch (runtime/** threads, lwcond, sys_fs; libs/spurs/cellSpurs.h error codes), docs/dod3-reuse.md
Reads: docs/dod3-reuse.md (T021 inventory), soyjxck/ps3recomp

## Goal
Port, with original authorship, these fork fixes that T021 ranked as generic and unowned: 0012+0148
(Linux SPU task thread stack use-after-free; ~90 such threads in 6 s here), 0100 (lwcond signals
wake waiters; today a wait is a 1 ms sleep), 0166+0167 (reclaim PPU thread slots and stacks), and
0131/0132/0119 (sys_fs). Also fix cellSpurs.h's error macros (0x804107xx; the real values are 0x804109xx,
found by T019). Then continue the inventory where T021 stopped (fork RSX/GCM/Vulkan commits; dod3
src/ and tools/).

## Done when
Ported with tests or boot evidence, with a boot_check summary before and after; docs/dod3-reuse.md updated.

## Log
