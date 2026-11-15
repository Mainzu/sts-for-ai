# Tight fights v2: many calibrated cells for the round checks

Status: closed (2026-10-29, built and in use; data/bench/tight2.json; decisions "Tight fights v2 as built").

## Outcome

The tight fights that decide a round (the gate, `tight_win`, the round-0
window rule, the monotone check) come from a new, larger set. Its
per-half interval is about ±0.01, honestly measured. Today's is about
±0.03, and smaller than it should be, because it treats every fight as
independent.

**Why.** The tight fights today: 1,160 fights over 116 cells (a cell is a
deck family × an encounter × a start HP calibrated so search + heuristic
wins about 50%), 10 seeds per cell. On 2026-10-29
(`docs/research/learned-play-results.md`, "one-round check"):

- **They are cheap now.** The set was built on 2026-10-24, before the
  native build and Rust inference. The whole set plays in ~2 s per player
  and 100 seeds per cell (11,600 fights) in ~20 s.
- **More seeds aren't enough.** At 100 seeds per cell the fight-by-fight
  interval is ±0.01, but a cell's fights share deck, encounter and HP.
  Averaged per cell first, the interval is still ±0.02-0.03 (55-61 cells
  per half). The number of cells limits certainty, and there are only 5
  hand-written families × 15 encounters.
- **The 10-seed set misled us.** s1 r4's +0.035 held-out lead was −0.022
  at 100 seeds per cell.

**Non-goals:** `data/bench/tight.json` and everything built from it (the
bench's tight metrics, the bench puzzles and decision sets, teacher
sizing). They stay as they are, so the puzzles and old bench results stay
comparable. Also out: the Silent; the gate's pass rule (interval above 0
on both halves); the stop rule.

## Behavior

### The set

- **A new file, `data/bench/tight2.json`,** written by `bench_sets.py` from
  its own calibration, `data/bench/calibration2.json`. It has two halves,
  as today:
  - **train:** decks drawn like self-play's varied decks (starter + 3-15
    training-pool cards, `selfplay.varied_deck`);
  - **held_out:** the same deck sizes, with at least 2 cards held out by
    check 6 or check 9 (`standard_held_out_deck`'s rule at varied size).
- **Cells.** Each cell is one drawn deck × one encounter. Encounters cycle
  through all 15 in order, so each half has about the same number of cells
  per encounter. Each cell's start HP is calibrated as today (bisection to
  ~50% for search + heuristic, kept only if inside `CAL_BAND`), but with
  half the games: `BISECT_GAMES2` **200** per probe and `FINAL_GAMES2`
  **800** at the end. A cell only needs its outcome in doubt, not exactly
  50%; the fresh-seed check below confirms each half still lands near
  50%. Cells that can't be calibrated are dropped and listed, and
  more decks are drawn until a half has its cells. Today's 116 family cells
  are included too, so the old matchups stay in.
- **Size (tunable defaults).** `CELLS2` **550** drawn cells per half plus
  the families' cells, `SEEDS2` **20** seeds per cell: about 12k fights per
  half. How the size was chosen, from the 2026-10-29 measurement:
  - The interval has two parts. One is how much the lead truly differs
    between cells (sd ~0.08); only more cells shrink it. The other is
    each cell's seed noise (a fight's sd ~0.41), which more seeds shrink.
  - For ±0.01 per half: 360 cells at 50 seeds, 550 at 20, or 880 at 10.
    Past ~20 seeds, extra seeds buy little, because the spread between
    cells dominates.
  - Seeds cost play time every round; cells cost calibration once (~3.5 s
    each at the lighter settings on 8 threads, measured at ~900 fights/s).
    20 seeds sits between the two: ~1.2 h of calibration, ~1 min of
    tight fights per round.
  - Step 3 measures the real spread and resizes.
- **Seeds.** The calibration seeds and the test seeds come from ranges of
  their own, disjoint from each other, from `tight.json`'s, and from
  self-play's.
- **Spec fields.** Each spec carries its `cell` index (per half) and its
  calibrated `hp`.

### Using it

