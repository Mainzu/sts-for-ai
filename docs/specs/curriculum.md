# Curriculum labels

Status: closed (2026-10-27, built and in use; decisions "Curriculum as built", "Curriculum Amendment 1 as built"); Amendments 2-3 built, A3's label settings reverted 2026-10-30 (352a3386).

## Outcome

Self-play rounds whose training labels come from the most trustworthy source
available for each position: exact values from the solved-position database
(rung 1), else the previous net's one-turn search value where the puzzles
show that net is accurate (rung 3, blended with the game's ending), else the
game's ending (rung 5). Accuracy then grows backward from the end of fights,
round by round. Success is a net whose search beats search + heuristic on
the tight fights (the existing gate). The puzzles' per-horizon scores show
whether the trusted zone is moving outward.

It replaces the outcome-only labels of learned-play rounds for the score
target. Learned-play Amendment 4's code (greedy self-play, branch rollouts,
sizing, watcher) stays; its D4 sweep is superseded and won't run.

**Non-goals:** rungs 2 and 4 (see Later); the HP-histogram head (switch 6
configs keep outcome labels); search labels on round 0's heuristic games
(wrong scale); any change to the gate or the stop rule; engine or feature
changes.

## Behavior

### The ladder, per training example

Every training example gets its label from the highest rung that applies.

1. **Exact (rung 1).** The example's state is in the solved-position
   database (current rules version) → its exact value.
2. **Search (rung 3).** Otherwise, if the example has a search number that
   looked further than the state itself, and its distance from the end is
   inside the trusted zone of the net that played its game → blend:
   `w_near` × search number + (1 − `w_near`) × the game's final score.
   `w_near` defaults to **0.8** (tunable).
3. **Outcome (rung 5).** Otherwise → the game's final score.

**Which examples have a usable search number:**

| Example | Search number | Notes |
|---|---|---|
| Sampled decision state (6 per game, as now) | The best option's recorded value | |
| Afterstate of the played option, when that option is deterministic or listed-chance | That option's recorded value | |
| Afterstate of the played option, when it is divergent (End turn, big draws) | None, so outcome or exact only | The search number there is the old net's direct rating of that state: copying it teaches nothing |
| Afterstate of an option not played | — | **Ranking only:** value-loss weight 0, kept for the ranking term, ordered by the recorded search values (or by exact option values when the decision is in the database). Branch games give some of these options real endings. |

**Today's labels change in one other way.** Not-played afterstates were
labelled with the played game's ending in the value loss. Now they only
feed the ranking term.

**Round 0** (heuristic games) uses rungs 1 and 5 only. The heuristic is
just the first player: its games supply positions to solve, and endings
for the parts that can't be solved. None of its numbers go into a label.
That makes round 0 a different run from learned-play's round 0, even on
the same games:

- **Games are reused.** The heuristic pool's recorded games (registry
  datasets) are the same games, so they're reused.
- **Nets are not.** Every run's config records `labels: "curriculum"` with
  its label settings (`w_near`, `exact_cap`, `exact_share`, the frontier
  rule). `sweep.ROUND0_KEYS` gains them, so `find_round0` never reuses an
  outcome-labelled round-0 net (Amendments 1-4), or one trained with
  different label settings.
- **The database's size is recorded.** Its row count when round 0 trained
  goes into `round.json`. It isn't part of the reuse key: a later round 0
  over a fuller database is still a valid reuse, and the count shows the
  difference.

