# Act-1 gauntlet with HP carried over

Status: closed (2026-11-01, built and in use as the goal-2 yardstick: decisions "Gauntlet spec confirmed", results doc "Act-1 gauntlet: first check and HP-price sweep").

## Why (goal 2)

Every measure so far scores single fights, each from a fixed or drawn start
HP. A run is a chain: HP lost in a hallway is HP missing at the boss. Since
the HP bonus (`@hpb0.01`) the champion matches the heuristic's HP lost per
fight, so the question goal 2 asks next is "how often does an agent clear an
Act", which no per-fight number answers (an agent can win more fights and
still die more often by arriving at the boss low). The gauntlet gives goal 2
a headline number: the Act-1 clear rate, paired by sequence seed, plus where
agents die. We'll know it works when the first check (heuristic vs champion,
200 sequences each, one turn) gives a clear rate between ~10% and ~90%, so
differences between agents can show.

## Outcome

`scripts/gauntlet.py` plays seeded Act-1-like fight sequences with HP carried
from fight to fight and reports clear rate, HP at the boss and deaths by
floor and encounter, paired between two agents.

Non-goals: card rewards, deck changes, potions, gold, shops, events, map
choice, relics other than the engine's Burning Blood, Silent, a promotion
rule (the ladder stays the promotion test).

## Behavior

- **Sequences.** Sequence i (from `--first`, default 0) draws, from
  `rng([GAUNTLET_SEED, i])`: a half (train / held_out, alternating by i), a
  deck (a uniformly drawn tight2 pool cell of that half; the deck only), and
  11 fights in this order: 3 easy hallways, 2 hard hallways, an elite, 2 hard
  hallways, an elite, 1 hard hallway, then a boss. Easy = cultist, jaw_worm,
  two_louse, small_slimes; hard = large_slime, lots_of_slimes, three_louse,
  two_fungi_beasts, exordium_thugs, exordium_wildlife, looter; elites =
  gremlin_nob, lagavulin, three_sentries; boss = slime_boss, hexaghost,
  the_guardian (uniform). No encounter twice in a row; the two elites
  differ. Fight k's seed = `9 * 10**15 + i * 100 + k`.
- **HP.** Start at the character's max HP (80). Each fight starts at the HP
  the last one ended at; the engine already adds Burning Blood's 6 on a win
  (capped at max). Before the boss, a rest site heals 30% of max HP
  (rounded down, capped at max). A loss ends the sequence at that floor.
- **Agents.** A player spec as `ladder.py` takes (`heuristic`, a net path,
  `a.pt@hpb0.01`), one-turn by default; `--two-turn` plays nets under the
  fallback two-turn player (`ladder.play_two_turn`). Floors are played as
  batches: floor k of every still-alive sequence in one `play` call.
- **Output.** `gauntlet.py play <player> --sequences N --threads T` writes
  `results/gauntlet/<tag>.json` (tag from the player and `--two-turn`):
  settings, and per sequence its half, deck cell, and per floor (encounter,
  hp_start, hp_end, won). A rerun with the same tag and settings resumes
  only missing sequences.
- **Read.** `gauntlet.py read A.json B.json` pairs by sequence index: each
  agent's clear rate, the paired clear difference with se, mean floors
  cleared, mean HP at the boss (sequences both reach), deaths by floor and
  by encounter, all by half too.

## Fits with

- `ladder.py` play helpers (`play_bench`, `play_two_turn`, `HEURISTIC`) are
  called, not changed; their tests in `test_ladder.py` stay green.
- `bench.run_specs` groups specs by (hp, character): floors with mixed HP
  must come back in order (new test).
- Seeds: 9e15 + ... is clear of tight2 (2e15), ladder (7e15) and run-HP
  blocks.

## When in doubt

Prefer a plain, fixed Act shape over a faithful map simulation.

## Scope

New `scripts/gauntlet.py`, new `scripts/tests/test_gauntlet.py`, README
section, results under `results/gauntlet/`. Off limits: the engine, `ladder.py`,
`bench.py`, training code.

## Decisions taken (on the owner's behalf)

- Fixed Act shape (11 fights, 2 elites, rest before boss) instead of a map
  walk; tunable later, recorded in docs/decisions.md "Gauntlet spec
  confirmed".
- Decks fixed per sequence (no rewards): measures combat play only.

## Outside assumptions

- Real Act 1 has ~6-9 hallway fights, 1-3 elites and a rest site before the
  boss; the shape sits inside that. No early test (it's a design choice).

## Verification

- `test_sequences_deterministic`: building sequences 0-49 twice gives equal
  lists; every sequence has 11 fights in the stated group order, no
  repeat in a row, two different elites, a boss last.
- `test_hp_carries`: with a fake play function (each fight loses 10 HP and
  wins, engine-like heal +6), HP at floor k+1 = end HP of floor k, and the
  boss starts after the 30% rest; a fake loss on floor 4 ends that
  sequence with 4 floors recorded.
- `test_read_pairs`: two fake result files give the expected clear
  difference and deaths by floor.
- End to end: `gauntlet.py play heuristic --sequences 4 --threads 2` runs
  and writes a file whose HP chain is consistent (hp_start of k+1 = hp_end
  of k, or the rest heal before the boss).

## Don't guard

Characters other than Ironclad; decks bigger than the pool's; agents that
don't load.

## Build steps

1. Sequence builder, HP chain with an injectable play function, output and
   resume, plus the three tests (check: tests pass; end-to-end run).
2. `read`, README section, and queue the first check (heuristic and
   champion `@hpb0.01`, 200 sequences each, one turn).

Build plan: 2 steps, in-session, Opus. No stop points.
