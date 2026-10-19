# Building on Linux

Host: Fedora (kernel 7.x), zsh. Available at the time of writing: `clang` (in
`~/.local/bin`), `gcc` via ccache, `cmake`, `ninja`, `python3`, `git`, `gh`. RPCS3 is
**not** installed (needed by the user for decryption only).

## Dependencies

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
git submodule update --init external/ps3recomp      # once the repo exists
cmake -S . -B build -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
      -DPS3RECOMP_DIR=$PWD/external/ps3recomp \
      -DPS3RECOMP_RSX_VULKAN=ON
cmake --build build
```

- Release by default: a debug build of lifted code runs at roughly a third of the speed
  (observed in sibling ports). Use `RelWithDebInfo` when you need a debugger.
- The project CMake is copied from `$PS3RECOMP/templates/project/CMakeLists.txt`. It
  links `ps3recomp_runtime`, compiles the per-game PPU scaffold (`runtime/ppu/`), and
  globs `src/recomp/*.cpp` — reconfigure after every relift.
- Lifted TUs are huge. Keep `--chunks` high enough that no single file takes minutes, and
  watch RAM with `-j$(nproc)`; lower parallelism if the linker or compiler OOMs.
- Verify the upstream runtime on its own first:
  `cmake -S external/ps3recomp -B build-rt -G Ninja -DPS3RECOMP_RSX_VULKAN=ON &&
  cmake --build build-rt --target ps3recomp_host && ./build-rt/ps3recomp_host --draw`.

## Graphics backend selection

The template's `main.cpp` picks the backend **at build time**: D3D12 on Windows, Metal on
Apple, the headless null backend elsewhere. On Linux we must switch `main.cpp` to the
Vulkan backend when `PS3RECOMP_RSX_VULKAN` is on (look at how `ps3recomp_host` does it).
Runtime switches (from upstream `BUILDING.md`):

| Variable | Effect |
|---|---|
| `PS3RECOMP_VK_WINDOW=1` | Show frames in an SDL2 window (otherwise headless) |
| `PS3RECOMP_VK_GUEST_PROGRAMS=1` | Run the game's own vertex/fragment programs; draw engine becomes default |
| `PS3RECOMP_VK_FULLSCREEN=1` / `PS3RECOMP_VK_HOLD=<s>` | Borderless full screen / hold last frame |
| `PS3RECOMP_VK_DEVICE=<n>` | Pick physical device n |
| `PS3RECOMP_VK_DUMP=<path>` + `PS3RECOMP_VK_DUMP_EVERY=<n>` | Write presented frames as PPM |
| `PS3RECOMP_RSX_ENGINE=dispatch\|vtable` | Choose draw path explicitly |

## Known Linux gaps (upstream, as of v0.15.0)

- No title has booted to gameplay from the upstream tree on Linux. The PPU boot scaffold
  (`ppu_loader.cpp`, `boot_main.cpp`, HLE dispatch) compiles on POSIX and the frame clock
  runs, but expect missing pieces. A CI ratchet (`tools/check_ppu_scaffold.py`) keeps it
  compiling.
- Twisted Metal reached menus on Linux/Vulkan downstream with patches still heading
  upstream — check that port and open upstream PRs before re-solving a Linux problem.
- Fibers use ucontext on POSIX; thread-local storage, `SIGPIPE`, and path separators are
  the usual POSIX trouble spots.
- Keep every Linux fix generic and file it as a patch in `patches/ps3recomp/` + an upstream PR.
