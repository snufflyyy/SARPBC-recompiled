/*
 * A fatal host signal (SIGSEGV, SIGBUS, SIGFPE, SIGILL, SIGABRT) prints what the
 * guest was doing before the process dies: the guest call chain of the crashing
 * thread (the same dump as PS3_NULL_READ_STACK=1) and a host backtrace, then the
 * default action runs, so the core dump and the exit status stay as they were.
 *
 * Before this a crash ended in "dumped core" and a log with no clue which
 * guest function was running (the round-end crash, T052). Best effort: it runs
 * in a dying process and is not async-signal-safe. SARPBC_NO_CRASH_HANDLER=1
 * turns it off, e.g. under a debugger that should see the raw signal.
 */
#ifndef _WIN32
#include <execinfo.h>
#include <initializer_list>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "ppu_recomp.h"

extern "C" void ppu_dump_guest_stack(ppu_context*, const char*);
extern "C" PPU_THREAD_LOCAL ppu_context* g_active_ctx;

namespace {

void on_fatal_signal(int sig, siginfo_t* si, void*)
{
    static volatile sig_atomic_t busy = 0;
    if (!busy) {
        busy = 1;
        fprintf(stderr, "\n[crash] signal %d (%s) at host address %p, fault address %p\n", sig,
                strsignal(sig), (void*)__builtin_return_address(0), si ? si->si_addr : nullptr);
        if (g_active_ctx) ppu_dump_guest_stack(g_active_ctx, "crash");
        else fprintf(stderr, "[crash] not on a guest thread\n");
        void* frames[40];
        const int n = backtrace(frames, 40);
        fprintf(stderr, "[crash] host backtrace:\n");
        fflush(stderr);
        backtrace_symbols_fd(frames, n, STDERR_FILENO);
    }
    signal(sig, SIG_DFL);
    raise(sig);
}

struct Installer {
    Installer()
    {
        const char* off = getenv("SARPBC_NO_CRASH_HANDLER");
        if (off && *off && *off != '0') return;
        struct sigaction sa;
        memset(&sa, 0, sizeof sa);
        sa.sa_sigaction = on_fatal_signal;
        sa.sa_flags = SA_SIGINFO | SA_NODEFER;
        sigemptyset(&sa.sa_mask);
        for (int sig : {SIGSEGV, SIGBUS, SIGFPE, SIGILL, SIGABRT}) sigaction(sig, &sa, nullptr);
    }
} s_installer;

}  // namespace
#endif
