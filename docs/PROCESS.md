# Translating a Japanese PSP game: the process

The method used here, written so it carries over to the next game. Each phase ends with
something that can be checked; do not move on until it is.

## 0. Tools

| Tool | Use |
|---|---|
| 7-Zip | unpack the ISO for browsing |
| pspdecrypt | decrypt `EBOOT.BIN` to a plain ELF |
| Ghidra (MIPS:LE:32:default) + `ghidra_scripts/` | headless analysis: decompile all, refs, asm dumps, dead functions |
| armips | assemble EBOOT patches (`.psp`, `.open IN, OUT, base`) |
| Python 3 + Pillow + capstone | the `tools/` scripts |
| PPSSPP libretro core | `tools/harness.py` runs the game headless (software renderer) and takes screenshots |
| OpenAI-compatible LLM endpoint | `tools/translate.py` (local llama.cpp works) |

## 1. Find the text

1. Unpack the ISO and list every file with size. Text is usually in the few
   medium-sized files whose names say `story`, `script`, `msg`, `scn`, `text`.
2. Hex-dump headers. Identify containers first (magic, count, entry table) and write a
   lossless unpacker/repacker before anything else.
3. Decrypt the EBOOT and grep its strings for file names - they show what the game loads
   and which formats exist (`FontA.fnt`, `story.dat`, `%02d_Story.dat`).
4. Find the encoding: try Shift-JIS on likely text; if it is noise, try simple transforms
   (XOR 0xFF, XOR a constant, byte rotation) on a short run - a known word such as the
   heroine's name makes this quick. Utapri was SJIS with every byte inverted.
5. Search for the same strings in the EBOOT (plain and transformed): UI, names and
   system messages often live there, sometimes UTF-8 for PSP system dialogs.

Check: you can print readable Japanese for a whole script file.

## 2. Understand the script format

1. Look for the framing: instruction markers, length fields, back-links.
2. Write a parser that walks every byte of every file. Desync = wrong model; fix the
   model, never skip.
3. Make **parse -> build reproduce the input byte for byte** for every file. This is the
   gate for everything after it.
4. Classify opcodes by what follows them (text, other opcodes) and by statistics.
   Identify: window open / line break / wait / page end, speaker, name variables,
   choices, jumps. Confirm jumps are by id, not byte offset - if by offset, the builder
   must relocate them.

Check: round trip exact; every text-bearing opcode explained.

## 3. Extract to translation units

- Unit = what a translator should see at once: a message page, a choice label, a title.
- Inline control codes become readable tokens (`{NAME}`, `{kw:ID:TEXT}`, `{op:...}`) so
  the text stays editable and lossless.
- Ids must be stable for a given original (`<scene>/p<n>`), and the extractor reads the
  original ISO directly so no Japanese ever needs committing.
- Applying the Japanese markup back must also be byte-exact.

## 3b. If the EBOOT is a PRX

Check `e_type`: 0x0002 is a static ELF (patch directly); 0xFFA0 is a relocatable PRX
linked at 0. Patching a PRX in place is fragile because the loader rewrites every
relocated word. `tools/prx.py` applies the relocations for 0x08804000 (where the main
module loads) and emits a static ELF; analyse and patch that. Confirm it boots before
patching anything.

## 3c. Reusing work from a related game

Games on the same engine usually share the bytecode and text path. Port by matching
decompiled patterns, not addresses: the VM's `^ 0xFF` text decoder, the `< 0x2a8` glyph
buffer append, the space-width special cases (`0x8140`, `0x20`, `0x876e`). Expect small
format changes (Kamigami's keyword opcode gained a flag byte and moved after its word) -
the byte-exact round trip finds them immediately.

## 4. Make the engine show English

1. Put a test string in a real page, build, run the harness, look at the screenshot.
2. If ASCII is missing, garbled or monospaced, follow the text path in Ghidra:
   VM text handler -> glyph buffer -> draw loop -> glyph lookup -> metrics. Font files
   with per-glyph bearings mean a proportional renderer already exists somewhere.
3. Patch with armips. Code caves: functions with no references, whose address never
   appears as a word, as a `jal`/`j` target, or as a `lui`/`addiu` pair. Verify all four.
4. Measure the window in the emulator (line width, lines per window) and feed those
   numbers to the word wrapper. Long pages continue in a new window, built from the
   game's own page opcodes.

Check: screenshots of narrow letters (`I l i`), a long line, a 3-line page, a split
page, a nameplate, a system dialog.

## 5. Translate

`tools/translate.py` batches units per scene with a few previous lines as context,
sends JSON items (`speaker`, `jp`) and expects a JSON array back, then repairs quotes,
restores tokens and rejects output with Japanese left. It is resumable: stop at any time,
run again to continue; delete an entry to redo it.

- Put names, terms and character voice in `data/glossary.json` before the run.
- Run a 50-unit pilot, read it, fix the prompt, delete the pilot output, then run all.
- Detach long runs (`Start-Process ... -WindowStyle Hidden`) and watch the log.
- Problems go to `work/mt_problems.log`; review those units by hand.
- UI and EBOOT strings are short and few: translate them by hand, checking each fits.

## 6. Build and test

`tools/build.py <original.iso> <out.iso>` decrypts and patches the EBOOT, applies EBOOT
strings, wraps and inserts script text, repacks archives and writes the ISO. It reports
pages that needed a second window, lines that are still too wide and EBOOT strings that do
not fit. Then run the harness scripts in `tests/` and look at every screenshot.

## Repository rules

- No game data in git: `work/` holds the ISO extraction, Japanese text, caches, builds.
- Commit tools, patches, docs and English translations only.
- Findings go in `docs/FORMATS.md` as they are made, with addresses.
