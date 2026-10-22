# T060: Vulkan batches: submit without waiting (T060)

Status: done
Owner: claude
Priority: 1
Touches: patches/ps3recomp/0074-vulkan-async-batches.patch (libs/video/rsx_vulkan_backend.c), docs/subsystems.md, docs/frame-pacing.md
Reads: docs/subsystems.md "Menu frame rate", docs/frame-pacing.md "Ranked changes"

## Goal
The arena's frame clock thread was 78% busy draining the FIFO, and 46% of its stack samples were in
`vk_submit_and_wait` (GPU wait): a batch was submitted and waited for, CPU and GPU in series. Overlap
them (double-buffered batches), and stop forcing flushes for destroys and the depth snapshot.

## Done when
Arena fps measured before/after (boot_check --scenario arena, PS3_VERBOSE=0), rendering unchanged in
captures, tests pass, patch exported, docs updated.

## Log
- 2026-10-22 15:46 claude: claimed
- 2026-10-22 15:46 claude: baseline arena 38.9-40 guest fps; PS3RECOMP_VK_BATCH_STATS: 41 s of GPU waits per 130 s, 4955 present flushes (2.7 ms each) + 7370 vk_eng_release flushes (2.9 ms each). Stage 1 deferred destroy (graveyard): waits 41->36 s, fps ~+1. Stage 2 double-buffered contexts + async flush at present/full batch: waits 36->13.6 s, fps ~40 (gdb: depth snapshot's submit_and_wait now the stall, 9 of 33 samples). Stage 3 depth snapshot recorded in batch via persistent staging buffer: arena 47-48 fps, waits 1.4 s/130 s, captures identical (shadow right). Patch 0074. lint --tests 98/0 failed.
- 2026-10-22 16:21 claude: Stage 4: present was split into begin (at the flip) and finish polled with rsx_vulkan_backend_present_ready (0075 + src/main.cpp present_finish_if_ready). PS3RECOMP_VK_GPU_TIMES: GPU busy 5.0 ms/batch, idle 99 s of 130 s => stall was CPU-side serialisation (clock waited for the frame it had just submitted). Arena 55-60 fps (60 Hz clock), frame_clock present 1.56 s -> 0.13 s per 5 s. Verified: tools/verify.sh OK; 330 s run with pad through round end -> results screen intact, no alerts; lint --tests 98/0. GPU at P8 405 MHz on this box (nvidia-smi -lgc denied).
- 2026-10-22 16:21 claude: DONE: Async double-buffered Vulkan batches (0074), split polled present (0075 + main.cpp): arena 39 to 55-60 fps, GPU waits 41 s to 1.4 s; verified boot, 330 s through results, lint --tests. Left: draw-engine vertex fetch/remap and texture hashing CPU cost (Port next 9).
