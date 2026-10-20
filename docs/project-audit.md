# Project maintainability audit — 2026-10-20 (T046)

## Purpose and verdict

Keep the recompilation simple to modify without losing the working 01.09 boot.
This is an evidence-backed review, not a claim that the whole runtime is safe.
Baseline: superproject `8252d70`, upstream `749182e`, 49 patch files / 67 commits.
The audit itself did not change implementation files; later T047 remediations are
recorded under A01/A02 below. T038's loading-screen orientation work is owned by
Antigravity and was not modified.

**Verdict: keep the architecture; strengthen its safety and verification boundaries.**
The port does not need a framework, plugin system, wholesale rewrite, or more layers.
Its main maintenance costs are patch provenance, implicit startup order, misleading
configuration, and incomplete test discovery. Fix those before cosmetic refactoring.

## Scope and checks

Reviewed the tracked-file inventory, recent churn, build/launch/lift/merge/task tools,
port-owned C++ sources, configuration, patch inventory and selected high-risk patch
changes (especially batching and callback ownership). Generated game code and assets
were excluded. This was not an exhaustive line-by-line audit of upstream ps3recomp,
a dependency vulnerability scan, or a new gameplay/performance qualification.

| Check | Observed result |
|---|---|
| Main checkout `tools/lint.py` | 0 problems |
| Apply all patches in the private pi worktree | 67 commits apply to the upstream pin |
| Private `tools/lint.py --tests`, under the CPU lock | All 85 discovered scripts exit zero; overall command fails on 10 documentation-path checks |
| Three additional nested test scripts, under the CPU lock | All pass: SDL pad (36 checks), Vulkan present/readback, Vulkan surface formats |
| Submodule after tests | Clean; runner restored the tracked conformance fixture |
| Tracked-data hygiene | Existing data check passes; this review did not repeat the historical Git-object scan |
| New build / game boot / Windows / Metal / sanitizers | Not run; no runtime code changed |

The 10 private-worktree lint errors concern absent local generated trees and RPCS3
paths. The main checkout has those paths. This exposes a clean-clone/worktree
portability issue, not ten broken source links. After adding read-only symlinks to
those existing main-checkout paths, private fast lint also reports 0 problems;
this local setup workaround does not fix the clean-clone defect. Test logs are retained locally in
the pi worktree's `analysis/audit-tests.log` and `analysis/audit-nested-tests.log`.
A zero exit from a script is not proof that it made assertions: skip reporting is
not preserved by the current runner.

## What to preserve

- **Clear ownership:** generated PPU/SPU output is ignored; title behavior lives in
  `src/overrides/`; shared runtime changes are exported patches against an upstream pin.
- **Small native surface:** most overrides solve one concrete compatibility problem.
  Guest addresses, ABI reasoning, provenance and escape hatches are documented.
- **Reuse with attribution:** the MP3 decoder carries the MIT notice; imported patch
  commits retain authorship. No need to replace working reuse with new dependencies.
- **Useful operating tools:** one-command build/run, PID-scoped boot checks, task
  scopes, worktrees and CPU/boot locks are already practical foundations.
- **Behavioral fixtures:** MP3 local-store bounds, SPURS arguments, callbacks, pad
  pressure and Vulkan enumeration have focused tests. Extend this style.

## Findings

Priority is cleanup order, not a remote-exploit severity score. The current application
runs local game files; no remote attack path was established by this audit.

### A01 — High: native zlib lacks a checked guest-memory boundary (fixed in T047)

**Remediation:** request/queue, actual input/output, optional counter and full 128-byte
flag spans are checked before access, against the 32-bit guest limit and a nonzero
`ppu_vm_size` when provided. Counter alignment and zero-count underflow are rejected.
Wide decoded-size arithmetic rejects overflow; prefix/suffix bytes go into fixed
scratch space rather than a request-sized vector. Success requires Z_STREAM_END and
an exact decoded length. Invalid requests and decode failures return a SPURS error
without decrementing the work counter or signalling successful completion. An event-
delivery error is propagated after successful work/counter completion; that decrement
is not rolled back or retried, which could race other requests.
This is the port's synchronous rejection policy, not a newly claimed firmware error
ABI: 01.09 caller `func_00B55024` checks the push result at `0x00B55168` and enters
its error path on nonzero. A failed inflate may have written partial output; callers
must not consume it. The checks bound address arithmetic, not allocation ownership
inside the deliberately flat guest mapping. Synthetic coverage: `tools/test_edgezlib.py`.

