# Dead neurons and the activation function (2026-11-15)

From an owner question while exploring the nets with the neuron microscope
(`scripts/analysis/neurons.py`): why do some neurons respond to nothing,
and would another activation function keep them alive?

## Why neurons die

A ReLU neuron outputs max(0, x). Once an update pushes x below 0 for every
input, it outputs 0 and gets no gradient, so nothing brings it back. After
that, Adam's weight decay shrinks its weights at a steady rate (Adam
rescales the decay-only gradient), its pre-activation settles at its
negative bias, and the head's weights on it shrink too (product net: weight
norm 0.17 dead vs 0.58 live; head |weight| 0.0018 vs 0.019).

- Not born dead: in a fresh net trained with snapshots
  (`results/neurons/fresh5k`), all 64 card neurons respond to some card at
  step 0. Seven die between step 8 and step 1,134 of 1,237.
- Not a probe artefact: none of the product net's dead card neurons fires
  on any card row of 281 decision states from greedy play.
- The card encoder sees only about 100 distinct card vectors, so one update
  can put all of them on the negative side.

## Dead neurons per layer

`neurons.py dead`: units whose pre-activation stays at or below 0 on every
decision state of 200 greedy-played fights (872 states; live monster slots
only). Layers are named by the module (`card.2` = the card encoder's
output layer, `head.0.0` / `head.0.2` = the head's two hidden layers).

| Net | card.2 | monster.2 | head.0.0 | head.0.2 |
|---|---|---|---|---|
| product 10-29 (281 states) | 16/64 | 6/64 | 97/256 | 43/128 |
| ReLU s1-s3 | 8, 11, 4 | 4, 4, 3 | 126, 107, 108 | 46, 46, 44 |
| LeakyReLU 0.01 | 2, 7, 4 | 3, 5, 2 | 109, 70, 89 | 14, 9, 21 |
| LeakyReLU 0.1 | 0, 0, 0 | 1, 1, 3 | 8, 2, 12 | 0, 0, 2 |
| SiLU | 0, 0, 0 | 0, 0, 0 | 2, 1, 3 | 0, 0, 0 |

The biggest loss is in the head: with ReLU about 40-50% of its first layer
and a third of its second never turn on.

## The screen

Same data for every arm: a fresh round-0 dataset under today's rules
(the product's config, 5,000 games per group; train `486f91a11382`, val
`ba211042ece2`), seeds 1-3, `neurons.py retrain --fresh 5000 --act <a>
--seed <s>`. Best validation MSE (score units, labels are real outcomes):

| Activation | s1 | s2 | s3 | Mean | Paired vs ReLU |
|---|---|---|---|---|---|
| ReLU | 0.1622 | 0.1653 | 0.1622 | 0.1632 | |
| LeakyReLU 0.01 | 0.1621 | 0.1657 | 0.1610 | 0.1629 | -0.0003 |
| LeakyReLU 0.1 | 0.1581 | 0.1628 | 0.1624 | 0.1611 | -0.0021 (2 of 3 better) |
| SiLU | 0.1621 | 0.1603 | 0.1615 | 0.1613 | -0.0019 (3 of 3 better) |

Reading: LeakyReLU 0.1 and SiLU keep nearly every neuron alive, and their
validation loss is about 1.3% lower, which is the size of the seed spread
(0.003) with three seeds: a lean, not a result. Validation MSE against real
outcomes is noisy and isn't the project's ruler; play strength is
(the gauntlet protocol). These are round-0 nets, far weaker than the product.

## What it would take to test in play

Rust search runs ReLU only (`py/src/net.rs`); `stsnet.rust_evaluator`
refuses another activation. LeakyReLU costs nothing extra there; SiLU needs
an exp per unit. A play test needs LeakyReLU in Rust, then a full
curriculum run per arm on today's rules (the product's own data no longer
replays) and the gauntlet protocol against a ReLU control trained the same
way.

Files: `results/neurons/act/` (each arm's snapshots, `dead.json`,
`run.sh`); delete the folder to clean up.
