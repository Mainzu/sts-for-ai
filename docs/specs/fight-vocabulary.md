# Fight vocabulary for relics and potions (small atoms and the gamble)

Status: closed (2026-11-12, built and in use; owner session, branch fight-vocab; 00b20ea9; As built: docs/extending.md "Relics"; rows in docs/research/act1-relics-potions.md "Fight vocabulary").

## Outcome

Nine more Act 1 entries load from content files and act as the game's
classes do: **Pen Nib, Orichalcum, Gremlin Horn, Ginger, Turnip, Meat on
the Bone, Gambling Chip** (relics) and **Fruit Juice, Gambler's Brew**
(potions). Each needed a piece of fight vocabulary the engine lacks
(`docs/research/act1-relics-potions.md` "Missing building blocks" and
"Counter relics"). The pieces are general: a designer can use each in any
pack, and a net reads each where a row column exists.

**How it moves the goals.** Act 1 (`decision/act1-finish`): 40 -> 47 of
141 relics, 21 -> 23 of 33 potions. Goal 1: seven new words a pack can
use. All net-format cost is paid once, in one re-pin.

**Non-goals:** the run layer (R2, P2: Fruit Juice's max HP outside the
fight, counters between fights); the after-block damage stage (R12); the
would-die replacement (R23); discovery (P3); any other entry.

## Behavior

### 1. A hook with two conditions (Pen Nib)

A hook's `"condition"` may be a list of two conditions; the hook fires
when both hold. At most one of the two may carry a number
(`CardsPlayedThisTurnBelow`, `CounterIs`, `OwnerBlockIs`): the row has one
`condition_param`. More than two, or two with numbers, is a load error
naming the hook's owner. A single condition is written as today.

**Pen Nib** (`relics/PenNib.java`, `powers/PenNibPower.java`), counter
carried between fights by the caller:
- `CombatStart`, `CounterIs 9` -> Apply pack power `PenNib` 1;
- `CardPlayed by Owner`, Attack -> AddCounter 1;
- `CardPlayed by Owner`, `CounterIs 10` -> SetCounter 0;
- `CardPlayed by Owner`, [Attack, `CounterIs 9`] -> Apply `PenNib` 1.

`PenNib`: static `DamageDealt` Multiply 2/1; `CardPlayed by Owner` Attack
-> `RemoveSelf`. Applied in a pass, it first fires on the next one (as
today), so the 9th Attack doesn't remove it.

### 2. Condition `OwnerBlockIs(n)` (Orichalcum)

True when the hook's owner has exactly `n` block. **Orichalcum**
(`relics/Orichalcum.java`): `OwnerTurnEnd`, `OwnerBlockIs 0` -> Block 6.
Relic hooks run before power hooks, so Metallicize and Plated Armor's
turn-end block comes after the check, as the game's `onPlayerEndTurn`
runs before the powers' `atEndOfTurn`. The class's `trigger` field is set
nowhere else in the game's code (searched): it's left out.

### 3. Trigger `OpponentDied` (Gremlin Horn)

