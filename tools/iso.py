"""Minimal ISO9660 file replacer for PSP UMD images.

A replacement that fits in the file's existing sectors (and does not run into the next
extent) is written in place; anything larger is appended at the end of the image and the
directory record is repointed. Directory records store extent and size both little and
big endian, and the primary volume descriptor's volume space size is bumped to match.
"""
import argparse
import os
import shutil
import struct
import sys

SECTOR = 2048


def _both32(v):
    return struct.pack("<I", v) + struct.pack(">I", v)


class Iso:
    def __init__(self, path, writable=False):
        self.path = path
        self.f = open(path, "r+b" if writable else "rb")
        pvd = self._read(16 * SECTOR, SECTOR)
        if pvd[1:6] != b"CD001":
            raise ValueError("not an ISO9660 image")
        self.volume_sectors = struct.unpack_from("<I", pvd, 80)[0]
        root = pvd[156:156 + 34]
        self.files = {}     # upper-case path -> (record offset in image, extent, size)
        self.dir_extents = []
        self._walk(struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0], "")

    def _read(self, off, n):
        self.f.seek(off)
        return self.f.read(n)

    def _walk(self, extent, size, prefix):
        self.dir_extents.append(extent)
        data = self._read(extent * SECTOR, size)
        pos = 0
        while pos < size:
            ln = data[pos]
            if ln == 0:
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            rec = data[pos:pos + ln]
            ext, sz, flags, nlen = struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0], rec[25], rec[32]
            name = rec[33:33 + nlen]
            if name not in (b"\0", b"\1"):
                name = name.decode("ascii").split(";")[0]
                path = f"{prefix}/{name}".upper()
                if flags & 2:
                    self._walk(ext, sz, path)
                else:
                    self.files[path] = (extent * SECTOR + pos, ext, sz)
            pos += ln

    def extents(self):
        return sorted([(ext, sz) for _, ext, sz in self.files.values()] + [(e, 0) for e in self.dir_extents])

    def read_file(self, path):
        _, ext, sz = self.files[path.upper()]
        return self._read(ext * SECTOR, sz)

    def replace(self, path, data):
        key = path.upper()
        rec_off, ext, old = self.files[key]
        later = [e for e, _ in self.extents() if e > ext]
        room = (later[0] if later else self.volume_sectors) - ext
        need = (len(data) + SECTOR - 1) // SECTOR
        if need <= room:
            new_ext = ext
        else:
            new_ext = self.volume_sectors
            self.volume_sectors += (len(data) + SECTOR - 1) // SECTOR
            self._set_volume_size()
        self.f.seek(new_ext * SECTOR)
        self.f.write(data)
        pad = -len(data) % SECTOR
        self.f.write(b"\0" * pad)
        self.f.seek(rec_off + 2)
        self.f.write(_both32(new_ext) + _both32(len(data)))
        self.files[key] = (rec_off, new_ext, len(data))
        return new_ext != ext

    def _set_volume_size(self):
        self.f.seek(16 * SECTOR + 80)
        self.f.write(_both32(self.volume_sectors))

    def close(self):
        self.f.seek(0, os.SEEK_END)
        end = self.volume_sectors * SECTOR
        if self.f.tell() < end:
            self.f.truncate(end)
        self.f.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src_iso")
    ap.add_argument("out_iso")
    ap.add_argument("replacements", nargs="+", help="ISO_PATH=LOCAL_FILE")
    a = ap.parse_args()
    shutil.copyfile(a.src_iso, a.out_iso)
    iso = Iso(a.out_iso, writable=True)
    for r in a.replacements:
        dst, src = r.split("=", 1)
        with open(src, "rb") as f:
            moved = iso.replace(dst, f.read())
        print(f"{dst}: {'appended' if moved else 'in place'}")
    iso.close()


if __name__ == "__main__":
    sys.exit(main())
