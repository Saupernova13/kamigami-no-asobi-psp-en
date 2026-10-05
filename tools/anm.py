"""Textures inside anm*.dat animation files (title cards, quiz screens, garden, effects).

  python tools/anm.py export <original.iso> [--out work/images/export/anm]

An anm file (FUN_088b631c): u32 block count, 12 bytes of padding, then the blocks. Each
block starts with a 0x3c-byte header:

  u32 size (to the next block), u32 x5 (counts; the fourth word's halves are the
  palette and texture counts), u32 x9 section offsets, relative to the block

Section 3 lists palettes, 8 bytes each: u32 offset (relative to the block), u32 colours
(16 or 256, RGBA8888). Section 4 lists textures, 12 bytes each: u32 offset, u16 width,
u16 height, u8 bits per pixel (4 or 8), u8 0x10, u8 0x10, u8 swizzled (1: PSP 16x8
blocks as in .txp, 0: linear rows). Texture i uses palette i. Sections 5 and 6 hold the
sprite rectangles and frames that cut the textures up; they are not touched here.

Texture paths for translation/images.json: "DATA.DAT/anm0092.dat#B.T" is texture T of
block B (0-based), e.g. "START.DAT/anm9000.dat#1.0".
"""
import argparse
import os
import struct
import sys

from PIL import Image

import txp

HEADER = 0x3c


class Texture:
    def __init__(self, block, index, off, w, h, bpp, swizzled, pal_off, colours):
        self.block, self.index = block, index
        self.off, self.w, self.h, self.bpp, self.swizzled = off, w, h, bpp, swizzled
        self.pal_off, self.colours = pal_off, colours

    @property
    def size(self):
        return self.w * self.h * self.bpp // 8

    @property
    def name(self):
        return f"{self.block}.{self.index}"


def is_anm(data):
    if len(data) < 0x10 + HEADER:
        return False
    n, = struct.unpack_from("<I", data, 0)
    first, = struct.unpack_from("<I", data, 0x10)
    return 0 < n < 64 and data[4:0x10] == b"\0" * 12 and HEADER < first <= len(data) - 0x10


def textures(data):
    """-> [Texture] with absolute offsets into data."""
    n, = struct.unpack_from("<I", data, 0)
    out, o = [], 0x10
    for b in range(n):
        h = struct.unpack_from("<15I", data, o)
        size, secs = h[0], h[6:15]
        npal, ntex = h[3] & 0xFFFF, h[3] >> 16
        pals = [struct.unpack_from("<II", data, o + secs[3] + 8 * i) for i in range(npal)]
        for t in range(ntex):
            off, w, hh, bpp, _, _, sw = struct.unpack_from("<IHHBBBB", data, o + secs[4] + 12 * t)
            poff, colours = pals[t] if t < len(pals) else pals[-1]
            out.append(Texture(b, t, o + off, w, hh, bpp, sw, o + poff, colours))
        o += size
    return out


def sprites(data):
    """-> {"B.T": [(x, y, w, h)]}: the rectangles section 5 cuts from each texture, 16 bytes
    an entry (u16 texture, u16 palette, u32 0, s16 x, y, w, h). Animations list a rect
    more than once while it grows (a typed title starts at width 0); the widest is kept."""
    n, = struct.unpack_from("<I", data, 0)
    out, o = {}, 0x10
    for b in range(n):
        h = struct.unpack_from("<15I", data, o)
        size, secs = h[0], h[6:15]
        rects = {}
        for e in range(o + secs[5], o + secs[6] - 15, 16):
            t, _, _, _, x, y, w, hh = struct.unpack_from("<4H4h", data, e)
            if w > 0 and hh > 0 and rects.get((t, x, y), (0, 0))[0] < w:
                rects[(t, x, y)] = (w, hh)
        for (t, x, y), (w, hh) in sorted(rects.items()):
            out.setdefault(f"{b}.{t}", []).append((x, y, w, hh))
        o += size
    return out


def find(data, name):
    for t in textures(data):
        if t.name == name:
            return t
    raise KeyError(f"no texture {name} in this anm file")


def palette(data, t):
    return [tuple(data[t.pal_off + 4 * i:t.pal_off + 4 * i + 4]) for i in range(t.colours)]


def read(data, t):
    """-> RGBA image of texture t."""
    raw = data[t.off:t.off + t.size]
    row = t.w * t.bpp // 8
    if t.swizzled:
        raw = txp.unswizzle(raw, row, t.h)
    pal = palette(data, t)
    if t.bpp == 4:
        idx = [v for b in raw for v in (b & 0xF, b >> 4)]
    else:
        idx = list(raw)
    img = Image.new("RGBA", (t.w, t.h))
    img.putdata([pal[i] if i < len(pal) else (0, 0, 0, 0) for i in idx[:t.w * t.h]])
    return img


def write(data, t, img):
    """-> data with texture t replaced by img (same size; colours mapped to its palette)."""
    if img.size != (t.w, t.h):
        raise ValueError(f"image is {img.size}, the texture is {(t.w, t.h)}")
    index = txp._nearest(palette(data, t))
    idx = [index(c) for c in img.convert("RGBA").getdata()]
    if t.bpp == 4:
        raw = bytes(idx[i] | (idx[i + 1] << 4) for i in range(0, len(idx), 2))
    else:
        raw = bytes(idx)
    if t.swizzled:
        raw = txp.swizzle(raw, t.w * t.bpp // 8, t.h)
    out = bytearray(data)
    out[t.off:t.off + t.size] = raw
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["export"])
    ap.add_argument("iso")
    ap.add_argument("--out", default=os.path.join("work", "images", "export", "anm"))
    a = ap.parse_args()
    import game
    img = game.Image(a.iso)
    count = 0
    for arc in ("/PSP_GAME/USRDIR/START.DAT", "/PSP_GAME/USRDIR/DATA.DAT"):
        files, _ = img.archive(arc)
        for name in sorted(files):
            data = files[name]
            if not name.startswith("anm") or not is_anm(data):
                continue
            for t in textures(data):
                dest = os.path.join(a.out, arc.rsplit("/", 1)[1], f"{name[:-4]}#{t.name}.png")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                read(data, t).save(dest)
                count += 1
    img.close()
    print(f"{count} anm textures -> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
