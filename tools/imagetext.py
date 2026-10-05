"""Re-letter text baked into textures, from a declarative spec.

  python tools/imagetext.py preview <original.iso> [--spec translation/images.json] [--out work/images/preview]
  python tools/imagetext.py export <original.iso> [--out work/images/export] [--art]

translation/images.json lists textures and the labels to replace:

  [{"texture": "DATA.DAT/OPTION.dat/optionElements00.txp",
    "labels": [{"rect": [13, 193, 62, 214], "text": "Read Only", "size": 12}, ...]}]

"texture" is the path through the ISO's archives (archive in USRDIR / nested pack /
file; "anm0304.dat#0.2" is texture 0.2 of an anm file, see tools/anm.py). Each label's
rect [x0, y0, x1, y1] is erased to transparent (or to "erase": "#rrggbbaa",
or "erase": "extend" to repeat the column left of the rect, for text on an opaque bar, or
"erase": "clean" to fill each column with its lightest pixel, for dark text on a gradient,
or "erase": "median" for text on a patterned bar, or "erase": "interp" to blend each column
from the rect's top row to its bottom row, when those rows are clear of text)
and the English is drawn centred in it, at "size" px (default: the rect height minus
4), in "fill"/"outline" colours (default: sampled from the original pixels in the rect -
the lightest and the darkest opaque colours; "outline": "#00000000" for none). "rotate": 270
runs the text top to bottom (90: bottom to top), for vertical labels. Glyphs come from the game's own FontA
(START.DAT), so nothing but the spec is committed. "align": "left" draws from x0.
"erase": "smooth" relaxes the rect from its border inwards (soft art and skies),
"erase": "none" draws without erasing, "erase": "dark" clears only dark ink. "text": "" only erases. "boost": 2 makes the fill solid (FontA strokes are partly
transparent, which washes a coloured fill out over a light outline).

`preview` writes before/after PNGs so a label can be checked without a build.
"""
import argparse
import json
import os
import struct
import sys

from PIL import Image, ImageFilter

import anm
import game
import nispack
import txp

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
USRDIR = "/PSP_GAME/USRDIR/"
CELL = 18          # FontA cell size; 16 cells a row in each 288 px page


