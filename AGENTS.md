# Repository working instructions

Owner away: Claude runs the project through three roles
(an app-scheduled steward; a lane worker and a navigator started by the role launcher). Read `docs/operating.md` first: the
owner's goals and standing grants, the shared rules and where things live.

## Project gotchas

- Never run `cargo fmt`: the code isn't rustfmt-formatted, so it rewrites
  the whole crate. Match the surrounding style by hand.
- Check a change with the debug tests that cover it plus golden
  (`cargo test --test golden`); for Python, only the test files that touch
  what changed. No full suites and no release-mode tests. Build a release
  wheel once per landing, only to swap main's installed `sts`.
- Windows locks a loaded `sts` module (`.pyd`): `maturin develop` can't
  replace it while any Python process using `sts` runs (a sweep, a bench, a
  notebook). Check `tasklist //FI "IMAGENAME eq python.exe"` before
  rebuilding. If a process you can't stop holds it, rename the loaded
  `.venv/Lib/site-packages/sts/sts.cp313-win_amd64.pyd` aside (Windows
  allows renaming a loaded DLL), then install; delete the renamed file
  once that process ends. Build first and swap last, so `sts` is never
  missing while the job runner may start a job: `cd py &&
  ../.venv/Scripts/maturin build --release -o ../target/wheels`, then
  rename the `.pyd` aside and `../.venv/Scripts/pip install --no-deps
  --force-reinstall` the new wheel (seconds, not the build's minute).
- Queued jobs are pinned by default (`jobs.py add`; docs/job-queue.md):
  they load `sts` from their snapshot's `pyroot` under `sts-builds/`, so a
  swap of main's `sts`, a merge or a landing concerns only unpinned jobs
  and runs by hand. Run `jobs.py impact sts` (or `scripts`) first and
  record its result in the commit. When a snapshot of the commit exists
  (`jobs.py pins` shows its wheel), install that wheel instead of building
  one: main and pinned jobs then load identical bytes and share the ladder
  caches keyed by the `.pyd` hash. Never delete a snapshot by hand or with
  `git worktree remove`: its junctions lead into main's data (`db/` isn't
  rebuildable); use `jobs.py unpin`.
- A new content element (an effect, a pick condition, a slot form, ...)
  goes in `registry::element_names()` with its words in
  `content/wording.json`; `cargo test` (`engine/tests/wording.rs`) names
  any miss. The explorer words all content from that file.
- `docs/INDEX.md` is written by `python scripts/docs_index.py --write`
  from the files in git (titles, each spec's line-3 Status, Act 1 coverage
  from `content/`). After staging a new doc, a spec's Status or title
  change, or a content change, run it and commit INDEX.md with them; the
  pre-commit hook (`--install-hook`) refuses a stale index, a spec without
  a valid Status line and a broken link in `docs/README.md`. On a rebase
  conflict in INDEX.md, take either side, rerun `--write` and stage it.
- Whether two lines of play are the same is judged by the state they reach
  (afterstate, docs/concept.md), never by the choices that reached it.
