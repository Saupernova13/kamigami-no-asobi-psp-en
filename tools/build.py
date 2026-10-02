"""Build a patched English ISO from the original Japanese one.

  python tools/build.py <original.iso> <output.iso> [--translations translation/en]

Needs pspdecrypt (decrypts EBOOT.BIN) and armips (assembles asm/eboot.asm), found on PATH
or via --pspdecrypt / --armips / the PSPDECRYPT and ARMIPS environment variables.
Intermediate files go to work/build/.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import eboot_strings
import font
import game
import iso as isolib
import nispack
import prx
import script_text
import story
import wrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MAX_LINE_PX = 390       # message window text area, measured in the emulator
MAX_LINES = 3
LETTER_SPACING = 1      # matches LETTER_SPACING in asm/eboot.asm


def find_tool(name, override, env):
    for cand in (override, os.environ.get(env), shutil.which(name), shutil.which(name + ".exe")):
        if cand and os.path.isfile(cand):
            return cand
    sys.exit(f"{name} not found: put it on PATH, set {env}, or pass --{name}")


def decrypt_eboot(img, pspdecrypt, workdir):
    enc = os.path.join(workdir, "EBOOT.BIN")
    elf = os.path.join(workdir, "EBOOT.ELF")
    if not os.path.exists(elf):
        with open(enc, "wb") as f:
            f.write(img.file(game.EBOOT))
        prx_path = os.path.join(workdir, "EBOOT.PRX")
        subprocess.run([pspdecrypt, enc, "-o", prx_path], check=True, capture_output=True)
        with open(prx_path, "rb") as f:
            static, _ = prx.to_static(f.read())
        with open(elf, "wb") as f:
            f.write(static)
    return elf


def assemble(armips, elf, out):
    subprocess.run([armips, os.path.join(ROOT, "asm", "eboot.asm"),
                    "-strequ", "IN", os.path.abspath(elf), "-strequ", "OUT", os.path.abspath(out)],
                   check=True, cwd=ROOT)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def layout_page(markup, metrics, report, uid):
    """Wrap to the window and continue in extra windows (\\f) past MAX_LINES lines.
    Markup that already contains line breaks is taken as laid out by hand."""
    windows = []
    for segment in markup.split("\f"):
        text = segment if "\n" in segment else wrap.wrap(segment, metrics, MAX_LINE_PX, LETTER_SPACING)
        lines = text.split("\n")
        if max(wrap.line_widths(text, metrics, LETTER_SPACING)) > MAX_LINE_PX:
            report["overflow"].append(uid)
        n = -(-len(lines) // MAX_LINES)          # windows needed, then spread lines evenly
        per = -(-len(lines) // n)
        windows += ["\n".join(lines[i:i + per]) for i in range(0, len(lines), per)]
    if len(windows) > 1:
        report["split"].append(uid)
    return "\f".join(windows)


def build_scripts(img, translations, metrics, report):
    """-> {archive path in ISO: rebuilt archive bytes}"""
    out = {}
    for tag, (arc, name) in game.STORY_FILES.items():
        tr = translations.get(tag, {})
        if not tr:
            continue
        st = img.story(tag)
        laid = {}
        for uid, en in tr.items():
            if not en:
                continue
            laid[uid] = layout_page(en, metrics, report, f"{tag}:{uid}") if "/p" in uid else en
        for sc in st.scenes:
            sc.instrs = script_text.apply_scene(sc.sid, sc.instrs, laid)
        files, entries = img.archive(arc)
        files = dict(files)
        files[name] = st.build()
        out[arc] = nispack.build(entries, files)
        report["units"] += len(laid)
    return out


def patch_eboot_strings(elf, original, table, report):
    """table: {"0xADDR": "English" | {"en": ..., "size": N}}. Strings are replaced in
    place; the room for each comes from the catalog of the original EBOOT unless the
    entry states a size (struct fields wider than the catalog can prove)."""
    slots = {e["addr"]: e for e in eboot_strings.catalog(original)}
    elf = bytearray(elf)
    for addr, ent in table.items():
        if isinstance(ent, str):
            ent = {"en": ent}
        slot = slots.get(addr, {})
        size = ent.get("size", slot.get("size"))
        if size is None:
            report["eboot_too_long"].append(f"{addr}: not a known string, give a size")
            continue
        raw = ent["en"].encode(slot.get("enc", "cp932")) + b"\0"
        if len(raw) > size:
            report["eboot_too_long"].append(f"{addr} {ent['en']!r} ({len(raw)} > {size})")
            continue
        o = game.elf_off(int(addr, 16))
        elf[o:o + size] = raw + b"\0" * (size - len(raw))
    return bytes(elf)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("iso")
    ap.add_argument("out")
    ap.add_argument("--translations", default=os.path.join(ROOT, "translation", "en"))
    ap.add_argument("--pspdecrypt")
    ap.add_argument("--armips")
    ap.add_argument("--workdir", default=os.path.join(ROOT, "work", "build"))
    a = ap.parse_args()
    os.makedirs(a.workdir, exist_ok=True)
    pspdecrypt = find_tool("pspdecrypt", a.pspdecrypt, "PSPDECRYPT")
    armips = find_tool("armips", a.armips, "ARMIPS")

    img = game.Image(a.iso)
    report = {"units": 0, "overflow": [], "split": [], "eboot_too_long": []}

    elf = decrypt_eboot(img, pspdecrypt, a.workdir)
    patched = os.path.join(a.workdir, "EBOOT.patched.ELF")
    assemble(armips, elf, patched)
    with open(patched, "rb") as f:
        eboot = f.read()
    with open(elf, "rb") as f:
        original_elf = f.read()
    eboot = patch_eboot_strings(eboot, original_elf, load_json(os.path.join(a.translations, "eboot.json"), {}), report)

    start_files, _ = img.archive("/PSP_GAME/USRDIR/START.DAT")
    metrics = font.Metrics(start_files["fontA.ftd"])
    translations = {tag: load_json(os.path.join(a.translations, f"{tag}.json"), {}) for tag in game.STORY_FILES}
    archives = build_scripts(img, translations, metrics, report)
    img.close()

    shutil.copyfile(a.iso, a.out)
    out = isolib.Iso(a.out, writable=True)
    out.replace(game.EBOOT, eboot)
    for path, data in archives.items():
        out.replace(path, data)
    out.close()

    print(f"wrote {a.out}: {report['units']} script units applied, "
          f"{len(report['split'])} long pages continued in a second window")
    if report["overflow"]:
        print(f"  {len(report['overflow'])} lines wider than {MAX_LINE_PX}px "
              f"(listed in {a.workdir}/overflow.txt)")
        with open(os.path.join(a.workdir, "overflow.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(report["overflow"]) + "\n")
    for line in report["eboot_too_long"]:
        print("  EBOOT string too long:", line)


if __name__ == "__main__":
    sys.exit(main())
