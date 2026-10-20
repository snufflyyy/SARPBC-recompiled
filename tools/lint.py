#!/usr/bin/env python3
"""Keep the repo clean and uniform: the checks behind the T039 audit, in one command.

Fast (a few seconds, no build, no game data needed) and stdlib only. Run it before you
commit; tools/merge_to_main.sh runs it before it merges.

  tools/lint.py            # all fast checks; exit 1 if anything is wrong
  tools/lint.py --tests    # also run tools/test_*.py and ps3recomp's tools/test_*.py
  tools/lint.py --only docs,patches   # a subset (names below)

Checks:
  data     no game data or generated code is tracked (AGENTS.md rule 1): no ELF/SELF/PKG/
           RAP/EDAT/... names, nothing under src/recomp, src/spu_gen, vfs/, game/, analysis/,
           captures/, and no tracked file over 1 MB
  docs     every docs/*.md is in AGENTS.md's index; every repo path a doc names in `code`
           or a link exists (tools/, docs/, patches/, src/, root files, and ps3recomp's
           runtime/ libs/ include/ tests/); every patches/ps3recomp/*.patch, and every
           `T###-name` patch or task, a doc names exists (merged patches become NNNN-).
           Skipped: docs/status.md's "## Log" (history), the task logs, and paths in the two
           docs about other repos (dod3-reuse.md, reference-ports.md)
  patches  patches/ps3recomp/ holds NNNN-*.patch numbered 0001.. without gaps, plus T###-*
           ones only on a task branch; the README table has one row per file, in order
  board    every docs/tasks/*/T###-*.md has Status (matching its folder), Owner, Priority
           (open/claimed: a number or `blocked`), Touches, Reads, ## Goal, ## Done when,
           ## Log; ids are unique
  scripts  build.sh, run.sh, tools/*.sh, tools/*.py: a shebang, a header comment or
           docstring, the executable bit in git; `shellcheck -S warning` and pyflakes clean
           (each skipped, with a note, when the tool is not installed)
"""
import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / "external" / "ps3recomp"
problems = []
notes = []


def problem(where, msg):
    problems.append(f"{where}: {msg}")


def git(*args, cwd=ROOT):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout


def tracked():
    return [l for l in git("ls-files").splitlines() if l]


# --- data -----------------------------------------------------------------------------
GAME_NAMES = re.compile(r"\.(elf|self|sprx|prx|pkg|rap|edat|sdat|bin|xxx|upk|tfc)$|(^|/)EBOOT", re.I)
GAME_DIRS = ("src/recomp/", "src/spu_gen/", "vfs/", "game/", "analysis/", "captures/",
             "gamedata/", "versions/", "updates/", "spu_dump/")


def check_data():
    for f in tracked():
        if GAME_NAMES.search(f) or f.startswith(GAME_DIRS):
            problem(f, "looks like game data or generated code; it must not be tracked (AGENTS.md rule 1)")
        p = ROOT / f
        if p.is_file() and p.stat().st_size > 1_000_000:
            problem(f, f"tracked file is {p.stat().st_size // 1024} KB (over 1 MB): game data or output?")


# --- docs -----------------------------------------------------------------------------
ROOT_FILES = {"build.sh", "run.sh", "CMakeLists.txt", "config.toml", "AGENTS.md", "CLAUDE.md",
              "GEMINI.md", ".gitignore", ".gitmodules"}
REPO_PREFIXES = ("tools/", "docs/", "patches/", "src/")
SUB_PREFIXES = ("runtime/", "libs/", "include/", "tests/", "external/ps3recomp/")
OTHER_REPO_DOCS = {"dod3-reuse.md", "reference-ports.md"}
TOKEN = re.compile(r"`([^`\s]+)`|\]\(([^)\s#]+)")


def doc_lines(path):
    """(line number, text) of a doc, without status.md's history."""
    in_log = False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if path.name == "status.md" and line.startswith("## Log"):
            in_log = True
        if not in_log:
            yield n, line


def ref_exists(tok, doc):
    if tok.startswith("external/ps3recomp/"):
        return (ROOT / tok).exists()
    if tok.startswith(SUB_PREFIXES):
        return (SUB / tok).exists()
    # Docs name ps3recomp's own tools and docs by their path inside the submodule.
    return ((ROOT / tok).exists() or (doc.parent / tok).exists()
            or (tok.startswith(("tools/", "docs/")) and (SUB / tok).exists()))


