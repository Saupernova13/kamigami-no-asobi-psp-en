"""Story script (story.dat / NN_Story.dat) parser and builder.

File layout (little endian):
  u32 table_size          byte size of the scene table (= 8 + 8 * count)
  u32 count
  count x (u32 scene_id, u32 offset)
  scene bytecode

Each scene is a stream of instructions:
  u8  0xFF                marker
  u8  size                header + args, unpadded (the VM steps by this)
  u16 opcode
  u16 prev                bytes taken by the previous instruction incl. its text (0 if first)
  u16 size                same as the size byte
  args                    then zero padding to a 4-byte boundary
  text                    optional: bit-inverted Shift-JIS, zero padded to 4 bytes

Opcode 0x518 is the odd one out: it carries one u16 argument *before* prev/size.

Text is any run of non-0xFF bytes after an instruction; the VM prints it into the open
message window. Inverted SJIS never contains 0xFF, and zero bytes are skipped as padding.
Control flow jumps by scene id (op 0x65 goto, 0x515 call), never by byte offset, so
scenes can change size freely as long as the scene table is rebuilt.
"""
import struct

MARK = 0xFF
OP_SHIFTED_HEADER = 0x518


def invert(b):
    return bytes(x ^ 0xFF for x in b)


def decode_text(raw):
    """Raw tail bytes -> str (padding removed)."""
    return invert(raw.replace(b"\0", b"")).decode("cp932")


def encode_text(s):
    """str -> raw tail bytes, padded to 4."""
    raw = invert(s.encode("cp932"))
    return raw + b"\0" * (-len(raw) % 4)


def align4(n):
    return (n + 3) & ~3


class Instr:
    """One instruction. `args` excludes the prev/size fields; `text` is the raw tail."""
    __slots__ = ("op", "args", "text")

    def __init__(self, op, args=b"", text=b""):
        self.op, self.args, self.text = op, args, text

    @property
    def arg0(self):
        return struct.unpack_from("<H", self.args, 0)[0] if len(self.args) >= 2 else None

    def encode(self, prev):
        if self.op == OP_SHIFTED_HEADER:
            lead, rest = self.args[:2], self.args[2:]
            size = 10 + len(rest)
            head = struct.pack("<BBH", MARK, size, self.op) + lead + struct.pack("<HH", prev, size)
        else:
            rest = self.args
            size = 8 + len(rest)
            head = struct.pack("<BBHHH", MARK, size, self.op, prev, size)
        if size > 0xFF:
            raise ValueError(f"instruction {self.op:#x} too long ({size} bytes)")
        body = head + rest
        return body + b"\0" * (align4(size) - size) + self.text

    def __repr__(self):
        return f"Instr({self.op:#06x}, {self.args.hex(' ', 2)}, text={len(self.text)}b)"


class Scene:
    __slots__ = ("sid", "instrs")

    def __init__(self, sid, instrs):
        self.sid, self.instrs = sid, instrs


class Story:
    def __init__(self, table, scenes):
        self.table = table      # [(scene_id, index into scenes)] in file table order
        self.scenes = scenes    # Scene objects in data (offset) order

    @classmethod
    def parse(cls, data):
        tsize, count = struct.unpack_from("<II", data, 0)
        if tsize != 8 + 8 * count:
            raise ValueError("bad scene table")
        ents = [struct.unpack_from("<II", data, 8 + i * 8) for i in range(count)]
        offsets = sorted({o for _, o in ents})
        bounds = dict(zip(offsets, offsets[1:] + [len(data)]))
        index = {o: i for i, o in enumerate(offsets)}
        owner = {}
        for sid, o in ents:
            owner.setdefault(o, sid)
        scenes = [Scene(owner[o], parse_scene(data, o, bounds[o])) for o in offsets]
        return cls([(sid, index[o]) for sid, o in ents], scenes)

    def build(self):
        head = 8 + 8 * len(self.table)
        blobs, offs, pos = [], [], head
        for sc in self.scenes:
            b = build_scene(sc.instrs)
            offs.append(pos)
            blobs.append(b)
            pos += len(b)
        out = bytearray(struct.pack("<II", head, len(self.table)))
        for sid, i in self.table:
            out += struct.pack("<II", sid, offs[i])
        for b in blobs:
            out += b
        return bytes(out)

    def scene(self, sid):
        for s, i in self.table:
            if s == sid:
                return self.scenes[i]
        raise KeyError(sid)


def parse_scene(data, start, stop):
    out = []
    p = start
    while p < stop:
        if data[p] != MARK:
            raise ValueError(f"desync at {p:#x}")
        size = data[p + 1]
        op = struct.unpack_from("<H", data, p + 2)[0]
        if op == OP_SHIFTED_HEADER:
            args = data[p + 4:p + 6] + data[p + 10:p + size]
        else:
            args = data[p + 8:p + size]
        q = p + align4(size)
        t = q
        while t < stop and data[t] != MARK:
            t += 1
        out.append(Instr(op, args, data[q:t]))
        p = t
    return out


def build_scene(instrs):
    out = bytearray()
    prev = 0
    for ins in instrs:
        b = ins.encode(prev)
        out += b
        prev = len(b)
    return bytes(out)
