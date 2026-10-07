"""NISPACK archive reader/writer (Nippon Ichi container holding this game's PSP data files).

Layout (little endian):
  0x00  char[8]  "NISPACK\0"
  0x08  u32      0
  0x0C  u32      entry count
  0x10  entries, 0x2C bytes each:
          char[32] name, u32 offset, u32 size, u32 checksum
  file data, each entry aligned to 0x800
"""
import argparse
import os
import struct
import sys

MAGIC = b"NISPACK\0"
ENTRY = struct.Struct("<32sIII")
ALIGN = 0x800


class Entry:
    def __init__(self, name, offset, size, checksum):
        self.name, self.offset, self.size, self.checksum = name, offset, size, checksum


def read_entries(data):
    if data[:8] != MAGIC:
        raise ValueError("not a NISPACK archive")
    count = struct.unpack_from("<I", data, 0xC)[0]
    out = []
    for i in range(count):
        raw, off, size, ck = ENTRY.unpack_from(data, 0x10 + i * ENTRY.size)
        out.append(Entry(raw.split(b"\0")[0].decode("cp932"), off, size, ck))
    return out


def load_bytes(data):
    entries = read_entries(data)
    return {e.name: data[e.offset:e.offset + e.size] for e in entries}, entries


def load(path):
    with open(path, "rb") as f:
        return load_bytes(f.read())


def build(entries, files):
    """Rebuild an archive. `entries` keeps the original order and checksums;
    `files` maps name -> bytes (replacement or original)."""
    head = 0x10 + len(entries) * ENTRY.size
    pos = (head + ALIGN - 1) // ALIGN * ALIGN
    table, blobs = [], []
    for e in entries:
        blob = files[e.name]
        table.append(ENTRY.pack(e.name.encode("cp932"), pos, len(blob), e.checksum))
        blobs.append((pos, blob))
        pos = (pos + len(blob) + ALIGN - 1) // ALIGN * ALIGN
    out = bytearray(pos)
    out[:8] = MAGIC
    struct.pack_into("<II", out, 8, 0, len(entries))
    out[0x10:head] = b"".join(table)
    for off, blob in blobs:
        out[off:off + len(blob)] = blob
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("archive")
    p = sub.add_parser("extract"); p.add_argument("archive"); p.add_argument("outdir")
    p = sub.add_parser("pack", help="rebuild archive, taking replacements from a dir")
    p.add_argument("archive"); p.add_argument("replacements"); p.add_argument("out")
    a = ap.parse_args()

    files, entries = load(a.archive)
    if a.cmd == "list":
        for e in entries:
            print(f"{e.offset:08X} {e.size:9d} {e.checksum:08X} {e.name}")
    elif a.cmd == "extract":
        os.makedirs(a.outdir, exist_ok=True)
        for name, blob in files.items():
            with open(os.path.join(a.outdir, name), "wb") as f:
                f.write(blob)
        print(f"extracted {len(files)} files to {a.outdir}")
    elif a.cmd == "pack":
        for name in files:
            rp = os.path.join(a.replacements, name)
            if os.path.isfile(rp):
                with open(rp, "rb") as f:
                    files[name] = f.read()
        with open(a.out, "wb") as f:
            f.write(build(entries, files))


if __name__ == "__main__":
    sys.exit(main())
