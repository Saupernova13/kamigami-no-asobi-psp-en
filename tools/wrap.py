"""Word-wrap page markup to the message window using the real glyph advances.

Explicit "\\n" in the markup is kept as a hard break. Tokens are zero width except the
name variables, which are measured with a reserve name so typical player names fit.
"""
import re

from script_text import split_markup

NAME_RESERVE = {"{NAME}": "Haruka", "{NICK}": "Haruka", "{SURNAME}": "Nanami"}
WORD = re.compile(r"\S+|\s+")


def _pieces(markup):
    """-> list of (kind, text, width_text): kind is 'word', 'space', 'tok', 'br'."""
    out = []
    for kind, val in split_markup(markup):
        if kind == "tok":
            if val == "\n":
                out.append(("br", val, ""))
            else:
                out.append(("tok", val, NAME_RESERVE.get(val, "")))
            continue
        for w in WORD.findall(val):
            out.append(("space" if w.isspace() else "word", w, w))
    return out


def _units(markup):
    """Group pieces into breakable units: runs of words and tokens with no space between
    them ("{NAME}." stays whole), single spaces, and hard breaks."""
    units = []
    for kind, text, wtext in _pieces(markup):
        if kind in ("word", "tok") and units and units[-1][0] == "unit":
            _, t, w = units[-1]
            units[-1] = ("unit", t + text, w + wtext)
        elif kind in ("word", "tok"):
            units.append(("unit", text, wtext))
        else:
            units.append((kind, text, wtext))
    return units


def wrap(markup, metrics, max_width, letter_spacing=0):
    def width(s):
        return metrics.width(s) + letter_spacing * len(s)

    lines, cur, cur_w = [], [], 0
    pending_space = ""
    for kind, text, wtext in _units(markup):
        if kind == "br":
            lines.append(cur)
            cur, cur_w, pending_space = [], 0, ""
            continue
        if kind == "space":
            pending_space = " " if cur else ""
            continue
        w = width(wtext)
        sp = width(pending_space) if pending_space else 0
        if cur and wtext and cur_w + sp + w > max_width:
            lines.append(cur)
            cur, cur_w, pending_space, sp = [], 0, "", 0
        if pending_space:
            cur.append(pending_space)
            cur_w += sp
            pending_space = ""
        cur.append(text)
        cur_w += w
    lines.append(cur)
    return "\n".join("".join(l) for l in lines)


def line_widths(markup, metrics, letter_spacing=0):
    out = []
    for line in markup.split("\n"):
        plain = re.sub(r"\{[^}]*\}", lambda m: NAME_RESERVE.get(m.group(0), ""), line)
        out.append(metrics.width(plain) + letter_spacing * len(plain))
    return out
