/*
 * SARPBC runner, adapted from ps3recomp templates/project/main.cpp (838800e).
 * Changes from the template: Vulkan backend on Linux, and the guest file system
 * set up for an HDD title (setup_vfs). Diff against the template on a pin bump.
 *
 * This is the runner. It boots a lifted title through the toolkit's PPU
 * scaffold: allocate the flat guest VM, load the PPU ELF named on the command
 * line, register the lifted function table and the HLE NID handlers, start a
 * frame clock, and dispatch the entry OPD.
 *
 * The scaffold does the work; nothing below reimplements it. ppu_load_elf,
 * ppu_recomp_register, ppu_hle_init, ppu_sysprx_register, ppu_fs_register,
 * lv2_init_syscalls and ppu_run all come from the toolkit, compiled into this
 * project from PS3RECOMP_DIR (see CMakeLists.txt). What is left here is the
 * part a port owns: which backend to present through, how the frame clock is
 * paced, and whatever diagnostics the title turns out to need.
 *
 * runtime/ppu/tests/boot_main.cpp in the toolkit is the same boot in its
 * fully-instrumented form -- crash filter, hang watchdog, guest-PC sampling
 * profiler. Read it when a boot goes wrong; copy from it what the title
 * needs. It is deliberately not what a fresh project starts with.
 *
 * The one part that IS duplicated from it is the frame clock below, because a
 * port is expected to change its pacing and a shared one would be the wrong
 * shape for that. It was copied faithfully, comments and all. If a pacing bug
 * is fixed in one of the two, look at the other.
 *
 * This builds on Windows, macOS and Linux. CI builds and runs it against the
 * boot smoke title on the last two, and compile-checks it against clang-cl on
 * the first (tools/check_ppu_scaffold.py).
 */

/* The lifter's generated header, which declares ppu_context and the function
 * table. It comes first: everything below is written against that struct. */
#include "ppu_recomp.h"

/* The Win32 names -- Sleep, GetTickCount64, CreateThread, InterlockedIncrement,
 * VirtualAlloc, the scalar typedefs -- from one place. On Windows this is a
 * passthrough to <windows.h>; off Windows the toolkit's shim supplies the same
 * names over pthreads and mmap, so the call sites below are written once. */
#include "win32_compat.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <atomic>
#include <string>
#ifndef _WIN32
#include <sys/mman.h>
#endif

#ifdef _WIN32
/* timeBeginPeriod: <windows.h> arrives with WIN32_LEAN_AND_MEAN set, which
 * excludes the multimedia timer API, so it is asked for by name -- and after
 * windows.h, since timeapi.h uses UINT. No shim exists off Windows because
 * there is nothing to shim: the 15.6 ms default timer granularity this works
 * around is a Windows problem. */
#include <timeapi.h>
#endif

/* ---------------------------------------------------------------------------
 * What the scaffold gives this file
 * -----------------------------------------------------------------------*/
