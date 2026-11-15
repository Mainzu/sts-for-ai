# Turn-start leaf

Status: closed (2026-11-07, built and in use; @tsl1; decisions "Lane turn-start-leaf closed"; in fights per "Turn-start leaf in fights, plain leaf in trial fights").

Lane `lane/turn-start-leaf` (exploration, cap 1 cpu-h). Spec confirmed by
the lane worker under the mandate (2026-11-07).

## How it moves the goals

Goal 1 (play well on content the net never trained on): one turn deep,
a power that pays at the owner's turn start (Demon Form; on the generated
bench every turn-start power, -0.292 (0.049) wins against the heuristic)
costs the nets because its first tick lands after the leaf
(`cause/unseen-cards-half-edge`). Scoring the leaf after the player's
turn-start hooks that need no chance moves that tick inside the search,
with no games and no change to any leaf without such a hook. We'll know
from one read: the 10-29 net with the flag on both cell books one turn
deep by the three strata (Demon Form decks against the plain-leaf files),
and on the generated-power bench by trigger. Go: Demon Form decks gain at
least 3 HP at 2 se, train decks and the other held-out decks within 1 HP.

## Outcome

A search switch, `turn_start_leaf`, off by default: with it on, every
end-of-turn leaf (the state after the last searched turn's `EndTurn`) is
scored as a copy on which the player's turn-start hooks have run, as far
as they need no chance. Non-goals: the heuristic evaluator (it prices
recurring powers by rule already), the draw leaf, two-turn tuning,
promoting anything.

## Behaviour

- `CombatState::turn_start_leaf(&self) -> Option<CombatState>`: when the
  state's player turn-start hooks are still to run (stage `MonsterRolls`,
  `StartTurn`, or `TurnStarted` with the turn's draw pending) and the
  player holds a power with an `OwnerTurnStart` hook, a copy with those
  hooks run; `None` otherwise (the leaf stays as it is). A finished
  combat or a state past the turn start (draw resolved, hooks run) gives
  `None`.
- Hook effects kept: `Damage`, `PlainDamage`, `Block`, `GainEnergy`,
  `LoseHp`, `Apply`, `RemoveSelf`, `ReduceSelf`. Everything else is left
  out: draws, random targets and exhausts, picks, card adds, and the
  effects that read the hand (`ScaledDamage`, `ScaledBlock`,
  `ExhaustHand`), since the hand isn't drawn yet. Hooks run as the engine
  runs them (`run_hooks_with`: stacks, `just_applied`, conditions, Poison's
  source, combat ending on a death).
- At `MonsterRolls` (a monster's move roll pending) the copy's block and
  energy are not reset first: a turn-start `Block` or `GainEnergy` adds to
  the leftover. Accepted: the read's cards are Strength, HP loss and
  damage.
- Search (`SearchConfig::turn_start_leaf`): in the tree, the `EndTurn`
  child that becomes a leaf is replaced by its `turn_start_leaf()` copy
  when that is `Some`; a copy that finished the combat scores exactly.
  Leaves cut by the node cap or by large chance events mid-turn, and the
  draw leaf's leaves, are untouched.
- Python: `NetEvaluator` config key `turn_start_leaf` (bool, default
  false); `stsnet.rust_evaluator(..., turn_start_leaf=False)`; player
  string setting `@tsl1` (bench.py; only the value 1). Ensemble members
  must share it.

## Fits with

- Golden replays and every search with the flag off: unchanged (golden
  test; `turn_start_leaf_off_is_unchanged`).
- `draw_k`, `end_hp_price`, `rule` plumbing in `Eval::config`: unchanged
  values when the flag is off (existing py tests).
- Player strings: every existing setting parses as before
  (`test_draw_leaf.py`, new `test_turn_start_leaf.py`).

When in doubt: prefer leaving a leaf unchanged over guessing an effect.

## Scope

May change: `engine/src/state.rs` (the copy method; a filtered form of
`run_hooks_with`), `engine/src/search.rs` (config field, the leaf
branch), `py/src/lib.rs` (Prices, config, ensemble check),
`scripts/stsnet.py`, `scripts/bench.py` (the `@tsl` setting),
`scripts/analysis/gen_powers_read.py` (`play` accepts a player string with
settings, saved under a name with the settings), `scripts/analysis/cards_by_half.py`
(the lane's read), tests under `engine/tests/` and `scripts/tests/`,
docs. Off limits: content, features/encoder, training, the heuristic.

## Verification

Engine (`engine/tests/turn_start_leaf.rs`):
1. `turn_start_leaf_off_is_unchanged`: a mid-fight search with the field
   false equals the default search (nodes, leaves, options, line).
2. `demon_form_tick_lands_in_the_leaf`: player with Demon Form 2 after
   `EndTurn`: `turn_start_leaf()` is `Some` with Strength +2; with no
   turn-start power, `None`.
3. `drawn_effects_left_out`: Brutality (lose 1 HP, draw 1): the copy has
   1 HP less, the same hand, draw pile and pending event.
4. `past_turn_start_is_none`: a state awaiting an action: `None`.
5. `search_scores_ticked_leaves`: a recording evaluator sees the
   Strength in every leaf of a Demon Form search with the flag on.
Python: `@tsl1` parses to `{"turn_start_leaf": 1.0}`, `@tsl2` is refused;
a net search with the flag on scores differently from off on a Demon Form
state, identically on a state without turn-start powers.
End to end: the read below.

## Build steps

1. Engine method, search field, engine tests 1-5; `cargo test` green,
   golden identical.
2. Python plumbing and tests; sts rebuilt in the worktree's venv-free
   check (`maturin build`), py tests pass.
3. Land with an sts swap (AGENTS.md gotchas); queue the read: cell
   gauntlet `model.pt@hpb0.01@tsl1` on both books (3 threads, ~3 min
   each) and the generated bench one turn deep (`gen_powers_read.py play`
   with `@tsl1`); then the read in `cards_by_half.py --tsl`.

Build plan: 3 steps, in-session, on Opus. No stop points.
