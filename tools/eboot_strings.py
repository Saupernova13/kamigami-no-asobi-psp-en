"""Catalog the Japanese strings in the decrypted EBOOT's data area.

  python tools/eboot_strings.py <EBOOT.ELF> [--out work/text/eboot.json]

Each entry: {"addr": "0x088dc4f4", "jp": "...", "size": N, "enc": "cp932" | "utf-8"}.
Game text is Shift-JIS; the PSP system dialog messages are UTF-8. `size` is the room a
replacement may use in place: the original bytes plus any alignment padding that runs
straight into the next string. Padding that ends anywhere else might be a struct field,
so it is not counted. `field` is set when the string looks like a fixed char array in a
record (zeros run on to a 16/32/64-byte boundary): the room a string nothing points to
can use, since it cannot be moved.
"""
import argparse
import json
import struct
import re
import sys

import game

DATA_START = 0x08804000 + 0x11EF7C   # end of .text in the static EBOOT
SJIS_STR = re.compile(rb"(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x09\x0a\x20-\x7e]){2,}\x00")
UTF8_STR = re.compile(rb"(?:[\xe2-\xe9][\x80-\xbf]{2}|\xef[\xbc-\xbd][\x80-\xbf]|[\x09\x0a\x20-\x7e]){4,}\x00")
JP = re.compile(r"[぀-ヿ一-鿿]")
FULLWIDTH_WORD = re.compile(r"[Ａ-Ｚａ-ｚ]{2,}")
ALLOWED = re.compile(r"^[\t\n　-ヿ一-鿿！-ﾟ‐-⌒㈱-㏿™ -~]+$")


def _plausible(text):
    if not ALLOWED.match(text):
        return False
    jp = len(JP.findall(text))
    if len(text) <= 5 and re.search(r"[!-~]", text):
        return False   # a couple of kanji next to ASCII punctuation: binary data
    return jp >= 2 or (jp >= 1 and len(text) <= 4) or bool(FULLWIDTH_WORD.search(text))


def _scan(elf, pattern, enc):
    start = game.elf_off(DATA_START)
    for m in pattern.finditer(elf, start):
        if m.start() % 4:
            continue
        raw = m.group()[:-1]
        if not any(b >= 0x80 for b in raw):
            continue
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if _plausible(text):
            yield m.start(), text, len(raw), enc


def catalog(elf):
    found = {}
    for off, text, n, enc in list(_scan(elf, UTF8_STR, "utf-8")) + list(_scan(elf, SJIS_STR, "cp932")):
        found.setdefault(off, (text, n, enc))
    offs = sorted(found)
    out = []
    for i, off in enumerate(offs):
        text, n, enc = found[off]
        size = n + 1
        nxt = offs[i + 1] if i + 1 < len(offs) else None
        if nxt is not None and nxt - (off + n + 1) < 4 and not any(elf[off + n + 1:nxt]):
            size = nxt - off
        ent = {"addr": f"{off + game.ELF_BASE:#010x}", "jp": text, "size": size, "enc": enc}
        field = _field(elf, off, n)
        if field > size:
            ent["field"] = field
        out.append(ent)
    return out


def _field(elf, off, n):
    """Largest of 16/32/64 bytes that the string plus the zeros after it fill."""
    end = off + n
    limit = min(off + 64, len(elf))
    while end < limit and elf[end] == 0:
        end += 1
    return max((f for f in (16, 32, 64) if f <= end - off), default=0)


CODE_END = 0x08804000 + 0x11EF7C


def references(elf):
    """-> {address: [("word", va) | ("hilo", lui_va, addiu_va), ...]} for every word in the
    image and every lui/addiu (or lui/ori) pair that forms an address. A pair is only
    reported when it can be repointed alone: the addiu writes back into the lui register
    and nothing reads that register in between."""
    first = game.elf_off(0x08804000)
    n = (len(elf) - first) // 4
    words = struct.unpack_from(f"<{n}I", elf, first)
    refs = {}
    for i, w in enumerate(words):
        refs.setdefault(w, []).append(("word", 0x08804000 + i * 4))
    ncode = (CODE_END - 0x08804000) // 4
    for i in range(ncode):
        w = words[i]
        op = w >> 26
        if op not in (0x09, 0x0D):
            continue
        rs, rt, lo = (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
        if rs != rt or rs == 0:
            continue
        for k in range(i - 1, max(-1, i - 24), -1):
            v = words[k]
            if v >> 26 == 0x0F and (v >> 16) & 31 == rs:
                if any(_reads(words[j], rs) for j in range(k + 1, i)):
                    break
                lo_s = lo - 0x10000 if (lo & 0x8000 and op == 0x09) else lo
                addr = (((v & 0xFFFF) << 16) + lo_s) & 0xFFFFFFFF
                refs.setdefault(addr, []).append(("hilo", 0x08804000 + k * 4, 0x08804000 + i * 4))
                break
            if _writes(v, rs):
                break
    return refs


def _reads(w, r):
    op = w >> 26
    rs, rt = (w >> 21) & 31, (w >> 16) & 31
    if op == 0:
        return r in (rs, rt)
    return rs == r or (op in (0x04, 0x05, 0x28, 0x29, 0x2B) and rt == r)


def _writes(w, r):
    op = w >> 26
    if op == 0:
        return (w >> 11) & 31 == r
    return op not in (0x02, 0x03, 0x04, 0x05, 0x28, 0x29, 0x2B) and (w >> 16) & 31 == r


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("elf")
    ap.add_argument("--out", default="work/text/eboot.json")
    a = ap.parse_args()
    with open(a.elf, "rb") as f:
        elf = f.read()
    cat = catalog(elf)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)
    print(f"{len(cat)} strings -> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
