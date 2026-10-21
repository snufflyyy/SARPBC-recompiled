# Building for Windows (not yet built, kept compile-clean) — T011

Linux is the primary platform. Windows (D3D12 backend, clang-cl) is a later target; this page says what
a Windows build needs and what has and has not been checked. **Nothing here has been compiled on
Windows or cross-compiled: this machine has no MSVC/Windows SDK headers and no mingw sysroot** (checked
2026-10-21: only Linux clang 19; `clang --target=x86_64-pc-windows-msvc` has no headers to compile
against, and installing a cross toolchain was not part of the task).

## What a Windows build needs

| Need | Notes |
|---|---|
| Visual Studio 2022 Build Tools or clang-cl, CMake, Ninja | `CMakeLists.txt` has `WIN32`/`MSVC` branches from ps3recomp's project template (`/bigobj` for the lifted files, `app.rc`, the Windows libs) |
| zlib | `find_package(ZLIB REQUIRED)` (edgezlib.cpp); vcpkg `zlib` |
| SDL2 | pad/audio on Windows use native backends upstream, SDL2 is only required off Windows |
| The lift | Generated on any host by `tools/relift.sh` (bash + Python): run it under WSL or on Linux, copy `src/recomp`, `src/spu_gen` |
| The game files | Same extraction as Linux (`tools/extract.sh`, `decrypt.sh` are bash scripts; the decrypt step needs RPCS3's AppImage, so do it on Linux) |

`build.sh`, `run.sh`, `tools/*.sh` are bash and Linux-specific (flock, /proc). A Windows build uses
`cmake -S . -B build -G Ninja` and `cmake --build build` directly.

## What the source tree does about it (audit 2026-10-21)

Every file in `src/` was read for POSIX-only calls outside `#ifdef`:

| File | POSIX use | Guard |
|---|---|---|
| `src/main.cpp` | `mmap` (VM arena), `setenv`, `realpath`, `clock_gettime` | `#ifndef _WIN32` include; the VM arena has a `VirtualAlloc` branch; `setenv`/`realpath` have `_WIN32` versions; `clock_gettime` comes from ps3recomp's `win32_compat.h` |
| `src/overrides/audio_mp3.cpp` | `readlink("/proc/self/exe")`, `mkdir`, `setenv`, `unistd.h` | each has a `_WIN32` branch (`GetModuleFileNameA`, `_mkdir`, `_putenv_s`) |
| `src/overrides/input_config.cpp` | `readlink`, `unistd.h`, `setenv` | `_WIN32` branches |
| `src/overrides/gcm_config.cpp` | `setenv` | `_WIN32` branch |
| `src/overrides/input_kbm.cpp` | `strcasecmp`, `strings.h` | only compiled with SDL2 on Linux (`__has_include`); the file is a no-op otherwise |
| `src/overrides/crash_report.cpp`, `clean_exit.cpp` | `sigaction`, `execinfo.h`, `pthread_sigmask`, `usleep` | whole file inside `#ifndef _WIN32` (Windows keeps its default crash dialog and Ctrl-C) |

Result: no Linux-only call outside an `#ifdef` was found. This is a reading audit, not a compile.

## What is verified versus untested

- **Verified (Linux):** the sources compile and run with clang 19 + Ninja + Vulkan.
- **Verified by reading:** the guards above.
- **Untested:** every `_WIN32` branch, the D3D12 backend with this title, MSVC/clang-cl codegen of the
  lifted code, the CMake Windows branches, long paths and the `\` separators in the VFS layer.
- **Next step when a Windows machine exists:** build with clang-cl, run `tools/test_*.py` source-only
  tests under Python on Windows (the Linux-only ones skip), then a boot check by hand.
