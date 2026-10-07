# Setup from zero

Everything needed to go from a fresh clone to a patched, tested ISO. Nothing here is
machine-specific; put your own paths in environment variables, never in the repository.

## 1. The game

You need your own dump of the Japanese UMD. The tools read it directly and never modify
it. The build was made against this one:

| | |
|---|---|
| Disc id | `NPJH50809` (PARAM.SFO `DISC_ID`), `DISC_VERSION` 1.01, title 神々の悪戯 |
| Size | 1,445,789,696 bytes |
| SHA-256 | `DED26F15C287D26D91EFBDB1BA78D1B5CA46939636A5711750ED2007803AFE16` |
| MD5 | `E89406C87DBFF5B34812A8355E3ECEC2` |

```
certutil -hashfile original.iso SHA256      # Windows
sha256sum original.iso                       # Linux / macOS
```

A different dump or revision may still work (the extractors check every file's layout),
but unit ids and EBOOT addresses are only verified for this one. Never commit the ISO or
anything extracted from it (`.gitignore` covers `work/`, `*.iso`, `*.DAT`, `*.ELF`).

## 2. Tools

| Tool | Needed for | Where | How the tools find it |
|---|---|---|---|
| Python 3.11+ | everything | python.org | `python` on PATH |
| Pillow | textures, harness screenshots | `pip install -r requirements.txt` | import |
| pspdecrypt | decrypting `EBOOT.BIN` (build) | github.com/John-K/pspdecrypt releases | PATH, `PSPDECRYPT`, or `--pspdecrypt` |
| armips | assembling `asm/eboot.asm` (build) | github.com/Kingcom/armips releases (or build it) | PATH, `ARMIPS`, or `--armips` |
| PPSSPP libretro core | headless testing | buildbot.libretro.com nightly, `ppsspp_libretro.dll/.so`, or RetroArch's core folder | `--core` |
| PPSSPP (desktop) | playing the result by hand | ppsspp.org | - |
| xdelta3 | making a release patch | github.com/jmacd/xdelta-gpl releases | PATH, `XDELTA3`, or `--xdelta3` |
| Ghidra 11+ | reverse engineering only | ghidra-sre.org | see below |
| An OpenAI-compatible chat endpoint | machine translation only | a hosted API, or a local server (llama.cpp, Ollama, LM Studio, vLLM) | `--endpoint` / `MT_ENDPOINT` |

`build.py` fails at once with "pspdecrypt not found" or "armips not found" if either is
missing; that is the most common first-run error.

PowerShell:

```
$env:PSPDECRYPT = "<path>\pspdecrypt.exe"
$env:ARMIPS     = "<path>\armips.exe"
```

bash:

```
export PSPDECRYPT=/path/to/pspdecrypt ARMIPS=/path/to/armips
```

## 3. First build

From the repository root:

```
pip install -r requirements.txt
python tools/extract.py    <original.iso>        # story units  -> work/text/01..12.json
python tools/quiz.py       <original.iso>        # quiz         -> work/text/quiz.json
python tools/dictionary.py <original.iso>        # dictionary   -> work/text/dictionary.json
python tools/memorial.py   <original.iso>        # monologues   -> work/text/memorial.json
python tools/selecter.py   <original.iso>        # chapters     -> work/text/selecter.json
python tools/check.py --iso <original.iso>       # must end with "0 errors"
python tools/build.py <original.iso> work/out/en.iso
```

The extract steps take seconds and only need repeating if the extractors change. The
first build decrypts and relocates the EBOOT into `work/build/` (cached afterwards); a
build then takes well under a minute. Expected tail of the build output:

```
wrote work/out/en.iso: 46087 script units applied, ... long pages continued in a second window
  109 textures re-lettered
  261 EBOOT strings moved to the extra segment
```

The numbers grow as work lands. "lines still too wide" or "does not fit" lines are
reports, not failures: they name units to shorten.

After the first build, the UI string catalog (the Japanese side of `eboot.json`) can be
made with:

```
python tools/eboot_strings.py work/build/EBOOT.ELF   # -> work/text/eboot.json
```

## 4. Test it

```
python tools/harness.py --core <ppsspp_libretro.dll> --out work/shots/first work/out/en.iso tests/ui.txt
```

Then open `work/shots/first/*.png`. See [TESTING.md](TESTING.md) for what each script
covers and how to write new ones. To play normally, load `work/out/en.iso` in PPSSPP.

## 5. Optional: a translation endpoint

Only needed to (re)translate units. `tools/translate.py` posts to any OpenAI-compatible
`/v1/chat/completions` endpoint and does not care what serves it: a hosted API, or a model
running on your own machine under llama.cpp, Ollama, LM Studio or vLLM.

```
python tools/translate.py --endpoint <base URL>/v1 --model <model name> --tags 04
```

`MT_ENDPOINT` and `MT_MODEL` set the defaults. A hosted API that wants a key reads it from
`MT_API_KEY` (or `--api-key`), sent as a bearer token. The built-in default,
`http://127.0.0.1:8080/v1`, is only where a local `llama-server` happens to listen.

By default the request carries `chat_template_kwargs`, a llama.cpp and vLLM extension that
turns a thinking model's reasoning off. An API that validates its request body strictly
rejects it; pass `--plain-request` to send standard fields only.

The setup behind v1.0 is one option, not a requirement, and yours will likely look
nothing like it: Qwen3.6-35B-A3B (Q4_K_M GGUF) under llama.cpp on a single desktop GPU,
started as

```
llama-server -m <model.gguf> --fit on --fit-ctx 32768 -np 1 -fa on -ctk q8_0 -ctv q8_0 --host 127.0.0.1 --port <port>
```

which gave 2-6 units/s. Another model, a hosted API or another machine will differ in
speed and in the English it writes, so run the 50-unit pilot in
[TRANSLATION.md](TRANSLATION.md) and read it before starting a full run. Runs are
resumable; detach long ones and watch the log rather than blocking a shell on them.

## 6. Optional: Ghidra

For engine work. Import `work/build/EBOOT.ELF` (made by the first build; a static ELF at
0x08804000) as MIPS:LE:32:default, run auto-analysis, then use the headless scripts in
`ghidra_scripts/`:

| Script | Args | Output |
|---|---|---|
| `DecompAll.java` | outfile | every function decompiled into one C file, for grepping |
| `DecompRefs.java` | outfile token... | functions that reference a string or `0xADDR` |
| `DumpAsm.java` | outfile 0xADDR... | disassembly of the functions at those addresses |
| `ListUnref.java` | outfile | functions with no references (code cave candidates) |

```
analyzeHeadless <project dir> <name> -process EBOOT.ELF -noanalysis -scriptPath ghidra_scripts -postScript DecompRefs.java work/refs.c 0x0887dd98
```

Addresses in the docs and `asm/eboot.asm` are runtime addresses in that ELF.