**Distance from the end:** the played game's final turn minus the state's
turn (an afterstate takes its decision's distance). This matches the
puzzles' "played horizon", so the trusted zone and the puzzle scores
measure the same thing.

### The trusted zone

- After each round's net is trained, the bench's puzzle section runs for it
  (puzzles only, seconds). Each horizon h is **verified** when it has at
  least `min_puzzles` puzzles (default **50**) and the net's mean exact
  regret there is at most `regret_max` (default **0.01**, about 1 HP; both
  tunable).
- The **frontier** is the last horizon of the unbroken run of verified
  horizons starting at 0, plus 1. A label at distance d+1 rests on the
  net's ratings about one turn closer to the end, so one extra turn is
  trusted. When horizon 0 isn't verified, there's no trusted zone, and rung
  3 isn't used for that net's games.
- Each dataset uses the frontier of **the net that played it**, read from
  that net's `round.json`. In a window of rounds k and k−1, each round's
  games are labelled with their own player's frontier.
- `round.json` records the per-horizon scores, the frontier, and how many
  examples took each rung.

### Exact examples from the database

- Each training set adds up to `exact_cap` examples (default **50,000**;
  tunable, counted in the memory sizing). They are sampled with a fixed
  seed from the database's current-version `states` rows, decoded with the
  codec and encoded into features like any state, with the exact value as
  label.
- A decision row also brings its options' afterstates as ranking-only
  examples, ordered by the row's exact option values.
- Their value-loss weights are scaled so they make up `exact_share` of each
  epoch's total value-loss weight (default **0.2**; tunable). Without that,
  a few thousand exact positions are lost among ~500k self-play examples.

### Growing the database each round

- Before building a round's examples, the round's new games are walked back
  and solved into the database (the exact-solver finder:
  `puzzles.py --run`, positions sourced to that dataset). The work is
  capped at `solve_games` games per round, taken in game order: the
  default is sized from the solver's measured rate to about 15 minutes.
  The cap counts games, not time, so runs stay reproducible.
- Round 0's heuristic pool is solved once, in `sweep.py --round0`, capped at
  about 60 minutes' worth of games.
- Rung 1 then covers the tails of the games each net trains on.

### Caches

- Dataset feature caches store each example's label inputs, not its
  labels: its own outcome, search number (or none), option kind, played or
  not, distance, its decision's grouping, and its codec bytes.
- `learn.fit` applies the ladder when it loads them. A cache built once
  stays valid as the database grows and as frontiers are measured.
- Cache version `v6`.

### Sizing: free memory, not a fixed cap

The owner's rule: use as much memory as speeds the run up, as long as
other processes on the laptop aren't pushed into paging.

- **Budget.** The fixed `WORKER_GB` (6.5) is replaced. When the sweep
  plans, it reads the memory that's physically free
  (`GlobalMemoryStatusEx`, already used by the watcher) and subtracts
  `MEM_MARGIN` (default **2 GB**, tunable) for other processes. The rest,
  divided by `--jobs`, is each run's budget. `--plan` prints the free
  memory, the margin and the budget it sized to.
- **The peak model has to be right.** Sizing from free memory only works if
  the estimate of a run's peak is accurate. Today's model is 0.7 GB base +
  2× the training examples while concatenating. It was checked against one
  round's training (6.88 GB), but a whole real run peaked at **8.21 GB**
  (Amendment 4, D2), and the cause was never found. Likely suspects:
  building a fresh dataset's feature cache, or self-play holding every
  recorded state. Step 7 finds it. Measure each phase of one real round
  (self-play, solve step, cache build, example load and concatenation,
  normalizer, training, puzzle and tight-fight checks) at two sizes, then
  either reduce the peak where it's cheap or add it to the model. The
  curriculum's new parts (exact examples, the solve step, the label inputs
  in the cache) are measured the same way.
- **Guard.** The watcher's existing memory check (commit charge near its
  limit) stays the protection against paging; a slow run is also flagged.

### Everything else stays as built

Validation (the real-outcome val set), the tight-fight gate against the
heuristic, the stop rule (rounds 6-10), the round-0 window rule, greedy
self-play with branches, sizing and the watcher are unchanged. The label
scale check keeps warning when mean labels drift from mean outcomes; with
search labels some drift is expected, and the warning is the signal to
look.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| `train.py` value loss | With every weight 1, the loss equals today's | **new** `weight_one_identity`: same loss to the bit on a fixed batch |
| Ranking term | Same formula; only its ordering values may come from exact values | existing ranking tests |
| Registry datasets and games | Format unchanged; existing datasets replay and build v6 examples | **new** `old_dataset_builds`: a pre-change tiny dataset builds v6 examples |
| HP-histogram configs (switch 6) | Outcome labels as today | **new** `hp_loss_unchanged`: switch 6 examples' targets identical to v5's |
| Solved-position database | Training only reads it; writes go through the finder's solve step | **new** `train_reads_only`: building examples leaves the database's row count unchanged |
| Bench | Unchanged; its puzzle section is called per round | bench tests |
| Round-0 reuse (`sweep.find_round0`) | Reuses only round-0 nets trained with the same labels and label settings; recorded games are still reused | **new** `round0_not_reused`: a registry holding an Amendment 3 round-0 run (outcome labels) and a curriculum round-0 run with other `exact_share` → neither is reused for a curriculum config; the pool dataset is |
| Sweep, watcher | Still plan, run, size and watch; the projection adds solve time and exact examples; sizes come from free memory, not `WORKER_GB` | sizing tests (updated), `sizing_free_memory`, `--plan`, tiny dry run |
| Engine, features, binding's existing calls | Unchanged | existing suites, golden trajectories |

