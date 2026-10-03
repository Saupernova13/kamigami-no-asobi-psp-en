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

Not seen in game yet: the mythology quiz (needs a save that reaches it), choices, most
EBOOT strings, route text.

## Build and test

Needs Python 3.11+ with Pillow (and capstone for disassembly), `pspdecrypt` and `armips`
(on PATH or `PSPDECRYPT` / `ARMIPS`), and for testing the PPSSPP libretro core.

```
python tools/build.py <original.iso> work/out/en.iso
python tools/check.py --iso <original.iso>
python tools/harness.py --core <ppsspp_libretro.dll> --out work/shots/x work/out/en.iso tests/ui.txt
```

`work/build/EBOOT.ELF` (decrypted, relocated) is cached; delete it to redo. armips
rewrites `work/build/EBOOT.patched.ELF` on every build.

### Harness notes

- Scripts: `wait N`, `press BTN [frames]`, `repeat K press ...`, `shot NAME`. Circle
  confirms/advances, cross cancels, triangle opens the system menu (only once the page
  has finished typing: `wait 400` first), square hides the window.
- `tests/ui.txt`: title -> New Game -> default name -> quiz difficulty -> prologue pages.
  `tests/options.txt`: title -> Option screens. `tests/dictionary.txt`: plays to the
  first keyword (iai), opens System Menu -> Dictionary -> entry 1.
- Each `press circle 6` advances about half a page (the first press completes typing).
  ~230 presses reach the end of the prologue's first day.
- PPSSPP 1.17's software renderer crashes if the first frame runs before the async boot
  finishes: `--boot-wait` (default 10 s); raise it when the machine is busy.
- Input timing drifts with load; leave generous waits around menus.
- The system language is Japanese in the harness, so PSP system dialogs (save/load)
  show Japanese; on hardware they follow the console language.

### Machine translation

`tools/translate.py` talks to any OpenAI-compatible chat endpoint (`--endpoint`,
`--model`, or `MT_ENDPOINT` / `MT_MODEL`). It was run with a local Qwen3.6-35B-A3B on
llama.cpp (`llama-server --fit on --fit-ctx 32768 -fa on -ctk q8_0 -ctv q8_0`); a plain
llama-server on its own port is the most reliable setup. 2-6 units/s.

## Patch overview

`asm/eboot.asm` (armips) against the static EBOOT made by `tools/prx.py`:

| Patch | Where | Why |
|---|---|---|
| second byte 1 for single-byte text | `0x08875228` | 2-byte renderers stop at a zero byte |
| `AsciiAdvance` | window layout `0x0887dd98` | ink-width advance for ASCII and full-width letters; bearing shift for full-width |
| `ModeCheck` stubs | 15 sites in 5 UI loops | proportional branch for ASCII units |
| `DictAdvance` | `0x08814094` | dictionary body advance |
| code cave | `0x088a7b80` (0x280 code, rest string heap) | stubs; small strings |

Build-side: `prx.add_segment` (128 KB PT_LOAD after bss for relocated strings),
`eboot_strings.references` (pointer and lui/addiu refs), `build.patch_nameplates`.

## Open tasks

In rough priority order. Each says where to start.

1. **Images.** Many labels are textures: option values (既読のみ, 普通, デフォルト, 無効,
   有効), Voice Setting names, dictionary page headers (`dbtx00`-`79.txp` in `DATA.DAT`,
   one per entry), title-screen character cards, chapter names (序章 badge), name-entry
   labels and the bottom button hints (初期化, 決定, 中止, ...). `tools/txp.py` reads TXP
   (4/8-bit palette, swizzled) but cannot write yet: add an encoder (quantize to the
   original palette size, swizzle, keep the header), then an image pipeline
   (`work/images/` exports, edited PNGs in a gitignored folder, the build re-imports).
   Fonts for re-lettering are an art decision; keep sizes identical.
2. **`memorial*.dat` (111 files in `DATA.DAT`)**: inverted SJIS, likely the Mythology
   Monologue stories (`MEMORIAL.dat` is its screen). Format unknown: start by diffing
   headers and checking whether it is the story bytecode (0xFF markers) like `*_Story.dat`.
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
10. Profiles (`PROFILE.dat` has only textures; the text may be images or EBOOT strings).

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
