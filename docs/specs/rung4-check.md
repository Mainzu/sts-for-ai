# Rung 4 check: do play-out averages make better labels?

Status: closed (2026-10-29, rung 4 gains nothing over three training seeds and stays off; decisions 'Rung 4 check as built (2026-10-29)').

## Outcome

A yes/no, measured before the engine upgrade, on whether rung 4 (labelling
positions far from the end with the average of several games played on
from them, instead of the one game's ending) gives a net that plays the
tight fights better than the same round trained on single endings.

**Why.** The curriculum's labels come from exact values (rung 1), the
previous net's search inside the trusted zone (rung 3), else the game's
ending (rung 5). The trusted zone hasn't left the last turn, so most
valued examples take rung 5: in the night's last round (s1 r10) 76k of
155k. A single ending is a noisy label: luck in the draws after the
position decides much of it. Amendment 3 showed that more exact labels
near the end don't move the tight fights, and idea #50 (in the owner's private idea list)
says rung 4 is "worth it if the remaining errors are far from the end".
Tight fights v2 can now see a change of about 0.01.

**What play-outs can and can't do.** Played by the net that played the
game, play-outs measure the same thing the single ending measures on
average, the value of the position under that net's play, with less
noise: K play-outs plus the ending cut the label's noise variance to
1/(K+1). They don't add better play. So rung 4 can only help if the net's
values are still measurably off from its own play's averages, and if that
error comes from noisy labels.

**Non-goals:** rung 4 in the nightly rounds (`learn.learn`, the sweep);
rung 2 (deep relabel); play-outs on round 0's heuristic games; any change
to the gate or the stop rule; the engine upgrade's own changes.

## Behavior

### Playing on from a stored position (engine and binding)

- **`engine::runner::play_from`**: plays a game from a given state and
  chance generator to the end with an agent. A state waiting on a chance
  event (a divergent afterstate, such as End turn before the draw) is
  advanced with that generator first. `play` becomes: build the start
  state, then `play_from`. Every existing game plays exactly as now.
