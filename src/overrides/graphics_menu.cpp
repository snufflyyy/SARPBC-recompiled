/*
 * The Options > Graphics page (T065): the host side of the script bridge.
 *
 * tools/graphics_menu_patch.py patches the game's menu scripts (docs/graphics-menu.md). The
 * patched script asks this file for everything the page shows and does, through one native
 * that nothing else calls, Helpers.FindLocalizedPropertyValue(Object O, string PropertyName)
 * -> string (UTAGame, exec thunk 0x00BBCC58 in 01.09). Its thunk is replaced here: the
 * PropertyName is a command, the returned string the answer.
 *
 *   page            "gfx" while the Graphics page is open, else "sys"
 *   open:gfx|sys    which page the Options menu is opening (selected row: Graphics or System)
 *   close           the page is closing
 *   rows            number of rows
 *   label:K         row K's label        title:K    its popup title
 *   nvals:K         number of choices    val:K:J    choice J's text
 *   get:K           the current choice   set:K:J    choose J (returns the choice now in force)
 *   frame:h|y       the page frame's height and screen position for this many rows
 *   isvsync:K       "1" when row K is VSync: the game's own setting (TAProfile.bUseVSync), which the
 *                   patched script keeps reading and writing itself, so the host only lists it
 *
 * The thunk follows the VM's own: this (r3), the caller's FFrame (r4: Object +8, Code +0xC),
 * where the result goes (r5). It evaluates its arguments out of the caller's bytecode, one
 * FFrame::Step each (the native for the opcode at Code, from GNatives), then steps over the
 * EndFunctionParms. Layout read from the lifted thunks at 0x00BCA908 and 0x00BBCC58.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <string>
#include <vector>

#include "graphics_settings.h"
#include "ppu_recomp.h"

extern "C" {
void ps3_indirect_call(ppu_context* ctx);
void ppu_register_function(uint64_t addr, void (*fn)(ppu_context*));
extern PPU_THREAD_LOCAL void (*g_trampoline_fn)(void*);
}

namespace {

constexpr uint32_t kThunkAddr = 0x00BBCC58;   // UTAGame Helpers::execFindLocalizedPropertyValue
constexpr uint32_t kGNatives = 0x012D17B8;    // {fn OPD (low bit: virtual), this adjust} per opcode
constexpr uint32_t kGMallocPtr = 0x0123CF30;  // GMalloc; its vtable: +8 Realloc(ptr, size, align), +0xC Free(ptr)
constexpr uint32_t kFrameObject = 0x08, kFrameCode = 0x0C;
constexpr uint8_t kOpDebugInfo = 0x41;

void drain(ppu_context* ctx)
{
    while (g_trampoline_fn) {
        void (*f)(void*) = g_trampoline_fn;
        g_trampoline_fn = 0;
        f(ctx);
    }
}

/* One FFrame::Step: evaluate the expression at Code with the native GNatives names for its
 * opcode; its value goes to `result`. */
void step(ppu_context* ctx, uint32_t stack, uint32_t result)
{
    const uint32_t obj = vm_read32(stack + kFrameObject);
    const uint32_t code = vm_read32(stack + kFrameCode);
    const uint32_t op = vm_read8(code);
    vm_write32(stack + kFrameCode, code + 1);
    uint32_t fn = vm_read32(kGNatives + op * 8);
    const uint32_t self = obj + vm_read32(kGNatives + op * 8 + 4);
    if (fn & 1) fn = vm_read32(vm_read32(self) + fn - 1);   // virtual: the vtable slot
    ctx->gpr[3] = self;
    ctx->gpr[4] = stack;
    ctx->gpr[5] = result;
    ctx->ctr = vm_read32(fn);
    ps3_indirect_call(ctx);
    drain(ctx);
}

