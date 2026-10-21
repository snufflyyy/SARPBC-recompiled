#!/usr/bin/env python3
"""Summarize how far a boot of the port got, from its log (stdlib only).

    tools/boot_report.py report LOG [--run-dir DIR] [--out FILE] [--summary]
    tools/boot_report.py watch  --log LOG --pid PID --run-dir DIR [--dump PPM]
    tools/boot_report.py noise          # print the noise regex, for grep -v -E

`report` works on any run log (e.g. analysis/run9.log). With the --run-dir that
tools/boot_check.sh fills (timeline.jsonl, frames.jsonl, meta.txt, gdb.txt) it
also gives times, frame stats, the exit status and guest stacks. `watch` is the
sampler boot_check.sh runs beside the game: every 0.5 s it records the log's
line count and byte size, and reads each new PS3RECOMP_VK_DUMP frame (the
runtime overwrites one file per dump) for the non-black check of
tools/ppm2png.py. It exits when PID is gone or DIR/stop exists.
"""
import argparse
import hashlib
import json
import os
import re
import signal
import struct
import sys
import time
from collections import Counter, OrderedDict

# Per-frame and polling chatter: docs/debugging.md's filter plus the event-queue
# polls and spin-waits that dominate a 60 s log.
NOISE = (r"^\s+(r[0-9]|rawstk|ARG)|timer_usleep\(30 us\)|opendir|CLEAR_SURFACE|SetFlipImmediate"
         r"|SetPrepareFlip|GET_REPORT|label write|usercmd|sys_memory\] allocate|LWM-|DRAW_ARRAYS"
         r"|port_send|\[WAIT\] event_queue_receive\(.*timeout=0\)|^\s*$")
NOISE_RE = re.compile(NOISE)
# Shown in the report but not counted as progress: runtime housekeeping that
# recurs while the game is stuck (the GCM ring recycle comes every ~25 s).
NOT_PROGRESS_RE = re.compile(r"recycled the title's own ring|^\[spu_workload\] task .* sleeping|"
                             r"^\[null-write\] further stores")

RE_OPEN = re.compile(r"^\[fs\] open '([^']+)' -> (fd \d+|.*)")
RE_ZLIB = re.compile(r"^\[edgezlib\] #(\d+) (?:inflate|copy)")
RE_ZLIB_TOTAL = re.compile(r"^\[edgezlib\] (\d+) requests \(")   # printed at a clean exit
RE_TCREATE = re.compile(r'^\[SYS\] sys_ppu_thread_create tid=(\d+) name="([^"]*)" entry=(0x[0-9A-Fa-f]+)')
RE_TEND = re.compile(r"^\[THREAD (\d+)\] entry RETURNED")
RE_THOST = re.compile(r"^\[THREAD (\d+)\] host thread started, entry=(0x[0-9A-Fa-f]+) hosttid=(\d+)")
RE_MISSING = re.compile(r"^\[fs\] (?:open FAIL '([^']+)'|stat '([^']+)' -> ENOENT)")
RE_UNRES_NID = re.compile(r"^\[hle\] (?:unresolved|UNRESOLVED) NID (0x[0-9A-Fa-f]+)")
RE_UNRES_CALL = re.compile(r"unresolved indirect call -> (0x[0-9A-Fa-f]+)")
RE_UNIMPL = re.compile(r"Unimplemented NID (0x[0-9A-Fa-f]+)")
RE_FLIP = re.compile(r"\] SetFlipImmediate\(")
RE_PKG = re.compile(r"/COOKEDPS3/([^/']+)\.XXX$", re.I)
RE_NORM = re.compile(r"0x[0-9A-Fa-f]+|\d+")

