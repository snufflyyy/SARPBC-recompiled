# T038: The 'Loading...' screen is drawn upside down (render-target orientation)

Status: open
Owner: -
Priority: 13
Touches: patches/ps3recomp/T038-*.patch (runtime/rsx/** orientation only), docs/subsystems.md (Graphics)
Reads: docs/subsystems.md

## Goal
From T028: the "Loading..." screen is drawn upside down. This is probably a render-target or present Y-flip mismatch between RSX surface origin and Vulkan. Check whether other screens are right (ESRB, menu look right), find the case that differs (window origin / surface clip / shader viewport), and fix it generally.

## Done when
Loading screen upright in a capture, other screens unchanged.

## Log
