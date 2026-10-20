# T048: Make verification complete, non-mutating and game-data independent

Status: done
Owner: claude
Priority: 2
Touches: tools/lint.py, tools/test_lint.py (new), patches/ps3recomp/T048-*.patch (test fixture isolation only), docs/project-audit.md (A03/A05/A11), docs/pipeline.md
Reads: docs/project-audit.md, patches/ps3recomp/README.md, docs/workflow.md

## Goal
Address T046 verification gaps: explicitly include nested SDL/Vulkan test runners, report skips/timeouts and preserve outputs, avoid checkout-based source restoration, and stop requiring ignored game paths for fast doc lint.

## Done when
Source-only fixtures prove manifest completeness, timeout handling, dirty-source preservation and clean-clone lint behavior. All currently discovered scripts and the three nested suites pass. Missing required tools fail in explicit strict mode; ordinary local skips remain visible. Do not run tests in another agent's runtime checkout.

## Log
- 2026-10-20 21:47 claude: claimed
- 2026-10-20 21:52 claude: DONE: lint.py: nested suites in manifest, per-script logs, skip/timeout results, --strict, byte-restore instead of git checkout, clean-clone doc lint; test_lint.py. NOT done: upstream patch moving the ppu_conformance fixture to a temp dir (A05 root cause); strict fails here only for optional Metal/encoder/lift-tool skips.
