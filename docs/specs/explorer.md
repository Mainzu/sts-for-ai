# Solved-state explorer

Status: superseded (2026-11-08, by docs/specs/explorer-v2.md; built 2026-10-27: decisions "Explorer as built"; v2 extends the same page).

## Outcome

A local, read-only page for browsing solved positions. For each one it shows:

- the board;
- every option's exact value;
- which option the heuristic or a net picks, and how much that pick costs.

Clicking an option plays it and moves on to the next position. The page
answers the question exact-puzzles.md left open: **where do the heuristic
and the nets go wrong, and what do those positions look like?** Today those
results are only averages ("~10% wrong picks at horizon ≥ 1"); the explorer
lets the owner open each wrong pick.

The explorer is built during the night run, so it may not change the Rust
crates. `maturin develop` can't replace the `.pyd` while the sweep has
`sts` loaded (AGENTS.md). Everything it needs is already in the binding:
`Combat.decode` / `render` / `step` / `advance`, and `SolvedDb.fetch` /
`lookup` / `positions`. Bench picks come from `sts.solve` and
`bench.search_puzzles`.

**Non-goals:**

- Editing or writing either database.
- A graphical card or board view: v1 shows the board as `render()` text.
- Constructing positions by hand.
- Distributions: `fetch` drops them.
- Hosting the page anywhere except localhost.

## Behavior

### Running it

`python scripts/explore.py [--db db/solved.sqlite] [--model RUN_ID] [--port 8765]`

- Serves `http://127.0.0.1:8765` using `http.server` from the standard
  library (no new dependency), single-threaded.
- The page is one static file, `scripts/explore.html`, with plain
  JavaScript and no build step.
- An `explore` entry in `.claude/launch.json` opens the page in the desktop
  app's browser pane.
- `--db` takes either database. `db/train.sqlite` can be read while the
  night writes to it: SQLite's WAL mode lets readers run beside a writer.
  The page sees the database as it was when the explorer opened it. A
  "reopen" control takes a fresh snapshot.
- Read-only:
  - Listing queries use stdlib `sqlite3` with `mode=ro`.
  - Before opening `sts.SolvedDb`, the explorer checks that the database
    already has rows of the current rules version. If it has none, the
    explorer refuses to start, because `open` would write a version row.
  - Solving on demand uses a memory-only `SolveStore`.

### Entry points (the list view)

1. **Bench puzzles** (`data/bench/puzzles.json`).
   - Filter by half, played horizon, contested or not, and "wrong picks
     only" (the evaluator's regret > 0).
   - Sort by regret or horizon.
   - 25 per page.
2. **Run positions**: the `positions` table by source (a registry run id
   or `bench`). Same columns, no picks.
3. **A row id**: open any state of the current rules version
   (`SolvedDb.fetch`).

Full-table scans over the 1.2 GB `states` table are out. It holds 3.9M rows
(2.7M decision states, `turns_left` up to 10, 12,625 bench positions), and
a single `COUNT(*)` grouped by version takes minutes. Listing reads only `positions`, the puzzle
file, and single rows by id.

### Picks

- The evaluator defaults to the heuristic. `--model` adds a net, loaded the
  way bench loads one.
- Picks are `bench.search_puzzles`, so they are the bench's own numbers, not
  a re-implementation.
- Computing them over the whole puzzle set runs once at startup with a
  `progress.py` bar. The result is cached to
  `cache/explore/<evaluator>-<puzzle file hash>.json`, so the next start is
  instant.
- Run positions and opened rows get picks when viewed: one search per state.

### The state view

- The board, as `Combat.render()` text in a monospace block.
- The state's exact value, `turns_left`, and cost (when it came from a row).
- A table of options:
  - the action group;
  - the exact value;
  - regret against the best option;
  - each evaluator's score, with a mark on its pick.
- **Step:** clicking an option decodes the state, plays the option's
  actions, and advances to the next decision with seed `k`. The child is
  one sampled chance outcome.
  - A "reroll" control changes `k`.
  - A breadcrumb trail goes back up the line.
- **Child value:**
  - If the child is in the database (`lookup`), it shows directly.
  - Otherwise a "solve" button runs `sts.solve(max_nodes=1_000_000)` with a
    memory store. Missing children are usually cheap: states under
    `min_nodes` aren't stored.
  - If the solve runs out of budget, the page says "unsolved".
- The client identifies a state by its codec bytes in hex (60–120 bytes), so
  the server keeps no session state.

### JSON endpoints

