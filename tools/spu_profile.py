#!/usr/bin/env python3
"""Helper for tools/spu_profile.sh (task T029). Python 3 stdlib only.

  spu_profile.py snap PID OUT.json   per-thread utime/stime/comm snapshot
  spu_profile.py report --work D --out F --perf 0|1 --why TEXT --boot FILE --secs N
"""
import argparse, collections, json, os, re, time

HZ = os.sysconf("SC_CLK_TCK")


def snap(pid):
    threads = {}
    base = "/proc/%s" % pid
    for tid in os.listdir(base + "/task"):
        try:
            s = open("%s/task/%s/stat" % (base, tid)).read()
        except OSError:
            continue
        comm = s[s.index("(") + 1:s.rindex(")")]
        f = s[s.rindex(")") + 2:].split()
        threads[tid] = {"comm": comm, "ticks": int(f[11]) + int(f[12])}
    total = open(base + "/stat").read()
    f = total[total.rindex(")") + 2:].split()
    return {"t": time.time(), "threads": threads, "proc_ticks": int(f[11]) + int(f[12])}


SPU_FUNC = re.compile(r"^spu_([0-9a-f]{8,64})_spu_func_([0-9a-fA-F]+)")
PPU_FUNC = re.compile(r"^func_[0-9a-fA-F]{6,8}")
# Classification of a leaf frame; order matters.
RULES = [
    ("lock_wait", re.compile(r"lockline|_spin|spinlock")),   # spu_lockline_lock = reservation-line spin
    ("spu_interp", re.compile(r"spu_interp|SpuInterp|spu_decode")),
    ("spu_runtime", re.compile(r"spu_channel|mfc_|spu_mfc|dma|coheren|spu_shufb|spu_|cellSpurs|spurs|SPURS|sys_spu")),
    ("lock_wait", re.compile(r"pthread_(rwlock|mutex|cond|spin)|futex|sched_yield|__lll|sem_|nanosleep|usleep|lwmutex|lwcond|sys_(rwlock|mutex|cond|semaphore|event|timer)")),
    ("gcm_vulkan", re.compile(r"^vk|^Vk|vulkan|[gG]cm|rsx|Rsx|RSX|libnvidia|libGL|mesa|radv|spirv|amdgpu|ps3_vk")),
]


def classify(sym, dso):
    m = SPU_FUNC.match(sym)
    if m:
        return "spu_lifted", m.group(1)[:12]
    if PPU_FUNC.match(sym):
        return "ppu_lifted", None
    d = os.path.basename(dso or "")
    for name, rx in RULES:
        if rx.search(sym) or (name == "gcm_vulkan" and rx.search(d)):
            return name, None
    if re.search(r"libc|libpthread|ld-linux", d) and re.search(r"cond|lock|wait|yield|sleep", sym):
        return "lock_wait", None
    return "other", None