The original audit evidence and recommendation follow for traceability.

**Evidence:** `src/overrides/edgezlib.cpp:105-160` checks queue element size, then
reads the request and passes guest addresses/lengths directly to `memmove`, zlib,
`memcpy`, and an atomic counter operation. There are no full-span checks, counter
alignment checks, or checked addition for `skip_begin + out_size + skip_end`.
That sum is evaluated in 32-bit unsigned arithmetic before vector allocation.
The final HLE result is CELL_OK and completion is signalled even when inflate fails.
`inflate_exact` also accepts Z_OK/Z_BUF_ERROR if the expected output length appeared;
that is not equivalent to observing the end of a valid deflate stream.

**Impact:** malformed requests or an upstream guest bug can become host out-of-bounds
accesses, excessive allocation, or a success-shaped failure far from its cause.
The flat 4 GB guest mapping is not a substitute for validating an entire span.

**Small fix:** validate descriptor/input/output/counter spans with wide arithmetic;
check temporary-size overflow and counter alignment before access. Specify the
truncated-stream and failure-completion behavior from the guest ABI, rather than
blindly returning an error that might strand a waiter. Add synthetic copy/inflate,
truncation, overflow, boundary and completion tests. No general LFQueue framework.

### A02 — High: the POSIX VFS resolver gives realpath an undersized buffer (fixed in T047)

**Remediation:** platform-allocated resolution and owned strings replace every fixed
VFS path buffer in setup. Existing environment values retain precedence without
truncation; failed environment updates stop setup before metadata loading. Synthetic
coverage: `tools/test_vfs.py`; platform limits and upstream filesystem code still apply.

**T047 verification (Linux/Clang):** private 01.09 Release build; all 87 discovered
scripts return zero plus three explicit nested SDL/Vulkan runners; 16 zlib and five
VFS tests also pass with ASan/UBSan. A 120 s boot renders the tutorial arena with
3717 zlib requests, none rejected, 2463 flips and zero unresolved imports. Antigravity's
subsequent patch 0050 is integrated unchanged into the private build; the combined
stack passes the 87-script gate again and a 30 s smoke (3279 zlib requests, 717 flips,
unresolved 0). The private runtime tree matches main's patched tree. GCC is absent;
Windows was not tested. No new performance claim is made.

The original audit evidence and recommendation follow for traceability.

**Evidence:** `src/main.cpp:321-324` passes `char vfs[1024]` to POSIX `realpath`.
That API has no destination-length argument; valid resolved paths can exceed 1024
bytes. A local libc guard-page check with a 1239-byte existing path faulted. This
was a libc boundary check, not a game boot or proof of remote exploitation.

**Small fix:** use an allocated realpath result on POSIX and owned storage, or a
bounded platform path helper; check downstream path construction for truncation.
Add a long-path regression that does not require game data.

### A03 — High: the advertised test gate omits three relevant regression scripts

**Evidence:** `tools/lint.py:230-235` discovers only the two top-level tools folders.
It omits `libs/input/tests/test_cellpad_sdl.py`,
`libs/video/tests/test_vulkan_present_readback.py`, and
`libs/video/tests/test_vulkan_surface_formats.py` inside ps3recomp. These are the
specific regression runners for patches 0015, 0037/0038 and 0039. All three pass
when invoked explicitly, but the normal gate does not protect them.

**Small fix:** add an explicit test manifest covering these suites, and test the
manifest/discovery rule. Do not recursively run every Python file indiscriminately.
Report passed/failed/skipped scripts and retain individual output. Add an opt-in
strict mode that makes missing required compilers/checkers fail rather than skip.

### A04 — High: build provenance can silently diverge from the patch stack

**Resolved by T049 (2026-10-20):** `tools/apply_patches.sh [--ensure]` builds pin + patches in a scratch worktree and compares tree hashes (stamp: `<hash of pin+patches> <tree>`), refuses a dirty runtime before touching anything (`SARPBC_ALLOW_DIRTY_RUNTIME=1` is the explicit override), leaves the checkout alone when a patch fails, and keeps a replaced tip under `refs/sarpbc-backup/*`. `build.sh` runs under a per-checkout `build-<id>` lock. `tools/test_build.py` proves it with throwaway repositories.

