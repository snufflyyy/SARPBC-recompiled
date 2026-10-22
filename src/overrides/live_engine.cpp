/*
 * Engine settings written into the running game: brightness and the frame-rate cap, with no restart.
 *
 * Both are native config values of UE3 objects (no script can reach them) that the engine reads every frame,
 * so a new float in the object takes effect on the next one. The objects are found by the neighbours their INI
 * block leaves in memory, searched for (never assumed) and re-searched when the neighbours stop matching:
 *
 *   DisplayGamma   [Engine.Client]: MinDesiredFrameRate 35.0f | DisplayGamma 2.2f | InitialButtonRepeatDelay 0.2f |
 *                  ButtonRepeatDelay 0.1f. Arena luma 88 -> 52 with 2.2 -> 1.4 in the same run (2026-10-22).
 *   Frame cap      [Engine.GameEngine]: MaxSmoothedFrameRate 60.0f directly followed by MinSmoothedFrameRate 22.0f,
 *                  inside a run of zero words (seen at 0x4049C71C, 0x4062897C, 0x40BA597C: the class default
 *                  object, the instance, a subclass; all are written). UE3 sleeps to hold the max and clamps its
 *                  frame time to it; 1000 lifts it (with the 1 kHz vblank and MAILBOX present src/main.cpp sets).
 *
 * A value is only written once it has been asked to leave its default: with the defaults nothing is scanned and
 * nothing is written, and the default run is byte-identical to the game's own.
 */
#include <stdint.h>
#include <string.h>
#include <unistd.h>

#include <stdio.h>
#include <algorithm>
#include <thread>
#include <vector>

#include "graphics_settings.h"
#include "ppu_recomp.h"

namespace {

constexpr uint32_t kMinFps = 0x420C0000, kDelay = 0x3E4CCCCD, kRepeat = 0x3DCCCCCD;   // 35.0f, 0.2f, 0.1f
constexpr uint32_t k22 = 0x41B00000, k60 = 0x42700000, k1000 = 0x447A0000;             // 22.0f, 60.0f, 1000.0f

uint32_t float_bits(float f)
{
    uint32_t b;
    memcpy(&b, &f, 4);
    return b;
}

// One value the worker keeps: where it is found, how to recognise it, what to write.
struct Live {
    const char* name;
    bool (*check)(uint32_t a);            // is `a` the value's address?
    bool (*first_word)(uint32_t a);       // cheap pre-filter for the scan
    std::vector<uint32_t> addrs;
    bool touched = false;
    int widen = 0, tick = 0;

    // Keeps `want` (a float's bits) in every copy found. `is_default` and never asked to change: do nothing.
    void apply(uint32_t want, bool is_default)
    {
        if (is_default && !touched) return;
        touched = true;
        for (size_t i = 0; i < addrs.size();)
            if (check(addrs[i])) i++;
            else addrs.erase(addrs.begin() + (long)i);
        // The objects appear as the engine starts up (the class default object first, the instance later), so
        // search again every few seconds and keep every copy found; the whole heap range only now and then.
        if (addrs.empty() || ++tick % 6 == 0) {
            std::vector<uint32_t> more = (addrs.empty() && widen++ % 8 == 0) ? scan(0x10000000, 0x60000000)
                                                                              : scan(0x40000000, 0x48000000);
            for (uint32_t a : more)
                if (std::find(addrs.begin(), addrs.end(), a) == addrs.end()) addrs.push_back(a);
            if (addrs.empty()) return;
        }
        for (uint32_t a : addrs)
            if (vm_read32(a) != want) {
                vm_write32(a, want);
                fprintf(stderr, "[live] %s at 0x%08X <- %08X\n", name, a, want);
            }
    }

    std::vector<uint32_t> scan(uint32_t lo, uint32_t hi) const
    {
        std::vector<uint32_t> found;
        for (uint64_t a = lo + 4; a < hi && found.size() < 8; a += 4)
            if (first_word((uint32_t)a) && check((uint32_t)a)) found.push_back((uint32_t)a);
        return found;
    }
};

// DisplayGamma: the word after MinDesiredFrameRate, before the two repeat delays.
bool gamma_first(uint32_t a) { return vm_read32(a - 4) == kMinFps; }
bool gamma_check(uint32_t a) { return vm_read32(a - 4) == kMinFps && vm_read32(a + 4) == kDelay && vm_read32(a + 8) == kRepeat; }

// MaxSmoothedFrameRate: the address is the 60.0f (or our 1000.0f) word, with 22.0f (MinSmoothedFrameRate) right
// after it and zero words around the pair.
bool cap_first(uint32_t a) { return vm_read32(a + 4) == k22; }
bool cap_check(uint32_t a)
{
    const uint32_t max = vm_read32(a);
    if (vm_read32(a + 4) != k22 || (max != k60 && max != k1000)) return false;
    for (int d = 8; d <= 32; d += 4)
        if (vm_read32(a + 4 + d) != 0 || vm_read32(a - d) != 0) return false;
    return true;
}

void worker()
{
    Live gamma{"DisplayGamma", gamma_check, gamma_first, {}};
    Live cap{"MaxSmoothedFrameRate", cap_check, cap_first, {}};
    for (;; usleep(500000)) {
        const auto& s = sarpbc_gfx::settings();
        const int bright = s.brightness.load(std::memory_order_relaxed);
        gamma.apply(float_bits(sarpbc_gfx::kBrightnessGamma[bright]), bright == 2);
        const bool unlocked = s.unlock_fps.load(std::memory_order_relaxed) != 0;
        cap.apply(unlocked ? k1000 : k60, !unlocked);
    }
}

}  // namespace

namespace sarpbc_gfx {
void start_live_engine() { std::thread(worker).detach(); }
}  // namespace sarpbc_gfx
