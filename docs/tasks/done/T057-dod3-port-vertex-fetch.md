# T057: Port next 4: fetch vertices attribute by attribute (fork df94c65)

Status: done
Owner: claude
Priority: 12
Touches: patches/ps3recomp/NNNN-vertex-fetch-by-attribute.patch (libs/video/rsx_vertex_fetch.c, rsx_draw_engine.c vertex decode), docs/dod3-reuse.md
Reads: docs/dod3-reuse.md Port next 4, https://github.com/soyjxck/ps3recomp commit df94c65 (MIT)

## Goal
Port the fork's per-attribute vertex fetch (self-checking with RSX_VFETCH_CHECK=1). The menu's biggest CPU item is the draw engine's per-vertex decode (docs/subsystems.md 'Menu frame rate'); dod3 measured 23-37% faster replays, byte-identical. Keep authorship (git format-patch from the fork or 'Ported from' in the message).

## Done when
Byte-identical output vs the old path (RSX_VFETCH_CHECK=1 clean over an arena run), measured drain-time gain in docs/subsystems.md, tests pass, patch exported.

## Log
- 2026-10-21 14:30 claude: claimed
- 2026-10-21 14:30 claude: Obsolete: v0.16.0 already has rsx_vertex_fetch_all (rsx_vertex_compact.c:361, per-attribute with stable_base fast path; used by rsx_draw_engine.c:1991). Applying the fork patch would duplicate it. Only the 8-lane eng_texture_content_hash remains; not taken (upstream's sparse re-hash already cut that cost).
- 2026-10-21 14:30 claude: DONE: Closed: per-attribute vertex fetch is already in the pin; docs/dod3-reuse.md corrected.
