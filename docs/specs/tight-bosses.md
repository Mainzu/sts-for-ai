# Tight boss fights (Hexaghost, The Guardian)

Status: closed (2026-10-30, built and in use; data/bench/tight_bosses.json; read: results doc "Boss lead per boss").

Written 2026-10-30; Next 7's follow-up.

**How this moves the goals.** Every "boss" result so far is Slime Boss
alone. Goal 2's gauntlet (Next 8) needs a per-boss measure, and the boss
lead the nets show (big-picture review 2026-10-30) may be one boss's
weakness of the heuristic. Goal 1 gains more: self-play draws encounters
from `Encounter::ALL`, which leaves the two new bosses out, so for every
existing net they are wholly unseen content with three unseen mechanics
(Burn, Sharp Hide, Mode Shift). We'll know from per-boss paired results:
net minus heuristic on each new boss, against the same on Slime Boss.

## Outcome

A calibrated bench set `tight_bosses` (Ironclad, train and held-out deck
halves, Hexaghost and The Guardian) like tight2's boss cells, and the boss
lead rechecked on it per boss.

Non-goals: adding the bosses to self-play or `sts.encounter_names()`;
feature changes (Burn, Mode Shift stay unencoded, docs/decisions.md "Act-1
bosses merged"); Silent cells for the new bosses; changes to tight2.

## Behavior

- `bench_sets.calibrate_bosses()`: as `calibrate_silent`, for the Ironclad,
  halves `train` (`selfplay.varied_deck`) and `held_out`
  (`held_out_varied_deck`), encounters `NEW_BOSSES = ("hexaghost",
  "the_guardian")`, `PER_ENC_B` 37 cells per boss and half (tight2's
  `PER_ENC2`), v2's games (200 bisect, 800 final) and band, decks from
  `DECK_B_SEED` 79, calibration seeds from `CAL_B_SEED` 5e15, up to
  `REDRAW_B` 4 batches, an encounter whose batch kept nothing not redrawn.
  Saved as `data/bench/calibration_bosses.json`.
- `tight_bosses_set(cal_b, seeds=20)`: {half: specs}, 20 test seeds per
  cell from `TEST_B_SEED` 6e15 by cell index over both halves, group
  `boss`, the cell's index within its half. Built by `build_sets` only when
  the calibration file exists (as tight_silent).
- `--calibrate-bosses` on `bench_sets.py`; the summary print lists the set.
- A short encounter is reported in `short`, not an error. Hexaghost may be
  short: heuristic search won 12% at 40 HP and 25% at 80 HP over 40 varied
  decks (Divider scales with the player's HP), so only strong decks reach
  the band.

## Fits with

- `test_sets_unchanged`: existing sets' hashes stay; `tight_bosses` joins
  `SET_HASHES` once calibrated (step 2).
- `test_silent_tight_set`, tight2 checks: unchanged.
- Seeds: test seeds disjoint from tight2's, tight_silent's and every
  calibration's (new test `test_boss_tight_set`).

**When in doubt:** prefer copying `calibrate_silent`'s shape over a shared
abstraction.

## Scope

`scripts/bench_sets.py`, `scripts/tests/test_bench.py`, `data/bench/`
(new files only), README's bench section, a results section in
`docs/research/learned-play-results.md`. Off limits: the engine, features,
existing set files, self-play.

## Verification

- `test_boss_tight_set` (tiny calibration: 1 cell per boss and half, 20/40
  games): cells only for the two bosses, HPs in 1..max, group `boss`, seeds
  disjoint from tight2 and tight_silent and past the calibration range,
  byte-identical rebuild.
- End to end: the calibration run (step 2) and the per-boss lead (step 3).

## Build steps

1. Code and `test_boss_tight_set`; `test_bench.py` passes. In-session.
2. **Long run** (job queue, 8 threads, est. 60 min): `bench_sets.py
   --calibrate-bosses`; commit the calibration, the set and its hash. Check:
   cells kept per boss and half, excluded reasons.
3. Boss lead per boss: the seed-check round-2 retrains (3 seeds) and the
   heuristic on `tight_bosses` and on tight2's Slime Boss cells, paired by
   fight, per boss and half. Write it into the results doc with MDE (boss
   seed sd 0.022 / 0.025).

Build plan: 3 steps, in-session, on Opus. No stop points expected.