All return JSON:

- `/api/puzzles?half=&horizon=&wrong=&sort=&page=`
- `/api/positions?source=&page=`
- `/api/state?puzzle=` | `?id=` | `?hex=`
- `/api/step?hex=&option=&seed=`
- `/api/solve?hex=`
- `/api/reopen`

The page is a thin client over them, and tests call the handler functions
directly.

## Fits with

- `bench.py`: the explorer reuses `load_puzzles`, `search_puzzles`,
  `regret` and the evaluator loading, so a pick on the page equals the
  bench's.
- `progress.py` (being committed now): the startup bar.
- `docs/research/exact-puzzles.md`: the explorer is the drill-down behind
  its averages.
- The curriculum: opening `db/train.sqlite` shows the labels a round
  trained on.

## When in doubt

- Show less, but correct. A value the page shows must be the database's or
  the bench's number, never recomputed a second way.
- Prefer one more endpoint field over client-side logic.

## Scope

- **In:**
  - `scripts/explore.py`
  - `scripts/explore.html`
  - `scripts/tests/test_explore.py`
  - the `.claude/launch.json` entry
  - a README line
- **Out:**
  - Rust and binding changes
  - new indexes or tables
  - writing to any database
  - authentication: the server binds 127.0.0.1 only

## Decisions taken (provisional)

- **A local web page over a terminal UI.** Tables of options, clickable
  lines and a back trail are what a browser does well. It costs no
  dependency and shows in the app's browser pane beside the chat. A terminal
  UI library would add a dependency and keyboard-only navigation.
- **Text board.** `render()` exists and is tested. A drawn board is a later
  spec, if the text proves hard to read.
- **Single-threaded server.** One user, and it gives deterministic tests.
  `SolvedDb` is safe across threads if this ever changes.

## Outside assumptions

- `SolvedDb.fetch` works on any row id of the current version, not only
  those from `decision_ids`. db.rs queries `WHERE id = ? AND version = ?`.
- `Combat.decode(bytes, seed)` plus `step`/`advance` reproduce the solver's
  option semantics. The test `explore_step_matches_solve` checks this.

## Memory and CPU during the night

The night is sized to free memory minus `MEM_MARGIN` (1 GB), so the
explorer has to fit inside that margin.

- Build step 3 measures its peak with the heuristic and with a net.
  **Stop point** if the peak is over 500 MB.
- Precomputing picks competes with the night's solver threads for CPU. It
  is a one-time cost of minutes, not paging.
- Build checks during the night run only `test_explore.py` and
  `test_bench.py`. The full suite runs after the night.

## Verification

`scripts/tests/test_explore.py` runs over a tiny database built in a temp
directory, the same way the puzzles tests build theirs:

- `explore_read_only`:
  - the database file's bytes and mtime are unchanged after every endpoint
    is called;
  - an empty database (no current-version rows) refuses to start.
- `explore_state_matches_db`: `/api/state?id=` returns `fetch`'s value and
  option values, unchanged.
- `explore_picks_match_bench`: on a 3-puzzle set, the picks and regrets
  equal `bench.search_puzzles` + `regret`.
- `explore_step_matches_solve`: for each option of a solved root:
  - stepping with several seeds gives children whose exact values
    (solved), averaged over every chance outcome, equal the option's value;
  - on a deterministic option, the one child's value equals it.
- `explore_filters`: the `wrong`, `horizon` and `half` filters, and paging,
  over a hand-made picks cache.
- `explore_cache`: a second start reads the picks cache and runs no search
  (the search is stubbed and counted).
- `explore_server_smoke`: a real server on port 0 serves the page and one
  endpoint.

Manual check: open the page in the browser pane, follow a wrong pick two
steps down, reroll, and go back. Take a screenshot.

## Don't guard

Concurrent writers to the explorer's own cache (one user), and malformed
hex from the page (it only sends what the server gave it).

## Build steps

1. **Data layer.** In `explore.py`: the read-only open, puzzle and position
   listing, state view, step, solve on demand. Check:
   - `explore_read_only`
   - `explore_state_matches_db`
   - `explore_step_matches_solve`
   - `explore_filters`
2. **Picks.** The startup precompute with the progress bar and the cache.
   Check: `explore_picks_match_bench`, `explore_cache`.
3. **Server and page.** `explore.html`, the endpoints, `launch.json`,
   README. Check:
   - `explore_server_smoke`;
   - the manual check in the browser pane;
   - the memory peak measured and written to `docs/decisions.md`.
