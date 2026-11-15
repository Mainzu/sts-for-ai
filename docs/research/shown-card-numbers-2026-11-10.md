# Shown card numbers and exhaust hidden: step 2 read (2026-11-10)

Lane `shown-card-numbers` (charter `lane/shown-card-numbers`, spec
`docs/specs/shown-card-numbers.md`). Step 1 built two encoder flags, `@sn1`
(card damage and block as the game shows them: + Strength x hits, x0.75
under Weak; + Dexterity, x0.75 under Frail) and `@xh1` (exhaust pile counts
written as 0), with exact parity against the zero-shot scripts. Step 2 plays
today's 10-29 net with them, no retrain.

## Cell gauntlet, one turn deep (jobs 0757-0759)

The 10-29 net @hpb0.01 on the one-turn cell gauntlet, sequences 0-499,
paired against `results/gauntlet/net1029-hpb0.01.json`, fixed n 500
(`scripts/analysis/shown_strata.py`). The stratum is decks holding a
Strength source or a multi-hit attack.

| arm | pairs | end HP (se) | clears (se) | arm clears |
|---|---|---|---|---|
| `@sn1` all | 500 | -0.24 (0.21) | +0.002 (0.006) | 0.636 |
| `@sn1` stratum | 436 | -0.23 (0.23) | +0.002 (0.007) | 0.674 |
| `@sn1` rest | 64 | -0.31 (0.30) | +0.000 | 0.375 |
| `@xh1` all | 500 | -0.24 (0.22) | +0.004 (0.007) | 0.638 |
| `@xh1` stratum | 436 | -0.28 (0.25) | +0.005 (0.009) | 0.677 |
| `@xh1` rest | 64 | +0.00 (0.15) | +0.000 | 0.375 |
| both all | 500 | -0.34 (0.26) | +0.004 (0.008) | 0.638 |
| both stratum | 436 | -0.34 (0.29) | +0.005 (0.009) | 0.677 |
| both rest | 64 | -0.31 (0.33) | +0.000 | 0.375 |

Every arm is level within 1.5 HP (all within 0.35 HP, se about 0.25): the
charter's **fail** branch. The protocol fails each arm at its first look.

Why, from the raw files:
- The flags were live: 154 (`@sn1`), 163 (`@xh1`) and 258 (both) of 500
  sequences end differently from the control; per fight, `@sn1` changes 63
  of 3695 hallway, 53 of 887 elite and 45 of 364 boss fights. So the net
  does read the new numbers; it does not play better with them.
- Changes by fight type (HP change against the control, mean over all
  paired fights): `@sn1` hallway +0.02, elite 0.00, boss -0.38; `@xh1`
  hallway -0.01, elite -0.19, boss -0.07; both hallway 0.00, elite -0.16,
  boss -0.54. The small drift is downward on bosses, where Strength stacks
  most. A net trained on the per-card cache numbers prices a card from its
  base damage; feeding it the shown value moves its inputs off the training
  distribution about as often as it corrects a mispricing. The zero-shot
  correlation gain at the pair level (0.218 on the attack pairs with
  Strength or Weak) did not carry into play.
- The stratum split carries little: 436 of the 500 cell decks hold a
  Strength source or a multi-hit attack (Twin Strike and Pummel are common),
  so "stratum" is nearly "all".
- The jobs ran in 2-4 minutes against 20-minute estimates (the machine was
  free); results are complete (500 sequences each) and agree with the
  control's clears to within 0.005, so the speed is not a short run.

## Generated bench, Weak and Frail turn rows (jobs 0760-0761)

`mutate_monsters.py compare results/mutate/gen-wf-tsl1.json
results/mutate/gen-wf-sn1-tsl1.json`: 675 elite starts x 8 seeds, the 10-29
net one turn deep @tsl1 with and without `@sn1` (the job command passes
`@tsl1`, not `@hpb0.01@tsl1` as its note says; both arms share the base, so
the comparison holds). Win rate:

| mechanic | base cost (se) | shown gain (se) | cut | parent change |
|---|---|---|---|---|
| TurnStart-Weak | -0.011 (0.003) | +0.006 (0.002) | 0.54 | 0.000 |
| TurnEnd-Weak | -0.013 (0.003) | +0.005 (0.001) | 0.40 | 0.000 |
| TurnStart-Frail | -0.002 (0.002) | +0.001 (0.001) | 0.50 | 0.000 |
| TurnEnd-Frail | -0.002 (0.002) | +0.001 (0.000) | 0.30 | 0.000 |

Shown numbers do recover part of the recurring-Weak cost (+0.5 points of
win rate, 3-5 se) with the parents untouched, but neither Weak row is
halved at 2 se (cuts 0.54 and 0.40 as point values, with wide intervals),
and the Frail rows' costs are within noise. By the note's rule
`recurring-debuff-leaf` (backlog 24) opens whole, not narrowed: Weak stays
in it.

## What it changes

- No arm goes to step 3; `pack-net-scratch` seeds 2-3 learn without the
  flags (its charter's "with 44's flags if 44 goes" clause does not fire).
- The flags stay in the engine, off by default, as an input a net trained
  with them could use: the zero-shot read only says today's net does not
  gain. Training a net with `@sn1` on is a different idea (a new input is
  the training rule's second reason) and would need its own lane.
- The Weak rows' partial cut is the one positive sign: the net misprices
  Weak-reduced attacks, and showing the number helps somewhat even zero-shot.
