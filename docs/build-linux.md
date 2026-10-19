# Building on Linux

Host: Fedora (kernel 7.x), zsh. Available at the time of writing: `clang` (in
`~/.local/bin`), `gcc` via ccache, `cmake`, `ninja`, `python3`, `git`, `gh`. RPCS3 is
**not** installed (needed by the user for decryption only).

Linux is the primary platform and Vulkan the renderer. Windows (D3D12, clang-cl) is a
later target: the template's Windows paths are kept intact, so don't remove them.

Machine notes (2026-10-18): AMD Radeon RX 7700/7800 XT (Navi 32) with Mesa RADV
installed; 16 threads; 31 GB RAM; **only ~21 GB free on /home**. The lift and build
outputs are large, so check `df -h` before a clean build.

## Dependencies

One command for Fedora 44:

```bash
sudo dnf install SDL2-devel vulkan-headers glslang-devel   # SDL2-devel = sdl2-compat-devel
```

| Need | Fedora package / note |
|---|---|
| C17/C++20 compiler | clang ≥ 15 or GCC ≥ 12. Prefer clang: upstream CI and most ports use it, and the lifted code leans on `__int128`, `__builtin_bswap*`, `__atomic_*` |
| CMake ≥ 3.20, Ninja | `cmake`, `ninja-build` |
| Python ≥ 3.10 | plus `pip install -r $PS3RECOMP/requirements.txt` in a venv (pycryptodome etc.) |
| SDL2 | `SDL2-devel` — **required** off Windows: cellPad and cellAudio use SDL2 backends; Vulkan window uses it too |
| Vulkan headers | `vulkan-headers` (libvulkan is loaded at run time; only headers are needed to build) |
| Vulkan driver | Mesa (RADV/ANV) or NVIDIA; `vulkan-tools` for `vulkaninfo`; lavapipe works for headless tests |
| FFmpeg (optional) | `ffmpeg-libs` — loaded at run time by cellVdec / cellAtrac only; Bink does not use it |

## Configure / build

```bash
git submodule update --init external/ps3recomp
cmake -S . -B build -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build          # -> build/sarpbc
tools/run.sh                 # build/sarpbc game/EBOOT.elf vfs, window + guest shaders on
```

- Our `CMakeLists.txt` defaults to `Release` and turns `PS3RECOMP_RSX_VULKAN` on for
  Linux, and points at `external/ps3recomp`, `src/recomp`, `src/spu_gen`. A debug
  build of lifted code runs at roughly a third of the speed; use `RelWithDebInfo` for
  a debugger.
- It is the template's `CMakeLists.txt` (ps3recomp `templates/project` @ `838800e`) with
  those changes; diff against the template on a pin bump. It links `ps3recomp_runtime`,
  compiles the per-game PPU scaffold (`runtime/ppu/`), and globs `src/recomp/*.cpp` —
  reconfigure after every relift.
- `clang` here is `~/.local/bin/clang` (ROCm clang 20); `/usr/bin/gcc` is GCC 16.
- **ccache** is on by default (`SARPBC_CCACHE`): a repo-wide cache at
  `<main checkout>/.cache/ccache` (40 GB cap) shared by all worktrees, with
  `CCACHE_BASEDIR` set to each source tree. Turning it on, or changing compile flags,
  recompiles everything once.
- Numbers (2026-10-18, 16 threads): full build 8 min 38 s, binary 385 MB, build dir
  0.9 GB. The largest lifted TU (`ppu_recomp_077.cpp`, 43k lines) takes 27 s and 630 MB at
  `-O3`, so `-j16` is safe on 31 GB of RAM.
- **Template bug on Linux (fixed in our `main.cpp`):** the template allocates guest memory
  with `calloc(0xE0000000)`, which glibc places 16 bytes into its mmap, so `vm_base` is
  not page-aligned. Every `vm_commit` mprotect fails, `sys_memory_allocate` returns
  ENOMEM, and the game's allocator spins on NULL. Ours maps the guest space with `mmap` on
  a 4 GB boundary, which the runtime also requires (`GUEST_EA` truncation). Upstream's
  `boot_main.cpp` has the same code (upstream candidate).
- Lifted TUs are huge. Keep `--chunks` high enough that no single file takes minutes, and
  watch RAM with `-j$(nproc)`; lower parallelism if the linker or compiler OOMs.
- Verify the upstream runtime on its own first:
  `cmake -S external/ps3recomp -B build-rt -G Ninja -DPS3RECOMP_RSX_VULKAN=ON &&
  cmake --build build-rt --target ps3recomp_host && ./build-rt/ps3recomp_host --draw`.

## Graphics backend selection

`src/main.cpp` picks the backend **at build time**: Vulkan when `PS3RECOMP_RSX_VULKAN`
is defined (Linux), else D3D12 on Windows, Metal on Apple, the headless null backend
elsewhere. Without glslang the Vulkan backend still builds but stays fixed-function
(no guest shaders). Runtime switches (from upstream `BUILDING.md`):

| Variable | Effect |
|---|---|
| `PS3RECOMP_VK_WINDOW=1` | Show frames in an SDL2 window (otherwise headless) |
| `PS3RECOMP_VK_GUEST_PROGRAMS=1` | Run the game's own vertex/fragment programs; draw engine becomes default |
| `PS3RECOMP_VK_FULLSCREEN=1` / `PS3RECOMP_VK_HOLD=<s>` | Borderless full screen / hold last frame |
| `PS3RECOMP_VK_DEVICE=<n>` | Pick physical device n |
| `PS3RECOMP_VK_DUMP=<path>` + `PS3RECOMP_VK_DUMP_EVERY=<n>` | Write presented frames as PPM |
| `PS3RECOMP_RSX_ENGINE=dispatch\|vtable` | Choose draw path explicitly |

## Known Linux gaps (upstream, as of v0.15.0)

- No title had booted to gameplay from the upstream tree on Linux. **SARPBC boots on
  Linux/Vulkan to its loading screen and package loading** (2026-10-18), with the fixes
  listed in [status.md](status.md). The PPU boot scaffold
  (`ppu_loader.cpp`, `boot_main.cpp`, HLE dispatch) compiles on POSIX and the frame clock
  runs, but expect missing pieces. A CI ratchet (`tools/check_ppu_scaffold.py`) keeps it
  compiling.
- Twisted Metal reached menus on Linux/Vulkan downstream with patches still heading
  upstream — check that port and open upstream PRs before re-solving a Linux problem.
- Fibers use ucontext on POSIX; thread-local storage, `SIGPIPE`, and path separators are
  the usual POSIX trouble spots.
- Keep every Linux fix generic and file it as a patch in `patches/ps3recomp/` + an upstream PR.