extern "C" {
uint32_t ppu_load_elf(const char* path);      /* ELF -> guest RAM, returns entry OPD */
void     ppu_recomp_register(void);           /* generated: lifted table -> address map */
void     ppu_hle_init(void);                  /* firmware import NID -> HLE handler */
void     ppu_sysprx_register(void);           /* boot-critical CRT (sys_initialize_tls, ...) */
void     ppu_fs_register(void);               /* cellFs over the real game directory */
void     lv2_init_syscalls(void);             /* the lv2 syscall table */
int      ppu_run(uint32_t entry_opd, uint32_t stack_top);

/* This project's own: load whatever real system PRX modules the title needs
 * into guest RAM and register their exports. stubs.cpp has the empty version
 * a game with no lifted PRX wants. */
void     ps3_load_prx_modules(void);

/* src/overrides/: firmware functions the runtime lacks, done for this title. */
void     sarpbc_register_edgezlib(void);
void     sarpbc_frame_stats_tick(uint64_t clock_ms, unsigned guest_frames);

/* libs/system/cellGame.c: title id and game type (CATEGORY HG -> HDD) from the
 * install's PARAM.SFO. Without it cellGame answers "disc game BLES00000", and
 * 01.09 builds every data path from that. */
void     cellGame_init_from_paramsfo(const char* sfo_path);

extern const char* ppu_vfs_root;              /* host dir the PS3 mount points map into */

/* The status the guest handed to sys_process_exit. A title that exits that way
 * never returns through ppu_run, so this is only read on the path where the
 * entry function unwound instead. */
extern int     g_sys_process_exit_called;
extern int32_t g_sys_process_exit_code;

/* Host-provided symbols the runtime and the HLE libraries link against. */
uint8_t* vm_base = nullptr;
extern uint32_t ppu_vm_size;                  /* ppu_loader.cpp: the OOB guard */

/* Guest-callback dispatch. g_ps3_guest_caller is the hook the HLE runtime
 * calls back into recompiled code through -- cellSysutil events and the GCM
 * vblank/flip handlers. ppu_guest_call does the OPD -> dispatch. */
typedef void (*ps3_guest_caller_fn)(uint32_t, uint64_t, uint64_t, uint64_t, uint64_t,
                                    uint64_t, uint64_t, uint64_t, uint64_t);
extern ps3_guest_caller_fn g_ps3_guest_caller;
uint64_t ppu_guest_call(uint32_t, uint64_t, uint64_t, uint64_t, uint64_t,
                        uint64_t, uint64_t, uint64_t, uint64_t);

/* The GCM half of the frame clock. */
void     cellGcmTickVBlank(void);
void     cellGcmTickFlip(void);
int      cellGcm_take_flip_pending(void);
void     cellGcm_rsx_process_fifo(void);      /* drain get -> put */
unsigned cellGcm_flip_request_count(void);
}

/* ---------------------------------------------------------------------------
 * RSX present backend
 * -----------------------------------------------------------------------*/
/* Linux (the primary platform) presents through Vulkan; Windows, later, through
 * D3D12; Apple through Metal; anything else through the null backend's headless
 * software path. PS3RECOMP_RSX_VULKAN is a PUBLIC definition of the runtime
 * target, on by default on Linux (see CMakeLists.txt). All of them expose the
 * same three entry points, so the frame clock below is backend-agnostic. */
#if defined(PS3RECOMP_RSX_VULKAN)
extern "C" int  rsx_vulkan_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_vulkan_backend_present(void);
extern "C" void rsx_vulkan_backend_present_begin(void);
extern "C" void rsx_vulkan_backend_present_finish(void);
extern "C" int  rsx_vulkan_backend_present_ready(void);
extern "C" int  rsx_vulkan_backend_pump_messages(void);
#  define rsx_backend_init    rsx_vulkan_backend_init
#  define rsx_backend_present rsx_vulkan_backend_present
/* The present in two halves: the copy out of the flipped surface is submitted
 * at the flip, and finished (waited for, read back, shown) after the next
 * drain, while the GPU ran it beside the CPU's work. Presenting whole waited
 * for the GPU to finish the frame just submitted, in series with the next
 * drain (T060: the GPU was idle 80% of the time, the clock thread waited). */
#  define rsx_backend_present_begin  rsx_vulkan_backend_present_begin
#  define rsx_backend_present_finish rsx_vulkan_backend_present_finish
#  define rsx_backend_present_ready  rsx_vulkan_backend_present_ready
#  define RSX_BACKEND_SPLIT_PRESENT 1
#  define rsx_backend_pump    rsx_vulkan_backend_pump_messages
#  define RSX_BACKEND_NAME    "Vulkan"
#elif defined(_WIN32)
extern "C" int  rsx_d3d12_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_d3d12_backend_present(void);
extern "C" int  rsx_d3d12_backend_pump_messages(void);
#  define rsx_backend_init    rsx_d3d12_backend_init
#  define rsx_backend_present rsx_d3d12_backend_present
#  define rsx_backend_pump    rsx_d3d12_backend_pump_messages
#  define RSX_BACKEND_NAME    "D3D12"
#elif defined(__APPLE__)
extern "C" int  rsx_metal_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_metal_backend_present(void);
extern "C" int  rsx_metal_backend_pump_messages(void);
#  define rsx_backend_init    rsx_metal_backend_init
#  define rsx_backend_present rsx_metal_backend_present
#  define rsx_backend_pump    rsx_metal_backend_pump_messages
#  define RSX_BACKEND_NAME    "Metal"
#else
extern "C" int  rsx_null_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_null_backend_present(void);
extern "C" int  rsx_null_backend_pump_messages(void);
#  define rsx_backend_init    rsx_null_backend_init
#  define rsx_backend_present rsx_null_backend_present
#  define rsx_backend_pump    rsx_null_backend_pump_messages
#  define RSX_BACKEND_NAME    "null (headless software)"
#endif

