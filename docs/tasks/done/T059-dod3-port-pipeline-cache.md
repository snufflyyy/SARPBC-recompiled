# T059: Port next 10a: shader pipelines built off the walker, VkPipelineCache (fork baa72c0, 382482c)

Status: done
Owner: claude
Priority: 14
Touches: patches/ps3recomp/NNNN-vulkan-pipeline-cache.patch (libs/video/rsx_vulkan_backend.c, rsx_draw_engine.c), docs/dod3-reuse.md
Reads: docs/dod3-reuse.md Port next 10, fork commits baa72c0 and 382482c (MIT)

## Goal
New shader pipelines are built on the FIFO walker (200-450 ms each in dod3, hitches when effects first appear, e.g. the arena's first frames). Build them off the walker and add a VkPipelineCache (optionally persisted under gamedata/, never game data in git).

## Done when
Measured pipeline-build stalls before/after on an arena boot (docs/subsystems.md), no rendering change, tests pass, patch exported.

## Log
- 2026-10-21 14:52 claude: claimed
- 2026-10-21 16:13 pi: RELEASED: User-authorized takeover after Claude exhausted usage; main clean except board, task log only claim and no T059 implementation found. Preserve all completed audio/shadow/profiler changes. Pi will implement caching after higher-priority queue.
- 2026-10-21 16:13 pi: claimed
- 2026-10-21 20:07 pi: HANDOFF: user now asks pi to finish T058 then stop. No async pipeline/VkPipelineCache implementation was started by pi. Preserve Claude main commit e2f4c73 and patch0070-pipe-times.patch: docs/subsystems.md Pipeline build cost records130s arena,189 pipelines,1.8s total,10ms average,65ms max,mostly hidden by loads and one25ms play build; its assessment is not to port until later-scene hitches justify it. T005/T009 were independently completed/closed by Claude and normally merged with T058. Next agent should use these measurements rather than add a worker/cache speculatively. branch=pi/work (merged); no cache WIP to recover.
- 2026-10-21 20:07 pi: RELEASED: User requested stop after current T058; see HANDOFF and existing measured non-port assessment, no cache implementation started.
- 2026-10-21 21:14 claude: claimed
- 2026-10-21 21:14 claude: pi stopped without implementing it. Measured (RSX_ENGINE_PIPE_TIMES, patch 0070): 189 pipelines, 1.8 s total, 10 ms avg, 65 ms max over a 130 s arena run, bursts hidden by load screens. Async build / VkPipelineCache not worth it on Vulkan (docs/subsystems.md 'Pipeline build cost').
- 2026-10-21 21:14 claude: DONE: Closed on measurement: pipeline builds are cheap here; diagnostic 0070 kept, no async build.