def parse_script(path):
    """Yield (tid, chain) per sample; chain = [(sym, dso), ...], leaf first."""
    tid, chain = None, []
    with open(path, errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                if tid is not None and chain:
                    yield tid, chain
                tid, chain = None, []
                continue
            if tid is None:
                m = re.match(r"^\s*(\d+)\s*$", line)
                if m:
                    tid = m.group(1)
                continue
            m = re.match(r"^\s*[0-9a-f]+\s+(.*?)\s+\((.*)\)\s*$", line)
            chain.append((m.group(1), m.group(2)) if m else ("?", ""))
    if tid is not None and chain:
        yield tid, chain


def pct(n, tot):
    return "%5.1f%%" % (100.0 * n / tot) if tot else "  n/a "


def fmt_sym(sym, dso):
    if sym in ("[unknown]", "?", ""):
        return "[unknown] (%s)" % os.path.basename(dso or "")
    return sym


ORDER = ["spu_lifted", "spu_interp", "spu_runtime", "lock_wait", "ppu_lifted", "gcm_vulkan", "other"]
LABEL = {"spu_lifted": "lifted SPU code (spu_<hash>_spu_func_*)",
         "spu_interp": "SPU interpreter",
         "spu_runtime": "SPU runtime helpers (channels, mfc, dma, shufb, spurs)",
         "lock_wait": "locks / futex / yield / sleep (user-side)",
         "ppu_lifted": "PPU lifted code (func_XXXXXXXX)",
         "gcm_vulkan": "GCM / Vulkan / driver",
         "other": "other"}


def report(a):
    p0 = json.load(open(os.path.join(a.work, "proc0.json")))
    p1 = json.load(open(os.path.join(a.work, "proc1.json")))
    dt = p1["t"] - p0["t"]
    pid_cpu = (p1["proc_ticks"] - p0["proc_ticks"]) / HZ / dt * 100 if dt > 0 else 0
    thr = []
    for tid, t in p1["threads"].items():
        t0 = p0["threads"].get(tid, {"ticks": 0})
        thr.append(((t["ticks"] - t0["ticks"]) / HZ / dt * 100 if dt > 0 else 0, tid, t["comm"]))
    thr.sort(reverse=True)

    parts = ["host %.0f%% CPU over %.0fs, %d threads" % (pid_cpu, dt, len(p1["threads"]))]
    body = []
    if a.perf == "1":
        cats = collections.Counter()
        spu_img = collections.Counter()
        spu_fn = collections.defaultdict(collections.Counter)
        catsym = collections.defaultdict(collections.Counter)
        tid_samples = collections.Counter()
        total = 0
        for tid, chain in parse_script(os.path.join(a.work, "perf.script")):
            sym, dso = chain[0]
            cat, img = classify(sym, dso)
            if cat in ("spu_runtime", "other"):
                # helper or unknown leaf called from lifted SPU code: charge that function
                # for the per-image view, but keep the leaf's own category in the table.
                for s2, d2 in chain[1:6]:
                    c2, i2 = classify(s2, d2)
                    if c2 == "spu_lifted":
                        break
            total += 1
            cats[cat] += 1
            tid_samples[tid] += 1
            catsym[cat][fmt_sym(sym, dso)] += 1
            if cat == "spu_lifted":
                spu_img[img] += 1
                spu_fn[img][SPU_FUNC.match(sym).group(2)] += 1
        body.append("== On-CPU samples by category (%d samples, -F 499, leaf frame, user space) ==" % total)
        for c in ORDER:
            body.append("  %s  %7d  %s" % (pct(cats[c], total), cats[c], LABEL[c]))
        body.append("  (blocked time and kernel time are not sampled: see the host-thread table for CPU use)")
        body.append("")
        body.append("== Lifted SPU code by image hash (share of ALL samples) ==")
        if not spu_img:
            body.append("  none")
        for img, n in spu_img.most_common():
            body.append("  %s  %7d  spu_%s...   (%s of lifted SPU)" % (pct(n, total), n, img, pct(n, cats["spu_lifted"]).strip()))
            for fn, k in spu_fn[img].most_common(8):
                body.append("      %s  %6d  spu_func_%s" % (pct(k, total), k, fn))
        body.append("")
        for c in ORDER[1:]:
            body.append("== Top symbols: %s ==" % LABEL[c])
            for s, k in catsym[c].most_common(20 if c == "other" else 10):
                body.append("  %s  %7d  %s" % (pct(k, total), k, s))
            if not catsym[c]:
                body.append("  none")
            body.append("")
        tid_name = {t: v["comm"] for t, v in p1["threads"].items()}
        body.append("== Samples per host thread (perf) ==")
        for tid, n in tid_samples.most_common(12):
            body.append("  %s  %7d  tid %s %s" % (pct(n, total), n, tid, tid_name.get(tid, "(gone)")))
        body.append("")
        parts.append("%d samples" % total)
        parts.append("SPU lifted %s interp %s rt %s" % tuple(pct(cats[c], total).strip() for c in ORDER[:3]))
        parts.append("lock/yield %s" % pct(cats["lock_wait"], total).strip())
        parts.append("PPU %s" % pct(cats["ppu_lifted"], total).strip())
        parts.append("GCM/VK %s" % pct(cats["gcm_vulkan"], total).strip())
        if spu_img:
            parts.append("top images " + ",".join("%s=%s" % (i[:8], pct(n, total).strip()) for i, n in spu_img.most_common(3)))
    else:
        body.append("perf not used: %s" % a.why)
        body.append("")

    parts.append("top threads: " + ", ".join("%s %.0f%%" % (c, v) for v, _, c in thr[:3]))
    summary = "spu_profile %s %ss | %s" % (time.strftime("%Y-%m-%d %H:%M"), a.secs, " | ".join(parts))

    L = [summary, "", "== Host process (/proc/<pid>, over %.1f s) ==" % dt,
         "  process CPU: %.0f%% (100%% = one core)   threads at end: %d" % (pid_cpu, len(p1["threads"])),
         "  top threads by CPU:"]
    for v, tid, comm in thr[:15]:
        L.append("    %6.1f%%  tid %-8s %s" % (v, tid, comm))
    L.append("")
    L.extend(body)
    if a.boot and os.path.exists(a.boot):
        L.append("== boot_check summary ==")
        L.extend("  " + x for x in open(a.boot).read().splitlines()[:1])
    open(a.out, "w").write("\n".join(L) + "\n")
    print(summary)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("snap")
    s.add_argument("pid")
    s.add_argument("out")
    r = sp.add_parser("report")
    r.add_argument("--work")
    r.add_argument("--out")
    r.add_argument("--perf")
    r.add_argument("--why", default="")
    r.add_argument("--boot", default="")
    r.add_argument("--secs", default="")
    a = ap.parse_args()
    if a.cmd == "snap":
        json.dump(snap(a.pid), open(a.out, "w"))
    else:
        report(a)


if __name__ == "__main__":
    main()
