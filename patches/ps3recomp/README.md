# Patches against ps3recomp

`external/ps3recomp` is pinned to upstream [sp00nznet/ps3recomp](https://github.com/sp00nznet/ps3recomp).
Everything we change in it lives here as a patch, so the submodule pointer always names
a real upstream commit and a bump is a rebase of this folder.

## The "middle path"

Upstream is the base. Features from the Drakengard 3 fork
([soyjxck/ps3recomp](https://github.com/soyjxck/ps3recomp), MIT) are ported over one at a
time, **only when this title needs them**, as separate patches. Candidates, roughly in the
order we expect to need them (details in `docs/reference-ports.md`):

1. Vulkan draw engine (`libs/video/rsx_vulkan_engine.c`) — upstream has only the backend.
2. SPURS Queue / LFQueue paths lifted from libsre (dod3's `tools/gen_libsre.py`).
3. Lifter `--hook <addr>` (native replacements) and `--nonvolatile-locals` (performance).
4. Guest memory page-table fast path, user-mode `sys_lwmutex`, `sys_lwcond` wakeups.

## Conventions

- One change per patch, named `NNNN-short-description.patch` (`git format-patch` output),
  applied in order with `git -C external/ps3recomp am ../../patches/ps3recomp/*.patch`.
- Each patch's commit message says why we need it and where it came from (upstream PR,
  dod3 fork commit, or our own). Keep the original author on ported commits.
- Generic fixes are also opened as upstream PRs; drop the patch once it lands.
- On a pin bump: `git -C external/ps3recomp checkout <new>`, re-apply, fix conflicts,
  re-export, relift, rebuild, and record the result in `docs/status.md`.

No patches yet (2026-10-18).
