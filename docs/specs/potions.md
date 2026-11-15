# Potions in a fight (P1)

Status: closed (2026-11-12, built and in use; owner-led; e5934e4..e4e2d84, landed on main at 716e21d/31907643; As built: docs/extending.md "Potions"; decisions "Potions, spec decisions").

The potion rows: `docs/research/act1-relics-potions.md`. Builds on
`docs/research/act1-relics-potions.md` "Potions" (the 33 potions, their
game classes and what each needs), on the relic entity
(`docs/specs/relic-entity.md`) and on `docs/specs/fractional-amounts.md`
(built first: `HealOf` by a share of max HP, for Blood Potion).

## Outcome

The player can hold potions in a fight and use them as the game does: a
held potion is a legal action that resolves its effects, and every Act 1
potion today's effects can write loads from a content file and plays as its
game class says. With Sacred Bark doubling them, and a net able to read held
potions (and Bark's doubling) as opt-in rows.

**How it moves the goals.** Act 1 (`decision/act1-finish`): about 20 of the
33 potions and Sacred Bark load and play. Goal 1: a designer writes a potion
in the card row vocabulary, and a net learns it by its rows. Fights without
potions, golden, the rules version and every existing net's input stay as
they are; the gauntlet holds no potions, so no headline score moves.

**Non-goals** (owner, 2026-11-11):
- P2, the run layer: carrying potions between fights, drops after combat,
  the shop, Neow, events. A fight takes the potions its caller gives.
- Potions still blocked on missing pieces: Attack, Skill, Power and
  Colorless Potion (P3 discovery), Distilled Chaos (C8), Gambler's Brew
  (R27), Liquid Memories (C5 cost change), Snecko Oil, Fairy in a Bottle
  (R23), Smoke Bomb (P5), Entropic Brew (P6), Fruit Juice (R32).
- Toy Ornithopter, Potion Belt (run layer), throwing a potion away.
- A value for holding a potion: the heuristic and existing nets give a held
  potion nothing, so search uses one whenever its effect helps (owner:
  "nothing for now"; it matters once P2 carries potions between fights).
- Choosers offering Sacred Bark (R2/P2).

## Behavior

### Holding potions

- `Player` holds up to 5 potions (`POTION_CAP`: the game's 3 slots plus
  Potion Belt's 2), as a list **kept in one fixed order** (by potion id) with
  no gaps (owner: "a sorted list"). Holding [Fire, Swift] and [Swift, Fire]
  is one state; drinking either copy of [Fire, Fire] reaches one state
  (AGENTS.md: lines of play are judged by the state they reach). More than 5
  is an error naming the potion. Monsters hold none. A fight built with no
  potions has an empty list.
- A fight is given potions by name: `sts.Combat(..., potions=)`,
  `sts.Combat.versus(..., potions=)`, the `"potions"` key of an `sts.run`
  dict spec, and the engine's fight constructors. `Combat.potions` reads the
  held list back.

### Using one

- **The action.** `UsePotion { slot, target }`: `slot` is the potion's
  position in the held list, `target` a living monster slot for a targeted
  potion (the card rule: an effect on `Opponent`, or a target condition),
  else none. It is legal at the player's turn when an action is awaited and
  no pick is open (the game doesn't let you drink during a hand select);
  also with 0 energy. Two copies of one potion give one action (the first
  slot), one per living target if targeted. In `legal_actions` the potion
  actions come after the card plays and before `EndTurn`.
- **Resolving.** The potion leaves the list first, then its effects run in
  order, stepping like a card's rows: row conditions, the chosen target,
  random hits through chance events, and picks (Elixir: exhaust any number
  of cards in hand) that pause for `Choose` / `Done`. Then the turn goes on.
- **Not a card.** A use is not a card play: no energy, no hand change, no
  `cards_played_this_turn`, no `OwnerPlaysCard`, `CardPlayed`, card-resolved
  or after-card hooks, no pile placement, no replays. Its `Block` is raw (the
  game's `GainBlockAction`: no Dexterity, no Frail), as a hook's is. Its
  damage is `PlainDamage` (the game's THORNS damage) where the game says so.
  How monster reactions to its damage and its HP loss count (a monster's
  `OwnerLostHp`, Curl Up's block) follow the game's code, checked per potion.
- **Ends.** A potion that ends the fight ends it (`check_over`), with no
  card bookkeeping.

### Potency and Sacred Bark

- A potion entry has `potency`: the game's number (`getPotency()`), default
  0 (none, as Elixir). Its effects keep their written amounts (Fire
  Potion's 20); a test checks that each Act 1 potion's written amounts equal
  its potency (owner: written amounts, option 2).
- Sacred Bark is a relic with `potion_potency: 2` (a new relic field,
  default 1). While the player holds it, a potion with potency > 0 runs its
  effects at twice their amounts (the same scaling a power's hook gets per
  stack) and its potency reads doubled. A potion with potency 0 is
  unchanged.

### Content format

- A potion entry (`content/potions.json` official; a pack's `"potions"`
  list, named `gen:<id>`) has `id`, `rarity` (`common`, `uncommon`, `rare`),
  `potency` and `effects`, its effects in the **card row format** (owner:
  card rows), so targets, conditions, picks and random hits work as on
  cards. Pack potions may name pack powers loaded before them. The key
  lists and the guard test cover the new keys; wording covers potions (the
  explorer words them).
- The Act 1 potions go in `content/packs/act1-potions.json` (several need
  pack powers, as the relics did); Sacred Bark joins
  `content/packs/act1-relics.json`.

### The potions this spec loads

From the research table, each read from its game class: Blood Potion
(`HealOf` 1/5 of `OwnMaxHp`, potency 20; the research doc's "sources
disagree" note is settled by its game class), Elixir, Heart of
Iron, Block, Dexterity, Energy, Explosive, Fire, Strength, Swift, Weak,
Fear, Flex, Speed (with a LoseDexterity pack power), Regen (a pack power
healing per stack at turn end, then one less: `Heal` exists now), Ancient,
Liquid Bronze, Essence of Steel (the Plated Armor pack power), Duplication
(a pack power replaying the next card this turn), Cultist; Blessing of the
Forge if an effect upgrading every card in hand for the combat exists
(else it is named blocked). One the build finds it can't write stays out
and is named with what's missing.

### State and codec

The held list lives in the fight state. The codec writes it as a new
optional section (8), only when the list is not empty, so a fight without
potions encodes byte for byte as today; the potion-use stage gets its own
stage tag; the action takes the reserved action tag 4 (`slot`, `target`).
The solved database stores option actions through the codec and keys
states by codec bytes, so it follows.

### Search, agents, bounds

- Search sees potion actions through `legal_actions`, as any action (merged
  by afterstate). `greedy_action` keeps choosing among card plays only.
- `can_heal` includes held potions' effects (Regen), so the score's upper
  bound stays sound.
- The heuristic and the turn-start and projected leaves don't read potions
  (held potions are worth nothing; see non-goals).

### The net (opt-in)

A new opt-in row kind `potion`: each held potion writes one row with its
effects in the columns a card's effects use, at its **effective** amounts
(doubled under Sacred Bark), a row-only column `potion_potency` (its
effective potency), and in ids mode only a `potion_<name>` column per known
official potion (pack potions in `potion_unknown`). Sacred Bark's relic row
carries a row-only `potion_potency` column (2). A net whose layout lacks the
kind or the columns gets the input it had before; default-width pins move
by added zero columns only (`docs/extending.md` "What a format change
costs"). No new effect scalar: the card vector's width stays.

### Python and scripts

`PyAction` gets kind `"potion"` (slot, target) and a constructor;
`sts.action_name`, the action label and `render` name it ("Potion:1@0"
style, `scripts/action_text.py`'s reserved form); `action_text` encodes and
decodes it (its `NotSupported` goes); the explorer offers and words potion
actions and held potions; replays of recorded games with potion actions
play.

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden, rules version | byte-identical, unchanged | golden |
| Fights without potions | byte-identical states, codec bytes, legal actions | `codec_golden`, `relic_baseline`, pins |
| Existing nets | byte-identical inputs in their layouts; `series_check` PASS | product-layout pins, `series_check` |
| Search and solver | potion-free node counts and results unchanged | `relic_baseline`, search tests, solvedb tests |
| Recorded games and action text | old records replay; `Potion:` parses and now decodes | `test_contract` (its NotSupported case changes to a decode) |
| Card triggers | a potion use fires none of them | new `potion_not_a_card` |
| Relics | Sacred Bark doubles; other relics unchanged | `act1_relics.rs`, new `sacred_bark` |
| Bounds | upper bound sound with a healing potion | new `potion_heal_lifts_the_bound` |
| Fine-tunes | children of nets keep working | `test_warm_start.py` |
| Search speed | `series_speed` at most 10% slower | job (step 7) |

## When in doubt

Prefer the game's potion code over convenience, and an unchanged
potion-free fight over anything else.

## Scope

May change: the engine's state (`Player`, a potion-use stage, the action),
codec (section 8, a stage tag, action tag 4), the effect runner (stepping
a potion's rows), potions (a new module beside relics), the registry
(potion parse, key lists, element names), relics (`potion_potency`),
bounds (`can_heal`), the solved database's action rows, `content/potions.json`
(new), `content/packs/act1-potions.json` (new), `content/packs/act1-relics.json`
(Sacred Bark), pack powers those need, `content/wording.json`,
`py/src/features.rs` (potion rows), the Python binding and `render.rs`,
`scripts/action_text.py`, the explorer, tests, docs, facts.

Off limits: potion-free codec encodings; `golden.txt`; any existing net's
input in its layout; configs, yardsticks, controls; the gauntlet and run
layer; saved packs and data on disk; card vectors' width.

## Decisions taken (owner, 2026-11-11; provisional)

- Potions in the fight only; the gauntlet holds none (P2 later).
- Game parity wins conflicts.
- Sacred Bark is in scope.
- Holding a potion is worth nothing for now; nets can read potions as
  opt-in rows.
- A potion is written in the card row format.
- Held potions are a list in one fixed order, at most 5; copies give one
  action.
- `potency` is the game's number, 0 for none; effects keep written amounts;
  Sacred Bark (`potion_potency: 2`) runs potions with potency > 0 at double.
- The net's potion rows show effective amounts and potency (Fire Potion
  reads 40 under Bark), and Bark's relic row shows `potion_potency`, so a
  start-state value can tell a Bark start from a plain one (owner: the run
  decision-maker must be able to value Bark).

## Outside assumptions

- The game's potion classes (decompiled, `aeubanks/sts`, `potions/*.java`)
  and `AbstractPotion`: potency values, `isThrown` / `targetRequired`, raw
  block, Sacred Bark's `getPotency` doubling, which potions have potency 0.
  Checked per potion in step 5, each test naming its class.
- The game allows drinking only on the player's turn and not inside a hand
  select (`AbstractRoom` / `PotionPopUp` checks). Checked by step 3's
  legality test against the class lines.

## Verification

Written first (step 1, passing on unchanged code): the potion-free pins
(`codec_golden`, `relic_baseline`, the product-layout pins; add any missing
legal-action pin for potion-free fights), and the `test_contract` potion
cases as they stand.

Then:
- `potion_list`: 5 potions hold, 6 is an error naming it; [Fire, Swift] and
  [Swift, Fire] give equal states; `Combat.potions` reads them back.
- `codec_potions`: potion-free bytes unchanged; a state with potions and
  one mid-use (paused in Elixir's pick) round-trips; action tag 4
  round-trips.
- `potion_actions`: Fire Potion against two monsters gives two actions;
  [Fire, Fire] gives the same two; none during a pick; legal at 0 energy;
  after the card plays, before `EndTurn`.
- `potion_not_a_card`: Block Potion with Dexterity 2 and Frail gives 12;
  no `OwnerPlaysCard` / `CardPlayed` hook fires (a Rage-like power and a
  monster card-played hook unchanged); `cards_played_this_turn` unchanged.
- `potion_pick`: Elixir pauses for Choose/Done, exhausts the chosen cards,
  returns to the player's turn.
- `potion_ends_fight`: Fire Potion killing the last monster ends the fight
  as won.
- `sacred_bark`: Fire Potion deals 40 with Bark, 20 without; Elixir is
  unchanged with Bark.
- `potency_matches`: each Act 1 potion's written amounts equal its potency
  (Blood Potion: its share, 1/5, is potency 20 percent).
- `blood_potion`: heals 16 at 80 max HP, 32 with Sacred Bark (the game's
  doubled potency 40 percent).
- `float_parity` (fractional-amounts' test) also covers 2/5, Blood Potion
  under Bark: `trunc(m × 2 / 5) == (m as f32 × (40.0 / 100.0)) as i32` for
  max HP 1-999; a max HP where they differ is named and the step asks.
- `potion_heal_lifts_the_bound`: Regen Potion held at HP 30 of 80:
  `can_heal()` true.
- Each Act 1 potion against its game class (a new `act1_potions.rs`).
- `potion_rows`: with the `potion` kind, a held Fire Potion's row reads 20,
  and 40 with Bark, with `potion_potency` 20 / 40; without the kind, none;
  Bark's relic row carries `potion_potency` 2.
- `action_text`: `Potion:1@0` encodes and decodes; a recorded game with a
  potion use replays.
- End to end: golden identical, `series_check` PASS, `series_speed` within
  10%, a search game with Fire, Block and Elixir held uses them and wins
  against Jaw Worm, the explorer words a potion and its action.

## Don't guard

Two Sacred Barks (they double once, as in the game; not guarded);
potions on monsters; potions outside a fight; potency beyond `i16`.

## Build steps

1. **Pins** on unchanged code; decisions into `docs/decisions.md`. Check:
   pass.
2. **Potions as content and state:** potion ids, the potion entry parse
   (`content/potions.json`, a pack's `"potions"`), key lists, wording,
   `Player.potions` (5, fixed order), the fight constructors, codec section
   8, Python `potions=` in and `Combat.potions` out. No action yet. Check:
   `potion_list`, `codec_potions` (held part), guard, wording, pins.
3. **The use action in the engine:** `Action::UsePotion`, legality, the
   potion-use stage stepping rows (targets, picks, random hits) without card
   bookkeeping, raw block, `check_over`, codec stage tag and action tag 4,
   the solved database's action rows, `can_heal`. Check: `potion_actions`,
   `potion_not_a_card`, `potion_pick`, `potion_ends_fight`,
   `codec_potions`, `potion_heal_lifts_the_bound`, solvedb tests, pins.
4. **The action in Python and scripts:** `PyAction` kind and constructor,
   `action_name`, label, `render`, `action_text` encode/decode, the
   explorer's actions and wording, replay. Check: `action_text` tests, the
   `test_contract` potion case, explorer tests (the four failing on main
   too stay as they are), a replayed record.
5. **The Act 1 potions and Sacred Bark**, each from its game class, in
   `content/packs/act1-potions.json` (with the pack powers they need) and
   Bark in `act1-relics.json`; `potion_potency`. Check: `act1_potions.rs`,
   `sacred_bark`, `potency_matches`, `blood_potion`, `float_parity` at 2/5; the potions that stay out named in the
   research doc.
6. **The net:** the `potion` row kind at effective amounts,
   `potion_potency` on potion rows and Bark's relic row, ids-mode columns;
   re-pin default-width pins (additive, checked by name). Check:
   `potion_rows`, product-layout pins, `series_check`.
7. **Speed and docs:** `series_speed` job (old: this spec's commit; new:
   step 6's; ~12 min, long run), `docs/extending.md` (a Potions section),
   the research doc's potion rows, facts. Check: `series_speed` within
   10%; the end-to-end search game.

## Build plan

7 steps, forks, Opus. Stop points: step 3, if a picking potion needs the
card stage reshaped beyond a parallel potion stage (ask before reshaping);
step 5, if a potion's game class needs a trigger or effect the engine
lacks (then it stays out and is named, or the step asks before adding it).
