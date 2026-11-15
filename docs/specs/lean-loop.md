# Lean loop and low-HP starts (confirmed 2026-10-30)

Status: closed (2026-10-30, read: results doc "Lean loop: no solve step, and a low-HP start slice").

## Why (goals)

Goal 2 needs many training runs judged across seeds; today a round spends
70% of its time in the solve step (big-picture review, addendum 3), so a
recipe question costs ~3x what it needs. Goal 1 and 2 both need nets that
play the fights the gate actually uses: 84-91% of hallway tight fights
start at 1-8 HP, and no self-play game starts below 8 HP. We'll know from
three seeds per arm, compared with the seed check's round-2 retrains on
the same tight2 fights: if lean nets lead the heuristic as much as the
seed check's r2 nets, the solve step goes; if the low-HP slice raises the
hallway lead, it joins the recipe.

## Outcome and non-goals

Outcome: two cheap three-seed runs that answer (a) does the loop need the
solve step at round 2, and (b) does a low-HP start slice help hallway play.
Non-goals: changing `learn.py`'s defaults (only after the result), sweep
time constants, new label kinds, the rules engine.

## Behaviour

- Config key `low_hp: {"share": s, "hp": [lo, hi]}`: in rounds >= 1, a
  share `s` of self-play games start at a whole HP uniform over [lo, hi],
  the rest as before (`selfplay.low_hp_fn`). Round 0's pool is unchanged
  and shared. The dataset config records it as `setup.low_hp`.
- `learn.py --round0 <run id>` reuses that run as round 0 (as the sweep
  does), so the six runs share the night's round-0 net
  (`2026-10-27-score+branch-s0-r0-bd9a1c3`, same pool and validation set).
- Configs `configs/lean-s{1,101,201}.json`: the seed check's r2 config
  with `solve_games` 0, `solve_games0` 0, rounds 0-2, no stop rule.
  `configs/lean-lowhp-s*.json` add `low_hp` share 0.25 at 1-8 HP.

Note: the solved database has 0 rows under the current rules fingerprint
(bosses merge), so the lean arms train with no exact labels at all. The
comparison is "no solve step and no database" against the seed check's r2
nets, which had both. That is the lean loop's real question.

## Fits with

- Configs without `low_hp` build the same dataset configs as before
  (`test_setups.test_low_hp_only_in_later_rounds`, existing pool-config
  tests).
- `learn.learn(round0=...)` unchanged; only the CLI gains the flag.

When in doubt: prefer reusing existing data over regenerating it.

## Scope

`scripts/selfplay.py`, `scripts/learn.py` (dataset config, CLI),
`scripts/tests/test_setups.py`, `configs/lean*.json`, docs. Off limits: the
engine, `sweep.py`, label code, defaults.

## Verification

- `test_setups.py`: `test_low_hp_slice` (share 0.25 at 1-8 gives 25-32% of
  3,000 specs at <= 8 HP, every value 1-7 drawn; share 0 never below 8),
  `test_low_hp_only_in_later_rounds`.
- End to end: the six jobs finish with round.json for r1 and r2 each.

MDE: seed sd of the tight lead ~0.007 overall, so 3 seeds per arm detect
~0.016 overall (2.8 x 0.007 x sqrt(2/3)); hallway/elite/boss cells are
noisier (elite sd 0.017-0.019, boss 0.022-0.025: MDE ~0.04).

## Build steps

1. `low_hp_fn`, the `low_hp` key, `--round0`; tests. Check: test_setups
   passes.
2. (Long run) queue the six runs (~25 min each, 6 threads). Then compare
   r2 against the seed check's r2 nets per half x fight type, and the
   low-HP arm against the lean arm on hallway fights at 1-8 HP; write
   `docs/research/learned-play-results.md` "Lean loop".
