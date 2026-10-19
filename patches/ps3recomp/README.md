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

## Current patches

| Patch | What | Upstream |
|---|---|---|
| `0001-trophy-deliver-RegisterContext-statuses-synchronousl.patch` | `sceNpTrophyRegisterContext` delivers PROCESSING_COMPLETE synchronously again (17047c9 deferred it, which races SARPBC's -1 "done" marker); test updated | to offer (it reverts a recent upstream choice, so explain the firmware ordering) |

Making a new one: commit inside `external/ps3recomp` on branch `sarpbc-patches`, then
`git -C external/ps3recomp format-patch -1 -o ../../patches/ps3recomp/ --start-number N`.
Agents working in parallel name theirs `T###-description.patch`; the coordinator
renumbers them on merge.

Upstream's unit tests assume macOS's `-dead_strip`. On Linux, build them with
`-ffunction-sections -fdata-sections -Wl,--gc-sections -Wl,-z,muldefs` and a no-op shim for
`cellMsgDialog_tick`, `np_psnr_pump`, `cellGame_get_title_id`, `vm_write32`, `vm_write8`.

## To upstream (handled port-side for now)

- **Linux guest VM in the template** (`templates/project/main.cpp`, `boot_main.cpp`):
  `calloc` → 4 GB-aligned `mmap`; see docs/build-linux.md.
- **`_cellSpursLFQueuePushBody`** has no HLE. Ours (`src/overrides/edgezlib.cpp`) is
  Edge-zlib specific; a general one needs libsre's push protocol.

- **Linker TOC-switch stubs** fold into the preceding function in `ppu_loader.py`, and
  the lifter turns each one into a wrapper running to the end of the run (3.6× source
  bloat on this EBOOT). Our workaround is `tools/split_toc_stubs.py`. The proper fix is in
  `ppu_loader.py` (or the lifter's boundary recovery): treat a run of
  `std r2,40(r1); addis/addi r2,r2; b` as one function per stub.
