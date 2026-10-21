/*
 * SIGTERM / SIGINT end the run in an orderly way (T018).
 *
 * Without a handler the default action kills the process on the spot: stdio
 * buffers are lost (logs end mid-line) and atexit reports (edgezlib totals) never
 * print. The handler only sets a flag and arms a watchdog; a small thread sees
 * the flag, flushes and calls quick_exit(128+sig): at_quick_exit handlers run (the edgezlib
 * report) but static destructors do not, which would race the live guest threads. If that stalls (a handler waiting on a lock a guest thread holds) the
 * 3 s alarm kills the process with the default SIGALRM, and a second signal
 * leaves at once. SARPBC_NO_CLEAN_EXIT=1 restores the plain default actions.
 */
#ifndef _WIN32
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <atomic>
#include <initializer_list>
#include <thread>

namespace {

std::atomic<int> s_sig{0};

void on_stop_signal(int sig)
{
    int none = 0;
    if (!s_sig.compare_exchange_strong(none, sig)) _exit(128 + sig);   // second signal: leave now
    alarm(3);
}

void watcher()
{
    sigset_t all;
    sigfillset(&all);
    pthread_sigmask(SIG_BLOCK, &all, nullptr);   // the handler runs on another thread
    for (;;) {
        const int sig = s_sig.load();
        if (sig) {
            fprintf(stderr, "\n[exit] signal %d (%s): flushing and exiting\n", sig, strsignal(sig));
            fflush(nullptr);
            quick_exit(128 + sig);
        }
        usleep(20000);
    }
}

struct Installer {
    Installer()
    {
        const char* off = getenv("SARPBC_NO_CLEAN_EXIT");
        if (off && *off && *off != '0') return;
        struct sigaction sa;
        memset(&sa, 0, sizeof sa);
        sa.sa_handler = on_stop_signal;
        sigemptyset(&sa.sa_mask);
        for (int sig : {SIGTERM, SIGINT}) sigaction(sig, &sa, nullptr);
        std::thread(watcher).detach();
    }
} s_installer;

}  // namespace
#endif
