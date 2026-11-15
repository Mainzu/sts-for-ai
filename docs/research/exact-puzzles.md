# Exact puzzles: do the heuristic and the current nets play endgames exactly? (2026-10-26)

The "measure first" answer from the exact-solver spec (`docs/specs/exact-solver.md`, step 10).
It's measured before any curriculum is built.

**Setup.**
- **The set:** `data/bench/puzzles.json` holds 1,000 puzzles per half, one per tight-fight game. The games were played by search + heuristic on fresh seeds (9,010,000+).
- **Exact values:** each puzzle is a real decision near the end of its game, solved exactly (`sts.solve`, 1M-node budget).
  - Every option's value is the true expected score under best play, with every random event listed.
  - These values were checked by playing the solver's own policy out 400 times on 200 puzzles (inside its 95% interval on 99% of them).
- **What's scored:** the evaluator's one-turn search (limit 16), as the agents play, against those exact values.
- **Evaluators:** the heuristic, `models/value_effects.pt`, and Amendment 3's final round nets.
  - `runs/2026-10-26-score-s0-r10-f3320c0` (A3 s0 r10)
  - `runs/2026-10-26-score-s1-r10-ddf9e4a` (A3 s1 r10)
- **Runs:** full bench at c99599f plus the step-10 bench code. The result files are in `results/exact-puzzles/`, about 100 s per evaluator.
  ```
  python scripts/bench.py --evaluator <e> --out results/exact-puzzles/<name>.json
  ```

**Metrics.**
- **accuracy:** the share of puzzles where the search picks an exactly best option.
- **regret:** exact best minus the exact value of the pick, in score units (0.01 is about 1 HP, or 0.5% of a win).
- **ranking:** order accuracy over option pairs whose exact values differ.
- **contested:** puzzles whose gap (best minus second best) is ≥ 0.05.
- **horizon:** the game's final turn minus the puzzle's turn.
- **Intervals:** 95% bootstrap.

## Answer

**The mistakes are real, and they sit one turn or more from the end.**
- **Horizon 0 (the last turn, 77% of puzzles):** every evaluator is exact. One-turn search sees the end of combat and scores it exactly, so no evaluator matters there.
- **Horizon ≥ 1 (448 puzzles, both halves):** every evaluator picks a non-best option 9-11% of the time.
  - Mean regret is 0.02-0.03, about 2-3 HP per puzzle.
  - Over half of those mistakes give up more than 0.05.
  - On contested puzzles, accuracy is 89-97% and regret 0.02-0.05.

**Nets and heuristic are indistinguishable here.**
- Paired on the same 448 deeper puzzles, regret minus the heuristic's:

  | net | minus heuristic |
  |---|---|
  | value_effects | +0.002 [-0.015, +0.020] |
  | A3 s0 r10 | -0.010 [-0.026, +0.006] |
  | A3 s1 r10 | -0.005 [-0.020, +0.011] |

- Every interval holds 0.
- 86 of the 448 deeper puzzles fool at least one evaluator. 13 fool all four: shared blind spots one turn out, which one-turn search over any of these evaluators misses.
- Held-out minus train gaps all hold 0.

**What this means for the curriculum.**
- Exact labels have something to fix: about 10% wrong picks at horizon 1-2+, with regret large enough to matter in fights won or lost by a few HP.
- The current nets haven't learned endgames better than the heuristic.
- The contested and horizon ≥ 1 cells are the informative ones. "All" is dominated by horizon 0, where every evaluator scores 100% by construction.
- With about 230 deeper puzzles per half, the set resolves differences of about 0.02 in regret, not finer.

## Results


#### all

