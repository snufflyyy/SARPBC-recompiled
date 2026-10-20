/* SARPBC's attached SPURS queue is a slab allocator service, not a job-chain
 * completion queue. The legacy HLE broadcast sends ShaderPatching's job index
 * as data2; func_008FFCB8 treats index 0 as shutdown and exits its
 * CellSlabMemoryManager thread. Later collision tasks wait forever for slabs
 * at EA 0x0125E000. Use the real SPU requests instead of synthetic completions.
 *
 * The runtime gate is ported from Drakengard 3's ps3recomp fork. This setting
 * belongs to the title: other ports still expect the compatibility events.
 * An explicit environment value wins, including =1 for regression testing.
 */
#include <stdlib.h>

namespace {
struct SpursConfig {
    SpursConfig()
    {
#ifdef _WIN32
        if (!getenv("SPURS_JC_DONE_EVENTS")) _putenv_s("SPURS_JC_DONE_EVENTS", "0");
#else
        setenv("SPURS_JC_DONE_EVENTS", "0", 0);
#endif
    }
} s_spurs_config;
}  // namespace