# Lines worth seeing even once; the report shows the first of each and a count.
ALERTS = OrderedDict([
    ("fatal", r"\bFATAL\b|aborting run"),
    ("unresolved-call", r"unresolved indirect call"),
    ("open-fail", r"^\[fs\] open FAIL"),
    ("unimplemented", r"Unimplemented NID"),
    ("hotread", r"^\[HOTREAD\]"),
    ("null-write", r"^\[null-write\] guest"),
    ("null-read", r"^\[null-read\]"),
    ("io-failure", r"IO Failure"),
    ("physx-error", r"^PhysX: Error"),
    ("assert", r"(?i)assert|appErrorf|fatal error|Critical:"),
    ("spu-miss", r"dispatch MISS"),
    ("zlib-fail", r"^\[edgezlib\] .*(did not inflate|unsupported)"),
    ("vk-error", r"^\[RSX vulkan\].*(fail|error)"),
    ("blocked", r"EventFlagWait BLOCKED"),
    ("host-signal", r"(?i)caught signal|SIGSEGV|SIGBUS|SIGILL|segmentation fault"),
])
ALERT_RES = {k: re.compile(v) for k, v in ALERTS.items()}

SIGNALS = {int(s): s.name for s in signal.Signals}


# ---------------------------------------------------------------------------
# watch: sample the running game

def ppm_stats(data):
    """(width, height, sampled, lit, md5) of a complete binary PPM, else None.
    Samples every 97th pixel, the same rule as tools/ppm2png.py."""
    try:
        magic, dims, maxval, px = data.split(b"\n", 3)
        w, h = map(int, dims.split())
    except ValueError:
        return None
    if magic != b"P6" or maxval != b"255" or len(px) != w * h * 3:
        return None   # caught mid-write: try again next tick
    step = 3 * 97
    sampled = len(range(0, len(px), step))
    lit = sum(1 for i in range(0, len(px), step) if px[i:i + 3] != b"\0\0\0")
    return w, h, sampled, lit, hashlib.md5(px).hexdigest()[:12]


def alive(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] not in ("Z", "X")
    except OSError:
        return False


def cmd_watch(a):
    t0 = a.t0 or time.time()
    stop = os.path.join(a.run_dir, "stop")
    tl = open(os.path.join(a.run_dir, "timeline.jsonl"), "a")
    fr = open(os.path.join(a.run_dir, "frames.jsonl"), "a")
    signal.signal(signal.SIGTERM, lambda *_: open(stop, "a").close())
    pos = lines = 0
    seen = None
    nframes = 0
    keep = {}           # name -> PPM bytes, written on exit
    while True:
        last = not alive(a.pid) or os.path.exists(stop)
        now = round(time.time() - t0, 2)
        try:
            with open(a.log, "rb") as f:
                f.seek(pos)
                chunk = f.read()
            pos += len(chunk)
            lines += chunk.count(b"\n")
        except OSError:
            pass
        tl.write(json.dumps({"t": now, "bytes": pos, "lines": lines}) + "\n")
        tl.flush()
        if a.dump:
            try:
                st = os.stat(a.dump)
                key = (st.st_mtime_ns, st.st_size)
                if key != seen:
                    data = open(a.dump, "rb").read()
                    s = ppm_stats(data)
                    if s:
                        seen = key
                        nframes += 1
                        w, h, sampled, lit, md5 = s
                        fr.write(json.dumps({"t": now, "n": nframes, "w": w, "h": h, "sampled": sampled,
                                             "lit": lit, "md5": md5}) + "\n")
                        fr.flush()
                        keep["last"] = data
                        if lit:
                            keep["last_lit"] = data
                            keep.setdefault("first_lit", data)
            except OSError:
                pass
        if last:
            break
        time.sleep(a.interval)
    for name, data in keep.items():
        with open(os.path.join(a.run_dir, f"frame_{name}.ppm"), "wb") as f:
            f.write(data)


# ---------------------------------------------------------------------------
# report

class Timeline:
    """Maps a log line index to the run time at which the sampler first saw it."""

    def __init__(self, path):
        self.samples = []
        if path and os.path.exists(path):
            for ln in open(path):
                try:
                    self.samples.append(json.loads(ln))
                except ValueError:
                    pass

    def __bool__(self):
        return bool(self.samples)

    def at(self, idx):
        for s in self.samples:
            if s["lines"] > idx:
                return s["t"]
        return self.samples[-1]["t"] if self.samples else None

    def end(self):
        return self.samples[-1]["t"] if self.samples else None

    def sample_before(self, t):
        best = self.samples[0] if self.samples else None
        for s in self.samples:
            if s["t"] <= t:
                best = s
        return best


