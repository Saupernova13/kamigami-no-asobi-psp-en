"""Dictionary entries: DICTIONARY.dat inside DATA.DAT.

  python tools/dictionary.py <original.iso> [--out work/text/dictionary.json]

dictionary.dat: u32 count, count x {u32 entry id, u32 offset}, then the entries:
  u32 category, s16 item count (always 1), s16 line count
  title: inverted SJIS (each byte XOR 0xFF), zero-padded, 64 bytes at +8
  one 20-byte item at +0x48 (constant here), copied as it is
  lines from +0x5c: inverted SJIS, each ending in a zero byte (an empty line is a lone
  zero); the first is always empty, and some entries end with extra empty lines. The
  line count covers all of them and drives the scroll bar (FUN_088140e0: 22 px a line)
  zero padding to a multiple of 4
  zero padding to a multiple of 4
Body lines are pre-broken at about 24 full-width characters; a line starting with
"■" is a section heading. "㌫" (87 6C) and "㍊" (87 6D) are markers the renderer (FUN_08813e58) replaces with
the player's surname and given name; units carry them as 草薙 and {NAME}.

Units: "dict/<id>/t" (title), "dict/<id>/h<n>" (headings), "dict/<id>/p<n>" (paragraphs:
the lines between headings and blank lines, joined).
"""
import argparse
import json
import os
import struct
import sys

import game
import nispack

ARCHIVE = "/PSP_GAME/USRDIR/DATA.DAT"
PACK = "DICTIONARY.dat"
NAME = "dictionary.dat"
TITLE_START, TITLE_END = 8, 0x48            # 64-byte title field
FIXED_AT = 0x4E
FIXED = bytes.fromhex("e001600000000000e0016000000000")
BODY_START = FIXED_AT + len(FIXED)
NICK_MARK = "\u3323"            # 87 6B: the renderer inserts the player's nickname,
SURNAME_MARK = "\u332b"         # 87 6C: ... surname
NAME_MARK = "\u334a"            # 87 6D: ... and given name
MARKS = {NICK_MARK: "{NICK}", SURNAME_MARK: "\u8349\u8599", NAME_MARK: "{NAME}"}


def invert(raw):
    return bytes(b ^ 0xFF for b in raw)


def entries(data):
    n, = struct.unpack_from("<I", data, 0)
    table = [struct.unpack_from("<II", data, 4 + i * 8) for i in range(n)]
    out = []
    for k, (eid, off) in enumerate(table):
        end = table[k + 1][1] if k + 1 < n else len(data)
        out.append((eid, data[off:end]))
    return out


def parse(rec):
    """-> (category, title, body lines)"""
    cat, one = struct.unpack_from("<IH", rec, 0)
    if one != 1 or rec[FIXED_AT:BODY_START] != FIXED:
        raise ValueError("unexpected dictionary entry layout")
    title = invert(rec[TITLE_START:TITLE_END].split(b"\0", 1)[0]).decode("cp932")
    body = rec[BODY_START:].rstrip(b"\0").split(b"\0")
    lines = [invert(x).decode("cp932") for x in body]
    return cat, title, lines


def trailing_zeros(rec):
    return len(rec) - len(rec.rstrip(bytes(1)))


def blocks(lines):
    """Group body lines: [(kind, original lines)], kind "h" (heading), "p" (paragraph)
    or "blank"."""
    out = []
    for line in lines:
        if not line:
            out.append(("blank", [line]))
        elif line.startswith("■"):
            out.append(("h", [line]))
        elif out and out[-1][0] == "p":
            out[-1][1].append(line)
        else:
            out.append(("p", [line]))
    return out


def unmark(text):
    for mark, token in MARKS.items():
        text = text.replace(mark, token)
    return text


def units_for(data, prefix="dict", kind="dict"):
    """Units of one file of entries. The memorial stories use the same layout with
    prefix "mem/<file number>" and kind "mem"."""
    for eid, rec in entries(data):
        _, title, lines = parse(rec)
        yield {"id": f"{prefix}/{eid}/t", "kind": f"{kind}_title", "jp": unmark(title)}
        nh = np_ = 0
        for k, block in blocks(lines):
            if k == "h":
                yield {"id": f"{prefix}/{eid}/h{nh}", "kind": f"{kind}_heading", "jp": block[0]}
                nh += 1
            elif k == "p":
                yield {"id": f"{prefix}/{eid}/p{np_}", "kind": f"{kind}_text",
                       "jp": unmark("".join(block))}
                np_ += 1


def encode_line(text, encode):
    # the surname slot holds three characters, so it is written out; the given name and
    # nickname stay markers the renderer fills in
    text = (text.replace("{SURNAME}", "Kusanagi").replace("{NAME}", NAME_MARK)
            .replace("{NICK}", NICK_MARK))
    return invert(encode(text)) + b"\0"


def rebuild(data, tr, encode, wrap_lines, report, prefix="dict"):
    """New file with English from tr; entries without English keep their bytes."""
    recs = []
    for eid, rec in entries(data):
        old = rec
        cat, title, lines = parse(rec)
        t = tr.get(f"{prefix}/{eid}/t")
        if not any(k.startswith(f"{prefix}/{eid}/") for k in tr):
            recs.append((eid, rec))
            continue
        head = bytearray(rec[:BODY_START])
        if t:
            raw = invert(encode(t))
            if len(raw) >= TITLE_END - TITLE_START:
                report["dict_too_long"].append(f"{prefix}/{eid}/t")
                raw = raw[:TITLE_END - TITLE_START - 2]
            head[TITLE_START:TITLE_END] = raw + bytes(TITLE_END - TITLE_START - len(raw))
        out_lines = []
        nh = np_ = 0
        for kind, block in blocks(lines):
            if kind == "blank":
                out_lines.append("")
            elif kind == "h":
                out_lines.append(tr.get(f"{prefix}/{eid}/h{nh}") or block[0])
                nh += 1
            else:
                en = tr.get(f"{prefix}/{eid}/p{np_}")
                out_lines += wrap_lines(en) if en else block
                np_ += 1
        count, = struct.unpack_from("<H", rec, 6)
        struct.pack_into("<H", head, 6, count - len(lines) + len(out_lines))
        body = b"".join(encode_line(x, encode) if x else b"\0" for x in out_lines)
        rec = bytes(head) + body
        rec += bytes(trailing_zeros(old) - 1)   # some entries end in extra empty lines
        rec += bytes(-len(rec) % 4)
        recs.append((eid, rec))
    table = bytearray(struct.pack("<I", len(recs)))
    pos = 4 + 8 * len(recs)
    for eid, rec in recs:
        table += struct.pack("<II", eid, pos)
        pos += len(rec)
    return bytes(table) + b"".join(rec for _, rec in recs)


def load(img):
    files, entries_ = img.archive(ARCHIVE)
    inner, inner_entries = nispack.load_bytes(files[PACK])
    return files, entries_, inner, inner_entries


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("iso")
    ap.add_argument("--out", default=os.path.join("work", "text", "dictionary.json"))
    a = ap.parse_args()
    img = game.Image(a.iso)
    _, _, inner, _ = load(img)
    units = list(units_for(inner[NAME]))
    img.close()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(units, f, ensure_ascii=False, indent=1)
    print(f"{len(units)} dictionary units -> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
