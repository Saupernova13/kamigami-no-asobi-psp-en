"""Build a patched English ISO from the original Japanese one.

  python tools/build.py <original.iso> <output.iso> [--translations translation/en]

Needs pspdecrypt (decrypts EBOOT.BIN) and armips (assembles asm/eboot.asm), found on PATH
or via --pspdecrypt / --armips / the PSPDECRYPT and ARMIPS environment variables.
Intermediate files go to work/build/.
"""
import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys

import dictionary
import eboot_strings
import font
import game
import imagetext
import iso as isolib
import memorial
import nispack
import prx
import quiz
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


QUIZ_LINE_PX = 320      # widest Japanese quiz line: 18 full-width glyphs + tracking
QUIZ_SPACING = 2        # the UI loops' proportional advance adds 2px per glyph


DICT_LINE_PX = 360      # dictionary text area (x 72 to the scroll bar)
DICT_SPACING = 1        # DictAdvance in asm/eboot.asm: ink width + 1
MEMORIAL_LINE_PX = 330  # Mythology Monologue text area (x 77; 20 full-width glyphs a line)


def fit_lines(text, metrics, px, spacing, field=None):
    """Word-wrap for the UI loops; with `field`, narrower until each line's pair
    encoding fits a field of that many bytes."""
    for width in range(px, 100, -10):
        out = wrap.wrap(text, metrics, width, spacing).split(chr(10))
        if field is None or all(len(encode_ui(x)) < field for x in out):
            return out
    return out


def patch_quiz(pack, tr, metrics, report):
    """QUIZ.dat bytes -> rebuilt with English from tr."""
    inner, inner_entries = nispack.load_bytes(pack)
    inner = dict(inner)
    for name in inner:
        if name.lower().endswith(".dat"):
            inner[name] = quiz.apply(
                inner[name], name, tr, encode_ui,
                lambda t: fit_lines(t, metrics, QUIZ_LINE_PX, QUIZ_SPACING, quiz.FIELD), report)
    return nispack.build(inner_entries, inner)


def patch_dictionary(pack, tr, metrics, report):
    """DICTIONARY.dat bytes -> rebuilt with English from tr."""
    inner, inner_entries = nispack.load_bytes(pack)
    inner = dict(inner)
    inner[dictionary.NAME] = dictionary.rebuild(
        inner[dictionary.NAME], tr, encode_ui,
        lambda t: fit_lines(t, metrics, DICT_LINE_PX, DICT_SPACING), report)
    return nispack.build(inner_entries, inner)


def set_nested(files, parts, data):
    """files[parts[0]] (a NISPACK when parts go deeper) with the file at parts replaced."""
    if len(parts) == 1:
        files[parts[0]] = data
        return
    inner, inner_entries = nispack.load_bytes(files[parts[0]])
    inner = dict(inner)
    set_nested(inner, parts[1:], data)
    files[parts[0]] = nispack.build(inner_entries, inner)


def image_edits(img, spec, start_files, report):
    """-> {archive path: [(parts, new texture bytes)]} for translation/images.json."""
    fnt = imagetext.Font(start_files)
    out, cache = {}, {}
    for ent in spec:
        archive, parts = imagetext.split_path(ent["texture"])
        if archive not in cache:
            cache[archive] = img.archive(archive)[0]
        before = imagetext.read_nested(cache[archive], parts)
        after = imagetext.apply(before, ent["labels"], fnt, ent.get("new_palette", False))
        out.setdefault(archive, []).append((parts, after))
        report["images"] += 1
    return out


def build_data_dat(img, quiz_tr, dict_tr, mem_tr, images, metrics, report):
    """-> {DATA.DAT path: rebuilt archive}, or {} when there is nothing to change.
    images: [(parts, texture bytes)] inside DATA.DAT."""
    if not quiz_tr and not dict_tr and not mem_tr and not images:
        return {}
    files, entries = img.archive(quiz.ARCHIVE)
    files = dict(files)
    if quiz_tr:
        files[quiz.PACK] = patch_quiz(files[quiz.PACK], quiz_tr, metrics, report)
    if dict_tr:
        files[dictionary.PACK] = patch_dictionary(files[dictionary.PACK], dict_tr, metrics, report)
    if mem_tr:
        files.update(memorial.rebuild(
            files, mem_tr, encode_ui,
            lambda t: fit_lines(t, metrics, MEMORIAL_LINE_PX, DICT_SPACING), report))
    for parts, data in images:
        set_nested(files, parts, data)
    report["units"] += len(quiz_tr) + len(dict_tr) + len(mem_tr)
    return {quiz.ARCHIVE: nispack.build(entries, files)}


