# Translation guide and work packages

For anyone (person or agent) improving the English. The whole game already has a first
machine translation; the work now is editing it into a good translation, one package at
a time. Engineering work (formats, patches, images) is in [HANDOFF.md](HANDOFF.md).

## Where the text lives

| File | What | Units | Japanese source (local, not committed) |
|---|---|---|---|
| `translation/en/01.json` ... `12.json` | story script, one file per `DATAnn.DAT` | 37,862 | `work/text/01.json` ... `12.json` |
| `translation/en/quiz.json` | mythology quiz questions and choices | 1,200 | `work/text/quiz.json` |
| `translation/en/dictionary.json` | dictionary titles, headings, entries | 254 | `work/text/dictionary.json` |
| `translation/en/eboot.json` | menus, help bar, dialogs, chapter/event/song titles, nameplates | ~400 | `work/text/eboot.json` (catalog) |

Make the Japanese files once from your own ISO (they hold the game's script, so they never
go in git):

```
python tools/extract.py <original.iso>          # work/text/01..12.json
python tools/quiz.py <original.iso>             # work/text/quiz.json
python tools/dictionary.py <original.iso>       # work/text/dictionary.json
python tools/eboot_strings.py work/build/EBOOT.ELF   # after one build; UI catalog
```

Translation files map a unit id to English: `{"10001/p3": "English markup", ...}`, one
unit per line, so edits to different units merge cleanly in git.

## Unit ids

| Id | Meaning |
|---|---|
| `10001/p3` | scene 10001, page 3: one message-window page (speaker in the Japanese file) |
| `10001/c0` | scene 10001, choice 0 |
| `10001/a0` | scene 10001, other text argument (titles, system text) |
| `4quiz00/101/q`, `.../c0`-`c3` | quiz question, answer choices (`c0` is the right answer) |
| `dict/12/t`, `/h0`, `/p0` | dictionary title, section heading, paragraph |
| `0x08925820` | EBOOT string at that address; `nameplates` holds speaker names by id |

## Markup rules

Text is plain English with these tokens, which must survive every edit exactly as in the
Japanese (the checker enforces it):

| Token | Meaning | Rule |
|---|---|---|
| `{NAME}` | player's given name (default Yui) | keep; e.g. `{NAME} Kusanagi` |
| `{NICK}` | player's nickname (default Yui) | keep |
| `{SURNAME}` | player's surname | rare; the surname is fixed, write `Kusanagi` instead where it is literal text |
| `{kw:ID:FLAG:TEXT}` | dictionary keyword (unlocks entry ID) | keep ID and FLAG; put it just before the English term and set TEXT to that term, e.g. `{kw:1:1:iai}iai`; TEXT may be empty |
| `{op:XXXX:HEX}` | other inline engine instruction | keep as is, same position in the sentence |
| `\f` | force a new message window | optional; the build already splits long pages |
| `\n` | hard line break | avoid: a page with any `\n` is taken as laid out by hand and not re-wrapped |

Characters: the font has printable ASCII plus Japanese full-width glyphs. Use straight
quotes `"` and `'`, `...` for ellipses, `-` for dashes, `~` for a sung or lilting tone.
No curly quotes, em dashes, accented letters (`Ragnarok`, `Laevateinn`) or emoji. The
checker lists anything the game cannot draw.

Lengths (the build wraps and reports overflow; the checker warns early):

- Story pages: 3 lines of ~390 px per window (about 55 characters a line). Longer pages
  continue in a second window automatically; keep it to two windows where possible.
- Choices: short, one line (under ~35 characters).
- Quiz: question up to 3 lines of 31 characters; each choice under 31 characters, no
  final period. Keep `c0` the correct answer.
- Dictionary: titles under 31 characters; paragraphs wrap freely (the page scrolls).
- EBOOT strings: dialog prompts are cut after ~20 characters a line (the name confirm
  dialog showed "Is this OK? Please c"); keep them short. Help-bar lines can be longer.

## Style

