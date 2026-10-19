# T007: Audio — MultiStream on SPU through cellAudio/SDL2

Status: open
Owner: -
Touches: src/overrides/audio_*.cpp (new), patches/ps3recomp/T007-*.patch (libs/audio/**, runtime/spu/** only for audio), docs/subsystems.md (Audio section only)
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
firmware files is an option only if the user explicitly agrees; ask the coordinator, never
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