class Font:
    """FontA ASCII glyphs from START.DAT: page FontA000.txp, index = code - 0x20."""

    def __init__(self, start_files):
        self.page = txp.read_txp(start_files["FontA000.txp"])
        self.ftd = start_files["fontA.ftd"]

    def glyph(self, ch):
        k = ord(ch) - 0x20
        if not 0 <= k < 95:
            raise ValueError(f"no glyph for {ch!r}")
        x, y = (k % 16) * CELL, (k // 16) * CELL
        lb, rb = struct.unpack_from("bb", self.ftd, 2 + 2 * k)
        return self.page.crop((x, y, x + CELL, y + CELL)), lb, rb

    def mask(self, text, spacing=1):
        """-> L-mode alpha mask of text at the font's native 18 px cell height."""
        parts, width = [], 0
        for ch in text:
            if ch == " ":
                width += 5
                continue
            g, lb, rb = self.glyph(ch)
            ink = g.crop((lb, 0, CELL - rb, CELL))
            parts.append((width, ink))
            width += ink.width + spacing
        out = Image.new("L", (max(1, width - spacing), CELL))
        for x, ink in parts:
            out.paste(ink.getchannel("A"), (x, 0), ink.getchannel("A"))
        return out


def parse_colour(s):
    s = s.lstrip("#")
    if len(s) == 6:
        s += "ff"
    return tuple(int(s[i:i + 2], 16) for i in range(0, 8, 2))


def sample_colours(img, rect):
    """Lightest and darkest clearly opaque colours in rect (the text and its outline)."""
    px = [c for c in img.crop(rect).getdata() if c[3] > 200]
    if not px:
        return (255, 255, 255, 255), (0, 0, 0, 255)
    lum = lambda c: c[0] * 299 + c[1] * 587 + c[2] * 114
    return max(px, key=lum), min(px, key=lum)


def render_label(img, label, font):
    x0, y0, x1, y1 = label["rect"]
    x1, y1 = min(x1, img.width), min(y1, img.height)     # sprite rects may overhang
    fill, outline = sample_colours(img, (x0, y0, x1, y1))
    if "fill" in label:
        fill = parse_colour(label["fill"])
    if "outline" in label:
        outline = parse_colour(label["outline"])
    erase = label.get("erase", "#00000000")
    if erase == "extend":       # opaque bars: repeat the column just left of the rect
        for y in range(y0, y1):
            c = img.getpixel((x0 - 1, y))
            for x in range(x0, x1):
                img.putpixel((x, y), c)
    elif erase == "none":       # draw over what is there (after an erase-only label)
        pass
    elif erase == "dark":       # clear dark ink, keep light ornaments around it
        for y in range(y0, y1):
            for x in range(x0, x1):
                c = img.getpixel((x, y))
                if c[3] and c[0] * 299 + c[1] * 587 + c[2] * 114 < 200000:
                    img.putpixel((x, y), (0, 0, 0, 0))
    elif erase == "smooth":     # fill from the border inwards (Laplace relaxation), for soft art
        import numpy as np
        a = np.asarray(img, dtype=np.float32).copy()
        top, bot = a[y0 - 1, x0:x1].copy(), a[y1, x0:x1].copy()
        for k in range(y1 - y0):                       # start from the vertical blend
            t = (k + 1) / (y1 - y0 + 1)
            a[y0 + k, x0:x1] = top * (1 - t) + bot * t
        for _ in range(400):
            a[y0:y1, x0:x1] = (a[y0 - 1:y1 - 1, x0:x1] + a[y0 + 1:y1 + 1, x0:x1]
                               + a[y0:y1, x0 - 1:x1 - 1] + a[y0:y1, x0 + 1:x1 + 1]) / 4
        img.paste(Image.fromarray(np.clip(a[y0:y1, x0:x1] + 0.5, 0, 255).astype("uint8"), "RGBA"),
                  (x0, y0))
    elif erase == "interp":     # per column, blend from the rect's top row to its bottom row
        for x in range(x0, x1):
            a, b = img.getpixel((x, y0)), img.getpixel((x, y1 - 1))
            n = max(1, y1 - 1 - y0)
            for y in range(y0, y1):
                t = (y - y0) / n
                img.putpixel((x, y), tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(4)))
    elif erase == "median":     # text on a patterned bar: per column, the quartile away from the text
        lum = lambda c: c[0] * 299 + c[1] * 587 + c[2] * 114
        pick = 0.25 if lum(fill) > 128000 else 0.75
        for x in range(x0, x1):
            col = sorted((img.getpixel((x, y)) for y in range(y0, y1)), key=lum)
            c = col[int(len(col) * pick)]
            for y in range(y0, y1):
                img.putpixel((x, y), c)
    elif erase == "clean":      # dark text on a light horizontal gradient: lightest per column
        lum = lambda c: c[0] * 299 + c[1] * 587 + c[2] * 114
        for x in range(x0, x1):
            c = max((img.getpixel((x, y)) for y in range(y0, y1)), key=lum)
            for y in range(y0, y1):
                img.putpixel((x, y), c)
    else:
        img.paste(Image.new("RGBA", (x1 - x0, y1 - y0), parse_colour(erase)), (x0, y0))
    if not label["text"]:            # erase only
        return
    size = label.get("size", (y1 - y0) - 4)
    m = font.mask(label["text"], label.get("spacing", 1))
    rotate = label.get("rotate", 0)            # 90: reads bottom to top, 270: top to bottom
    room = (y1 - y0) if rotate in (90, 270) else (x1 - x0)
    if label.get("fit"):        # shrink until it fits along the text direction
        while size > 8 and round(m.width * size / CELL) + 2 > room:
            size -= 1
    w = max(1, round(m.width * size / CELL))
    m = m.resize((w, size), Image.LANCZOS)
    pad = 1 if outline[3] else 0
    canvas = Image.new("L", (w + 2 * pad, size + 2 * pad))
    canvas.paste(m, (pad, pad))
    ring = canvas.filter(ImageFilter.MaxFilter(3)) if pad else None
    if rotate:
        canvas = canvas.rotate(rotate, expand=True)
        ring = ring.rotate(rotate, expand=True) if ring is not None else None
    if canvas.width > x1 - x0 or canvas.height > y1 - y0:
        raise ValueError(f"{label['text']!r} is {canvas.size}, the rect is {(x1 - x0, y1 - y0)}")
    if label.get("align") == "left":
        px = x0
    else:
        px = x0 + (x1 - x0 - canvas.width) // 2
    py = y0 + (y1 - y0 - canvas.height) // 2
    if ring is not None:
        img.paste(Image.new("RGBA", canvas.size, outline), (px, py), ring)
    boost = label.get("boost", 1)       # >1: solid strokes, for a colour fill over a light outline
    if boost != 1:
        canvas = canvas.point(lambda v: min(255, round(v * boost)))
    img.paste(Image.new("RGBA", canvas.size, fill), (px, py), canvas)


def apply(txp_bytes, labels, font, new_palette=False):
    img = txp.read_txp(txp_bytes)
    for label in labels:
        render_label(img, label, font)
    return txp.write_txp(img, txp_bytes, new_palette)


