"""Merge edited English into a translation file.

  python tools/apply_edits.py <tag> <edits.json> [--text work/text]

edits.json is {"unit id": "English", ...} (any subset of units). Units are written back
in the Japanese file's order, so diffs stay small and edits from different people merge.
Unknown ids are refused. Run tools/check.py on the result before committing.
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
    ap.add_argument("edits")
    ap.add_argument("--text", default=os.path.join(ROOT, "work", "text"))
    a = ap.parse_args()
    with open(os.path.join(a.text, f"{a.tag}.json"), encoding="utf-8") as f:
        order = [u["id"] for u in json.load(f)]
    path = os.path.join(ROOT, "translation", "en", f"{a.tag}.json")
    tr = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            tr = json.load(f)
    with open(a.edits, encoding="utf-8") as f:
        edits = json.load(f)
    unknown = [k for k in edits if k not in set(order)]
    if unknown:
        sys.exit(f"unknown unit ids: {unknown[:5]}")
    changed = sum(1 for k, v in edits.items() if tr.get(k) != v)
    tr.update(edits)
    out = {k: tr[k] for k in order if k in tr}
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{a.tag}: {changed} units changed, {len(out)} in file")


if __name__ == "__main__":
    sys.exit(main())
