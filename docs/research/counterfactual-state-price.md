# Counterfactual state price: step-1 read (lane counterfactual-state-price)

Spec `docs/specs/counterfactual-state-price.md`; charter `lane/counterfactual-state-price` (closed).

## Step 1 read (2026-11-11, job 0889; diagnostic re-run with own prices)

Job `jobs/done/0889-cf-price-probe.json` (pin d5db794), output
`results/cf_price/probe.json`; the same probe with an own-price column run by
hand at the lane's HEAD, `results/cf_price/probe-own.json` (identical term
and worth columns, so the run is deterministic). The leaf-numbers probe's
167 held-out cells x 3 fights = 501 fights a set, 1,438-1,969 draw and
decision leaves a set; k = 4 windows a price; se over fights. Ran 1.5
minutes against a 20-minute estimate (the 3-cell smoke run predicted
about 10; greedy windows are cheaper than the estimate assumed).

| set | perturbation | term change | own price | worth |
|---|---|---|---|---|
| without | str-2 | +4.32 (1.33) | +4.07 (0.26) | +9.89 |
| Disarm | str-2 | -4.02 (4.93) | +5.74 (0.33) | +12.51 |
| Impervious | str-2 | +1.94 (13.39) | +0.72 (1.88) | +13.07 |
| Intimidate | str-2 | -5.05 (8.33) | +0.19 (4.20) | +9.81 |
| without | weak+1 | -4.45 (3.15) | +1.09 (0.06) | +2.67 |
| Disarm | weak+1 | -10.27 (5.95) | +1.19 (0.11) | +2.50 |
| Impervious | weak+1 | +47.77 (25.70) | +0.46 (0.10) | +2.45 |
| Intimidate | weak+1 | -14.19 (10.83) | +0.61 (0.08) | +2.19 |
| without | ritual+2 | +2.49 (14.81) | -30.20 (3.82) | -2.03 (rollout) |
| Disarm | ritual+2 | +41.80 (23.61) | -56.62 (5.82) | -2.53 |
| Impervious | ritual+2 | +61.79 (76.40) | -68.90 (6.23) | -2.87 |
| Intimidate | ritual+2 | +54.10 (42.58) | -40.39 (7.08) | -2.88 |
| without | demonform+2 | +180.79 (57.50) | +185.18 (58.63) | +41.68 (rollout) |
| Disarm | demonform+2 | +52.89 (92.37) | +63.46 (91.89) | +45.60 |
| Impervious | demonform+2 | +85.53 (94.67) | +29.87 (87.10) | +32.29 |
| Intimidate | demonform+2 | +70.16 (63.22) | +85.01 (62.63) | +39.14 |

**Verdict: fail** (0 of 4 inside; the charter's stop rule needs 3). The
diagnostic own price fails the same way, so the fail is the method's, not
the summing. Why:
- **The sum is noise.** An edit changes every other element's windows
  (greedy plays differently, the shared seeds fall on different draws), so
  the term change carries other elements' price shifts, extrapolated by
  the remaining rounds: se 3-95 HP, Weak +1 negative on three sets.
- **Strength and Weak at a single element: about half their worth or
  less.** Strength -2 +0.2 to +5.7 against +9.8 to +13 (the net's own
  price is +4.9); Weak +1 +0.5 to +1.2 against +2.2 to +2.7. The greedy
  policy blocks first when attacked, so a weaker hit often saves block,
  not HP, and the window prices block saved at 0. The worths are upper
  estimates (`measurement/leaf-numbers@probe`), but Weak's is one turn,
  and the term undershoots it too.
- **Growth extrapolation overprices 10-25 times.** Ritual 2's own price is
  -30 to -69 HP against a greedy rollout worth of -2 to -3 to the fight's
  end; Demon Form 2's is +30 to +185 against +32 to +46 with se 60-90
  (heavy tails). The quadratic sum over the heuristic's remaining rounds
  (`turns_left_estimate`) runs far past where the played-out fight ends:
  the rollout's monsters die (or the fight turns) long before the
  extrapolated rounds, and an early large per-round gain squares.
- **What it changes.** A one-window counterfactual scaled by expected
  rounds is not a usable leaf price under the greedy policy: neither the
  window (block absorbs the difference) nor the scale (fight length is
  the thing the leaf can't see) holds. This agrees with `@pl2`
  (`measurement/projected-leaf@cards-k2`): crediting ticks by a guessed
  horizon moves HP only where fights are already won. The value that keeps
  paying after the leaf is what deeper search (the product's second turn,
  `cause/leaf-gain-third`) and the 5k bursts (`measurement/later-ticks-count@burst5k`)
  reach; a hand-built simulation price did not. About 0.15 thread-h used
  of the 5 cpu-h cap. Step 2 (the search flag) is not built.
