# Testing

There are no unit tests; the checks are the translation checker, the build's own reports
and screenshots from the real game running headless. Run all three before calling a
change done.

## 1. Checker (every translation edit)

```
python tools/check.py --iso <original.iso>              # all files
python tools/check.py translation/en/04.json --iso <original.iso>
python tools/check.py --iso <original.iso> --quiet      # summary only
```

**ERROR** (must be 0 before a commit): unknown unit id, broken or missing keyword/op
token, a character the game cannot draw, Japanese left in the English.
**WARN** (read them): a name token dropped or added (often a correct pronoun), a word
wider than the window, quiz/title text that will be cut, untranslated units.
`--iso` (or a cached `work/fontA.ftd`) enables the width checks.

## 2. Build reports (every build)

`tools/build.py` prints the units applied, pages continued in a second window, lines
wider than the window (listed in `work/build/overflow.txt`), `text cut to fit: <id>`,
`EBOOT string too long: ...`, the textures re-lettered and the EBOOT strings moved to
the extra segment. An exception means a broken spec, token or patch; a report line
means a unit to shorten.

## 3. Harness (anything visible)

`tools/harness.py` runs the PPSSPP libretro core headless (software renderer, no window,
no GPU needed) with a scripted pad and saves PNG screenshots.

```
python tools/harness.py --core <ppsspp_libretro.dll> --out work/shots/<name> work/out/en.iso tests/ui.txt
```

Options: `--assets <PPSSPP assets dir>` seeds `work/harness/system/PPSSPP` (optional;
the game uses its own font), `--boot-wait S` (default 10), `-v` for core logs,
`--workdir` (default `work/harness`, holds the system and save folders).

### Scripts in `tests/`

| Script | Path through the game | Shots |
|---|---|---|
| `boot.txt` | boot -> title screen | 4 |
| `prologue.txt` | title -> New Game -> default name -> first story pages | 6 |
| `ui.txt` | title -> New Game -> name confirm (`v1_confirm`) -> quiz difficulty (`v2_quiz`) -> prologue pages (`n01`..`n07` mid-page, `m01`..`m07` finished page) | 16 |
| `options.txt` | title -> Option screens (values, hint bar, help) | 9 |
| `dictionary.txt` | plays to the first keyword (iai), System Menu -> Dictionary -> entry 1 | 3 |

`ui.txt` is the regression gate: after any engine, wrap or EBOOT change, its `n*`/`m*`
shots must show English inside the window, wrapped, with no stray or overlapping glyphs.

### Script language

```
wait N                  run N frames with no input (60 frames = 1 s)
press BTN [BTN..] [N]   hold buttons for N frames (default 4), then release for 4
repeat K press ...      repeat a press K times
shot NAME               save the current frame as NAME.png
# comment
```

Buttons: `circle cross square triangle start select up down left right l r`.

In this game: circle confirms and advances text (the first press finishes typing the
page, so one `press circle 6` is about half a page), cross cancels, triangle opens the
system menu (only once the page has finished typing: `wait 400` first), square hides
the message window. About 230 presses reach the end of the prologue's first day.

### Writing a new script

1. Copy the nearest existing script and extend it a few steps at a time, with a `shot`
   after each step, until it reaches the screen you need.
2. Leave generous waits around menus and screen changes (300-600 frames): input timing
   drifts with machine load.
3. Commit the script to `tests/` with a header comment saying where it goes. Shots stay
   in `work/` (they are game art).

### Known behaviour

- The process exits with status 9 after the last line (the core tearing down). A run
  that printed every `shot` line completed; judge it by the screenshots.
- PPSSPP 1.17's software renderer crashes if the first frame runs before the async boot
  finishes: raise `--boot-wait` when the machine is busy.
- The emulated system language is Japanese, so PSP system dialogs (save/load) show
  Japanese. On hardware they follow the console language; that is not a patch bug.
- Saves persist in `work/harness/saves`. Delete that folder if a run takes a different
  path than expected (for example the title screen offering Continue).
- Screens behind progress (quiz, Mythology Monologue, chapter select, gallery, garden,
  routes) need a save that reaches them. Getting there by script is slow; a save from a
  real play-through copied into `work/harness/saves` is the practical route.

## 4. Playtesting by hand

Load the built ISO in desktop PPSSPP (or on a PSP with custom firmware; not yet tested on
hardware). Report problems with a screenshot and, where possible, the unit id:
`python tools/show.py <tag> <scene>` finds a page by scene, and grepping the English
text in `translation/en/` finds its id.