## When in doubt

Prefer falling back to the game's ending over a label from a rung that
hasn't been verified.

## Scope

May change: `scripts/` (`learn.py`, `selfplay.py`, `registry.py`,
`train.py`, `stsnet.py` for the weight and the new extras, `sweep.py`
sizing, `puzzles.py` for the solve step, tests), `py/src/lib.rs` (new
read-only database calls: look up a state's exact value and options, sample
rows), `configs/`, `docs/`, `README.md`, `docs/specs/learned-play.md` (mark
D4 superseded) and `docs/specs/queue.md`.

Interfaces it may change: the label path of score configs, the dataset
cache format (v6), new binding calls.

**Off limits:** the engine, `solvedb`'s schema and write path, the feature
format, the score, the bench's sets and metrics, the gate and stop rule,
switch 6's labels. No new dependencies.

## Decisions taken (provisional, also in docs/decisions.md)

- Labels follow the ladder per example: exact if solved, else a blend of
  the playing net's one-turn search value and the outcome inside that net's
  verified zone, else the outcome. This replaces outcome-only labels for
  score configs.
- The trusted zone comes from measurement: per-horizon exact regret on the
  bench's puzzles, an unbroken run from the end, plus one turn.
- Not-played options are ranking-only. Divergent options (End turn, big
  draws) never take search labels.
- Each round solves its own games' tails into the database (a game-count
  cap, for reproducibility). Exact examples get a fixed share of the loss.
- Learned-play Amendment 4's D4 sweep is superseded by this spec's run.
- Runs are sized to the memory free at plan time minus a margin, split
  across jobs, instead of the fixed 6.5 GB. The peak model is refit to
  measured whole-round peaks, the unexplained 8.21 GB included.
- Tunable defaults: `MEM_MARGIN` 2 GB, `w_near` 0.8, `regret_max` 0.01, `min_puzzles` 50,
  `exact_cap` 50,000, `exact_share` 0.2, `solve_games` ~15 min per round,
  round-0 pool ~60 min.

## Outside assumptions

None from outside the project. Internal bets, checked by the run:

- **Puzzles cover several horizons with ≥ 50 each,** so a frontier past 1
  is possible. The exact-solver's step 7 measures the horizon spread. If
  only horizons 0-1 are covered, the frontier can't move past 2. That's
  the first thing to look at in review.
- **Solving one round's games fits about 15 minutes for a useful share of
  tails.** Set from the solver's measured rate.

## Verification

Tests written first:

- `weight_one_identity`, `old_dataset_builds`, `hp_loss_unchanged`,
  `train_reads_only` (Fits with).
- `ladder_exact`: an example whose state is planted in a temporary
  database gets its exact value, whatever its distance.
- `ladder_search`: decision at distance 1 with frontier 2 →
  0.8 × best value + 0.2 × outcome; same at distance 3 → outcome; frontier
  none → outcome; played divergent option's afterstate → outcome; played
  deterministic option's afterstate inside the zone → blend with that
  option's value.
- `not_played_rank_only`: not-played afterstates have value weight 0 and
  rank by search values; with the decision in the database, by exact option
  values.
- `round0_no_search`: round 0 examples never take rung 3, even with a
  frontier.
- `frontier_rule`: per-horizon (count, regret) inputs → expected frontier:
  unbroken run, a gap stops it, too few puzzles stops it, horizon 0 failing
  gives none.
- `frontier_per_dataset`: rounds k and k−1 in one window use their own
  playing nets' frontiers.
- `exact_share`: the exact examples' total value weight is `exact_share` of
  the total (to 1e-6); at most `exact_cap` drawn; the same draw for the
  same seed.
