# Card removal on the gauntlet

Status: closed (2026-11-02, read: decisions "Card removal read"; confirmed by the manager role).

## Why (goal 2)

Deck choice is the biggest goal-2 lever found (card rewards +0.18 clears,
sim-boss +0.155). A real Act 1 offers one or two removals (shops, events,
Neow); the gauntlet has none. This measures how many clears one removal
buys on the headline setting, and whether the sim chooser approach extends
from adding cards to removing them. We'll know from two protocol reads:
`--remove strike` vs none (value of a removal) and `--remove sim` vs
strike (value of choosing). If a removal is worth under ~1 HP end-HP, shops
and removal events drop down the run-layer list.

## Outcome

`gauntlet.py play ... --remove {none,strike,sim}` offers one removal after
the first elite's reward (floor index `REMOVE_FLOOR` = 5, a shop proxy);
without the flag (or `none`) nothing changes.

Non-goals: gold, shops, more than one removal, curses, two-turn
simulation in the chooser, a learned chooser.

## Behavior

- `run(..., remove_hook=None)`: after floor `REMOVE_FLOOR`'s reward (if
  any), for every sequence still alive, `remove_hook(items)` with items
  `(sequence, HP, deck)` returns per sequence `None` (keep) or a card name;
  the first copy of that name leaves the deck. That floor's row records
  `"removed": name` or `"removed": null`. No hook: no key, rows unchanged.
- `strike`: remove the first card whose base name is `Strike` (`Strike` or
  `Strike+`), else keep. No simulation.
- `sim`: options are keep, then each distinct name in the deck in
  first-occurrence order. Each option is scored exactly as `sim_choose`
  scores its options (same horizon: the next floor's pool, plus the boss
  pool with `--sim-boss`; same seeds for every option; same score), with
  the option's deck. Seeds come from a stream clear of the reward
  chooser's: encounter streams 5000 / 6000 (the reward chooser uses
  3000 / 4000) and seed offsets 70 / 80 within the floor's `k * 100`
  block (the reward chooser uses 0-7 and 50-57; the rest chooser
  1000-1015). First maximum wins,
  so ties keep the deck.
- Factor the scoring so `sim_choose` and the removal chooser share one
  function over option decks; `sim_choose`'s results stay bit-identical
  (existing tests `test_skip_reproduces`, `test_deck_grows`,
  `test_blocks_same_rows` and the reward-chooser tests pass unchanged).
- CLI `--remove {none,strike,sim}` (default none; `"remove": <kind>` enters
  settings only when not none, so older files keep matching). The sim
  chooser plays one turn deep with the same player, like `--rewards sim`.

## Fits with

Rewards, sim-boss and `--rest` unchanged; `gauntlet_protocol`, `summary`,
`read` ignore the new key. When in doubt, match the reward chooser.

## Scope

`scripts/gauntlet.py`, `scripts/tests/test_gauntlet.py`, README gauntlet
lines. Off limits: Rust engine, sequences, shape, the reward chooser's
choices.

## Decisions

- One removal after the first elite: early enough to matter for most of
  the act, late enough that one reward has joined the deck. Alternatives:
  Neow-style removal before floor 1 (removes only starter cards; simpler
  but less like a shop); two removals (more effect, less realistic).
- The `strike` rule arm separates "a removal helps" from "the chooser
  helps", and guards against the winner's curse seen at the rest site.

## Verification

Tests first (`test_gauntlet.py`):
- `test_remove_hook_run`: a hook removing `Strike` at floor 5: decks of
  floors 6+ have one `Strike` fewer, the floor-5 row has `"removed":
  "Strike"`; a hook returning None -> `"removed": None`, decks unchanged;
  no hook -> rows identical to today's.
- `test_remove_strike`: rule removes `Strike` / `Strike+`, keeps a deck
  without one.
- `test_remove_sim`: fake sim_play that wins only decks without `Defend`
  -> picks `Defend`; a fake that wins everything -> keep (tie); option
  seeds equal across options and disjoint from the reward chooser's seeds
  for the same sequence and floor.
- Existing gauntlet tests pass unchanged.
- End-to-end (job queue, one turn, 10-29 net `@hpb0.01`, `--start starter
  --rewards sim --sim-boss`, sequences 0-499):
  `--remove strike --against results/gauntlet/net1029-hpb0.01-starter-simboss.json`
  and `--remove sim --against <the strike file>`. Read: protocol verdicts,
  what the sim chooser removes (counts), deaths by floor.

## Build steps

1. Tests + `remove_hook`, `strike` and `sim` choosers, `--remove`
   (one step). Check: `pytest scripts/tests/test_gauntlet.py`.
2. (long) The two reads through the job queue.
