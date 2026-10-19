#!/usr/bin/env python3
"""HLE coverage audit: every firmware import of the EBOOT against the HLE registry.

For each import (library, NID, name) it answers:
  * is a handler registered for the NID, and through which path:
      ctx      -- ps3_hle_register_ctx() in the runtime / libs / our src/ (checked first
                  by ps3_hle_call, first registration wins)
      generic  -- the generated ppu_hle_nids.cpp table (gen_hle_nids.py --all)
      online   -- only registered when PS3_NET_ONLINE is set (libs/network/sysNet.c)
      missing  -- nothing; ps3_hle_call fakes r3 = CELL_OK and logs "unresolved NID"
  * is the handler a real implementation or a stub (a heuristic over the C body:
    statements left after removing logging, (void) casts and returns; see --help-class)
  * did a boot hit it (from a PS3_MILESTONE_OUT log or a run log with [HLETRACE] /
    "unresolved NID" lines)

Names the toolkit's NID database cannot produce come from KNOWN_NAMES below. Every
entry there is re-verified at start-up: compute_nid(name) must equal the NID, or the
tool aborts.

Usage:
  tools/hle_coverage.py                                  # defaults: 01.09 primary, 01.02 column
  tools/hle_coverage.py --hits 01.09=analysis/milestone.txt --hits 01.02=analysis/run.log
  tools/hle_coverage.py --set 01.02 analysis/imports_named.json src/recomp/ppu_hle_nids.cpp
  tools/hle_coverage.py --format json --out analysis/hle_coverage.json
  tools/hle_coverage.py --check-names                    # only verify KNOWN_NAMES
  tools/hle_coverage.py --online                         # count PS3_NET_ONLINE handlers too
  tools/hle_coverage.py --hits 01.09=<milestone> --doc docs/hle-coverage.md   # refresh the doc

The first --set is the primary version (full table); later sets only add a column.
HLE_TABLE may be `regen`: the table gen_hle_nids.py --all would generate from the
current external/ps3recomp tree (to see a toolkit patch before the lift's table is
regenerated). --tree LABEL=DIR scans another ps3recomp checkout for that version
(e.g. the main checkout's, to show the state before a patch).
Defaults: 01.09 from <main checkout>/versions/0109 (if present) and 01.02 from this
checkout's analysis/ and src/recomp/.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# NIDs the toolkit's database cannot name, named by computing SHA-1 NIDs of candidate
# SDK names (T004, 2026-10-18). Verified at start-up; a wrong entry aborts the tool.
KNOWN_NAMES = {
    # cellSysutil (01.02; 01.09 imports these through the cellGame library instead)
    0xA9B0C1D9: "cellGameDataGetSizeKB",
    0x9949BF82: "cellGameDataExitBroken",
    # sys_net
    0x3F09E20A: "socketselect",
    0xF7AC8941: "gethostbyaddr",
    # cellMic (01.02)
    0x05709BBF: "cellMicOpenEx",
    0x65336418: "cellMicRemoveNotifyEventQueue",
    0x6BC46AAB: "cellMicReset",
    0x7903400E: "cellMicSetNotifyEventQueue",
    0xB2C16321: "cellMicSetDeviceAttr",
    # cellVoice (01.09)
    0x2A01013E: "cellVoiceCreateNotifyEventQueue",
    0x35D84910: "cellVoiceSetNotifyEventQueue",
    0x94D51F92: "cellVoiceStartEx",
    0xB1A2C38F: "cellVoiceInitEx",
    # sceNp
    0x7DEB244C: "sceNpScoreCensorComment",
    0x7E2FEF28: "sceNpManagerRequestTicket",
    0x166DCC11: "sceNpLookupNpId",
    0x32C78A6A: "sceNpBasicGetFriendPresenceByIndex",
    0xBE81C71C: "sceNpBasicSetPresenceDetails",
    # cellVideoExportUtility / cellVideoUpload
    0x2F457571: "cellVideoExportInitialize2",
    0x81296524: "cellVideoExportFromFile",
    0xC15BE817: "cellVideoExportFinalize",
    0x122E0D0F: "cellVideoUploadInitialize",
    # cellMusicUtility
    0x8793EF97: "cellMusicGetSelectionContext2",
    0xAD04CDDD: "cellMusicSelectContents2",
    0x0B461648: "cellMusicGetSelectionContext",
    0x5BFF31BF: "cellMusicSetSelectionContext",
    0x72EC14B5: "cellMusicInitialize",
    0xA0661626: "cellMusicSetPlaybackCommand",
    0xE74CE7BD: "cellMusicSetVolume",
}

LOG_CALL = re.compile(
    r"^\s*(?:printf|fprintf|puts|fputs|fflush|snprintf|LOG\w*|\w*_LOG\w*|\w*_log\w*|"
    r"\w*TRACE\w*|\w*_trace\w*|ps3_msf?|DBG\w*|WARN\w*)\s*\(")


def main_checkout():
    """The main checkout (worktrees share its git common dir)."""
    try:
        common = subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=True).stdout.strip()
        return os.path.dirname(common)
    except (OSError, subprocess.CalledProcessError):
        return ROOT


def strip_c(text):
    """Remove comments and the contents of string/char literals."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    text = re.sub(r"'(?:\\.|[^'\\])'", "''", text)
    return text


