# T007: Audio — MultiStream on SPU through cellAudio/SDL2

Status: open
Owner: -
Priority: 14
Touches: tools/make_spu_overlays.py + its relift.sh step (coordinator-approved 2026-10-19), src/overrides/audio_*.cpp (new), patches/ps3recomp/T007-*.patch (libs/audio/**, runtime/spu/** only for audio), docs/subsystems.md (Audio section only)
Reads: analysis/spu_EBOOT_elf/ (images 12-14 mstream_dsp_*), docs/reference-ports.md (dod3 src/apu/)

## Goal
The game uses MultiStream (`cellMS*`, statically linked, SPU-side mixing, DSP effects as
SPU images 12-14) feeding cellAudio. Find out whether audio starts during the current
boot (cellAudio port open, MultiStream SPU task dispatch, mstream images HIT/MISS), and
what blocks it: e.g. MultiStream loading an MP3 decoder from firmware (Drakengard 3 had
to replace it natively, see docs/reference-ports.md); `/dev_flash` maps to
`PS3_DEV_FLASH`, which defaults to a Windows path upstream. Get sound out through SDL2 or
document precisely what is missing. Test with a real audio device (not SDL dummy) and
check the log for underruns.

## Lead from T001 (2026-10-18)
On both versions MultiStream's update thread starts after MAINMENU and blocks on event flag
`0x01372000` (01.09) after trying to open the firmware file `/dev_flash/.../flashMP3.pic`.
ps3recomp maps `/dev_flash` to `$PS3_DEV_FLASH`, defaulting to a Windows path
(`D:/recomp/tools/rpcs3/dev_flash`, runtime/ppu/ppu_fs.cpp:144). We ship no firmware.
Preferred fix: a native stand-in for the MP3 decoder MultiStream loads, as Drakengard 3 did
(docs/reference-ports.md, dod3 src/apu/mp3_native.c + a stand-in SPU image). Using real
firmware files is an option only if the user explicitly agrees; ask the user, never
download firmware yourself. Also make the default `/dev_flash` path sane on Linux (patch).
Target 01.09 (versions/0109, read-only).

## Done when
Either audible output (state how verified) or a precise blocker list with addresses, all
in docs/subsystems.md.

## Log
- 2026-10-18 23:49 agent-audio: claimed
- 2026-10-18 23:54 agent-audio: 01.09 (+local cellOvis workaround): cellAudio Init/PortOpen(8ch,8blk)/PortStart OK (buf 0x58000000). MultiStream mixer = SPU image 0 (sha e33837bb, fp C1759183E2FF7448, task entry EA 0x010AF300), lifted, dispatched as taskset 0x01370680 task 0. It ends at 'branched into unlifted LS 0x37018 (lr 0x03930)': the DSP plugin block DMA'd to LS 0x37000 (same as dod3). Update thread then blocks on flag 0x01372000. SPU_INTERP_UNLIFTED=1 gets past it (no more BLOCKED on 0x01372000), but drain-resume host depth climbs per call. flashMP3.pic missing -> 'mp3 failed to load MP3 codec' + MFC GET size=0 at SPU pc 0x0B1C8 lsa 0x30B60.
- 2026-10-18 23:57 agent-audio: Merged main (0001-0008), dropped local cellOvis workaround. Plan per user directive: port dod3 src/apu (mp3dec.c, mp3_native.c stand-in flashMP3.pic, msdsp) with attribution. NEED (outside my Touches): the DSP plugin block that MultiStream DMAs to LS 0x37000 (images 12-14 packed) must be lifted as an overlay at 0x37000 like dod3 tools/make_spu_overlays.py + a relift.sh step. Until granted I run it through SPU_INTERP_UNLIFTED=1 (works: flag 0x01372000 no longer blocks).
- 2026-10-19 00:08 agent-audio: HANDOFF: done=cellAudio port runs on a real device (PipeWire, SDL pulseaudio) at 187.5 blocks/s, 0 underruns, 0 dropped (patch T007-audio-pacing-devflash-sig-region: POSIX pacing + AUDIO_RATE/PEAK/WAV, /dev_flash default off Windows, spu_overlay_register_sig_region); stand-in flashMP3.pic + native decodeFrame at LS 0x1A910 ported from dod3 (src/overrides/audio_mp3*.cpp, MIT): the file opens, the 'mp3 failed' error is gone. state=the mixer (SPU image 0, fp C1759183E2FF7448) calls the DSP plugin block DMA'd to LS 0x37000 (0x37018 lr 0x03930), which is not lifted, so the task ends and flag 0x01372000 blocks; SPU_INTERP_UNLIFTED=1 works around it (flag no longer blocks), but every block is still silent (100%) and decodeFrame has not been called yet (no MP3 stream starts before the Loading... stall). next=(1) port dod3 tools/make_spu_overlays.py wrap/register to lift the DSP block (images 12-14 packed as dod3 PLUGINS, check the offsets with SPU_DUMP_OVL=<dir>,0x37000) at 0x37000 + a relift.sh step (needs tools/ in Touches); (2) port msdsp_hooks.c; (3) once the boot gets past Loading, verify with SARPBC_MP3_TRACE=20 AUDIO_RATE=1 AUDIO_PEAK=1 SDL_AUDIODRIVER=pulseaudio; (4) check the drain-resume host depth under SPU_INTERP_UNLIFTED over long runs. branch=worktree-agent-acc9f9ae8ed145a97
- 2026-10-19 00:08 agent-audio: RELEASED: paused for usage; see HANDOFF note
- 2026-10-19 08:58 agent-audio: claimed
- 2026-10-19 09:14 agent-audio: Resumed (merged worktree-agent-acc9f9ae8ed145a97 clean, 16 patches apply). SPU_DUMP_OVL dump of the 0x37000 GET (01.09): block = mstream_dsp_i3dl2 text @+0x0 (0x27C0) + mstream_dsp_para_eq @+0x2800 (0x690), span 0x2E90, byte-identical to the ELF PT_LOADs (no relocs); filter plugin not loaded. tools/make_spu_overlays.py (dod3 port) lifts it at 0x37000 as spu_ovl_msdsp_37000 (94 funcs incl 0x37018/0x37010/0x37C20/0x39818/0x39810/0x39B50), image id 0x4D534401, sig-region registered by a constructor appended to its spu_recomp.c (no CMake change). relift.sh step added.
- 2026-10-19 09:22 agent-audio: VERIFIED: without SPU_INTERP_UNLIFTED, 01.09 build-0109 (overlay lifted) has no 'unlifted LS 0x37018' and no EventFlagWait BLOCKED on 0x01372000 (before: BLOCKED 10s..). boot_check: 'STALLED since 22.1s | last open GUIDCACHE.XXX@4.1s | pkgs 13 | zlib 3147 | unresolved 0' (stall is T022's guard 0x0133AA80). Mixer cycles: SPURS_EF_STATS flag 0x01372000 75/s mean 11ms; SPU_DMA_RANGE=58000000-58200000 PUT 410 KB/s into the cellAudio port (real time 8ch*256*4*187.5=1.536 MB/s). perf: 37% in out-of-line spu_shufb byte loop (no __SSE4_1__ in our build). Same build with -DCMAKE_C_FLAGS=-msse4.1: 120 cycles/s, 660 KB/s. Audio still 100% silent (pulseaudio, 0 underruns) -- nothing plays during Loading.
- 2026-10-19 09:32 agent-audio: After merging main (22 patches + T007 patch apply: 'external/ps3recomp: 41 patch(es) on 39a3629'), build-0109 with the overlay, no SPU_INTERP_UNLIFTED: boot_check 2026-10-19 09:31 v01.09 5f6de36 60s: STALLED since 22.2s | last open GUIDCACHE.XXX@7.2s | pkgs 13 (GUIDCACHE last) | zlib 3147 | dumps 8 lit 8 distinct 1 | flips 9 | threads 13/8 alive | unresolved 0. No BLOCKED on 0x01372000, no 'unlifted LS 0x37', ef-stats flag 0x01372000 ~75 waits/s. Remaining stall is not MultiStream (only other unlifted: PhysX img 363824547 LS 0x20180).
- 2026-10-19 09:32 agent-audio: HANDOFF: done=tools/make_spu_overlays.py (dod3 port) + relift.sh step lift MultiStream's DSP block (i3dl2 @+0, para_eq @+0x2800, span 0x2E90) at LS 0x37000 as spu_ovl_msdsp_37000, sig-region image 0x4D534401; flag 0x01372000 no longer blocks without SPU_INTERP_UNLIFTED (01.09). Docs: subsystems.md Audio. state=coordinator must run '.venv/bin/python tools/make_spu_overlays.py --spu versions/0109/src/spu_gen' (and src/spu_gen for 01.02, layout there unverified) or relift, then reconfigure CMake; pipeline.md should list the step. Mixer is CPU-bound: 75 cycles/s = 27% of real time (1 block of 8 KB per cycle, 187.5 needed); -msse4.1 gives 43%. Audio still 100% silent (nothing plays before the stall). next=(1) generic SPU perf: build SPU sources with SSE4.1/x86-64-v2 (CMakeLists) and an x86 SIMD fast path for spu_fa/fs/fm/fma in runtime/spu/spu_helpers.h (37% shufb, 17% float helpers in perf); (2) verify 01.02 layout with SPU_DUMP_OVL=<dir>,0x37000; (3) once past Loading: SARPBC_MP3_TRACE=20 AUDIO_RATE=1 AUDIO_PEAK=1 SDL_AUDIODRIVER=pulseaudio for non-silent blocks + decodeFrame; (4) maybe native hooks for the i3dl2 loop 0x37478-0x37974 (dod3 msdsp_hooks addresses do not apply); (5) cellAudio patch 0058/0080/0081/0076 pacing items from dod3-reuse. branch=worktree-agent-a4f6294d20d599a57
- 2026-10-19 09:32 agent-audio: RELEASED: paused; see HANDOFF (boot blocker fixed, audio polish remains)
