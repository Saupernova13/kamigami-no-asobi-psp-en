"""Make a distributable patch: an xdelta3 (VCDIFF) patch from the original ISO to the
English one, with apply instructions and checksums, and check it applies.

  python tools/release.py <original.iso> <english.iso> [--version 1.0] [--out patch]

Needs xdelta3 on PATH, in XDELTA3, or via --xdelta3. Replaces the contents of <out>
(default: the committed patch/ folder, which is what people clone or download) with:

  <name>.xdelta        the patch (no game data: only the differences)
  README.txt           how to apply it, the expected original checksum, credits
  apply-patch.bat      Windows: drag the original ISO onto it
  apply-patch.sh       Linux / macOS / Steam Deck
  SHA256SUMS.txt       original, patch and patched ISO

and writes the same files as work/release/<name>.zip for a release download. The patch is applied to the original once more
and the result compared with <english.iso>, so a release never ships a broken patch.
"""
import argparse
import datetime
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from build import find_tool   # noqa: E402

TITLE = "Kamigami no Asobi English Patch"
DISC = "NPJH50809"
ORIGINAL_SHA256 = "DED26F15C287D26D91EFBDB1BA78D1B5CA46939636A5711750ED2007803AFE16"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def git_commit():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


README = """{title} v{version}
{rule}

An English translation patch for Kamigami no Asobi (PSP, Japan,
{disc}). It changes the script, menus, quiz, dictionary, Mythology Monologue,
chapter titles and the text drawn into the game's images.

The patch contains no game data. You need your own copy of the Japanese UMD as
an ISO image.

Original ISO (check before patching):
  size    {orig_size:,} bytes
  SHA-256 {orig_sha}

Applying the patch
------------------
Windows:   put the original ISO in this folder and drag it onto
           apply-patch.bat. The English ISO is written next to it.
           (Or use any xdelta UI: "Delta Patcher", "xdelta UI".)
Linux, macOS, Steam Deck:
           sh apply-patch.sh /path/to/original.iso
           (needs xdelta3: apt install xdelta3 / brew install xdelta)
By hand:   xdelta3 -d -s original.iso {patch} "{iso}"

The result must have SHA-256
  {iso_sha}

Playing
-------
PPSSPP (PC, Android, Steam Deck) or a PSP with custom firmware. On a PSP, put
the ISO in ISO/ on the memory stick.

The player's default name is Yui. Name entry opens on its alphabet page; the
L and R buttons switch to the kana pages.

Notes
-----
- Most of the story text is machine-translated and has not been edited by
  hand yet. Menus, names, titles and image text were translated by hand.
- The fixed family name (Kusanagi) is left blank in the name box: its
  3-character slot cannot hold it, and the story never inserts it.
- Built from commit {commit} on {date}.

Credits
-------
Translation tooling, engine patch and translation: Saupernova13.
Built with armips (Kingcom), pspdecrypt (John-K), PPSSPP (testing) and
xdelta3 (Joshua MacDonald). Kamigami no Asobi (c) Broccoli. This is an
unofficial fan translation; please support the official release.
"""

BAT = """@echo off
setlocal
if "%~1"=="" (
  echo Drag the original Japanese ISO onto this file.
  pause
  exit /b 1
)
where xdelta3 >nul 2>nul
if errorlevel 1 (
  if not exist "%~dp0xdelta3.exe" (
    echo xdelta3.exe was not found. Download it from
    echo https://github.com/jmacd/xdelta-gpl/releases and put it next to this file.
    pause
    exit /b 1
  )
  set "XD=%~dp0xdelta3.exe"
) else (
  set "XD=xdelta3"
)
"%XD%" -d -s "%~1" "%~dp0{patch}" "%~dp1{iso}"
if errorlevel 1 (
  echo Patching failed. Check that the ISO is the original Japanese image.
) else (
  echo Done: %~dp1{iso}
)
pause
"""

SH = """#!/bin/sh
# Apply the English patch: sh apply-patch.sh /path/to/original.iso
set -e
if [ -z "$1" ]; then
  echo "usage: sh apply-patch.sh /path/to/original.iso" >&2
  exit 1
fi
here=$(cd "$(dirname "$0")" && pwd)
out="$(cd "$(dirname "$1")" && pwd)/{iso}"
if ! command -v xdelta3 >/dev/null 2>&1; then
  echo "xdelta3 not found: install it (apt install xdelta3, brew install xdelta)" >&2
  exit 1
fi
xdelta3 -d -s "$1" "$here/{patch}" "$out"
echo "Done: $out"
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("original")
    ap.add_argument("english")
    ap.add_argument("--version", default="1.0")
    ap.add_argument("--out", default=os.path.join(ROOT, "patch"))
    ap.add_argument("--zip-dir", default=os.path.join(ROOT, "work", "release"))
    ap.add_argument("--xdelta3")
    a = ap.parse_args()
    xdelta = find_tool("xdelta3", a.xdelta3, "XDELTA3")

    orig_sha = sha256(a.original)
    if orig_sha != ORIGINAL_SHA256:
        print(f"warning: the original's SHA-256 is {orig_sha}, not the known dump's", file=sys.stderr)
    name = f"Kamigami-no-Asobi-EN-v{a.version}"
    iso = f"Kamigami no Asobi - English v{a.version}.iso"   # no parentheses: cmd blocks
    patch = f"{name}.xdelta"
    dest = a.out
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)

    patch_path = os.path.join(dest, patch)
    # The source window must span the whole original: rebuilt archives move to the end of
    # the image, and with the default 64 MB window xdelta stores them whole (83 MB vs 3 MB).
    window = str(max(os.path.getsize(a.original), 1 << 26))
    subprocess.run([xdelta, "-e", "-9", "-S", "djw", "-B", window, "-f", "-s", a.original,
                    a.english, patch_path], check=True)
    os.makedirs(a.zip_dir, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=a.zip_dir) as tmp:
        check = os.path.join(tmp, "check.iso")
        subprocess.run([xdelta, "-d", "-f", "-s", a.original, patch_path, check], check=True)
        iso_sha = sha256(check)
    if iso_sha != sha256(a.english):
        sys.exit("the patch does not reproduce the English ISO")

    fields = dict(title=TITLE, rule="=" * (len(TITLE) + len(a.version) + 2), version=a.version,
                  disc=DISC, orig_size=os.path.getsize(a.original), orig_sha=orig_sha,
                  patch=patch, iso=iso, iso_sha=iso_sha, commit=git_commit(),
                  date=datetime.date.today().isoformat())
    files = {"README.txt": README.format(**fields).replace("\n", "\r\n"),
             "apply-patch.bat": BAT.format(**fields).replace("\n", "\r\n"),
             "apply-patch.sh": SH.format(**fields),
             "SHA256SUMS.txt": (f"{orig_sha}  original (Japanese) ISO\n"
                                f"{sha256(patch_path)}  {patch}\n"
                                f"{iso_sha}  {iso}\n")}
    for fname, text in files.items():
        with open(os.path.join(dest, fname), "w", encoding="ascii", newline="") as f:
            f.write(text)

    zpath = os.path.join(a.zip_dir, name + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fname in sorted(os.listdir(dest)):
            z.write(os.path.join(dest, fname), f"{name}/{fname}")
    print(f"{patch}: {os.path.getsize(patch_path):,} bytes, verified")
    print(f"release -> {dest} and {zpath}")


if __name__ == "__main__":
    sys.exit(main())
