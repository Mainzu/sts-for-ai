# Saved from death: Lizard Tail and Fairy in a Bottle (R23)

Status: closed (2026-11-12, built and in use; landed c065cdee, e65da2d..786f2da; Lizard Tail and Fairy in a Bottle load from content packs).

## Outcome

Two more Act 1 entries load from content files and act as their game
classes do: **Lizard Tail** (relic: once per run, when you would die, heal
to 50% of max HP) and **Fairy in a Bottle** (potion: when you would die,
heal to 30% of max HP; used up; can't be drunk by hand). The piece they
share is general: "when the player would die" is a moment where the
player's hooks and a held potion can heal, and a player healed there
lives. A designer can use it in any pack; a net reads it in the columns it
already has.

**How it moves the goals.** Act 1: 47 -> 48 of 141 relics, 23 -> 24 of 33
potions. Goal 1: a pack can write a "saved from death" relic or potion. No
net-format change, no codec change, no stage: nothing to re-pin.

**R7 (heal) is already built**: `Heal` (since fickle-enemy step 1) and
`HealOf` (fractional-amounts). Its five unblocked entries, Blood Vial,
Bird-Faced Urn, Pantograph, Blood Potion and Regen Potion, already load
(research doc rows). Its other partners stay blocked on other atoms: Magic
Flower (R47 a heal modifier), Toy Ornithopter (P7 a "potion used"
trigger). So this spec loads no further R7 entry.

**Non-goals:** the run layer (R2, P2: carrying Lizard Tail's used counter
and the Fairy's slot between fights); Mark of the Bloom (no healing; an
Act 3 event relic, not in the 141); Magic Flower raising these heals (R47);
throwing a potion away; any other entry.

## The game's order

Read from the decompiled game (`decision/parity-source`;
Li-Binghui/MySlayTheSpire `characters/AbstractPlayer.java` 1501-1640,
`potions/FairyPotion.java`, `relics/LizardTail.java`,
`core/AbstractCreature.java` `heal`). `AbstractPlayer.damage`, once the
amount is final:
1. the `onLoseHp` / `wasHPLost` hooks of powers and relics are called
   *before* HP drops (Runic Cube, Self-Forming Clay, Centennial Puzzle:
   each queues an action, which runs after the death check);
2. HP drops, floored at 0; `onBloodied` if it crossed half (Red Skull,
   line 1605);
3. `if (currentHealth < 1)` (line 1614) and no Mark of the Bloom:
   - if the player holds a `FairyPotion` (any slot): `currentHealth = 0`,
     `potion.use(player)`, the slot is emptied, return;
   - else if Lizard Tail is held with `counter == -1`: `currentHealth = 0`,
     `onTrigger()`, return;
   - else the player is dead.

`FairyPotion.use`: heal `(int)(maxHealth * potency / 100)`, at least 1;
potency 30 (60 with Sacred Bark); `canUse()` is false, so it is never
drunk by hand. `LizardTail.onTrigger`: heal `maxHealth / 2`, at least 1,
then `setCounter(-2)` (used up). Its counter starts at -1 (the relic
default) and lives with the relic for the whole run. `heal` adds the
amount up to max HP and calls `onNotBloodied` if HP ends above half while
bloodied (no `isDying` check is hit: the player isn't dying yet).

## Behavior

### 1. The player's `OwnerDied` saves (Lizard Tail)

Today `OwnerDied` is a monster's trigger: its hooks run when the monster
reaches 0 HP (Spore Cloud), and nothing heals a monster at 0. This spec
gives the same moment to the player: **when the player's HP drops below 1
after an HP loss, the player's `OwnerDied` pass runs before the death
counts.** If the player's HP is 1 or more after it, the player lives and
the fight goes on; else the player is dead, as today.

- HP is set to 0 first (the game's `currentHealth = 0`; in no-death mode
  HP may be below 0 before it).
- First, a held potion with `"trigger": "OwnerDied"` (section 2) is used,
  if there is one; then, only if the HP is still below 1, the player's
  `OwnerDied` hooks run: relics first in order, then powers, as in any
  pass. Once the HP is 1 or more, the later hooks of the pass don't run
  (the game saves once: Fairy, else Lizard Tail).
- A heal in this pass works from 0 HP (today's `heal` refuses the dead)
  and heals at least 1 (both classes floor `healAmt` at 1).
- Effects allowed in a relic's `OwnerDied` hook: `Heal`, `HealOf`,
  `SetCounter`, `AddCounter`; others are a load error (as `CombatWon`).
  Pack powers' `OwnerDied` hooks load as today (a monster's Spore Cloud
  applies a debuff); for the player they run with today's effect runner.
- **Bloodied.** A saved player's bloodied state moves once, from the HP
  before the loss to the HP after the save: `OwnerBloodied` if it crossed
  down to half or below, `OwnerUnbloodied` if it ends above half from at
  most half before. The save's own heal runs neither. (The game runs
  `onBloodied` before the save and `onNotBloodied` inside the heal; the net
  result is the same for Red Skull, the only bloodied content: +3 then -3
  Strength is 0, its counter back where it was.) A player who isn't saved
  gets no bloodied hooks, as today.
- **After the save** the HP loss's other reactions run as for any living
  player: the matching `OwnerLostHp` hooks (the game queued them before
  the death check, so they resolve after it: Runic Cube draws, Centennial
  Puzzle draws 3), and the attack's remaining hits land.
- No-death mode: the same pass runs when HP drops below 1 (the game's
  check is `currentHealth < 1`).

**Lizard Tail** (`relics/LizardTail.java`): file counter -1 (the game's
unused value); `OwnerDied`, `CounterIs -1` -> `HealOf` 1/2 of `OwnMaxHp`
(`maxHealth / 2`), `SetCounter -2`. "Once per run" is the counter: -2 is
used up. The fight already takes a relic's starting counter from its
caller (`relics=[("Lizard Tail", -2)]`) and reads it back
(`Combat.relics`), so the run layer (R2) carries it between fights as it
will Happy Flower's; until then each fight starts it at the file's -1.

### 2. A potion with a trigger (Fairy in a Bottle)

A potion entry may have `"trigger"`. Only `"OwnerDied"` is accepted (any
other is a load error naming the potion). Such a potion:
- is never a legal action (`UsePotion` skips it: the game's `canUse()`
  false);
- is used in the player's `OwnerDied` pass (section 1), before the hooks:
  it leaves the held list, then its effects run at once, scaled by Sacred
  Bark as a drunk potion's are (`potion_scale`);
- has `effects` only (no `rows`), each `Heal` or `HealOf` (else a load
  error): it runs inside an HP loss, where nothing can pause.

When two held potions have the trigger, the first in held order is used.

**Fairy in a Bottle** (`potions/FairyPotion.java`): rare, potency 30,
trigger `OwnerDied`, `HealOf` 3/10 of `OwnMaxHp`. With Sacred Bark 6/10
(`(int)(maxHealth * 0.6)`); the potency test reads the share as a percent,
as Blood Potion's.

### Content format and wording

New: a potion's `"trigger"` key (`POTION_KEYS`, the key guard test,
`element_names` if keys are listed there). The player's use of
`OwnerDied` adds no element; its wording in `content/wording.json`
changes to cover both owners ("When its owner's HP reaches 0; the
player's hooks may heal here and save them"). The entries go in
`content/packs/act1-relics.json` and `act1-potions.json`.

### State, codec, search

No new state field, stage, codec tag or section: the save runs inside the
HP loss. Lizard Tail's counter and the held potions are already in the
state and the codec. The score's upper bound already counts a relic
hook's or a held potion's heal (`can_heal`), so it stays sound.

### The net

No new column. A Lizard Tail relic row sets `trigger_OwnerDied` with the
heal and counter columns it already has. A Fairy potion row writes its
trigger in the trigger column (`trigger_OwnerDied`) instead of
`Potion(Use)`, so a net can tell it from a drinkable heal. Existing nets'
inputs and every pin are unchanged.

## Steps

1. The player's `OwnerDied` pass in `state.rs` `lost_hp` (one loop shared
   with `combat_won_hooks`, which already runs relic and power hooks with
   counters outside a normal pass), the revive heal, the bloodied
   transition; the relic-hook load check; Lizard Tail; wording; tests.