def body_at(text, brace):
    """Return the text between the brace at index `brace` and its match."""
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1:i]
    return text[brace + 1:]


def classify(body):
    """(class, effective statement count, constant return or None) for a C body.

    stub  -- nothing but logging, (void) casts, guards and `return <expr>;`
    thin  -- 1-3 other statements (usually writes one out-param or a flag)
    impl  -- more than that
    """
    b = strip_c(body)
    stmts = [s.strip() for s in re.split(r"[;{}]", b) if s.strip()]
    eff = 0
    last_ret = None
    for s in stmts:
        s1 = re.sub(r"^(?:if|else if|while)\s*\(.*?\)\s*", "", s, flags=re.S).strip()
        s1 = re.sub(r"^else\s*", "", s1)
        if not s1:
            continue
        if re.match(r"^return\b", s1):
            last_ret = re.sub(r"\s+", " ", s1[6:].strip())
            continue
        # ctx handlers return through r3: `ctx->gpr[3] = <constant>` (no call, no load)
        m = re.match(r"^ctx->gpr\[3\]\s*=\s*([^()]*?|\(\w+\)\s*-?\w+)$", s1)
        if m and "ctx->" not in m.group(1):
            last_ret = re.sub(r"\s+", " ", m.group(1))
            continue
        m = re.match(r"^RET_[SU]\(\s*(-?\w+)\s*\)$", s1)
        if m:
            last_ret = m.group(1)
            continue
        if LOG_CALL.match(s1) or re.match(r"^\(void\)\s*\w+$", s1):
            continue
        if re.match(r"^static\s+(?:int|unsigned|bool|u32|s32)\s+\w+\s*(?:=\s*\w+)?$", s1):
            continue  # one-shot log counters
        if re.match(r"^\w+\+\+$", s1):
            continue
        eff += 1
    if eff == 0:
        return "stub", 0, last_ret
    return ("thin" if eff <= 3 else "impl"), eff, last_ret


