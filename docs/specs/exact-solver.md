# Exact solver and position finder

Status: closed (2026-10-27, built; the solved DB is no longer maintained: approach review 2026-11-02 "Stop or pause").

## Outcome

An exact solver for small combat positions, a permanent database of every
position it has solved, a finder that turns real games' tails into solved
positions ("puzzles"), and a puzzle section in the bench that scores any
evaluator's decisions against values that are proven, not estimated by a
heuristic search. Its first result answers one question before any
curriculum is built: **are the heuristic and the current nets already
near-exact at endgames, or do they make mistakes there?**

It is the measuring stick, and later the label source, for the backward
curriculum (exact positions first, then one turn earlier, and so on).
That curriculum is its own spec.

**Non-goals:** training on puzzles (no `learn.py` / `selfplay.py` change:
no exact labels, curriculum, puzzle weighting or deep relabel pass);
constructed or random positions (puzzles come only from real games' tails);
no-death combats; approximating positions that are too big to solve.

## Behavior

### Solver

- **What it computes.** From a state awaiting an action, each root option's
  exact expected final score (`CombatState::score`, 0..=2) under the best
  play from there on: the best option at every decision, the
  probability-weighted mean over **every** outcome of every random event
  (draws, monster moves, random targets), with no turn limit and no
  evaluator, down to the end of combat in every branch. The player knows
  everything the state holds, so this is the true value of each choice.
- **Root options** are grouped exactly as `search` groups them (merged by
  afterstate, in `legal_actions` order, each with all its actions), so the
  bench pairs a puzzle's options with an evaluator's search options one to
  one.
- **Transpositions:** inside one solve, equal states share one solved value
  (a table keyed by the whole state, `turn` included, as search's memo is).
  Values are summed in f64 in a fixed order, so the same position always
  gives bit-identical values.
- **Budget, never truncation.** A node budget (`max_nodes`, default
  **1,000,000**; tunable) counts states newly expanded. Past it the solve
  stops and reports **unsolvable**. It never returns a partial or
  approximate value. A position whose tree never ends (both sides stall
  forever) runs out of budget the same way.
- **Distribution, as an option** (`distribution=True`, default off): from the
  same solve, each root option also gets the exact distribution of the
  combat's outcome under the best play: P(loss) and P(win with k HP lost),
  with k counted as the score counts it (after the end-of-combat heal,
  floored at 0). Ties between equal-valued options are broken by the first
  best, as search does. The distribution and the value must agree:
  Σ P(win, k) · (2 − k/100) equals the value to 1e-9.
- **Store interface.** The solver takes an optional store (a Rust trait
  `SolvedStore` in `solve.rs`: look up a state, insert a solved state). On
  every newly reached state it asks the store first. A hit uses the stored
  value (and distribution) instead of expanding the state, and costs 1 node
  of the budget. A distribution solve treats a value-only entry as a miss
  and upgrades it. Values are bit-identical with and without a store,
  because a subtree's value does not depend on how it was reached. A solve
  reports `nodes` (new expansions) and `hits`.
- **What gets stored.** When a solve ends, each state it finished solving is
  offered to the store with its value, its distribution (when computed) and
  its **cost**: the larger of the expansions its subtree took and one more
  than its costliest child's cost, a hit's stored cost included (a lower
  bound on what a cold solve would take; hits' subtrees overlap, so their
  costs aren't summed: docs/decisions.md, "Solved-state cost"). States costing under
  `min_nodes` (default **1,000**; tunable, measured in step 7) are fast to
  re-solve, so they are not stored. A solve that runs out of budget still
  offers the subtrees it finished, since those values are exact.
- **Where it lives:** a new engine module `engine/src/solve.rs`, built only
  from public engine calls (`legal_actions`, `apply_action`,
  `chance_outcomes`, `score`), with the `SolvedStore` trait and an in-memory
  store (`MemoryStore`). No other engine file changes, and the engine gains
  no dependency.

### Solved-position database

- **What it is.** A permanent SQLite database of every solved position
  worth keeping, kept for future reference across runs, sessions and
  specs. Entries are deleted only to save space. Default path
  `db/solved.sqlite` (gitignored: too big for git).
- **Rust reads and writes it directly.** A new workspace crate `solvedb/`
  (depends on `sts-engine` and `rusqlite` with SQLite bundled) implements
  `SolvedStore` on the database, with a `MemoryStore` in front for the
  current game. So the solver finds a position solved in any earlier run,
  from any fight. The engine crate stays dependency-free.
- **Three jobs, one structure.** The database serves (1) lookups while
  solving, (2) a permanent record of exact values that later training reads
  directly (any stored state can be rebuilt and turned into features), and
  (3) the record of which positions came from real games (puzzles).
- **Tables:**

  | Table | One row per | Columns |
  |---|---|---|
  | `versions` | engine version | id, rules fingerprint, codec version, first seen |
  | `states` | solved state | version id, key hash, state bytes, value, cost, `turns_left`, solved at; for decision states also `options` (per root option: its action group and exact value, plus its distribution when computed) |
  | `positions` | played position (puzzle) | state id, source (`bench` or a registry run id), spec, action prefix, step, played horizon, gap |
  | `meta` | — | schema version |

  `states` is unique on (version id, state bytes) and indexed on (version
  id, key hash) for lookups and (version id, cost) for eviction.
  `positions` is indexed on source. More indexes can be added later without
  changing rows.
- **State bytes: a decodable encoding.** A new engine module
  `engine/src/codec.rs` turns a state into compact bytes and back
  (`encode(&CombatState) -> Vec<u8>`, `decode(&[u8]) -> CombatState`):
  piles as (card, count) lists, empty monster slots skipped, a codec
  version byte first. Roughly 60-120 bytes per state; step 7 measures it.
  `encode` takes the state apart by naming every field, so a new
  `CombatState` field is a compile error until the codec handles it.
  `decode(encode(s)) == s` proves two different states never share bytes,
  so a row matches a state only when they are equal. Lookup: a 64-bit hash
  of the bytes (FNV-1a, written in the crate), confirmed by comparing the
  full bytes, so a hash collision is a miss, never a wrong value.
- **Per-option values on decision states.** A decision found in the
  database must still give each option's value, and the options' own states
  are often too cheap to be stored. Those values are also the ranking
  targets the curriculum will want.
- **`turns_left`:** the most turns the combat can still last from this state
  under the best play (the solver's tree height in turns: best option at
  decisions, the longest outcome at chance nodes; 0 = it ends this turn). It
  is a property of the state, unlike a position's played horizon, so the
  curriculum can order positions by distance from the end.
- **Rules fingerprint: when rows go stale.** A version is a hash of the
  engine's rule files (`state`, `cards`, `monsters`, `powers`, `hooks`,
  `effects`, `chance`, `character`, `registry`; read at build time by
  `solvedb`), with
  comments and whitespace stripped, plus the name order of every content
  table the codec writes as a number (cards, powers, monster kinds, moves),
  plus the codec version. Any real rules edit makes a new version; comment
  and formatting edits don't. Lookups only match rows of the current
  version. Older versions' rows are never used, and are the first to go
  when space is needed.
- **Fast misses.** On open, the database loads the 64-bit hashes of the
  current version's rows into memory (8 bytes each). A state whose hash
  isn't there is a miss with no disk query; only possible hits query SQLite.
- **A run sees the database as it was when opened**, plus its game's own
  solves. Rows written by other games or processes later in the run are not
  used until the next open. So a run's output depends only on the
  database's contents at the start (and is the same with any number of
  threads), never on timing.
- **Writes:** each solve's offered states go in one transaction. SQLite's
  WAL mode lets other threads and processes read while one writes. Each
  thread has its own connection.
- **Distributions** are compact blobs of (HP lost, probability) pairs plus
  P(loss), stored per option when computed. A distribution solve that hits
  a row without them re-solves that state and adds them.
- **Space.** A size cap (`max_gb`, default **5 GB**; tunable) is checked at the end of a run. Over the cap, rows go in
  this order until the file is under 90% of the cap: other rules versions
  first, then the cheapest to re-solve (lowest cost). Then the file is
  compacted (`VACUUM`). Nothing else ever deletes rows.
  `scripts/puzzles.py db --stats` prints size, rows per rules version and
  cost spread; `db --evict` runs the same rule by hand.

### Binding

- `sts.SolvedDb(path="db/solved.sqlite", max_gb=5)` opens (or creates) the
  database under the current rules fingerprint. `sts.Combat.encode()` and
  `sts.Combat.decode(bytes)` expose the codec, so later training code can
  rebuild any stored state.
- `sts.SolveStore(min_nodes=1_000, db=None)` is one game's store: memory
  only, or memory in front of a database.
- `sts.solve(combat, max_nodes=1_000_000, distribution=False, store=None)`
  returns `{"options": [(actions, value[, dist])], "nodes": n, "hits": h}`,
  or `None` when unsolvable. It releases Python's lock, so the finder solves
  games on a thread pool.
- **Memory:** each thread holds one solve's table plus its game's memory
  store; the process holds the hash set. Build step 7 measures bytes per
  state and peak memory at the budget, and sets the default `threads` so
  that threads × peak stays under ~6 GB (roughly 4-6 threads at 1M nodes).

### Position finder

- **Input:** game records (spec with deck, encounter, seed, HP, character,
  plus the action list), the format the bench's decisions and the registry
  already use. A no-death record is refused with an error.
- **Walk back from the end.** For each game, replay to each decision from
  the last one backward. Decisions with fewer than 2 options are skipped.
  Each one is solved, and the walk stops at the first unsolvable decision
  (earlier ones are almost always bigger). Puzzles that this stop misses are
  accepted: exactness wins over coverage.
- **One store per game, over the shared database.** An earlier decision's
  tree contains the later decisions on the played path, so they come back
  as hits instead of being solved again. Hits also let the walk reach
  further back within the budget. Everything worth keeping lands in the
  database.
- **Per solved decision it records:** the spec, `step` (index in the action
  list), the action prefix (encoded as `bench_decisions.encode_action`), the
  root options' action groups, their exact values, `gap` (best minus second
  best), `horizon` (the played game's final turn minus the decision's turn;
  0 = the last turn), `nodes`, `hits`, and the distributions when asked.
