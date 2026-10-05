# Engineering handoff

State of the reverse engineering and the open tasks, for whoever picks this up next.
Formats and addresses are in [FORMATS.md](FORMATS.md), the general method in
[PROCESS.md](PROCESS.md), translation editing in [TRANSLATION.md](TRANSLATION.md).

## What works (verified in the emulator)

- Story text in the message window: proportional ASCII, word wrap at 390 px, 3 lines,
  automatic continuation windows, `!`/`'`/narrow glyphs placed correctly.
- Nameplates (all speakers, repacked), the heroine's nameplate as her given name.
- Player name: default "Yui" (full-width, so name entry and the script accept it),
  rendered proportionally in the window; `{NAME}` / `{NICK}` inserts.
- UI strings: menus' help bar, dialogs, quiz-difficulty prompt, Yes/No, option help,
  system menu help, dictionary list. Long strings move to an extra ELF segment.
- Dictionary: titles in the list, entry bodies (proportional, scrolling).
- Build: `tools/build.py` makes a full English ISO from the original in seconds once the
  EBOOT is decrypted; `tools/check.py` validates all translation files.

Not seen in game yet: the Mythology Monologue screen, chapter select, the mythology quiz (needs a save that reaches it), choices, most
EBOOT strings, route text.

## Current state (2026-10-05)

- Coverage: every extracted unit has English - 37,862 story units (01-12), 1,200 quiz,
  254 dictionary, 6,771 Mythology Monologue, the hand-written EBOOT UI, 109 re-lettered
  textures. `check.py`: 0 errors, 14 warnings (memorial name tokens turned into pronouns).
- Quality: story, quiz, dictionary and monologue are **unedited machine translation**.
  Hand-written: EBOOT UI, nameplates, event/chapter titles, image labels. The editing
  passes (packages S01-S12, Q, D, M in [TRANSLATION.md](TRANSLATION.md)) are the main
  remaining translation work; none has been merged yet.
- The first playtest ISO went out at this state (built from `feat/text-pipeline` at
  `49bf49b`). Playtest reports are the fastest way to find the in-game checks below.

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
| `DictAdvance` | `0x08814094` | dictionary body advance |
| code cave | `0x088a7b80` (0x300 code, rest string heap) | stubs; small strings |

Build-side: `prx.add_segment` (128 KB PT_LOAD after bss for relocated strings),
`eboot_strings.references` (pointer and lui/addiu refs), `build.patch_nameplates`.

## Open tasks

In rough priority order. Each says where to start.

1. **Images (package IMG, mostly done).** Text baked into textures is re-lettered from
   `translation/images.json` by `tools/imagetext.py` (see its docstring and
   [TRANSLATION.md](TRANSLATION.md#images)). Checked in game: option values and hint
   bar, decision button, name-entry labels and hints, dictionary page headers (all 80,
   generated from the dictionary titles). Done, not yet seen in game: chapter select
   (86 titles, tabs, name tags, labels), gallery tags and hints, Garden menu/help/hints,
   audio room help, skip hints, profile (stats table, name banners, vertical myth
   labels), backlog hints, sub-menu help. Still Japanese:
   - `START.DAT/systemMenu_ChapterIcons.txp` (序章, 第1章 ... badges) and the season
     icons 春 夏 秋 冬 in `DATA.DAT/SKIP.dat`: calligraphic art, an art decision.
   - Designer notes left in atlases (sizes, spacing): never shown, leave them.
   - Title-screen character cards (attract mode) and text inside event CGs: not surveyed.
2. **Mythology Monologue (done, MT).** `tools/memorial.py`: the 111 `memorial*.dat` files
   use the dictionary layout; the body renderer `FUN_088233c4` shares `DictAdvance`.
   `MEMORIAL_LINE_PX` (330) is a guess from the Japanese line length: check in game once a
   monologue is unlocked, and fix titles that come out too long.
3. **Quiz in game.** Reach the quiz (it is in the story after the prologue, or Extra after
   a clear) and check line layout; adjust `QUIZ_LINE_PX` in `tools/build.py`.
4. **Choices.** Check the choice box width with a long English choice; add a limit to
   `check.py`.
5. **Name entry screen.** Kana grid and labels are Japanese; slots are 3/3/4 full-width
   characters (`u16[10]` at `0x0896630e`). An English grid would need the grid data
   (in the name-entry screen code/`NAME.dat`) and probably longer slots.
6. **UI centering.** The width loops (`FUN_0888a3b0`, `FUN_0888a6a4`, `FUN_0888a7b0`,
   `FUN_0888a4ac`) still measure fixed widths, so centered English is offset. Same
   ModeCheck approach as the draw loops.
7. **Help-bar tracking.** `FUN_08889b2c`'s proportional path adds 2 px per glyph, which
   looks loose for English; patch the `+ 2` for ASCII units.
8. **Full-width names in UI loops** (nameplate "Y u i", name entry) are fixed width;
   extend the ModeCheck stubs to `82 4F`-`82 9A`, with the bearing shift `AsciiAdvance`
   does.
9. `0x0892855c` (read-rate screen) mixes single-byte ASCII into a UI string in the
   original; confirm its renderer accepts pairs.
10. Profiles: `PROFILE.dat` is textures only and its labels are re-lettered (item 1);
    check in game whether any profile text comes from EBOOT strings still in Japanese.
11. **Release tooling.** A patch generator (xdelta3 from the original ISO) and the rest
    of the checklist in [RELEASE.md](RELEASE.md).

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