- `cache_ingredients`: a v6 cache built before rows are added to the
  database yields exact labels for them on the next load, without
  rebuilding the cache.
- `solve_step`: a round's solve step solves at most `solve_games` games,
  in game order, sourced to the dataset id.
- `sizing_free_memory`: with free memory mocked at 12 GB, margin 2 and
  `--jobs 2`, each run's largest training set fits 5 GB under the peak
  model; with 4 GB free it fits 1 GB per run, or the plan refuses to start
  when that is below the smallest round worth running.
- `peak_model_matches`: on one real round at two sizes, the model's peak
  is within 10% of the measured whole-round peak (the largest phase), and
  never below it.

**End-to-end:**

1. A tiny dry run: 3 rounds at tiny sizes, against a database filled by
   the step. It finishes, and each `round.json` has the per-horizon scores,
   the frontier and the counts per rung.
2. The real run: `sweep.py` with the curriculum, both seeds, rounds 6-10,
   with the watcher.
3. The result goes into `docs/research/learned-play-results.md`: the tight
   fights against the heuristic (the gate) and the frontier per round.

## Don't guard

- A database from another rules version: lookups already ignore its rows.
- Frontier jumps of several horizons in one round: allowed, since each is
  measured.
- Label drift warnings with search labels: logged, not fatal.

## Build steps

