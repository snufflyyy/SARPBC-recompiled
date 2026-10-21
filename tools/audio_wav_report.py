#!/usr/bin/env python3
"""Judge an AUDIO_WAV capture: silent blocks, gaps and block-edge clicks. Python 3 stdlib only (T053).

  AUDIO_WAV=/tmp/a.f32 tools/boot_check.sh 100 --scenario menu
  tools/audio_wav_report.py /tmp/a.f32 [--from SEC] [--to SEC] [--max-gaps N] [--max-clicks N]

The capture is raw f32le stereo at 48 kHz, one cellAudio block (256 frames) after another, the
final mix before the device. A non-silent file is not good audio: the PS3's mixer writes one
block per 5.33 ms into an 8-block ring, and a round that runs late leaves ring slots empty, which
the reader plays as 5.33 ms of silence (a gap, heard as crackling). So this reports

  silent    share of blocks that are all zero, from the first non-silent block on
  gaps      transitions from a sound block to a silent one (a natural pause counts as one gap)
  clicks    sample steps at a block edge more than --click-ratio (8) times the local mean step:
            a block that was overwritten or dropped, or one that starts or ends in silence, leaves a
            discontinuity there

Window times count from the start of the capture. Exit status 1 when --max-gaps / --max-clicks
(if given) are exceeded, so a script can gate on it.
"""
import argparse
import array
import sys

BLOCK = 256
RATE = 48000


def load(path):
    a = array.array("f")
    with open(path, "rb") as f:
        data = f.read()
    a.frombytes(data[: len(data) // 8 * 8])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def analyse(samples, lo_s=0.0, hi_s=None, click_ratio=8.0, k=64):
    """samples: interleaved stereo floats. Returns a dict of counts for the window."""
    frames = len(samples) // 2
    lo = int(lo_s * RATE) // BLOCK * BLOCK
    hi = frames if hi_s is None else min(frames, int(hi_s * RATE))
    hi = lo + (hi - lo) // BLOCK * BLOCK
    left = samples[2 * lo: 2 * hi: 2]
    nblocks = len(left) // BLOCK
    silent = [not any(left[b * BLOCK:(b + 1) * BLOCK]) and
              not any(samples[2 * (lo + b * BLOCK) + 1: 2 * (lo + (b + 1) * BLOCK): 2]) for b in range(nblocks)]
    first = next((i for i, s in enumerate(silent) if not s), nblocks)
    live = silent[first:]
    gaps = sum(1 for i in range(1, len(live)) if live[i] and not live[i - 1])
    # discontinuities at block edges, against the mean absolute step around them
    clicks = 0
    for b in range(max(first, 1), nblocks):
        if silent[b] and silent[b - 1]:
            continue
        e = b * BLOCK
        step = abs(left[e] - left[e - 1])
        around = [abs(left[i] - left[i - 1]) for i in range(max(1, e - k), min(len(left), e + k)) if i != e]
        mean = sum(around) / len(around) if around else 0.0
        if step > click_ratio * (mean + 1e-6):
            clicks += 1
    return {"blocks": len(live), "first_sound_block": first, "silent_blocks": sum(live),
            "silent_pct": 100.0 * sum(live) / len(live) if live else 0.0, "gaps": gaps, "clicks": clicks,
            "seconds": len(live) * BLOCK / RATE}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("wav")
    ap.add_argument("--from", dest="lo", type=float, default=0.0)
    ap.add_argument("--to", dest="hi", type=float, default=None)
    ap.add_argument("--click-ratio", type=float, default=8.0)
    ap.add_argument("--max-gaps", type=int, default=None)
    ap.add_argument("--max-clicks", type=int, default=None)
    args = ap.parse_args(argv)
    r = analyse(load(args.wav), args.lo, args.hi, args.click_ratio)
    print("%s: %.1f s from the first sound, silent %.1f%% (%d of %d blocks), gaps %d, block-edge clicks %d"
          % (args.wav, r["seconds"], r["silent_pct"], r["silent_blocks"], r["blocks"], r["gaps"], r["clicks"]))
    bad = (args.max_gaps is not None and r["gaps"] > args.max_gaps) or \
          (args.max_clicks is not None and r["clicks"] > args.max_clicks)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