/* ---------------------------------------------------------------------------
 * Configuration
 * -----------------------------------------------------------------------*/
/* The flat VM must span every region the PS3 memory map uses, not just the
 * game image: sys_ppu_thread_create puts thread stacks at 0xD0000000, so a
 * smaller arena makes every spawned thread's stack access out of bounds. */
#define VM_SIZE       0x100010000ull   /* the full 32-bit guest space + a 64K guard */
#define STACK_TOP     0x0FF00000u      /* main-thread stack, below the 0x10000000 segment */
#define WINDOW_WIDTH  1280
#define WINDOW_HEIGHT 720

/* ---------------------------------------------------------------------------
 * Frame clock
 * -----------------------------------------------------------------------*/
/* On real hardware the RSX raises a vblank interrupt about 60 times a second
 * and that is what drives the game's frame loop. With no RSX it is synthesized
 * here: a host thread calls cellGcmTickVBlank/TickFlip, which invoke the
 * handlers the guest registered, and drains the GCM FIFO. Without this the
 * title initialises, registers its handlers and then waits forever.
 *
 * The ticks are driven off real elapsed time rather than off how long present()
 * took. A hidden or occluded window makes present block hard, and pacing the
 * ticks behind it paces the whole game behind it. */
static std::atomic<unsigned> g_frames_presented{0};

/* Frames handed to the backend at a guest FLIP boundary -- one per frame the
 * guest actually finished. The presents made before the guest's first flip, so
 * a fresh window is not left blank through a long boot, carry no guest frame
 * and are deliberately not counted. */
extern "C" unsigned ppu_boot_frames_presented(void)
{
    return g_frames_presented.load(std::memory_order_acquire);
}

#ifdef RSX_BACKEND_SPLIT_PRESENT
static bool g_present_open;     // a present_begin not yet finished; frame-clock thread only

// SARPBC_SPLIT_PRESENT=0 presents whole again (waits for the frame it submitted).
static bool getenv_split_present()
{
    static const bool on = [] { const char* e = getenv("SARPBC_SPLIT_PRESENT"); return !(e && *e == '0'); }();
    return on;
}

static void present_finish_pending(void)
{
    if (!g_present_open) return;
    g_present_open = false;
    rsx_backend_present_finish();
}

// Finish it now if the GPU is done with the copy; never wait. The drain right after a flip is
// short (the guest queues the next frame only once the flip is serviced), so a blocking finish
// there stalled the clock for the GPU's whole frame time.
static void present_finish_if_ready(void)
{
    if (g_present_open && rsx_backend_present_ready()) present_finish_pending();
}
#else
static void present_finish_pending(void) {}
static void present_finish_if_ready(void) {}
#endif

static void present_guest_frame(void)
{
#ifdef RSX_BACKEND_SPLIT_PRESENT
    present_finish_pending();   // the previous frame's, if its drain did not already
    if (getenv_split_present()) {
        rsx_backend_present_begin();
        g_present_open = true;
    } else
#endif
    rsx_backend_present();
    /* This thread increments and guest threads read: a real atomic, not a
     * volatile, which gives no ordering on arm64 or in the C++ model. */
    g_frames_presented.fetch_add(1, std::memory_order_release);
}

/* The next time a capped flip may complete: one interval after the last
 * deadline, or after now when the frame was late by more than an interval. */
static unsigned long long flip_cap_deadline(unsigned long long prev, unsigned long long interval,
                                            unsigned long long now)
{
    if (!interval) return 0;
    unsigned long long next = prev + interval;
    return next + interval < now ? now + interval : next;
}

/* Hold the thread until `deadline` (monotonic us): sleeps while more than 2 ms
 * remain, then yields, so the cap lands within ~0.1 ms of the interval. */
static void flip_cap_wait(unsigned long long deadline)
{
    for (;;) {
        struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
        const unsigned long long now = (unsigned long long)ts.tv_sec * 1000000ull + (unsigned long long)ts.tv_nsec / 1000ull;
        if (now >= deadline) return;
        if (deadline - now > 2000) Sleep(1); else Sleep(0);
    }
}

