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
spaces 8 px. The draw already offsets ASCII glyphs by their left bearing, so for those the
patch only supplies the advance; shifting the entry x as well puts narrow glyphs
(`! ' i l I`) on top of the previous letter. Full-width letters and digits (`82 4F`-`82 9A`,
what player names are typed in) are drawn at their cell origin, so the patch measures
them too and moves their entry x left by the bearing. With the patch, English renders proportionally in the message
window (verified in the emulator). Window: 3 lines of ~390 px.

The backlog takes its code from the same emitter call, so the one hi-byte patch covers it.

## UI strings (`tools/eboot_strings.py`, `tools/build.py`)

The UI loops step 2 bytes and stop at a zero byte, so English is stored as `(c, 0x01)`
pairs (`build.encode_ui`); a space is the 8 px half space `87 6E` (the game uses it too,
shown as `㌻` by cp932), and printf specifiers and `
`/`	` stay single bytes for the
code that formats them. The loops reload a fixed/proportional flag from the stack; the
patch replaces each reload with a call that reports "proportional" for an ASCII unit (15
sites in 5 loops, listed in `asm/eboot.asm`).

Room: a pair-encoded string is twice as long as its ASCII, so most English does not fit
in place. `eboot_strings.references` finds what points at each string: data words (251
strings) and `lui`/`addiu` or `lui`/`ori` pairs that can be repointed alone (117). Those
strings move to an extra PT_LOAD segment that `prx.add_segment` appends after bss
(128 KB at `0x08c4ab00`; the loader reserves it as part of the module). Strings nothing
points to are char arrays inside records (32 or 64 bytes: quiz options, song and event
titles, Garden objects); the catalog's `field` gives that room. The current table moves
259 strings and fits everything else in place.

Dialog boxes cut a line after a fixed number of 2-byte units (the name confirm dialog
shows 20), so dialog prompts must stay short. Help-bar lines are not cut.

## Nameplates

`0x08964b54`: `{u32 id, char *name}` pairs, ending with id 9999. `build.patch_nameplates`
repacks every name (English where `eboot.json` has a `nameplates` entry) into the
original pool, then the cave tail, then the extra segment, and repoints the table.
Verified in the emulator ("Father").

## Player name

Name entry keeps a `u16[10]` at `0x0896630e`: surname 3 characters, given name 3,
nickname 4, copied into 32-byte buffers at `0x089ef088` (`FUN_08805c48`). Only the given
name is used in the script (`{NAME}`, 130 lines); the surname is fixed and appears as
literal text. The name pipeline reads SJIS characters, so `(c, 0x01)` pairs break it; the
defaults are full-width (`Ｙｕｉ`), which the window patch renders proportionally. The
surname slot cannot hold "Kusanagi", so the heroine's nameplate (`%s㌻%s` at
`0x08929974`) and backlog speaker (`【%s㌻%s】` at `0x08924d38`) become `%.0s%s`: given
name only.

## Mythology quiz (`tools/quiz.py`)

`DATA.DAT` -> `QUIZ.dat` (a nested NISPACK) -> eight files of 23,016 bytes:
`4quiz00`-`03` (four choices) and `tfquiz00`-`03` (true/false). Each: `u32` header size
(0x1a0), three `u32` question counts (15 + 20 + 15), 50 `{u32 id, u32 offset}` pairs, then
50 records of `u32 id`, three 64-byte question lines and four 64-byte choices, all
zero-padded SJIS. The first choice is the right answer; true/false records keep their
answer key (a circle or cross) in choice 0, which stays untouched. English is stored as
`(c, 0x01)` pairs, so a field holds 31 characters; the build wraps questions at 320 px
(the widest Japanese line) and narrower until every line fits. 400 questions, 1,000
choices. Not yet checked in the emulator (the quiz is not reachable from a new game
without a save).

## Not done yet

- Name entry screen: the kana grid and labels are still Japanese; Latin needs the
  grid's full-width page. Full-width names in UI loops (nameplate, name entry) are
  still fixed width.
- UI centering: the width loops (`FUN_0888a3b0`, `FUN_0888a6a4`, `FUN_0888a7b0`,
  `FUN_0888a4ac`) still measure fixed widths, so centered English sits a little off.
- `0x0892855c` (read rates screen) mixes single-byte ASCII into a UI string in the
  original; check that its renderer takes pairs.
- Dictionary, profiles, `memorial*.dat`, Garden/gallery screens, images (option values,
  voice-setting names and menu labels are textures).
