# Working on this repository (people and agents)

Read this first if you are new here, human or AI agent, and have no other context. It
says what to read, the rules that are not negotiable, how to pick up a task, and when a
task counts as done.

## Read in this order

1. [README.md](README.md): what the project is, its status, the pipeline, the tools.
2. [docs/SETUP.md](docs/SETUP.md): get the tools and make a first build. Do this before
   any task; nearly every task is checked by building and looking at the game.
3. Then, depending on the task:
   - translation or editing: [docs/TRANSLATION.md](docs/TRANSLATION.md)
   - engine, formats, images, open engineering tasks: [docs/HANDOFF.md](docs/HANDOFF.md)
     and [docs/FORMATS.md](docs/FORMATS.md)
   - testing: [docs/TESTING.md](docs/TESTING.md)
   - a playtest ISO or a release: [docs/RELEASE.md](docs/RELEASE.md)
   - the general method (porting to another game): [docs/PROCESS.md](docs/PROCESS.md)

## Hard rules

1. **No game data in git.** The ISO, anything extracted from it (Japanese text in
   `work/text/`, decrypted EBOOT, textures, exported PNGs, screenshots, built ISOs)
   stays in `work/` or outside the repository. Commit tools, patches, docs, specs and
   English only. `.gitignore` enforces most of this; check `git status` anyway.
2. **No machine-specific values in the repository.** No local paths, user names, ports
   of someone's setup or credentials, in code defaults or docs. Use arguments,
   environment variables (`PSPDECRYPT`, `ARMIPS`, `MT_ENDPOINT`, `MT_MODEL`,
   `MT_API_KEY`) and placeholders like `<original.iso>`.
3. **Never commit to the primary branch** (`main`). One branch per task, named
   `<type>/<slug>` (`feat/`, `fix/`, `docs/`, `chore/`, `refactor/`), merged by the
   maintainer.
4. **Conventional commits**: `type(scope): imperative summary`, e.g.
   `fix(translation): edit Apollon route scenes 50001-50020`,
   `feat(images): re-letter the gallery tags`. Commit after each self-contained change.
5. **`python tools/check.py --iso <original.iso>` reports 0 errors** before any commit
   that touches `translation/`.
6. **Keep markup tokens exactly** (`{NAME}`, `{NICK}`, `{SURNAME}`, `{kw:ID:FLAG:TEXT}`,
   `{op:XXXX:HEX}`): see the markup rules in [docs/TRANSLATION.md](docs/TRANSLATION.md).
7. **Engine changes are proved by a screenshot**, not by reasoning: build, run
   `tests/ui.txt` through the harness and look at the shots. A change that cannot be
   observed yet (the screen needs a save) is marked "not seen in game" in HANDOFF.md.
8. **Record findings as you make them**: new addresses and formats in FORMATS.md, state
   and open tasks in HANDOFF.md, package state in TRANSLATION.md. The next person has
   only these files.

## Picking up a task

- **Translation editing**: the work packages table in
  [docs/TRANSLATION.md](docs/TRANSLATION.md#work-packages). Take one whose Owner is empty,
  put your branch name there in your first commit, and follow "Workflow for one
  package". Big files can be split by scene range. Packages are independent, so several
  people or agents can work in parallel, each on its own branch.
- **Engineering**: the numbered open tasks in
  [docs/HANDOFF.md](docs/HANDOFF.md#open-tasks), in priority order. Each names where to
  start.
- **Images**: the IMG items in HANDOFF.md's open tasks; method under Images in
  TRANSLATION.md.

Bugs found outside your task: fix them in their own `fix(...)` commit if they are small
and obviously right; otherwise write them up in HANDOFF.md's open tasks and carry on.

## Definition of done

- [ ] `check.py` 0 errors (translation) and the build runs without an exception.
- [ ] Visible changes seen in a harness screenshot or a playtest, or explicitly marked
      as not seen yet.
- [ ] Docs updated: package state/owner, HANDOFF state, FORMATS findings.
- [ ] Commits conventional, on a task branch, nothing from `work/` staged.

## Gotchas that cost time before

- `build.py` needs `PSPDECRYPT` and `ARMIPS` (or PATH); it stops with "not found"
  otherwise.
- Japanese units live only in `work/text/` of the checkout where the extractors ran. A
  fresh clone or a git worktree has none: run the extractors there, or pass
  `--text <other checkout>/work/text` to `check.py`, `show.py` and `apply_edits.py`.
- Writing Python or JSON through a shell heredoc can turn `\n`, `\0`, `\\` into raw
  characters. Use a real editor or file-writing tool for anything with backslashes.
- UI strings (EBOOT, quiz, dictionary titles) are pair-encoded and have fixed fields;
  story text is plain ASCII and re-wrapped by the build. Do not add `\n` to story
  pages: a page with any `\n` is treated as hand laid out and not re-wrapped.
- The game's font has printable ASCII only on the English side: no curly quotes, em
  dashes, accents or emoji.
- The harness exits with status 9 after a completed run; judge by the screenshots.
- Harness savestates are only valid for the ISO they were made with: after a rebuild,
  replay from boot (`tests/setup_skip.txt`, then `tools/autoplay.py`).
- Choice labels hold at most 32 characters; quiz and dictionary titles 31.
- Later screens (quiz, chapter cards, Extra) are reached with `tools/autoplay.py`; see
  docs/TESTING.md before writing long input scripts by hand.
- Long machine-translation runs: run them detached and resumable (they skip finished
  units); do not block a session waiting for one.