2. The potion `"trigger"` key: parse and checks, `legal_actions`, use in
   the pass, the potion row's trigger column; Fairy in a Bottle; tests.
3. Docs (`docs/extending.md` "Relics" and "Potions", the research doc's
   rows, section and counts), the kb fact `measurement/act1-relics@files`,
   review fixes.

## Tests

In `engine/tests/act1_relics.rs` (`lizard_tail`) and `act1_potions.rs`
(`fairy_in_a_bottle`), each against the decompiled class:
- Lizard Tail: a lethal hit leaves the player at `max_hp / 2` and counter
  -2; a second lethal hit kills; started at counter -2 it doesn't save; a
  non-lethal hit changes nothing; `OwnerLostHp` hooks (Runic Cube) still
  run after a save; a save at 80 max HP from above half fires Red Skull's
  bloodied once.
- Fairy: saves to `(int)(max_hp * 0.3)` and leaves the held list; 60%
  with Sacred Bark (and Red Skull's Strength nets 0 when that ends above
  half from above half); never in `legal_actions`; with both Fairy and an
  unused Lizard Tail, the Fairy is used and the counter stays -1; at
  max HP 3 it heals 1.
- Load errors: a relic `OwnerDied` hook with `Draw`; a potion trigger
  other than `OwnerDied`; a triggered potion with `rows` or a `Block`.
