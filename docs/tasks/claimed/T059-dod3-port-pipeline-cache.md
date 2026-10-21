# T059: Port next 10a: shader pipelines built off the walker, VkPipelineCache (fork baa72c0, 382482c)

Status: claimed
Owner: pi
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
