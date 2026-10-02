# kamigami-psp-en

English translation tooling for *Kamigami no Asobi InFinite / Ludere deorum* (PSP,
Broccoli, NIS engine). Built on the method and tools from utapri-psp-en. No game data
lives in this repository; everything is extracted from your own ISO.

## Status

| Step | State |
|---|---|
| Archives (NISPACK) unpacked | done |
| Script decoded, 12 files round-trip byte-exact | done |
| Text extraction (37,862 units) | done |
| EBOOT: PRX converted to a patchable static ELF | done, boots |
| English in the message window (proportional) | done, verified in emulator |
| Word wrap + window continuation | done (390 px, 3 lines) |
| Glossary | done (`data/glossary.json`) |
| Machine translation | ready, not run (local LLM could not start: C: full) |
| UI / EBOOT strings, nameplates | catalogued, not translated |
| Name entry, quiz, dictionary, images | not started |

## Use

Needs Python 3.11+ with Pillow, pspdecrypt and armips (PATH, or `PSPDECRYPT` / `ARMIPS`).

```
python tools/extract.py original.iso            # Japanese units -> work/text/
python tools/translate.py                       # MT, resumable -> translation/en/
python tools/build.py original.iso english.iso  # patched ISO
```

Test headless:

```
python tools/harness.py --core <ppsspp_libretro.dll> --assets <PPSSPP assets> english.iso tests/prologue.txt
```

## Docs

- [docs/PROCESS.md](docs/PROCESS.md) - the method for any PSP game
- [docs/FORMATS.md](docs/FORMATS.md) - this game's formats and the engine patch
