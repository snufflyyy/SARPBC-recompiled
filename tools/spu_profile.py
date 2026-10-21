#!/usr/bin/env python3
"""Helper for tools/spu_profile.sh (task T029). Python 3 stdlib only.

  spu_profile.py snap PID OUT.json   per-thread utime/stime/comm snapshot
  spu_profile.py stacks PID OUT.txt --since proc0.json --secs N --interval S --sample 0|1
                                     until proc0's time + N: every S seconds, unwind each
                                     thread /proc shows running (`eu-stack -1 -p TID`)
                                     (--sample 0: just wait out the window)
  spu_profile.py report --work D --out F --perf 0|1 --stacks 0|1 --why TEXT --boot FILE --secs N
"""
import argparse, collections, json, os, re, subprocess, time

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
    return {"t": time.time(), "monotonic": time.monotonic(), "threads": threads,
            "proc_ticks": int(f[11]) + int(f[12])}


def running_tids(pid):
    """Threads in state R right now (on a CPU or runnable), from /proc."""
    out = []
    base = "/proc/%s/task" % pid
    for tid in os.listdir(base):
        try:
            st = open("%s/%s/stat" % (base, tid)).read()
        except OSError:
            continue
        if st[st.rindex(")") + 2:st.rindex(")") + 3] == "R":
            out.append(tid)
    return out


STACK_FRAMES = 12


