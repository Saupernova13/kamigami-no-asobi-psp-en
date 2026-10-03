"""Turn the relocatable PRX EBOOT into a fixed-address ELF.

  python tools/prx.py <decrypted EBOOT (PRX)> <out.ELF> [--base 0x08804000]

The game's EBOOT is a PRX (e_type 0xFFA0) linked at 0 with a plain Elf32_Rel table in
program header 0x700000A0 (PT_PSPREL1). Applying them for the address the PSP and PPSSPP
load the main module at, and marking the file ET_EXEC, gives a static ELF whose code can be
patched with absolute addresses - the same workflow as a non-relocatable EBOOT.

Relocations are applied the way PPSSPP's ElfReader::LoadRelocations does.
"""
import argparse
import struct
import sys

PT_LOAD, PT_PSPREL1 = 1, 0x700000A0
R_MIPS_16, R_MIPS_32, R_MIPS_26, R_MIPS_HI16, R_MIPS_LO16 = 1, 2, 4, 5, 6
ET_EXEC, ET_PSPEXEC = 2, 0xFFA0
DEFAULT_BASE = 0x08804000


def phdrs(elf):
    phoff, = struct.unpack_from("<I", elf, 0x1C)
    phnum, = struct.unpack_from("<H", elf, 0x2C)
    return [list(struct.unpack_from("<8I", elf, phoff + i * 32)) for i in range(phnum)]


def relocations(elf):
    """-> [(offset_segment, offset, target_segment, type)] from the PT_PSPREL1 table
    (plain Elf32_Rel: r_offset, r_info = type | offset_seg << 8 | target_seg << 16)."""
    ph = phdrs(elf)
    p = next(p for p in ph if p[0] == PT_PSPREL1)
    out = []
    for i in range(p[4] // 8):
        off, info = struct.unpack_from("<II", elf, p[1] + i * 8)
        out.append(((info >> 8) & 0xFF, off, (info >> 16) & 0xFF, info & 0xF))
    return out


def to_static(elf, base=DEFAULT_BASE):
    """-> (static ELF bytes, file offsets of relocated words)."""
    elf = bytearray(elf)
    if struct.unpack_from("<H", elf, 0x10)[0] != ET_PSPEXEC:
        raise ValueError("not a PRX")
    ph = phdrs(elf)
    seg_vaddr = [p[2] + base for p in ph]
    seg_off = [p[1] for p in ph]
    rels = relocations(bytes(elf))
    fo = [seg_off[os_] + off for os_, off, _, _ in rels]
    orig = [struct.unpack_from("<I", elf, x)[0] for x in fo]
    touched = []
    for r, (off_seg, off, to_seg, typ) in enumerate(rels):
        to = seg_vaddr[to_seg]
        op = orig[r]
        if typ == R_MIPS_32:
            op = (op + to) & 0xFFFFFFFF
        elif typ == R_MIPS_26:
            op = (op & 0xFC000000) | (((op & 0x03FFFFFF) + (to >> 2)) & 0x03FFFFFF)
        elif typ == R_MIPS_HI16:
            lo = next((orig[t] for t in range(r + 1, len(rels)) if rels[t][3] != R_MIPS_HI16), 0)
            lo = (lo & 0xFFFF) - 0x10000 if lo & 0x8000 else lo & 0xFFFF
            cur = ((op & 0xFFFF) << 16) + lo + to
            op = (op & 0xFFFF0000) | (((cur + 0x8000) >> 16) & 0xFFFF)
        elif typ in (R_MIPS_LO16, R_MIPS_16):
            op = (op & 0xFFFF0000) | (((op & 0xFFFF) + to) & 0xFFFF)
        elif typ in (0, 7):
            continue
        else:
            raise ValueError(f"unknown relocation type {typ}")
        struct.pack_into("<I", elf, fo[r], op)
        touched.append(fo[r])
    # header: executable, entry and segments at their load address, relocations dropped
    struct.pack_into("<H", elf, 0x10, ET_EXEC)
    entry, = struct.unpack_from("<I", elf, 0x18)
    struct.pack_into("<I", elf, 0x18, entry + base)
    phoff, = struct.unpack_from("<I", elf, 0x1C)
    for i, p in enumerate(ph):
        o = phoff + i * 32
        if p[0] == PT_LOAD:
            struct.pack_into("<I", elf, o + 8, p[2] + base)
            if i == 0:
                struct.pack_into("<I", elf, o + 12, p[2] + base)   # paddr held the modinfo offset
        else:
            struct.pack_into("<I", elf, o, 0)                     # PT_NULL
    shoff, = struct.unpack_from("<I", elf, 0x20)
    shnum, = struct.unpack_from("<H", elf, 0x30)
    for i in range(shnum):
        o = shoff + i * 40
        flags, addr = struct.unpack_from("<II", elf, o + 8)
        if flags & 2:                                             # SHF_ALLOC
            struct.pack_into("<I", elf, o + 12, addr + base)
        if struct.unpack_from("<I", elf, o + 4)[0] in (0x700000A0, 0x700000A1):
            struct.pack_into("<I", elf, o + 4, 0)                 # SHT_NULL for PSP reloc sections
    return bytes(elf), touched


def add_segment(elf, size, align=0x100):
    """Append a zero-filled PT_LOAD segment just past the highest loaded address, reusing
    the program header freed by to_static. -> (elf, segment address). The loader then
    reserves it as part of the module, so it is safe space for relocated strings."""
    elf = bytearray(elf)
    ph = phdrs(elf)
    top = max(p[2] + p[5] for p in ph if p[0] == PT_LOAD)
    va = (top + align - 1) & ~(align - 1)
    slot = next(i for i, p in enumerate(ph) if p[0] == 0)
    # keep file offset = address - (segment 0 address - its file offset), the linear mapping
    # every tool here uses (game.elf_off); the gap after the file end is zero padding
    off = va - (ph[0][2] - ph[0][1])
    if off < len(elf):
        raise ValueError("segment would overlap existing file data")
    elf += bytes(off - len(elf) + size)
    phoff, = struct.unpack_from("<I", elf, 0x1C)
    struct.pack_into("<8I", elf, phoff + slot * 32, PT_LOAD, off, va, va, size, size, 6, 16)
    return bytes(elf), va


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("prx")
    ap.add_argument("out")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=DEFAULT_BASE)
    a = ap.parse_args()
    with open(a.prx, "rb") as f:
        data = f.read()
    out, touched = to_static(data, a.base)
    with open(a.out, "wb") as f:
        f.write(out)
    print(f"applied {len(touched)} relocations, base {a.base:#x} -> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
