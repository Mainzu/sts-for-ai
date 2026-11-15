# Bench baseline (2026-10-24)

First full run of the evaluation bench (`scripts/bench.py`) on search +
heuristic and the two value nets from `generalise.py`
(`models/value_effects.pt`, `models/value_ids.pt`), at commit `887e970`;
representation checks and a random-evaluator floor rerun at `2cc01ca`
(the other numbers didn't change).
All agents use the same one-turn search (limit 16, no sampling). Brackets
are 95% intervals; two configs differ only when they don't overlap.

Regenerate:

```bash
.venv/Scripts/python scripts/bench.py --evaluator heuristic --out results/baseline/heuristic.json
.venv/Scripts/python scripts/bench.py --evaluator models/value_effects.pt --out results/baseline/effects.json
.venv/Scripts/python scripts/bench.py --evaluator models/value_ids.pt --out results/baseline/ids.json
.venv/Scripts/python scripts/bench.py --evaluator bench:random_evaluator --out results/baseline/random_evaluator.json
.venv/Scripts/python scripts/bench_compare.py results/baseline/*.json
```

Runtime per evaluator: heuristic 42 s, effects net 222 s, ids net 219 s,
random 68 s. The random evaluator scores states with a fixed hash of their
features (unrelated to value) and is the floor any evaluator must beat.

## Tight fights (~50% win rate for search + heuristic)

Decisions: 1,000 per half against the cached reference search; regret and
ranking on all decisions, `rank(unc)` on decisions where the reference
didn't hit the node cap.

| Half | Config | mse | regret | ranking | rank (uncapped) | win | HP lost |
|---|---|---|---|---|---|---|---|
| held-out | heuristic | – | 0.037 [0.023, 0.053] | 0.918 [0.900, 0.935] | 0.952 [0.937, 0.966] | 0.496 [0.455, 0.538] | 8.6 [7.4, 10.0] |
| held-out | effects | 1.030 [0.939, 1.116] | 0.040 [0.027, 0.056] | 0.882 [0.860, 0.902] | 0.916 [0.894, 0.937] | 0.460 [0.419, 0.502] | 9.4 [8.2, 10.7] |
| held-out | ids | 1.032 [0.947, 1.122] | 0.034 [0.025, 0.045] | 0.872 [0.850, 0.893] | 0.904 [0.881, 0.925] | 0.447 [0.406, 0.489] | 9.6 [8.3, 10.9] |
| held-out | random | 1.238 [1.205, 1.268] | 0.131 [0.106, 0.161] | 0.744 [0.716, 0.771] | 0.770 [0.736, 0.803] | 0.178 [0.148, 0.212] | 12.8 [11.4, 14.3] |
| train | heuristic | – | 0.056 [0.039, 0.075] | 0.899 [0.881, 0.919] | 0.939 [0.922, 0.954] | 0.528 [0.488, 0.567] | 8.4 [7.3, 9.6] |
| train | effects | 0.853 [0.798, 0.906] | 0.094 [0.070, 0.118] | 0.844 [0.823, 0.867] | 0.883 [0.861, 0.903] | 0.426 [0.388, 0.466] | 9.5 [8.4, 10.7] |
| train | ids | 0.840 [0.789, 0.893] | 0.085 [0.065, 0.107] | 0.831 [0.809, 0.855] | 0.863 [0.840, 0.885] | 0.402 [0.363, 0.441] | 9.6 [8.5, 10.7] |
| train | random | 1.204 [1.167, 1.237] | 0.175 [0.143, 0.209] | 0.701 [0.674, 0.727] | 0.728 [0.696, 0.759] | 0.184 [0.155, 0.216] | 12.7 [11.5, 14.0] |

Random ranks ~0.70–0.74, not 0.5: search scores wins and deaths exactly,
whatever the evaluator, so some pairs are ordered right for free.

## Standard set (starting HP, today's check 5/6/8 mix)

| Half | Config | mse | win | HP lost |
|---|---|---|---|---|
| train | heuristic | – | 0.927 [0.891, 0.951] | 22.6 [20.0, 25.3] |
| train | effects | 0.067 [0.047, 0.090] | 0.937 [0.903, 0.959] | 24.7 [21.9, 27.4] |
| train | ids | 0.064 [0.045, 0.087] | 0.947 [0.915, 0.967] | 23.1 [20.5, 25.6] |
| held-out | heuristic | – | 0.957 [0.927, 0.975] | 19.9 [17.6, 22.5] |
| held-out | effects | 0.166 [0.120, 0.210] | 0.963 [0.936, 0.979] | 21.6 [19.3, 24.2] |
| held-out | ids | 0.246 [0.187, 0.302] | 0.950 [0.919, 0.969] | 22.4 [19.9, 25.1] |
| Silent A | heuristic | – | 0.720 [0.667, 0.768] | 32.0 [28.8, 35.1] |
| Silent A | effects | 0.182 [0.123, 0.252] | 0.773 [0.723, 0.817] | 33.5 [30.4, 36.5] |
| Silent A | ids | 0.214 [0.141, 0.292] | 0.740 [0.688, 0.786] | 31.7 [28.5, 34.6] |
| Silent B | heuristic | – | 0.853 [0.809, 0.889] | 26.3 [23.4, 29.4] |
| Silent B | effects | 0.423 [0.348, 0.499] | 0.823 [0.776, 0.862] | 29.0 [26.3, 31.9] |
| Silent B | ids | 0.486 [0.404, 0.574] | 0.840 [0.794, 0.877] | 29.1 [26.4, 32.0] |

## Representation

Probes: 14 hand-built pairs, each with a reference gap of at least 0.05
(5 HP). Aliasing: within each saved decision, pairs of options that encode
to identical features but differ in reference value by more than 0.05
(22,123 sibling pairs in all).

| Config | probes passed (of 14) | aliased pairs, effects features | aliased pairs, own features |
|---|---|---|---|
| heuristic | 1.000 [0.79, 1.00] | 0 | – |
| effects | 0.857 [0.60, 0.96] (fails block_matches_hit, debuff_no_artifact) | 0 | 0 |
| ids | 1.000 [0.79, 1.00] | 0 | 1 (held-out) |
| random | 0.571 [0.33, 0.79] (fails 6) | 0 | – |

- **The effect features tell apart every pair of options search compares.**
  So where the nets rank badly, the cause is learning, not the
  representation.
- **The id features don't:** the one aliased pair is Uppercut vs Uppercut+,
  both held-out cards, so both map to the same `unknown` id (reference
  values 0.011 vs 0.080). This is the failure effect features exist to
  avoid, caught by the audit.

## Reading

- **Do the nets rank held-out actions correctly?** Mostly, but worse than
  the heuristic: 0.88 (effects) and 0.87 (ids) against 0.92 on held-out
  ranking; regret overlaps the heuristic's. On training cards the gap is
  clearer: both nets' regret (0.09) is above the heuristic's (0.056) with
  non-overlapping intervals, and their tight-fight win rate is lower.
- **The nets don't play better than the heuristic** anywhere on the tight
  fights; on the standard set all three overlap.
- **Effects vs ids:** indistinguishable on the tight fights. The effects
  net's lead shows only in standard-set held-out prediction (0.166 vs
  0.246, intervals overlap slightly), consistent with check 6/9's margins.
- **Held-out looks easier than train** for every evaluator (lower regret,
  higher ranking), the heuristic included, so it's a property of the
  decision sets, not of generalisation. Compare gaps between evaluators,
  not to zero.
- **Tight-fight mse is high** (~0.85–1.03) because the nets were trained on
  full-HP games and these fights end in a loss about half the time.

This is the baseline `learned-play` sets out to beat.
