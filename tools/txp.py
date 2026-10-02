"""TXP texture <-> PNG (NIS PSP texture format).

Header (0x10 bytes, little endian):
  u16 width, u16 height, u16 palette entries (0 = none), u16 0,
  u16 palette entries (again), u16 1, u16 1, u16 1
Palette: RGBA8888 entries. Pixels: 4bpp (16-colour, low nibble first) or 8bpp (256-colour),
stored PSP-swizzled (16-byte x 8-row blocks).
"""
import argparse
import struct
import sys

from PIL import Image


def unswizzle(px, row_bytes, h):
    out = bytearray(row_bytes * h)
    bw = row_bytes // 16
    i = 0
    for by in range(h // 8):
        for bx in range(bw):
            for r in range(8):
                o = (by * 8 + r) * row_bytes + bx * 16
                out[o:o + 16] = px[i:i + 16]
                i += 16
    return bytes(out)


def swizzle(px, row_bytes, h):
    out = bytearray(row_bytes * h)
    bw = row_bytes // 16
    i = 0
    for by in range(h // 8):
        for bx in range(bw):
            for r in range(8):
                o = (by * 8 + r) * row_bytes + bx * 16
                out[i:i + 16] = px[o:o + 16]
                i += 16
    return bytes(out)


def read_txp(data):
    w, h, npal = struct.unpack_from("<HHH", data, 0)
    pal = [tuple(data[0x10 + i * 4:0x14 + i * 4]) for i in range(npal)]
    bpp = 4 if npal == 16 else 8
    px = unswizzle(data[0x10 + npal * 4:], w * bpp // 8, h)
    img = Image.new("RGBA", (w, h))
    out = []
    if npal == 16:
        for b in px[: w * h // 2]:
            out += [pal[b & 0xF], pal[b >> 4]]
    elif npal == 256:
        out = [pal[b] for b in px[: w * h]]
    else:
        raise ValueError(f"unsupported palette size {npal}")
    img.putdata(out)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("txp"); ap.add_argument("png")
    a = ap.parse_args()
    with open(a.txp, "rb") as f:
        read_txp(f.read()).save(a.png)


if __name__ == "__main__":
    sys.exit(main())
