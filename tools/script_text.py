"""Text units of a story script: extraction to markup and reinsertion from markup.

Units
  page    a message window: from op 0x7DE (open, arg0 = speaker id) to op 0xCC with a
          non-zero argument (wait for input / close). Text runs hang off instructions
          inside it; op 0xCC arg 0 is a line break.
  choice  op 0x74 (arg0 = target scene); its tail text is the option label.
  arg     strings stored inside an instruction's arguments (name prompt 0x3E9, system
          prompt 0x51E, staff roll 0x579, keyword/title card 0x7DD outside a page).

Page markup
  \\n                 line break (op 0xCC 0000)
  {SURNAME} {NAME}   player name variables (op 0xD5 arg 0 / 1)
  {kw:ID:F:TEXT}     keyword marker (op 0x7DD: u16 id, u8 flag F, u8 len, text): tags the
                     word TEXT that comes just *before* it as dictionary entry ID; the
                     marker itself is not printed
  {op:XXXX:HEX}      any other instruction found between two text runs, kept verbatim
  \\f                 (insertion only) continue in a fresh window: wait for input, close,
                     re-mark the same page id and reopen for the same speaker

Unit ids are stable for a given original script: "<scene>/p<n>", "<scene>/c<n>",
"<scene>/a<n>", numbered in stream order within the scene.
"""
import re
import struct

from story import Instr, decode_text, encode_text, invert

OP_PAGE = 0x7DE
OP_LINE = 0xCC
OP_NAME = 0xD5
OP_KEYWORD = 0x7DD
OP_CHOICE = 0x74
ARG_TEXT_OPS = (0x3E9, 0x51E, 0x579, 0x7DD)

OP_WAIT_ARGS = b"\x01\x03"   # op 0xCC 0x0301: wait for input
OP_PAGE_END = 0x04
OP_PAGE_ID = 0x03

TOKEN = re.compile(r"\{(SURNAME|NAME|kw:\d+:\d+:[^}]*|op:[0-9a-f]{4}:[0-9a-f]*)\}|\n|\f")


# --- argument strings -------------------------------------------------------------

def arg_text_split(ins):
    """-> (prefix, raw inverted text, trailing bytes) for ops that embed a string.
    Length-prefixed ops (0x51E u16, 0x7DD u8) keep the length field in the prefix."""
    a = ins.args
    if ins.op == 0x51E:
        n = struct.unpack_from("<H", a, 0)[0]
        return a[:2], a[2:2 + n], a[2 + n:]
    if ins.op == OP_KEYWORD:
        n = a[3]
        return a[:4], a[4:4 + n], a[4 + n:]
    if ins.op == 0x3E9:
        skip = 8
    elif ins.op == 0x579:
        skip = 4
    else:
        raise ValueError(f"op {ins.op:#x} has no argument text")
    end = a.find(b"\0", skip)
    end = len(a) if end < 0 else end
    return a[:skip], a[skip:end], a[end:]


def arg_text_get(ins):
    return invert(arg_text_split(ins)[1]).decode("cp932")


def arg_text_set(ins, text):
    if ins.args and text == arg_text_get(ins):
        return  # unchanged: keep the original bytes (cp932 has duplicate code points)
    pre, _, post = arg_text_split(ins)
    raw = invert(text.encode("cp932"))
    if ins.op == 0x51E:
        pre = struct.pack("<H", len(raw))
    elif ins.op == OP_KEYWORD:
        if len(raw) > 0xFF:
            raise ValueError("keyword too long")
        pre = pre[:3] + bytes([len(raw)])
    ins.args = pre + raw + (post or b"\0")


# --- markup ---------------------------------------------------------------------

def token_for(ins):
    if ins.op == OP_LINE and ins.arg0 == 0:
        return "\n"
    if ins.op == OP_NAME and ins.arg0 in (0, 1):
        return "{SURNAME}" if ins.arg0 == 0 else "{NAME}"
    if ins.op == OP_KEYWORD:
        return f"{{kw:{ins.arg0}:{ins.args[2]}:{arg_text_get(ins)}}}"
    return f"{{op:{ins.op:04x}:{ins.args.hex()}}}"


def instr_for(token):
    if token == "\n":
        return Instr(OP_LINE, b"\0\0")
    if token == "{SURNAME}":
        return Instr(OP_NAME, b"\0\0")
    if token == "{NAME}":
        return Instr(OP_NAME, b"\1\0")
    body = token[1:-1]
    if body.startswith("kw:"):
        _, kid, flag, text = body.split(":", 3)
        ins = Instr(OP_KEYWORD, struct.pack("<HBB", int(kid), int(flag), 0))
        arg_text_set(ins, text)
        return ins
    if body.startswith("op:"):
        _, op, hexargs = body.split(":", 2)
        return Instr(int(op, 16), bytes.fromhex(hexargs))
    raise ValueError(f"bad token {token!r}")


