# Exact-only experiment: can the net learn one-turn-out values?

Status: closed (2026-10-28, approved and read: results doc "Exact-only experiment" and its rerun).

## Outcome

One answer, in about an hour of compute, no night: **is the net's horizon-1
weakness a data problem, a mismatch between what it trains on and what
search asks it, or a limit of the net itself?** The answer picks the next
version.

**Why.** The curriculum night (`docs/research/learned-play-results.md`,
"Curriculum night") left every net at about 0.03 mean regret on the bench
puzzles one turn from the end (horizon 1), round 1 to round 10, against the
zone's 0.01. The heuristic and the older nets sit at 0.02-0.03 there too
(`docs/research/exact-puzzles.md`). Horizon 0 proves nothing about an
evaluator: one-turn search sees the end of the fight and scores it exactly,
so the zone's verified horizon 0 never tested the net.

Three explanations fit, and the experiment separates them:

1. **Too little exact data.** `db/train.sqlite` holds about 175k decision
   positions one turn from the end and 65k two turns out (solver's
   `turns_left`, 2026-10-28), but each night round drew only about 9.2k
   exact decisions (`EXACT_CAP` 50k examples with their afterstates),
   beside about 77k outcome labels and 70k search labels.
2. **The wrong states.** One-turn search scores its leaves with the net,
   and its End turn leaf is the state right after End turn, paused at the
   next turn's draw (`engine/src/search.rs`, `child`). The exact examples
   give value targets only to decision states; those afterstates are
   ranking-only (weight 0), labelled with their option's value. So the net
   is never taught the exact value of the states it is asked about most.
3. **The net can't represent it** (features or size): then it fails to fit
   these values even on the rows it trains on.

**Non-goals:** changing the curriculum, the sweep or the gate; a night run;
new engine or binding code (everything needed is in `sts`: `SolvedDb`
`fetch` / `lookup`, `Combat.decode` / `options`, `solve`).

## Behavior

`python scripts/exact_only.py [--db db/train.sqlite] [--out runs/...]`
builds two training sets from the training database (never
`db/solved.sqlite`, whose rows are the bench puzzles' tails), trains one net
on each from scratch, scores them and writes a results table.

### The two arms

Both draw the current version's decision rows with `turns_left` 0-3, dull
ones skipped (`learn.dull`, as the curriculum), every row at `turns_left`
1-3 and as many `turns_left` 0 rows as those together (drawn at a fixed
seed). 10% of rows, by key hash, are held out for the fit check.

- **A, decisions:** each decision state labelled with its exact value; its
  options' afterstates ranking-only, exactly as `learn.exact_examples`
  builds them (no cap). The curriculum's exact labels, with more of them.
- **B, decisions + leaves:** A, plus every option afterstate gets a value
  target of its own exact value (not the option's): from `SolvedDb.lookup`
  (which answers trivial rows too, so certain losses get 0), else solved
  on the spot (`sts.solve`, default budget; unsolvable afterstates stay
  ranking-only and are counted). An End turn option's afterstate is the
  paused state search scores, so B teaches it directly.

The value weights of decision states and afterstates are equal per
example. Training: `train.train` with the night rounds' settings
(`effects` features, `RANK_WEIGHT`, score target), same seed for both arms;
the validation set is the held-out rows.

### What it measures, per arm (plus the night's `s1 r10` net and the heuristic as references)

- **Puzzle regret per horizon** (the decider): `learn.trusted_zone`'s
  per-horizon mean regret on the bench puzzles, both halves, dull puzzles
  skipped, with a 95% bootstrap interval per horizon (puzzles resampled),
  and the paired difference against the heuristic at horizons 1 and 2.
- **Fit:** value MSE on training rows and held-out rows, split by state kind
  (decision state / afterstate paused at a draw / other afterstate) and by
  `turns_left`. The nets at `s1 r10` and the heuristic are scored on the
  same held-out rows.
- **Tight-fight win, paired against the heuristic** (diagnostic only: these
  nets never saw an early-fight position).

### Reading the result

- **B well under 0.03 at horizon 1** (ideally at or under 0.01), A not:
  explanation 2. The next version gives the search's leaf states exact
  value targets.
- **A and B both well under 0.03:** explanation 1. The next version makes
  the solver the main teacher near the end and raises the share.
- **Both near 0.03, held-out MSE high but training MSE low:** the net fits
  the rows it saw but not new positions; more varied positions, not more
  labels.
- **Both near 0.03 and training MSE high too:** explanation 3; look at the
  features and size before any more label work.

Sizes (rows per arm, example caps) are set from free memory and measured
time, not asked for; the results record them.

## Verification

- `exact_only_arms` (a small fixture database, solved in the test): arm A's
  examples are exactly the non-dull decision rows' states with their values
  and their afterstates at weight 0; arm B's afterstates carry their own
  exact value (a certain-loss afterstate 0, an End turn afterstate paused
  at its draw equal to `sts.solve` on it), with value weight > 0.
- `held_out_split`: the split is deterministic and no row is in both sets.
- Regret table: on two puzzles with known picks, the per-horizon means and
  the paired difference match a hand computation.

## Scope

New `scripts/exact_only.py` and its test. `learn.exact_examples` may gain
optional arguments (row ids, afterstate labels) with today's behavior
unchanged by default. Results go to `docs/research/learned-play-results.md`.

## Steps

1. Arms builder with its tests. Check: `exact_only_arms`,
   `held_out_split`, existing `test_curriculum`.
2. Train both arms and score them with the references. Check: the results
   table, the regret table test. Stop point: review the result with the
   owner, who picks the next version.