- **`sts.play_on(combats, evaluator=None, features=None, limit=...,
  threads=...)`**: plays each `Combat` (from `Combat.decode(bytes, seed)`,
  whose seed sets the play-out's chance generator) to the end with the
  search agent `sts.run("search", ...)` builds, on `threads` threads.
  Returns per game `won`, `score`, `hp_end`, `turns`, in order. No
  recording.

### The pre-check (`scripts/rung4.py precheck`)

Measures, with no training, whether there is an error for rung 4 to fix.

- **Positions:** 2,000 valued rung-5 examples (decision states and played
  options' afterstates; the same rule as `learn.ladder`) from s1 r10's own
  games (`d77bb12e7cef`, played by s1 r9's net), 400 per distance band:
  1, 2, 3, 4-5, 6+ turns from the end, drawn with a fixed seed.
- **Play-outs:** 16 per position, by the net that played the game (the
  dataset's `parent_model`) with the dataset's own search settings
  (`config["search"]`), each with its own chance seed.
- **It reports, per band and overall:**
  1. **Play-outs reproduce the games:** mean(single ending - play-out
     mean) with its 95% interval. The ending is one more draw from the
     same play, so the interval must reach 0.
  2. **Label noise:** σ², the mean over positions of the play-outs'
     variance: the noise a single ending carries.
  3. **The net's own error:** err², mean((net's value - play-out mean)²)
     - σ²/16 (the play-out mean's own noise taken out), with a bootstrap
     95% interval, for the playing net (s1 r9) at these positions it
     didn't train on.
  4. **Speed:** play-outs per second, and from it **K** for the main
     check: the largest K from 4 to 16 whose play-outs over all of the
     window's rung-5 examples fit in **1 hour**.
- Writes `runs/rung4/precheck.json`.

### Rung 4 labels

- **The labels:** for each valued example that would take rung 5, the
  target becomes (ending + the sum of K play-out scores) / (K + 1), and
  its rung 4. Rungs 1 and 3, ranking-only examples and the database's
  exact draws are untouched.
- **Producing them** (`scripts/rung4.py labels`): play-outs for every
  such example of the window's datasets (s1 r10's `d77bb12e7cef` and
  `a205959573dd`), each dataset by its own player, cached as
  `cache/rung4/<dataset>-k<K>.npz` (example indices and play-out means),
  so retraining never replays. Rerunning fills only what's missing.
- **Using them:** a config with `"rung4": {"k": K}` makes the training
  set's labelling read that cache for each dataset; a missing cache stops
  the run with an error, never falls back to endings. Configs without the
  key (every nightly config) label exactly as now. `rung_counts` adds a
  `playout` count only when it isn't 0, so nightly `round.json` files keep
  their keys.

### The one-round check (`scripts/rung4.py check`)

Like Amendment 3's round check, against the same database copy
(`db/bounds-check.sqlite`) and window, but both sides retrained:

- **A:** s1 r10's round retrained with its own config (the night's label
  settings).
- **B:** the same, plus `"rung4": {"k": K}`.
- Both are registry runs left unfinished, so no sweep reuses them.
- **Measured:**
  - the tight fights (v2), B paired with A per cell, and each against
    the heuristic (the gate);
  - each net's err² on the pre-check's positions (B's should be lower);
  - val MSE, training time, rung counts.
- **Passes** when B - A's interval lies above 0 on held-out cards and
  isn't below 0 on train cards (its upper end reaches 0 or above).
- Writes `runs/rung4/check.json` and a markdown report.

### Edge and failure cases

- A play-out that hits an illegal state or panics is a bug: the run stops;
  nothing is skipped silently.
- A dataset whose manifest has no `parent_model` (heuristic games) has no
  rung-5 examples in this window; if one appears, the run stops.
- Seeds: play-out chance seeds come from their own range (from 3 x 10^15,
  past tight fights v2's), distinct per dataset, example and play-out, and
  reproducible.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Engine games (`play`, `play_many`, check 4, golden games) | Bit-identical | `engine/tests/determinism.rs` and golden tests (existing) |
| `sts.run`, forced replay (branch games) | Unchanged | `test_branches`, `test_bench` (existing) |
| Nightly labels (`learn.ladder` without `rung4`) | Identical targets, weights, rungs | `test_curriculum` (existing) + **new** `ladder_without_rung4_unchanged` |
| `round.json` `rungs` | Same keys when no rung 4 | **new** assertion in `rung4_labels` |
| Sweep configs, resume keys | No new key in `label_settings` or `ROUND0_KEYS` | `test_sweep` (existing) |
| `round_check.py` | Its modes unchanged | untouched |
| Codec (`Combat.decode`) | Holds everything needed to play on | pre-check item 1 |

## When in doubt

Prefer a clear answer over a quick one; prefer a stop with a measured
reason over a borderline pass.

## Scope

May change: the engine's runner (`play_from` only), the Python binding
(`play_on`), `scripts/learn.py`'s labelling (the `rung4` cache read and
rung 4 in `ladder` / `rung_counts`), a new `scripts/rung4.py`, tests,
`docs/` (this spec, decisions, results).

**Off limits:** the search agent, the codec, the net, `sts.run`'s
interface, `learn.learn` and the sweep, `round_check.py`, the gate and
the stop rule, the solver and its database (read only, via the copy).

## Decisions taken (provisional)

- Play-outs are played by the game's own player (owner, 2026-10-29), so
  they test noise reduction alone.
- Play-outs get at most ~1 hour (owner); K follows from the measured
  speed, 4-16.
- The pass rule is B over A on held-out, not worse on train (owner).
- The single ending counts as one of the K + 1 samples.
- Rung 4 stays out of nightly rounds until this check passes.

## Outside assumptions

- **The codec holds the whole game state for playing on** (the solver
  already relies on it for exact values). Checked by the pre-check's
  item 1: if the play-outs' mean differs from the endings, stop.
- **The manifest names the playing net and its search settings**
  (`parent_model`, `config["search"]`). Checked when the pre-check starts.
- **Play-outs run near self-play speed** (net rounds ~200 games/s on all
  threads; a play-out is part of a game). K 4 over 76k examples in an
  hour needs ~85 play-outs/s. Measured by the pre-check.

## Verification

Tests first:
- `play_from_matches_play` (Rust): for check 4's specs, `play` and
  `play_from` on the same start state and generator give the same result
  and trajectory.
- `play_on` (Python): deterministic per seed; different seeds give
  different games from one stored position; a divergent afterstate plays;
  a finished state returns its own result; results come back in order.
- `rung4_labels`: on a small fake dataset with a fake cache, rung-5 valued
  examples get (ending + sum) / (K + 1) and rung 4; rung 1 and 3
  examples, ranking-only weights and exact draws are unchanged; a missing
  cache raises; `rung_counts` gains `playout` only when it is above 0.
- `ladder_without_rung4_unchanged`: on a real dataset, targets, weights
  and rungs equal today's.

End to end: the pre-check's item 1 (play-outs reproduce the games), then
the one-round check's verdict.

## Don't guard

The search agent's internals, the codec format, float summation order in
Python, timing noise from other sessions.

## Build steps

1. **`play_from` and `play_on`** (engine runner, binding; rebuild with no
   Python process holding `sts`). Check: `play_from_matches_play`, the
   engine tests, `play_on` tests, `test_branches`, `test_bench`'s old sets.
2. **The pre-check** (`rung4.py precheck`, ~10 min). Check: it runs and
   writes its report. **Stop points:** item 1's interval misses 0 (the
   play-outs don't reproduce the games: a bug to find first); err²'s
   interval reaches 0 overall (the net already matches its own play's
   averages, so rung 4 has nothing to fix); K below 4 within the hour.
   Otherwise go on.
3. **Rung 4 labels** (`learn.py`, `rung4.py labels`). Check:
   `rung4_labels`, `ladder_without_rung4_unchanged`, `test_curriculum`,
   `test_rounds`.
4. **Play-outs for the window** (long run: ~1 hour, 8 threads). Check:
   every rung-5 valued example of both datasets has K play-outs in the
   cache.
5. **The one-round check** (`rung4.py check`, ~45 min: two trainings and
   three tight-fight runs). Check: verdict computed and written.
6. **Write-up** (results doc, decisions), then review with the owner.
   **Stop point:** the review decides whether rung 4 goes into nightly
   rounds (its own spec).

## Amendment 1 (2026-10-29): training seeds · built 487cd9d

**Why.** Rerun against the night's own database (`db/train.sqlite`), the
check gave B - A +0.006 / +0.005 (train / held-out) and narrowly failed;
the first run's +0.017 came mostly from the bounds-walked copy weakening
A. Retraining the same round already moves the lead by about 0.007, so one
retrain per arm can't separate a 0.005 effect from training luck. The
owner chose (2026-10-29) to measure that before speccing rung 4 for the
nightly rounds.

### Behavior (adds to the one-round check)

- `rung4.py check --seeds S1 S2 ...` trains A and B once per training
  seed (the `seed` `learn.fit` takes; it sets the net's initialisation and
  the batch order), against `db/train.sqlite`, with the same play-out
  caches (K 12). The night's seed (1) is the first; the default list is
  1, 101, 201. Runs already in `runs/rung4-nightdb/check.json` (seed 1)
  are reused; results per seed are kept under their seed, resumable as
  now.
- **Measured per seed:** B - A paired per cell (as now), each arm's lead
  over the heuristic, val MSE, training minutes, err².
- **Measured over seeds:** per fight spec, the mean over seeds of (B - A);
  then per cell and the interval over cells as now. Also the spread of
  the per-seed B - A means and A's own spread over seeds (the training
  noise).
- **Passes** when, on held-out, B - A's point estimate is above 0 at every
  seed and the seed-averaged interval lies above 0; and on train the
  seed-averaged interval's upper end reaches 0 or above.

### Verification (added)

- `seeds_verdict` on hand-made per-seed results: passes when every seed's
  held-out B - A is above 0 and the averaged interval clears 0; fails when
  one seed's is at or below 0, or when the average's interval reaches 0.
- `seeds_average`: averaging specs over seeds before the per-cell step
  matches a direct computation.

### Scope

`scripts/rung4.py`, tests, docs. Nothing else.

### Steps

A1. Seeds in `rung4.py check` and the over-seeds summary. Check:
    `seeds_verdict`, `seeds_average`, `test_rung4.py`.
A2. The run (~45 min: four trainings, four tight-fight runs). Then
    write-up and review with the owner. **Stop point:** the review
    decides whether to spec rung 4 for the nightly rounds.
