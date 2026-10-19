# T007: Audio — MultiStream on SPU through cellAudio/SDL2

Status: claimed
Owner: agent-audio
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
