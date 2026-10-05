"""Mythology quiz text: QUIZ.dat inside DATA.DAT.

  python tools/quiz.py <original.iso> [--out work/text/quiz.json]

QUIZ.dat is a NISPACK of eight files (4quiz00-03: four choices, tfquiz00-03: true or
false), each laid out as
  u32 header size (0x1a0), u32 x3 (question counts per difficulty, 15 + 20 + 15)
  50 x {u32 question id, u32 offset}
  50 x {u32 question id, char question[3][64], char choice[4][64]}
Question lines and choices are zero-padded SJIS in fixed 64-byte fields; the first
choice is the right answer. The quiz screen draws them with the 2-byte UI loops, so
English goes in as (c, 0x01) pairs (31 characters per field).

Units: {"id": "4quiz00/101/q", "kind": "quiz", "jp": "question lines joined"} and
"4quiz00/101/c0".."c3" for non-empty choices (the true/false files keep their answer key,
a circle or cross, in c0).
"""
import argparse
import json
import os
import struct
import sys

import game
import nispack

ARCHIVE = "/PSP_GAME/USRDIR/DATA.DAT"
PACK = "QUIZ.dat"
FIELD = 64
LINES, CHOICES = 3, 4
RECORD = 4 + (LINES + CHOICES) * FIELD
ANSWER_MARKS = ("○", "×")   # true/false answer keys, not text to translate


def records(data):
    """-> [(question id, record offset)]"""
    hsize, a, b, c = struct.unpack_from("<4I", data, 0)
    n = a + b + c
    if 16 + n * 8 != hsize:
        raise ValueError("unexpected quiz header")
    return [struct.unpack_from("<II", data, 16 + i * 8) for i in range(n)]


def field(data, off):
    raw = data[off:off + FIELD].split(b"\0", 1)[0]
    return raw.decode("cp932")


def units_for(name, data):
    stem = name.rsplit(".", 1)[0]
    for qid, off in records(data):
        if struct.unpack_from("<I", data, off)[0] != qid:
            raise ValueError(f"{name}: record {qid} misplaced")
        lines = [field(data, off + 4 + i * FIELD) for i in range(LINES)]
        yield {"id": f"{stem}/{qid}/q", "kind": "quiz", "jp": "".join(lines)}
        for i in range(CHOICES):
            text = field(data, off + 4 + (LINES + i) * FIELD)
            if text and text not in ANSWER_MARKS:
                yield {"id": f"{stem}/{qid}/c{i}", "kind": "quiz_choice", "jp": text}


def load(img):
    files, entries = img.archive(ARCHIVE)
    inner, inner_entries = nispack.load_bytes(files[PACK])
    return files, entries, inner, inner_entries


def apply(data, name, tr, encode, wrap_lines, report):
    """Write English from tr (unit id -> text) into one quiz file."""
    data = bytearray(data)
    stem = name.rsplit(".", 1)[0]
    for qid, off in records(bytes(data)):
        q = tr.get(f"{stem}/{qid}/q")
        if q:
            lines = wrap_lines(q)
            if len(lines) > LINES:
                report["quiz_too_long"].append(f"{stem}/{qid}/q")
                lines = lines[:LINES]
            for i in range(LINES):
                put(data, off + 4 + i * FIELD, encode(lines[i]) if i < len(lines) else b"", report,
                    f"{stem}/{qid}/q")
        for i in range(CHOICES):
            c = tr.get(f"{stem}/{qid}/c{i}")
            if c:
                put(data, off + 4 + (LINES + i) * FIELD, encode(c), report, f"{stem}/{qid}/c{i}")
    return bytes(data)


def put(data, off, raw, report, uid):
    if len(raw) >= FIELD:
        report["quiz_too_long"].append(uid)
        raw = raw[:FIELD - 2] if raw[FIELD - 2] != 1 else raw[:FIELD - 1]
        raw = raw[:len(raw) - len(raw) % 2]
    data[off:off + FIELD] = raw + bytes(FIELD - len(raw))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("iso")
    ap.add_argument("--out", default=os.path.join("work", "text", "quiz.json"))
    a = ap.parse_args()
    img = game.Image(a.iso)
    _, _, inner, _ = load(img)
    units = []
    for name in sorted(inner):
        if name.lower().endswith(".dat"):
            units += units_for(name, inner[name])
    img.close()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(units, f, ensure_ascii=False, indent=1)
    print(f"{len(units)} quiz units -> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
