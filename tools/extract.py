"""Dump every translatable script unit from the original ISO to JSON.

  python tools/extract.py <original.iso> [--out work/text]

Writes <out>/<tag>.json per script (00 = common route, 02-08 = character routes):
  [{"id": "10001/p3", "kind": "page", "speaker": 4, "jp": "..."}, ...]
in play order within each scene. These files hold the Japanese script and stay local
(work/ is not committed); translations are keyed by the same ids.
"""
import argparse
import json
import os
import sys

import game
import script_text


def units_for(st):
    for sc in st.scenes:
        pages = {pg.start: pg for pg in script_text.find_pages(sc.instrs)}
        speakers = [sc.instrs[k].arg0 for k in sorted(pages)]
        si = 0
        for uid, kind, jp in script_text.scene_units(sc.sid, sc.instrs):
            u = {"id": uid, "kind": kind, "jp": jp}
            if kind == "page":
                u["speaker"] = speakers[si]
                si += 1
            yield u


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("iso")
    ap.add_argument("--out", default="work/text")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    img = game.Image(a.iso)
    total = 0
    for tag in game.STORY_FILES:
        units = list(units_for(img.story(tag)))
        total += len(units)
        with open(os.path.join(a.out, f"{tag}.json"), "w", encoding="utf-8") as f:
            json.dump(units, f, ensure_ascii=False, indent=1)
        print(f"{tag}: {len(units)} units")
    img.close()
    print(f"total {total}")


if __name__ == "__main__":
    sys.exit(main())
