# Kamigami no Asobi PSP: formats and engine notes

Same NIS engine family as *Uta no Prince-sama* (see the utapri-psp-en repo); this file
records what differs. Addresses are runtime addresses in the static EBOOT made by
`tools/prx.py` (module at 0x08804000, file offset 0xC0).

## Disc layout

| ISO path | Contents |
|---|---|
| `PSP_GAME/SYSDIR/EBOOT.BIN` | encrypted **PRX** (relocatable, linked at 0) |
| `PSP_GAME/USRDIR/DATA01..12.DAT` | NISPACK: `NN_Story.dat` (script), `NN_Story.did`, `NN_Keyword.dat` (01-09) |
| `PSP_GAME/USRDIR/TITLE01..11.DAT` | NISPACK: `NN_Selecter.dat`, `NN_Story.did` |
| `PSP_GAME/USRDIR/START.DAT` | NISPACK: `fontA.fnt/.ftd`, font sheets, `common.dat`, `00_Selecter.dat`, icons |
| `PSP_GAME/USRDIR/DATA.DAT` | NISPACK: `memorial*.dat`, `QUIZSETTING.dat`, `GARDEN.dat`, `GALLERY.dat`, textures |
| `PSP_GAME/USRDIR/SOUNDMSG.DAT`, `SOUNDBGMSE.DAT` | voice / music banks |
| `PSP_GAME/INSDIR/DATA.DAT` | data for the "Data Install" option |

There is no `story.dat` in START.DAT here; the prologue is in `01_Story.dat`.

## The EBOOT is a PRX (`tools/prx.py`)

`e_type` 0xFFA0, two PT_LOAD segments at 0 (code+data, then bss) and a plain `Elf32_Rel`
table in PT 0x700000A0 (38,925 entries: R_MIPS_26, HI16, LO16, 32). `prx.py` applies the
relocations for 0x08804000 the way PPSSPP does, marks the file ET_EXEC and drops the
relocation headers. The result boots in PPSSPP and patches like a static ELF. Verified: a
`lui/addiu` pair resolves to the `FontA.fnt` string at 0x0892482c.

The code is unoptimised (`-O0`): locals live on the stack, functions are longer, and
there are at least 11 separate 2-byte string loops (`FUN_08889b2c`, `FUN_08889cbc`,
`FUN_0888a028`, `FUN_0888a3b0`, `FUN_0888a6a4`, `FUN_0888a7b0`, `FUN_0888ab70`,
`FUN_0888ad18`, `FUN_0888fe8c`, `FUN_08890550`, `FUN_088907dc`).

## Story script

Bytecode identical to Utapri (`tools/story.py`); all 12 files round-trip byte-exactly.
Totals: 37,142 pages, 720 choices; 34,691 unique strings, ~940k characters. Japanese
pages have up to 3 lines, max 311 px.

One difference: the keyword op `0x7DD` is `u16 id, u8 flag, u8 len, text` and comes
**after** the word it tags (`"...ゼウス" {kw:2:1:ゼウス} "。"`). Markup: `{kw:ID:FLAG:TEXT}`.
Flag is 1 or 0 (92 each).

## Text rendering and the patch (`asm/eboot.asm`)

| Role | Utapri | Kamigami |
|---|---|---|
| VM text path | `FUN_0884da54` | `FUN_08871678` |
| single-byte emit, hi byte | `0x088505ac` | `0x08875228` (`FUN_08862f20(.., c, 0)`) |
| window glyph append | `FUN_08856384` | `FUN_0887dcd8` (table `0x089ad410`, count `+0x1aa0`, cursor `+0x2d28`) |
| fixed advance call | `0x088564d4` | `0x0887dd98` (`FUN_0888a998`) |
| FontA width(code, %) | `FUN_088669b0` | `FUN_088a1690` |
| glyph index | `FUN_088672c4` | `FUN_088a2128` -> `FUN_088a216c` (ignores 2nd byte for 0x20-0x7E) |
| FontA.ftd pointer | `0x08b5dbb8` | `0x08996934` |
| code cave | `FUN_0880d2b0` | `FUN_088a7b80` (1,076 B, dead) |

The font here uses 18 px cells drawn at 16 px: advance = `int((18 - l - r) * 16/18 + 0.5)`,
spaces 8 px. With the patch, English renders proportionally in the message window
(verified in the emulator). Window: 3 lines of ~390 px.

The backlog takes its code from the same emitter call, so the one hi-byte patch covers it.

## Nameplates

`0x08964b54`: `{u32 id, char *name}` pairs, ending with id 9999. Because these are
pointers, long English names can live anywhere (not done yet). Ids are listed in
`data/glossary.json`.

## Not done yet

- UI/EBOOT strings: catalog exists (`tools/eboot_strings.py`, 774 unique), no English yet.
  The 11 string loops still stop at a zero byte, so UI English must either use the
  `(c, 0x01)` pair encoding or get the Utapri-style `CharAt` loop patch.
- Translation run: the pipeline works, but the run was blocked by the local LLM failing to
  start while C: was full.
- Name entry (kana grid), quiz data, keywords/dictionary, `memorial*.dat`, images.
