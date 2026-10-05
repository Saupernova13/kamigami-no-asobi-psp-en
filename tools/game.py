"""Where things live in the Kamigami no Asobi PSP image."""
import struct

import iso as isolib
import nispack
import story

EBOOT = "/PSP_GAME/SYSDIR/EBOOT.BIN"
ELF_BASE = 0x08804000 - 0xC0   # address of file offset 0 in the static EBOOT (tools/prx.py)

# tag -> (archive in the ISO, script inside the archive)
STORY_FILES = {f"{n:02d}": (f"/PSP_GAME/USRDIR/DATA{n:02d}.DAT", f"{n:02d}_Story.dat") for n in range(1, 13)}

SPEAKER_TABLE = 0x08964B54   # {u32 id, char *name} pairs, last id 9999 ("no speaker set")


class Image:
    """Read-only view of the original ISO with archive caching."""

    def __init__(self, path):
        self.iso = isolib.Iso(path)
        self._archives = {}

    def archive(self, path):
        if path not in self._archives:
            files, entries = nispack.load_bytes(self.iso.read_file(path))
            self._archives[path] = (files, entries)
        return self._archives[path]

    def story(self, tag):
        arc, name = STORY_FILES[tag]
        files, _ = self.archive(arc)
        return story.Story.parse(files[name])

    def file(self, path):
        return self.iso.read_file(path)

    def close(self):
        self.iso.f.close()


def elf_off(va):
    return va - ELF_BASE


def elf_cstring(elf, va):
    o = elf_off(va)
    return elf[o:elf.index(b"\0", o)]


def speaker_table(elf):
    """-> {speaker id: name string address} from the nameplate table."""
    out, va = {}, SPEAKER_TABLE
    while True:
        sid, ptr = struct.unpack_from("<II", elf, elf_off(va))
        out[sid] = ptr
        if sid == 9999:
            return out
        va += 8