- **Every solved decision is a `positions` row** (its state in `states`).
  The two outputs below are exports from the database, so neither defines
  its own format beyond what the export writes.
- **Two outputs:**
  1. **Bench puzzle set** (`data/bench/puzzles.json`, committed, the
     decisions file's row format, exported from `positions` with source
     `bench`). Search + heuristic (the calibration
     agent, one turn, limit 16) plays the bench's tight specs (610 train /
     550 held-out) on fresh game seeds from `PUZZLE_SEED` = 9,000,000 +
     `SEED_SKIP` 10,000: seed = 9,010,000 + pass × 2,000 + half × 1,000 +
     spec index, at most 45 passes, so under 9,100,000. (9,000,000 itself is
     not free: calibration plays cell i on 5,000,000 + i × 100,000, up to
     1,600 games per cell, so 9,000,000-9,001,599 are cell 40's. The skip
     keeps puzzle seeds in that block's unused rest, disjoint from
     calibration, the tight specs' own 3,000,000+, decisions' 7,000,000 and
     the fresh-seed check's 50,000,000+.) It plays more seed passes until each
     half has `PUZZLES_PER_HALF` (default **1,000**; tunable) games with at
     least one puzzle. **One puzzle per game**, picked uniformly (seeded)
     among the game's solved decisions, so the bench's intervals can assume
     independent rows. The distributions are stored too, so the histogram
     head can use them later. The set is built once, and rebuilt only with
     `--rebuild`, like the reference values. Its header records the
     database's row count when the build started, since hits can let a
     later build reach deeper.
  2. **Registry dump** (`scripts/puzzles.py --run <run id>`): every solved
     decision of every game in that run's dataset (main and branch games)
     goes into `positions` with that run id as source, for the curriculum
     later. `--export` also writes them to
     `datasets/puzzles-<run id>.jsonl` (gitignored). It writes nothing in
     the registry.

### Bench puzzle section

- `bench.py` adds a `puzzles` set to every run, beside `tight` and
  `standard`, per half with a held-out minus train gap like the others.
  Exact values come from the committed file, so the bench never solves
  anything or opens the database; the evaluator's one-turn search at each
  puzzle is the only cost (seconds). Quick mode keeps every 20th puzzle.
- **Metrics,** on `all` and `contested` (gap ≥ `CONTESTED`, default 0.05,
  the decisions set's value; tunable) puzzles, with the bench's 95%
  intervals:
  - `accuracy`: the share of puzzles where the evaluator's one-turn search
    picks an exactly best option (value within 1e-9 of the best).
  - `regret`: the exact best value minus the exact value of the option it
    picks.
  - `ranking`: pairwise order accuracy of its search option values against
    the exact values, over pairs whose exact values differ by more than
    1e-9.
  - Accuracy and regret per horizon (0, 1, 2+), with counts.
- Every existing number in the bench's output stays byte-identical.
  `bench_compare.py` shows the new set.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Engine: state, search, agents, runner | Unchanged behaviour; `solve.rs` and `codec.rs` are additive; the only other engine edit is crate-visibility (`pub(crate)`) on `Powers`' two private fields for the codec; no engine dependency | existing suites, golden trajectories (`engine/tests/golden.rs`), `git diff engine/src` showing only those |
| `CombatState` and its parts | The codec covers every field | compile error on a new field (the codec names every field); **new** `codec_roundtrip`; **new** `codec_golden`: 20 committed encodings still decode to the same states, so an unintended format change fails loudly |
| Rules files | A real rules edit retires the database's rows | **new** `fingerprint_tracks_rules`: the fingerprint changes when a rule file's code changes, and stays the same when only a comment or whitespace changes |
| `sts` binding's existing calls (`run`, `search`, `Combat`, `NetEvaluator`, features) | Unchanged signatures and results | `py/tests`, `scripts/tests/test_rust_net.py` |
| Bench sets, decisions, reference, calibration | Files unchanged; existing metrics byte-identical | **new** `test_bench_unchanged`: quick bench of the heuristic, minus the `puzzles` key, equals a snapshot taken in step 1 on the unchanged code |
| `bench_compare.py` | Still compares old result files, which have no `puzzles` set | **new** test: comparing an old-format result with a new one doesn't fail |
| Registry datasets and records | Read-only for the finder | **new** test: dumping from a tiny run leaves the registry's files unchanged (hash before and after) |
| `cargo test` at the root | Still runs the engine, and now `solvedb` too | workspace `default-members` |
| Learned-play sweep | Untouched. On Windows a loaded `sts` module locks its `.pyd`, so the binding is rebuilt only while no sweep or other `sts` process runs | build procedure (check `tasklist` before `maturin develop`) |

## When in doubt

Prefer a smaller set of exactly solved puzzles over a larger set of
approximately solved ones. Prefer a database miss over any chance of a
wrong hit.

## Scope

May change: `engine/src/solve.rs` and `engine/src/codec.rs` (new),
`engine/src/lib.rs` (the `mod` lines and re-exports), `engine/src/powers.rs`
(`pub(crate)` on its two private fields, nothing else), `engine/tests/` (new
solver and codec tests), `solvedb/` (new crate), the root `Cargo.toml`
(workspace members), `py/Cargo.toml` and `py/src/lib.rs` (new `solve`,
`SolveStore`, `SolvedDb`, `Combat.encode` / `decode` only), `scripts/`
(new `puzzles.py` for the finder, set building, registry dump and database
commands; `bench.py` and `bench_compare.py` for the puzzle section; tests),
`data/bench/puzzles.json` (new), `db/` and `datasets/` (gitignored),
`.gitignore`, `docs/`, `README.md`.

Interfaces it may change: new binding classes and functions, the new
state encoding and database format, and the bench result's new `puzzles`
set only.

**Off limits:** every other engine file (search, chance, state, heuristic,
agents) and any behaviour change in `powers.rs`, the feature format, the score, the existing bench files (sets,
calibration, decisions, reference) and existing metrics, `learn.py`,
`selfplay.py`, `sweep.py`, the registry's write paths. One new dependency
only: `rusqlite` (bundled SQLite), in `solvedb` alone.

## Decisions taken (provisional, also in docs/decisions.md)

- The solver is exact or silent: a node budget yields "unsolvable", never an
  approximation. It runs to the end of combat with every random event fully
  listed.
- Every solved position worth keeping (cost ≥ `min_nodes`) goes into a
  permanent SQLite database that Rust reads and writes directly (new crate
  `solvedb`, `rusqlite` bundled). Tables: `versions`, `states` (decodable
  state bytes, value, cost, `turns_left`, per-option values on decisions),
  `positions` (played positions with their source), `meta`. Rows are
  deleted only to save space, stale versions and cheapest first.
- States are stored in an explicit, decodable engine encoding (`codec.rs`),
  so every row can be rebuilt as a training example.
- A row goes stale when the rules fingerprint changes: a hash of the rule
  files without comments and whitespace, the content tables' name order and
  the codec version.
- A run reads the database as it was when opened, so its output doesn't
  depend on timing.
- Puzzles come from real games' tails only, walked back from the end to the
  first unsolvable decision.
- The bench set uses tight-spec games by search + heuristic on fresh seeds,
  one puzzle per game, train and held-out halves. The registry dump keeps
  every solved decision, for training later.
- Puzzle metrics join `bench.py` as a new set. Existing numbers are
  unchanged.
- Tunable defaults: `max_nodes` 1M, `min_nodes` 1,000, `max_gb` 5,
  `PUZZLES_PER_HALF` 1,000, `CONTESTED` 0.05, `threads` from the measured
  peak memory.

## Outside assumptions

- **`rusqlite` with bundled SQLite builds on this laptop's MSVC toolchain**
  (Visual Studio 2022 is installed) and supports WAL mode: one writer and
  concurrent readers across threads and processes. Checked by step 5's first
  test (open, write from one connection, read from four threads).
- **Tight fights' tails hold enough positions solvable within 1M nodes**
  (internal bet). Expected: at least one puzzle in most games, so 1,000 per
  half from ≤ 3 seed passes. Step 7 measures the solvable share and time
  per solve on 200 games per half. If it is far off, that step stops for a
  decision (budget or source).

## Verification

Tests written first:

- `solve_terminal`: a state one action from a won combat (lethal in hand,
  one living monster) → that option's value equals `score()` of the result
  exactly; EndTurn's value is lower.
- `solve_matches_brute_force` (Python): 30 tiny positions from game tails
  (one monster under 15 HP, draw pile ≤ 3 cards). An independent recursive
  expectimax written in Python over `Combat.options(limit=10**6)` to the end
  of combat gives the same option values to 1e-9.
- `solve_budget`: an opening position with `max_nodes` 1,000 returns
  `None`; `nodes` never exceeds `max_nodes`.
- `solve_deterministic`: two solves of the same 20 positions give
  bit-identical values; the finder on 50 games gives byte-identical output
  with 1 and 8 threads from the same starting database.
- `store_exact`: walking back 20 games with a memory store and without one
  gives bit-identical values for every decision both solve; with the store,
  total `nodes` is lower, and each later decision on the played path is a
  hit for the decision before it.
- `store_skips_fast`: with `min_nodes` 1,000 every stored state cost ≥
  1,000; with `min_nodes` 0 every solved state is stored.
- `store_partial`: a solve that runs out of budget leaves its finished
  subtrees stored, and re-solving with a bigger budget gives the same
  values as a cold solve.
- `codec_roundtrip`: `decode(encode(s)) == s` for 100k states reached in
  random and search play (both characters, every encounter, mid-card and
  chance-paused states included).
- `db_persists`: solve, close, reopen in a new process → the same root is
  a hit with bit-identical option values and distributions; its row
  decodes to the same state.
- `db_rules_version`: rows written under fingerprint A are misses when
  opened under B.
- `db_turns_left`: a lethal-in-hand root has `turns_left` 0; a position
  whose best line needs one more EndTurn has 1.
- `db_positions`: walking back one game twice adds no duplicate `states`
  rows, and adds `positions` rows only for decisions not yet recorded for
  that source.
- `db_collision`: two different keys planted with the same 64-bit hash →
  each looks up only itself.
- `db_snapshot`: rows written by another connection after open are not
  used until reopen.
- `db_evict`: over a tiny cap, other-version rows go first, then lowest
  cost; the file ends under 90% of the cap; nothing is deleted under the
  cap.
- `codec_golden`, `fingerprint_tracks_rules` (Fits with).
- `solve_groups_like_search`: on 200 decisions, the root option groups equal
  `sts.search`'s options exactly (actions and order).
- `distribution_consistent`: each option's distribution sums to 1 (1e-9)
  and implies its value (1e-9); with `distribution=False` the values are
  identical.
- `finder_walk_back`: on a recorded game, puzzles are contiguous from the
  last decision backward, stop at the first unsolvable one, and skip
  single-option decisions; a no-death record raises.
- `puzzle_set_format`: one puzzle per game, `horizon` ≥ 0, `gap` correct,
  seeds ≥ 9,000,000, reruns from an empty database byte-identical.
- `test_bench_unchanged` and the `bench_compare` / registry tests from Fits
  with.
- `puzzle_metrics`: a planted evaluator that returns each option's exact
  value scores accuracy 1, regret 0 and ranking 1; the random evaluator
  scores ranking near the bench's known floor.

**End-to-end:** on 200 puzzles (both halves), playing each puzzle's
position on 400 sampled continuations with the solver's own policy averages
to the exact value (|mean − value| inside the 95% interval on ≥ 95% of
puzzles), and search + heuristic from the same positions never averages
above the exact value outside its interval. Building the set a second time
over the filled database solves the same puzzles with mostly hits and
identical values. Then the bench's puzzle section for the heuristic and the
current nets (Amendment 3's final round nets and `models/value_effects.pt`)
is recorded in `docs/research/exact-puzzles.md`. That is the "measure first"
answer.

## Don't guard

- Positions the engine can't reach (hand-made states, no-death states):
  the finder refuses no-death records and nothing else is accepted.
- Stack depth: trees inside the budget are a few hundred decisions deep.
  Write the solver so 1M nodes can't overflow the stack (an explicit stack,
  or recursion on a thread with a large stack), but don't add a depth limit.
- f64 rounding beyond 1e-9 tolerance checks.
- A corrupted database file: SQLite's own error surfaces; no repair tool.

## Build steps

1. **Pins.** Snapshot the heuristic's quick bench on the unchanged code and
   write `test_bench_unchanged`, the `bench_compare` old-format test and the
   registry read-only test (they pass trivially or are skipped until step
   8). Check: they pass on unchanged code.
2. **Solver core** (`engine/src/solve.rs`): values, transpositions, budget,
   root grouping like search, the `SolvedStore` trait. Check:
   `solve_terminal`, `solve_budget`, `solve_deterministic` (single thread)
   in Rust; golden trajectories and the engine suites pass.
3. **Memory store** (cost, `min_nodes`, hits, partial subtrees kept). Check:
   `store_exact`, `store_skips_fast`, `store_partial` in Rust.
4. **Distribution option.** Check: `distribution_consistent` in Rust.
5. **Codec and fingerprint** (`engine/src/codec.rs`, `pub(crate)` on
   `Powers`' fields; the fingerprint in `solvedb`). Also `turns_left` in the
   solver. Check: `codec_roundtrip`, `codec_golden`,
   `fingerprint_tracks_rules`, `db_turns_left`'s solver half; golden
   trajectories unchanged.
6. **Database** (`solvedb`: schema, `versions` / `states` / `positions` /
   `meta`, hash set, snapshot reads, batched writes, cap and eviction,
   stats). Check: the WAL smoke test, `db_persists`, `db_rules_version`,
   `db_collision`, `db_snapshot`, `db_evict`.
7. **Binding + measurement.** `sts.solve` (lock released), `SolveStore`,
   `SolvedDb`, `Combat.encode` / `decode`. Measure bytes per state, peak memory at 1M nodes, time per
   solve cold and over the database, rows and bytes per row at a few
   `min_nodes` values, and the solvable share of tight-fight tails (200
   games per half); set the defaults for `threads` and `min_nodes`. Check:
   `solve_matches_brute_force`, `solve_groups_like_search`; measurements
   written to `docs/decisions.md`. **Stop point** if the solvable share
   can't fill 1,000 per half from ≤ 3 seed passes.
8. **Finder + registry dump + db commands** (`scripts/puzzles.py`, one
   store per game over the database, games on a thread pool). Check:
   `finder_walk_back`, `db_positions`, threaded determinism, the registry
   read-only test, a dump of a tiny run.
9. **Bench puzzle set.** Build `data/bench/puzzles.json`, then run the
   end-to-end policy check and the second build over the filled database.
   Check: `puzzle_set_format`, end-to-end check, generation time recorded.
10. **Bench section.** `bench.py` puzzles set, `bench_compare.py`, README
    and concept docs. Check: `puzzle_metrics`, `test_bench_unchanged`;
    bench the heuristic and the current nets into
    `docs/research/exact-puzzles.md`.

## Amendment 1 (draft, 2026-10-27): trivial states are stored as hash and value only

Status: approved 2026-10-27. Written and Rust-tested during the night
run in a worktree; installed and migrated after it: it changes the Rust crates, and the night has the `.pyd` loaded.

**Why.** Most solved states don't need their full record. In `db/solved.sqlite`,
17% of the 2.7M decision states are certain losses (value 0) and 42% are
flawless wins (value 2.0). Many have options whose values are all equal.
The solver only needs a value back when it meets the state again, and it
already has the state in hand then. The state bytes (60–120 B) and the
options blob are only needed to rebuild a state nobody holds: for
training draws, puzzles and the explorer.

**Behavior.**
- **Trivial:** a stored state is trivial when its value is 0 (every line
  loses), or, at a decision, when every option's exact value is within
  `TIE_EPS` (1e-9) of every other's (the choice doesn't matter now).
- **A new table** `trivial (version, key_hash, check_hash, value, cost,
  turns_left)`, primary key (version, key_hash), `WITHOUT ROWID`: about
  30 bytes per row against about 250 in `states`. `check_hash` is a second
  32-bit hash of the bytes (FNV-1a with another offset), so a hit is
  trusted on 96 bits. Expected wrong hits over the database's lifetime
  (~1e10 lookups at a few million rows) are about 1e-10. The no-collision
  guarantee becomes "practically none" for trivial rows only.
- **Writes:** a state offered to the store goes to `trivial` instead of
  `states` when it is trivial. Exception: `add_position` (a played puzzle)
  always writes a full `states` row, moving it out of `trivial`, so every
  puzzle can be rebuilt.
- **Lookups:** the in-memory hash set holds both tables' hashes. A hit in
  `states` is confirmed by bytes as now. A hit in `trivial` is confirmed
  by `check_hash`, and its options are rebuilt from the state in hand
  (`group_options`, every option at the row's value). A distribution
  solve treats a trivial row like a row without distributions: it
  re-solves.
- **Migration:** `puzzles.py db --compact` moves existing trivial rows
  (not referenced by `positions`) from `states` into `trivial`, then runs
  `VACUUM`. It runs once by hand and is irreversible: the bytes are gone,
  though the states can be re-solved. Schema version 2. Opening a version-1
  database adds the empty table, and nothing else changes until
  `--compact`.
- **`stats`** reports rows and bytes per table.

**What this changes elsewhere.**
- **Curriculum exact examples:** `decision_ids` lists only `states` rows.
  Tied decisions are already skipped by curriculum Amendment 2; what this
  adds is that they are never read at all.
- **Explorer:** opens `states` rows only. A trivial state is reachable by
  stepping into it, shown as "trivial: value only".
- **Bench puzzles:** unchanged (they always keep full rows).

**Verification.**
- `db_trivial_roundtrip`: a solve over a store with a database writes its
  trivial states to `trivial` and the rest to `states`. A second solve
  over a fresh handle gives identical values and option values, with the
  hits counted.
- `db_trivial_check`: a forged `trivial` row with the right `key_hash`
  and a wrong `check_hash` is a miss.
- `db_position_full`: `add_position` on a trivial root writes a full row
  and removes the `trivial` one.
- `db_compact`: on a small version-1 database, `--compact` moves exactly
  the trivial rows not in `positions`. Lookups before and after agree on
  every state, and the file shrinks.
- `db_schema_upgrade`: a version-1 database opens and works unchanged.
- Measured: bytes before and after `--compact` on `db/solved.sqlite`,
  recorded in `docs/decisions.md`.

**Steps.**
1. Schema, write path, lookup path, stats. Check: `db_trivial_roundtrip`,
   `db_trivial_check`, `db_position_full`, `db_schema_upgrade`, the
   existing db tests.
2. `--compact` and the measurement. Check: `db_compact`, then run it on
   `db/solved.sqlite` and `db/train.sqlite`.