class Registry:
    def __init__(self, ps3recomp, src_dir, hle_table, online):
        self.ps3recomp = ps3recomp
        self.entries = OrderedDict()   # nid -> dict(path, name, handler, file)
        self.defs = {}                 # function name -> (file, body)
        sys.path.insert(0, os.path.join(ps3recomp, "tools"))
        from nid_database import compute_nid  # noqa: E402
        self.compute_nid = compute_nid
        self._index_defs()
        self._scan_ctx(src_dir, online)
        self._load_table(hle_table)

    def _index_defs(self):
        pat = re.compile(r"^(?:[A-Za-z_][\w \t\*]*?[\s\*])?(\w+)\s*\(([^;{}]*?)\)\s*\{", re.M)
        files = []
        for sub in ("libs", "runtime"):
            for ext in ("c", "cpp"):
                files += glob.glob(os.path.join(self.ps3recomp, sub, "**", "*." + ext),
                                   recursive=True)
        files += glob.glob(os.path.join(ROOT, "src", "*.cpp"))
        files += glob.glob(os.path.join(ROOT, "src", "overrides", "*.cpp"))
        for f in sorted(files):
            if "/tests/" in f:
                continue
            txt = open(f, encoding="latin1").read()
            for m in pat.finditer(txt):
                name = m.group(1)
                if name in ("if", "for", "while", "switch", "return", "sizeof"):
                    continue
                self.defs.setdefault(name, []).append((f, body_at(txt, m.end() - 1)))

    def find_def(self, fn, prefer_file=None):
        """(file, body) of fn: the registering file first, then libs/, then anything."""
        cands = self.defs.get(fn, [])
        for want in (prefer_file, os.path.join(self.ps3recomp, "libs")):
            for f, b in cands:
                if want and f.startswith(want):
                    return f, b
        return cands[0] if cands else None

    def classify_fn(self, fn, prefer_file=None, depth=0):
        """classify() with one level of delegation: `return other(...)` is graded by `other`."""
        d = self.find_def(fn, prefer_file)
        if not d:
            return "?", 0, None, prefer_file or ""
        cls, eff, ret = classify(d[1])
        if cls == "stub" and ret and depth < 2:
            call = re.match(r"^(?:\([^()]*\)\s*)?(\w+)\s*\(", ret)
            if call and call.group(1) not in ("sizeof",) and call.group(1) != fn:
                if call.group(1) in self.defs:
                    c2, e2, r2, _ = self.classify_fn(call.group(1), d[0], depth + 1)
                    return (c2 if c2 != "stub" else "stub"), e2, (r2 if c2 == "stub" else None), d[0]
                return "thin", 1, None, d[0]   # returns a call into something we cannot see
        return cls, eff, ret, d[0]

    def _add(self, nid, path, name, handler, f):
        if nid in self.entries:
            return  # first registration wins (ctx table) / ctx shadows generic
        self.entries[nid] = dict(path=path, name=name, handler=handler, file=f)

    def _scan_ctx(self, src_dir, online):
        files = []
        for sub in ("runtime", "libs"):
            for ext in ("c", "cpp"):
                files += glob.glob(os.path.join(self.ps3recomp, sub, "**", "*." + ext),
                                   recursive=True)
        files += glob.glob(os.path.join(src_dir, "*.cpp"))
        files += glob.glob(os.path.join(src_dir, "overrides", "*.cpp"))
        call = re.compile(r"ps3_hle_register_ctx\s*\(\s*([^,]+?)\s*,\s*\"([^\"]+)\"\s*,\s*(\w+)\s*\)",
                          re.S)
        online_tab = re.compile(r"\{\s*\"(\w+)\"\s*,\s*(h_\w+)\s*\}")
        # ppu_sysprx.cpp registers PS3_NET_ONLINE first (it wins when enabled).
        for f in sorted(files, key=lambda p: (not p.endswith("sysNet.c"), p)):
            if "/tests/" in f or "host_stubs" in f:
                continue
            txt = open(f, encoding="latin1").read()
            if f.endswith("sysNet.c"):
                if online:
                    m = re.search(r"ps3_net_host_register.*?tab\[\]\s*=\s*\{(.*?)\};", txt, re.S)
                    for name, fn in online_tab.findall(m.group(1) if m else ""):
                        self._add(self.compute_nid(name), "online", name, fn, f)
                continue
            for m in call.finditer(strip_comments_keep_strings(txt)):
                arg, name, fn = m.groups()
                lit = re.match(r"0x([0-9A-Fa-f]+)u?$", arg)
                nid = int(lit.group(1), 16) if lit else self.compute_nid(name)
                if not lit and "ps3_compute_nid" in arg:
                    inner = re.search(r"\"([^\"]+)\"", arg)
                    nid = self.compute_nid(inner.group(1) if inner else name)
                self._add(nid, "ctx", name, fn, f)

    def _load_table(self, path):
        if path == "regen":
            # What gen_hle_nids.py --all would emit from THIS ps3recomp tree (e.g. with
            # an unmerged patch applied) instead of the table the lift was built with.
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                out = os.path.join(td, "ppu_hle_nids.cpp")
                subprocess.run([sys.executable, os.path.join(self.ps3recomp, "tools",
                                                             "gen_hle_nids.py"),
                                "--all", "--out", out], check=True, capture_output=True)
                txt = open(out, encoding="latin1").read()
            path = "gen_hle_nids.py --all"
        else:
            txt = open(path, encoding="latin1").read()
        for m in re.finditer(r"ps3_hle_register(_ctx)?\(0x([0-9A-Fa-f]+)u,\s*\"([^\"]+)\",\s*"
                             r"(?:\(void\*\))?(\w+)\)", txt):
            ctx, nid, name, fn = m.groups()
            self._add(int(nid, 16), "ctx" if ctx else "generic", name, fn, path)

    def describe(self, nid):
        e = self.entries.get(nid)
        if not e:
            return dict(path="missing", handler="", cls="missing", eff=0, ret=None, file="")
        prefer = e["file"] if e["path"] in ("ctx", "online") else None
        cls, eff, ret, f = self.classify_fn(e["handler"], prefer)
        f = f or e["file"]
        return dict(path=e["path"], handler=e["name"], fn=e["handler"], cls=cls, eff=eff,
                    ret=ret, file=os.path.relpath(f, self.ps3recomp)
                    if f.startswith(self.ps3recomp) else os.path.relpath(f, ROOT))


