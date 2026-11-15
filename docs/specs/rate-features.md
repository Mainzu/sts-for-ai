# Power-rate feature columns: what each power is worth per turn

Status: closed (2026-10-31, built, off by default; decisions "Rate features: Guardian cost real but smaller; test depth, not a feature fix").

## Why (goal 1, and how we'll know)

The Demon Form probe (learned-play-results "Demon Form probe") shows the
r2 nets value playing Demon Form 0.09-0.15 below their best alternative on
states where the heuristic would play it 41% of the time; they play it in
12-17% of fights against the heuristic's 65% and lose Hexaghost 0.07 vs
0.54. Effects-mode rows already show the hook (turn start -> +Strength per
stack), so the net *sees* the mechanic; it doesn't turn it into its worth.
The heuristic does, through `hook_rates` (engine/src/heuristic.rs): per
power on an entity it sums Strength per turn, block per turn, self HP loss
per turn, damage to all per turn, draw per turn, and their one-shot and
per-event variants, in outcome units. Giving the net those sums as columns
is the most direct test of whether goal 1's representation is the gap. It
is content-agnostic: any power, official or generated, built from known
atoms gets rates without new code.

How we'll know: (1) the Demon Form probe on the new nets: the first-offer
gain moves toward the heuristic's (-0.007) and the played share toward
~40%; (2) three lean nets with `rates` on (`lean-rates-s{1,101,201}`)
against the lean nets they're paired with (same configs, seeds and shared
round 0, columns off), on tight2 and `tight_bosses`: adopt as default if
held-out boss gains >= 0.06 (Demon Form cells are 39 of ~115 held-out boss
cells; MDE on held-out boss with 3 shared-round-0 seeds ~0.05) with train
no worse than -0.015.

## Behavior

- Encoder option `rates` (off by default; off writes today's layout bit
  for bit, like `lookahead`). On: every entity (player and each monster)
  gets the `HookRates` fields as named scalar columns `rate_<field>`
  (block, block_once, strength, strength_once, strength_per_skill,
  strength_per_self_loss, self_loss, self_losses, countdown_loss,
  damage_all, draw), computed by the engine's own `hook_rates` (made
  `pub` and moved to `agent.rs` like lookahead's helpers, so heuristic and
  encoder share one function). Cards that grant a power (power rows'
  `grant_*`) get `grant_rate_<field>` = the rates of that power at the
  granted amount, so Demon Form in the draw pile carries its worth too.
- One horizon column per state: `turns_left_est`, the heuristic's own
  estimate if it has one (build step 0 checks `heuristic.rs`); if none,
  total monster HP / max(1, deck damage per turn from `deck_output`).
  Also per entity `rate_strength_x_turns` and `rate_block_x_turns`
  (rate x turns_left_est), since an MLP forms products poorly.
- `learn.py` config key `rates` (cache layout tag, net meta), `stsnet`
  passes it to Features and NetEvaluator, auto-on from a net's columns.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Encoder with rates off | identical batches | test_contract pins, golden_rows, lookahead_rows, threshold tests |
| Heuristic | identical values | engine golden + heuristic tests (moving `hook_rates` changes no number) |
| Saved nets | load and score identically | test_contract tiny-net outputs, test_net TRAIN_PIN |
| Lookahead option | composes (both on works) | new test: both on, column sets disjoint, round-trip |

## When in doubt

Prefer the heuristic's exact definitions over new ones (one source of
truth); prefer off-by-default over re-pinning.

## Scope

May change: `engine/src/agent.rs`, `heuristic.rs` (move only),
`py/src/features.rs`, `py/src/lib.rs` option plumbing, `scripts/stsnet.py`,
`scripts/learn.py`, configs `lean-rates-s*`, tests, README. Off limits:
column names/order with rates off, the heuristic's numbers, saved nets.

## Decisions (also in docs/decisions.md)

- Raw rates + two products with a turns-left estimate (over: raw rates
  only, which leaves the product to the MLP; over: sandbox-simulated rates,
  arm (b), later and costlier).
- Off by default behind an option (over: re-pinning every fixture).

## Verification

- `scripts/tests/test_rates.py`: on golden states, rates off is
  bit-identical to main; with rates on, a player with Demon Form 2 has
  `rate_strength` 2 and Metallicize 3 `rate_block` 3; a Demon Form card in
  the draw pile has `grant_rate_strength` = its amount; a generated copy of
  Demon Form (registry-lite pack) gives the same columns as Demon Form;
  save/load round trip with rates on.
- End to end (long run, ~3 x 50 min + probe): `lean-rates-s*`, then the
  Demon Form probe and the paired read.

## Build steps

0. Check `heuristic.rs` for a turns-left estimate; move `hook_rates` to
   `agent.rs`, `pub`. Check: engine tests, golden unchanged.
1. Encoder option `rates` with the columns. Check: test_rates (off
   identical, on values), test_contract, test_lookahead.
2. learn.py / stsnet plumbing, configs. Check: test_net, test_setups,
   round trip.
3. **Long run:** queue `lean-rates-s{1,101,201}` (and their columns-off
   twins if the matching lean nets don't exist on the merged layout), then
   the Demon Form probe on the new nets; read per the rule above.

Build plan: 4 steps, forks, Opus. No expected stop points.