static DWORD WINAPI frame_clock(LPVOID)
{
    const char* title = getenv("PS3_TITLE");
    if (!title || !*title) title = "ps3recomp";

    int rsx_ok = (rsx_backend_init(WINDOW_WIDTH, WINDOW_HEIGHT, title) == 0);
    fprintf(stderr, "[rsx] %s backend init %s\n", RSX_BACKEND_NAME,
            rsx_ok ? "OK -- window open" : "FAILED");

    unsigned  last_flip = 0;

    /* FRAME_CLOCK_SLEEP_MS: the outer drain cadence (default 1 ms: with the
     * render-pass sharing and inlined vertex decode, 4 ms left the thread idle a
     * quarter of the time and held the menus at ~37 fps against ~53 at 1 ms, the
     * arena 31 against 34; the guest waits on labels this drain writes). FRAME_CLOCK_STATS=1: where this
     * thread's time goes, as ms per 5 s in sleep / FIFO drain / present. */
    DWORD outer_ms = 1;
    if (const char* e = getenv("FRAME_CLOCK_SLEEP_MS")) {
        char* end = nullptr;
        const long v = strtol(e, &end, 10);
        if (end != e && *end == '\0' && v >= 0 && v <= 100) outer_ms = (DWORD)v;
        else fprintf(stderr, "[frame_clock] ignoring FRAME_CLOCK_SLEEP_MS='%s' (want 0-100)\n", e);
    }
    const int stats = getenv("FRAME_CLOCK_STATS") != nullptr;
    /* SARPBC_FPS_CAP=<n> (default off; 0 or >= 60 = off): an opt-in limiter. The game's own
     * config asks for UE3 frame smoothing between 22 and 60 fps with vsync (COALESCED.INI,
     * docs/frame-pacing.md) and no web source gives a hard 30 fps cap, so the faithful
     * default is no cap (user, 2026-10-21: as close to the original as possible). The guest here is bound by how fast the drain runs, not by
     * vsync (completing flips on the tick does not slow it), so the cap holds each
     * guest flip's present back to a deadline that advances by whole intervals. The
     * drain thread is the one waiting, which is what the RSX does at a flip: the
     * next frame's commands and the labels the game fences on wait too. A slow frame
     * is presented at once, never rounded up to a whole number of vblanks. */
    long cap_fps = 0;
    if (const char* e = getenv("SARPBC_FPS_CAP")) {
        char* end = nullptr;
        const long v = strtol(e, &end, 10);
        if (end != e && *end == '\0' && v >= 0 && v <= 1000) cap_fps = v;
        else fprintf(stderr, "[frame_clock] ignoring SARPBC_FPS_CAP='%s' (want 0-1000)\n", e);
    }
    const int cap_on = cap_fps > 0 && cap_fps < 60;
    const unsigned long long cap_interval_us = cap_on ? 1000000ull / (unsigned long long)cap_fps : 0;
    unsigned long long next_flip_us = 0;
    auto now_us = []() -> unsigned long long {
        struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
        return (unsigned long long)ts.tv_sec * 1000000ull + (unsigned long long)ts.tv_nsec / 1000ull;
    };
    /* The vblank deadline is a fractional 60 Hz on the monotonic clock
     * (16666.67 us, kept in 1/3 us): a fixed 16 ms step ran at 62.5 Hz. */
    unsigned long long next_tick_x3 = now_us() * 3ull;
    unsigned long long st_sleep = 0, st_fifo = 0, st_present = 0, st_t0 = now_us(), st_n = 0;
    unsigned st_presents = 0;
    #define FC_TIMED(acc, stmt) do { if (stats) { unsigned long long _t = now_us(); stmt; acc += now_us() - _t; } else { stmt; } } while (0)

    for (;;) {
        FC_TIMED(st_sleep, Sleep(outer_ms));
        if (stats && now_us() - st_t0 >= 5000000ull) {
            fprintf(stderr, "[frame_clock] per 5 s: sleep %llu ms, fifo %llu ms, present %llu ms (%u presents), loops %llu\n",
                    st_sleep / 1000, st_fifo / 1000, st_present / 1000, st_presents, st_n);
            st_sleep = st_fifo = st_present = st_n = 0; st_presents = 0; st_t0 = now_us();
        }
        st_n++;
        const unsigned long long now_x3 = now_us() * 3ull;

        int fired = 0;
        while ((long long)(now_x3 - next_tick_x3) >= 0 && fired < 240) {
            cellGcmTickVBlank();
            cellGcmTickFlip();
            /* Present a pending flip BEFORE draining any further. A PPU-side
             * request or the previous drain's FIFO marker marks the completed
             * frame; another drain could overwrite it with next-frame draws. */
            if (rsx_ok && cellGcm_take_flip_pending()) {
                if (cap_on) FC_TIMED(st_sleep, flip_cap_wait(next_flip_us));
                FC_TIMED(st_present, present_guest_frame()); st_presents++;
                last_flip = cellGcm_flip_request_count();
                next_flip_us = flip_cap_deadline(next_flip_us, cap_interval_us, now_us());
            }
            /* Drain the FIFO every tick. This is what writes the RSX sync-fence
             * labels the game's per-frame logic blocks on, so it has to keep
             * advancing at 60 Hz even while present() throttles. */
            if (rsx_ok) { FC_TIMED(st_fifo, cellGcm_rsx_process_fifo()); FC_TIMED(st_present, present_finish_if_ready()); }
            next_tick_x3 += 50000ull;    /* 1/60 s = 16666.67 us = 50000/3 us */
            fired++;
        }
        if (fired >= 240) next_tick_x3 = now_x3;   /* fell too far behind -- resync */

        /* Drain at the outer cadence too, not only on the 16 ms tick: titles
         * fence every render pass on a label the drain writes, and one wave of
         * those at 16 ms apiece paces the guest into single-figure frame rates.
         * The real RSX writes them in microseconds. */
        if (rsx_ok) {
            if (cellGcm_take_flip_pending()) {
                if (cap_on) FC_TIMED(st_sleep, flip_cap_wait(next_flip_us));
                FC_TIMED(st_present, present_guest_frame()); st_presents++;
                last_flip = cellGcm_flip_request_count();
                next_flip_us = flip_cap_deadline(next_flip_us, cap_interval_us, now_us());
            }
            FC_TIMED(st_fifo, cellGcm_rsx_process_fifo());
            FC_TIMED(st_present, present_finish_if_ready());   // once its copy has run beside the drains

            if (rsx_backend_pump() != 0) {
                rsx_ok = 0;              /* window closed */
                continue;
            }
            /* Present on a guest flip. A present on a fixed clock can catch the
             * drain mid-frame and flash a partial one. Before the first flip
             * present freely, so the window is not blank during boot. */
            unsigned fc = cellGcm_flip_request_count();
            /* A queued ordinary marker increments fc before it executes.
             * Require and claim the completed-frame flag here too: otherwise
             * we present early, or present this marker again next iteration. */
            if (fc != last_flip && cellGcm_take_flip_pending()) {
                if (cap_on) FC_TIMED(st_sleep, flip_cap_wait(next_flip_us));
                FC_TIMED(st_present, present_guest_frame()); st_presents++;
                last_flip = fc;
                next_flip_us = flip_cap_deadline(next_flip_us, cap_interval_us, now_us());
            } else if (fc == 0) {
                present_finish_pending();
                rsx_backend_present();
            }
        }
        /* Report completed guest boundaries, never the pre-first-flip fallback
         * presents. A fresh timestamp includes time spent draining/presenting. */
        sarpbc_frame_stats_tick(GetTickCount64(), ppu_boot_frames_presented());
    }
    return 0;
}

