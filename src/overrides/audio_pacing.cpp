/* MultiStream's update thread paces the mixer with a nap, and the nap is the problem here.
 *
 * "MultiStream Update Thread" (01.09 entry 0x01225628; the loop is func_0077CEB0) runs
 * update, then Sleep(obj+0x1EC seconds), which is 5 ms. On the PS3 the SPU mixer needs
 * ~0.3 ms per 256-sample block, so the round is ~5.3 ms: one block per round, the rate the
 * cellAudio port consumes them (5.33 ms). Here the same SPU code takes ~3 ms on the host, so
 * a round of 5 ms nap + 3 ms of work spans two blocks: the game then writes every second ring
 * slot, the reader finds the others empty, and the output is a block of sound, a block of
 * silence. That is the crackle (measured 2026-10-21: 66% silent blocks, 860 block-edge clicks
 * in 42 s). The update loop already polls the ring's read index, so with the nap gone it
 * starts a round as soon as a block is free; with it gone the same 42 s have no silent
 * block and one click.
 *
 * The nap is shortened by the runtime's PS3_USLEEP_SCALE (<thread name>:<percent>, applied in
 * sys_timer_usleep). An explicit environment value wins, e.g. PS3_USLEEP_SCALE= (empty) to
 * restore the game's own timing, or "MultiStream Update Thread:50" to try half.
 */
#include <stdlib.h>

namespace {
struct AudioPacing {
    AudioPacing()
    {
        const char* v = "MultiStream Update Thread:0";
#ifdef _WIN32
        if (!getenv("PS3_USLEEP_SCALE")) _putenv_s("PS3_USLEEP_SCALE", v);
#else
        setenv("PS3_USLEEP_SCALE", v, 0);
#endif
    }
} s_audio_pacing;
}  // namespace