| evaluator | half | n | accuracy | regret | ranking |
|---|---|---|---|---|---|
| heuristic | held_out | 1000 | 98.4% [97.6, 99.1] | 0.006 [0.001, 0.011] | 96.5% [95.1, 97.6] |
| heuristic | train | 1000 | 97.3% [96.3, 98.3] | 0.008 [0.004, 0.013] | 95.0% [93.3, 96.6] |
| value_effects.pt | held_out | 1000 | 98.0% [97.1, 98.8] | 0.005 [0.001, 0.009] | 95.9% [94.4, 97.3] |
| value_effects.pt | train | 1000 | 96.9% [95.8, 98.0] | 0.010 [0.005, 0.016] | 94.8% [93.4, 96.1] |
| A3 s0 r10 | held_out | 1000 | 98.0% [97.0, 98.8] | 0.004 [0.001, 0.009] | 96.0% [94.5, 97.2] |
| A3 s0 r10 | train | 1000 | 97.5% [96.5, 98.4] | 0.006 [0.002, 0.010] | 94.6% [93.2, 96.0] |
| A3 s1 r10 | held_out | 1000 | 98.5% [97.7, 99.2] | 0.004 [0.001, 0.008] | 96.1% [94.2, 97.7] |
| A3 s1 r10 | train | 1000 | 97.6% [96.7, 98.5] | 0.008 [0.004, 0.014] | 95.3% [93.9, 96.7] |

#### contested

| evaluator | half | n | accuracy | regret | ranking |
|---|---|---|---|---|---|
| heuristic | held_out | 118 | 95.8% [91.5, 99.2] | 0.030 [0.003, 0.067] | 94.8% [91.7, 97.6] |
| heuristic | train | 141 | 90.1% [85.1, 95.0] | 0.043 [0.018, 0.075] | 93.8% [90.6, 96.8] |
| value_effects.pt | held_out | 118 | 94.9% [90.7, 98.3] | 0.033 [0.007, 0.072] | 94.8% [92.1, 97.0] |
| value_effects.pt | train | 141 | 89.4% [84.4, 94.3] | 0.046 [0.021, 0.074] | 92.2% [89.2, 95.1] |
| A3 s0 r10 | held_out | 118 | 94.9% [90.7, 98.3] | 0.030 [0.003, 0.068] | 95.3% [92.6, 97.7] |
| A3 s0 r10 | train | 141 | 94.3% [90.1, 97.9] | 0.021 [0.005, 0.042] | 94.9% [92.3, 97.4] |
| A3 s1 r10 | held_out | 118 | 96.6% [93.2, 99.2] | 0.026 [0.001, 0.066] | 96.3% [93.8, 98.4] |
| A3 s1 r10 | train | 141 | 92.9% [88.7, 97.2] | 0.038 [0.013, 0.068] | 94.6% [91.9, 97.2] |

#### per horizon (all puzzles)

| evaluator | half | h0: n / accuracy / regret | h1: n / accuracy / regret | h2+: n / accuracy / regret |
|---|---|---|---|---|
| heuristic | held_out | 790 / 100.0% [100.0, 100.0] / 0.000 [0.000, 0.000] | 154 / 91.6% [87.0, 96.1] / 0.036 [0.006, 0.073] | 56 / 94.6% [87.5, 100.0] / 0.003 [0.000, 0.008] |
| heuristic | train | 762 / 100.0% [100.0, 100.0] / 0.000 [0.000, 0.000] | 159 / 88.7% [83.6, 93.1] / 0.030 [0.013, 0.054] | 79 / 88.6% [81.0, 94.9] / 0.044 [0.014, 0.085] |
| value_effects.pt | held_out | 790 / 100.0% [100.0, 100.0] / 0.000 [0.000, 0.000] | 154 / 90.9% [85.7, 94.8] / 0.021 [0.003, 0.052] | 56 / 89.3% [80.4, 96.4] / 0.023 [0.002, 0.052] |
| value_effects.pt | train | 762 / 100.0% [100.0, 100.0] / 0.000 [0.000, 0.000] | 159 / 90.6% [86.2, 95.0] / 0.019 [0.006, 0.035] | 79 / 79.7% [70.9, 88.6] / 0.091 [0.036, 0.167] |
| A3 s0 r10 | held_out | 790 / 100.0% [100.0, 100.0] / 0.000 [0.000, 0.000] | 154 / 90.9% [85.7, 95.5] / 0.016 [0.002, 0.041] | 56 / 89.3% [80.4, 96.4] / 0.029 [0.002, 0.076] |
| A3 s0 r10 | train | 762 / 100.0% [100.0, 100.0] / 0.000 [0.000, 0.000] | 159 / 91.8% [86.8, 95.6] / 0.023 [0.005, 0.046] | 79 / 84.8% [75.9, 91.2] / 0.027 [0.009, 0.054] |
| A3 s1 r10 | held_out | 790 / 100.0% [100.0, 100.0] / 0.000 [0.000, 0.000] | 154 / 94.2% [90.3, 97.4] / 0.019 [0.002, 0.047] | 56 / 89.3% [80.4, 96.4] / 0.013 [0.000, 0.035] |
| A3 s1 r10 | train | 762 / 100.0% [100.0, 100.0] / 0.000 [0.000, 0.000] | 159 / 93.1% [89.3, 96.9] / 0.014 [0.004, 0.029] | 79 / 83.5% [74.7, 91.1] / 0.076 [0.028, 0.136] |