def check_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for d in sorted((ROOT / "docs").glob("*.md")):
        if f"(docs/{d.name})" not in agents:
            problem("AGENTS.md", f"the docs index has no row for docs/{d.name}")
    docs = [ROOT / "AGENTS.md", *sorted((ROOT / "docs").glob("*.md")),
            *sorted((ROOT / "patches").glob("*/README.md"))]
    for doc in docs:
        rel = doc.relative_to(ROOT)
        for n, line in doc_lines(doc):
            for m in TOKEN.finditer(line):
                tok = (m.group(1) or m.group(2)).rstrip(".,:;)")
                tok = re.sub(r":\d+(-\d+)?$", "", tok)          # file.c:123
                if tok.startswith("./"):
                    tok = tok[2:]
                if not tok or re.search(r"[*<>{}$|~]|NNNN|T###|\.\.\.", tok) or tok.startswith(("http", "/", "-")):
                    continue
                link = m.group(2) is not None
                tm = re.fullmatch(r"(T\d{3}-[\w-]+)(\.patch)?", tok)
                if tm and not link:
                    name = tm.group(1)
                    if not ((ROOT / "patches" / "ps3recomp" / (name + ".patch")).exists()
                            or list((ROOT / "docs" / "tasks").glob(f"*/{name}*.md"))):
                        problem(f"{rel}:{n}", f"names `{tok}`: no such patch or task (renumbered to NNNN-?)")
                    continue
                if tok.startswith("patches/ps3recomp/") and tok.endswith(".patch"):
                    if not (ROOT / tok).exists():
                        problem(f"{rel}:{n}", f"names {tok}, which does not exist (renumbered?)")
                    continue
                if doc.name in OTHER_REPO_DOCS and tok.startswith(("tools/", "src/", "docs/", "include/", "runtime/")):
                    continue
                if not (link or tok in ROOT_FILES or tok.startswith(REPO_PREFIXES + SUB_PREFIXES)):
                    continue
                if link and not tok.endswith(".md"):
                    continue
                if not ref_exists(tok, doc):
                    problem(f"{rel}:{n}", f"names `{tok}`, which does not exist")