**Evidence:** `build.sh:55-73` accepts an unstamped checkout if its branch, ancestry
and commit count match. Equal commit counts do not prove equal patch contents.
If the expected stack changes while the submodule is dirty, the script warns and
continues building the unexpected tree. `tools/apply_patches.sh:13-22` performs
`git submodule update` before checking dirty state; a refusal is therefore not a
reliable promise that the checkout was untouched. The CPU lock covers only the
final compilation, not patching/configuration/cleaning of the same build tree.

**Small fix:** fail closed on a dirty mismatched runtime; require an explicit
experimental override if needed. Verify a deterministic patched-tree identity,
not a commit count. Preflight before mutations, and serialize the whole build
transaction for a checkout. Test with throwaway source-only repositories.

### A05 — Medium: test cleanup can overwrite pre-existing source changes

**Evidence:** `tools/lint.py:239-248` snapshots porcelain status, runs tests in the
source tree, then restores newly changed paths with Git checkout. A previously
clean file edited concurrently is indistinguishable from test output. An already
dirty file that a test rewrites has the same status line as before, so its original
contents are neither protected nor restored. `git()` ignores command failures.
A subprocess timeout also escapes the future without a normal per-test result.

**Small fix:** upstream the conformance fixture into a temporary directory. Until
then refuse unsafe dirty fixture inputs or run the mutating test in isolation;
never infer ownership from a status-line difference. Preserve failures and timeouts
as results and check Git exit status. Keep tests out of another agent's checkout.

### A06 — Medium: startup order and runtime configuration are implicit

**Evidence:** audio, input, GCM, injection and SPURS overrides use independent static
constructors. Their relative initialization order across translation units is not
a public contract. Startup writes a decoder stand-in beside the executable before
main; the install target only installs the executable. A read-only installed binary
directory therefore prevents creating the native MP3 stand-in.
`config.toml` contains memory/threading/graphics/debug settings, but the port's
reader consumes only uppercase keys in `[input]`. That reader will accept unrelated
uppercase environment names too. Changing most advertised settings does nothing.

**Small fix:** one explicit port-initialization function called before guest workers,
with a fixed order: supported settings, defaults, registrations, writable resources.
Retain the useful small implementation files. Restrict the input keys to supported
settings and mark inert template sections clearly or remove them. Put generated
stand-ins in a selected writable data location, or install them explicitly.

### A07 — Medium: frame-clock lifetime and timing need an explicit contract

**Evidence:** `src/main.cpp:252` advances by 16 ms, which is 62.5 Hz, not 60 Hz.
The frame thread loops forever; after window close it disables rendering but keeps
running the guest. `CreateThread` at line 453 is unchecked. Presented-frame reads
use volatile while writes use an interlocked operation; volatile reads do not form
a C++ atomic synchronization contract. Negative/invalid `FRAME_CLOCK_SLEEP_MS`
values go through unchecked `atoi` into an unsigned delay.

**Small fix:** keep pacing work under T012/T040 and shutdown under T018. Use a
monotonic fractional 60 Hz deadline, checked settings, actual atomic counter access,
startup failure propagation, and an owned stop/join lifecycle. Preserve GCM callback
affinity: do not move callbacks back onto the rendering thread during this cleanup.
This finding does not establish that 62.5 Hz is the cause of observed FPS dips.

### A08 — Medium: cross-platform claims exceed current verification

**Evidence:** main's inherited header claims Windows/macOS CI coverage, but this
superproject has no tracked CI workflow. The frame clock uses POSIX clock_gettime
unconditionally; the zlib override uses GNU atomic/byte-swap builtins; executable
path discovery uses `/proc/self/exe` on every non-Windows host. Windows and macOS
are not proven by the Linux script results. Some of this is already tracked by T011.

**Small fix:** state Linux/Vulkan as verified, Windows/Metal as future targets. Use
`std::chrono` for port-owned clocks and small platform helpers where needed. Add a
source-only compile smoke job before promising another platform. Do not claim an
unperformed MSVC build failure or a macOS boot failure from inspection alone.