def build_image_archives(img, edits, done):
    """Rebuild the other archives that only have texture edits."""
    out = {}
    for archive, items in edits.items():
        if archive in done:
            raise ValueError(f"{archive}: texture edits in an archive the script build rewrites")
        files, entries = img.archive(archive)
        files = dict(files)
        for parts, data in items:
            set_nested(files, parts, data)
        out[archive] = nispack.build(entries, files)
    return out


HALF_SPACE = bytes([0x87, 0x6E])


FORMAT_SPEC = re.compile(r"%[-+ 0#]*\d*(?:\.\d+)?[sdxXuc]|[\n\t]")


def encode_ui(text):
    """Game UI strings go through 2-byte string loops that stop at a zero byte, so ASCII is
    stored as (c, 0x01) pairs: the glyph lookup ignores the second byte of an ASCII unit.
    The space becomes the engine's 8px half space (87 6E), which its metrics special-case;
    a paired 0x20 would be measured as a full-width glyph. printf specifiers and line
    breaks stay single bytes, as in the original strings, for the code that formats them."""
    out = bytearray()
    pos = 0
    for m in list(FORMAT_SPEC.finditer(text)) + [None]:
        for ch in text[pos:m.start() if m else len(text)]:
            if ch == " ":
                out += HALF_SPACE
            elif " " < ch <= "~":
                out += bytes([ord(ch), 1])
            else:
                out += ch.encode("cp932")
        if m:
            out += m.group().encode("ascii")
            pos = m.end()
    return bytes(out)


# Free space for relocated strings: the nameplate string pool (only referenced through
# game.SPEAKER_TABLE) and the tail of the asm code cave.
NAMEPLATE_POOL = (0x089243BC, 0x089246C4)
STRING_HEAP = (0x088A7B80 + 0x280, 0x088A7B80 + 1076)
EXTRA_SEGMENT = 0x20000   # bytes added after bss for strings that outgrow their slot


def patch_nameplates(elf, names, heap, report):
    """names: {speaker id: English}. Repack every nameplate string (English where given,
    otherwise the original bytes) into the free regions, then the extra segment's heap,
    and repoint the table."""
    elf = bytearray(elf)
    table = game.speaker_table(bytes(elf))
    regions = [list(NAMEPLATE_POOL), list(STRING_HEAP), heap]
    blobs = {}
    for sid, ptr in table.items():
        en = names.get(str(sid))
        blobs[sid] = (encode_ui(en) if en is not None else game.elf_cstring(bytes(elf), ptr)) + b"\0"
    o = game.elf_off(NAMEPLATE_POOL[0])
    elf[o:game.elf_off(NAMEPLATE_POOL[1])] = bytes(NAMEPLATE_POOL[1] - NAMEPLATE_POOL[0])
    placed = {}
    va = game.SPEAKER_TABLE
    for sid in table:
        blob = blobs[sid]
        if blob not in placed:
            region = next((r for r in regions if r[1] - r[0] >= len(blob)), None)
            if region is None:
                report["eboot_too_long"].append(f"nameplates: out of room at speaker {sid}")
                return bytes(elf)
            addr = region[0]
            elf[game.elf_off(addr):game.elf_off(addr) + len(blob)] = blob
            region[0] = (addr + len(blob) + 3) & ~3
            placed[blob] = addr
        while struct.unpack_from("<I", elf, game.elf_off(va))[0] != sid:
            va += 8
        struct.pack_into("<I", elf, game.elf_off(va) + 4, placed[blob])
    return bytes(elf)


def patch_eboot_strings(elf, original, table, heap, report):
    """table: {"0xADDR": "English" | {"en": ..., "size": N}}. Strings are replaced in
    place; the room for each comes from the catalog of the original EBOOT unless the
    entry states a size (struct fields wider than the catalog can prove). Strings that
    do not fit move to heap ([next free, end], advanced here) and their references follow."""
    slots = {e["addr"]: e for e in eboot_strings.catalog(original)}
    refs = eboot_strings.references(original)
    elf = bytearray(elf)
    for addr, ent in table.items():
        if isinstance(ent, str):
            ent = {"en": ent}
        slot = slots.get(addr, {})
        size = ent.get("size", slot.get("size"))
        if size is None:
            report["eboot_too_long"].append(f"{addr}: not a known string, give a size")
            continue
        enc = slot.get("enc", "cp932")
        raw = (encode_ui(ent["en"]) if enc == "cp932" else ent["en"].encode(enc)) + b"\0"
        where = refs.get(int(addr, 16), [])
        if len(raw) > size and not where and "size" not in ent:
            size = max(size, slot.get("field", 0))        # inline record field: grow in place
        if len(raw) > size:
            if not where or heap[1] - heap[0] < len(raw):
                report["eboot_too_long"].append(f"{addr} {ent['en']!r} ({len(raw)} > {size}, "
                                                f"{'no room' if where else 'no references to move it'})")
                continue
            new = heap[0]
            heap[0] = (new + len(raw) + 3) & ~3
            o = game.elf_off(new)
            elf[o:o + len(raw)] = raw
            for ref in where:
                repoint(elf, ref, new)
            report["relocated"] += 1
            continue
        o = game.elf_off(int(addr, 16))
        elf[o:o + size] = raw + b"\0" * (size - len(raw))
    return bytes(elf)


