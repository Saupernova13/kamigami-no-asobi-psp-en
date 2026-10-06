# Engineering handoff

State of the reverse engineering and the open tasks, for whoever picks this up next.
Formats and addresses are in [FORMATS.md](FORMATS.md), the general method in
[PROCESS.md](PROCESS.md), translation editing in [TRANSLATION.md](TRANSLATION.md).

## What works (verified in the emulator)

Seen in harness screenshots, on a new game and on a full route played to its ending with
`tools/autoplay.py` (see [TESTING.md](TESTING.md)):

- Story text: proportional ASCII, word wrap at 390 px, 3 lines, continuation windows.
- Choices ("Select the phrase", "Thread of fate"): proportional, labels up to 32 characters.
- Nameplates; the heroine's nameplate is her given name. Player name defaults to "Yui";
  name entry opens on its ABC page.
- UI strings: help bar, dialogs (unlock notices, save prompts), Yes/No, options, system
  menu, key config, quiz setting. Centred text is centred (width loops patched).
- Mythology quiz (four-choice and true/false), quiz prep and result screens.
- Chapter cards (the typed chapter title), chapter select, the "To the next chapter"
  screens, the ending ("fin.") and credits roll.
- Extra: Miniature Garden title, Profile, Graphic, Music, Dictionary (list, entries),
  Mythology Monologue (list and story pages), Mythology Quiz title and setting.

## Current state (2026-10-06, v1.0)

- Coverage: every extracted unit has English - 37,862 story units (01-12), 1,200 quiz,
  254 dictionary, 6,771 Mythology Monologue, 103 chapter titles, the hand-written EBOOT
  UI, 135 re-lettered textures (txp and anm). `check.py`: 0 errors, 0 warnings.
- Every texture (txp, anm, and the 152 event CGs) was reviewed; what is not re-lettered
  is English already, art without text, or designer notes the game never shows.
- In the emulator: Apollon, Hades and Anubis played to their endings; Tsukito, Takeru,
  Balder, Loki and Thoth played 50-130 autoplay steps into the route (autoplay then
  wandered into a menu; no patch problem seen). Plus all Extra screens and the Garden.
- Quality: story, quiz, dictionary and monologue are **machine translation** with an
  automatic cleanup (tokens, keyword terms, names, line fits). The editing passes in
  [TRANSLATION.md](TRANSLATION.md) are the way to improve it further.
- The fixed surname is a full-width space: the game requires one and "Kusanagi" does
  not fit its 3-character slot; the script never prints it.
- The "Get New Story" popup cuts titles wider than 96 px with an ellipsis, as the
  original does for long Japanese.
- Release v1.0: the xdelta3 patch, apply scripts and checksums are in `patch/`, made by
  `tools/release.py`; see [RELEASE.md](RELEASE.md). The build is deterministic.

## Build and test

Setup from zero, the ISO hash and the first build: [SETUP.md](SETUP.md). Checker, build
reports and the harness: [TESTING.md](TESTING.md). Playtest ISOs and what a release
still needs: [RELEASE.md](RELEASE.md). Machine translation server: SETUP.md section 5.

`work/build/EBOOT.ELF` (decrypted, relocated) is cached; delete it to redo. armips
rewrites `work/build/EBOOT.patched.ELF` on every build.

## Patch overview

`asm/eboot.asm` (armips) against the static EBOOT made by `tools/prx.py`:

| Patch | Where | Why |
|---|---|---|
| second byte 1 for single-byte text | `0x08875228` | 2-byte renderers stop at a zero byte |
| `AsciiAdvance` | window layout `0x0887dd98` | ink-width advance for ASCII and full-width letters; bearing shift for full-width |
| `ModeCheck` stubs | 15 sites in 5 UI loops | proportional branch for ASCII units |
| `DictAdvance` | `0x08814094`, `0x0882369c` | dictionary and monologue body advance |
| `ChoiceAdvance` | 4 sites in `FUN_08871678` / `FUN_088753fc` | choice label advance |
| width-loop `ModeCheck` | `FUN_0888a7b0`, `FUN_0888a6a4`, `FUN_0888a4ac`, `FUN_088907dc` | centred English measured proportionally |
| `UI_SPACING` | 9 sites in the UI draw and width loops | 1 px between glyphs instead of 2 |
| name entry mode | `0x088156cc`, `0x088156e4` | opens on the ABC page |
| code cave | `0x088a7b80` (0x300 code, rest string heap) | stubs; small strings |

Keyword markers (`op 0x7DD`) carry the term the "Get New Word" popup shows; the popup
draws it with a 2-byte UI loop, so `script_text` stores English terms pair-encoded.

Build-side: `prx.add_segment` (128 KB PT_LOAD after bss for relocated strings),
`eboot_strings.references` (pointer and lui/addiu refs), `build.patch_nameplates`.

## Open tasks

1. **Edit the machine translation** (optional quality work): work packages in
   [TRANSLATION.md](TRANSLATION.md#work-packages). Rebuild and release a new version
   with `tools/release.py --version 1.x`.
2. **Hardware test.** Verified on PPSSPP; a run on a PSP with custom firmware is still
   welcome (memory use: the extra ELF segment is 128 KB).

## Gotchas

- Japanese source text, ISOs and binaries never go in git (`work/` is ignored).
- Strings for the UI must be pair-encoded (`build.encode_ui`); the story VM takes plain
  ASCII. printf specifiers stay single bytes.
- A string nothing points to is a char array in a record: only its field size is
  available (`field` in the catalog). Anything referenced can move to the extra segment.
- The dictionary's `u16` at +6 is the line count the scroll bar uses; keep it in step.
- Keyword tokens carry a flag: `{kw:ID:FLAG:TEXT}` (Utapri's had none).
- When writing Python through a shell heredoc, backslash escapes (`\n`, `\0`) can be
  turned into raw characters by the shell layer; prefer an editor, and scan sources for
  NUL bytes if in doubt.
