# Playtest builds and releases

## Playtest build

A playtest ISO is the normal pipeline run from a clean, committed tree:

1. `git status` clean, on the primary branch (or the branch under test) and up to date.
2. `python tools/check.py --iso <original.iso> --quiet` ends with `0 errors`.
3. `python tools/build.py <original.iso> work/out/en.iso`, with no exception.
4. `python tools/harness.py --core <core> --out work/shots/release work/out/en.iso tests/ui.txt`,
   then look at `work/shots/release/n*.png` and `m*.png` (see [TESTING.md](TESTING.md)).
5. Copy the ISO out under a dated name, e.g.
   `Kamigami no Asobi (EN patch WIP YYYY-MM-DD).iso`, and record the commit it was built
   from in the "Current state" section of [HANDOFF.md](HANDOFF.md).

Keep "WIP" in the name while the story text is unedited machine translation.

A built ISO contains the whole game: hand it only to people who own the original, and
never commit or publish it.

## Public release

The released patch lives in `patch/` and is committed, so a clone or the repository ZIP
is all a player needs. To publish a new version, on a release branch:

1. `check.py` 0 errors, the harness regression, and ideally an autoplay run of every
   route ([TESTING.md](TESTING.md)).
2. Build from the committed tree: `python tools/build.py <original.iso> work/out/en.iso`.
3. `python tools/release.py <original.iso> work/out/en.iso --version 1.x`

   needs xdelta3 (PATH, `XDELTA3` or `--xdelta3`; github.com/jmacd/xdelta-gpl releases).
   It replaces `patch/` with the `.xdelta` patch, `README.txt` (apply guide, the
   original's checksum, credits), `apply-patch.bat` (drag the ISO onto it),
   `apply-patch.sh` and `SHA256SUMS.txt`, and writes the same files as
   `work/release/Kamigami-no-Asobi-EN-v1.x.zip`. It applies the patch once more and
   compares the result with the built ISO, so a broken patch never ships.
4. Update the patch file name in README.md ("Play it"), commit `patch/` as
   `chore(release): v1.x`, merge, and tag the merge `v1.x`.
5. On the hosting side, create a release for the tag and attach the ZIP.

The encoder uses a source window as large as the original ISO (`-B`): rebuilt archives
are appended at the end of the image, and with xdelta3's default 64 MB window the
patch grows from about 3 MB to over 80 MB. Decoding needs no extra option.

The build is deterministic: the same commit and original ISO give the same patched
ISO, so anyone can check a published patch by building it themselves.

The tools and translation are MIT licensed (`LICENSE`); the game itself is not.