def repoint(elf, ref, new):
    if ref[0] == "word":
        struct.pack_into("<I", elf, game.elf_off(ref[1]), new)
        return
    _, lui, lo_ins = ref
    lo_word, = struct.unpack_from("<I", elf, game.elf_off(lo_ins))
    signed = lo_word >> 26 == 0x09            # addiu sign-extends its half, ori does not
    hi = ((new + 0x8000) >> 16 if signed else new >> 16) & 0xFFFF
    lui_word, = struct.unpack_from("<I", elf, game.elf_off(lui))
    struct.pack_into("<I", elf, game.elf_off(lui), (lui_word & 0xFFFF0000) | hi)
    struct.pack_into("<I", elf, game.elf_off(lo_ins), (lo_word & 0xFFFF0000) | (new & 0xFFFF))


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
    report = {"units": 0, "overflow": [], "split": [], "eboot_too_long": [], "relocated": 0,
              "quiz_too_long": [], "dict_too_long": [], "images": 0}

    elf = decrypt_eboot(img, pspdecrypt, a.workdir)
    patched = os.path.join(a.workdir, "EBOOT.patched.ELF")
    assemble(armips, elf, patched)
    with open(patched, "rb") as f:
        eboot = f.read()
    with open(elf, "rb") as f:
        original_elf = f.read()
    eboot_tr = load_json(os.path.join(a.translations, "eboot.json"), {})
    names = eboot_tr.pop("nameplates", {})
    eboot, seg = prx.add_segment(eboot, EXTRA_SEGMENT)
    heap = [seg, seg + EXTRA_SEGMENT]
    eboot = patch_eboot_strings(eboot, original_elf, eboot_tr, heap, report)
    eboot = patch_nameplates(eboot, names, heap, report)

    start_files, _ = img.archive("/PSP_GAME/USRDIR/START.DAT")
    metrics = font.Metrics(start_files["fontA.ftd"])
    translations = {tag: load_json(os.path.join(a.translations, f"{tag}.json"), {}) for tag in game.STORY_FILES}
    archives = build_scripts(img, translations, metrics, report)
    images = image_edits(img, imagetext.load_spec(os.path.join(a.translations, "..", "images.json")),
                         start_files, report)
    archives.update(build_data_dat(img, load_json(os.path.join(a.translations, "quiz.json"), {}),
                                   load_json(os.path.join(a.translations, "dictionary.json"), {}),
                                   load_json(os.path.join(a.translations, "memorial.json"), {}),
                                   images.pop(quiz.ARCHIVE, []), metrics, report))
    archives.update(build_image_archives(img, images, set(archives)))
    img.close()

    shutil.copyfile(a.iso, a.out)
    out = isolib.Iso(a.out, writable=True)
    out.replace(game.EBOOT, eboot)
    for path, data in archives.items():
        out.replace(path, data)
    out.close()

    print(f"wrote {a.out}: {report['units']} script units applied, "
          f"{len(report['split'])} long pages continued in a second window")
    overflow_path = os.path.join(a.workdir, "overflow.txt")
    if os.path.exists(overflow_path):
        os.remove(overflow_path)              # never leave a list from an earlier build
    if report["overflow"]:
        print(f"  {len(report['overflow'])} lines wider than {MAX_LINE_PX}px "
              f"(listed in {a.workdir}/overflow.txt)")
        with open(overflow_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report["overflow"]) + "\n")
    if report["images"]:
        print(f"  {report['images']} textures re-lettered")
    if report["relocated"]:
        print(f"  {report['relocated']} EBOOT strings moved to the extra segment")
    for uid in report["quiz_too_long"] + report["dict_too_long"]:
        print("  text cut to fit:", uid)
    for line in report["eboot_too_long"]:
        print("  EBOOT string too long:", line)


if __name__ == "__main__":
    sys.exit(main())
