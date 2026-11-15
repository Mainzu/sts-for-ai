# Recurring debuff leaf (lane `recurring-debuff-leaf`, steps 1-2)

Status: closed (2026-11-10, lane read: fail; decisions "Lane recurring-debuff-leaf closed"; kb measurement/portfolio-recurring-debuff-leaf; The @pd1 setting stays in scripts/bench.py).

Lane `recurring-debuff-leaf` (charter `kb get lane/recurring-debuff-leaf`;
decisions "Lane recurring-debuff-leaf opened"). Spec by the lane worker,
2026-11-10, confirmed under the mandate (operating.md, "Specs and builds").

## Why (goal 1)

Goal 1 needs a player that prices content it never trained on. On the
generated enemies bench the 10-29 net one turn deep loses HP to monsters
that put Weak back on the player every turn (GE-TurnStart-Weak,
GE-TurnEnd-Weak; `measurement/gen-enemies@table24`), and shown card
numbers only cut that cost to 0.54 / 0.40 of itself
(`measurement/portfolio-shown-card-numbers`). The net sees Weak 1-2 at a
leaf and prices a debuff that wears off, when it never will. A leaf that
also applies the next k turns of those hooks simulates the rule instead of
adding a price, with no games. We'll know at step 2: per mechanic, the
change in HP lost and win rate per elite fight against the same net `@tsl1`
(`results/mutate/gen-wf-tsl1.json`), parents as retention; go if both Weak
rows lose half their cost at 2 se at one k with parents within 0.3 HP.

## Outcome and non-goals

Outcome: a player setting `@pd1` (with `@pl<k>`) whose projected leaf also
runs living monsters' once-a-turn Apply of Weak, Frail or Vulnerable to the
player k more times; step 2's two reads queued.

Non-goals: debuffs the player applies to monsters; one-shot or
self-removing hooks; Strength loss and other debuffs; training; changing
`@pl<k>` alone.

## Behaviour

- `CombatState::projected_leaf_with(k, debuffs)`: `projected_leaf(k)` when
  `debuffs` is false; when true, a monster's hook (same `fires` filter)
  also runs its `Apply { power: Weak | Frail | Vulnerable, target:
  AllOpponents | Opponent }` effects (amounts times stacks times k) through
  the engine's own `apply_power` (Artifact cancels as in play). The
  player's own hooks keep the Strength/Dexterity filter.
  `projected_leaf(k)` is `projected_leaf_with(k, false)`.
- Search: `SearchConfig.projected_debuffs: bool` (false: off), used only
  where `projected_ticks > 0`.
- Python: evaluator key `projected_debuffs` (default false), ensemble
  members must share it, `stsnet.rust_evaluator(projected_debuffs=...)`,
  `bench.player_settings` reads `@pd1` and refuses it without `@pl<k>`.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| default search, `@pl<k>` alone | unchanged | golden (`cargo test`), `engine/tests/projected_leaf.rs` unchanged and passing |
| player strings | existing strings parse as before | `scripts/tests/test_projected_leaf.py` |

## Scope

May change: `engine/src/state.rs`, `engine/src/search.rs`, `py/src/lib.rs`,
`scripts/stsnet.py`, `scripts/bench.py`, their tests, this spec, the lane's
results doc (`docs/research/recurring-debuff-leaf.md`).

Off limits: official content, golden data, rules version, codec, features,
default search, training.

## Decisions taken

- A flag on top of `@pl<k>` sharing its k (alternatives: its own k, more
  surface for no read the charter asks for; widening `@pl` itself, which
  would change the closed lane's player).

## Verification

1. Rust `projects_recurring_weak`: a monster holding a pack power whose
   OwnerTurnStart hook applies Weak 1 to AllOpponents; k = 2 with debuffs:
   player Weak +2; without: unchanged; with Artifact 1 on the player: the
   first Apply is cancelled. Search with `projected_debuffs` true and
   `projected_ticks` 0 equals the default.
2. Python: `@pl2@pd1` parses; `@pd1` alone and `@pd2` refuse.
3. End to end: `mutate_monsters.py play --starts 10 --seeds 1 --groups
   elite --players one --net <10-29>@tsl1@pl2@pd1 --mods GE-TurnStart-Weak`.

## Build steps

1. Engine + Python + tests. Check: `cargo test --release`, the Python test.
2. Queue step 2 (two jobs: k 2 and 4, 8 seeds, the charter's mods), with
   the compare against `results/mutate/gen-wf-tsl1.json` in the notes.
