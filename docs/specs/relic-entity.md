# Relics as their own entity

Status: closed (2026-11-11, built and in use; owner-led; 56943d6..9f2a7ed, landed 58e2c153; As built: docs/extending.md "Relics"; decisions "Relics as their own entity, spec decisions").

The relic rows and step 4's difference table:
`docs/research/act1-relics-potions.md` "Relic entity (step 4)".

## Outcome

A relic exists in a fight as itself: the player holds a list of relics,
each with its own hooks and a counter, acting at the game's times, and a
net can read them as relic rows. This replaces "a relic is a set of
starting powers" (`docs/specs/relics.md`), which can't hold relic state,
shares the 12-power cap, needs one-shot helper powers (AnchorStart,
RedSkullStart, ...) and shows the net a relic's Strength as any Strength.

**How it moves the goals.** Act 1 (`decision/act1-finish`): relics act as
the game's (Red Skull's active flag exactly; no helper powers), and R2's
counters carried between fights get a home. Goal 1: a designer writes a
relic as hooks in the vocabulary powers use, and a net learns it by its
rows. Fights without relics, golden, the rules version and every
existing net's input stay as they are.

**Non-goals** (owner, 2026-11-11): the run layer (the gauntlet holding,
dropping, buying relics; Neow); carrying counters between fights (R2: this
spec gives each relic a starting counter the fight takes, nothing more);
loading relics beyond today's 23; potions.

## Behavior

### In the fight

- **The list.** `Player` holds up to 16 relics (`RELIC_CAP`; owner), each a
  relic id and an `i16` counter, in the order given. More is an error
  naming the relic. Monsters hold none. A fight built with no relics has an
  empty list.
- **Hooks.** A relic carries hooks in the power hook format (trigger,
  condition, effects) and runs them for the player. For one trigger, the
  player's relics run first, in list order, then the player's powers (the
  game runs relic hooks before power hooks at turn start; any other order
  the game's code shows for a relic is checked by its test).
- **Combat start**, two triggers with the game's names (`AbstractRoom`
  ~255, `decision/parity-source`): `CombatStartPreDraw`
  (`atBattleStartPreDraw`) runs before the opening draw; `CombatStart`
  (`atBattleStart`) after it, before the turn-1 post-draw and turn-start
  hooks. Powers may use them too.