`data/glossary.json` is the reference: speaker names, fixed terms (`箱庭` = Garden,
`草薙` = Kusanagi, ...) and voice notes per character (Apollon sunny and clingy, Hades
gloomy, Takeru rough, Tsukito formal and literal, Loki a trickster, Anubis growls, Thoth
cold and sarcastic, Zeus says "Washi" and sounds imperious). Keep honorifics (-san, -kun,
-sama, -sensei). Narration is Yui's first person, past or present tense as the Japanese.
Translate meaning and tone, not word order; dialogue should sound like people talking.

When you change a fixed term, change it everywhere (grep the translation files) and in
the glossary.

## Workflow for one package

```
git checkout -b feat/edit-<package>              # never commit to the primary branch
python tools/show.py 04 50001                    # Japanese and English side by side
  ... edit translation/en/04.json ...
python tools/check.py translation/en/04.json --iso <original.iso>
python tools/build.py <original.iso> work/out/en.iso    # optional: see it in game
git commit -m "fix(translation): edit Apollon route scenes 50001-50020"
```

`check.py` must report 0 errors before a commit. To look at a page in the emulator, see
the harness section of [HANDOFF.md](HANDOFF.md); `tests/ui.txt` reaches the prologue.

Machine retranslation of single units: delete the unit from the translation file and
run `python tools/translate.py --tags 04` with an OpenAI-compatible endpoint
(`--endpoint`, `--model`). It skips units that already have English and caches results in
`work/mt_cache.json` (delete a cache entry, keyed by the Japanese text, to force a redo).

## Work packages

States: **MT** = unedited machine translation; **edited** = a full editing pass against
the Japanese; **reviewed** = read through in context (ideally in game) by someone else.
Take a package by putting your branch name in the Owner column in your first commit.
Big files can be split by scene range (the scene id is the part before `/`).

| Package | File | Units | Scenes | Content (main characters) | State | Owner |
|---|---|---|---|---|---|---|
| S01 | `01.json` | 1,050 | 10001-10180 | prologue: summoned to the Garden (Zeus, Thoth, Apollon) | MT | |
| S02 | `02.json` | 2,527 | 20001-30263 | common route: council, clubs, early school life | MT | |
| S03 | `03.json` | 1,143 | 40001-40602 | common Garden/side events (Apollon, Loki, Balder) | MT | |
| S04 | `04.json` | 6,165 | 50001-58008 | Apollon route | MT | |
| S05 | `05.json` | 3,879 | 60001-68006 | Hades route | MT | |
| S06 | `06.json` | 4,629 | 70001-78022 | Tsukito route | MT | |
| S07 | `07.json` | 3,888 | 80001-88005 | Takeru route | MT | |
| S08 | `08.json` | 4,889 | 90001-98012 | Balder route | MT | |
| S09 | `09.json` | 4,330 | 100001-108029 | Loki route | MT | |
| S10 | `10.json` | 3,011 | 110001-115011 | Anubis route | MT | |
| S11 | `11.json` | 1,870 | 120001-125005 | Thoth route | MT | |
| S12 | `12.json` | 481 | 200001-207005 | extra/after stories (Dionysus, Hades, Takeru) | MT | |
| Q | `quiz.json` | 1,200 | 8 quiz files | mythology quiz: check facts and that `c0` stays correct | MT | |
| D | `dictionary.json` | 254 | 80 entries | dictionary: terms, myth notes | MT | |
| U | `eboot.json` | ~400 | - | UI, help bar, titles, nameplates (hand translated) | edited | |

Route labels come from the speakers in each file and may be loose; check the Japanese.

Suggested order: S01 and S02 first (everyone plays them, they set names and terms), then
U, Q, D, then the routes in any order.

## What MT got wrong so far (watch for these)

- Name tokens dropped or replaced with "Yui" (the checker catches missing tokens).
- Keyword tokens with empty TEXT (`{kw:12:1:}`) where the model lost the term: fill TEXT
  and move the token before the English term.
- Literal translations of idioms and set phrases (`いただきます` is "Let's eat.").
- Speaker voice drift: Tsukito too casual, Zeus too modern, Anubis too articulate (he
  speaks in growls; Kaa translates in brackets).
- Very long ellipses collapse to `......`; keep silent lines as `"......"`.
