# Data scaling: round-0 games per group (confirmed 2026-10-31)

Status: closed (2026-11-01, read: decisions "Data scaling: 80k shows no gain over 40k").

## Why (goals)

The coverage pilot's full-pool arm (`cover21`, 5,000 round-0 games per
group, fresh round 0 per seed) trails the lean arm (20,000 per group, one
shared round 0) by ~0.04 on both halves at round 1, larger than anything a
label or curriculum variant has bought. If data per round is the lever,
it moves goal 2 (strength on train) and goal 1 (the held-out lead rose by
the same amount) for CPU minutes alone, and every later experiment should
run at the better size. Two things make the gap unproven: the lean arm's
three seeds share one round-0 net (the 2026-10-27 night's), so its seed sd
leaves out round-0 luck; and cover21 ran on the pre-threshold-rows layout.
We'll know from a three-point curve (5k / 20k / 40k games per group, five, five and three
fresh round-0 seeds each, same layout): if 20k beats 5k by more than the
MDE on either half, data size is real; the 40k point says whether to go
further.

## Outcome and non-goals

Outcome: round-1 lead over the heuristic on tight2 per half x fight type
for `data{5,20}k-s{1,101,201,301,401}` and `data40k-s{1,101,201}`, the seed sd per arm including round-0
luck, and minutes per run. Non-goals: changing `learn.py` defaults (only
after the result), later-round size (`n_round` stays 1048), coverage at
20k (a follow-up if 10 kinds at 20k is worth asking), Silent.

## Behaviour

- Configs `configs/data{5,20,40}k-s*.json`: the `cover21-s*`
  configs (lean recipe, full 21-kind pool, fresh round 0 with
  `train_seed` 1000 + seed, rounds n 1) with `n_train` 5,000 / 20,000 /
  40,000 and no `train_pool` key (full pool is the default). Same seeds
  across arms, so round-0 pools nest by seed where the generator allows.
- They run on main after the threshold-rows merge, so all thirteen share one
  feature layout. The 5k arm reruns cover21 on that layout (and is its
  layout check: within ~0.01 of cover21 means the merge didn't move
  non-slime, non-Guardian play).

## Fits with

No code change. Memory: round 0 at 40k doubles the 20k fit's examples;
check free RAM before the runner starts each 40k job (the runner checks
`--mem-gb`).

## Verification and MDE

Each job ends with round 1's round.json. Seed sd with fresh round 0s: the
coverage arms showed 0.005-0.017 per half overall (cover21 0.017 / 0.014,
about twice the shared-round-0 sd); take 0.015. Five seeds for 5k and
20k (seeds 301 / 401 added, `train_seed` 1000 + seed) detect
2.8 x 0.015 x sqrt(2/5) ~ 0.027 per half; 40k against 20k (3 vs 5) ~0.031;
per fight type ~0.06. Read with `scripts/analysis/coverage_read.py`-style output (arms
data5k / data20k / data40k), and report minutes per run.

## Build steps

1. Write the thirteen configs. Check: each differs from `cover21-s*` only in
   name, `n_train`, the dropped `train_pool` (and seeds for s301 / s401). Done: jobs 0045-0057.
2. (Long run, after the threshold-rows merge, 6 threads each; ~12 / ~35 /
   ~65 min) queue them, 5k first. Then the curve into
   `docs/research/learned-play-results.md` "Data scaling", and a
   decision on the experiment default size under "For the owner".
