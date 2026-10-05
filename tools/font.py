"""Glyph metrics for FontA (mirrors the EBOOT's advance calculation).

FontA.ftd: u16 count, then per glyph index two signed bytes (left, right bearing) in
20px-cell units. Index for a character (FUN_088672c4):
  single byte 0x20-0x7E   -> c - 0x20
  SJIS lead/trail         -> (trail - 0x40) + lead' * 0xC0 + 0x5F,
                             lead' = lead - 0x81 (0x81-0x9F) or lead - 0xC1 (0xE0-)
Advance at 100% size (FUN_088a1690): int((18 - left - right) * 16/18 + 0.5) - 18px cells
drawn at 16px; the full-width space is 16px and the ASCII space / half spaces (87 6B,
87 6E) are 8px.
"""
import os
import struct

SPECIAL = {0x8140: 16, 0x20: 8, 0x876B: 8, 0x876E: 8}


def glyph_index(code):
    """code: single byte value, or (lead << 8) | trail."""
    if code <= 0xFF:
        if 0x20 <= code <= 0x7E:
            return code - 0x20
        raise ValueError(f"unsupported single byte {code:#x}")
    lead, trail = code >> 8, code & 0xFF
    lead = lead - 0x81 if lead <= 0x9F else lead - 0xC1
    return ((trail - 0x40) & 0xFF) + lead * 0xC0 + 0x5F


def iter_codes(sjis):
    i = 0
    while i < len(sjis):
        b = sjis[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            yield (b << 8) | sjis[i + 1]
            i += 2
        else:
            yield b
            i += 1


class Metrics:
    def __init__(self, ftd_bytes):
        self.ftd = ftd_bytes

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            return cls(f.read())

    def advance(self, code):
        if code in SPECIAL:
            return SPECIAL[code]
        k = glyph_index(code)
        lb, rb = struct.unpack_from("bb", self.ftd, 2 + 2 * k)
        return int((18 - lb - rb) * 0.8888889 + 0.5)

    def width(self, text):
        if isinstance(text, str):
            text = text.encode("cp932")
        return sum(self.advance(c) for c in iter_codes(text))


def default_metrics(root):
    return Metrics.load(os.path.join(root, "FontA.ftd"))
