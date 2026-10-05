"""Chapter titles: NN_Selecter.dat in TITLE01.DAT ... TITLE11.DAT.

  python tools/selecter.py <original.iso> [--out work/text/selecter.json]

Each file: u32 count, count x u32 offset, then records of 0x70 bytes. A record starts
with the title, inverted SJIS (each byte XOR 0xFF) zero-padded to 64 bytes, then a
16-byte field (always 無, "none") and numbers. TITLE04-11 hold the chapter titles of
each route (the card that types the title under "Prologue", "Chapter 1"...), in the
order of the chapter select title images; TITLE01-03 name the routes. Records titled
無 are unused slots and are not extracted.

Units: "sel/04/1" - TITLE04, record 1. English is stored as (c, 0x01) pairs like other
UI text, so a title holds 31 characters.
"""
import argparse
import json
import os
import struct
import sys

import game

TITLE = 0x40           # bytes in the title field
UNUSED = "無"


def path(num):
    return f"/PSP_GAME/USRDIR/TITLE{num}.DAT", f"{num}_Selecter.dat"


def records(data):
    n, = struct.unpack_from("<I", data, 0)
    return list(struct.unpack_from(f"<{n}I", data, 4))


def invert(raw):
    return bytes(b ^ 0xFF for b in raw)


def title_at(data, off):
    return invert(data[off:off + TITLE].split(b"\0")[0]).decode("cp932")


def units_for(img):
    for i in range(1, 12):
        num = f"{i:02d}"
        arc, name = path(num)
        data = img.archive(arc)[0][name]
        for k, off in enumerate(records(data)):
            jp = title_at(data, off)
            if jp and jp != UNUSED:
                yield {"id": f"sel/{num}/{k}", "kind": "sel_title", "jp": jp}


def rebuild(data, num, tr, encode, report):
    """-> NN_Selecter.dat bytes with English titles from tr."""
    out = bytearray(data)
    for k, off in enumerate(records(data)):
        en = tr.get(f"sel/{num}/{k}")
        if not en:
            continue
        raw = encode(en)
        if len(raw) >= TITLE:
            report["quiz_too_long"].append(f"selecter:sel/{num}/{k}")
            raw = raw[:TITLE - 2]
        out[off:off + TITLE] = invert(raw) + b"\0" * (TITLE - len(raw))
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("iso")
    ap.add_argument("--out", default=os.path.join("work", "text", "selecter.json"))
    a = ap.parse_args()
    img = game.Image(a.iso)
    units = list(units_for(img))
    img.close()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(units, f, ensure_ascii=False, indent=1)
    print(f"{len(units)} chapter titles -> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
