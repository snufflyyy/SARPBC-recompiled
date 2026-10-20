# T051: Replace shader-length viewport heuristic with semantic orientation handling

Status: open
Owner: -
Priority: 1
Touches: patches/ps3recomp/T051-*.patch, patches/ps3recomp/README.md, docs/subsystems.md (Graphics orientation), docs/t038-review.md (resolution), docs/status.md (verification note)
Reads: docs/t038-review.md, patches/ps3recomp/0050-loadscreen-passthrough-orientation.patch, docs/reference-ports.md, docs/dod3-reuse.md

## Goal
Resolve T050 finding F01 without regressing T038's visibly correct loading screen. Establish the actual RSX/host viewport contract, then replace the instruction-count-only Y flip with a title-agnostic rule. If a temporary title workaround is unavoidable, keep it out of the shared runtime and explicitly extend Touches to the needed src/overrides files before editing them. Correct the projection-dependent setInvertY rationale; the current SPIR-V compiler applies it to all vertex stages.

## Done when
Commit source-only regressions proving identical shader semantics retain orientation after adding a NOP, unrelated two-instruction arithmetic/constant programs are not treated as passthrough, and non-centered viewport offsets work. Cover both viewport scale signs and fixed/guest pipeline paths. Existing renderer tests pass; 01.09 loading text, logos, menu, arena and HUD remain upright in a bounded boot. Document untested backends rather than assuming Vulkan evidence proves Metal/D3D12. Update the patch provenance and review resolution.

## Log
- 2026-10-20 pi: Created from T050. Synthetic neutral-backend probe produces byte-identical HLSL for two- and three-instruction MOV/MOV(+NOP) shaders, but opposite Y transforms: (-1,-0.5) vs (+1,+0.5). Fresh 120 s Linux/Vulkan run confirms upright Loading and arena/HUD with patch 0050 still present. This is a runtime-generalization defect, not a newly demonstrated SARPBC visual regression.
