# T034: runtime/ppu: locked stack carve for callback stacks + callbacks run with the caller's TLS (r13)

Status: done
Owner: claude
Priority: 10
Touches: patches/ps3recomp/T034-*.patch (runtime/ppu/ppu_loader.cpp guest-call path, runtime/syscalls/sys_ppu_thread.c stack allocator only), docs/ps3recomp-primer.md (T026 section)
Reads: docs/tasks/done/T026*, patches/ps3recomp/0028-ppu-guest-call-stacks.patch

## Goal
Two follow-ups from T026 (patch 0030). (1) Callback stacks are carved by storing `g_vm_stack_alloc.region_end` without `sys_ppu_thread.c`'s table lock. Today that's safe only because of the 16 MB headroom. Export a locked `ppu_stack_carve()` from sys_ppu_thread.c and use it. (2) Callbacks run with the shared TLS block (`r13 = PPU_TLS_TP`) instead of the calling guest thread's r13. On the console, sysutil and GCM callbacks run with the caller's TLS. Inherit `g_active_ctx->gpr[13]` when there is a calling guest thread, and keep PPU_TLS_TP for host-only threads. Low priority unless a boot shows TLS corruption in a callback.

## Done when
Tests extended (a carve racing a thread create; callback r13 equals the caller r13); the stack applies; a 01.09 boot_check line with no regression.

## Log
- 2026-10-21 01:50 claude: claimed
- 2026-10-21 01:50 claude: done as patch 0057: ppu_stack_carve() under the table lock, r13 inherited from g_active_ctx (shared TLS only on host-only threads); test_ppu_guest_call_stacks extended (r13, carve/allocate race); arena boot_check verify OK (36 fps, unresolved 0).
- 2026-10-21 01:50 claude: DONE: 
