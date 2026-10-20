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

Debian 13 (the container used since 2026-10-19 evening):

```bash
apt-get install gawk libsdl2-dev libvulkan-dev glslang-dev glslang-tools ccache gdb libopengl0
```

`gawk` because `tools/relift.sh` uses `strtonum` (Debian's default mawk lacks it), and
`libopengl0` because RPCS3's AppImage (`tools/decrypt.sh`) needs `libOpenGL.so.0`. In that
container perf is denied even at `perf_event_paranoid=2` (no permission for `task-clock`), so
`tools/spu_profile.sh` falls back to `/proc` sampling.

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

## Desktop launch (T041)

Use `./run.sh` on a normal X11 or Wayland desktop. It selects 01.09 and requests
an SDL2/Vulkan window by default (`PS3RECOMP_VK_WINDOW=1`), with guest shaders on.
The window title defaults to `SARPBC`. Keyboard configuration comes from the
checkout's `config.toml`, even when a desktop shortcut starts in another directory.
Caller-provided title, config, renderer, and path settings still take precedence.

```bash
./run.sh                                      # visible desktop game window
./run.sh --build                              # build, then open the window
PS3RECOMP_VK_WINDOW=0 ./run.sh                  # explicit headless operation
```

For a windowed Linux launch, the launcher rejects a known Vulkan-disabled CMake
build or `SDL_VIDEODRIVER=dummy` / `offscreen`. Its error gives the repair command.
Unset a headless SDL driver for desktop play. A working Vulkan presentation driver
and the desktop session environment are required; do not strip `DISPLAY` or
`WAYLAND_DISPLAY` when starting the game through SSH or `sudo`.

**Verified (2026-10-20):** the real `./run.sh`, executed outside the checkout under
Xvfb, opened a mapped 1280×720 `SARPBC` window on the RTX 2070 SUPER. SDL selected
X11 and Vulkan created a three-image swapchain. `xwininfo` confirmed `IsViewable`
again five seconds later; no headless fallback or presentation error appeared.
This checks an actual window, not just the scaffold's “window open” message.

**Native Wayland verified (T042, 2026-10-20, Fedora / RX 7800 XT):** patch
`0039-vk-wayland-surface-formats.patch` removes the 64-entry surface-format limit.
RADV exposes 99 format/colorspace pairs on this desktop. The old fill call returned
`VK_INCOMPLETE` (5), which the backend treated as fatal, then continued headless.
The scaffold still printed “window open”, so that line alone is not proof.

The backend now allocates the full list and retries up to four times if the list
changes during enumeration. UNORM preference and headless behavior are unchanged.
`SDL_VIDEODRIVER=wayland ./run.sh` created a native 1280×720, four-image swapchain
(format 44). A 45-second desktop test presented 3,581 guest frames with no headless
fallback or presentation errors. Wayland protocol logs confirm surface buffer
attachments and commits; the captured frame shows the Guest1 profile screen.
An X11 regression test also passed: 2,074 guest frames in 30 seconds, with no
headless fallback or presentation errors. Both tests stopped their own game at
the time limit. These are window/presentation tests, **not main-menu FPS benchmarks**.

```bash
./run.sh                                      # SDL chooses the desktop driver
SDL_VIDEODRIVER=wayland ./run.sh               # require native Wayland
SDL_VIDEODRIVER=x11 ./run.sh                   # X11/XWayland; older-build workaround
python3 external/ps3recomp/libs/video/tests/test_vulkan_surface_formats.py
```

The new GPU-independent regression fails on the old 64-entry implementation. It
covers large lists, format preference, changing counts, driver errors, allocation
failure and cleanup. GCC and Clang pass; Valgrind reports zero errors or leaks.
ASan/UBSan could not link because their runtime libraries are absent on this host.
Logs and captures: `analysis/pi-desktop/wayland-fixed.{log,ppm,png}`. The original
failure and X11 workaround logs are `game.log` and `game-x11.log` in that directory.

`python3 tools/test_run.py` tests the real launcher chain without game files or a
display: defaults, 01.02 selection, build option, caller overrides, paths/arguments
with spaces, exit status, and explicit headless use. Window tests do not establish
main-menu FPS; performance acceptance remains a separate benchmark.

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

## SRW locks prefer writers on glibc (T027)

ps3recomp's runtime is written against Win32 primitives, and `runtime/platform/win32_compat.h`
maps them onto pthreads on POSIX. An `SRWLOCK` becomes a lazily allocated `pthread_rwlock_t`.
The two do not schedule the same way:

- A **Windows SRW lock** lets a waiting writer in ahead of readers that arrive after it.
- **glibc's default rwlock prefers readers.** While read sections overlap, the lock never goes
  idle, and a writer waits for as long as readers keep coming.

**How it hit SARPBC (01.09, found by T022).** Every SPU channel access goes through `mfc_for`
(`runtime/spu/spu_channels.c`), which takes the shared side of `s_mfc_claim_lock` to find the
context's MFC engine. A context seen for the first time takes the exclusive side to register
itself. Dozens of PhysX SPU task threads spin on the shared side (`spu-spin pc=0x32B44 GETLLAR
ea=0x0133B880`). The ShaderPatching job (chain `0x012B6F00`) then blocked in
`pthread_rwlock_wrlock` for good. The FIFO park before `SET_SHADER_PROGRAM` was never released, and
the legal/ESRB screen stopped after 8-25 s.

**Fix:** patch `0027-win32-compat-srw-writer-preference.patch`. On glibc (`#ifdef __GLIBC__`),
`ps3__rwl_init` sets `PTHREAD_RWLOCK_PREFER_WRITER_NONRECURSIVE_NP`. Only the `NONRECURSIVE`
kind changes anything: glibc treats plain `PTHREAD_RWLOCK_PREFER_WRITER_NP` as reader preference.
Windows is unchanged. Other POSIX libcs have no setkind call and keep their default. As far as
we know musl also prefers readers, so a writer could still starve there. Darwin and the BSDs
have their own policies. Neither has been tested.

**The rule this imposes (it is SRW's own rule too):** code must not take the shared side twice
on one thread. It also must not wait, while holding the shared side, for another thread that
needs the same lock. With a writer queued in between, either one deadlocks. Every shared-side
user in the tree was checked on 2026-10-19 and is a leaf table lookup that takes no other lock
and waits for nothing:

| Site | Lock |
|---|---|
| `mfc_for`, runtime/spu/spu_channels.c | `s_mfc_claim_lock` |
| `spurs_port_queue`, libs/spurs/cellSpurs.c | `s_spurs_queue_lock` |
| `sq_spurs_of`, libs/spurs/cellSpursQueue.c | `s_sq_lock` |
| SPU `send_event` port lookup, runtime/syscalls/lv2_register.c | `s_spu_port_lock` |
| `SleepConditionVariableSRW(..., CONDITION_VARIABLE_LOCKMODE_SHARED)` | drops and re-takes once; only the shim's own test uses it |

The guest's `sys_rwlock_*` (runtime/syscalls/sys_rwlock.c) uses its own `pthread_rwlock_t` with
default attributes on POSIX, so this patch does not affect it. If a guest writer ever starves
behind spinning guest readers, look there next (it is still reader-preferring on glibc).
When you add a new `AcquireSRWLockShared` call, keep it a leaf.

**Test:** `test_srw_writer_progress` in `runtime/platform/tests/test_win32_compat.c` (built
as the upstream CI does: `cc -std=gnu17 -Wall -Wextra -I runtime/platform
runtime/platform/tests/test_win32_compat.c runtime/platform/win32_compat.c -lpthread`). Four
readers re-take the shared lock in overlapping 50 us sections while a writer needs it 20
times, with a 3 s deadline. Without the fix: `writer starved: 0/20 writes in 3001 ms`. With
it: `343 passed, 0 failed` (clang and gcc, glibc 2.43, also pinned to 1, 2 and 4 cores with
`taskset`). It asserts only on glibc and prints the result elsewhere.

**Boot evidence (01.09, 2026-10-19, main relifted, no `SPU_INTERP_UNLIFTED`).** Every run had
`GCM_INTR_THREAD=1 GCM_PARK_GRACE_MS=600000 GCM_PARK_LOG=1`. The large grace stands in for the
"never skip a park" GCM experiment: with the default 50 ms grace, one `FIFO resync (jump-park)`
dropped a fence, and the run stayed on "Loading..." whatever the lock did. Each run was 90 s,
under `tools/task.sh lock boot`, with `--gdb`. The control is the **same binary** with
`LD_PRELOAD` of a 1-line shim that turns `pthread_rwlockattr_setkind_np` into a no-op, which
gives the glibc default. That shim makes the unit test fail again, `0/20 writes`. The boot order
of the screens is legal/ESRB, then the Psyonix logo, then the Unreal logo, then the safe-area screen.

| Run | Lock | Screens reached (time of the frame dump) | gdb at 90 s, `s_mfc_claim_lock` |
|---|---|---|---|
| L1 | writer-pref | ESRB, then **Psyonix @33.8 s** | 1 writer and 55 readers queued (congested; jobs and parks still logged to 98 s) |
| L3 | writer-pref | ESRB @6.6 s, then **Unreal logo @39.7 s** | readers flowing, a writer just released |
| L2 | glibc default | ESRB @10.7 s, then nothing new until Psyonix fading in @86.3 s | a writer (`spu_mfc_release`) starved in `wrlock` |
| L4 | glibc default | **stuck on ESRB** from 6.6 s to the end | ShaderPatching job (`jc_thread` → `spu_prxjob_0caea65c...` → `spu_wrch` → `mfc_for`) starved in `wrlock` |

boot_check first lines: L1 `STALLED since 70.1s | last open TEXTURES.TFC@25.2s | ... dumps 15
lit 15 distinct 2 | flips 58`. L3 `STALLED since 75.9s | last open TEXTURES.TFC@5.6s | ... dumps
7 lit 7 distinct 3 | flips 103`. L2 `STALLED since 71.2s (frames still presented) | ... TEXTURES.TFC@9.7s
| ... flips 69`. L4 `STALLED since 68.1s | ... TEXTURES.TFC@5.6s | ... dumps 6 lit 6 distinct 2 |
flips 80`. ("STALLED" means no new kinds of log line. Parks were still being patched at the
end of every run.) An earlier unlocked run, with the same settings and the fix, reached the
**safe-area screen** ("Use the Left Stick to adjust the screen...") at 76.2 s.

**What this shows.** With writer preference, both runs left the ESRB screen within about 35 s.
With reader preference, one control sat on ESRB for the whole run with the job starved, and the
other needed 75 s. It is **not enough on its own.** Dozens of PhysX SPU task threads (image
`363824547`, spinning at `0x32B44` on `GETLLAR 0x0133B880`, see debugging.md) all go through
`mfc_for` on every channel access. L1 had 91 threads and L3 had 172. That many threads on one
rwlock congest it whatever the policy, so the frame rate falls after the logos. The real fixes:
(1) take the hot path of `mfc_for` off the lock, for example by caching the engine in
`spu_context` (runtime/spu, proposed as a follow-up task); (2) find why the PhysX tasks spin and
assert (T028).
