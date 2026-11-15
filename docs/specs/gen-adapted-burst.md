# Bursts on generated enemy mechanics (lane gen-adapted-column, step 1)

Status: closed (2026-11-08, built and in use; finetune.py generated-mechanic bursts, b8c189f3/f9898327; lane read: decisions "Lane gen-adapted-column closed (2026-11-08)").

**Outcome.** `finetune.py` trains a burst whose new games are a generated
enemy mechanic of the bench (`mutate_monsters.GEN`, a pack power on every
living monster) on its parent elites, played by the net or the heuristic,
so the lane can measure games to adapt per mechanic by teacher (goal 1's
adapted column on generated enemies).

**How it moves goal 1, and how we'll know.** Goal 1 is play on generated
content; its number is how few games a net needs to adapt to new content
(operating.md, "Training"). The bench (`measurement/gen-enemies@table24`)
measured what generated enemies cost zero-shot; it cannot say whether the
cost is cheap to train away, nor whose games teach it. This source makes
the burst; the lane's step 2 reads the target pairing on the bench's 1000
starts x 4 seeds against the zero-shot net: a teacher that halves the cost
at 99 games is the column's first row, none that does fails the lane.

**Non-goals.** No new monster or engine code; no change to the bench's
reads; no new teacher beyond the net (any search setting) and the
heuristic.

## Behavior

The existing mutated-content dict (`{"mutated": [...], "skip", "val_fights"}`)
gains, all optional:
- names from `mutate_monsters.GEN` (and the ladder) in `mutated`, beside
  `MODS`; a pack mechanic is applied with `mutate_monsters.variant` after the
  bench's pack (`gen_pack()`) is loaded, as the bench plays it;
- `encounters`: [encounter names]: only fights on those encounters count;
  validation is the last `val_fights` of them, training the rest from
  position `skip` on (positions over all fights, as `--starts` counts);
- `repeat`: true: when `games` exceeds the training fights, game g plays
  training fight g mod n with play seed index g div n (each repeat a fresh
  seed); without it, too few fights refuse before any play, as today;
- `net_settings` (default `@hpb0.01`): the parent's search settings when
  the net plays (the bench reads `@hpb0.01@tsl1`).
- The config's `player` ("net", default, or "heuristic") picks the
  teacher, as for generated cards.
Configs without these keys play, seed and cache exactly as before (their
cache identity is unchanged).

## Fits with

- Existing mutated bursts (`configs/adapt-*`): same fights, seeds and cache
  key; pinned by `test_mutated_unknown_mod`, `test_mutated_games`
  (unchanged), and a new `test_mutated_ident_unchanged`.
- The bench (`mutate_monsters.play`): the variant of a pack mechanic is
  built by the same `variant` function; `test_mutated_gen_games` checks the
  pack power is on every monster in the first state.

**When in doubt:** prefer the bench's way of building a variant over a new one.

## Scope

`scripts/finetune.py` (the mutated path), `scripts/family.py` (a table kind
"gen" for these reads), their tests, new burst and family configs in
`configs/`. Off limits: the engine, `mutate_monsters.py`'s play and read,
the cache identity of existing configs.

## Verification

- `test_mutated_encounters`: 20 fake fights alternating two encounters,
  `encounters` one, skip 4, val 3: validation the last three of that
  encounter, training from position 4; with `repeat` and games 9 over 4
  fights, the fights cycle with repeat indices 0, 0, 0, 0, 1, 1, ...; without
  `repeat` it refuses.
- `test_mutated_gen_games`: a heuristic game of `GE-AttackLoss-Damage` on
  Sentries starts with the pack power on all three monsters.
- `test_mutated_ident_unchanged`: the cache identity of an old dict equals
  the identity built before this change.
- End to end: the lane's first queued burst (a smoke run needs main's
  data, which only a queued job sees) writes a run whose log shows the
  mutated train and validation sets built.

## Build steps

1. The source and its tests (above); in-session.
2. Configs for the target pairing (step 2 of the lane), once the probes pick it.
