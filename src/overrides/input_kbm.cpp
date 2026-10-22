/*
 * The keyboard and mouse as the pad (port 0).
 *
 * Ported from soyjxck/dod3-recomp 96df4c3 src/input/kbm.cpp (Drakengard 3's
 * port, MIT, (c) soyjxck): the binding table, the key-name parser and the
 * four-direction sticks are that file's. What is new here is where the keys
 * come from: SDL2, whose window the Linux Vulkan backend draws into
 * (ps3recomp libs/video/rsx_vulkan_backend.c), read by scancode -- a place on
 * the keyboard, whatever the layout prints on it, so WASD stays WASD on
 * AZERTY. Mouse look (dod3 src/input/camera.cpp) is not ported: it patches
 * the camera at Drakengard 3's own addresses.
 *
 * Why it is needed: SARPBC imports cellKbRead and cellMouseGetDataList but
 * nothing calls them, and cellKbInit/cellMouseInit are not imported at all
 * (docs/subsystems.md, Input). Keyboard play has to arrive as a pad. The pad
 * library asks host_input() for port 0's keys at every sweep
 * (cellPad_set_host_input, ps3recomp patch T008-1), beside whatever real pad
 * is plugged in; the two are merged.
 *
 * The bindings, each a list of keys ("none" for no key), from the
 * environment or config.toml [input] (src/overrides/input_config.cpp). The
 * defaults are for a rocket car (docs/subsystems.md has the table):
 *
 *   KEY_R2  W  (throttle)            KEY_L2  S  (brake / reverse)
 *   KEY_MOVE_UP/_DOWN/_LEFT/_RIGHT   W S A D  (the left stick: steer, air pitch)
 *   KEY_CROSS     Space Mouse2  (jump)     KEY_CIRCLE   Shift Mouse1 Backspace (boost)
 *   KEY_SQUARE    Ctrl  (powerslide)       KEY_TRIANGLE R
 *   KEY_L1 Q   KEY_R1 E   KEY_L3 C   KEY_R3 V
 *   KEY_START     Esc Enter                KEY_SELECT   Tab
 *   KEY_UP/_DOWN/_LEFT/_RIGHT        the arrows (d-pad)
 *   KEY_LOOK_UP/_DOWN/_LEFT/_RIGHT   I K J L  (the right stick)
 *
 * Keys: A-Z, 0-9, F1-F12, Space, Enter, Tab, Esc, Backspace, Shift, Ctrl,
 * Alt, LShift RShift LCtrl RCtrl LAlt RAlt, Up Down Left Right, Insert
 * Delete Home End PageUp PageDown, CapsLock, Minus Equals LBracket RBracket
 * Semicolon Quote Comma Period Slash Backslash Grave, Num0-Num9, Mouse1
 * (left) Mouse2 (right) Mouse3 (middle) Mouse4 Mouse5, WheelUp WheelDown.
 *
 * A key bound to R2 or L2 pulls that trigger fully (pressure 255), which is
 * what the game's throttle and brake read (the press-mode words, +0xA8/+0xAA
 * of the cellPadData it fetches in func_000D101C).
 *
 * Esc closes the window in the Vulkan backend's pump; while Esc is bound to
 * something, an SDL event filter drops the Esc key-down before the pump sees
 * it (SDL updates its key state before filtering, so the key still reads as
 * held). Closing the window with its close button still quits.
 *
 *   SARPBC_KEYBOARD=0   no keyboard or mouse reaches the game
 *   SARPBC_KBM_LOG=1    a line whenever what the keys hold changes
 *
 * Windows and macOS: not built here (no SDL window there); ps3recomp's own
 * keyboard fallback in cellPad.c covers them until a port of dod3's
 * GetAsyncKeyState / Metal key sources is needed.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern "C" void sarpbc_input_config(void);   /* src/overrides/input_config.cpp */

#if !defined(_WIN32) && !defined(__APPLE__) && defined(__has_include)
#if __has_include(<SDL2/SDL.h>)
#define SARPBC_KBM_SDL 1
#endif
#endif

