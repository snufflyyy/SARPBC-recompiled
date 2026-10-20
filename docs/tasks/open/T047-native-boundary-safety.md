# T047: Validate native zlib requests and VFS path bounds

Status: open
Owner: -
Priority: 2
Touches: src/overrides/edgezlib.cpp, src/main.cpp (setup_vfs only), tools/test_edgezlib.py (new), tools/test_vfs.py (new), docs/project-audit.md (A01/A02), docs/build-linux.md
Reads: docs/project-audit.md, docs/subsystems.md (SPURS/Edge zlib), docs/reference-ports.md, docs/dod3-reuse.md

## Goal
Address T046 A01/A02: check complete guest spans and size arithmetic at the native zlib boundary; define failure/completion behavior from ABI evidence; replace the undersized POSIX realpath destination. Preserve the working boot and keep runtime code title-agnostic where applicable.

## Done when
Synthetic tests cover valid copy/inflate, truncated streams, invalid spans, temporary-size overflow, counter alignment/completion, and long VFS paths without game data. Verify with lint/tests and a controlled 01.09 boot before claiming runtime success. Avoid uncontrolled crash reproductions.

## Log
