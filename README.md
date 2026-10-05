# kamigami-psp-en

Fan English translation tooling for *Kamigami no Asobi* (神々の悪戯, PSP, `NPJH50809`,
Broccoli, NIS engine). The repository holds the tools, the engine patch, the English
text and the docs; no game data. Everything is extracted from, and patched onto, your
own copy of the Japanese ISO.

New here, person or agent? Start with [AGENTS.md](AGENTS.md).

## Status

All extracted text has English, most of it **unedited machine translation**; the editing
passes are the main remaining work. The opening (title, name entry, prologue, options,
dictionary) has been played in the emulator; screens further in are patched but not yet
seen.

| Area | Units | State |
|---|---|---|
| Story script (12 files, all routes) | 37,862 | MT, in game; wrap + continuation windows verified |
| Menus, help bar, dialogs, titles, nameplates (EBOOT) | ~400 | hand translated, in game |
| Mythology quiz | 1,200 | MT, patched; not yet seen in game |
| Dictionary | 254 | MT, in game (list, entries, page-header images) |
| Mythology Monologue side stories | 6,771 | MT, patched; not yet seen in game |
| Text baked into textures | 109 textures | re-lettered; option, name entry, dictionary seen in game |
| Player name | - | default "Yui"; the name-entry kana grid is still Japanese |
| Still Japanese | - | chapter badges, season icons, name-entry grid, some title/event art |

Checker: 0 errors. Verified on PPSSPP; not yet on hardware. Details and open tasks:
[docs/HANDOFF.md](docs/HANDOFF.md). Translation packages and their state:
[docs/TRANSLATION.md](docs/TRANSLATION.md#work-packages).

## Quick start

Needs Python 3.11+ (`pip install -r requirements.txt`), pspdecrypt and armips (on PATH or
in `PSPDECRYPT` / `ARMIPS`). Full setup, the expected ISO hash and where to get each tool:
[docs/SETUP.md](docs/SETUP.md).

```
python tools/extract.py    original.iso      # story units      -> work/text/01..12.json
python tools/quiz.py       original.iso      # quiz units       -> work/text/quiz.json
python tools/dictionary.py original.iso      # dictionary units -> work/text/dictionary.json
python tools/memorial.py   original.iso      # monologue units  -> work/text/memorial.json
python tools/check.py --iso original.iso     # validate translation files (0 errors)
python tools/build.py original.iso work/out/en.iso
python tools/harness.py --core <ppsspp_libretro.dll> --out work/shots/x work/out/en.iso tests/ui.txt
```

## How it works

1. **Read** the ISO (`iso.py`), unpack the NISPACK archives (`nispack.py`), decode the
   story bytecode (`story.py`) and turn each message window, choice and title into a
   translation unit with readable tokens (`script_text.py`, `extract.py`). Quiz,
   dictionary and monologue files have their own extractors.
2. **Translate**: `translation/en/<tag>.json` maps unit ids to English markup. The first
   pass is machine translation (`translate.py`, any OpenAI-compatible endpoint); people
   and agents then edit it package by package.
3. **Patch the engine**: the EBOOT is decrypted and converted from a PRX to a static ELF
   (`prx.py`), then `asm/eboot.asm` (armips) adds proportional ASCII rendering and
   fixes the advance loops. UI strings are written in place or moved to an added ELF
   segment (`eboot_strings.py`).
4. **Build**: word-wrap pages with the game's own font metrics (`font.py`, `wrap.py`),
   rebuild the scripts and data files, re-letter textures (`imagetext.py`, `txp.py`),
   repack and write a new ISO (`build.py`).
5. **Test**: drive the real game headless through the PPSSPP libretro core and look at
   screenshots (`harness.py`, `tests/*.txt`).

## Repository layout

| Path | Contents |
|---|---|
| `tools/` | every script (table below) |
| `asm/eboot.asm` | the armips EBOOT patch |
| `translation/en/` | English: `01`-`12.json` story, `quiz`, `dictionary`, `memorial`, `eboot` (UI) |
| `translation/images.json` | texture re-lettering spec (rects + English) |
| `data/glossary.json` | names, fixed terms, character voice notes (MT prompt and style reference) |
| `tests/` | harness input scripts |
| `ghidra_scripts/` | headless Ghidra scripts for engine analysis |
| `docs/` | documentation (below) |
| `work/` | local only, gitignored: Japanese text, builds, caches, screenshots |

## Tools

| Tool | Does |
|---|---|
| `extract.py` | story units from the ISO -> `work/text/01..12.json` |
| `quiz.py`, `dictionary.py`, `memorial.py` | quiz / dictionary / Mythology Monologue units |
| `eboot_strings.py` | catalog of the EBOOT's Japanese strings (after one build) |
| `translate.py` | resumable machine translation into `translation/en/` |
| `show.py` | Japanese and English side by side, by scene or id prefix |
| `apply_edits.py` | merge an `{id: English}` edits file into a translation file |
| `check.py` | validate translations: tokens, drawable characters, widths, coverage |
| `build.py` | the whole patch: EBOOT, strings, scripts, data, images -> ISO |
| `imagetext.py` | export every texture to PNG; preview re-lettering before a build |
| `harness.py` | headless PPSSPP runner with scripted input and screenshots |
| `story.py`, `script_text.py` | script bytecode parser/builder; units <-> markup |
| `wrap.py`, `font.py` | word wrap with FontA metrics |
| `nispack.py`, `iso.py`, `txp.py`, `prx.py`, `game.py` | containers, ISO writing, textures, PRX -> ELF, file locations |

Each tool's docstring has its usage and the format it handles.

## Docs

| File | For |
|---|---|
| [AGENTS.md](AGENTS.md) | start here: reading order, rules, picking a task, definition of done |
| [docs/SETUP.md](docs/SETUP.md) | tools, ISO hash, first build, optional MT server and Ghidra |
| [docs/TRANSLATION.md](docs/TRANSLATION.md) | editing the English: units, markup, style, workflow, work packages, images |
| [docs/TESTING.md](docs/TESTING.md) | checker, build reports, the harness and its scripts, playtesting |
| [docs/HANDOFF.md](docs/HANDOFF.md) | engineering state, patch overview, open tasks, gotchas |
| [docs/FORMATS.md](docs/FORMATS.md) | this game's file formats and engine addresses |
| [docs/RELEASE.md](docs/RELEASE.md) | playtest ISOs; what a public release still needs |
| [docs/PROCESS.md](docs/PROCESS.md) | the method, for porting the approach to another PSP game |

## Legal

This project distributes no game files. Built ISOs contain the full game and are for
people who own the original; a public release will be a patch against the hash in
[docs/SETUP.md](docs/SETUP.md). No license has been chosen yet.
