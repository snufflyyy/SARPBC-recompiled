# T056: SPU perf: the GCM pushbuffer hook walks 512 IO mappings on every SPU PUT

Status: claimed
Owner: pi
Priority: 7
Touches: patches/ps3recomp/T056-*.patch (libs/video/cellGcmSys.c: gcm_note_spu_put / gcm_ea2io_range and the IO-mapping add/remove sites only), docs/subsystems.md (SPU/SPURS, T032's subsection)
Reads: docs/subsystems.md "MFC DMA fast paths (T032)", docs/tasks/*/T032*

## Goal
**Phase: SPU performance, easy wins only.** Found by T032 (2026-10-21). `cellGcmInit` installs
`g_spu_put_hook = gcm_note_spu_put` (libs/video/cellGcmSys.c), which spu_dma.h calls on every SPU
DMA PUT. `gcm_ea2io_range` then walks all `CELL_GCM_MAX_IO_MAPPINGS` (512) `s_io_mappings`
slots looking for an active mapping that contains the EA. In the arena the MultiStream mixer SPU
issues ~65k PUTs/s; with the hook a PUT costs ~517 ns, with the hook skipped (experiment
build) ~218 ns: ~19 ms/s, about 2% of the busiest thread. Guess: every PUT misses (a full
512-slot walk; mixer output is not in IO-mapped memory).

Make the miss cheap with identical results, e.g. a generation counter bumped (after the
fields are written) at every site that changes `s_io_mappings` (find_free_mapping users,
unmap, cellGcmInit's reset), plus a cached [lowest ea, highest ea+size) and highest active
slot that the hook recomputes when the generation moves. Watch out: `s_io_mapping_count` is
NOT a reliable count of active slots (cellGcmInit resets it to 0 without clearing old slots),
so do not stop the walk after `count` hits. Measure as in T032 (rdtsc around
`spu_wrch(MFC_Cmd)`, or the PUT ns from subsystems.md) and keep the pushbuffer detection
tests passing.

## Done when
PUT cost in the arena within ~10% of the hook-skipped figure (~218 ns), GCM tests green, the
numbers in docs/subsystems.md, patch applies in the stack.

## Log
- 2026-10-21 15:40 pi: claimed
- 2026-10-21 15:51 pi: Root cause confirmed: gcm_ea2io_range scans 512 slots on every miss although the mixer never maps most of them. Implemented atomic allocation high-water mark, never active-count shortcut: grows before find_free_mapping returns; unmaps/reuse cannot shrink it; only real table-clear paths reset; direct Init slot 0 publishes one. Oracle test covers 50k random lookups, holes/count reset, full table, wrapping ends, SPU block coalescing/rejection. Baseline 2 efficiency assertions fail; optimized all pass including ASan/UBSan. Synthetic miss 8 slots: 188.91 -> 7.31 ns/call. Benchmarking actual hook delivery next; no DMA/coherency edits.
- 2026-10-21 16:06 pi: Actual sampled hook latency in two 130 s arena runs: baseline ~257 ns; high-water alone ~33.5 ns. Added an 8-byte monotonic 64 MiB-region EA bitmap for constant-time rejection of unmapped mixer regions; published at every map-add path and reset only with the whole table. Unmaps conservatively retain bits (no false negatives or generation/slot-count assumptions). New oracle includes region boundaries, whole-address ranges and overflow; sanitizer clean. Region-cache actual-game benchmark running.