/* ---------------------------------------------------------------------------
 * Guest file system
 * -----------------------------------------------------------------------*/
/* SARPBC is an HDD (PSN) title: everything it reads lives under
 * /dev_hdd0/game/NPUB30035/, which tools/extract.sh lays out as
 * <vfs>/dev_hdd0/game/NPUB30035/. The runtime has three path translators
 * (ppu_fs.cpp, sys_fs.c, cellFs.c) with different knobs, so point all of them
 * at that one tree:
 *
 *   PS3_VFS_ROOT    <vfs>/dev_hdd0          mount prefix stripped, rest appended
 *   PS3_HDD0_ROOT   <vfs>/dev_hdd0          /dev_hdd0/... in ppu_fs.cpp
 *   PS3_USRDIR_BASE <...>/game/NPUB30035    ".../USRDIR/..." in sys_fs.c
 *   PS3_BOOT_PATH   the guest's argv[0]     UE3 derives its base dir from it
 *
 * <vfs> is argv[2], else ./vfs. Each variable already set in the environment
 * is left alone. */
#ifdef _WIN32
/* Environment defaults for the later Windows build. */
static int setenv(const char* k, const char* v, int overwrite)
{
    if (!overwrite && getenv(k)) return 0;
    return _putenv_s(k, v);
}
#endif

