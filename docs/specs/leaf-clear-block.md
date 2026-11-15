# Leaf clear block (lane leaf-blind-numbers, step 3)

Status: closed (2026-11-07, built and in use; @lcb1 in 17ca5006; in the product since 2026-11-13: decisions "Product read 0986: `@tsl1@lcb1` two turns deep is level...").

Charter: fact `lane/leaf-blind-numbers`. Read that opens it:
`docs/research/leaf-blind-numbers-2026-11-07.md#Read (2026-11-07, job 0434)`,
fact `measurement/leaf-numbers@probe`.

## How it moves the goals, and how we'll know

Goal 1: the net prices leftover player block at end-of-turn leaves with the
wrong sign (about -0.3 HP a point on most decks, +1 HP on the Impervious
deck), a number the next StartTurn sets to 0 anyway. Clearing it at the leaf
is exact (the engine has no block-keeping effect), needs no training and
holds for any new content, so content whose turns end with surplus block
stops paying for the net's misreading. Goal 2: the option changes every
deck's leaves, so a retention gain reaches the one-turn headline. We'll know
from the pack-cards read of Disarm, Impervious and Intimidate (each card's
lead with the option against without it, se over cells) and the one-turn
cell gauntlet `--against` the one-turn cell control (paired HP, the
protocol). Expected: Impervious's lead moves toward 0; Disarm and
Intimidate stay (their numbers are Strength and Weak), so the lane's go
(two of three cards within 2 se of 0) is unlikely, about one in five; the
cell gauntlet decides whether the option is worth keeping on its own.

## Outcome and non-goals

A search option, off by default, that scores every end-of-turn leaf of a
one-turn search with the player's block set to 0, read on the three cards
and on the cell gauntlet. Non-goals: energy (also reset by StartTurn; not
priced by the probe), Strength and Weak (no exact fix), two-turn search
(product promotion would need its own read), training.

## Behaviour

- `SearchConfig::leaf_clear_block` (default false). In `child`, at an
  EndTurn that becomes a leaf (the plain leaf and the `turn_start_leaf`
  leaf; not the draw leaf, whose StartTurn already cleared block, and not
  the sample_k look-ahead), when the state is not over: player block := 0,
  then the turn-start hooks if `turn_start_leaf` (StartTurn clears block
  before those hooks run, so hook block survives).
- Player string `@lcb1` (bench.py `player_settings`, at most once, only the
  value 1), passed as `leaf_clear_block` through `stsnet.rust_evaluator`
  into the `NetEvaluator` config (`Prices.leaf_clear_block`, like
  `turn_start_leaf`); ensemble members must share it. Gauntlet files record
  it in `price` (the part after `@`), so a read `--against` the control
  declares `--vary price`.
- Off: search, golden and every existing player string unchanged.

## Fits with

- Existing search tests and the golden (`engine/tests/data/golden.txt`)
  stay identical (default off).
- `player_settings` keeps refusing a repeated or bad setting
  (`scripts/tests/test_bench.py` or the nearest settings test; new case for
  `@lcb1`, `@lcb2` refused).

## Scope

- `engine/src/search.rs` (config field, `child`), `py/src/lib.rs` (Prices,
  config, ensemble check, doc), `scripts/bench.py`, `scripts/stsnet.py`,
  their tests, this spec and the results doc. Off limits: `engine/src/state.rs`
  rules, features, nets, gauntlet.py, pack_cards_read.py.

## Verification

- Rust test `leaf_clear_block_scores_without_block`: a state at an EndTurn
  leaf with leftover block; a search with the option gives the leaf the
  score of the same state with block 0; without the option the score keeps
  the block. 
- Python: `player_settings("x.pt@hpb0.01@lcb1")` gives
  `leaf_clear_block: 1.0`; `@lcb2` raises.
- End to end: `pack_cards_read.py play --cards Impervious --limit 2` with
  `@lcb1` runs.

## Runs (queued after the build)

1. Pack read, out-dir `results/pack_cards/act1-lcb`, `--cards Disarm
   Impervious Intimidate`, players heuristic, `<net>@hpb0.01@lcb1`,
   `<net>@hpb0.01@lcb1@tsl1`, then `table --net <net>@hpb0.01@lcb1`
   (about 0.3 cpu-h). Compare each card's lead with
   `results/pack_cards/act1/table.json` (same fights, deterministic).
2. Cell gauntlet: `gauntlet.py play <net>@hpb0.01@lcb1 --sequences 500
   --threads 3 --against results/gauntlet/net1029-hpb0.01.json --vary price
   --min-n 500` (about 0.15 cpu-h).
3. Only if 2 does not fail the protocol: the one-turn headline `--start
   starter --rewards sim --sim-boss --against
   results/gauntlet/net1029-hpb0.01-starter-simboss.json --vary price`
   (queued after reading 1 and 2).

## Build steps

1. Engine field + `child` + Rust test; lib.rs plumbing; bench.py and
   stsnet.py; Python test. Check: cargo test for search, the Python test
   against a wheel built into a temporary pyroot, golden identical.
2. Queue runs 1 and 2.
