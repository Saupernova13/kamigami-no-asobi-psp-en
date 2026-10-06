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

```
python tools/release.py <original.iso> work/out/en.iso --version 1.0
```

needs xdelta3 (PATH, `XDELTA3` or `--xdelta3`; github.com/jmacd/xdelta-gpl releases).
It writes `work/release/Kamigami-no-Asobi-EN-v<version>/` and a zip of it: the
`.xdelta` patch, `README.txt` (apply guide, the original's checksum, credits),
`apply-patch.bat` (drag the ISO onto it), `apply-patch.sh` and `SHA256SUMS.txt`. It
applies the patch once more and compares the result with the built ISO, so a broken
patch never ships. Both apply scripts were tested end to end for v1.0.

Before a release: `check.py` 0 errors, the harness regression, and ideally an autoplay
run of every route (TESTING.md). Bump the version for every published patch.

The tools and translation are MIT licensed (`LICENSE`); the game itself is not.