def apply_anm(data, tex, labels, font):
    """anm file bytes -> the same with texture tex ("B.T") re-lettered."""
    t = anm.find(data, tex)
    img = anm.read(data, t)
    for label in labels:
        render_label(img, label, font)
    return anm.write(data, t, img)


def split_anm(parts):
    """["anm0304.dat#0.2"] -> (["anm0304.dat"], "0.2"); other paths -> (parts, None)."""
    if "#" in parts[-1]:
        name, tex = parts[-1].split("#", 1)
        return parts[:-1] + [name], tex
    return parts, None


def edit(before, ent, font):
    """Apply one spec entry to the bytes of its file (a .txp, or an anm file for #B.T)."""
    _, parts = split_path(ent["texture"])
    _, tex = split_anm(parts)
    if tex:
        return apply_anm(before, tex, ent["labels"], font)
    return apply(before, ent["labels"], font, ent.get("new_palette", False))


def dictionary_headers(dict_tr):
    """Spec entries for the dictionary page headers: dbtxNNNN.txp in DATA.DAT is the title
    of entry NNNN, 256x24, brown with a white outline, centred."""
    out = []
    for key, title in dict_tr.items():
        parts = key.split("/")
        if len(parts) == 3 and parts[2] == "t" and title:
            out.append({"texture": f"DATA.DAT/dbtx{int(parts[1]):04d}.txp",
                        "labels": [{"rect": [0, 0, 256, 24], "text": title, "size": 19, "fit": True,
                                    "fill": "#60411fff", "outline": "#fbfaf9ff"}]})
    return out


def split_path(path):
    """"DATA.DAT/OPTION.dat/x.txp" -> ("/PSP_GAME/USRDIR/DATA.DAT", ["OPTION.dat", "x.txp"])"""
    head, *rest = path.split("/")
    return USRDIR + head, rest


def read_nested(files, parts):
    data = files[parts[0]]
    for p in parts[1:]:
        data = nispack.load_bytes(data)[0][p]
    return data


def load_spec(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


ART_ONLY = ("ci", "bg")    # character sprites and backgrounds: no text, skipped by export


def walk_textures(files, prefix):
    """Yield (spec path, texture bytes) for every .txp, descending into nested NISPACKs."""
    for name in sorted(files):
        data = files[name]
        if name.lower().endswith(".txp"):
            yield f"{prefix}/{name}", data
        elif data[:7] == b"NISPACK":
            yield from walk_textures(nispack.load_bytes(data)[0], f"{prefix}/{name}")


def export(img, out, include_art=False):
    """Every texture as PNG under out/, named by its spec path, for finding baked-in text."""
    count = 0
    for arc in sorted(p for p in img.iso.files if p.startswith(USRDIR.upper()) and p.endswith(".DAT")):
        try:
            files, _ = img.archive(arc)
        except Exception:
            continue
        for path, data in walk_textures(files, arc[len(USRDIR):]):
            stem = path.rsplit("/", 1)[-1]
            if not include_art and stem.lower().startswith(ART_ONLY) and stem[2:3].isdigit():
                continue
            try:
                im = txp.read_txp(data)
            except ValueError:
                continue
            dest = os.path.join(out, *path.split("/"))[:-4] + ".png"
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            im.save(dest)
            count += 1
    return count


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["preview", "export"])
    ap.add_argument("iso")
    ap.add_argument("--spec", default=os.path.join(ROOT, "translation", "images.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "work", "images", "preview"))
    ap.add_argument("--art", action="store_true", help="export: include ci*/bg* art too")
    a = ap.parse_args()
    img = game.Image(a.iso)
    if a.cmd == "export":
        out = a.out if a.out != ap.get_default("out") else os.path.join(ROOT, "work", "images", "export")
        print(f"{export(img, out, a.art)} textures -> {out}")
        img.close()
        return
    start, _ = img.archive(USRDIR + "START.DAT")
    font = Font(start)
    os.makedirs(a.out, exist_ok=True)
    cache = {}
    for ent in load_spec(a.spec):
        archive, parts = split_path(ent["texture"])
        if archive not in cache:
            cache[archive] = img.archive(archive)[0]
        file_parts, tex = split_anm(parts)
        before = read_nested(cache[archive], file_parts)
        after = edit(before, ent, font)
        stem = ent["texture"].replace("/", "_").replace("#", "_")
        for tag, data in (("before", before), ("after", after)):
            im = anm.read(data, anm.find(data, tex)) if tex else txp.read_txp(data)
            bg = Image.new("RGBA", im.size, (40, 40, 90, 255))
            bg.alpha_composite(im)
            bg.convert("RGB").save(os.path.join(a.out, f"{stem}.{tag}.png"))
        print(ent["texture"], len(ent["labels"]), "labels")
    img.close()


if __name__ == "__main__":
    sys.exit(main())