#define TITLE_ID   "NPUB30035"
#define BOOT_PATH  "/dev_hdd0/game/" TITLE_ID "/USRDIR/EBOOT.BIN"

static std::string s_vfs_root;

static bool setup_vfs(const char* vfs_arg)
{
    /* realpath has no destination-size parameter. Let the platform allocate
     * its result, then retain dynamic strings through every derived path. */
#ifdef _WIN32
    char* resolved = _fullpath(nullptr, vfs_arg, 0);
#else
    char* resolved = realpath(vfs_arg, nullptr);
#endif
    if (!resolved) {
        fprintf(stderr, "ERROR: cannot resolve VFS root %s -- check the path and run tools/extract.sh\n", vfs_arg);
        return false;
    }
    const std::string hdd0 = std::string(resolved) + "/dev_hdd0";
    free(resolved);
    const std::string game = hdd0 + "/game/" TITLE_ID;

    if (setenv("PS3_VFS_ROOT", hdd0.c_str(), 0) ||
        setenv("PS3_HDD0_ROOT", hdd0.c_str(), 0) ||
        setenv("PS3_USRDIR_BASE", game.c_str(), 0) ||
        setenv("PS3_BOOT_PATH", BOOT_PATH, 0) ||
        setenv("PS3_TITLE", "Supersonic Acrobatic Rocket-Powered Battle-Cars", 0)) {
        fprintf(stderr, "ERROR: cannot configure the VFS environment\n");
        return false;
    }
    const std::string sfo = game + "/PARAM.SFO";
    cellGame_init_from_paramsfo(sfo.c_str());

    s_vfs_root = getenv("PS3_VFS_ROOT");
    ppu_vfs_root = s_vfs_root.c_str();   /* stable until the next setup, before guest threads start */
    return true;
}

/* ---------------------------------------------------------------------------
 * Guest VM
 * -----------------------------------------------------------------------*/
#ifdef _WIN32
/* Demand-paging for the flat VM: reserve the whole 4 GB guest space, which
 * costs no commit, and commit each 64 KB page on first access. Every 32-bit
 * guest offset is then valid, so a garbage guest pointer reads zero instead of
 * killing the process. Faults outside the arena fall through untouched. */
static LONG WINAPI vm_commit_veh(EXCEPTION_POINTERS* ep)
{
    if (ep->ExceptionRecord->ExceptionCode == EXCEPTION_ACCESS_VIOLATION) {
        ULONG_PTR fault = ep->ExceptionRecord->ExceptionInformation[1];
        uintptr_t base  = (uintptr_t)vm_base;
        if (vm_base && fault >= base && fault < base + VM_SIZE) {
            void* page = (void*)(fault & ~(uintptr_t)0xFFFF);
            if (VirtualAlloc(page, 0x10000, MEM_COMMIT, PAGE_READWRITE))
                return EXCEPTION_CONTINUE_EXECUTION;
        }
    }
    return EXCEPTION_CONTINUE_SEARCH;
}
#endif