def read_meta(run_dir):
    meta = {}
    p = run_dir and os.path.join(run_dir, "meta.txt")
    if p and os.path.exists(p):
        for ln in open(p):
            if "=" in ln:
                k, v = ln.rstrip("\n").split("=", 1)
                meta[k] = v
    return meta


def sfo_fields(path):
    """Key -> value of a PARAM.SFO (little-endian PSF table); {} if unreadable."""
    try:
        d = open(path, "rb").read()
        magic, _, keys, data, n = struct.unpack_from("<4sIIII", d, 0)
        if magic != b"\0PSF":
            return {}
        out = {}
        for k in range(n):
            ko, fmt, ln, _, do = struct.unpack_from("<HHIII", d, 20 + 16 * k)
            key = d[keys + ko:d.index(b"\0", keys + ko)].decode()
            v = d[data + do:data + do + ln]
            out[key] = struct.unpack("<I", v[:4])[0] if fmt == 0x0404 else v.rstrip(b"\0").decode("utf-8", "replace")
        return out
    except (OSError, ValueError, UnicodeDecodeError, struct.error):
        return {}


def app_version(vfs_dir):
    """APP_VER of the title installed under <vfs>/dev_hdd0/game/*/PARAM.SFO."""
    base = os.path.join(vfs_dir or "", "dev_hdd0", "game")
    try:
        for title in sorted(os.listdir(base)):
            f = sfo_fields(os.path.join(base, title, "PARAM.SFO"))
            if f.get("APP_VER"):
                return f"{title} {f['APP_VER']}"
    except OSError:
        pass
    return None


def load_imports(path):
    names = {}
    try:
        for e in json.load(open(path)):
            names[int(e["nid"], 16)] = (e.get("lib", "?"), e.get("name"))
    except (OSError, ValueError, KeyError):
        pass
    return names


def guest_fps(lines, window_ms=10000):
    """Guest frames per second over the last window of SARPBC_FRAME_STATS lines, or None."""
    pts = []
    for ln in lines:
        if ln.startswith("[frame-stats] "):
            m = re.fullmatch(r"\[frame-stats\] clock_ms=(\d+) guest_frames=(\d+)\s*", ln)
            if m:
                pts.append((int(m.group(1)), int(m.group(2))))
    if len(pts) < 2:
        return None
    t1, n1 = pts[-1]
    t0, n0 = next((p for p in pts if p[0] >= t1 - window_ms), pts[-2])
    if t1 <= t0 or n1 < n0:
        return None
    return (n1 - n0) * 1000.0 / (t1 - t0)


def short(path):
    return path.rsplit("/", 1)[-1]


def fmt_t(t):
    return "" if t is None else f"@{t:.1f}s"


def gdb_summary(path, lwp_names, maxthreads=40):
    """One line per thread running guest code: its guest name (from the log's
    hosttid=), the innermost guest frames and the host frame it sits in. Host
    threads with no guest frame are folded into one line."""
    if not path or not os.path.exists(path):
        return []
    out, other, cur, frames, host = [], Counter(), None, [], None

    def flush():
        if not cur:
            return
        if frames:
            out.append(f"  {cur:<34} {' < '.join(frames[:5])}" + (f"   [{host}]" if host else ""))
        else:
            other[cur.split(" ", 2)[2]] += 1

    for ln in open(path, errors="replace"):
        m = re.match(r'^Thread \d+ \(Thread 0x[0-9a-f]+ \(LWP (\d+)\) "([^"]*)"\)', ln)
        if m:
            flush()
            cur, frames, host = f"LWP {m.group(1)} {lwp_names.get(int(m.group(1)), m.group(2))}", [], None
            continue
        m = re.match(r"^#\d+\s+(?:0x[0-9a-f]+ in )?([^\s(]+)", ln)
        if m and cur:
            fn = m.group(1)
            if fn.startswith("func_"):
                frames.append(fn)
            elif host is None and not frames and " from /" not in ln:
                host = fn   # innermost frame in our binary: the HLE/syscall it waits in
    flush()
    out = out[:maxthreads]
    if other:
        out.append(f"  + {sum(other.values())} host threads with no guest frame: "
                   + ", ".join(f"{n} x{c}" if c > 1 else n for n, c in other.most_common()))
    if not out:
        out.append("  (gdb printed no threads; see gdb.txt)")
    return out


