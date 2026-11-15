# Block and Apply amounts that read a quantity (building block C4)

Status: closed (2026-11-07, built and in use; lane act1-content, 3a3116e5; decisions "act1-content C4 build: ApplyOf takes official powers only"; Entrench and Limit Break are in content/packs/act1-ironclad.json).

## Outcome

A pack card can gain block, or apply a power, by an amount read from the
state when it resolves (`base + k × quantity`, the `Amount` that
`ScaledDamage` already uses), so Entrench ("double your Block") and Limit
Break ("double your Strength") are written as pack entries.

**How it moves the goals.** Goal 1's custom content needs effects whose
size depends on the state, not only on the card; today only damage can
(`ScaledDamage`). This gives block and powers the same expression, so any
new card of the "scale what you have" kind is data, not code. For the lane
(goal 2's real Act 1 pool) it writes 2 of the 15 missing Ironclad cards (4
entries with upgrades). We'll know: the two cards load from
`act1-ironclad.json`, tests check their numbers against the game's, and
the series checks hold (golden identical, `series_check` PASS,
`series_speed` at most +10%).

**Non-goals.** No official card moves to the new effects (Body Slam and the
rest stay as they are). No new `Quantity`. No headline read: nothing
official changes.

## Behavior

- New effect `BlockOf(Amount)`: the user gains `resolve(amount)` block as
  is, with no Dexterity or Frail (the game's Entrench gains block equal to
  current block through a plain block action). A negative or zero amount
  gains nothing.
- New effect `ApplyOf { power, amount: Amount, target }`: resolves the
  amount, then applies it exactly as `Apply` with that amount (so a negative
  Strength doubles further and counts as a debuff, as `Apply` of a negative
  Strength does today; Artifact cancels it). A zero amount applies nothing.
- Both resolve when they run, like `ScaledDamage`. Pack JSON:
  `{"BlockOf": {"base": 0, "k": 1, "of": "OwnBlock"}}` and
  `{"ApplyOf": {"power": "Strength", "amount": {...}, "target": "Me"}}`,
  read and written by the registry's existing `amount` parser and
  `amount_json`.
- `Effect::scaled(k)` (a power's stacks) multiplies `base` and `k` of both.
- Features: `BlockOf` adds `base` to `block` and `k` to a new scalar
  `block_of_k`; `ApplyOf` adds `base` to its power's column (as `Apply`)
  and `k` to a new scalar `apply_of_k`. The heuristic values `BlockOf`
  at the block it would gain now and `ApplyOf` as `Apply` of its resolved
  amount where it reads a state, else of `base`.
- The cards (values checked in build step 1): Entrench, Skill, cost 2
  (Entrench+ cost 1), `BlockOf {0, 1, OwnBlock}`. Limit Break, Skill, cost
  1, exhaust (Limit Break+ not exhaust), `ApplyOf Strength {0, 1,
  OwnStrength}` on `Me`.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Golden and the rules version | identical | golden test |
| Official features and the product net | official states encode the same; new scalars are zero on them | `series_check` (heuristic and product bit-identical) |
| Exhaustive matches on `Effect` (`bound.rs` heals, `target()`) | new arms; `ApplyOf` has a target, `BlockOf` none | compile, `quantity_amounts` tests |
| Pack loading and writing | a pack with the new effects round-trips through `amount_json` | new test |
| Existing pack tests | pass | engine suites |

## When in doubt

Prefer the game's numbers and `Apply`'s existing path over a new rule.

## Scope

May change: `engine/src/effects.rs`, `state.rs` (run the effects),
`registry.rs` (parse, write), `bound.rs`, `heuristic.rs`,
`py/src/features.rs` (two scalars), `content/packs/act1-ironclad.json`
(four entries), engine and Python tests, the inventory doc,
`docs/decisions.md`. Off limits: official content files, golden, the net,
`scripts/` except tests.

## Decisions taken

- Two new effects rather than a raw-block flag on `Block` and an `Amount`
  inside `Apply` (alternative: widen `Block(i16)` and `Apply`'s `amount`
  to `Amount`, which touches every official card's effect and the
  features' hot path; the new arms leave official play untouched).
- Features: one scalar each for the quantity part, not a one-hot of the
  quantity (alternative: reuse `expr_q_*`, which today mean a damage
  expression and would make old nets read a Body Slam). Only one quantity
  each is in content; a one-hot can follow when a second appears.

## Outside assumptions

- Entrench: cost 2, upgrade cost 1, doubles current block, not modified by
  Dexterity or Frail. Limit Break: cost 1, exhaust, upgrade removes
  exhaust, doubles Strength (negative too). Checked 2026-11-07 against
  sts_lightspeed (`Cards.h` costs and `doesCardExhaust`; `Actions.cpp`:
  `EntrenchAction` is `player.gainBlock(bc, player.block)`, a raw add;
  `LimitBreakAction` is `player.buff<STRENGTH>(strength)`); the wiki pages
  were unreachable (HTTP 402). One mismatch: sts_lightspeed's `buff` path
  lets a negative Limit Break past Artifact, while the game applies a
  `StrengthPower` through `ApplyPowerAction`, where negative Strength is a
  debuff Artifact cancels. The spec keeps the game's rule (the `Apply`
  path); the case needs negative Strength and Artifact at once.

## Verification

- `block_of_doubles_block`: with 7 block, 2 Dexterity and Frail, Entrench
  leaves 14 block; with 0 block, 0.
- `apply_of_doubles_strength`: Strength 3 -> 6; Strength -2 -> -4; 0 stays
  0 with no power entry; with Artifact 1 and Strength -2, Artifact goes to
  0 and Strength stays -2.
- `limit_break_exhausts_unless_upgraded`: Limit Break ends in the exhaust
  pile, Limit Break+ in the discard pile.
- `quantity_effects_round_trip`: a pack holding both effects writes and
  re-reads to equal definitions.
- End to end: the `act1_cards` test that plays the pack's entries with
  greedy play to an end now includes the four entries.

## Don't guard

Quantities other than `OwnBlock` and `OwnStrength` in the new effects
(they resolve like `ScaledDamage`'s), amounts that overflow `i16`.

## Build steps

1. Check the outside assumptions; write the tests above (they fail: the
   effects don't exist). Check: tests compile once the variants exist.
2. The two effects (effects, state, registry, bound, heuristic), the four
   pack entries. Check: engine suites (all but solve) pass, golden
   identical.
3. Features' two scalars; build the wheel; Python suites touching packs,
   features and nets pass; `series_check` PASS against main.
4. `series_speed` main against the build, as a queued job with 14 idle
   cores (S1's 0454 pattern). Check: at most 10% slower.

Build plan: 4 steps, in-session, on Opus. No stop points expected.
