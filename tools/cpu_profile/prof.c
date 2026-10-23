// LD_PRELOAD CPU-time sampler: per-thread CPU-clock timers, RIP histogram, dumped to $PROF_OUT.
// PROF_START=<s> PROF_SECS=<s> PROF_HZ=<hz>
#define _GNU_SOURCE
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/syscall.h>
#include <ucontext.h>
#include <link.h>

#define N 65536
static struct { long tid; unsigned long rip; unsigned long cnt; } tab[N];
static volatile int active;
static void handler(int sig, siginfo_t* si, void* uc_) {
    if (!active) return;
    ucontext_t* uc = uc_;
    unsigned long rip = uc->uc_mcontext.gregs[REG_RIP];
    long tid = syscall(SYS_gettid);
    unsigned long h = (rip * 1315423911ul ^ (unsigned long)tid * 2654435761ul) % N;
    for (int i = 0; i < N; i++) {
        unsigned long k = (h + i) % N;
        if (tab[k].cnt == 0) { tab[k].tid = tid; tab[k].rip = rip; tab[k].cnt = 1; return; }
        if (tab[k].rip == rip && tab[k].tid == tid) { tab[k].cnt++; return; }
    }
}
static long armed[512]; static int narmed;
static void arm(long tid, int hz) {
    for (int i = 0; i < narmed; i++) if (armed[i] == tid) return;
    clockid_t cid;
    if (pthread_getcpuclockid(0, &cid)) {}
    cid = ((~(clockid_t)tid) << 3) | 6;   // CPUCLOCK_SCHED | PERTHREAD per-thread cpu clock of tid
    struct sigevent sev; memset(&sev, 0, sizeof sev);
    sev.sigev_notify = SIGEV_THREAD_ID; sev.sigev_signo = SIGPROF; sev._sigev_un._tid = (int)tid;
    timer_t t;
    if (timer_create(cid, &sev, &t)) return;
    struct itimerspec its = {{0, 1000000000 / hz}, {0, 1000000000 / hz}};
    timer_settime(t, 0, &its, NULL);
    if (narmed < 512) armed[narmed++] = tid;
}
static void* sampler(void* a) {
    const char* e;
    int start = (e = getenv("PROF_START")) ? atoi(e) : 60, secs = (e = getenv("PROF_SECS")) ? atoi(e) : 10, hz = (e = getenv("PROF_HZ")) ? atoi(e) : 1000;
    sleep(start);
    struct sigaction sa; memset(&sa, 0, sizeof sa); sa.sa_sigaction = handler; sa.sa_flags = SA_SIGINFO | SA_RESTART; sigaction(SIGPROF, &sa, NULL);
    active = 1;
    for (int s = 0; s < secs * 5; s++) {
        DIR* d = opendir("/proc/self/task");
        if (d) { struct dirent* de; while ((de = readdir(d))) if (de->d_name[0] != '.') arm(atol(de->d_name), hz); closedir(d); }
        usleep(200000);
    }
    active = 0;
    const char* out = getenv("PROF_OUT"); FILE* f = fopen(out ? out : "/tmp/prof.out", "w");
    struct { unsigned long lo; char name[256]; } maps[64]; int nm = 0;
    FILE* m = fopen("/proc/self/maps", "r"); char line[512];
    while (m && fgets(line, sizeof line, m)) {
        unsigned long lo, hi, off; char perm[8], path[256] = "";
        if (sscanf(line, "%lx-%lx %7s %lx %*s %*s %255s", &lo, &hi, perm, &off, path) >= 4 && perm[2] == 'x' && path[0] == '/' && nm < 64) fprintf(f, "MAP %lx %lx %lx %s\n", lo, hi, off, path), nm++;
    }
    for (int i = 0; i < N; i++) if (tab[i].cnt) fprintf(f, "S %ld %lx %lu\n", tab[i].tid, tab[i].rip, tab[i].cnt);
    { DIR* d = opendir("/proc/self/task"); struct dirent* de;
      while (d && (de = readdir(d))) { if (de->d_name[0]=='.') continue; char pth[64], nm[64]="";
        snprintf(pth, sizeof pth, "/proc/self/task/%s/comm", de->d_name); FILE* c = fopen(pth, "r"); if (c) { if (fgets(nm, sizeof nm, c)) nm[strcspn(nm,"\n")]=0; fclose(c);} fprintf(f, "T %s %s\n", de->d_name, nm); } if (d) closedir(d); }
    fclose(f);
    return NULL;
}
__attribute__((constructor)) static void init(void) {
    char exe[256] = ""; ssize_t n = readlink("/proc/self/exe", exe, sizeof exe - 1); if (n > 0) exe[n] = 0;
    if (!strstr(exe, "sarpbc")) return;
    pthread_t t; pthread_create(&t, NULL, sampler, NULL); pthread_detach(t);
}
