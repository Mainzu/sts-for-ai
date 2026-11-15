# Bias audit, first slice: does the leaf price enemy Strength and Poison right?

Status: closed (2026-11-02, slice 1 read: results doc "Bias audit, slice 1" and "Bias audit on the 10-29 net"; later slices not queued).

## Why (goal 2)

Review 2026-11-02 (rank 5): the product's losses are decided before the
fatal fight, by HP spent on the way, and the one leaf bias measured so far
(the HP price, `hp_price_probe.py`) was real and paid off when fixed (the
search HP bonus, +0.06 clears with `@hpe`). The enemy-Strength price
(built 2026-11-01) fixed Gremlin Nob but lost at run level, so we don't
know whether the net misprices Strength at all, or whether the fix was
aimed at the wrong thing. This probe measures the leaf's bias directly,
on the states the product actually meets (gauntlet elites and bosses):
for one quantity at a time, the net's static value change against the
change in the true outcome (play-outs). We'll know: a quantity whose
ratio (leaf delta / play-out delta) is below 0.5 or above 2 at 2 se is a
named bias and becomes a targeted fix candidate (a search price or a label
fix for that quantity); ratios near 1 strike leaf-bias arms for these
quantities off the list, and the stop list's "unless a probe first names
the bias they fix" stays shut for them.

## Outcome

`scripts/analysis/bias_audit.py --states 300 --threads 3 --out
results/probes/bias_audit.json`: per perturbation (enemy Strength +2 / +4,
Poison +3 / +6 on one living enemy), mean leaf delta, mean play-out delta
(both with se, paired per state), their ratio, and the same split by group
(elite / boss) and by encounter.

Non-goals: no fix, no engine change, no other quantities (own block,
Vulnerable / Weak, energy, power stacks come in a later slice if this one
names a bias).

## Behavior

- **States.** Gauntlet sequences from 0 up (`gauntlet.sequences`): their
  elite (floors 5, 8) and boss (floor 10) fights that the product reached
  in `results/gauntlet/champion-hpe0.01-two.json`, entered at the
  product's HP there. Each fight is played once with the one-turn
  champion (`@hpb0.01`); `--per-fight` (2) decision states are sampled
  (`random.Random(1)`), one living enemy per state.
- **Perturbation.** The state's codec bytes are patched (as
  `hp_price_probe.py` patches HP): the chosen enemy's Strength or Poison
  amount is raised; nothing else changes (start HP, piles, intents). The
  patch is checked by re-encoding the decoded state.
- **Leaf.** The net's static value (`stsnet.Evaluator`, no HP bonus) of
  each variant; leaf delta = variant - base.
- **Play-outs.** Each variant is played to the end `--k` (16) times with
  the one-turn champion `@hpb0.01` (`sts.play_on`), the same K seeds for
  every variant of a state (common random numbers). Outcome = the net's
  label: `learn.hp_scale(score, w)` with the net's `hp_weight` (2).
  Play-out delta = mean over the K seeds of variant - base.
- Ratio = mean leaf delta / mean play-out delta (se by the delta method,
  states as the unit). Also reported: base leaf vs base play-out mean
  (calibration).

## Verification

A smoke run (4 states, K 4, 1-2 threads) prints a table, every patch
re-encodes to the expected bytes, and Strength +4 makes the play-out
outcome worse on average over the smoke states (a sign check). Then the
full run through the job queue (3 threads).

## Build plan

One step, in session (a fork). Confirmed by the
manager, 2026-11-02.