uint32_t gmalloc_call(ppu_context* ctx, uint32_t slot, uint32_t a, uint32_t b, uint32_t c)
{
    const uint32_t gm = vm_read32(kGMallocPtr);
    ctx->gpr[3] = gm;
    ctx->gpr[4] = a;
    ctx->gpr[5] = b;
    ctx->gpr[6] = c;
    ctx->ctr = vm_read32(vm_read32(vm_read32(gm) + slot));
    ps3_indirect_call(ctx);
    drain(ctx);
    return (uint32_t)ctx->gpr[3];
}

std::string read_fstring(uint32_t fs)
{
    const uint32_t data = vm_read32(fs), num = vm_read32(fs + 4);
    std::string s;
    for (uint32_t i = 0; data && i + 1 < num; i++) s += (char)vm_read16(data + 2 * i);
    return s;
}

/* *fs = text: Data reallocated to the exact size, Num = Max = characters + NUL. */
void set_fstring(ppu_context* ctx, uint32_t fs, const std::string& text)
{
    const uint32_t n = (uint32_t)text.size() + 1;
    const uint32_t data = gmalloc_call(ctx, 8, vm_read32(fs), n * 2, 8);
    for (uint32_t i = 0; i + 1 < n; i++) vm_write16(data + 2 * i, (uint8_t)text[i]);
    vm_write16(data + 2 * (n - 1), 0);
    vm_write32(fs, data);
    vm_write32(fs + 4, n);
    vm_write32(fs + 8, n);
}

/* ---- the page ---------------------------------------------------------------- */

struct Row {
    const char* label;
    const char* title;
    std::vector<std::string> choices;
    int (*get)();
    void (*set)(int);
};

using sarpbc_gfx::settings;

std::vector<Row> make_rows()
{
    std::vector<Row> rows;
    {
        Row r{"Resolution", "Resolution", {}, [] { return settings().window_size.load(); },
              [](int i) { settings().window_size = i; }};
        for (int i = 0; i < sarpbc_gfx::kNumWindowSizes; i++)
            r.choices.push_back(std::to_string(sarpbc_gfx::kWindowSizes[i].w) + " x " +
                                std::to_string(sarpbc_gfx::kWindowSizes[i].h));
        rows.push_back(r);
    }
    {
        Row r{"Render Scale", "Render Scale", {}, [] { return settings().render_scale.load(); },
              [](int i) { settings().render_scale = i; }};
        for (int i = 0; i < sarpbc_gfx::kNumRenderScales; i++)
            r.choices.push_back(std::to_string(sarpbc_gfx::kRenderScalePercent[i]) + "%");
        rows.push_back(r);
    }
    rows.push_back({"VSync", "VSync", {"Enabled", "Disabled"}, [] { return 0; }, [](int) {}});
    rows.push_back({"Frame Rate", "Frame Rate (restart to apply)", {"Game default", "Unlocked"},
                    [] { return settings().unlock_fps.load(); }, [](int i) { settings().unlock_fps = i; }});
    rows.push_back({"FPS Counter", "FPS Counter", {"Off", "On"},
                    [] { return settings().fps_overlay.load(); }, [](int i) { settings().fps_overlay = i; }});
    return rows;
}

const std::vector<Row>& rows()
{
    static const std::vector<Row> r = make_rows();
    return r;
}

bool s_gfx_page = false;
constexpr int kVsyncRow = 2;   // after Resolution and Render Scale (make_rows)

bool parse_int(const char*& p, int& out)
{
    char* end;
    const long v = strtol(p, &end, 10);
    if (end == p) return false;
    out = (int)v;
    p = end;
    return true;
}