def strip_comments_keep_strings(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?<![:\"])//[^\n]*", " ", text)


def load_hits(path, registry):
    """nid -> hit description, from a milestone log or a run log."""
    by_name = {e["name"]: nid for nid, e in registry.entries.items()}
    hits = {}
    txt = open(path, encoding="latin1").read()
    if txt.startswith("# ps3recomp milestone log"):
        counts = {}
        for line in txt.splitlines():
            p = line.split("\t")
            if p[0] == "count" and len(p) == 3:
                counts[p[1]] = p[2]      # last block wins
        order = {}
        for line in txt.splitlines():
            p = line.split("\t")
            if len(p) == 2 and p[0].isdigit():
                order.setdefault(p[1], int(p[0]))
        for key in set(order) | set(counts):
            if key.startswith("hle:unresolved:0x"):
                nid = int(key[len("hle:unresolved:"):], 16)
            elif key.startswith("prx:0x"):
                nid = int(key[4:], 16)
            elif key.startswith("hle:"):
                nid = by_name.get(key[4:])
                if nid is None:
                    continue
            else:
                continue
            hits[nid] = dict(first=order.get(key), count=counts.get(key, "?"),
                             unresolved=key.startswith("hle:unresolved:"),
                             prx=key.startswith("prx:"))
    else:
        for m in re.finditer(r"\[HLETRACE\] nid=0x([0-9A-Fa-f]{8})", txt):
            h = hits.setdefault(int(m.group(1), 16), dict(first=None, count=0,
                                                          unresolved=False, prx=False))
            h["count"] += 1
        for m in re.finditer(r"unresolved NID 0x([0-9A-Fa-f]{8})", txt, re.I):
            h = hits.setdefault(int(m.group(1), 16), dict(first=None, count=0,
                                                          unresolved=True, prx=False))
            h["unresolved"] = True
            h["count"] = h["count"] or "seen"
    return hits


def import_name(e, registry):
    nid = int(e["nid"], 16)
    if e.get("name"):
        return e["name"], "db"
    if nid in KNOWN_NAMES:
        return KNOWN_NAMES[nid], "computed"
    return "", "unknown"


def check_names(compute_nid):
    bad = [(n, nm) for n, nm in KNOWN_NAMES.items() if compute_nid(nm) != n]
    for n, nm in bad:
        print(f"KNOWN_NAMES mismatch: 0x{n:08X} != compute_nid({nm!r}) = "
              f"0x{compute_nid(nm):08X}", file=sys.stderr)
    return not bad


def hit_str(h):
    if not h:
        return ""
    if h["unresolved"]:
        return f"UNRESOLVED ({h['count']})"
    if h["prx"]:
        return f"via PRX ({h['count']})"
    return str(h["count"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n", 1)[1])
    ap.add_argument("--set", nargs=3, action="append", metavar=("LABEL", "IMPORTS", "HLE_TABLE"),
                    help="a version: label, imports_named.json, ppu_hle_nids.cpp (repeatable; "
                         "first = primary)")
    ap.add_argument("--hits", action="append", default=[], metavar="LABEL=FILE",
                    help="milestone log (PS3_MILESTONE_OUT) or run log for a version")
    ap.add_argument("--ps3recomp", default=os.path.join(ROOT, "external", "ps3recomp"))
    ap.add_argument("--tree", action="append", default=[], metavar="LABEL=DIR",
                    help="ps3recomp checkout to scan for this version (default --ps3recomp)")
    ap.add_argument("--src", default=os.path.join(ROOT, "src"))
    ap.add_argument("--online", action="store_true",
                    help="count handlers that exist only with PS3_NET_ONLINE set")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("--out", help="write here instead of stdout")
    ap.add_argument("--doc", help="rewrite the generated block of this markdown file "
                                  "(e.g. docs/hle-coverage.md) in place")
    ap.add_argument("--check-names", action="store_true", help="only verify KNOWN_NAMES")
    args = ap.parse_args()

    sys.path.insert(0, os.path.join(args.ps3recomp, "tools"))
    from nid_database import compute_nid
    if not check_names(compute_nid):
        sys.exit(1)
    if args.check_names:
        print(f"KNOWN_NAMES: all {len(KNOWN_NAMES)} entries match compute_nid()")
        return

    sets = args.set
    if not sets:
        sets = []
        v9 = os.path.join(main_checkout(), "versions", "0109")
        if os.path.exists(os.path.join(v9, "analysis", "imports_named.json")):
            sets.append(["01.09", os.path.join(v9, "analysis", "imports_named.json"),
                         os.path.join(v9, "src", "recomp", "ppu_hle_nids.cpp")])
        sets.append(["01.02", os.path.join(ROOT, "analysis", "imports_named.json"),
                     os.path.join(ROOT, "src", "recomp", "ppu_hle_nids.cpp")])
    hits_by_label = {}
    for h in args.hits:
        label, _, path = h.partition("=")
        hits_by_label.setdefault(label, []).append(path)

    trees = dict(t.split("=", 1) for t in args.tree)
    versions = []
    for label, imports, table in sets:
        reg = Registry(os.path.abspath(trees.get(label, args.ps3recomp)), args.src, table,
                       args.online)
        imps = json.load(open(imports))
        hits = {}
        for p in hits_by_label.get(label, []):
            for nid, h in load_hits(p, reg).items():
                hits.setdefault(nid, h)
        rows = []
        for e in imps:
            nid = int(e["nid"], 16)
            name, src = import_name(e, reg)
            d = reg.describe(nid)
            rows.append(dict(lib=e["lib"], nid=nid, name=name, name_src=src,
                             hit=hits.get(nid), **d))
        versions.append(dict(label=label, rows=rows, hits=bool(hits_by_label.get(label))))

    if args.doc:
        import io
        buf = io.StringIO()
        emit_md(versions, buf)
        txt = open(args.doc).read()
        a, b = "<!-- BEGIN GENERATED: tools/hle_coverage.py -->", "<!-- END GENERATED -->"
        if a not in txt or b not in txt:
            sys.exit(f"{args.doc}: markers {a!r} / {b!r} not found")
        head, rest = txt.split(a, 1)
        _, tail = rest.split(b, 1)
        open(args.doc, "w").write(head + a + "\n" + buf.getvalue() + b + tail)
        print(f"updated {args.doc}")
        return
    out = open(args.out, "w") if args.out else sys.stdout
    if args.format == "json":
        json.dump([dict(label=v["label"], rows=[dict(r, nid=f"0x{r['nid']:08X}")
                                                for r in v["rows"]]) for v in versions],
                  out, indent=1)
        out.write("\n")
        return
    emit_md(versions, out)


def emit_md(versions, out):
    w = out.write
    w("| Version | Imports | Libraries | ctx | generic | missing | of which stub | thin | impl "
      "| unnamed by DB | hit at boot | hit & unresolved |\n")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    for v in versions:
        rows = v["rows"]
        c = Counter(r["path"] for r in rows)
        k = Counter(r["cls"] for r in rows if r["path"] != "missing")
        hit = sum(1 for r in rows if r["hit"])
        hun = sum(1 for r in rows if r["hit"] and r["hit"]["unresolved"])
        w(f"| {v['label']} | {len(rows)} | {len({r['lib'] for r in rows})} | {c['ctx']} | "
          f"{c['generic']} | {c['missing']} | {k['stub']} | {k['thin']} | {k['impl']} | "
          f"{sum(1 for r in rows if r['name_src'] != 'db')} | "
          f"{hit if v['hits'] else 'n/a'} | {hun if v['hits'] else 'n/a'} |\n")
    w("\n")

    prim = versions[0]
    others = versions[1:]
    w(f"### Per library ({prim['label']})\n\n")
    w("| Library | Imports | ctx | generic | missing | stub | thin | impl | hit |\n")
    w("|---|---|---|---|---|---|---|---|---|\n")
    libs = OrderedDict()
    for r in prim["rows"]:
        libs.setdefault(r["lib"], []).append(r)
    for lib, rs in sorted(libs.items(), key=lambda kv: -len(kv[1])):
        c = Counter(r["path"] for r in rs)
        k = Counter(r["cls"] for r in rs if r["path"] != "missing")
        w(f"| {lib} | {len(rs)} | {c['ctx']} | {c['generic']} | {c['missing']} | {k['stub']} | "
          f"{k['thin']} | {k['impl']} | {sum(1 for r in rs if r['hit'])} |\n")
    w("\n")

    other_idx = [{r["nid"]: r for r in o["rows"]} for o in others]
    w(f"### Full table ({prim['label']})\n\n")
    hdr = "| Library | NID | Name | Handler | Kind | Class | Return | Defined in | Hit |"
    sep = "|---|---|---|---|---|---|---|---|---|"
    for o in others:
        hdr += f" {o['label']} |"
        sep += "---|"
    w(hdr + "\n" + sep + "\n")
    for lib, rs in libs.items():
        for r in sorted(rs, key=lambda r: r["name"] or "~"):
            name = r["name"] or "?"
            if r["name_src"] == "computed":
                name += " ¹"
            handler = r["handler"] if r["handler"] and r["handler"] != r["name"] else (
                "=" if r["handler"] else "")
            ret = (r["ret"] or "") if r["cls"] == "stub" else ""
            ret = ret.replace("|", "\\|")
            row = (f"| {lib} | `{r['nid']:08X}` | {name} | {handler} | {r['path']} | "
                   f"{r['cls']}{'' if r['cls'] in ('missing', 'stub', '?') else ' ' + str(r['eff'])} | "
                   f"{('`' + ret + '`') if ret else ''} | {r['file']} | {hit_str(r['hit'])} |")
            for o, idx in zip(others, other_idx):
                orow = idx.get(r["nid"])
                if not orow:
                    row += " not imported |"
                else:
                    row += f" {orow['path']}{(' / ' + hit_str(orow['hit'])) if orow['hit'] else ''} |"
            w(row + "\n")
    w("\n")
    for o, idx in zip(others, other_idx):
        prim_nids = {r["nid"] for r in prim["rows"]}
        only = [r for r in o["rows"] if r["nid"] not in prim_nids]
        if not only:
            continue
        w(f"### Imported by {o['label']} only ({len(only)})\n\n")
        w("| Library | NID | Name | Kind | Class | Hit |\n|---|---|---|---|---|---|\n")
        for r in sorted(only, key=lambda r: (r["lib"], r["name"])):
            name = (r["name"] or "?") + (" ¹" if r["name_src"] == "computed" else "")
            w(f"| {r['lib']} | `{r['nid']:08X}` | {name} | {r['path']} | {r['cls']} | "
              f"{hit_str(r['hit'])} |\n")
        w("\n")
    w("¹ named by T004: NID computed from the name and matched, not in the toolkit "
      "database. `=` in Handler: registered under the import's own name.\n")


if __name__ == "__main__":
    main()