#### held-out minus train

| evaluator | accuracy (all) | regret (all) | accuracy (contested) | regret (contested) |
|---|---|---|---|---|
| heuristic | 0.011 [-0.002, 0.024] | -0.003 [-0.009, 0.005] | 0.057 [-0.007, 0.116] | -0.012 [-0.054, 0.032] |
| value_effects.pt | 0.011 [-0.003, 0.024] | -0.006 [-0.013, 0.002] | 0.056 [-0.007, 0.115] | -0.012 [-0.055, 0.035] |
| A3 s0 r10 | 0.005 [-0.008, 0.017] | -0.002 [-0.007, 0.004] | 0.006 [-0.050, 0.060] | 0.009 [-0.029, 0.052] |
| A3 s1 r10 | 0.009 [-0.003, 0.021] | -0.005 [-0.011, 0.002] | 0.037 [-0.021, 0.088] | -0.012 [-0.054, 0.033] |

#### for context: tight-fight win and decisions regret (contested), same files

| evaluator | half | win | regret@decisions |
|---|---|---|---|
| heuristic | held_out | 49.6% [45.5, 53.8] | 0.037 [0.023, 0.053] |
| heuristic | train | 52.8% [48.8, 56.7] | 0.056 [0.039, 0.075] |
| value_effects.pt | held_out | 46.0% [41.9, 50.2] | 0.040 [0.027, 0.056] |
| value_effects.pt | train | 42.8% [38.9, 46.7] | 0.094 [0.070, 0.118] |
| A3 s0 r10 | held_out | 45.3% [41.2, 49.5] | 0.037 [0.023, 0.055] |
| A3 s0 r10 | train | 47.5% [43.6, 51.5] | 0.073 [0.053, 0.094] |
| A3 s1 r10 | held_out | 43.8% [39.7, 48.0] | 0.033 [0.022, 0.047] |
| A3 s1 r10 | train | 47.4% [43.4, 51.3] | 0.072 [0.050, 0.096] |

#### paired, horizon ≥ 1 puzzles of both halves (448)

| evaluator | wrong picks | regret | picks giving up > 0.05 |
|---|---|---|---|
| heuristic | 9.6% (43) | 0.031 [0.017, 0.048] | 30 |
| value_effects.pt | 11.4% (51) | 0.033 [0.019, 0.049] | 29 |
| A3 s0 r10 | 10.0% (45) | 0.022 [0.010, 0.036] | 24 |
| A3 s1 r10 | 8.7% (39) | 0.027 [0.014, 0.042] | 24 |

## Notes

- **Random-evaluator floor.** A random leaf evaluator searched through ranks 77-82% of contested puzzle pairs right, and 86-87% of all pairs. The decisions set's floor is about 72%. The puzzle floor is higher because so many puzzles end within the searched turn.
- **What the set leaves out.** The puzzles are the tails that fit the solver's budget, walked back from each game's end. Horizon 2+ is only 6-8% of the set, and bigger mid-fight positions aren't in it. The set measures endgames, not openings.
- **Matches the tight set.** The tight-set numbers in the same result files match each run's own `bench.json` (for example, A3 s0 r10 tight win 0.453 / 0.475). So the existing metrics are unchanged.
