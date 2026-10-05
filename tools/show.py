"""Print Japanese and English side by side, for editing a scene.

  python tools/show.py <tag> [scene or unit id prefix ...] [--untranslated]

  python tools/show.py 04 50001            every unit of scene 50001
  python tools/show.py 04 50001/p1         units whose id starts with 50001/p1
  python tools/show.py quiz 4quiz02
  python tools/show.py 01 --untranslated   only units with no English yet

Speakers come from data/glossary.json. Japanese is read from work/text/<tag>.json
(made by the extractors), English from translation/en/<tag>.json.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tag")
    ap.add_argument("prefixes", nargs="*")
    ap.add_argument("--untranslated", action="store_true")
    ap.add_argument("--text", default=os.path.join(ROOT, "work", "text"))
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with open(os.path.join(a.text, f"{a.tag}.json"), encoding="utf-8") as f:
        units = json.load(f)
    tr_path = os.path.join(ROOT, "translation", "en", f"{a.tag}.json")
    tr = {}
    if os.path.exists(tr_path):
        with open(tr_path, encoding="utf-8") as f:
            tr = json.load(f)
    with open(os.path.join(ROOT, "data", "glossary.json"), encoding="utf-8") as f:
        speakers = json.load(f)["speakers"]
    for u in units:
        uid = u["id"]
        if a.prefixes and not any(uid == p or uid.startswith(p + "/")
                                  for p in a.prefixes):
            continue
        if a.untranslated and uid in tr:
            continue
        who = speakers.get(str(u.get("speaker")), u["kind"]) if "speaker" in u else u["kind"]
        print(f"[{uid}] {who}")
        print("  JP: " + u["jp"].replace("\n", " / "))
        print("  EN: " + tr.get(uid, "(none)"))


if __name__ == "__main__":
    sys.exit(main())