- `learn.tight_results` plays `tight2.json` instead of `tight.json`. So
  does everything that calls it: the round's `tight_win`, the round-0
  window rule, the monotone check, the gate, `round_check.py` and
  `exact_only.py`.
- **Intervals per cell.** Per half, each cell's mean result is taken
  first; then the mean over cells, with the 95% interval mean ±
  Z · sd / √cells (sd over cells, n − 1). This applies to:
  - **the gate (paired):** per cell, the mean of net − heuristic over its
    specs (Amendment 5's pairing, cells weighted equally). The half passes
    when the interval's lower end is above 0, as now.
  - **`tight_win`:** a player's win rate with the per-cell interval, in
    place of Wilson's, so the monotone check compares honest intervals.
    The round-0 window rule still uses point estimates.
- `every` (the sweep's thinning) keeps every n-th seed **within each
  cell**, so thinning never drops cells.
- `round.json` keeps the per-fight results as now (`tight_results`, one
  0/1 string per player and half, in spec order); the cells are recovered
  from the set.
- **Sweep sizing.** `sweep.TIGHT_FIGHTS` and `TIGHT_RATE_NET` are
  re-measured on the new set, so the plan counts the longer check (~1
  min per round for the net at 12k fights per half, by today's rates).

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| `tight.json` and what's built from it | Byte-identical; bench, puzzles and decision sets unchanged | **new** `old_sets_unchanged`: `bench_sets.py` regenerates `standard`, `families`, `tight` byte-identical |
| Gate pass rule, stop rule | Same rule, now over per-cell means | `paired_gate` (updated), stop rule tests |
| Round records | Same fields; older round.json files still read | existing round tests |
| Sweep plan | Counts the tight-fight time from the new set | sizing tests (updated) |

## Verification

- `tight2_build`: the set regenerates byte-identical from
  `calibration2.json`. Every train deck uses only training-pool cards and
  every held-out deck has at least 2 held-out cards. Encounters are
  balanced within one cell per half. Every cell's HP comes from the
  calibration, and the seed ranges don't overlap the calibration's,
  `tight.json`'s or self-play's.
- `cell_gate`: on hand-made results, identical players give lead 0 and
  fail. A lead spread evenly over cells passes once its interval clears 0.
  The same total lead packed into one cell gives a wider interval than
  when it is spread, and fails. The interval matches a direct
  computation.
- `every_keeps_cells`: thinning by n keeps every cell and every n-th seed
  in each.
- `old_sets_unchanged` (above).
- **Calibration holds on fresh seeds:** search + heuristic wins 0.45-0.55
  per half on the test seeds.
- **Measured (decides the size):** the night's 20 round nets and the three
  check nets are re-scored on the new set (results doc). Per half, the
  per-cell interval's half-width is at most 0.012. If it's wider than
  0.015, **stop point**: resize `CELLS2` / `SEEDS2` from the measured
  spread with the owner.

## Scope

`scripts/bench_sets.py` (the new set and its calibration), `scripts/learn.py`
(`tight_results`, `gate`, `win_rates`), `scripts/bench.py` (`every` within
cells, if that is where it lives), `scripts/sweep.py` (rates), tests,
`data/bench/tight2.json`, `data/bench/calibration2.json`, `docs/` (this
spec, decisions, results). `docs/specs/learned-play.md` gets a note that
Amendment 5's interval is now per cell. Nothing changes in the engine or
the binding.

## Steps

1. **The set's builder and calibration** (`bench_sets.py`), checked on a
   tiny version (a few cells). Then measure calibration time on the first
   20 real cells and project it. Check: `tight2_build` on the tiny set,
   `old_sets_unchanged`.
2. **Full calibration** in the background on 8 threads, leaving half the
   cores free (about 1,450 cells, some dropped, at ~3.5 s each: ~1.4 h by
   today's rates; the projection from step 1 replaces this). Check:
   calibration holds on fresh seeds.
3. **Per-cell intervals and the switch** (`learn.py`, `every`, sweep
   rates). Check: `cell_gate`, `every_keeps_cells`, updated `paired_gate`
   and sizing tests, the existing round tests. Then re-score the night's
   nets and the check nets. **Stop point** if the interval is wider than
   0.015; otherwise review the numbers with the owner.
