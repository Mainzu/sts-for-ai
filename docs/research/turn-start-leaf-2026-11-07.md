# Turn-start leaf: results (lane turn-start-leaf)

Spec: `docs/specs/turn-start-leaf.md`. Charter: `kb get lane/turn-start-leaf`.

## Build

- Engine: `CombatState::turn_start_leaf` and `SearchConfig::turn_start_leaf`
  (off by default). All engine test files pass except `solve`, which wasn't
  rerun after the rebase (it passed before the rebase); golden identical.
- Python: `@tsl1` player setting; `test_turn_start_leaf`, `test_draw_leaf`,
  `test_contract` and `test_bench` pass on the branch's wheel (53 tests).
- Spec review: no must-fix. Optional notes:
  `turn_start_leaf_off_is_unchanged` can't fail (the default is already off;
  golden is the real check); there is no test of a leaf at `MonsterRolls` or
  of the ensemble refusal; `@dl<k>` together with `@tsl1` quietly ignores
  the flag (draw-leaf leaves come first).

## The read

Queued from the branch, pinned to its commit:
- the 10-29 net `@hpb0.01@tsl1` on both cell books, one turn deep
  (`results/gauntlet/net1029-hpb0.01-tsl1{,-b500}.json`; same command as
  0192, the plain-leaf control);
- the generated-power bench one turn deep (`gen_powers_read.py play`,
  `model.pt@tsl1`, against the 10-29 net's plain file in
  `results/gen_powers/arms/gen_powers12c3/`).

Read: `python scripts/analysis/cards_by_half.py --tsl`. Sanity check: decks
without a turn-start power should give mostly identical sequences (the
"identical sequences" column). If they don't, a change since the control
files were made (2026-11-05 and earlier) moved play, and the controls must be
replayed before the read counts.

## Result: go (jobs 0324-0326, read 2026-11-07)

`cards_by_half.py --tsl`, the 10-29 net `@hpb0.01@tsl1` minus the plain
leaf, both cell books one turn deep (paired by sequence, se over sequences):

| stratum | n | end-HP | clears | identical sequences |
|---|---|---|---|---|
| train | 500 | -0.02 (0.15) | +0.000 (0.005) | 469 |
| held-out | 326 | +0.04 (0.08) | +0.000 (0.000) | 313 |
| held-out DF | 174 | +7.54 (1.10) | +0.149 (0.028) | 73 |

Charter: **go** (Demon Form decks +7.54 HP at 6.9 se, above the 3 HP bar;
train and the other held-out decks within 1 HP).

Why, and checks:
- Sanity check holds: every train or held-out sequence that changed (31 and
  13) has Brutality or Brutality+ in its deck, the other power with an
  `OwnerTurnStart` hook; none without it changed. The controls (0192 and its
  twin, 2026-11-05) still replay, so the read counts. Brutality decks net
  -0.32 HP (train) and +1.08 HP (held-out) on those few sequences: the copy
  takes Brutality's HP loss into the leaf and leaves out its draw, a small
  pessimistic bias that costs nothing measurable.
- Generated-power bench, elite + boss, flag minus plain wins (se over
  cells): `OwnerTurnStart` powers +0.243 (0.054) over 12 cells, with an
  `OwnerLostHp` second trigger +0.194 (0.073); the swapped original Demon
  Form +0.170 (0.030) over 44 cells; `OwnerTurnEnd` -0.011 (0.011), the
  other triggers and Metallicize within 0.03. The gain is where the hook
  is, on generated powers as on the hand-made card: the repair is zero-shot,
  not a Demon Form special case.
- Size against the other repairs: burst8 s1, fine-tuned on generated power
  cards, plays Demon Form decks +6.13 (1.94) HP better (cause/unseen-cards-half-edge);
  this flag gets +7.54 (1.10) with no games and no training. Two turns deep
  the search already sees the first tick, so the flag's value for the
  product (two-turn) is not measured here.
- Cost: 0324/0325 took 4.6 and 4.1 min at 3 threads against 2.5-3.0 min for
  the plain controls (0192-0197), but with other jobs loading the machine;
  the leaf copy only runs on states whose player holds an `OwnerTurnStart`
  power, so its price outside those decks should be near zero. Not timed
  cleanly.

CPU: 0.71 thread-hours (0324 0.23, 0325 0.20, 0326 0.28) against the 1 cpu-h cap.

What it changes: one turn deep, the leaf horizon was the Demon Form half of
the unseen-cards edge; a search rule fixes it. Open for the navigator: the
flag on the two-turn product (does it still gain when the first tick is
inside the search for the first turn but not the second?), the flag as the
default for one-turn screens, and whether other horizon effects (turn-end
powers on the second turn, Poison) want the same treatment.
