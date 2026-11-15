# Act 1 cards zero-shot read (lane act1-cards-zero-shot)

Status: closed (2026-11-07, read in: decisions "Lane act1-cards-zero-shot closed (2026-11-07)"; docs/research/act1-cards-zero-shot-2026-11-07.md; kb measurement/act1-cards@zero-shot).

## How it moves goal 1, and how we'll know

Goal 1 asks for first-class custom content: a card written in a file should
play well with no training. The 22 Act 1 Ironclad cards in
`content/packs/act1-ironclad.json` are the first real content loaded that
way. This read measures, card by card, what each costs the product's net
one turn deep against the heuristic (which plays every card in the engine
and needs no training), on both one-turn leaves, with each card's predicted
cost class written down before any fight. We'll know from one table: for
each card, the net-minus-heuristic lead with the card minus the same lead on
the same fight without it, in wins and end HP, with an se over cells. A card
that costs is a new cost class (open question 2 in the backlog); level cards
give goal 1 a standing count of new cards played at no cost.

## Outcome

`scripts/analysis/pack_cards_read.py` with three commands:

- `play --players <p> ... --out-dir results/pack_cards/act1`: plays the
  fights below with each player and saves per-fight wins and end HP (and,
  for the heuristic, how often it plays the card when it holds it);
- `table --out-dir results/pack_cards/act1`: per card and leaf the paired
  read, by fight type, written to `results/pack_cards/act1/table.json` and
  printed as a markdown table with the prediction beside each card.

Non-goals: two-turn reads (a later step, only on cards that cost at 2 se
under `@tsl1`, as the charter says); hallway fights; upgraded cards; any
engine change; training.

## Behavior

- **Fights.** tight2's held-out half, elite and boss fights (167 cells: 126
  elite, 41 boss), the first `--seeds` fights of each cell (default 3). Set
  `without` is the cell's deck as it is. For each base card of the pack (ids
  without `+`, in the pack's order; `--cards` limits the list), set `<card>`
  is the same fight with three Strikes, then Defends, turned into
  `gen:<card>` (every one of the 167 decks holds at least three). Fights
  per set: 501; 23 sets.
- **Players.** `heuristic`; any player string `bench.load_evaluator`
  takes (`<run>/model.pt@hpb0.01`, `...@hpb0.01@tsl1`). A player whose
  string holds `@tsl1` plays only the fights whose deck holds a power with a
  turn-start hook (`Demon Form`, `Brutality`, `gen:Berserk`; `+` ignored);
  its other entries stay `null` and `table` reads the plain player's result
  there (the turn-start leaf leaves such decks unchanged: 46 of 46 fights
  equal, checked 2026-11-07; the test pins it on a few fights).
- **Files.** `results/pack_cards/act1/<name>.json`, `name` the player with
  `@` as `-` and the run folder's name for a model path; holds the pack's
  content hash, the fight keys (cell, set, seed) and `won`, `hp_end`; the
  heuristic's file adds `in_hand` and `played` (turns the set's card was in
  hand at any decision, turns it was played). An existing file is skipped.
- **Table.** For each card c and leaf L (plain; tsl1): per cell,
  d = mean over seeds of (net - heuristic) on set c minus the same on
  `without`, for `won` and `hp_end`; mean and se (ddof 1) over cells; all
  fights, elite, boss. Costs: `won` mean below -2 se. Beside it: the
  heuristic's play rate (played / in-hand turns) and the prediction class.
  The tsl1 column is printed where it differs from plain (Berserk and cards
  whose cells hold another turn-start power: in practice every card, since
  75 of the 167 cells hold Demon Form or Brutality; the table prints both).
- **Predictions** (from the charter, fixed in the script before any fight):
  in-turn, level: Disarm, Ghostly Armor, Intimidate, Searing Blow, Seeing
  Red, Shockwave, Bludgeon, Feed, Impervious, Offering (ten; the charter
  says eleven, but its five classes cover 22 cards only with ten here);
  turn-start: Berserk, costs on plain, open under tsl1; status-later: Power
  Through, Reckless Charge, Immolate, open; unreadable trigger: Double Tap,
  Flame Barrier, open; new atoms (C1): True Grit, Burning Pact, Second
  Wind, Sever Soul, Fiend Fire, Exhume, level by the in-turn rule.

**Fits with:** `gen_powers_read.py` and its bench files stay untouched
(test_gen_powers_read.py); `bench.run_specs` and `selfplay.load_content`
are called as they are; the results folder is new.

**When in doubt:** prefer the gen-powers bench's conventions (cell-level
se, paired by cell) over new ones.

**Scope:** a new script in `scripts/analysis/`, its test in
`scripts/tests/`, this spec, a results doc in `docs/research/`. Off limits:
the engine, `bench.py`, `selfplay.py`, the pack file, other scripts' outputs.

**Outside assumptions:** none beyond the repo (the pack's values were
checked by the act1-content lane).

## Verification

- `test_fights`: on a small fake held-out list, the sets are `without` plus
  one per card, Strikes are swapped before Defends, three copies, seeds are
  the first k of each cell, only elite and boss.
- `test_play_stats`: on a recorded state/action list, in-hand and played
  turn counts.
- `test_table`: on synthetic per-fight results the paired mean and se equal
  a hand computation, and a tsl1 `null` reads the plain value.
- `test_tsl_same_on_plain_decks` (plays): 8 fights of decks without a
  turn-start power give the same results under `@hpb0.01` and
  `@hpb0.01@tsl1`.
- End to end: `play --cards Berserk --seeds 1 --limit 5` then `table`
  prints a row.

## Build steps

1. The script and its tests (above); check: the tests pass and the end to
   end smoke prints a row.
2. Queue the three players (heuristic, plain, tsl1; about 15, 15 and 7 min
   at 3 threads, about 1.9 cpu-h together) and the table after them (long
   run); the results doc states the predictions before the jobs run.
3. Read the table into the results doc; then the two-turn step for cards
   that cost at 2 se under tsl1, if any (a later spec within the cap).