def cmd_report(a):
    rd = a.run_dir
    meta = read_meta(rd)
    tl = Timeline(rd and os.path.join(rd, "timeline.jsonl"))
    frames = []
    if rd and os.path.exists(os.path.join(rd, "frames.jsonl")):
        frames = [json.loads(ln) for ln in open(os.path.join(rd, "frames.jsonl")) if ln.strip()]
    imp = a.imports
    if not imp:   # a staged version (versions/V/build) has its own versions/V/analysis
        own = meta.get("build_dir") and os.path.join(os.path.dirname(meta["build_dir"]), "analysis",
                                                     "imports_named.json")
        imp = own if own and os.path.exists(own) else os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "analysis", "imports_named.json")
    imports = load_imports(imp)

    raw = open(a.log, "rb").read().decode("utf-8", "replace").split("\n")
    if raw and raw[-1] == "":
        raw.pop()

    opens, pkgs, zlib, threads, unres, unres_calls = [], OrderedDict(), [], [], OrderedDict(), OrderedDict()
    zlib_total = 0
    missing = OrderedDict()
    lwp_names = {}
    alerts = OrderedDict()
    flips = 0
    noise = 0
    seen_norm = set()
    new_lines = []          # (idx, line): first appearance of a normalized non-noise line
    tail = OrderedDict()    # normalized -> [count, idx, line], recency order
    for i, ln in enumerate(raw):
        if RE_FLIP.search(ln):
            flips += 1
        if NOISE_RE.search(ln):
            noise += 1
            continue
        m = RE_OPEN.match(ln)
        if m:
            opens.append((i, m.group(1), m.group(2)))
            p = RE_PKG.search(m.group(1))
            if p:
                pkgs.setdefault(p.group(1).upper(), [i, 0])[1] += 1
        m = RE_ZLIB.match(ln)
        if m:
            zlib.append((i, int(m.group(1))))
        m = RE_ZLIB_TOTAL.match(ln)
        if m:
            zlib_total = max(zlib_total, int(m.group(1)))
        m = RE_TCREATE.match(ln)
        if m:
            threads.append({"tid": int(m.group(1)), "name": m.group(2), "entry": m.group(3), "i": i, "end": None})
        m = RE_THOST.match(ln)
        if m:
            tid = int(m.group(1))
            name = next((th["name"] for th in reversed(threads) if th["tid"] == tid), "?")
            lwp_names[int(m.group(3))] = f"tid {tid} {name}"
        m = RE_MISSING.match(ln)
        if m:
            missing.setdefault(m.group(1) or m.group(2), [i, 0, "open FAIL" if m.group(1) else "stat ENOENT"])[1] += 1
        m = RE_TEND.match(ln)
        if m:
            for th in reversed(threads):
                if th["tid"] == int(m.group(1)) and th["end"] is None:
                    th["end"] = i
                    break
        m = RE_UNRES_NID.match(ln) or RE_UNIMPL.search(ln)
        if m:
            unres.setdefault(int(m.group(1), 16), [i, 0])[1] += 1
        m = RE_UNRES_CALL.search(ln)
        if m:
            unres_calls.setdefault(m.group(1), [i, 0])[1] += 1
        for k, r in ALERT_RES.items():
            if r.search(ln):
                if k in alerts:
                    alerts[k][1] += 1
                else:
                    alerts[k] = [i, 1, ln]
        norm = RE_NORM.sub("#", ln.strip())
        if norm not in seen_norm:
            seen_norm.add(norm)
            if not NOT_PROGRESS_RE.search(ln):
                new_lines.append((i, ln))
        if norm in tail:
            c = tail.pop(norm)[0]
            tail[norm] = [c + 1, i, ln]
        else:
            tail[norm] = [1, i, ln]

    t = tl.at if tl else (lambda i: None)
    nlines = len(raw)

    # ---- exit status
    secs = float(meta.get("seconds", 0) or 0)
    status = meta.get("exit_status")
    killed_by_us = meta.get("killed") == "1"
    exit_desc = None
    early = False
    if status is not None and status != "":
        st = int(status)
        sig = st - 128 if st > 128 else None
        if killed_by_us:
            exit_desc = (f"still running at {meta.get('stop_t') or meta.get('elapsed', '?')} s, "
                         f"stopped by boot_check ({SIGNALS.get(sig, sig) if sig else st})")
        else:
            early = True
            how = f"signal {SIGNALS.get(sig, sig)}" if sig else f"exit code {st}"
            exit_desc = f"game ended by itself after {meta.get('elapsed', '?')} s ({how})"
            if meta.get("timeout_fired") == "1":
                early = False
                exit_desc = f"killed by the safety timeout ({how})"

    # ---- progress in the final window
    win = a.window
    prog = None
    end = tl.end() if tl else None
    if meta.get("stop_t") and end is not None:
        end = min(end, float(meta["stop_t"]))   # the game keeps running after SIGTERM
    if tl and end is not None:
        cut = end - win
        s0 = tl.sample_before(cut)
        s1 = tl.sample_before(end)
        idx0, idx1 = s0["lines"], s1["lines"]

        def inwin(i):
            return idx0 <= i < idx1
        prog = {
            "from": round(max(cut, 0), 1), "to": round(end, 1),
            "bytes": s1["bytes"] - s0["bytes"], "lines": s1["lines"] - s0["lines"],
            "opens": sum(1 for o in opens if inwin(o[0])),
            "zlib": sum(1 for z in zlib if inwin(z[0])),
            "threads": sum(1 for th in threads if inwin(th["i"])),
            "unres": sum(1 for i, _ in unres.values() if inwin(i)),
            "new": [ln for i, ln in new_lines if inwin(i)],
            "frames": sum(1 for f in frames if cut <= f["t"] <= end),
            "distinct": len({f["md5"] for f in frames if cut <= f["t"] <= end}),
        }

    # last "new" activity: first sight of a non-noise line, a file open, zlib or thread
    marks = [i for i, _ in new_lines] + [o[0] for o in opens] + [z[0] for z in zlib] + [th["i"] for th in threads] \
        + [i for i, _ in unres.values()] + [i for i, _ in unres_calls.values()]
    if prog:   # activity after the stop (SIGTERM grace) does not count
        marks = [i for i in marks if i < idx1]
    last_mark = max(marks) if marks else None
    last_mark_t = t(last_mark) if last_mark is not None else None

    if early:
        verdict = "CRASHED" if (status and int(status) > 128) else "EXITED"
        verdict += f" at {meta.get('elapsed', '?')}s"
    elif prog is None:
        verdict = "NO-TIMELINE"
    elif prog["bytes"] == 0:
        verdict = f"HUNG (log silent for the last {win:g}s)"
    elif prog["opens"] or prog["zlib"] or prog["threads"] or prog["unres"] or prog["new"]:
        verdict = "PROGRESSING"
    else:
        verdict = f"STALLED since {fmt_t(last_mark_t)[1:] or '?'}"
        if prog["frames"]:
            verdict += " (frames still presented)"

    lit_frames = [f for f in frames if f["lit"]]
    distinct = len({f["md5"] for f in frames})
    every = int(meta.get("dump_every", 0) or 0)
    lo = opens[-1] if opens else None
    alive_threads = [th for th in threads if th["end"] is None]

    # ---- summary line
    parts = [verdict]
    if lo:
        parts.append(f"last open {short(lo[1])}{fmt_t(t(lo[0]))}")
    parts.append(f"pkgs {len(pkgs)}" + (f" ({','.join(list(pkgs)[-1:])} last)" if pkgs else ""))
    nzlib = max(zlib_total, zlib[-1][1] + 1 if zlib else 0)
    parts.append(f"zlib {nzlib}")
    if frames or meta:
        parts.append(f"dumps {len(frames)} lit {len(lit_frames)} distinct {distinct}")
    parts.append(f"flips {flips}")
    fps = guest_fps(raw)
    if fps is not None:
        parts.append(f"guest fps {fps:.1f}")
    parts.append(f"threads {len(threads)}/{len(alive_threads)} alive")
    parts.append(f"unresolved {len(unres)}" + (f"+{len(unres_calls)} calls" if unres_calls else ""))
    if alerts:
        parts.append("alerts " + ",".join(alerts))
    ver = app_version(meta.get("vfs_dir")) if meta else None
    head = " ".join(x for x in ("boot_check", meta.get("date"), ver and "v" + ver.split()[-1],
                                meta.get("rev"), f"{secs:g}s") if x) \
        if meta else f"boot_report {os.path.basename(a.log)}"
    summary = f"{head}: " + " | ".join(parts)

    if a.summary:
        print(summary)
        return

    R = []
    w = R.append
    w(summary)
    w("")
    if meta:
        w(f"run      {meta.get('date', '?')}  branch {meta.get('branch', '?')} @ {meta.get('rev', '?')}  "
          f"{secs:g} s requested, pid {meta.get('pid', '?')}")
    if meta.get("build_dir"):
        w(f"version  {ver or '? (no PARAM.SFO APP_VER)'}  vfs {meta.get('vfs_dir')}")
        w(f"build    {meta['build_dir']}/sarpbc (built {meta.get('build_time', '?')})  game {meta.get('game_dir')}")
    if meta.get("env"):
        w(f"env      {meta['env']}")
    w(f"log      {a.log}  ({nlines} lines, {noise} noise, {len(seen_norm)} distinct non-noise shapes)")
    if exit_desc:
        w(f"exit     {exit_desc}")
    if last_mark is not None:
        verdict_more = f"; last new activity {fmt_t(last_mark_t) + ' ' if last_mark_t is not None else ''}" \
                       f"(line {last_mark + 1} of {nlines})"
    else:
        verdict_more = ""
    w(f"verdict  {verdict}{verdict_more}")

    if prog:
        w("")
        w(f"-- final {win:g} s (t={prog['from']:g}..{prog['to']:g}s)")
        w(f"   log +{prog['bytes'] // 1024} KB / +{prog['lines']} lines; new opens {prog['opens']}, "
          f"zlib {prog['zlib']}, threads {prog['threads']}, unresolved {prog['unres']}, "
          f"new line shapes {len(prog['new'])}, "
          f"dumps {prog['frames']} ({prog['distinct']} distinct)")
        for ln in prog["new"][:8]:
            w(f"   + {ln[:150]}")

    w("")
    w(f"-- packages, first-open order ({len(pkgs)})")
    for n, (name, (i, c)) in enumerate(pkgs.items(), 1):
        w(f"   {n:2} {name:<36} {fmt_t(t(i)):>8}" + (f"  x{c}" if c > 1 else ""))
    w("")
    if lo:
        w(f"-- last file opened {fmt_t(t(lo[0]))} (line {lo[0] + 1}): {lo[1]} -> {lo[2]}")
        w(f"   {len(opens)} opens of {len({o[1] for o in opens})} distinct files")
    else:
        w("-- no file opened (is PS3_FSLOG / [fs] logging on?)")
    w(f"-- Edge zlib: {nzlib} requests" + (f", last logged #{zlib[-1][1]} {fmt_t(t(zlib[-1][0]))}" if zlib else "")
      + ("" if meta.get("env", "").find("SARPBC_ZLIB_TRACE=1") >= 0 or zlib_total
         else "  (only #0-3 are logged without SARPBC_ZLIB_TRACE=1)"))
    if missing:
        w(f"-- missing files: {len(missing)} distinct (last 8)")
        for path, (i, c, how) in list(missing.items())[-8:]:
            w(f"   {how:<11} {fmt_t(t(i)):>8} " + (f"x{c:<3} " if c > 1 else "     ") + path)

    w("")
    if frames:
        f0 = frames[0]
        w(f"-- frames: {len(frames)} dumps (every {every or '?'} presents, so ~{len(frames) * (every or 1)} presented), "
          f"{len(lit_frames)} non-black, {distinct} distinct; {f0['w']}x{f0['h']}; {flips} SetFlipImmediate in log")
        if lit_frames:
            w(f"   first non-black {fmt_t(lit_frames[0]['t'])}, last {fmt_t(lit_frames[-1]['t'])}, "
              f"last frame {fmt_t(frames[-1]['t'])} lit {frames[-1]['lit']}/{frames[-1]['sampled']}")
        changes = [f for k, f in enumerate(frames) if k == 0 or f["md5"] != frames[k - 1]["md5"]]
        w("   image changes at " + " ".join(fmt_t(f["t"])[1:] for f in changes[-12:]))
    elif meta:
        w(f"-- frames: no dump written ({flips} SetFlipImmediate in log)")
    else:
        w(f"-- frames: {flips} SetFlipImmediate in log (no dump data without --run-dir)")

    w("")
    w(f"-- threads: {len(threads)} created, {len(alive_threads)} not returned (+ main tid 1)")
    for th in threads:
        state = f"returned {fmt_t(t(th['end']))}".strip() if th["end"] is not None else "alive"
        w(f"   tid {th['tid']:<3} {th['name']:<24} entry {th['entry']}  created {fmt_t(t(th['i'])):>8}  {state}")

    w("")
    w(f"-- unresolved NIDs: {len(unres)}" + (f"; unresolved indirect calls: {len(unres_calls)}" if unres_calls else ""))
    for nid, (i, c) in unres.items():
        lib, name = imports.get(nid, ("?", None))
        w(f"   0x{nid:08X} {lib}::{name or '(unnamed)'}  x{c}  first {fmt_t(t(i))} line {i + 1}")
    for addr, (i, c) in unres_calls.items():
        w(f"   call -> {addr}  x{c}  first {fmt_t(t(i))} line {i + 1}")

    if alerts:
        w("")
        w("-- alerts (first occurrence)")
        for k, (i, c, ln) in alerts.items():
            w(f"   {k:<16} x{c:<5} {fmt_t(t(i)):>8} line {i + 1}: {ln[:120]}")

    w("")
    w(f"-- last {a.last} distinct non-noise lines (digits folded; xN = repeats)")
    for c, i, ln in list(tail.values())[-a.last:]:
        w(f"   {fmt_t(t(i)):>8} " + (f"x{c:<4} " if c > 1 else "      ") + ln[:150])

    if meta.get("pid"):
        lwp_names.setdefault(int(meta["pid"]), "tid 1 main")
    gs = gdb_summary(rd and os.path.join(rd, "gdb.txt"), lwp_names)
    if meta.get("gdb") == "1" and not gs:
        w("")
        w("-- guest stacks: --gdb skipped, the game had already ended")
    if gs:
        w("")
        w("-- guest stacks at the end (gdb; innermost first)")
        R.extend(gs)

    if rd:
        w("")
        w(f"files    {rd}/  (run.log, timeline.jsonl, frames.jsonl" +
          (", gdb.txt" if os.path.exists(os.path.join(rd, "gdb.txt")) else "") + ")")
        fd = meta.get("frames_dir", rd)
        pngs = sorted(p for p in os.listdir(fd) if p.endswith(".png")) if os.path.isdir(fd) else []
        if pngs:
            w("frames   " + "  ".join(os.path.join(fd, p) for p in pngs))

    text = "\n".join(R) + "\n"
    if a.out:
        with open(a.out, "w") as f:
            f.write(text)
    sys.stdout.write(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report", help="summarize a run log")
    r.add_argument("log")
    r.add_argument("--run-dir", help="boot_check.sh run directory (timeline, frames, meta, gdb)")
    r.add_argument("--out", help="also write the report here")
    r.add_argument("--summary", action="store_true", help="print only the one-line summary")
    r.add_argument("--window", type=float, default=10.0, help="final window for the progress check (s)")
    r.add_argument("--last", type=int, default=20, help="how many distinct tail lines to show")
    r.add_argument("--imports", help="NID names (default: <build_dir>/../analysis/imports_named.json "
                                     "if present, else this checkout's analysis/imports_named.json)")
    wa = sub.add_parser("watch", help="sample a running game (used by boot_check.sh)")
    wa.add_argument("--log", required=True)
    wa.add_argument("--pid", type=int, required=True)
    wa.add_argument("--run-dir", required=True)
    wa.add_argument("--dump", help="the PS3RECOMP_VK_DUMP path")
    wa.add_argument("--t0", type=float, help="run start (epoch seconds)")
    wa.add_argument("--interval", type=float, default=0.5)
    sub.add_parser("noise", help="print the noise regex (grep -v -E \"$(tools/boot_report.py noise)\")")
    a = ap.parse_args()
    if a.cmd == "watch":
        cmd_watch(a)
    elif a.cmd == "report":
        cmd_report(a)
    else:
        print(NOISE)


if __name__ == "__main__":
    main()
