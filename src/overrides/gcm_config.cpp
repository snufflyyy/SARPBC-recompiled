/*
 * SARPBC's defaults for cellGcmSys's FIFO-park handling (T024).
 *
 * Unreal Engine 3's PS3 RHI ends command segments with a JUMP-to-itself
 * ("park") and patches it later; the RSX sits on the park until then. On
 * 01.09 two writers release parks (docs/subsystems.md, Graphics):
 *   1. the flip handler func_000DC144: GCM_SET_USER_COMMAND 0xEB00 before the
 *      park -> user handler 0xDC390 -> cellGcmSetFlipImmediate -> flip handler
 *      rewrites the park as JUMP park+4;
 *   2. the ShaderPatching SPURS job chain 0x012B6F00, which rewrites the park
 *      word to 0 (a NOP).
 * cellGcmSys gives up on a park after GCM_PARK_GRACE_MS (50 ms at the pin)
 * and resyncs to `put`, dropping every command in between, including the
 * fence label the rendering thread then waits on forever. Measured with
 * GCM_PARK_LOG=1 on a loaded host (load average ~150, 2026-10-19): chain
 * parks are released after ~45 ms on average and up to 852 ms; flip-handler
 * parks after up to 192 ms when handlers are only pumped at HLE calls, 28 ms
 * with the interrupt thread. With the 50 ms grace the boot stops on the
 * legal/ESRB screen (36 flips); with a long grace it goes on to the Psyonix
 * logo and keeps flipping (0 resyncs in 90-150 s).
 *
 *   GCM_PARK_GRACE_MS=5000  a resync stays a last resort for a park nobody
 *                           will patch, well past the slowest release seen.
 *   GCM_INTR_THREAD=1       vblank/flip/user handlers run on a host interrupt
 *                           thread, as libgcm's interrupt PPU thread does on
 *                           the console, instead of waiting for the next HLE
 *                           call (the rendering thread polls in
 *                           sys_timer_usleep, an lv2 call, so that can be late).
 *
 * Values already in the environment win (setenv without overwrite), so
 * GCM_INTR_THREAD=0 or another GCM_PARK_GRACE_MS still works for experiments.
 * cellGcmSys reads both lazily, long after static initialisation.
 */
#include <stdlib.h>

namespace {

void set_default(const char* name, const char* value)
{
#ifdef _WIN32
    if (!getenv(name)) _putenv_s(name, value);
#else
    setenv(name, value, 0);
#endif
}

struct GcmConfig {
    GcmConfig()
    {
        set_default("GCM_PARK_GRACE_MS", "5000");
        set_default("GCM_INTR_THREAD", "1");
    }
} s_gcm_config;

}  // namespace
