"""Validate translation files before building.

  python tools/check.py [files...] [--text work/text] [--iso original.iso] [--strict]

With no files, checks every translation/en/*.json that has Japanese units in work/text
(run tools/extract.py, quiz.py and dictionary.py first). Reports, per unit:

  ERROR   unknown unit id, broken or missing keyword/op token, character the game cannot
          draw, Japanese left in the English, choice over 32 characters, a
          dictionary keyword with no term
  WARN    name token dropped or added, line wider than the window after layout, text that will be
          cut, untranslated units (coverage)

Exit status is 1 when there are errors (or warnings with --strict). Fix errors before
committing; warnings are worth a look. eboot.json is checked for encodability only;
the build reports strings that do not fit.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build          # noqa: E402  (encode_ui, layout constants)
import font           # noqa: E402
import quiz           # noqa: E402
import script_text    # noqa: E402
import wrap           # noqa: E402

JP_CHARS = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")
BRACE = re.compile(r"\{[^}]*\}?")
KW_EMPTY = re.compile(r"\{kw:\d+:1:\}")


def tokens(markup):
    """Markup tokens that must survive translation: names, keywords (by id), op tokens."""
    out = collections.Counter()
    for kind, val in script_text.split_markup(markup):
        if kind != "tok" or val in ("\n", "\f"):
            continue
        if val.startswith("{kw:"):
            out["{kw:" + ":".join(val[4:-1].split(":")[:2]) + "}"] += 1
        else:
            out[val] += 1
    return out


def encodable(text):
    try:
        build.encode_ui(text)
        return True
    except UnicodeEncodeError:
        return False


def bad_chars(text):
    return sorted({ch for ch in text if not encodable(ch)})


def load_metrics(iso):
    if iso:
        import game
        img = game.Image(iso)
        files, _ = img.archive("/PSP_GAME/USRDIR/START.DAT")
        img.close()
        return font.Metrics(files["fontA.ftd"])
    path = os.path.join(ROOT, "work", "fontA.ftd")
    return font.Metrics.load(path) if os.path.exists(path) else None


def check_file(path, units, metrics, issues):
    tag = os.path.basename(path)[:-5]
    with open(path, encoding="utf-8") as f:
        tr = json.load(f)
    jp = {u["id"]: u for u in units}
    for uid, en in tr.items():
        where = f"{tag}:{uid}"
        if uid not in jp:
            issues.append(("ERROR", where, "unknown unit id"))
            continue
        if not isinstance(en, str) or not en:
            continue
        for m in BRACE.finditer(en):
            if not script_text.TOKEN.fullmatch(m.group()):
                issues.append(("ERROR", where, f"malformed token {m.group()!r}"))
        want, got = tokens(jp[uid]["jp"]), tokens(en)
        if want != got:
            missing = want - got
            extra = got - want
            # Name inserts may become pronouns ("you", "her") or be added where the Japanese
            # leaves the name implied: worth a look, not an error. Anything else must match.
            names = {"{NAME}", "{NICK}", "{SURNAME}"}
            hard = {k for k in list(missing) + list(extra) if k not in names}
            level = "ERROR" if hard else "WARN"
            issues.append((level, where, f"tokens differ: missing {dict(missing)} extra {dict(extra)}"))
        for m in KW_EMPTY.finditer(en):
            issues.append(("ERROR", where, f"keyword {m.group()} has no term (the Get New Word popup shows it)"))
        if JP_CHARS.search(en):
            issues.append(("ERROR", where, "Japanese characters in the English"))
        chars = bad_chars(en)
        if chars:
            issues.append(("ERROR", where, f"characters the game cannot draw: {chars!r}"))
        kind = jp[uid]["kind"]
        if metrics and kind == "page" and not chars:
            rep = {"overflow": [], "split": []}
            build.layout_page(en, metrics, rep, where)
            if rep["overflow"]:
                issues.append(("WARN", where, f"a word is wider than {build.MAX_LINE_PX}px"))
        if kind == "choice" and len(en) > build.CHOICE_UNITS:
            issues.append(("ERROR", where, f"choice longer than {build.CHOICE_UNITS} characters "
                           "(it would overwrite the next choice; the build cuts it)"))
        if kind == "quiz_choice" and not chars and len(build.encode_ui(en)) >= quiz.FIELD:
            issues.append(("WARN", where, "choice longer than 31 characters (will be cut)"))
        if kind == "quiz" and metrics and not chars:
            lines = build.fit_lines(en, metrics, build.QUIZ_LINE_PX, build.QUIZ_SPACING, quiz.FIELD)
            if len(lines) > quiz.LINES:
                issues.append(("WARN", where, "question needs more than 3 lines (will be cut)"))
        if kind in ("dict_title", "mem_title", "sel_title") and not chars and len(build.encode_ui(en)) >= 64:
            issues.append(("WARN", where, "title longer than 31 characters (will be cut)"))
    missing = [u["id"] for u in units if u["id"] not in tr]
    return len(tr), len(units), missing


def check_eboot(path, issues):
    with open(path, encoding="utf-8") as f:
        tr = json.load(f)
    for key, ent in tr.items():
        if key == "nameplates":
            for sid, name in ent.items():
                if bad_chars(name):
                    issues.append(("ERROR", f"eboot:nameplates/{sid}", f"cannot draw {bad_chars(name)!r}"))
            continue
        text = ent["en"] if isinstance(ent, dict) else ent
        if not re.fullmatch(r"0x[0-9a-f]{8}", key):
            issues.append(("ERROR", f"eboot:{key}", "key is not a 0x-prefixed lowercase address"))
        if bad_chars(text):
            issues.append(("ERROR", f"eboot:{key}", f"cannot draw {bad_chars(text)!r}"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--text", default=os.path.join(ROOT, "work", "text"))
    ap.add_argument("--iso", help="original ISO, for the font metrics used by layout checks")
    ap.add_argument("--strict", action="store_true", help="fail on warnings too")
    ap.add_argument("--quiet", action="store_true", help="summary only")
    a = ap.parse_args()
    files = a.files or sorted(glob.glob(os.path.join(ROOT, "translation", "en", "*.json")))
    metrics = load_metrics(a.iso)
    if metrics is None:
        print("note: no --iso and no work/fontA.ftd, so line widths are not checked")
    issues = []
    for path in files:
        tag = os.path.basename(path)[:-5]
        if tag == "eboot":
            check_eboot(path, issues)
            continue
        src = os.path.join(a.text, f"{tag}.json")
        if not os.path.exists(src):
            issues.append(("ERROR", tag, f"no Japanese units at {src}: run the extractors"))
            continue
        with open(src, encoding="utf-8") as f:
            units = json.load(f)
        done, total, missing = check_file(path, units, metrics, issues)
        print(f"{tag}: {done}/{total} units translated")
        if missing:
            issues.append(("WARN", tag, f"{len(missing)} untranslated, first {missing[0]}"))
    counts = collections.Counter(level for level, _, _ in issues)
    if not a.quiet:
        for level, where, msg in issues:
            print(f"{level:5} {where}: {msg}")
    print(f"{counts['ERROR']} errors, {counts['WARN']} warnings")
    return 1 if counts["ERROR"] or (a.strict and counts["WARN"]) else 0


if __name__ == "__main__":
    sys.exit(main())