std::string command(const std::string& cmd)
{
    const char* c = cmd.c_str();
    const int n = (int)rows().size();
    if (cmd == "page") return s_gfx_page ? "gfx" : "sys";
    if (cmd == "open:gfx") { s_gfx_page = true; return ""; }
    if (cmd == "open:sys" || cmd == "close") { s_gfx_page = false; return ""; }
    if (cmd == "rows") return std::to_string(n);
    if (!strncmp(c, "isvsync:", 8)) return atoi(c + 8) == kVsyncRow ? "1" : "0";
    // 64 + 64 per row of frame, centred: the System page (7 rows) is 512 high at 0.2777, the
    // Profile page (3 rows) 256 at 0.3888 (MidGameMenuActor SystemOptions/ProfileOptions BeginState)
    if (cmd == "frame:h") return std::to_string(64 + 64 * n);
    if (cmd == "frame:y") { char b[32]; snprintf(b, sizeof b, "%.4f", 0.4722f - 0.02777f * n); return b; }
    int k = 0, j = 0;
    if (!strncmp(c, "label:", 6)) { c += 6; if (parse_int(c, k) && k >= 0 && k < n) return rows()[k].label; }
    else if (!strncmp(c, "title:", 6)) { c += 6; if (parse_int(c, k) && k >= 0 && k < n) return rows()[k].title; }
    else if (!strncmp(c, "nvals:", 6)) { c += 6; if (parse_int(c, k) && k >= 0 && k < n) return std::to_string(rows()[k].choices.size()); }
    else if (!strncmp(c, "get:", 4)) { c += 4; if (parse_int(c, k) && k >= 0 && k < n) return std::to_string(rows()[k].get()); }
    else if (!strncmp(c, "val:", 4)) {
        c += 4;
        if (parse_int(c, k) && *c++ == ':' && parse_int(c, j) && k >= 0 && k < n && j >= 0 &&
            j < (int)rows()[k].choices.size())
            return rows()[k].choices[j];
    } else if (!strncmp(c, "set:", 4)) {
        c += 4;
        if (parse_int(c, k) && *c++ == ':' && parse_int(c, j) && k >= 0 && k < n && j >= 0 &&
            j < (int)rows()[k].choices.size()) {
            rows()[k].set(j);
            if (k != kVsyncRow) sarpbc_gfx::save();
            fprintf(stderr, "[gfx] %s -> %s\n", rows()[k].label, rows()[k].choices[j].c_str());
            return std::to_string(rows()[k].get());
        }
    }
    return "";
}

/* The replacement exec thunk. */
void thunk(ppu_context* ctx)
{
    const uint32_t stack = (uint32_t)ctx->gpr[4];
    const uint32_t result = (uint32_t)ctx->gpr[5];
    const uint64_t sp = ctx->gpr[1];
    const uint32_t nsp = ((uint32_t)sp - 0xC0u) & ~0xFu;   // a frame of our own for the arguments
    vm_write64(nsp, sp);
    ctx->gpr[1] = nsp;
    const uint32_t objSlot = nsp + 0x80, strSlot = nsp + 0x90;
    vm_write32(objSlot, 0);
    vm_write32(strSlot, 0);
    vm_write32(strSlot + 4, 0);
    vm_write32(strSlot + 8, 0);

    step(ctx, stack, objSlot);                       // Object O (ignored)
    step(ctx, stack, strSlot);                       // string PropertyName
    uint32_t code = vm_read32(stack + kFrameCode) + 1;   // EndFunctionParms
    vm_write32(stack + kFrameCode, code);
    if (vm_read8(code) == kOpDebugInfo) step(ctx, stack, 0);

    const std::string answer = command(read_fstring(strSlot));
    if (vm_read32(strSlot)) gmalloc_call(ctx, 0xC, vm_read32(strSlot), 0, 0);   // free the argument
    if (result) set_fstring(ctx, result, answer);
    ctx->gpr[1] = sp;
}

}  // namespace

extern "C" void sarpbc_register_graphics_menu(void)
{
    sarpbc_gfx::load();
    const char* off = getenv("SARPBC_NO_GRAPHICS_MENU");
    if (off && *off && *off != '0') return;
    ppu_register_function(kThunkAddr, thunk);
}
