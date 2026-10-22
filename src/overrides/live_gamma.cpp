/*
 * Brightness without a restart: the engine's DisplayGamma, written into the running game.
 *
 * UClient::DisplayGamma is native only (no script can reach it), but the engine reads it every frame:
 * writing a new float into the client object changes the image on the next one (arena luminance 88 -> 52
 * with 2.2 -> 1.4, in the same run, 2026-10-22). The object is found by its INI neighbours: the config
 * block of [Engine.Client] sits in memory as
 *     MinDesiredFrameRate 35.0f | DisplayGamma 2.2f | InitialButtonRepeatDelay 0.2f | ButtonRepeatDelay 0.1f
 * (the class default object, the instance and a subclass each have one; all are written, a default
 * object's copy is harmless). Heap addresses were 0x40583794 / 0x4063F1E4 / 0x40BA7174 in one boot; they are
 * searched for, not assumed, and re-searched when the neighbours stop matching.
 *
 * The worker sleeps unless the brightness is not the default (or was, earlier): by default nothing is scanned
 * and nothing is written.
 */
#include <stdint.h>
#include <string.h>
#include <unistd.h>

#include <thread>
#include <vector>

#include "graphics_settings.h"
#include "ppu_recomp.h"

namespace {

constexpr uint32_t kMinFps = 0x420C0000, kDelay = 0x3E4CCCCD, kRepeat = 0x3DCCCCCD;   // 35.0f, 0.2f, 0.1f

bool is_client_gamma(uint32_t a)
{
    return vm_read32(a - 4) == kMinFps && vm_read32(a + 4) == kDelay && vm_read32(a + 8) == kRepeat;
}

std::vector<uint32_t> scan(uint32_t lo, uint32_t hi)
{
    std::vector<uint32_t> found;
    for (uint64_t a = lo; a < hi && found.size() < 8; a += 4)
        if (vm_read32(a) == kMinFps && vm_read32(a + 8) == kDelay && vm_read32(a + 12) == kRepeat)
            found.push_back((uint32_t)a + 4);
    return found;
}

uint32_t float_bits(float f)
{
    uint32_t b;
    memcpy(&b, &f, 4);
    return b;
}

void worker()
{
    std::vector<uint32_t> addrs;
    bool touched = false;
    int widen = 0;
    for (;; usleep(500000)) {
        const int idx = sarpbc_gfx::settings().brightness.load(std::memory_order_relaxed);
        const bool want_default = idx == 2;
        if (want_default && !touched) continue;
        touched = true;
        for (size_t i = 0; i < addrs.size();)
            if (is_client_gamma(addrs[i])) i++;
            else addrs.erase(addrs.begin() + (long)i);
        if (addrs.empty()) {
            // the heap the client lives in first; the whole guest heap range now and then
            addrs = widen++ % 8 ? std::vector<uint32_t>{} : scan(0x10000000, 0x60000000);
            if (addrs.empty()) addrs = scan(0x40000000, 0x48000000);
            if (addrs.empty()) continue;
        }
        const uint32_t want = float_bits(sarpbc_gfx::kBrightnessGamma[idx]);
        for (uint32_t a : addrs)
            if (vm_read32(a) != want) vm_write32(a, want);
    }
}

}  // namespace

namespace sarpbc_gfx {
void start_live_gamma() { std::thread(worker).detach(); }
}  // namespace sarpbc_gfx