static bool alloc_guest_vm(void)
{
#ifdef _WIN32
    AddVectoredExceptionHandler(1, vm_commit_veh);
    vm_base = (uint8_t*)VirtualAlloc(NULL, VM_SIZE, MEM_RESERVE, PAGE_READWRITE);
    ppu_vm_size = 0;              /* the whole space is backed; no OOB guard needed */
#else
    /* The template's calloc(0xE0000000) does not work here: glibc hands back a
     * pointer 16 bytes into its mmap, so vm_base is not page aligned and every
     * vm_commit() mprotect fails (sys_memory_allocate -> ENOMEM, and the game's
     * allocator spins on NULL). The runtime also needs the low 32 bits of
     * vm_base to be zero (GUEST_EA truncates host pointers; see vm_init in
     * runtime/memory/vm.h). So: map the whole guest space read/write, lazily
     * backed and zero-filled, on a 4 GB boundary -- over-map by 4 GB and trim. */
    const uintptr_t align = 0x100000000ull;
    const size_t    span  = VM_SIZE + align;
    uint8_t* raw = (uint8_t*)mmap(NULL, span, PROT_READ | PROT_WRITE,
                                  MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    if (raw == MAP_FAILED) return false;
    uint8_t* base = (uint8_t*)(((uintptr_t)raw + align - 1) & ~(align - 1));
    if (base > raw) munmap(raw, (size_t)(base - raw));
    if (raw + span > base + VM_SIZE) munmap(base + VM_SIZE, (size_t)(raw + span - (base + VM_SIZE)));
    vm_base = base;
    ppu_vm_size = 0;              /* the whole space is backed; no OOB guard needed */
#endif
    return vm_base != nullptr;
}

/* ---------------------------------------------------------------------------
 * Main
 * -----------------------------------------------------------------------*/
static void harness_guest_caller(uint32_t opd, uint64_t a0, uint64_t a1,
                                 uint64_t a2, uint64_t a3, uint64_t a4,
                                 uint64_t a5, uint64_t a6, uint64_t a7)
{
    ppu_guest_call(opd, a0, a1, a2, a3, a4, a5, a6, a7);
}

int main(int argc, char** argv)
{
    if (argc < 2) {
        printf("usage: %s <EBOOT.elf> [vfs root, default ./vfs]\n", argv[0]);
        return 2;
    }
    if (!setup_vfs(argc > 2 ? argv[2] : "vfs"))
        return 1;

#ifdef _WIN32
#pragma comment(lib, "winmm.lib")
    /* 1 ms timer resolution. The default granularity is about 15.6 ms, which
     * inflates every shorter wait the title makes and throttles the whole
     * thing. POSIX timers are already fine-grained. */
    timeBeginPeriod(1);
    setvbuf(stdout, NULL, _IONBF, 0);   /* unbuffered: do not lose prints on a kill */
#endif

    printf("=== SARPBC (NPUB30035) -- ps3recomp, %s ===\n", RSX_BACKEND_NAME);

    if (!alloc_guest_vm()) {
        fprintf(stderr, "ERROR: could not allocate the guest address space\n");
        return 1;
    }

    uint32_t entry = ppu_load_elf(argv[1]);
    if (!entry) {
        fprintf(stderr, "ERROR: could not load %s\n", argv[1]);
        return 1;
    }

    printf("[boot] VFS root: %s\n", ppu_vfs_root);
    printf("[boot] argv[0]:  %s\n", getenv("PS3_BOOT_PATH"));

    ppu_recomp_register();   /* lifted function table -> address map */
    ps3_load_prx_modules();  /* this game's lifted system PRX, if it has any */
    ppu_hle_init();          /* firmware import NID -> HLE handlers */
    sarpbc_register_edgezlib();   /* _cellSpursLFQueuePushBody for Edge zlib */
    ppu_sysprx_register();   /* boot-critical CRT */
    ppu_fs_register();       /* cellFs over the game directory */
    lv2_init_syscalls();     /* the lv2 syscall table */

    /* Install the guest-callback hook, then start the frame clock. It no-ops
     * until the title registers its vblank and flip handlers during init. */
    g_ps3_guest_caller = harness_guest_caller;
    if (!CreateThread(NULL, 4u * 1024 * 1024, frame_clock, NULL, 0, NULL)) {
        fprintf(stderr, "ERROR: could not start the frame clock thread\n");
        return 1;
    }

    printf("\n[boot] dispatching entry OPD 0x%08X (stack top 0x%08X)\n\n",
           entry, STACK_TOP);

    int rc = ppu_run(entry, STACK_TOP);
    printf("\n[boot] ppu_run returned %d (entry function unwound)\n", rc);

    /* A title that called sys_process_exit never reaches this line: that path
     * ends in the host exit(). Getting here means the entry function returned
     * instead, so hand back the status the guest published if it published
     * one. Returning a hardcoded 0 would report success for a run that never
     * got anywhere. */
    return g_sys_process_exit_called ? (int)g_sys_process_exit_code : 0;
}