def split_markup(s):
    """-> list of ('text', str) / ('tok', str)."""
    out, pos = [], 0
    for m in TOKEN.finditer(s):
        if m.start() > pos:
            out.append(("text", s[pos:m.start()]))
        out.append(("tok", m.group(0)))
        pos = m.end()
    if pos < len(s):
        out.append(("text", s[pos:]))
    return out


# --- unit discovery ---------------------------------------------------------------

class Page:
    """Slice of a scene: instrs[start:end] with end the closing 0xCC (inclusive)."""
    def __init__(self, start, end, carrier, last):
        self.start, self.end, self.carrier, self.last = start, end, carrier, last


def find_pages(instrs):
    pages, i = [], 0
    while i < len(instrs):
        if instrs[i].op != OP_PAGE:
            i += 1
            continue
        j = i
        while j < len(instrs) and not (instrs[j].op == OP_LINE and instrs[j].arg0 not in (0, None)):
            j += 1
            if j < len(instrs) and instrs[j].op == OP_PAGE:
                break
        if j >= len(instrs) or instrs[j].op == OP_PAGE:
            i = j  # unterminated page: skip it
            continue
        content = [k for k in range(i, j)
                   if instrs[k].text or (k > i and instrs[k].op in (OP_NAME, OP_KEYWORD))]
        if any(instrs[k].text for k in content):
            first = content[0]
            # A leading name/keyword op becomes a token, so the text hangs off the op before it.
            carrier = first - 1 if instrs[first].op in (OP_NAME, OP_KEYWORD) else first
            pages.append(Page(i, j, carrier, content[-1]))
        i = j + 1
    return pages


def page_markup(instrs, pg):
    parts = [decode_text(instrs[pg.carrier].text)]
    for ins in instrs[pg.carrier + 1:pg.last + 1]:
        parts.append(token_for(ins))
        if ins.text:
            parts.append(decode_text(ins.text))
    return "".join(parts)


def page_rebuild(instrs, pg, markup):
    """-> replacement list for instrs[pg.start:pg.last + 1]."""
    head = [Instr(x.op, x.args, x.text) for x in instrs[pg.start:pg.carrier + 1]]
    carrier = head[-1]
    carrier.text = b""
    cur = carrier
    out = head
    page_id = next((x for x in reversed(instrs[max(0, pg.start - 4):pg.start]) if x.op == OP_PAGE_ID), None)
    for kind, val in split_markup(markup):
        if kind == "text":
            cur.text = encode_text(val)
        elif val == "\f":
            out += [Instr(OP_LINE, OP_WAIT_ARGS), Instr(OP_PAGE_END)]
            if page_id is not None:
                out.append(Instr(OP_PAGE_ID, page_id.args))
            cur = Instr(OP_PAGE, instrs[pg.start].args)
            out.append(cur)
        else:
            cur = instr_for(val)
            out.append(cur)
    return out


def scene_units(sid, instrs):
    """Yield (unit_id, kind, japanese_markup) in stream order."""
    pages = find_pages(instrs)
    inside = set()
    for pg in pages:
        inside.update(range(pg.start, pg.end + 1))
    np = nc = na = 0
    page_at = {pg.start: pg for pg in pages}
    for k, ins in enumerate(instrs):
        if k in page_at:
            yield f"{sid}/p{np}", "page", page_markup(instrs, page_at[k])
            np += 1
        if ins.op == OP_CHOICE and ins.text:
            yield f"{sid}/c{nc}", "choice", decode_text(ins.text)
            nc += 1
        if ins.op in ARG_TEXT_OPS and k not in inside:
            yield f"{sid}/a{na}", "arg", arg_text_get(ins)
            na += 1


def apply_scene(sid, instrs, tr):
    """Return a new instruction list with translations from `tr` (unit_id -> markup)."""
    pages = find_pages(instrs)
    inside = set()
    for pg in pages:
        inside.update(range(pg.start, pg.end + 1))
    page_at = {pg.start: pg for pg in pages}
    out, k, np, nc, na = [], 0, 0, 0, 0
    while k < len(instrs):
        if k in page_at:
            pg = page_at[k]
            uid = f"{sid}/p{np}"
            np += 1
            if uid in tr and tr[uid] != page_markup(instrs, pg):
                out += page_rebuild(instrs, pg, tr[uid])
                k = pg.last + 1
                continue
        ins = Instr(instrs[k].op, instrs[k].args, instrs[k].text)
        if ins.op == OP_CHOICE and ins.text:
            uid = f"{sid}/c{nc}"
            nc += 1
            if uid in tr and tr[uid] != decode_text(ins.text):
                ins.text = encode_text(tr[uid])
        if ins.op in ARG_TEXT_OPS and k not in inside:
            uid = f"{sid}/a{na}"
            na += 1
            if uid in tr:
                arg_text_set(ins, tr[uid])
        out.append(ins)
        k += 1
    return out
