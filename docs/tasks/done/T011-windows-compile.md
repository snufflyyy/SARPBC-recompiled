# T011: Keep the port compile-clean for the future Windows (D3D12) build

Status: done
Owner: claude
Priority: 23
Touches: src/main.cpp (#ifdef _WIN32 regions only), CMakeLists.txt (WIN32 branches only), docs/build-windows.md (new)
Reads: external/ps3recomp/tools/check_ppu_scaffold.py, external/ps3recomp/docs/BUILDING.md

## Goal
Linux is primary, but Windows comes later on D3D12. Find out whether our sources (main.cpp,
src/overrides/*.cpp, CMake) compile for Windows without a Windows machine, e.g. with
clang-cl/--target=x86_64-pc-windows-msvc and a sysroot, or the approach upstream's
check_ppu_scaffold.py uses. Fix what is Linux-only behind #ifdef (POSIX realpath/setenv
are already shimmed; mmap is ifdef'd; check zlib, ccache launcher, flock-free paths).
Write docs/build-windows.md: what a Windows build needs (clang-cl, vcpkg zlib/SDL2, D3D12)
and what is verified versus untested.

## Done when
A documented compile check (or a precise reason one cannot run here) and no Linux-only
code outside #ifdef in our sources.

## Log
- 2026-10-21 02:01 claude: claimed
- 2026-10-21 02:01 claude: docs/build-windows.md: reading audit of src/ for POSIX use outside #ifdef (none found), needs list, verified/untested split. No compile possible here (no Windows SDK headers or mingw sysroot; not installing one unasked).
- 2026-10-21 02:01 claude: DONE: 