1. **Pins.** `weight_one_identity` (against today's loss), `old_dataset_builds`
   (pinning today's v5 build), `hp_loss_unchanged`. Check: they pass on
   unchanged code.
2. **Value-loss weight** (`Dataset.weight`, `train.py`). Check:
   `weight_one_identity`.
3. **Label inputs in the cache** (distance, search number, kind, played,
   codec bytes; v6) and ranking-only not-played afterstates. Check:
   `cache_ingredients` (database part stubbed), `not_played_rank_only`,
   `old_dataset_builds`, `hp_loss_unchanged`.
4. **Database reads** (binding lookup and sample), rung 1, exact examples
   with their share. Check: `ladder_exact`, `exact_share`,
   `train_reads_only`, `cache_ingredients`.
5. **Trusted zone and rung 3** (puzzle scores per round, frontier rule,
   per-dataset frontiers, blend). Check: `frontier_rule`,
   `frontier_per_dataset`, `ladder_search`, `round0_no_search`.
6. **Solve step** per round and for the round-0 pool; label settings in
   the config and in `ROUND0_KEYS`. Check: `solve_step`,
   `round0_not_reused`.
7. **Sizing and docs.**
   - **Memory:** find the unexplained peak by measuring every phase of a
     real round at two sizes. Reduce it where that's cheap, and refit the
     peak model to the measurements.
   - **Budget:** size runs to free memory minus `MEM_MARGIN`, split across
     jobs, instead of `WORKER_GB`.
   - **Projection:** count the solve time and the exact examples.
   - **Records and docs:** `round.json` gets the rung counts; update the
     README, `learned-play.md` (D4 superseded) and decisions.

   Check: `peak_model_matches` (measurements written to
   `docs/decisions.md`), `sizing_free_memory`, the sizing tests,
   `--plan --jobs 2`, the tiny dry run. **Stop point** if the night doesn't
   fit at sizes worth running.
8. **The run** (night, watcher), then review with the owner. **Stop point:**
   the review decides what's next (rung 2 or 4, tuning, or the gate is
   met).

## Later (ideas, not built here)

Neither is scheduled.

- **Rung 2, deep relabel.** Re-score sampled decision states with a
  two-turn search over the playing net (sampling big events, `sample_k` 4),
  replacing the one-turn number in the blend. Less of the net's error per
  label; about 20 ms per position at Rust speed. Worth it if the frontier
  stalls while puzzle regret just past it is small.
- **Rung 4, play-out averages.** For positions outside the trusted zone,
  replace the single game's ending with the average of several games
  played on from the position (`forced=` replay, different seeds). Less
  noise without more examples, which matters because memory caps the
  training set. Worth it if the remaining errors are far from the end.

## Amendment 1 (2026-10-27): train from memory-mapped caches

**Why.** Step 7's stop point fired. This laptop has 15.7 GB, of which about
4.7 GB is available with everything closed (kernel pools and background
processes hold the rest). The step-7 peak model (1.25 GB + 12.8 KB per
example) then allows about 60k training examples per run: rounds of under
150 games per group even at `--jobs 1`, and `--round0` (7.3 GB) can't run.
The cost is holding every example in RAM, twice while parts are
concatenated, and the pool's whole cache while round 0 builds it.

**Behavior.**
- **Caches are memory-mapped.** The feature cache (v7) is stored as plain
  arrays that `numpy` can memory-map (one uncompressed `.npy` per field). A
  memory-mapped file is read from disk page by page as it is touched;
  Windows keeps those pages as file cache, which it drops whenever another
  process needs memory, so they never push anything into the page file.
- **No copy of the training set.** A round's training set is a view over
  its parts' mapped caches: per part, the indices of the examples it uses
  (round 0's sample included) and their labels and weights (in RAM, small).
  Batches gather only their own examples from the mapped files. Nothing
  concatenates the examples in RAM or writes them again to disk.
- **The cache build streams.** Building a cache writes each chunk of games
  to the files as it goes, so its peak doesn't grow with the dataset
  (`--round0`'s pool included).
- **Exact examples** are written once per draw as a cache of their own and
  mapped like the others.
- **The normalizer and validation** read the mapped arrays in chunks.
- **Training order** is unchanged in meaning (a seeded permutation, or
  decisions kept whole for the ranking term), so with the same data and
  seed the trained net is bit-identical to step 7's.
- **Sizing.** The peak model becomes a base plus a small per-example term
  (indices, labels, weights), refit by re-measuring with `memprobe.py` at
  two sizes. Runs are then sized by time (the night) and by disk: caches
  stay under `CACHE_CAP`, and the planner refuses when free disk is below
  the caches the night will write plus a margin (`DISK_MARGIN`, default
  2 GB). File cache isn't counted against the memory budget.
- **Speed.** When the mapped caches don't fit in the file cache, batches
  read from the SSD. The time projection is re-calibrated from the
  measurement; a slowdown over 25% in training time per example against
  step 7's in-RAM rate is a stop point.

**Fits with.**

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Training result | Same data and seed → same net, bit for bit | **new** `mapped_same_net`: one round's net trained from the view equals the in-RAM concat's |
| Example builds | Same arrays as v6 | `old_dataset_builds` (pins read through the v7 cache) |
| Everything in the base spec's Fits with | Unchanged | its tests |

**Verification.**
- `mapped_same_net` (above).
- `cache_v7_streams`: building a cache of N and 4N games peaks within
  10% of each other.
- `view_batches`: batches from the view equal `Dataset.concat(...).batch`
  on the same indices, across part boundaries, with round 0's sample and
  exact examples.
- `sizing_disk`: free disk below the night's caches plus `DISK_MARGIN` →
  the plan refuses.
- `peak_model_matches` re-measured (model ≥ measured, within 10%).
- `--plan --jobs 1` at today's free memory sizes rounds of at least
  `MIN_N_ROUND`; the tiny dry run passes.

**Scope.** As the base spec, plus `scripts/memprobe.py`. The cache format
(v7) is the one interface it changes. Old v6 caches are rebuilt on demand.

**Steps.**
1. **v7 cache and streaming build** (`registry`, `stsnet.Dataset` save,
   load and append). Check: `cache_v7_streams`, `old_dataset_builds`.
2. **Training view** (training set over mapped parts; `train.py`,
   normalizer, validation and `learn.training_set` read through it).
   Check: `view_batches`, `mapped_same_net`, `weight_one_identity`,
   `exact_share`.
3. **Re-measure and resize** (memprobe at two sizes, peak model, disk
   check, time rates). Check: `peak_model_matches`, `sizing_disk`,
   `--plan --jobs 1`, the tiny dry run. **Stop point** if training slows by
   more than 25% or the night still doesn't fit.
4. Then base step 8 (the run).

## Amendment 2 (2026-10-27): the trusted zone and exact examples skip dull decisions

**Why.** A puzzle whose options all have the same exact value scores
regret 0 whatever the net picks, so it adds evidence the net never earned.
In the bench set that is 73% of horizon-0 puzzles (1,133 of 1,552), 27% of
horizon 1, 10% of horizon 2. They dilute the mean: at horizon 0 the
effective `regret_max` on puzzles that test a choice was about 0.037,
not 0.01. The owner, browsing the explorer, added the same day: a decision
where the only worse option is ending the turn with cards still playable
tests nothing interesting either.

**Behavior.**
- **Dull decision** (`learn.dull`): every option except End turn is
  within `TIE_EPS` (1e-9) of the best exact value. That covers all options
  tied, and "only End turn loses". A decision where some card play is worse
  stays in, whether End turn is worse, equal or best.
- A horizon's count and mean regret use only puzzles that aren't dull.
  `min_puzzles` counts those too.
- `round.json` records per horizon `n` (counted), `tied` (dull, skipped)
  and `regret`.
- The bench's own puzzle metrics are unchanged (its "contested" subset
  already exists); this is only the zone.
- **Exact examples skip dull decisions** (owner): `exact_examples` passes
  over a dull decision row and draws the next. In `db/solved.sqlite` 17% of
  decision rows are certain losses, all tied.
- Round 0 was restarted (the first run's solve step overran its sizing; the
  second was killed with its session), so it trains with this amendment.

**Verification.** `zone_skips_dull`: given puzzle rows and picks, dull
puzzles (tied, or only End turn worse) are left out of each horizon's count
and mean and counted as `tied`; a puzzle with a worse card play is kept,
with End turn worse or best; the frontier then follows from the counted
puzzles. `exact_share` gains: with no cap, the drawn decisions are exactly
the database's decision rows that aren't dull (the fixture has both kinds).

**Steps.** 1. `trusted_zone` through a tested helper. Check:
`zone_skips_dull`, `frontier_rule`. 2. Exact examples skip dull rows. Check:
`exact_share`.

## Amendment 3 (2026-10-29): exact labels a turn or two from the end

Status: approved 2026-10-29.

**Why.** The curriculum night (2026-10-28) ended level with the heuristic,
and its trusted zone never moved past one turn from the end. Two things
held the exact labels back:

- **There were few of them, mostly at the last turn.** Each round drew
  about 9.2k exact decisions (the 50k cap counts the options' afterstates
  too). 85% of `db/train.sqlite`'s decision rows are at `turns_left` 0
  (1.37M, against 175k at 1 and 65k at 2), because walks without solver
  bounds stopped before the positions further out.
- **They labelled the wrong states for one-turn search.** Search scores
  the state right after End turn, before the next draw (a state paused at
  a random event). The exact examples never labelled those states.

The exact-only rerun (`docs/research/learned-play-results.md`, 2026-10-28)
fixed both, on a database walked with bounds (`db/bounds.sqlite`) and with
the paused states labelled (arm B). Trained on nothing else, that net picks
as well as the night's net one and two turns from the end (bench games'
positions: 0.028 / 0.032 against 0.031 / 0.031). On the bench puzzles two
turns out it is the best evaluator (0.030 against the night's 0.072). It
can't play whole fights. This amendment puts its labels into the
curriculum next to the rest.

**Non-goals:** `regret_max`, the frontier rule and rung 3 (unchanged: the
zone may stay at one turn, and these labels don't depend on it); the gate
(learned-play Amendment 5's paired gate, as built); a database merge tool;
the solver.

### Behavior

- **Paused states join the exact examples.** Each drawn decision row also
  gives one value example per exact (not bounded) option that pauses at a
  random event: that paused state, labelled with the option's exact value
  (`exact_examples(..., leaves=True)`, as arm B built them). These count
  toward `exact_cap` and share the exact examples' value weight
  (`exact_share`) with the decision states.
- **The draw is split by distance from the end.** Half of the drawn
  decisions come from rows at `turns_left` 0 and half from rows at 1 or
  more. Each side has its own fixed random order (`EXACT_SEED`). Rows are
  taken from the two sides in turn until the next row's examples wouldn't
  fit under the cap; when one side runs out, the other fills the rest. The
  experiment split its rows the same way. Dull decisions are still
  skipped.
- **The draw gets bigger.** The `exact_cap` default goes from 50,000 to
  **150,000**: about 25k decisions with their paused states, ~2.7x the
  night's exact value examples. The planner already counts exact examples
  in a round's training time (2.9 ms per example), so this adds ~5 min per
  round and the plan shrinks the games to fit. The one-round check below
  decides whether 150k is enough. `exact_share` stays 0.2.
- **The settings are recorded.** `label_settings` gains `exact_leaves`
  (true) and `exact_split` (0.5), so they join `sweep.ROUND0_KEYS`. Round 0
  then retrains under them: its pool's games are reused, and its solve
  step walks the pool again, now with bounds. Configs without the keys
  keep the Amendment 2 draw (no paused states, no split), so old runs
  replay.
- **The next night's database starts from `db/bounds.sqlite`.** That
  database holds the population the experiment needed: 357k decisions one
  turn out, 384k two, and 103k at the last turn. It was walked with bounds
  from the night's own self-play games, not the bench's. The old
  `db/train.sqlite` (3.5M rows, walked without bounds) moves aside to
  `db/train-2026-10-28.sqlite`. A copy of `db/bounds.sqlite` becomes
  `db/train.sqlite`, and the night's solve steps grow it as before.
- **The solve step is resized.** `sweep.SOLVE_S_PER_GAME` goes from 12.0
  to **7.5**, measured on the bounded re-walk (525 games in 63 min on 6
  threads, 7.2 s per game). The 15-minute rule per round, and 60 minutes
  for round 0's pool, stay. Each step then walks more games, and each game
  gives 5-7x the positions it used to.

### Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Configs without the new keys | Same exact examples as Amendment 2 | **new** `exact_draw_unchanged`: without `exact_leaves` / `exact_split` the fixture gives the same examples, in the same order, as today's code |
| `exact_share` | The exact value weights (decision states and paused states) sum to the share | `exact_share`, extended with paused states |
| Round-0 reuse | Not reused across different `exact_leaves` / `exact_split` | `round0_not_reused`, extended |
| Solver bounds | Bounded options give no paused-state example; their afterstates keep the one-sided term | `test_bounds` (`dull_bounded`, `ranking_bounded`), plus `exact_split` below |

### Verification

- `exact_split`: the fixture database has rows at `turns_left` 0 and at
  1-3, with dull rows and bounded options among them. The draw takes rows
  from the two sides in turn until the cap. When one side runs out, it
  fills from the other. It skips dull rows. The same seed gives the same
  draw. Paused states carry their option's exact value, and none come from
  bounded options.
- `exact_draw_unchanged`, `exact_share` (extended), `round0_not_reused`
  (extended).
- **One-round check (the measurement that decides the cap).** Retrain the
  night's last round, s1 r10, with the new settings against a copy of
  `db/bounds.sqlite`, at below-normal priority. It uses the same window
  (datasets `d77bb12e7cef` and `a205959573dd`), their frontiers and the
  same seed. Then compare the new net with s1 r10's own net on:
  - the bench puzzles: regret per horizon, paired against s1 r10;
  - the bench games' other positions (`db/solved.sqlite`): 600 non-dull
    decisions at `turns_left` 1 and 2 with every option exact, as in the
    rerun;
  - the tight fights, paired against the heuristic (Amendment 5's gate).

  It passes when the new net is at least level with s1 r10 one turn out,
  better two turns out, and its tight-fight lead is not lower by more than
  the paired interval. If 150k doesn't pass, the check runs once more at
  400k. **Stop point** either way: the owner reviews the numbers before
  the night. Results go to `docs/research/learned-play-results.md`.

### Scope

`scripts/learn.py` (the draw, the settings), `scripts/sweep.py`
(`SOLVE_S_PER_GAME`), a check script (`scripts/round_check.py`, reusing
`exact_only.py`'s tables), tests, and `docs/` (this amendment, decisions,
results). The database files move as above. Nothing changes in the engine,
`solvedb` or the binding.

### Steps

1. Split the draw and add paused states, behind the new settings. Check:
   `exact_split`, `exact_draw_unchanged`, `exact_share`,
   `round0_not_reused`, the existing curriculum tests.
2. One-round check (above). **Stop point:** the owner reviews it and
   decides on the night.
3. Swap the database, set `SOLVE_S_PER_GAME`, then `--plan`, the tiny dry
   run, and the night (`sweep.py --round0`, both seeds, watcher).
