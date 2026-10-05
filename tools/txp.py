"""TXP texture <-> PNG (NIS PSP texture format).

  python tools/txp.py decode <in.txp> <out.png>
  python tools/txp.py encode <in.png> <original.txp> <out.txp> [--new-palette]

Header (0x10 bytes, little endian):
  u16 width, u16 height, u16 palette entries (0 = none), u16 0,
  u16 palette entries (again), u16 1, u16 1, u16 1
Palette: RGBA8888 entries. Pixels: 4bpp (16-colour, low nibble first) or 8bpp (256-colour),
stored PSP-swizzled (16-byte x 8-row blocks).

Encoding keeps the original header and size. By default each pixel maps to the nearest
colour of the original palette, which suits re-lettering on the same artwork; with
--new-palette the image is quantized to a fresh palette of the same size.
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


def header(data):
    """-> (width, height, palette entries, bits per pixel, palette)"""
    w, h, npal = struct.unpack_from("<HHH", data, 0)
    if npal not in (16, 256):
        raise ValueError(f"unsupported palette size {npal}")
    pal = [tuple(data[0x10 + i * 4:0x14 + i * 4]) for i in range(npal)]
    return w, h, npal, 4 if npal == 16 else 8, pal


def read_txp(data):
    w, h, npal, bpp, pal = header(data)
    px = unswizzle(data[0x10 + npal * 4:], w * bpp // 8, h)
    img = Image.new("RGBA", (w, h))
    out = []
    if npal == 16:
        for b in px[: w * h // 2]:
            out += [pal[b & 0xF], pal[b >> 4]]
    else:
        out = [pal[b] for b in px[: w * h]]
    img.putdata(out)
    return img


def _nearest(pal):
    cache = {}
    clear = [k for k, p in enumerate(pal) if p[3] == 0]

    def index(c):
        i = cache.get(c)
        if i is None:
            if c[3] == 0 and clear:          # transparent: any clear entry, whatever its RGB
                i = clear[0]
            else:
                i = min(range(len(pal)), key=lambda k: sum((a - b) ** 2 for a, b in zip(pal[k], c)))
            cache[c] = i
        return i
    return index


def write_txp(img, original, new_palette=False):
    """PNG image -> TXP bytes with the original's header, size and (by default) palette."""
    w, h, npal, bpp, pal = header(original)
    img = img.convert("RGBA")
    if img.size != (w, h):
        raise ValueError(f"image is {img.size}, the texture is {(w, h)}")
    if new_palette:
        q = img.quantize(colors=npal, method=Image.Quantize.FASTOCTREE)
        raw = q.getpalette(rawmode="RGBA") or []
        pal = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)][:npal]
        pal += [(0, 0, 0, 0)] * (npal - len(pal))
        idx = list(q.getdata())
    else:
        index = _nearest(pal)
        idx = [index(c) for c in img.getdata()]
    row_bytes = w * bpp // 8
    if bpp == 4:
        packed = bytes(idx[i] | (idx[i + 1] << 4) for i in range(0, len(idx), 2))
    else:
        packed = bytes(idx)
    body_start = 0x10 + npal * 4
    old_px = original[body_start:]
    area = row_bytes * (h // 8 * 8)
    sw = swizzle(packed[:area].ljust(area, b"\0"), row_bytes, h // 8 * 8)
    out = bytearray(original[:0x10])
    out += b"".join(bytes(c) for c in pal)
    out += sw + old_px[len(sw):]
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decode")
    d.add_argument("txp")
    d.add_argument("png")
    e = sub.add_parser("encode")
    e.add_argument("png")
    e.add_argument("original")
    e.add_argument("out")
    e.add_argument("--new-palette", action="store_true")
    a = ap.parse_args()
    if a.cmd == "decode":
        with open(a.txp, "rb") as f:
            read_txp(f.read()).save(a.png)
    else:
        with open(a.original, "rb") as f:
            original = f.read()
        with open(a.out, "wb") as f:
            f.write(write_txp(Image.open(a.png), original, a.new_palette))


if __name__ == "__main__":
    sys.exit(main())