- **The counter.** Effects `SetCounter(n)` and `AddCounter(n)` change the
  relic's own counter (an error in a power's hook); condition
  `CounterIs(n)` tests it (false in a power's hook). The fight starts each
  counter at the value the caller gives (default: the relic's `counter`
  field, default 0).
- **Effects** a relic's hooks run are the power hooks' (Apply, Block,
  Draw, GainEnergy, damage, Heal, WinHeal, ...), acting as the player's.
  Powers a relic applies are real powers: they use the 12 power slots and
  can be removed, as in the game.

### Content format

A relic entry (`content/relics.json`, a pack's `"relics"`) gains
`"hooks"` and `"counter"`. Its `"powers"` list stays as shorthand for a
`CombatStart` hook applying each to Me, in order (the game's battle-start
relics: Vajra, Bronze Scales, Thread and Needle, ...). `rarity`, `fights`,
`win_heal` keep their meaning. The key lists and the guard test
(`docs/extending.md` "Card rules") cover the new keys; wording covers the
new triggers, effects and condition.

### The 23 relics move over

Every helper power goes (`PreparationStart`, `AnchorStart`, `MarblesStart`,
`PhilosopherStart`, `MarkOfPainStart`, `LanternStart`, `TeaSetStart`,
`RedSkullStart`, `Hourglass`, `RelicEnergy`, `PuzzleOnHpLoss`,
`StrikeDummy`, `AshesOnExhaust` and the rest named only by relics): each
relic writes its hooks itself, at the game's trigger, read from the game's
relic class. Red Skull becomes exact: `CombatStart` (HP at most half,
counter 0: +3 Strength, counter 1), `OwnerBloodied` (counter 0: +3, counter
1), `OwnerUnbloodied` (counter 1: −3, counter 0). The official `RedSkull`
power goes back to unused (its id and net column stay). A relic fight may
play differently from today where the new shape is closer to the game
(owner: game parity wins); each difference is named in the build's report
with the game's line.

### State and codec

The list lives in the fight state (so two states with different relics
never encode the same). The codec writes it as a new optional section,
only when the list is not empty: a fight without relics encodes byte for
byte as today. Solved-DB keys follow the codec.

### The net (opt-in)

A new opt-in row kind `relic`: each held relic writes its hook rows in the
power row format with a new grant column `relic`, a row-only column
`relic_counter` (its counter), and, in ids mode only, a `relic_<name>`
column per known relic (as cards' ids). New trigger, effect and condition
names add row columns. A net whose layout lacks them leaves them out, so
every existing net's input is byte-identical; the default-width pins move
by added zero columns only (`docs/extending.md` "What a format change
costs"). The powers a relic applies still reach the power columns.

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden, rules version | byte-identical, unchanged | golden test |
| Fights without relics | byte-identical states, codec bytes | `red_skull_pins`, `card_rules_pins`, `turn_start_pins` |
| Existing nets | byte-identical inputs in their layouts; `series_check` PASS | product-layout pins, `series_check` |
| The 23 relics | each plays as the game's code says; differences from today named | `act1_relics.rs`, `red_skull.rs`, `game_turn_order.rs`, new `relic_entity.rs` |
| Turn order (turn-start-draw) | relic hooks in the pre/post-draw buckets as their trigger says | `game_turn_order.rs` |
| Codec | relic-free encodings unchanged; a relic state round-trips | codec tests + new round-trip |
| Fine-tunes | children of nets keep working | `test_warm_start.py` |
| Search speed | `series_speed` at most 10% slower | job (step 6) |

## When in doubt

Prefer the game's code over today's relic behavior, and an unchanged
relic-free fight over anything else.

## Scope

May change: the engine's state (`Player`), codec (a new optional
section), hooks (triggers, effects, condition), the hook runner, relics
(`relics.rs`, registry relic parse, key lists, element names), the
official writer, `content/relics.json`, `content/packs/act1-relics.json`,
`content/powers.json` (`RedSkull` unused again), `content/wording.json`,
`py/src/features.rs` (relic rows), the Python binding (relic counters in,
relic list out), tests, docs, facts.

Off limits: relic-free codec encodings; `golden.txt`; any existing net's
input in its layout; configs, yardsticks, controls; the gauntlet and run
layer; saved packs and data on disk.

## Decisions taken (owner, 2026-11-11; provisional)

- A relic is its own entity: a list on the player, each with hooks and a
  counter (owner chose this over powers marked "from a relic").
- Relic fights may change toward the game; game parity wins conflicts.
- The net reads relics as opt-in rows with their counter; relic id columns
  only in ids mode.
- At most 16 relics per fight.
- Out of scope: run layer, counters between fights, new relics, potions.

## Outside assumptions

- The game's relic classes and `AbstractRoom` / `GameActionManager` order
  (decompiled copies, `aeubanks/sts`), read per relic in step 4; each
  relic's test names its line.

## Verification

Written first (step 1, passing on unchanged code): `relic_free_pins` (codec
bytes and product-layout features on relic-free fights; the existing pins
may serve) and `relic_baseline` (each of the 23 relics' fight: states at
every decision for fixed seeds, recorded to diff against in step 4).

Then:
- `relic_list`: 16 relics hold, 17 is an error naming the relic; counters
  start at the given value.
- `relic_hooks_first`: a relic's turn-start hook runs before a power's.
- `combat_start_order`: `CombatStartPreDraw` before the opening draw,
  `CombatStart` after it, before the turn-1 post-draw hooks.
- `counter_effects`: SetCounter / AddCounter / CounterIs on a relic; an
  error on a power.
- `codec_relics`: relic-free bytes unchanged; a relic state round-trips.
- `relic_rows`: with the `relic` kind, a relic's rows carry `grant_relic`
  and `relic_counter`; without, none.
- Each moved relic against the game (`act1_relics.rs`, `red_skull.rs`):
  Red Skull's start, crossing and no-double-count cases.
- End to end: golden identical, `series_check` PASS, `series_speed` within
  10%, the explorer words relic hooks.

## Don't guard

Two copies of one relic (allowed: two entries, two counters); a relic in a
monster's start powers (not a thing); counters beyond `i16`.

## Build steps

1. **Pins** on unchanged code (`relic_free_pins`, `relic_baseline`);
   decisions into `docs/decisions.md`. Check: pass.
2. **State and codec:** relic ids, `Player.relics` (16, counters), the
   optional codec section, constructors take relic counters. No behavior.
   Check: `relic_list`, `codec_relics`, pins, golden.
3. **Relic hooks:** content format (`hooks`, `counter`, `powers`
   shorthand), the runner (relics before powers), `CombatStartPreDraw`,
   `CombatStart`, the counter effects and condition, key lists, wording.
   Check: `relic_hooks_first`, `combat_start_order`, `counter_effects`,
   guard, wording, pins.
4. **Move the 23 relics** off helper powers, each from its game class;
   Red Skull exact; the official `RedSkull` power unused. Check:
   `act1_relics.rs`, `red_skull.rs`, `game_turn_order.rs`, the diff
   against `relic_baseline` with every difference explained by a game line.
5. **The net:** the `relic` row kind, `grant_relic`, `relic_counter`,
   ids-mode relic columns; re-pin default-width pins (additive, checked by
   name). Check: `relic_rows`, product-layout pins, `series_check`.
6. **Speed and docs:** `series_speed` job (old: this spec's commit; new:
   step 5's), `docs/extending.md` (relics section rewritten), the relic
   inventory and its deviation notes, facts. Check: `series_speed` within
   10%.

## Build plan

6 steps, forks, Opus. Stop point: step 4, if a relic's game class needs a
trigger or effect the engine lacks (then it stays as today and is named,
or the step asks before adding it).
