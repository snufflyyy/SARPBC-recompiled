---
type: impact-analysis
context: T042 native Wayland desktop launch failure
---

# T042: Native Wayland surface-format enumeration

## Target
`external/ps3recomp/libs/video/rsx_vulkan_backend.c`: surface-format selection in
`vk_create_swapchain`, exported as an upstreamable patch.

## Dependents (2)
- Vulkan backend initialization calls `vk_create_swapchain` for windowed launches.
- `vk_swapchain_lost` calls it again after an out-of-date swapchain.

Headless mode does not call this code. SDL's Wayland and X11 drivers both use it.
T040 draw batching and T024 present readback are outside this change.

## Affected Stories
No release-plan stories exist. Board tasks: T042 (fix), T041 (desktop launch).
Work is in main per the user instruction recorded in docs/status.md session 9.

## Test Coverage
- Existing `test_vulkan_present_readback.py` covers present/readback, not WSI setup.
- New mocked regression will extract production format selection and cover lists
  larger than 64, VK_INCOMPLETE/retry, preference ordering, zero formats, allocation
  failure and driver errors, with allocation tracking and Valgrind.
- GCC and ROCm clang sanitizer runtimes are absent on this host, so ASan/UBSan
  cannot link. Valgrind Memcheck passes: 15 allocations/frees, zero leaks/errors.
- Native Wayland desktop smoke must create a swapchain and present frames.
- X11 desktop smoke checks the previously working path remains usable.

## Risk: Medium
Two callers share the WSI path across platforms; format policy must remain unchanged.
No public API, renderer pipeline, or title-specific behavior changes are needed.

## Recommended action
Add a failing regression first. Replace fixed-size truncation with complete,
dynamically sized enumeration and bounded retries if the driver's list changes.
Retain existing UNORM preference and unsupported/error fallback behavior.

## Evidence
The failing desktop log reports SDL `wayland` and
`vkGetPhysicalDeviceSurfaceFormatsKHR failed (VkResult 5)`. The source clamps `nf`
to 64 and sends the fill call through VK_CHECK, which accepts only VK_SUCCESS.
Vulkan defines 5 as VK_INCOMPLETE, not a fatal enumeration error:
https://docs.vulkan.org/refpages/latest/refpages/source/vkGetPhysicalDeviceSurfaceFormatsKHR.html