- No-death mode: a save fires below 1.

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden, rules version | byte-identical, unchanged | golden |
| Fights without the new content | identical play and codec bytes | `relic_baseline` (old sections identical), `codec`, `potion_free_pins` |
| Monsters' `OwnerDied` (Spore Cloud) | unchanged | `monster_powers`, `monsters_act1` |
| Existing nets, pins | inputs byte-identical; no pin moves | `series_check` PASS, sts-py tests |
| Potions | drinkable potions unchanged | `act1_potions.rs`, `potion_use` |
| Bounds | sound with a save held | `can_heal` already counts it; a test |
| Search speed | `lost_hp` gains one comparison on an HP loss, no new pass otherwise | not measured (not the per-hit damage pipeline); `series_speed` on request |

## When in doubt

Prefer the game's `AbstractPlayer.damage` order, and an unchanged fight
without these entries over anything else.

## Scope

May change: `engine/src/state.rs` (`lost_hp`, the shared hook loop, a
revive heal, `legal_actions`), `potions.rs` (the `trigger` key),
`registry.rs` (the relic-hook check, key lists if needed),
`py/src/features.rs` (a potion row's trigger), `content/packs/act1-relics.json`,
`act1-potions.json`, `content/wording.json`, the explorer's potion wording
if it shows "use" for a triggered potion, tests, docs, the kb fact.

Off limits: codec, row columns, pins, `golden.txt`, existing nets' inputs,
the gauntlet and run layer, configs and yardsticks.

## Decision to confirm (expensive to reverse)

Reuse **`OwnerDied`** for the player's "would die" moment rather than a
new trigger (`OwnerWouldDie`). Reuse: no row column, no re-pin, no
conflict with the other three sessions' format changes; the two owners'
meanings line up (the moment HP reaches 0; a monster can't be healed
there, the player can). A new trigger: one zero column per mode and the
full re-pin recipe; clearer by name. Splitting them later is a format
change then. Recommended: reuse.
