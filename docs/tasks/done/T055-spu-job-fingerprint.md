# T055: SPU perf: hashing the whole job image on every SPURS job dispatch

Status: done
Owner: claude
Priority: 6
Touches: patches/ps3recomp/T055-*.patch (runtime/spu/spu_workload.c: spu_workload_dispatch_job and its fingerprint lookup only), docs/subsystems.md (SPU/SPURS, own subsection)
Reads: docs/debugging.md "Profiling", docs/subsystems.md "SPU time by category (T029)", docs/tasks/*/T029*

## Goal
**Phase: SPU performance, easy wins only.** Found by T029's stacks sampler (2026-10-21): on the
Single Player screen (`tools/spu_profile.sh 30 --warmup 75 --scenario menu --version 0109`)
`spu_workload_dispatch_job` is the leaf of 28% of all on-CPU stacks (54 of 190), every one on a
short-lived `jc_thread` host thread (libs/spurs/cellSpurs.c). The leaf is the inlined
`spu_workload_fingerprint` (runtime/spu/spu_workload.c): a byte-at-a-time FNV-1a over the
**whole job image**, run on every job dispatch only to find the registered lifted entry. Not
seen in the arena run (0 of 127).

Make the lookup cheap without changing which function runs: e.g. memoize the last few
(image pointer, size) -> registry entry pairs and re-verify cheaply (the bytes can change at the
same EA when the title loads a different job), or hash a word at a time and register both
fingerprints. The registered fingerprint values are part of the generated registration, so the
mapping must stay exact. Measure with `tools/spu_profile.sh` before and after (share of
`spu_workload_dispatch_job`, host CPU, guest FPS); also check why each job chain walk runs on a
fresh thread (one `(gone)` tid per sample), which may be the next cost.

## Done when
`spu_workload_dispatch_job` drops out of the top SPU-runtime symbols on the Single Player screen,
before/after numbers in docs/subsystems.md, SPU tests green, the patch applies in the stack.

## Log
- 2026-10-21 14:30 claude: claimed
- 2026-10-21 14:52 claude: Memo implemented and verified to remove the hash from the profile, but 6 A/B menu runs show no fps gain (on 48-49, off 48-56); patch dropped. Documented in subsystems.md.
- 2026-10-21 14:52 claude: DONE: Closed without a patch: removing the job-image hash from the profile does not raise fps (A/B documented). The job-thread churn is not on the critical path.
