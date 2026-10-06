"""Test only: copy a built ISO and send the first route branch to another route.

  python tools/routeiso.py <english.iso> <out.iso> <route>

The common route ends in scenes 40512-40522 of 03_Story.dat, each with an op 0x63 of
subtype 7: (7, flag, route start scene, route index). Which one runs depends on flags
set by earlier choices, and `tools/autoplay.py` always reaches the Apollon branch
(40512). This rewrites that branch so the same autoplay run continues into another
route, which is how every route is checked in the emulator. Never ship the result.

Routes: apollon hades tsukito takeru balder loki anubis thoth.
"""
import argparse
import shutil
import struct
import sys

import game
import iso as isolib
import nispack

ROUTES = {"apollon": (50001, 0), "hades": (60001, 1), "tsukito": (70001, 2),
          "takeru": (80001, 3), "balder": (90001, 4), "loki": (100001, 5),
          "anubis": (110001, 6), "thoth": (120001, 7)}
BRANCH_SCENE = 40512


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("iso")
    ap.add_argument("out")
    ap.add_argument("route", choices=sorted(ROUTES))
    a = ap.parse_args()
    scene, index = ROUTES[a.route]
    shutil.copyfile(a.iso, a.out)
    img = game.Image(a.out)
    st = img.story("03")
    done = False
    for sc in st.scenes:
        if sc.sid != BRANCH_SCENE:
            continue
        for ins in sc.instrs:
            if ins.op == 0x63 and len(ins.args) >= 16 and struct.unpack_from("<I", ins.args)[0] == 7:
                kind, flag, _, _ = struct.unpack_from("<4I", ins.args)
                ins.args = struct.pack("<4I", kind, flag, scene, index) + ins.args[16:]
                done = True
    if not done:
        sys.exit(f"no route branch found in scene {BRANCH_SCENE}")
    arc, name = game.STORY_FILES["03"]
    files, entries = img.archive(arc)
    files = dict(files)
    files[name] = st.build()
    data = nispack.build(entries, files)
    img.close()
    out = isolib.Iso(a.out, writable=True)
    out.replace(arc, data)
    out.close()
    print(f"{a.out}: the first route branch now starts {a.route} (scene {scene})")


if __name__ == "__main__":
    sys.exit(main())