### A09 — Medium: patch complexity has outgrown inventory-only verification

**Evidence:** patch 0038 adds batching arenas, constant reuse, a geometry cache and
GPU timing, but its included test change exercises present/readback, not batch
rollover, descriptor capacity, cache reset or resource lifetime. Patch 0044's README
explicitly says it has no dedicated regression. Most patch rows are still "to offer".
The README also has stale cross-references (0029 describes 0028 as the ctor seed;
the seed patch is 0026). These are not evidence of a current rendering failure.

**Small fix:** add targeted source-only state/lifetime tests and a Vulkan validation
run when GPU work resumes. Track dependencies/upstream disposition for each patch.
Keep the exportable patch model; split new behavioral features from diagnostics
where practical, rather than rewriting or squashing the entire working series.

### A10 — Medium: task-board creation is not safe for concurrent writers

**Resolved by T049 (2026-10-20):** claim/note/done/release/new run under a `board` flock; note/done/release verify the owner (`TASK_FORCE=1` overrides); `new` validates the slug. `tools/test_task.py` covers concurrency and ownership. The merge-commits-whole-board behavior is documented in workflow.md, not changed.

**Evidence:** `tools/task.sh` computes the next ID from existing names and writes
it without a board lock. Two agents can choose the same ID. Note/done/release do
not verify the caller owns the task. Merge commits the entire shared board, so
another agent's state can be published by a merge unrelated to its work.

**Small fix:** serialize board mutations and ID allocation with one short board
lock; validate owner on done/release. Document the shared-board commit behavior.
Keep the file-based board; no scheduler or database is warranted.

### A11 — Low: documentation and contribution metadata need one cleanup pass

**Evidence:** status still names desktop patch 0041 instead of 0039, lists completed
T043 in the queue, and says "goal 60" in the phase table. `src/stubs.cpp` retains
unused template examples. No top-level README or project license is tracked. Imported
MIT notices exist, but they do not choose a license for the project's original code.
The doc linter checks local filesystem existence, including ignored game-derived
paths, despite advertising no game-data requirement. That blocks clean clones.

**Small fix:** remove inert examples; keep current status separate from immutable
history; check tracked paths without requiring proprietary data. Add a short human
README linking existing docs. Ask the owner to choose the original-code license;
retain third-party notices. Avoid a second documentation hierarchy in specs.

## Minimal extension rules

1. Guest-address/NID behavior stays in a named title override. Add evidence and a test.
2. Reusable firmware/renderer behavior stays title-agnostic in an exported runtime patch.
3. Generated lifts remain unedited inputs, with explicit generation provenance.
4. New startup behavior uses an explicit call, not another side-effectful constructor.
5. Keep ABI declarations in one header where available (the keyboard bridge currently
   repeats CellPadHostInput). Do not add virtual interfaces merely to shorten files.
6. Extract only meaningful units: VFS/VM setup, frame lifecycle, configuration and test
   discovery. Do not mechanically split the MP3 decoder/tables to meet line counts.

## Cleanup sequence and verification

| Order | Work | Acceptance |
|---|---|---|
| 1 (T047) | A01/A02: native boundary safety | Synthetic boundary, overflow, truncated-stream and long-path regressions; no game data |
| 2 (T048) | A03/A05/A11: trustworthy verification | Manifest includes the three nested suites; skips visible; no source restoration; fast lint works without local game trees |
| 3 (T049) | A04/A10: predictable tooling | Source-only fixtures prove dirty-state refusal, stack identity, serialized builds and unique task IDs |
| 4 | A06: explicit startup and honest settings | Initialization-order and setting-precedence tests; read-only install location works |
| 5 | A07/A08/A09: existing runtime follow-ups | T012/T018/T011/T040/T013; controlled before/after boot and performance checks when implementation changes |

Verification commands used: `tools/lint.py`; private `tools/task.sh lock cpu
 tools/lint.py --tests`; and explicit `python3` invocation of each nested suite in
A03 under the same CPU lock. No network services, firmware downloads, agents or
new dependencies were used. After the user reported a cybersecurity flag, review
continued with static inspection and existing regression tests only.
