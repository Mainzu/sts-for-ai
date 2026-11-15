# Mutated cards (yardstick-cards step 3)

Status: closed (2026-11-07, built and in use; 5909a1af; scripts/analysis/mutate_cards.py, yardstick-cards step 3).

## How it moves goal 1, and how we'll know

Goal 1's number is what new content costs the net zero-shot and how few
games repair it (decision/goal1-yardstick: boon + bane pairs on official
parents, the cost measured per modifier). The monsters rung has its bench
(`mutate_monsters.py`); the cards rung has none, so the cost of a changed
card has only been read on one card (Demon Form, held out). This bench
patches official cards into boon + bane variants and reads, per modifier,
the difficulty change (heuristic) and the net's drop beyond it (novelty
cost), one turn deep. We'll know it works when the first table is recorded
with se <= 0.02 per modifier (the lane's stop rule) and the plain control
reads level, as predicted.

## Outcome

`scripts/analysis/mutate_cards.py`: the gauntlet's elite and boss fights,
replayed with one official card of the deck swapped for a pack variant,
played by the heuristic and the product net one turn deep (plain leaf and
`@tsl1`), on common seeds; `read` gives per modifier the win and HP-lost
change from its parent and the novelty cost, by fight type.

Non-goals: two-turn play; the adapted column (bursts on a modifier: the
next step, only for modifiers whose cost passes 2 se); new engine atoms;
changing `mutate_monsters.py`.

## Behavior

- **Variants are pack cards.** Every modified card, and an exact copy of
  each parent (`<parent>~copy`: the official entry's id, cost, type and
  effects), is a card of one generated pack loaded with `sts.load_content`;
  decks name it `gen:<id>`. A modifier swaps every copy of its parent
  (the base card; the upgraded `+` card stays) in the deck.
- **The parent of a modifier is its card's copy, not the official card.**
  A pack copy plays almost but not exactly like the official card (measured
  2026-11-07 on 16 Demon Form fights x 4 seeds: 54 of 64 heuristic and 57 of
  64 one-turn outcomes identical, mean end HP within 0.13), so reading the
  modifier against the copy leaves only the numbers changed. Each row also
  keeps the official card's games, and `read` prints copy minus official as
  a check line.
- **Combats with a pack card have no state encoding**, so each game is built
  from its spec with `sts.Combat(deck, encounter, seed=s, hp, character)`
  per seed and advanced to its first decision; parent, copy and variants
  share the seeds (the seed fixes the shuffle and the play-out).
- **Starts:** `bias_audit.fights` of the product file (1471 elite and boss
  fights over sequences 0-499; rule c: cell decks at the product's entry HP);
  per parent card, the first `--starts` (default 200) fights whose deck holds
  it. Seeds per start from `np.random.default_rng([20261107, i, floor])`,
  `--seeds` (default 8).
- **Players:** `heuristic`, `one` (the 10-29 net `@hpb0.01`), `tsl`
  (`@hpb0.01@tsl1`, measurement/turn-start-leaf@cells). `--net` swaps the
  net for an adapted burst later.
- **Output:** `results/mutate/cards-<name>.json`, rewritten after each start
  (resumable: a rerun skips starts and players already played). Rows keyed by
  (start, parent card): `{i, floor, encounter, group, hp, card, official:
  {player: [(won, hp_end)]}, parent: {...}, mods: {mod: {player: [...]}}}`.
- **Read:** per modifier and player, win change and HP-lost change from the
  parent (paired by start, mean and se); novelty `one - heuristic` and
  `tsl - heuristic` contrasts in wins and in HP lost; all fights, elites,
  bosses. A pooled line: the mean novelty cost over the power-parent pairs,
  se over pairs (the charter: the pair is the sample unit), beside the
  plain control.
- **Modifiers (first table), fixed before it runs:**

  | modifier | parent | change | pays |
  |---|---|---|---|
  | `bash-c1-d5` (plain control) | Bash | cost 2 -> 1, damage 8 -> 5 | inside the turn |
  | `inflame-turn1` | Inflame | +2 Strength now -> +1 Strength per turn (DemonForm 1) | later turns |
  | `df-c2-s1` | Demon Form | cost 3 -> 2, Strength per turn 2 -> 1 | later turns |
  | `metal-c0-a2` | Metallicize | cost 1 -> 0, block per turn 3 -> 2 | later turns |
  | `metal-c2-a5` | Metallicize | cost 1 -> 2, block per turn 3 -> 5 | later turns |
  | `combust-d8-l2` | Combust | damage per turn 5 -> 8, HP lost per turn 1 -> 2 | later turns |
  | `combust-c0-d3` | Combust | cost 1 -> 0, damage per turn 5 -> 3 | later turns |

- **Prediction (trade-off rule), written before the run:** the plain control
  costs the net nothing beyond the heuristic (both parts land inside the
  turn). On the turn-start parents (`inflame-turn1`, `df-c2-s1`) the plain
  one-turn leaf never sees the Strength a turn later, so `one` should lose
  beyond the heuristic, and `tsl` should cut that cost. On the turn-end
  parents (Metallicize, Combust) the leaf is scored after the player's turn
  end, so the block and damage show inside it: costs near zero for both
  nets. If the turn-start pairs read level, the cards rung's zero-shot cost
  is Demon Form's own and not its mechanic; if the turn-end pairs cost, the
  leaf's turn end is not where the cost lives.
- **Failure cases:** a modifier whose parent card isn't in `content/cards.json`
  or a pack that doesn't load is an error before any play; a start whose
  deck lacks the parent isn't selected.

## Fits with

- `mutate_monsters.py`: unchanged; the new script imports its player table
  (`PLAYERS`, `PRODUCT`, `NET`) and `bias_audit`'s `fights` / `mean_se`.
  Pinned by `scripts/tests/test_mutate_monsters.py` (unchanged, still passes).
- Official content files: read only.
- `bench.load_evaluator`: player strings as today (`@tsl1` exists).

## When in doubt

Prefer the monsters bench's read conventions (paired by start, a loss costs
the entry HP) over new statistics.

## Scope

May change: `scripts/analysis/mutate_cards.py` (new), its test
`scripts/tests/test_mutate_cards.py` (new), `docs/research/learned-play-results.md`,
this spec, `docs/decisions.md`, kb facts of this lane. Off limits: the
engine, `py/`, `mutate_monsters.py`, `bench.py`, content files.

## Decisions taken (provisional, docs/decisions.md)

- Variants as pack cards read against a pack copy of the parent (not state
  patches: a card's numbers aren't in the combat state, and the per-copy
  `Overrides` hold only damage).
- Players `heuristic`, `one`, `tsl`; one turn deep only.

## Outside assumptions

None outside the project.

## Verification

Tests first (`scripts/tests/test_mutate_cards.py`):
- `test_pack_loads`: the generated pack loads; every modifier's card differs
  from its copy only in the fields the table names; each copy equals its
  official entry's id-less (cost, type, effects).
- `test_swap`: `swapped(deck, "Bash", "gen:x")` swaps every `Bash` and keeps
  `Bash+`.
- `test_play_tiny`: `play` on 2 starts per card, 1 seed, players heuristic,
  writes rows with official, parent and every modifier; a rerun adds nothing.
- `test_read`: on a hand-made file, the novelty contrast and the pooled
  over-pairs line come out as computed by hand.
End to end: the queued job writes the table (the long run).

## Don't guard

Upgraded parents, Silent decks, two-turn play.

## Build steps

1. Script and tests (in-session): check `test_mutate_cards.py` passes and
   `test_mutate_monsters.py` still passes.
2. Queue the run: `play --starts 200 --seeds 16 --players heuristic,one,tsl
   --threads 3 --out results/mutate/cards-a.json`, then `read` into
   `results/mutate/cards-a.txt`, as one job pair; its note says how to read
   it. A 6-start, 4-seed smoke run of all seven modifiers and three players
   took 8 s at 3 threads (1224 games), so the full run is about 30-60 min;
   16 seeds instead of the charter's 8 cost little and make the se <= 0.02
   stop more likely (start-to-start spread still dominates).
