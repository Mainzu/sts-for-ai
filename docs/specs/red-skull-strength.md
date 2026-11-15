# Red Skull as real Strength

Status: closed (2026-11-11, built and in use; owner-led; 8751c27..7f4ed3e on lane act1-content; As built: docs/extending.md "Relics"; decisions "Red Skull as real Strength, spec decisions").

## Outcome

Red Skull gives real Strength at the game's times, so Heavy Blade's
multiplier and Limit Break count it and the net sees it as Strength.

**Why.** Red Skull is the official static power `RedSkull` today
(`content/powers.json`: +1 damage dealt per hit per stack while the
owner's HP is at most half, 3 stacks from `content/packs/act1-relics.json`).
The relics build listed the gap (`docs/research/act1-relics-potions.md`
"R1 as built"): Heavy Blade multiplies only the Strength power and Limit
Break doubles only it, so the static's +3 is counted once where the game
counts 9, 15 or 6; and nothing the net learns about Strength carries over.

**How it moves the goals.** Act 1 (`decision/act1-finish`): one more relic
acts as the game's. Goal 1: two general HP-threshold triggers that
generated powers can use. Official fights without Red Skull, golden (no
Red Skull in any golden game), the rules version and every net stay as
they are.

## The game's behavior (parity source)

From the game's decompiled code (GitHub `aeubanks/sts`, read 2026-11-11;
`decision/parity-source`):
- `relics/RedSkull.java`: at battle start, an action queued at the back
  gives 3 Strength if the player `isBloodied` and the relic isn't active;
  `onBloodied` gives 3 Strength (queued at the front) if not active, then
  marks it active; `onNotBloodied` takes 3 Strength (front) if active,
  then marks it inactive; victory resets it.
- `characters/AbstractPlayer.java` ~1458 (`damage`, any HP loss that
  reaches HP): when HP is at most max HP / 2 and the player wasn't
  bloodied, it becomes bloodied and every relic's `onBloodied` runs.
  ~1529 (`heal`) and `core/AbstractCreature.java` ~393: when HP is above
  max HP / 2 and the player was bloodied, it stops being bloodied and
  `onNotBloodied` runs. ~1557 (combat start): bloodied is set from HP
  (HP at most max HP / 2, integer halves) with no relic call.
- So Strength changes only when HP crosses the half line, and at combat
  start when the fight begins at or below it. Max HP changes don't count.

## Behavior

- **Two triggers** (general; any owner, player or monster):
  `OwnerBloodied`: after HP loss takes the owner from above half its max
  HP to at most half (`2 × hp <= max_hp`, as `OwnerHpAtMostHalf` today);
  `OwnerUnbloodied`: after a heal takes it from at most half to above.
  They fire once per crossing, right after the HP change, in power-slot
  order; `OwnerBloodied` before the HP loss's `OwnerLostHp` reactions (as
  built: the game calls `onBloodied` inside `damage`, so it isn't deferred
  behind a card's own HP loss, and Hemokinesis' hit sees the Strength). A hit that kills fires
  nothing (the fight or the monster is over).
- **A hook condition** `OwnerHpAtMostHalf` (the static condition's rule,
  for hooks).
- **Red Skull:** the official power `RedSkull` becomes hooks:
  `OwnerBloodied` → `Apply Strength 1` to Me, `OwnerUnbloodied` →
  `Apply Strength -1` to Me (3 stacks: ±3). The combat-start check is a
  new pack power `RedSkullStart` in `content/packs/act1-relics.json`,
  `OwnerTurnStartPostDraw` (with the other start-of-combat relic powers),
  condition `OwnerHpAtMostHalf`: `Apply Strength 3` to Me; then
  `RemoveSelf`. The Red Skull relic grants both. The static condition
  `OwnerHpAtMostHalf` stays (generated statics may use it); `RedSkull`
  leaves `GENERIC_STATICS`.
- The power id, its index and its net column stay; only its rows change
  (a static row becomes two hook rows).

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden, rules version | byte-identical, unchanged | golden test |
| Official fights without Red Skull, nets | byte-identical states and features in their layouts | `series_check` PASS (product net) |
| The static mechanism | `OwnerHpAtMostHalf` statics still work | `statics.rs`, moved from `RedSkull` to a test pack power |
| Relics (R1) | the other relic tests pass unchanged | `act1_relics.rs` |
| Codec | encodings unchanged | codec tests |
| Search speed | `series_speed` at most 10% slower | job (step 3) |

## Scope

May change: `engine/src/hooks.rs` (triggers, condition, `GENERIC_STATICS`),
`engine/src/state.rs` (`lose_hp`, `heal`, `condition_holds`),
`engine/src/registry.rs` (parse, element names), `content/powers.json`
(`RedSkull`), `content/packs/act1-relics.json`, `content/wording.json`,
`py/src/features.rs` (the trigger list; new row trigger columns are zero
on every state without these hooks), tests, docs.

Off limits: codec encodings; `golden.txt`; any existing net's input in its
layout; configs, yardsticks, controls; gauntlet and run layer; saved packs
and data on disk.

## Verification

Written first (step 1, passing on unchanged code): `red_skull_pins`
(feature arrays in the product layout and a fixed set of official fight
states without Red Skull), and the static tests moved to a pack power.

Then (`engine/tests/red_skull.rs`, each against a line of the game's
code):
- a fight started at half HP or below: 3 Strength after the opening draw;
  above half: none.
- damage to half or below: +3 Strength once; more damage below half: no
  change; a heal above half: Strength back down by 3; down again: +3.
- Heavy Blade under Red Skull deals 14 + 3 × 3 (and 14 + 3 × 5 upgraded);
  Limit Break doubles the 3.
- `OwnerBloodied` / `OwnerUnbloodied` on a monster's pack power fire at
  its crossings; a killing hit fires neither.
- End to end: golden identical, `series_check` PASS, wording and explorer.

## Build steps

1. **Pins** on unchanged code; the static tests moved off `RedSkull`;
   decision into `docs/decisions.md`. Check: pass.
2. **Triggers and condition:** `OwnerBloodied`, `OwnerUnbloodied`,
   `OwnerHpAtMostHalf` (hooks), parse, element names, wording, features'
   trigger list. Check: trigger tests on a pack power, pins, wording.
3. **Red Skull:** the power's hooks, `RedSkullStart`, the relic, the
   game-order tests, docs (`docs/extending.md` triggers;
   `act1-relics-potions.md` row and deviation notes; the lane fact).
   Check: `red_skull.rs`, `act1_relics.rs`, golden, `series_check`, and a
   `series_speed` job (the crossing check sits in `lose_hp`, a hot path;
   at most 10% slower).

## Build plan

3 steps, forks, Opus. No stop point.
