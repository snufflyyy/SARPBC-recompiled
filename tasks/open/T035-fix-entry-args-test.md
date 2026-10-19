# T035: Fix tools/test_ppu_entry_arguments.py link failure (ppu_loaded_elf_path, from patch 0004)

Status: open
Owner: -
Priority: 8
Touches: patches/ps3recomp/T035-*.patch (tools/test_ppu_entry_arguments.py and its harness only)
Reads: patches/ps3recomp/0004-sys-prx-load-module.patch

## Goal
Found by T026: `external/ps3recomp/tools/test_ppu_entry_arguments.py` no longer links on our patch stack (`undefined symbol: ppu_loaded_elf_path`). Patch 0004 (T002, sys_prx_load_module) added a reference the test harness doesn't provide. Fix the harness (define the symbol or link the object that has it), not the runtime. Run every `tools/test_*.py` in ps3recomp and list any other failures in the task log.

## Done when
The test passes on the full stack (`tools/apply_patches.sh`); the other test results are logged.

## Log