#ifdef SARPBC_KBM_SDL
#include <SDL2/SDL.h>
#include <strings.h>

#include <atomic>
#include <chrono>
#include <string>
#include <vector>

#include "graphics_settings.h"

extern "C" {
/* ps3recomp/libs/input/cellPad.h (patch T008-1); declared here so this file
 * needs none of the runtime's include paths. */
typedef struct CellPadHostInput {
    uint16_t buttons;
    uint8_t lx, ly, rx, ry;
    uint8_t l2, r2;
} CellPadHostInput;
typedef int (*cellPad_host_input_fn)(void* user, int focused, CellPadHostInput* out);
void cellPad_set_host_input(cellPad_host_input_fn fn, void* user);
}

namespace {

enum Bind {
    kBindCross,
    kBindCircle,
    kBindSquare,
    kBindTriangle,
    kBindL1,
    kBindR1,
    kBindL2,
    kBindR2,
    kBindL3,
    kBindR3,
    kBindStart,
    kBindSelect,
    kBindUp,
    kBindDown,
    kBindLeft,
    kBindRight,
    kBindMoveUp,
    kBindMoveDown,
    kBindMoveLeft,
    kBindMoveRight,
    kBindLookUp,
    kBindLookDown,
    kBindLookLeft,
    kBindLookRight,
    kBinds
};

/* A key is its SDL scancode. Above those: the names that mean either of two
 * keys, the mouse's buttons, and the wheel's notches (not keys: each is a
 * short press). */
const int kEitherShift = 0x1000, kEitherCtrl = 0x1001, kEitherAlt = 0x1002, kEitherEnter = 0x1003;
const int kMouseButton = 0x2000;   /* + SDL_BUTTON_LEFT (1) .. SDL_BUTTON_X2 (5) */
const int kWheelUp = -1, kWheelDown = -2;

const struct {
    const char* name;
    int code;
} kKeys[] = {
    { "Space", SDL_SCANCODE_SPACE },
    { "Enter", kEitherEnter },
    { "Tab", SDL_SCANCODE_TAB },
    { "Esc", SDL_SCANCODE_ESCAPE },
    { "Backspace", SDL_SCANCODE_BACKSPACE },
    { "Shift", kEitherShift },
    { "Ctrl", kEitherCtrl },
    { "Alt", kEitherAlt },
    { "LShift", SDL_SCANCODE_LSHIFT },
    { "RShift", SDL_SCANCODE_RSHIFT },
    { "LCtrl", SDL_SCANCODE_LCTRL },
    { "RCtrl", SDL_SCANCODE_RCTRL },
    { "LAlt", SDL_SCANCODE_LALT },
    { "RAlt", SDL_SCANCODE_RALT },
    { "Up", SDL_SCANCODE_UP },
    { "Down", SDL_SCANCODE_DOWN },
    { "Left", SDL_SCANCODE_LEFT },
    { "Right", SDL_SCANCODE_RIGHT },
    { "Insert", SDL_SCANCODE_INSERT },
    { "Delete", SDL_SCANCODE_DELETE },
    { "Home", SDL_SCANCODE_HOME },
    { "End", SDL_SCANCODE_END },
    { "PageUp", SDL_SCANCODE_PAGEUP },
    { "PageDown", SDL_SCANCODE_PAGEDOWN },
    { "CapsLock", SDL_SCANCODE_CAPSLOCK },
    { "Minus", SDL_SCANCODE_MINUS },
    { "Equals", SDL_SCANCODE_EQUALS },
    { "LBracket", SDL_SCANCODE_LEFTBRACKET },
    { "RBracket", SDL_SCANCODE_RIGHTBRACKET },
    { "Semicolon", SDL_SCANCODE_SEMICOLON },
    { "Quote", SDL_SCANCODE_APOSTROPHE },
    { "Comma", SDL_SCANCODE_COMMA },
    { "Period", SDL_SCANCODE_PERIOD },
    { "Slash", SDL_SCANCODE_SLASH },
    { "Backslash", SDL_SCANCODE_BACKSLASH },
    { "Grave", SDL_SCANCODE_GRAVE },
    { "Mouse1", kMouseButton + SDL_BUTTON_LEFT },
    { "Mouse2", kMouseButton + SDL_BUTTON_RIGHT },
    { "Mouse3", kMouseButton + SDL_BUTTON_MIDDLE },
    { "Mouse4", kMouseButton + SDL_BUTTON_X1 },
    { "Mouse5", kMouseButton + SDL_BUTTON_X2 },
    { "WheelUp", kWheelUp },
    { "WheelDown", kWheelDown },
};

/* 'A'-'Z' and '0'-'9' (SDL puts 0 after 9, as the keyboard does). */
int letter_key(char c)
{
    if (c >= 'A' && c <= 'Z') return SDL_SCANCODE_A + (c - 'A');
    return c == '0' ? SDL_SCANCODE_0 : SDL_SCANCODE_1 + (c - '1');
}
int function_key(int n) { return SDL_SCANCODE_F1 + n - 1; }   /* 1-12 */
int numpad_key(int n) { return n == 0 ? SDL_SCANCODE_KP_0 : SDL_SCANCODE_KP_1 + n - 1; }

bool key_held(const Uint8* ks, Uint32 mouse, int k)
{
    switch (k) {
    case kEitherShift: return ks[SDL_SCANCODE_LSHIFT] || ks[SDL_SCANCODE_RSHIFT];
    case kEitherCtrl: return ks[SDL_SCANCODE_LCTRL] || ks[SDL_SCANCODE_RCTRL];
    case kEitherAlt: return ks[SDL_SCANCODE_LALT] || ks[SDL_SCANCODE_RALT];
    case kEitherEnter: return ks[SDL_SCANCODE_RETURN] || ks[SDL_SCANCODE_KP_ENTER];
    }
    if (k >= kMouseButton) return (mouse & SDL_BUTTON(k - kMouseButton)) != 0;
    return k >= 0 && k < SDL_NUM_SCANCODES && ks[k];
}

const struct {
    const char* key;   /* config.toml [input] / environment */
    const char* defaults;
    uint16_t button;   /* CELL_PAD_CTRL_*, or 0 for a stick's direction */
} kBind[kBinds] = {
    { "KEY_CROSS", "Space Mouse2", 1 << 14 },
    { "KEY_CIRCLE", "Shift Mouse1 Backspace", 1 << 13 },
    { "KEY_SQUARE", "Ctrl", 1 << 15 },
    { "KEY_TRIANGLE", "R", 1 << 12 },
    { "KEY_L1", "Q", 1 << 10 },
    { "KEY_R1", "E", 1 << 11 },
    { "KEY_L2", "S", 1 << 8 },
    { "KEY_R2", "W", 1 << 9 },
    { "KEY_L3", "C", 1 << 1 },
    { "KEY_R3", "V", 1 << 2 },
    { "KEY_START", "Esc Enter", 1 << 3 },
    { "KEY_SELECT", "Tab", 1 << 0 },
    { "KEY_UP", "Up", 1 << 4 },
    { "KEY_DOWN", "Down", 1 << 6 },
    { "KEY_LEFT", "Left", 1 << 7 },
    { "KEY_RIGHT", "Right", 1 << 5 },
    { "KEY_MOVE_UP", "W", 0 },
    { "KEY_MOVE_DOWN", "S", 0 },
    { "KEY_MOVE_LEFT", "A", 0 },
    { "KEY_MOVE_RIGHT", "D", 0 },
    { "KEY_LOOK_UP", "I", 0 },
    { "KEY_LOOK_DOWN", "K", 0 },
    { "KEY_LOOK_LEFT", "J", 0 },
    { "KEY_LOOK_RIGHT", "L", 0 },
};

std::vector<int> s_keys[kBinds];
bool s_log, s_esc_bound;
std::atomic<int> s_wheel{ 0 };            /* notches since the last sweep, up > 0 */
std::atomic<bool> s_filter_on{ false };
uint64_t s_wheel_until[2];                /* a notch's press, up and down, lasts until then */

uint64_t now_us()
{
    using namespace std::chrono;
    return (uint64_t)duration_cast<microseconds>(steady_clock::now().time_since_epoch()).count();
}

bool lookup(const std::string& word, int& out)
{
    if (word.size() == 1) {
        char c = word[0];
        if (c >= 'a' && c <= 'z') c = (char)(c - 32);
        if ((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) {
            out = letter_key(c);
            return true;
        }
    }
    if ((word[0] == 'F' || word[0] == 'f') && word.size() >= 2 && word.size() <= 3) {
        const int n = atoi(word.c_str() + 1);
        if (n >= 1 && n <= 12) {
            out = function_key(n);
            return true;
        }
    }
    if (word.size() == 4 && !strncasecmp(word.c_str(), "Num", 3) && word[3] >= '0' && word[3] <= '9') {
        out = numpad_key(word[3] - '0');
        return true;
    }
    for (const auto& k : kKeys)
        if (!strcasecmp(word.c_str(), k.name)) {
            out = k.code;
            return true;
        }
    return false;
}

void parse(int b, const char* list)
{
    s_keys[b].clear();
    std::string word;
    for (const char* p = list;; p++) {
        if (*p && *p != ',' && *p != ' ' && *p != '\t') {
            word += *p;
            continue;
        }
        if (!word.empty()) {
            int k = 0;
            if (!strcasecmp(word.c_str(), "none")) {
                /* no key */
            } else if (lookup(word, k)) {
                s_keys[b].push_back(k);
                if (k == SDL_SCANCODE_ESCAPE) s_esc_bound = true;
            } else {
                fprintf(stderr, "[keyboard] %s: no key called \"%s\"\n", kBind[b].key, word.c_str());
            }
            word.clear();
        }
        if (!*p) break;
    }
}

/* Runs on the thread that pumps SDL's events (the Vulkan backend's
 * rsx_vulkan_backend_pump_messages). Returning 0 drops the event. */
int SDLCALL event_filter(void*, SDL_Event* e)
{
    /* F11 toggles fullscreen (the Graphics page changes the same setting) */
    if (e->type == SDL_KEYDOWN && !e->key.repeat && e->key.keysym.scancode == SDL_SCANCODE_F11) {
        auto& fs = sarpbc_gfx::settings().fullscreen;
        fs = fs.load() ? 0 : 1;
        sarpbc_gfx::save();
    }
    /* F3 toggles the FPS counter (T064); the Graphics page changes the same setting */
    if (e->type == SDL_KEYDOWN && !e->key.repeat && e->key.keysym.scancode == SDL_SCANCODE_F3) {
        auto& on = sarpbc_gfx::settings().fps_overlay;
        on = on.load() ? 0 : 1;
        sarpbc_gfx::save();
    }
    if (e->type == SDL_KEYDOWN && e->key.keysym.scancode == SDL_SCANCODE_ESCAPE && s_esc_bound) return 0;
    if (e->type == SDL_MOUSEWHEEL) {
        /* Smooth-scrolling wheels and touchpads report fractions, which
         * leave the integer y at 0, and through sdl2-compat (Fedora's
         * SDL2, 2.32.x) a pushed notch arrives as y=0 preciseY=1.0 --
         * measured. A notch is a notch whichever way it comes. */
        int y = e->wheel.y;
#if SDL_VERSION_ATLEAST(2, 0, 18)
        if (!y) y = e->wheel.preciseY > 0 ? 1 : e->wheel.preciseY < 0 ? -1 : 0;
#endif
        if (e->wheel.direction == SDL_MOUSEWHEEL_FLIPPED) y = -y;
        s_wheel += y;
    }
    return 1;
}

bool down(const Uint8* ks, Uint32 mouse, int b, uint64_t now)
{
    for (int k : s_keys[b]) {
        if (k == kWheelUp) {
            if (now < s_wheel_until[0]) return true;
        } else if (k == kWheelDown) {
            if (now < s_wheel_until[1]) return true;
        } else if (key_held(ks, mouse, k))
            return true;
    }
    return false;
}

/* A stick from its four directions: a full push, the diagonals on the circle. */
void stick(bool up, bool dn, bool lf, bool rt, uint8_t& x, uint8_t& y)
{
    const int h = (rt ? 1 : 0) - (lf ? 1 : 0), v = (dn ? 1 : 0) - (up ? 1 : 0);
    const int reach = (h && v) ? 90 : 127;
    x = (uint8_t)(128 + h * reach);
    y = (uint8_t)(128 + v * reach);
}

/* The pad library's sweep thread, every few milliseconds. */
int host_input(void*, int /*focused: always 1 off Windows/macOS*/, CellPadHostInput* out)
{
    /* SDL's video (the window, its keyboard and mouse) comes up after this
     * is registered, on the render thread; until then there are no keys. */
    if (!SDL_WasInit(SDL_INIT_VIDEO)) return 0;
    if (!s_filter_on.exchange(true)) SDL_SetEventFilter(event_filter, nullptr);

    const uint64_t now = now_us();
    const int wheel = s_wheel.exchange(0);
    /* Keys held while another window is in front are not ours. */
    if (!SDL_GetKeyboardFocus()) return 0;
    if (wheel > 0) s_wheel_until[0] = now + 70000;
    if (wheel < 0) s_wheel_until[1] = now + 70000;

    int nkeys = 0;
    const Uint8* ks = SDL_GetKeyboardState(&nkeys);
    if (!ks) return 0;
    const Uint32 mouse = SDL_GetMouseState(nullptr, nullptr);

    bool on[kBinds];
    bool any = false;
    for (int b = 0; b < kBinds; b++) {
        on[b] = down(ks, mouse, b, now);
        any = any || on[b];
        if (on[b]) out->buttons |= kBind[b].button;
    }
    stick(on[kBindMoveUp], on[kBindMoveDown], on[kBindMoveLeft], on[kBindMoveRight], out->lx, out->ly);
    stick(on[kBindLookUp], on[kBindLookDown], on[kBindLookLeft], on[kBindLookRight], out->rx, out->ry);
    if (on[kBindL2]) out->l2 = 255;
    if (on[kBindR2]) out->r2 = 255;
    if (s_log) {
        static CellPadHostInput last;
        if (memcmp(&last, out, sizeof last)) {
            last = *out;
            fprintf(stderr, "[keyboard] buttons %04X left %u,%u right %u,%u L2 %u R2 %u\n", out->buttons, out->lx,
                    out->ly, out->rx, out->ry, out->l2, out->r2);
        }
    }
    return any;
}

void install()
{
    sarpbc_input_config();   /* config.toml [input] -> environment, first */
    if (const char* e = getenv("SARPBC_KEYBOARD"))
        if (!strcmp(e, "0")) {
            printf("[keyboard] off (SARPBC_KEYBOARD=0)\n");
            return;
        }
    for (int b = 0; b < kBinds; b++) {
        const char* e = getenv(kBind[b].key);
        parse(b, e && *e ? e : kBind[b].defaults);
    }
    s_log = getenv("SARPBC_KBM_LOG") != nullptr;
    cellPad_set_host_input(host_input, nullptr);
    printf("[keyboard] keyboard and mouse on pad port 0 (SDL scancodes)%s\n",
           s_esc_bound ? "; Esc is bound, so it no longer closes the window" : "");
}

/* Before main: the pad library is not started until the game's cellPadInit,
 * and every getenv the pad library makes (PAD_TRACE, ...) comes later still,
 * so config.toml's settings are in the environment in time. */
struct Installer {
    Installer() { install(); }
} s_installer;

}  // namespace

#else /* no SDL window on this platform: ps3recomp's built-in keys stay */

namespace {
struct Installer {
    Installer() { sarpbc_input_config(); }
} s_installer;
}  // namespace

#endif
