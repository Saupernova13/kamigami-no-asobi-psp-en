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

## Public release (not done yet)

A public release must be a **patch**, not an ISO. What is still needed:

- [ ] Editing passes merged for at least S01, S02, U, Q, D (see the work packages in
      [TRANSLATION.md](TRANSLATION.md)).
- [ ] The in-game checks in [HANDOFF.md](HANDOFF.md) open tasks done (quiz, choices,
      chapter select, Mythology Monologue).
- [ ] Tested on real hardware (custom firmware) as well as PPSSPP.
- [ ] A patch generator: an xdelta3 (VCDIFF) patch from the original ISO (hash in
      [SETUP.md](SETUP.md)) to the built one, plus a short apply guide (xdelta UI on
      Windows, `xdelta3 -d -s original.iso patch.xdelta out.iso` elsewhere). Building
      it is one command; it is not scripted in `tools/` yet.
- [ ] A license chosen for the tools and the translation (the repository has none yet).
- [ ] Credits: translators/editors per package, the tools this builds on (armips,
      pspdecrypt, PPSSPP).
