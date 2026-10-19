#!/usr/bin/env python3
"""Convert a binary PPM frame dump (PS3RECOMP_VK_DUMP) to PNG, stdlib only.

    python3 tools/ppm2png.py captures/frame.ppm [out.png]

Prints the size and how many sampled pixels are non-black, a quick "did anything
draw" check before opening the image.
"""
import argparse
import struct
import sys
import zlib


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("ppm")
    ap.add_argument("png", nargs="?")
    args = ap.parse_args()
    out = args.png or args.ppm.rsplit(".", 1)[0] + ".png"

    data = open(args.ppm, "rb").read()
    magic, dims, maxval, px = data.split(b"\n", 3)
    if magic != b"P6" or maxval != b"255":
        sys.exit("not an 8-bit binary PPM")
    w, h = map(int, dims.split())
    rows = b"".join(b"\x00" + px[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    with open(out, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))
    lit = sum(1 for i in range(0, len(px), 3 * 97) if px[i:i + 3] != b"\0\0\0")
    print(f"{out}: {w}x{h}, {lit} of {len(px) // (3 * 97)} sampled pixels non-black")


if __name__ == "__main__":
    main()
