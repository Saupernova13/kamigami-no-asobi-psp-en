"""Mythology Monologue stories: memorial0001.dat ... memorial0117.dat in DATA.DAT.

  python tools/memorial.py <original.iso> [--out work/text/memorial.json]

Each file uses the dictionary's entry layout (see tools/dictionary.py): an offset table,
then entries with a title (e.g. a Garden event name in 『』) and inverted-SJIS lines,
pre-broken at about 20 full-width characters, paragraphs separated by empty lines. The
screen draws them with FUN_088233c4 (x 77, 19 px a line), which inserts the player's
nickname, surname and given name for 87 6B / 87 6C / 87 6D.

Units: "mem/0002/2/t" (title) and "mem/0002/2/p0".. (paragraphs) - file number, entry id.
"""
import argparse
import json
import os
import re
import sys

import dictionary
import game

ARCHIVE = "/PSP_GAME/USRDIR/DATA.DAT"
FILE = re.compile(r"memorial(\d{4})\.dat$")


def files(archive_files):
    """-> [(number, name)] of the story files (memorial0001-0015.dat is an empty index)."""
    return sorted((m.group(1), n) for n in archive_files if (m := FILE.match(n)))


def units_for(archive_files):
    for num, name in files(archive_files):
        yield from dictionary.units_for(archive_files[name], prefix=f"mem/{num}", kind="mem")


def rebuild(archive_files, tr, encode, wrap_lines, report):
    """-> {name: new bytes} for files that have English in tr."""
    out = {}
    for num, name in files(archive_files):
        prefix = f"mem/{num}"
        if any(k.startswith(prefix + "/") for k in tr):
            out[name] = dictionary.rebuild(archive_files[name], tr, encode, wrap_lines, report,
                                           prefix=prefix)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("iso")
    ap.add_argument("--out", default=os.path.join("work", "text", "memorial.json"))
    a = ap.parse_args()
    img = game.Image(a.iso)
    archive_files, _ = img.archive(ARCHIVE)
    units = list(units_for(archive_files))
    img.close()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(units, f, ensure_ascii=False, indent=1)
    print(f"{len(units)} memorial units -> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
