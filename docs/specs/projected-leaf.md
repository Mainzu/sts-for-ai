# Projected leaf (lane `projected-leaf`, steps 1-2)

Status: closed (2026-11-07, lane read: fail; decisions "Lane projected-leaf closed"; kb measurement/portfolio-projected-leaf; The @pl<k> leaf setting stays in scripts/bench.py).

Lane `projected-leaf` (charter `kb get lane/projected-leaf`; decisions "Lane
projected-leaf opened"). Spec by the lane worker, 2026-11-07, confirmed
under the mandate (operating.md, "Specs and builds").

## Why (goal 1)

Goal 1 needs a player that prices new content it never trained on. The
record says the one-turn net's remaining novelty costs sit in value that
recurs past the leaf (`cause/novelty-is-horizon`): `@tsl1` repaired Demon
Form's first tick with no games (+7.54 HP), but inflame-turn1 still costs
-0.018 (0.005) wins `@tsl1`, and Ritual 2 on elites costs the net. A leaf
that also applies the next k ticks of a growth hook lets the net's value
see Strength it will have (or face) in k turns, with no training. We'll
know by step 2: the cards rung's novelty cost on inflame-turn1 at k = 2
against `@tsl1` on the same starts and seeds (charter: go needs 2 se toward
zero on some target; fail if inflame-turn1 moves less than 1 se).

## Outcome and non-goals

Outcome: a player setting `@pl<k>` (k a whole number 1-9; off by default)
whose one-turn search scores each end-of-turn leaf after the projection,
and step 2's read queued.

Non-goals: projecting block, damage, draw, energy or debuffs (the
charter's targets are lasting powers); hooks that remove or reduce
themselves (one-shots such as Lose Strength, wearing-down powers); a
chance-weighted or decaying k; two turns deep (the option is applied where
`@tsl1` is, at one-turn leaves; the two-turn search's leaves are untouched
unless it reaches the same code path, which the build checks and notes);
training.

## Behaviour

- `CombatState::projected_leaf(k)`: a copy in which, for the player and then
  each living monster in slot order, every hook of a held power whose
  trigger is `OwnerTurnStart` or `OwnerTurnEnd`, whose effects hold no
  `RemoveSelf` or `ReduceSelf`, runs its `Apply { power: Strength |
  Dexterity, target: Me }` effects k more times (amounts times stacks times
  k; other effects of the hook dropped), skipping powers marked
  just-applied as the engine's hooks do. A state with no such hook, a
  finished combat, or k = 0 is returned unchanged.
- Search: `SearchConfig.projected_ticks: u8` (0 = off). At an end-of-turn
  leaf the order is: leaf clear block (`@lcb1`), turn-start leaf (`@tsl1`),
  then the projection; the leaf scores the projected state.
- Python: the evaluator config key `projected_ticks` (default 0), ensemble
  members must share it, `stsnet` passes it, and `bench.player_settings`
  reads `@pl<k>` (once, k whole 1-9), so any bench takes
  `<net>.pt@hpb0.01@tsl1@pl2`.
- Cards rung (`mutate_cards.py`): players `pl2` and `pl3` (the net
  `@hpb0.01@tsl1@pl<k>`) next to `tsl`, read like `tsl` (novelty column
  per player) plus the paired contrast `pl<k> - tsl` by start.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| search with the option off | bit-identical | `cargo test` golden; `series_check` not needed: the option defaults off and no default path changes (a test plays search with projected_ticks 0 and compares with the base config) |
| `@tsl1`, `@lcb1` | unchanged alone | `engine/tests/leaf_clear_block.rs`, turn-start leaf tests |
| `player_settings` | existing strings parse as before | `scripts/tests` bench settings tests (existing) plus `@pl2` cases |
| `mutate_cards.py` existing players and files | same rows and reads | `scripts/tests/test_mutate_cards.py` |

## When in doubt

Prefer the turn-start leaf's pattern (`run_hooks_*` with a keep filter)
over new hook machinery; prefer leaving an effect unprojected over guessing
its future.

## Scope

May change: `engine/src/state.rs` (projected_leaf), `engine/src/search.rs`
(the config field and the leaf), `py/src/lib.rs` (config key, ensemble
check), `scripts/stsnet.py`, `scripts/bench.py`,
`scripts/analysis/mutate_cards.py`, their tests (a new
`engine/tests/projected_leaf.rs`, `scripts/tests/test_projected_leaf.py`),
this spec, the lane's results section.

Off limits: official content, golden data, the rules version, the codec,
feature layout, default search behaviour, training code.

## Decisions taken

- Only Strength and Dexterity applied to the owner, from once-a-turn hooks
  without self-removal (the charter's wording). Alternatives: every
  once-a-turn effect (block and damage would be credited without the turns
  being played: Metallicize's block counted k times at a leaf whose block
  the next turn clears), or a learned projection (needs games, which is
  what the lane avoids).
- Monsters projected too (Ritual, the generated enemies' TurnStart-Strength),
  as the charter says: the net sees the Strength a monster will have.

## Verification

Tests first:
1. `projects_demon_form` (Rust): player with DemonForm 2 at a leaf, k = 2:
   Strength +4; k = 0: unchanged.
2. `projects_ritual_on_monster`: a Cultist with Ritual 3 (not just applied),
   k = 3: Strength +9; LoseStrength on the player is not projected;
   Metallicize gives no block.
3. `search_option_off_identical`: search on a few states with
   projected_ticks 0 equals the default config's result.
4. `test_projected_leaf.py`: `@pl2` parses, `@pl0` / `@pl10` / twice
   refuse; `bench.load_evaluator` with `@tsl1@pl2` plays a Demon Form
   fight; a Demon Form decision changes on at least one bench state
   between `@tsl1` and `@tsl1@pl2` (or the test records that none did).
End to end: `mutate_cards.py play --starts 10 --seeds 2 --players
heuristic,tsl,pl2 --mods inflame-turn1 --out <tmp>` and its read.

## Don't guard

k above 9; powers with both a self-removal and a growth effect.

## Build steps

1. Engine: `projected_leaf`, the config field, the leaf order; tests 1-3.
   Check: `cargo test --release`.
2. Python: config key, ensemble check, stsnet, `@pl<k>`, mutate_cards
   players; test 4. Check: suites on a dev build; end to end.
3. (Long run, about 50 min.) Queue step 2 of the charter: `mutate_cards.py
   play --starts 200 --seeds 16 --players heuristic,tsl,pl2 --mods
   inflame-turn1,df-c2-s1,metal-c2-a5,bash-c1-d5 --out
   results/mutate/cards-pl.json` (tsl replayed on the same seeds as the
   control rows; it must equal cards-a.json's tsl rows).

Build plan: 3 steps, in-session, on Opus. No stop
points expected.
