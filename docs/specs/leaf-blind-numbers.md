# Leaf numbers probe (lane leaf-blind-numbers, steps 1 and 2)

Status: closed (2026-11-07, probe read: leftover block mispriced; decisions "Lane leaf-blind-numbers closed (2026-11-07)", fact measurement/leaf-numbers@probe).

Charter: fact `lane/leaf-blind-numbers`. Opening entry: `docs/decisions.md`
"After act1-cards-zero-shot: ...".

## How it moves the goals, and how we'll know

Goal 1: three Act 1 pack cards (Disarm, Impervious, Intimidate) cost the
10-29 net one turn deep (`measurement/act1-cards@zero-shot`), and their
value sits in a number left in the leaf state, not in damage or cards
played. If the net misprices such a number at the leaf and the search can
fix it exactly (step 3, a later spec), content of that kind stops costing
without training; if the net prices them right, the cost is in the play and
the leaf is cleared as a cause. We'll know from step 2's table: per
perturbation, the net's value change against its true worth, se over
fights. Goal 2 only if step 3 changes the product's leaves.

## Outcome and non-goals

One CPU job (`scripts/analysis/leaf_numbers_probe.py run`) replays the pack
read's fights for `without` and the three cards with the 10-29 net
(`@hpb0.01`, plain leaf, as the pack read played these decks), takes the
leaf of every played EndTurn, counts its forms (step 1) and prices
perturbations of its numbers with the net and the heuristic (step 2).
Non-goals: any change to search or play (step 3 is its own spec, only on a
go), training, two-turn reads.

## Step 1: code read (done, no CPU)

- Plain leaf (`engine/src/search.rs` `child`, no draw_k, no tsl): the state
  after `apply_action(EndTurn)`, which runs the monsters' turn and the
  RoundEnd countdowns (Weak, Vulnerable tick down), then stops at the first
  chance event: `MonsterRolls` when a living monster's next move is random
  (`chance.rs` `request_monster_move`); otherwise `StartTurn` runs (block
  0, energy reset, turn + 1, `engine/src/state.rs` `Stage::StartTurn`) and
  the leaf is the draw (`TurnStarted`, draw pending). With no chance event
  at all the leaf is the next decision or the end.
- `@tsl1` (`state.rs` `turn_start_leaf`) runs only the player's
  `OwnerTurnStart` hooks on a copy and only for a deck holding such a power;
  it does not run `StartTurn`, so a `MonsterRolls` leaf keeps its leftover
  block and energy under `@tsl1` too. The pack read played `@tsl1` only on
  decks with a turn-start power, so for the three cards plain is the read.
- So a `monster_rolls` leaf holds leftover player block and energy that are
  worth nothing (no block-keeping power in these decks), and monster Weak
  and Vulnerable already counted down once; a `draw` leaf holds block 0.

## Behaviour

- `run`: fights as `pack_cards_read.fights` (tight2 held-out elite and boss
  cells, 3 seeds, 3 copies), sets `without`, Disarm, Impervious,
  Intimidate; played with `bench.run_specs(..., record=True)` one set at a
  time. For each recorded state whose action is EndTurn: `leaf =
  state.after_end_turn()`. Per leaf: form, block, energy, monster numbers,
  net score (`NetEvaluator.score`, what search sees) and heuristic estimate.
- Perturbations, each as net change and heuristic change in HP (score x
  100), with the leaf's true worth:
  - `block0`: a `monster_rolls` leaf with its leftover block set to 0 (the
    form the draw leaf would give): true worth 0; reported as the price of
    the leftover block (value with minus value without).
  - `block+10`, `+20`, `+30` at `monster_rolls` leaves: true worth 0.
  - `str-2` (draw and decision leaves; at `monster_rolls` the rolling
    monster still shows its last move): the first living monster's Strength -2: true worth estimated
    as the change in that monster's intent damage times the heuristic's
    rounds left (an upper-side estimate: block can absorb hits).
  - `weak+1`: the first living monster's Weak +1: true worth the change in
    its intent damage (one monster turn).
  - Also per set: the share of leaves with a monster at Strength < 0 and
    with a monster's Weak > 0.
- se over fights (each fight's mean over its leaves is one unit).
- Output `results/leaf_numbers/probe.json` and a markdown table on stdout.
- Mispriced (the stop rule's test): a perturbation whose net change has the
  wrong sign by 2 se, or for `block*` is more than 2 HP from 0 by 2 se, or
  for `str-2`/`weak+1` lies outside half to twice its true worth by 2 se.

## Predictions (written before the run)

- Forms: Act 1 elites and bosses mostly roll fixed moves, so `draw` leaves
  outnumber `monster_rolls` ones; `monster_rolls` 20-50% of leaves.
- Impervious leaves at `monster_rolls` hold far more block than
  `without` (mean over 10 against under 5).
- `block0` price: the net pays for leftover block, about +2 HP for 20 block
  (even odds that it is mispriced by the rule above).
- `str-2`: net change positive but under half of the true-worth estimate
  (a Strength below zero never occurs in training): mispriced, likely.
- `weak+1`: within the factor of two (Weak is in training): priced right.

## Fits with

- `Combat` gains read-only getters and copy-returning edit methods only;
  nothing existing changes (engine untouched, golden identical). Tests:
  `scripts/tests/test_leaf_numbers_probe.py` (new).
- `pack_cards_read.fights` reused as is.

When in doubt: prefer a smaller, exact read over a wider one.

## Scope

- `py/src/lib.rs`: new `Combat` methods `after_end_turn`, `leaf_form`,
  `player_block_energy`, `monster_numbers`, `with_player_block`,
  `with_monster_power`, `heuristic_parts`.
- `scripts/analysis/leaf_numbers_probe.py`, its test, this spec, results doc.
- Off limits: `engine/`, search, features, nets, every other script.

## Verification

- `test_after_end_turn_forms`: a starter deck vs a monster with a random
  next move gives a `monster_rolls` leaf holding the block played; after
  `with_player_block(0)` block is 0; a `draw`-form leaf has block 0.
- `test_with_monster_power`: Strength -2 lowers that monster's Strength by
  2 and leaves the original combat unchanged; a dead slot raises.
- `test_cluster_se`: the fight-cluster se on a toy list.
- End to end: `run --limit 2` on two cells writes the json with every set
  and perturbation filled.

## Build steps

1. Binding methods + tests (build the wheel into a temporary target, not
   main's `sts`). Check: tests pass.
2. Probe script + `--limit` end-to-end check. Check: json complete.
3. Queue `run` (about 0.2 cpu-h: 4 sets of the pack read's 23, one player).
   Long run; the read is the next session's.
