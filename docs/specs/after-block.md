# After-block damage stages (R12: The Boot, Torii, Tungsten Rod, Fossilized Helix)

Status: closed (2026-11-12, built and in use; confirmed by the coordinator session; landed 11c49f9..6b61946; docs/extending.md "After block"; series_speed 0942).

The rows and named limits: `docs/research/act1-relics-potions.md` "After
block".

## Outcome

Four more Act 1 relics load from content files and act as the game's
classes do: **The Boot, Torii, Tungsten Rod, Fossilized Helix**, with the
game's **Buffer** power (a pack power any pack's card, potion, relic or
monster can apply). They need what the research doc calls R12: changes to
the amount of damage or HP loss *after block is removed*, which the engine
lacks (its replacements act before block: Intangible).

**How it moves the goals.** Act 1 (`decision/act1-finish`): 47 -> 51 of
141 relics. Goal 1: four replacement events a pack can use (one per game
hook point), one action, one range field.

**Non-goals:** any other entry; the run layer; the agents' damage
estimates (named limit below); Buffer as an official power.

## The game's order (decompiled AxorusMT/sts, read 2026-11-12)

`AbstractPlayer.damage(DamageInfo)` runs for every hit and every HP loss
to the player: attacks (`NORMAL`), thorns-like damage (`THORNS`: Thorns,
Burn, Sharp Hide, Combust, potions, relic damage) and `HP_LOSS`
(`LoseHPAction`, `PoisonLoseHpAction` both call `target.damage`):

1. amount floored at 0; `IntangiblePlayer` caps it at 1 (every type);
2. `decrementBlock` (skipped for `HP_LOSS`);
3. the attacker's relics' and powers' `onAttackToChangeDamage`;
4. the target's relics', then powers' `onAttackedToChangeDamage`
   (**Buffer**: amount > 0 -> 0, and Buffer loses 1);
5. the target's powers', then relics' `onAttacked` (**Torii**: owner
   set, not `HP_LOSS` or `THORNS`, amount 2..5 -> 1), only when the
   damage has an owner;
6. the target's relics' `onLoseHpLast` (**Tungsten Rod**: amount > 0 ->
   amount - 1), every type;
7. if amount > 0: `wasHPLost` hooks, HP falls, `onBloodied`, death.

`AbstractMonster.damage` is the same up to its end: block, then the
player's relics' `onAttackToChangeDamage` when the player attacks (**The
Boot**: owner set, not `HP_LOSS` or `THORNS`, amount 1..4 -> 5), the
attacker's powers' `onAttackToChangeDamage`, the monster's powers'
`onAttackedToChangeDamage` (Buffer on a monster), `wasHPLost`,
`onAttacked`; no `onLoseHpLast`. The Boot acts after the monster's
Intangible (applied while the damage is computed), so an Intangible
monster hit for 1 takes 5, as in the game.

Every one of the four checks `amount > 0` (Torii `> 1`), so a hit block
fully absorbs touches none of them: Buffer isn't spent on it.

**Fossilized Helix** (`relics/FossilizedHelix.java`): `atBattleStart`
applies `BufferPower(1)` to the player.

## Behavior

### 1. Four after-block replacement events

A replacement row's `"event"` may name four new events. Each is one pass
over the owner's replacement rows (in power order, as today), run in this
order after block, while the amount is above 0 (once a pass leaves 0, the
later passes don't run and no row's `then` fires):

| Event | Whose rows | Damage kinds | Game hook | Content |
|---|---|---|---|---|
| `DealtAfterBlock` | the attacker's | attacks only | `onAttackToChangeDamage` | The Boot |
| `TakenAfterBlock` | the target's | every hit and HP loss | `onAttackedToChangeDamage` | Buffer |
| `AttackedAfterBlock` | the target's | attacks only | `onAttacked` | Torii |
| `HpLossLast` | the target's | every hit and HP loss | `onLoseHpLast` | Tungsten Rod |

