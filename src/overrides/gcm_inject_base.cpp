/*
 * Move the runtime's GCM window (labels, control register, offset tables) off
 * the title's own memory.
 *
 * ps3recomp keeps the guest-visible structures it injects -- the 4 KB GCM label
 * area, the control register (put/get/ref at +0x2000) and the IO<->EA offset
 * tables -- in a 0x8000-byte window at `ppu_hle_inject_base`, 0x20000000 by
 * default. SARPBC reserves its RSX-visible heap with a raw lv2 call,
 * sys_mmapper_allocate_address(size 0x10000000, align 0x10000000) at
 * 0x000DFA68 (01.09), and the runtime's syscall 330 hands back the first
 * 256 MB-aligned address past 0x11000000: 0x20000000. The game then maps the
 * first 10 MB of it as RSX main memory (cellGcmMapMainMemory(0x20000000,
 * 0xA00000)) and places its own GPU-fence bookkeeping at the very start of it.
 *
 * Both sides then wrote the same bytes. On 01.09 the RHI's fence object at
 * 0x20000000 keeps its next-fence value at +0xFA4 and an 18-entry table at
 * +0xC80, while the RSX's back-end label 255 (the fence the rendering thread
 * polls, func_000DD014 called from func_000E7B70) is +0xFF0 of the same
 * page, and the FIFO control register sits at +0x2000. Seen at the stall
 * (gdb, 2026-10-19): label 0x20000FF0 = 0x44 while the FIFO had already
 * executed the write of 0x49, and the rendering thread slept forever waiting
 * for 0x45/0x46; frames stopped and the main thread spun on its 100 ms wait.
 *
 * Upstream's own comment (runtime/memory/vm.h) says this is the port's call:
 * Gran Turismo 5 Prologue hit the same overlap. 0x1FF00000 is free here: past
 * the TLS images (0x10F00000), below the title's mmapper heap (0x20000000),
 * and nothing else in the runtime allocates between 0x11000000 and 0x20000000
 * once the title's one 256 MB-aligned reservation has moved the mmapper
 * cursor to 0x30000000. Keep it below 0x50000000: several SPURS heuristics
 * treat higher EAs as implausible.
 *
 * SARPBC_GCM_INJECT_BASE=<hex> overrides the address (for experiments).
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

extern "C" uint32_t ppu_hle_inject_base;

namespace {

constexpr uint32_t kInjectBase = 0x1FF00000u;

struct InjectBase {
    InjectBase()
    {
        uint32_t base = kInjectBase;
        if (const char* e = getenv("SARPBC_GCM_INJECT_BASE"))
            base = (uint32_t)strtoul(e, nullptr, 16);
        /* ppu_hle_inject_base has a constant initializer, so it is already
         * set when this dynamic initializer runs, and no guest code (which
         * is the only thing that learns the window's address) has run yet. */
        ppu_hle_inject_base = base;
    }
} s_inject_base;

}  // namespace