def stacks(pid, out, since, secs, interval, sample):
    """Poor man's profiler for hosts where perf cannot record. Every interval: list the
    threads /proc shows in state R, and unwind each of them alone with
    `eu-stack -1 -p TID`, which ptrace-stops only that thread (~25 ms on the 01.09 game;
    the rest of the game keeps running). Stop times are logged for the report."""
    deadline = json.load(open(since))["t"] + secs
    with open(out, "w") as f:
        while True:
            left = deadline - time.time()
            if left <= 0:
                break
            if not sample:
                time.sleep(left)
                break
            tick = time.time()
            try:
                run = running_tids(pid)
            except OSError:
                break                       # game gone: stop sampling
            for tid in run:
                t0 = time.time()
                if t0 >= deadline:
                    break
                try:
                    r = subprocess.run(["eu-stack", "-1", "-p", tid, "-m", "-n", str(STACK_FRAMES)],
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       text=True, errors="replace", timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    continue
                # rc 1 = some frames incomplete (normal with -n); 2 = nothing shown (exited)
                if r.returncode == 2:
                    continue
                f.write("@@ capture t=%.3f dur=%.3f rc=%d running=%s\n" % (
                    t0, time.time() - t0, r.returncode, tid))
                f.write(r.stdout)
            f.flush()
            time.sleep(max(0.0, min(interval - (time.time() - tick), deadline - time.time())))


EU_FRAME = re.compile(r"^#\d+\s+0x[0-9a-fA-F]+\s?(.*)$")


def strip_args(sym):
    """'func_00B60184(ppu_context*)' -> 'func_00B60184' (demangled argument list)."""
    if not sym.endswith(")"):
        return sym
    depth = 0
    for i in range(len(sym) - 1, -1, -1):
        depth += {")": 1, "(": -1}.get(sym[i], 0)
        if depth == 0:
            return sym[:i] if i else sym
    return sym


def parse_stacks(path):
    """eu-stack captures -> (samples, meta). samples: (tid, chain) for threads that
    /proc showed running before the capture; chain = [(sym, dso), ...], leaf first."""
    samples, meta = [], {"captures": 0, "stopped": 0.0, "first": None, "last": None,
                         "running": 0}
    running, tid, chain = set(), None, []

    def flush():
        if tid is not None and chain and tid in running:
            samples.append((tid, chain))
    with open(path, errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("@@ capture "):
                flush()
                tid, chain = None, []
                kv = dict(x.split("=", 1) for x in line[11:].split() if "=" in x)
                running = set(t for t in kv.get("running", "").split(",") if t)
                meta["captures"] += 1
                meta["running"] += len(running)
                meta["stopped"] += float(kv.get("dur", 0))
                t = float(kv.get("t", 0))
                meta["first"] = t if meta["first"] is None else meta["first"]
                meta["last"] = t + float(kv.get("dur", 0))
                continue
            m = re.match(r"^TID (\d+):", line)
            if m:
                flush()
                tid, chain = m.group(1), []
                continue
            m = EU_FRAME.match(line)
            if m and tid is not None:
                rest = m.group(1)
                if rest.startswith("- "):
                    sym, dso = "", rest[2:]
                elif " - " in rest:
                    sym, dso = rest.rsplit(" - ", 1)
                else:
                    sym, dso = rest, ""
                chain.append((strip_args(sym.strip()) or "?", dso.strip()))
    flush()
    return samples, meta


# Leaf frames that mean "asleep in the kernel": a stacks sample whose thread /proc showed
# running but which eu-stack found here had blocked before the capture reached it (the
# capture walks threads one by one for ~0.2 s). perf never samples these.
BLOCKING = re.compile(r"^(__)?(pthread_cond_(timed|clock)?wait|pthread_join|clock_nanosleep|"
                      r"nanosleep|usleep|poll|ppoll|select|pselect6?|epoll_p?wait|read|recv|"
                      r"recvmsg|sem_(timed|clock)?wait|futex_abstimed_wait_common|"
                      r"lll_lock_wait|syscall|sigtimedwait|wait4|waitpid)(64)?$")


def thread_kind(chain):
    """What kind of host thread a stack belongs to, from any frame in it."""
    syms = [sym for sym, _ in chain]
    if any(SPU_FUNC.match(x) or x.startswith(("spu_drain", "spu_run", "spu_workload")) for x in syms):
        return "SPU"
    if any(PPU_FUNC.match(x) for x in syms):
        return "PPU"
    if any(x in ("frame_clock", "cellGcm_rsx_process_fifo") or x.startswith(("gcm_rsx", "rsx_")) for x in syms):
        return "RSX"
    if any(x.startswith(("vk_", "ps3_vk")) for x in syms):
        return "Vulkan"
    return "host"


def leaf(chain):
    """Leaf frame to classify. An unnamed libc/ld frame (a syscall stub) takes the
    nearest named caller (clock_nanosleep, pthread_cond_wait, ...)."""
    for sym, dso in chain[:4]:
        if sym not in ("?", "[unknown]", ""):
            return sym, dso
        if not re.search(r"libc|libpthread|ld-linux", os.path.basename(dso or "")):
            break
    return chain[0]


# Eight float32 mixer channels at 48 kHz (activity windows, not whole-run rates).
MIXER_TARGET_BPS = 48_000 * 8 * 4

# spu_<sha256>_spu_func_<ls>, spu_prxjob_<id>_..., spu_ovl_<name>_<ls>_... (overlays)
SPU_FUNC = re.compile(r"^spu_([0-9a-z_]+?)_spu_func_([0-9a-fA-F]+)")
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
        img = m.group(1)
        return "spu_lifted", img[:12] if re.fullmatch(r"[0-9a-f]{64}", img) else img
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


def runtime_metrics(text: str, start_ms: float | None, end_ms: float | None) -> dict:
    """Guest counter rates for the sample window; mixer rates are boot log windows.

    No frame data is inferred from dumps, HLE chatter or backend presentations.
    Missing/stale/reset telemetry cannot establish the requested FPS target.
    """
    result = {"frame_fps": None, "frame_reason": "guest-frame telemetry unavailable",
              "mixer_put_bps": [float(x) for x in re.findall(
                  r"\[dma-range\] (\d+(?:\.\d+)?) B/s put,", text)],
              "mixer_waits": [float(x) for x in re.findall(
                  r"\[ef-stats\] flag=0x01372000 waits=(\d+(?:\.\d+)?)/s", text)]}
    if start_ms is None or end_ms is None:
        return result
    # Mixer lines carry no time stamp, but stderr is line-ordered: a line printed
    # between two in-window frame-stats lines was printed inside the window (each
    # [dma-range] rate covers the 5 s before it was printed).
    inside, win_puts, win_waits = False, [], []
    for line in text.splitlines():
        m = re.match(r"\[frame-stats\] clock_ms=(\d+)", line)
        if m:
            inside = start_ms <= int(m.group(1)) < end_ms
            continue
        if not inside:
            continue
        m = re.match(r"\[dma-range\] (\d+(?:\.\d+)?) B/s put,", line)
        if m:
            win_puts.append(float(m.group(1)))
        m = re.match(r"\[ef-stats\] flag=0x01372000 waits=(\d+(?:\.\d+)?)/s", line)
        if m:
            win_waits.append(float(m.group(1)))
    result.update(mixer_put_window_bps=win_puts, mixer_waits_window=win_waits)
    frames = [(int(t), int(n)) for t, n in re.findall(
        r"\[frame-stats\] clock_ms=(\d+) guest_frames=(\d+)", text)
        if start_ms <= int(t) <= end_ms]
    if (len(frames) < 2 or frames[0][0] - start_ms > 2000
            or end_ms - frames[-1][0] > 2000):
        return result
    rates, gaps = [], []
    for (t0, n0), (t1, n1) in zip(frames, frames[1:]):
        if n1 < n0:
            result["frame_reason"] = "guest-frame counter reset"
            return result
        if t1 <= t0:
            return result
        gaps.append((t1 - t0) / 1000)
        rates.append((n1 - n0) / gaps[-1])
    seconds = (frames[-1][0] - frames[0][0]) / 1000
    result.update(frame_fps=(frames[-1][1] - frames[0][1]) / seconds,
                  frame_seconds=seconds, frame_min_fps=min(rates),
                  frame_max_gap_seconds=max(gaps), frame_reason="")
    return result


def categories(samples, head, tid_name, tid_cpu, parts, unit, drop_blocked=False):
    """Category / per-image / top-symbol tables for perf samples or eu-stack stacks.
    Returns (report lines, {tid: main category})."""
    cats = collections.Counter()
    spu_img = collections.Counter()
    spu_incl = collections.Counter()
    spu_fn = collections.defaultdict(collections.Counter)
    catsym = collections.defaultdict(collections.Counter)
    tid_samples = collections.Counter()
    tid_cats = collections.defaultdict(collections.Counter)
    tid_leaf = collections.defaultdict(collections.Counter)
    blocked = collections.Counter()
    kinds = collections.defaultdict(collections.Counter)
    total = 0
    for tid, chain in samples:
        kinds[tid][thread_kind(chain)] += 1
        sym, dso = leaf(chain)
        if drop_blocked and BLOCKING.match(sym):
            blocked[sym] += 1
            continue
        cat, img = classify(sym, dso)
        incl = img
        if cat != "spu_lifted":
            # a helper, lock or unknown leaf called from lifted SPU code: charge that
            # image in the inclusive per-image column; the leaf keeps its own category.
            for s2, d2 in chain[1:6]:
                c2, i2 = classify(s2, d2)
                if c2 == "spu_lifted":
                    incl = i2
                    break
        total += 1
        cats[cat] += 1
        tid_samples[tid] += 1
        tid_cats[tid][cat] += 1
        tid_leaf[tid][fmt_sym(sym, dso)] += 1
        catsym[cat][fmt_sym(sym, dso)] += 1
        if cat == "spu_lifted":
            spu_img[img] += 1
            spu_fn[img][SPU_FUNC.match(sym).group(2)] += 1
        if incl:
            spu_incl[incl] += 1
    body = ["== On-CPU %s by category (%s) ==" % (unit, head)]
    for c in ORDER:
        body.append("  %s  %7d  %s" % (pct(cats[c], total), cats[c], LABEL[c]))
    body.append("  (blocked time and kernel time are not sampled: see the host-thread table for CPU use)")
    if drop_blocked:
        body.append("  left out, blocked by the time the capture reached the thread: %d (%s)" % (
            sum(blocked.values()), ", ".join("%s %d" % kv for kv in blocked.most_common(5)) or "none"))
    body.append("")
    body.append("== Lifted SPU code by image hash (share of ALL %s; incl. = with helpers it called) ==" % unit)
    if not spu_incl:
        body.append("  none")
    for img, n in spu_incl.most_common():
        body.append("  %s  %7d  spu_%s%s   (leaf in its own code %s, %d)" % (
            pct(n, total), n, img, "..." if len(img) == 12 else "",
            pct(spu_img[img], total).strip(), spu_img[img]))
        for fn, k in spu_fn[img].most_common(8):
            body.append("      %s  %6d  spu_func_%s" % (pct(k, total), k, fn))
    body.append("")
    for c in ORDER[1:]:
        body.append("== Top symbols: %s ==" % LABEL[c])
        for sym, k in catsym[c].most_common(20 if c == "other" else 10):
            body.append("  %s  %7d  %s" % (pct(k, total), k, sym))
        if not catsym[c]:
            body.append("  none")
        body.append("")
    role = {t: k.most_common(1)[0][0] for t, k in kinds.items()}
    body.append("== %s per host thread (CPU from /proc; kind; main category; top leaf) ==" % unit.capitalize())
    for tid, n in tid_samples.most_common(12):
        top_cat = tid_cats[tid].most_common(1)[0][0]
        top_leaf = tid_leaf[tid].most_common(1)[0][0]
        body.append("  %s  %7d  tid %-8s %-10s cpu %5.1f%%  %-6s %-11s %s" % (
            pct(n, total), n, tid, tid_name.get(tid, "(gone)")[:10], tid_cpu.get(tid, 0.0),
            role.get(tid, ""), top_cat, top_leaf[:60]))
    body.append("")
    parts.append("%d %s" % (total, unit))
    parts.append("SPU lifted %s interp %s rt %s" % tuple(pct(cats[c], total).strip() for c in ORDER[:3]))
    parts.append("lock/yield %s" % pct(cats["lock_wait"], total).strip())
    parts.append("PPU %s" % pct(cats["ppu_lifted"], total).strip())
    parts.append("GCM/VK %s" % pct(cats["gcm_vulkan"], total).strip())
    parts.append("other %s" % pct(cats["other"], total).strip())
    if spu_incl:
        parts.append("top images " + ",".join("%s=%s" % (i[:8], pct(n, total).strip())
                                               for i, n in spu_incl.most_common(3)))
    return body, role


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
    tid_name = {t: v["comm"] for t, v in p1["threads"].items()}
    tid_cpu = {tid: v for v, tid, _ in thr}
    roles = {}
    if a.perf == "1":
        samples = list(parse_script(os.path.join(a.work, "perf.script")))
        head = "%d samples, perf -F 499, leaf frame, user space" % len(samples)
        lines, roles = categories(samples, head, tid_name, tid_cpu, parts, "samples")
        body += lines
    elif getattr(a, "stacks", "0") == "1" and os.path.exists(os.path.join(a.work, "stacks.txt")):
        samples, meta = parse_stacks(os.path.join(a.work, "stacks.txt"))
        span = (meta["last"] - meta["first"]) if meta["captures"] else 0
        stopped = 100.0 * meta["stopped"] / span if span > 0 else 0
        mean_ms = 1000.0 * meta["stopped"] / meta["captures"] if meta["captures"] else 0
        head = ("%d captures of threads in state R over %.0f s, one thread stopped %.0f ms "
                "each" % (len(samples), span, mean_ms))
        if a.why:
            body.append("perf not used: %s" % a.why)
        body.append("Stacks sampler: every interval, each thread /proc shows running is unwound alone")
        body.append("(eu-stack -1 -p TID) while the rest of the game runs. Coarse: hundreds of samples,")
        body.append("not perf's tens of thousands; read shares of +-5 points as noise. Thread stops add")
        body.append("up to %.0f%% of one core over the window (%.1f s): compare FPS with an" % (
            stopped, meta["stopped"]))
        body.append("unsampled run (--sampler none).")
        body.append("")
        lines, roles = categories(samples, head, tid_name, tid_cpu, parts, "stacks",
                                  drop_blocked=True)
        body += lines
        parts.append("sampler stops %.1fs" % meta["stopped"])
    else:
        body.append("perf not used: %s" % a.why)
        body.append("")

    # boot_check's PID announcement also names the raw runtime log. Keep old
    # report directories usable even when they predate frame telemetry.
    runtime_log = ""
    announcement = os.path.join(a.work, "boot_check.err")
    if os.path.exists(announcement):
        match = re.search(r"^boot_check:.* log (.+)$", open(announcement).read(), re.M)
        if match and os.path.exists(match.group(1)):
            runtime_log = open(match.group(1), errors="replace").read()
    metrics = runtime_metrics(runtime_log,
                              p0.get("monotonic", 0) * 1000 or None,
                              p1.get("monotonic", 0) * 1000 or None)
    if metrics["frame_fps"] is not None:
        parts.append("guest %.2f FPS over %.1fs (min window %.2f)" % (
            metrics["frame_fps"], metrics["frame_seconds"], metrics["frame_min_fps"]))
    else:
        parts.append("guest FPS n/a (%s)" % metrics["frame_reason"])
    body += ["== Runtime diagnostics ==",
             "  guest frame rates count completed flip-boundary presents, not boot fallback presents"]
    if metrics["frame_fps"] is not None:
        body.append("  guest %.2f FPS over %.1fs, min window %.2f FPS, largest telemetry gap %.2fs" % (
            metrics["frame_fps"], metrics["frame_seconds"], metrics["frame_min_fps"],
            metrics["frame_max_gap_seconds"]))
    else:
        body.append("  " + metrics["frame_reason"])
    wputs = metrics.get("mixer_put_window_bps") or []
    if wputs:
        mean = sum(wputs) / len(wputs)
        parts.append("mixer PUT in window %.0f KB/s (%.1f%% real time, %d windows, min %.0f)" % (
            mean / 1000, mean / MIXER_TARGET_BPS * 100, len(wputs), min(wputs) / 1000))
        body.append("  mixer PUT printed inside the sample window: mean %.0f, min %.0f, max %.0f B/s "
                    "(%d five-second windows; %.1f%% of 8 ch x 48 kHz x f32)" % (
                        mean, min(wputs), max(wputs), len(wputs), mean / MIXER_TARGET_BPS * 100))
    elif metrics.get("mixer_put_window_bps") is not None:
        body.append("  mixer PUT: none printed inside the sample window")
    wwaits = metrics.get("mixer_waits_window") or []
    if wwaits:
        body.append("  01.09 mixer flag 0x01372000 inside the window: mean %.1f waits/s (%d lines)" % (
            sum(wwaits) / len(wwaits), len(wwaits)))
    puts = metrics["mixer_put_bps"]
    if puts and not wputs:
        parts.append("mixer PUT last %.0f KB/s (%.1f%% real time)" % (
            puts[-1] / 1000, puts[-1] / MIXER_TARGET_BPS * 100))
    if puts:
        body.append("  mixer logged PUT windows (whole boot log): min %.0f, max %.0f, last %.0f B/s (%d samples)" % (
            min(puts), max(puts), puts[-1], len(puts)))
    else:
        body.append("  mixer PUT: no logged window")
    waits = metrics["mixer_waits"]
    if waits:
        body.append("  01.09 mixer flag 0x01372000 (whole boot log): last %.1f waits/s" % waits[-1])
    body += ["  in-window mixer lines need SARPBC_FRAME_STATS (frame-stats lines mark the window)",
             "  diagnostic rates print only on activity; silence does not establish real-time mixing", ""]
    # name a thread by what the samples saw it running (every game thread is "sarpbc")
    parts.append("top threads: " + ", ".join(
        "%s %.0f%%" % (roles.get(tid, c) if c == "sarpbc" else c, v) for v, tid, c in thr[:3]))
    summary = "spu_profile %s %ss | %s" % (time.strftime("%Y-%m-%d %H:%M"), a.secs, " | ".join(parts))

    L = [summary, "", "== Host process (/proc/<pid>, over %.1f s) ==" % dt,
         "  process CPU: %.0f%% (100%% = one core)   threads at end: %d" % (pid_cpu, len(p1["threads"])),
         "  top threads by CPU:"]
    for v, tid, comm in thr[:15]:
        L.append("    %6.1f%%  tid %-8s %-16s %s" % (v, tid, comm, roles.get(tid, "")))
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
    r.add_argument("--stacks", default="0")
    k = sp.add_parser("stacks")
    k.add_argument("pid")
    k.add_argument("out")
    k.add_argument("--since", required=True)
    k.add_argument("--secs", type=float, required=True)
    k.add_argument("--interval", type=float, default=0.25)
    k.add_argument("--sample", default="1")
    a = ap.parse_args()
    if a.cmd == "snap":
        json.dump(snap(a.pid), open(a.out, "w"))
    elif a.cmd == "stacks":
        stacks(a.pid, a.out, a.since, a.secs, a.interval, a.sample == "1")
    else:
        report(a)


if __name__ == "__main__":
    main()