# --- patches --------------------------------------------------------------------------
def check_patches():
    pdir = ROOT / "patches" / "ps3recomp"
    files = sorted(p.name for p in pdir.glob("*.patch"))
    numbered = [f for f in files if re.match(r"^\d{4}-", f)]
    task = [f for f in files if re.match(r"^T\d{3}-", f)]
    for f in files:
        if f not in numbered and f not in task:
            problem(f"patches/ps3recomp/{f}", "name is neither NNNN-*.patch nor T###-*.patch")
    for i, f in enumerate(numbered, 1):
        if int(f[:4]) != i:
            problem(f"patches/ps3recomp/{f}", f"expected number {i:04d} (gap or duplicate)")
            break
    branch = git("branch", "--show-current").strip()
    if task and branch == "main":
        problem("patches/ps3recomp", f"T###- patches on main (merge_to_main.sh renumbers them): {', '.join(task)}")
    readme = (pdir / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([^`]+\.patch)` \|", readme, re.M)
    for f in files:
        if rows.count(f) != 1:
            problem("patches/ps3recomp/README.md", f"{rows.count(f)} table rows for {f} (want 1)")
    for r in rows:
        if r not in files:
            problem("patches/ps3recomp/README.md", f"table row for {r}, which does not exist")
    ordered = [r for r in rows if r in files]
    if ordered != sorted(ordered):
        problem("patches/ps3recomp/README.md", "table rows are not in apply (file name) order")


# --- board ----------------------------------------------------------------------------
def check_board():
    seen = {}
    for f in sorted((ROOT / "docs" / "tasks").glob("*/T[0-9][0-9][0-9]-*.md")):
        rel = f.relative_to(ROOT)
        text = f.read_text(encoding="utf-8")
        tid = f.name[:4]
        if tid in seen:
            problem(rel, f"id {tid} is also used by {seen[tid]}")
        seen[tid] = rel
        if not text.startswith(f"# {tid}:"):
            problem(rel, f"first line should be '# {tid}: <title>'")
        fields = dict(re.findall(r"^(Status|Owner|Priority|Touches|Reads): *(.*)$", text, re.M))
        for k in ("Status", "Owner", "Touches", "Reads"):
            if k not in fields:
                problem(rel, f"no '{k}:' line")
        folder = f.parent.name
        if fields.get("Status", folder) != folder:
            problem(rel, f"Status: {fields.get('Status')} but the file is in {folder}/")
        if folder != "done" and not re.fullmatch(r"\d+|blocked", fields.get("Priority", "")):
            problem(rel, "Priority: must be a number or 'blocked'")
        for h in ("## Goal", "## Done when", "## Log"):
            if not re.search("^" + h + r"\b", text, re.M):
                problem(rel, f"no '{h}' section")


# --- scripts --------------------------------------------------------------------------
def check_scripts():
    modes = {}
    for line in git("ls-files", "-s").splitlines():
        meta, path = line.split("\t", 1)
        modes[path] = meta.split()[0]
    scripts = ["build.sh", "run.sh"] + sorted(
        str(p.relative_to(ROOT)) for p in (ROOT / "tools").glob("*") if p.suffix in (".sh", ".py"))
    for s in scripts:
        head = (ROOT / s).read_text(encoding="utf-8").splitlines()[:3]
        if not head or not head[0].startswith("#!"):
            problem(s, "no shebang line")
        elif not (len(head) > 1 and head[1].startswith(("#", '"""'))):
            problem(s, "no header comment or docstring right after the shebang (what it does, usage)")
        if s in modes and modes[s] != "100755":
            problem(s, "not executable in git (git update-index --chmod=+x)")
    sh = [s for s in scripts if s.endswith(".sh")]
    py = [s for s in scripts if s.endswith(".py")]
    if shutil.which("shellcheck"):
        r = subprocess.run(["shellcheck", "-S", "warning", "-f", "gcc", *sh], cwd=ROOT,
                           capture_output=True, text=True)
        for l in r.stdout.splitlines():
            problem("shellcheck", l)
    else:
        notes.append("shellcheck not installed: shell checks skipped")
    flakes = shutil.which("pyflakes3") or shutil.which("pyflakes")
    if flakes:
        r = subprocess.run([flakes, *py], cwd=ROOT, capture_output=True, text=True)
        for l in (r.stdout + r.stderr).splitlines():
            problem("pyflakes", l)
    else:
        notes.append("pyflakes not installed: Python checks skipped")


# --- tests ----------------------------------------------------------------------------
def run_tests():
    py = str(ROOT / ".venv" / "bin" / "python") if (ROOT / ".venv" / "bin" / "python").exists() else sys.executable
    tests = sorted((ROOT / "tools").glob("test_*.py")) + sorted((SUB / "tools").glob("test_*.py"))

    def one(t):
        r = subprocess.run([py, str(t)], cwd=t.parent.parent, capture_output=True, text=True, timeout=600)
        return t, r.returncode, (r.stdout + r.stderr)[-1500:]

    before = git("status", "--porcelain", cwd=SUB)
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        for t, rc, tail in ex.map(one, tests):
            if rc:
                problem(str(t.relative_to(ROOT)), f"test failed (exit {rc}):\n    " + tail.strip().replace("\n", "\n    "))
    # Some upstream tests regenerate files in their own tree (test_ppu_lift.py rewrites
    # scratch/ppu_conformance.cpp). Put back what this run changed; never commit it.
    changed = [l[3:] for l in git("status", "--porcelain", cwd=SUB).splitlines() if l not in before.splitlines()]
    if changed:
        git("checkout", "--", *changed, cwd=SUB)
        notes.append(f"restored files the tests rewrote in external/ps3recomp: {', '.join(changed)}")
    notes.append(f"ran {len(tests)} test scripts")


CHECKS = {"data": check_data, "docs": check_docs, "patches": check_patches,
          "board": check_board, "scripts": check_scripts}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tests", action="store_true", help="also run the test scripts (about a minute)")
    ap.add_argument("--only", help="comma-separated subset of: " + ", ".join(CHECKS))
    args = ap.parse_args()
    names = args.only.split(",") if args.only else list(CHECKS)
    for n in names:
        if n not in CHECKS:
            ap.error(f"unknown check {n}")
        CHECKS[n]()
    if args.tests:
        run_tests()
    for n in notes:
        print(f"lint: note: {n}")
    for p in problems:
        print(p)
    print(f"lint: {len(problems)} problem(s) in {', '.join(names)}{' + tests' if args.tests else ''}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
