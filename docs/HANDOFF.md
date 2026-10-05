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

## Current state (2026-10-06)

- Coverage: every extracted unit has English - 37,862 story units (01-12), 1,200 quiz,
  254 dictionary, 6,771 Mythology Monologue, 103 chapter titles, the hand-written EBOOT
  UI, 130 re-lettered textures (txp and anm). `check.py`: 0 errors.
- Quality: story, quiz, dictionary and monologue are **unedited machine translation**.
  Hand-written: EBOOT UI, nameplates, chapter/event titles, image labels, the 137 long
  choices (shortened to fit). The editing passes (packages S01-S12, Q, D, M in
  [TRANSLATION.md](TRANSLATION.md)) are the main remaining translation work.
- Known and accepted: the fixed surname shows as 草薙 in the name-entry box (3-character
  slot; the surname is never inserted into text). The "Get New Story" popup cuts titles
  wider than 96 px and adds an ellipsis - the original does the same for long Japanese.
- Playtest ISOs went out at `c38c7f8` (2026-10-05) and after this pass (2026-10-06).

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

Build-side: `prx.add_segment` (128 KB PT_LOAD after bss for relocated strings),
`eboot_strings.references` (pointer and lui/addiu refs), `build.patch_nameplates`.

## Open tasks

In rough priority order. Each says where to start.

1. **Edit the machine translation** (the bulk of the remaining work): work packages in
   [TRANSLATION.md](TRANSLATION.md#work-packages).
2. **Hardware test.** Everything is verified on PPSSPP only; run a build on a PSP with
   custom firmware (memory use: the extra ELF segment is 128 KB).
3. **Release tooling.** A patch generator (xdelta3 from the original ISO) and the rest
   of the checklist in [RELEASE.md](RELEASE.md).
4. **Screens not yet seen in game**, each reachable with `tools/autoplay.py` plus a few
   presses from a saved state: the Miniature Garden's own menus and help (re-lettered),
   the Skip/audio room screens, every route other than the first one autoplay takes
   (route text is MT like the rest, so layout is the main risk).
5. **Images not surveyed:** text inside event CGs (`ci*`/`bg*` art; export with
   `imagetext.py export --art`) and the attract-mode title cards. Designer notes left
   in atlases (sizes, spacing in Japanese) are never shown; leave them.
6. **Help-bar word gap.** Spaces are the game's 8 px half space (`87 6E`), which looks a
   little wide in the help bar at its larger size; `FUN_088a1c58` measures it. Cosmetic.

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