"Attacks" are the engine's `HpLossFrom::Attack` (`attack()`: card and
monster `Damage` / `ScaledDamage` hits), the game's `NORMAL` type.
`PlainDamage` (the game's `THORNS`) and `LoseHp` / Poison (`HP_LOSS`)
run only the two "every" passes; for `LoseHp` and Poison there is no block
step, the passes follow the existing `HpLoss` replacement (Intangible).
All four passes run for the player and monsters alike (the game's monster
has no `onLoseHpLast`; nothing official uses it on a monster). The amount
the passes leave (floored at 0) is the HP lost: the `OwnerLostHp`,
`OwnerBloodied`, `OwnerDied`, `OwnerAttackHit` reactions and The
Guardian's Mode Shift see it, as the game's `wasHPLost` sees it. The
`OwnerAttacked` hooks (Thorns, Flame Barrier) fire as today, lost HP or
not (the game's Thorns checks no amount).

### 2. Action `AtLeast(n)` and row field `upTo`

- `{"AtLeast": n}` (n >= 1): an amount below `n` becomes `n` (only
  positive amounts reach the after-block passes, so 0 stays 0).
- `"upTo": n` on any replacement row (n >= 0): the row applies only when
  the amount is at most `n`. Without it, as today.

### 3. The relics and Buffer (pack data)

Relics hold no replacements (fight-vocabulary decision), so each gives a
helper pack power holding the row, as Ginger gives `GingerWard`; all in
`content/packs/act1-relics.json`:

- **Buffer** (the game's id): `TakenAfterBlock`, `Cancel`, then
  `ReduceSelf 1`. Stacks: each stack absorbs one hit.
- **The Boot** `powers` [`TheBoot` 1]: `DealtAfterBlock`, `AtLeast 5`
  (the game's "1..4 -> 5": only positive amounts reach the pass).
- **Torii** [`Torii` 1]: `AttackedAfterBlock`, `Cap 1`, `upTo 5`.
- **Tungsten Rod** [`TungstenRod` 1]: `HpLossLast`, `Add -1`.
- **Fossilized Helix** [`Buffer` 1] (the `powers` shorthand is the game's
  `atBattleStart`).

If a power id equal to a relic id clashes in the registry, the helper powers get a
`Ward` suffix as Ginger's.

### Content format and wording

New words: the four events, `AtLeast`, `upTo`. Each in
`registry::element_names()` (`replacement_event`, `replacement_action`,
and `upTo` with the replacement keys) with its words in
`content/wording.json`. The official powers' writer writes `upTo` when
set (no official power uses the new words).

### State and codec

No change: no new state field, stage or codec tag. Buffer and the helper
powers are pack powers on the player's (or a monster's) power list.

### Speed

The hot damage path gains one test per hit: the binding records, once
per interned slot set, whether any bound power has a row of the four
events; official content (empty binding) and packs without such rows skip
the passes. While here, `replaced_of` reads the generated powers from the
binding's `'static` slice instead of collecting them into a `Vec` per
call (same order, same result).

### The net

New row columns: the four events as replacement-row triggers
(`Replace(DealtAfterBlock)` and the rest); the condition column
`AmountAtMost` for `upTo` (its `n` in `condition_param`, as `CounterIs`);
the row-only column `replace_at_least` (as the relic row's
`counter_set_to`, so card and intent vectors keep their width and the
contract tiny nets load). Six zero columns per mode; existing nets'
inputs in their layouts are byte-identical; the default-width pins move
by added zero columns only (re-pin as `docs/extending.md` "What a format
change costs", the handoff's recipe, as the last commit before landing,
on top of current main).

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden, rules version | byte-identical, unchanged | golden test |
| Fights without the new words | identical play and codec bytes | `relic_baseline` (old sections identical), `codec` pins |
| Intangible, Artifact, Ginger, Turnip | unchanged (before-block and debuff passes untouched) | existing tests |
| Existing nets | byte-identical inputs in their layouts; `series_check` PASS | product-layout pins, `series_check` |
| Default-width pins | old columns equal by name, new columns zero | re-pin per `docs/extending.md` |
| Score bounds | still upper bounds (the passes only lower HP loss, never raise HP) | existing bound tests |
| Search speed | `series_speed` at most 10% slower than its old build (as fight-vocabulary accepted; 0936 worst -3.5%) | job (last step) |

## Known limits (named)

- `agent::incoming_damage` and the greedy agent's / heuristic's damage
  estimates (`attack_damage` per intent hit, minus block) don't apply
  Torii, Tungsten Rod or Buffer, as they don't apply the player's
  Intangible cap today. The search and `projected_leaf` play the real engine and
  see them.
- Order inside one pass is power order (official, then pack powers in
  bind order), as for every replacement today. Content has at most one
  row per pass.

## When in doubt

The game's decompiled class over the research doc's line; an unchanged
fight without the new words over anything else.

## Scope

May change: `hooks.rs` (`Replaced`, `Replace`, `Replacement.up_to`),
`state.rs` (`take_damage`, `lose_hp`, `attack`, `replaced_of`), registry
parse, key lists, element names, wording, the official writer, the
binding's slot-set flag, `py/src/features.rs`, `act1-relics.json`, tests
(`act1_relics.rs`, a new `engine/tests/after_block.rs`,
`relic_baseline` new sections), docs, facts.

Off limits: `golden.txt`; existing nets' inputs in their layouts;
configs, yardsticks, controls; the gauntlet and run layer; saved packs
and data; the other three sessions' blockers.

## Outside assumptions

The decompiled game (AxorusMT/sts, read 2026-11-12):
`characters/AbstractPlayer.java` `damage`, `monsters/AbstractMonster.java`
`damage`, `core/AbstractCreature.java` `decrementBlock`,
`relics/Boot.java`, `Torii.java`, `TungstenRod.java`,
`FossilizedHelix.java`, `powers/BufferPower.java`,
`actions/common/LoseHPAction.java`, `actions/unique/PoisonLoseHpAction.java`;
each test names its class.

## Verification

Written first, passing on unchanged code: `relic_baseline`, the codec
pins, the product-layout pins.

Then, in `act1_relics.rs` (the four relics) and `after_block.rs` (the
words):
- **The Boot**: a Strike on a monster with 3 block takes 5 HP (3 -> 5);
  with 6+ block, 0; a Weak Strike (4) on 0 block, 5; a Bash (8), 8; Bronze
  Scales' Thorns 3 and Mercury Hourglass' 3 (`PlainDamage`) stay 3; a pack
  monster with Intangible hit by Strike loses 5.
- **Torii**: unblocked attack damage 5 -> 1, 2 -> 1, 1 -> 1, 6 -> 6;
  fully blocked: 0; Burn's 2 at turn end (`PlainDamage`) stays 2;
  Bloodletting's 3 stays 3.
- **Tungsten Rod**: an unblocked attack of 6 -> 5; 1 -> 0 (no
  `OwnerLostHp` reaction: Centennial Puzzle doesn't draw); Bloodletting's
  3 -> 2; Burn's 2 -> 1; with Torii, 5 -> 0; with Intangible, 10 -> 0.
- **Fossilized Helix / Buffer**: Buffer 1 at combat start; a fully
  blocked hit leaves it; the first unblocked hit loses no HP and spends
  it; the next hit lands; with Buffer and Torii a hit of 4 spends Buffer;
  Bloodletting with Buffer loses no HP and still gives its energy;
  Buffer 2 absorbs both hits of a two-hit attack (or two attacks);
  Plated Armor (Thread and Needle) keeps its stacks when Buffer absorbs
  the hit; Centennial Puzzle doesn't draw on an absorbed hit.
- **Buffer on a monster** (a pack monster's `start_powers`): a Strike
  loses it no HP and spends Buffer; with The Boot the same (The Boot runs
  first).
- Load errors: `AtLeast 0`, `upTo -1`.
- wording: every new word has its text; the four events, `AtLeast` and
  `upTo` round-trip through the official writer's format.
- The binding flag: a fight with the act1-relics pack bound and none of
  the new powers held plays identically to before (relic_baseline).

## Build steps

1. Pins first (as Verification's first line).
2. The four events, `AtLeast`, `upTo` (parse, runner in `take_damage` /
   `lose_hp` / `attack`, binding flag, `replaced_of` slice, wording,
   element names, writer); `after_block.rs` with pack powers written in
   the test.
3. The pack entries: Buffer, the three helper powers, the four relics;
   `act1_relics.rs` tests; relic_baseline new sections.
4. Net columns; re-pin by column name (last commit before landing, on
   current main); `series_check`.
5. Research doc rows and section, `docs/extending.md` "Relics", the kb
   fact `measurement/act1-relics@files`; `series_speed` job.
