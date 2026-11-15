# Enemy Strength priced by the hits it will still land

Status: closed (2026-11-08, built and in use; @shl<k>, off by default; lane failed, decisions "Lane strength-by-hits-left closed"; @shl0.005 a goal-1 candidate column, kb decision/shl-goal1-column).

## Why (goal 1, goal 2 through Nob)

One turn deep the leaf's HP price (`@hpb0.01`) decides most choices at
elites, and enemy Strength reaches the score only through the saturated
net value. On generated punish-an-action mechanics this walks the net into
a growing enemy: AttackLoss-Damage x Gremlin Nob costs +12.8 HP a fight
(`measurement/gen-enemies@batch1`). The flat `@esp0.04` removes that cost
but costs +13 to +22 HP on AttackLoss-Strength, where every attack feeds
the Strength and a flat price stops the net attacking
(`measurement/esp-on-gen@batch1`). A price that scales with the hits the
Strength will still land falls as attacking shortens the fight, so it can
keep the first fix without the second failure. It reads only primitives
(Strength, HP, damage rates), so it carries to generated and custom
monsters: a zero-games answer is goal 1's best kind. How we'll know:
step 2 of the lane (gen batch 1 on elites, 4 seeds) reads the Nob cost and
AttackLoss-Strength's cost against zero-shot and `@esp0.04`; the stop rule
is the charter's (`lane/strength-by-hits-left`).

## Outcome

A player setting `@shl<k>` that subtracts `k x clamp(score / 2, 0, 1) x
H` from each leaf score, where `H = sum over living monsters of Strength
x hits per round x rounds it still lands hits`. Off by default: nothing
re-pins, golden and series_check are unchanged.

Non-goals: learning the price; other powers (Vulnerable, Weak, Ritual's
rate); two-turn tuning; changing the heuristic player's own estimate.

## Behavior

- `H` comes from the heuristic's own kill-order estimate
  (`heuristic::parts`), in a new `pub fn strength_hits_left(s) -> f32`:
  - hits per round: `damage_rate(s, slot).1` (expected hits over the next
    4 rolls), at least 0;
  - rounds it lands hits: `min(t_i, t_player)`, where `t_i` is the round
    the kill-order loop expects that monster to die (the `t` already
    computed there, capped at `MAX_ROUNDS`), and `t_player` is the rounds
    until the player dies at the expected rate: `rounds x hp / taken` when
    the expected damage `taken` exceeds the HP, else no limit;
  - Strength as held (negative counts negative, a credit for Strength down).
- Over combats (`is_over`) and with no living monster `H` is 0.
- `@shl` combines with `@hpb`, `@esp`, `@tsl1` and the other leaf settings;
  with a survive score net it is refused, like `@esp`.
- The heuristic's `estimate`, `hp_loss_estimate` and `turns_left_estimate`
  return bit-identical values (the new value is computed beside them).

## Fits with

- Heuristic player and its estimates: unchanged values (existing engine
  tests and golden; series_check PASS with `@shl` off).
- `@esp`, `@hpb`, `@hpe`: unchanged scores when `@shl` is absent (the
  existing `hp_bonus`/`enemy_strength_price` Rust test; `Prices::default()`
  keeps the early return bit-identical).
- `bench.player_settings`, `stsnet.rust_evaluator`, and every script that
  passes a player string through (mutate_monsters.py, gauntlet.py).

## When in doubt

Prefer `@esp`'s exact pattern (a field next to `enemy_strength`, applied in
`add_prices`) over a general framework.

## Scope

May change: `engine/src/heuristic.rs` (the new function and the fourth
value inside `parts`), `py/src/lib.rs` (Prices field, config key
`strength_hits_price`, `add_prices`, its Rust test), `scripts/stsnet.py`
(`rust_evaluator` kw), `scripts/bench.py` (`@shl` parsing), Python tests,
README player-spec lines. Off limits: rules, features and encoders,
training code, the heuristic player's scores, the solved DB.

## Decisions taken (on the owner's behalf)

- Rounds from the heuristic's kill order, not a fresh estimate: one
  definition of "rounds left" in the project. Alternative: total rounds
  for every monster (prices a monster killed first as if it lived to the
  end; worse for multi-monster fights such as Sentries).
- Scales for step 2: k 0.005 and 0.01. At 0.01 a point of Strength that
  will land 10 hits costs what 10 HP cost under `@hpb0.01` (the price's
  natural unit, before block); 0.005 allows for block absorbing about
  half, and at Nob's opening (about 10 rounds, under 1 hit a round) it about equals the flat
  `@esp0.04` that fixed Nob.

## Verification

1. Engine test: on a Gremlin Nob state with +3 Strength,
   `strength_hits_left` > 0, equals 3 x hits x rounds within 1e-4 when
   checked against `damage_rate` and `turns_left_estimate` (one monster:
   its t is the rounds), and is 0 with Strength 0, with Nob dead, and when
   over. `estimate` on that state is bit-identical before and after the
   change (pinned value from unchanged code).
2. Rust test in `py/src/lib.rs` beside the `enemy_strength_price` one:
   score = net + HP term - k x f x H, within 1e-6; k 0 bit-identical.
3. Python: `player_settings("a/m.pt@hpb0.01@shl0.01@tsl1")` parses; a bad
   suffix raises; `load_evaluator` with `@shl0` scores bit-identically to
   without.
4. End-to-end: `mutate_monsters.py play` with `--net ...@hpb0.01@shl0.01@tsl1`
   on a few starts runs.

## Don't guard

Huge Strength (bounded by the score factor); Strength on the player.

## Build steps

1. Engine: `strength_hits_left` inside `parts`; test 1. Check: `cargo
   test -p sts-engine heuristic`, golden identical.
2. Bindings and parsing: Prices field, config key, `@shl` in bench and
   stsnet, tests 2-3; build the wheel. Check: `cargo test` for the py crate
   filter `net_eval`, the Python tests, test 4.
3. (lane step 2, a queued run of about 45 min x 2 at 3 threads) the two
   scales on gen batch 1.
