# Mechanic count curve (lane mechanic-count-curve)

Status: closed (2026-11-12, lane capped; decisions "Lane mechanic-count-curve closed"; read after close: go, 6-arm cut 0.88, measurement/mechanic-count@six-arm).

Charter: fact `lane/mechanic-count-curve`. Confirmed on the owner's behalf
(2026-11-11).

## How it moves goal 1

Goal 1 asks how cheaply a net learns to play content it has never seen. The
generated-pack recipe trains on 18 generated mechanics and cuts the cost of
6 unseen pairings by 0.76 (fact `measurement/genpack-transfer@three-seeds`).
This lane asks whether the count matters or only the atoms: a pack of 6
mechanics that holds every trigger and effect the 6 held-out pairs use. If
the 6-arm cuts as much (0.6 or more at 2 se), a generator only has to cover
the atoms, and the wider grid can be built for coverage, not volume. If it
cuts under 0.4, the count carries the transfer, and a 12-arm reads the
curve's middle. We know from one seed-1 learn and one read on the 24 rows,
the read that gave the 18-arm 0.81 on seed 1.

## Step 1 (code)

- `scripts/gen_enemy_pack.py --six` writes `content/packs/gen-enemies-six.json`:
  the writer's own output over 6 mechanics (`SIX`): AttackLoss-PlainDamage,
  AttackLoss-Frail, OppCard-Weak, OppCard-Frail, TurnEnd-Damage,
  TurnEnd-PlainDamage. Why these 6: the charter's set. Each trigger of the
  held-out pairs (AttackLoss, OppCard, TurnEnd) comes twice, and each of the
  held-out effects (Damage, PlainDamage, Weak, Frail) at least once, with no
  held-out pair in it. The encounters and groups are the 18-pack's (the same
  generated share of hallways and elites); stacks vary per monster by the
  same hash. 60 monsters.
- `configs/genpack6-40k-s1.json`: `configs/genpack40k-s1.json` with the six
  pack in place of `gen-enemies-train.json`, name `genpack6-40k-s1`.
- `mutate_monsters.py play --net` takes a glob in the path (one match, else
  exit), so the read is queued before the learn names its run folder.
- `genpack_cut.py --trained M1,..`: the training rows split into the
  mechanics the pack trained on and the 12 in neither split, and the stop
  rule's line (go, fail, between). On the 18-arm's seed-1 files it gives the
  held-out cut 0.81 (se 0.02), the number on record.
- Tests: `scripts/tests/test_gen_enemy_pack.py` (the six pack is the
  writer's output, covers the held-out atoms, has the 18-pack's
  encounters; loads and plays at random in a fresh process; the glob
  lookup).

## Step 2 (runs)

- learn: `scripts/learn.py --config configs/genpack6-40k-s1.json` (6
  threads, about 2.5 h).
- read: `mutate_monsters.py play` with the 18-arm's 0809 settings (1000
  starts, elite, 8 seeds, heuristic and one, the 24 GE rows) on
  `runs/*-genpack6-40k-s1-r1-*/model.pt@tsl1`, out
  `results/mutate/gen-gp6-1-tsl1-all24.json` (3 threads, about 70 min).
- cut: `genpack_cut.py --trained <SIX> --pair
  results/mutate/gen-pns1-tsl1-all24.json results/mutate/gen-gp6-1-tsl1-all24.json`.

Checkpoint `step2-six-arm`: go if the held-out pooled cut is 0.6 or more at
2 se; fail under 0.4 (then a 12-arm on seed 1); between, a seed-101 learn of
the 6-arm decides by its pooled cut. About 18 of the 27 CPU-hours.

## 18-arm on the same split (seed 1, for the read beside it)

Held-out cut 0.81 (0.02). Trained 6 (the SIX rows in the 18-arm) base +1.49
genpack -1.16; neither 12 base +2.24 genpack -1.26 (HP beyond parent, 675
starts).