The player's hooks, when a monster reaches 0 HP and some monster still
lives (the game's `onMonsterDeath` with `currentHealth == 0 &&
!areMonstersBasicallyDead()`), after that monster's own `OwnerDied` hooks.
A split (Slime Boss) isn't a death. **Gremlin Horn**: `OpponentDied` ->
GainEnergy 1, Draw 1.

### 4. A debuff filter on `DebuffApplied` (Ginger, Turnip)

A `DebuffApplied` replacement may name one power (`"power": "Weak"`): it
acts only on that power being applied. Without the name it acts on every
debuff, as today (Artifact). Relics hold no replacements, so Ginger and
Turnip each give a pack power holding the replacement, as Strike Dummy
gives its static: **Ginger** `powers` [`GingerWard` 1]: `DebuffApplied`
Weak -> Cancel; **Turnip** [`TurnipWard` 1]: Frail -> Cancel. Neither
loses a stack (the game checks `hasRelic` in `ApplyPowerAction`). Check
the game's order against Artifact in the build (with both, does Artifact
still lose a stack on Weak?) and follow it.

### 5. Trigger `CombatWon` (Meat on the Bone)

The player's hooks once when the fight is won, before the combat-end heal
(`win_heal`), as `AbstractRoom.endBattle` calls Meat on the Bone's
`onTrigger` before `player.onVictory()` (Burning Blood). No hook runs when
the player dies. Effects allowed: `Heal`, `HealOf`, `SetCounter`,
`AddCounter`; others are a load error (nothing else means anything once
the fight is over). **Meat on the Bone**: `CombatWon`,
`OwnerHpAtMostHalf` -> Heal 12 (the game's `currentHealth <= maxHealth /
2.0F`, which is `2 × hp <= max_hp`). The search's heal bound counts a
`CombatWon` heal as it counts `win_heal`.

### 6. Effect `GainMaxHp(n)` (Fruit Juice)

Max HP and HP both rise by `n` (the game's `increaseMaxHp(n, true)`).
Raised by potency (Sacred Bark: 10). **Fruit Juice**: `GainMaxHp` 5. The
run layer doesn't carry the new max HP out of the fight yet (P2): the
fight result reports it, the gauntlet ignores it.

### 7. Effect `DrawPicked` and a relic's pick (Gambler's Brew, Gambling Chip)

`DrawPicked` draws as many cards as the `Pick` just before it in the same
row (card, potion or relic hook) took; written right after a `Pick`, else
a load error. Chosen cards are discarded first, then all are drawn in one
draw (a reshuffle may bring the discarded cards back, as the game's
`GamblingChipAction`).

**Gambler's Brew**: [Pick `DiscardFromHand` any number (`exact` false),
`DrawPicked`]. With an empty hand it does nothing.

**A relic hook may hold a `Pick`** (only on `CombatStart` and
`OwnerTurnStartPostDraw`). The pick opens once the trigger's pass has run
(the game's `addToBot`), before the player's first play; the hook's
effects after the `Pick` run after `Done`. The player chooses with the
existing `Choose` / `Done` actions. **Gambling Chip**: `OwnerTurnStartPostDraw`,
`CounterIs 0` -> SetCounter 1, Pick `DiscardFromHand` any number,
`DrawPicked` (the game's `activated` flag, reset at `atBattleStartPreDraw`;
the counter starts at 0 each fight).

### Content format and wording

New words: the condition list, `OwnerBlockIs`, `OpponentDied`,
`CombatWon`, a replacement's `power`, `GainMaxHp`, `DrawPicked`. Each in
`registry::element_names()` with its words in `content/wording.json`. The
entries go in `content/packs/act1-relics.json` and `act1-potions.json`.

### State and codec

The relic's open pick is a new stage, written only while it is open:
every other state's bytes are unchanged. No other state field changes
(the pick count is the pick's `n` minus what's left).

### The net

New row columns: triggers `OpponentDied` and `CombatWon`; condition
`OwnerBlockIs` (its `n` in `condition_param`). A two-condition hook's row
sets both condition columns. The filter of a replacement row: one new
column per power, `Applying(<power>)` (reusable later for a trigger "the
owner applies a power", Champion Belt). `GainMaxHp` and `DrawPicked` add no
column (as `HealOf`): a card or potion vector stays the same width, so the
contract tiny nets keep loading. Existing nets' inputs in their layouts
are byte-identical; the default-width pins move by added zero columns
only (`docs/extending.md` "What a format change costs").

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden, rules version | byte-identical, unchanged | golden test |
| Fights without the new words | identical play and codec bytes | `relic_baseline` (old sections identical), `codec` pins |
| Existing nets | byte-identical inputs in their layouts; `series_check` PASS | product-layout pins, `series_check` |
| Default-width pins | old columns equal by name, new columns zero | re-pin per `docs/extending.md` |
| Picks | card and potion picks unchanged; agents and search see the relic pick's actions | `potion_use`, `decisions`, new tests |
| Search speed | `series_speed` at most 10% slower | job (last step) |

## When in doubt

The game's decompiled class over the research doc's line; an unchanged
fight without the new words over anything else.

## Scope

May change: hooks (condition list, triggers, replacement filter), effects,
the hook runner and stage machine (relic pick), registry parse, key lists,
element names, wording, the official writer, `py/src/features.rs`, the
heal bound, the two Act 1 pack files, tests, docs, facts.

Off limits: `golden.txt`; existing nets' inputs in their layouts; configs,
yardsticks, controls; the gauntlet and run layer; saved packs and data.

## Decisions taken (owner, 2026-11-12)

- One batch: small vocabulary and the pick-count draw; one re-pin.
- Ginger and Turnip as helper pack powers (relics hold no replacements),
  as Strike Dummy for statics, rather than giving relics replacements.
- The filter's net column per power (`Applying(<power>)`), rather than no
  column for the filter.

## Outside assumptions

The decompiled game (AxorusMT/sts, read 2026-11-12): the relic and potion
classes named above, `AbstractRoom.endBattle` (Meat before `onVictory`),
`GamblingChipAction`; each test names its line.

## Verification

Written first, passing on unchanged code: `relic_baseline`, the codec
pins, the product-layout pins.

Then, each in `act1_relics.rs` / `act1_potions.rs` or a new
`fight_vocabulary.rs`:
- two conditions: a hook fires only when both hold; three conditions and
  two numbers are load errors; Pen Nib: the 10th Attack deals double
  (Strike 12; with 1 Strength and Weak, 10, `trunc((6+1) × 2 × 3/4)`, as
  the game's float), a Skill at counter 9 doesn't add a second stack, the
  11th deals 6; a fight starting at counter 9 doubles the first Attack.
- Orichalcum: 6 block at turn end with 0 block, none with 1; with
  Metallicize 3 and 0 block, 9.
- Gremlin Horn: killing one of two Louses gives +1 energy and 1 card;
  killing the last ends the fight with nothing.
- Ginger: Weak from a monster is cancelled, Vulnerable lands; Turnip the
  same for Frail; Artifact with Ginger as the game's order.
- Meat on the Bone: won at 40/80 HP ends at 40 + 12 + 6; at 41/80, 41 + 6;
  the heal bound with it held counts the 12.
- Fruit Juice: 80/80 -> 85/85; with Sacred Bark 90/90.
- Gambler's Brew: discard 2 of 5, hand ends at 5 (3 kept, 2 drawn);
  `Done` with none picked draws none; empty hand: nothing.
- Gambling Chip: on turn 1 the pick opens after Bag of Preparation's draw
  and before any play; turn 2 has none; the open pick's state round-trips
  through the codec; `greedy_action` and the search finish a fight with it.
- wording: every new word has its text.

## Build steps

1. Pins first (as Verification's first line).
2. Two conditions, `OwnerBlockIs`, `OpponentDied` (parse, runner, wording);
   Pen Nib, Orichalcum, Gremlin Horn.
3. Replacement filter; Ginger, Turnip.
4. `CombatWon`, the heal bound; Meat on the Bone.
5. `GainMaxHp`; Fruit Juice.
6. `DrawPicked`, the relic pick stage (codec, actions, agents); Gambler's
   Brew, Gambling Chip.
7. Net columns, re-pin by column name; `series_check`.
8. Research doc rows, facts; `series_speed` job.
