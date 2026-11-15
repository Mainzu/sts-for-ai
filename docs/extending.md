# Extending the engine and the net

How new content and new mechanics are meant to enter this project, and
why. Settled with the owner on 2026-10-26. This is the concept; the build
plan was `docs/specs/rules-engine-upgrade.md` (the umbrella and its series
of specs, built) and the warm-start workflow (README "Fine-tuning on new
content (warm start)"); the idea is idea 51 in the owner's private tracker.
Read `docs/concept.md` first for how the engine and nets work today.

## The goal

Extending the engine and the net is a **workflow**: a repeatable process
with checks a program runs, like `/spec` and `/build`. Three tiers:

| Tier | What | Cost once the series is built |
|---|---|---|
| A | new content from existing atoms (most cards, monster moves) | data only; no engine code, no retrain |
| B | a new mechanic: a new effect, trigger, condition, keyword or target | an engine update plus a vocabulary append; every net saved under the contract still loads; the cost of teaching it is measured as a learning curve |
| C | a new entity kind (Defect's orbs, potions) | out of scope for now; the entity shape makes it a vocabulary entry later |

The fundamental limit: a net can't generalise to semantics it has never
seen. What the workflow does is make the rest of the net untouched by the
addition and make learning the new atom cost a few thousand games instead
of a retrain, and measure that cost.

## Rules

- **The engine takes data only. No scripting.** Content is rows the engine
  interprets; the atom vocabulary is closed and small; every control-flow
  shape (when, if, repeat, choose) is an atom or a decision-point kind the
  engine owns.
- **A choice is a decision between changes to apply.** Every option, play
  or choose, is "apply these rows", and the player picks among the
  resulting states (the afterstate principle, extended). A decision point
  is a descriptor (what for) plus candidates, each a label and its rows;
  data generates candidates from a source (a pile, potion slots, or an
  inline list) with a filter. Multi-select is a sequence of single picks
  plus Done. Play-then-target stays pre-combined. In-card decisions are
  always expanded, never leaves (a large draw before the pick in the same
  card is still a leaf, so the features carry the pending decision).
  Decisions come from cards only; one a power's hook raises (Well-Laid
  Plans at turn end) is deferred.
- **Information principle.** A random event is rolled at the moment its
  outcome becomes visible to the player, so no hidden value ever sits in
  the state and equality covers "what the player knows". The draw pile
  (rolled at the draw), the known top prefix (Headbutt, Scry) and Runic
  Dome (the move roll deferred to the monster's action) and a card
  shuffled into a pile with a known top (a *floater*: known card, unknown
  position, rolled at the draw) all follow it.
- **Self-describing numbers, never bare counters.** A card's per-copy
  state is its own numbers as modified (damage, block, magic, cost, with
  a lifetime), not a count of plays; the net already reads those columns.
  A power's counter is encoded inside the row that reads it as (current,
  threshold, effects), so the net reads progress toward a row firing, not
  a number whose meaning differs per power.
- **Amounts are expressions:** `base + k × quantity`, one quantity from a
  closed vocabulary (own block, Strength, energy spent, cards with a tag,
  stacks), replacing one-off primitives like Body Slam's (their columns
  stay, computed from the expression, so old nets stay exact). The net
  reads both the value resolved against the current state (its own
  column, `expr_value`, so old nets stay exact) and the form (base, k,
  quantity) beside it. Built 2026-11-02 (spec 2), with the X-cost keyword
  (X kept in the card-in-play stage) and Whirlwind as proving content.
- **Fractions and max HP** (`docs/specs/fractional-amounts.md`, built
  2026-11-11): an amount can carry a bottom, `per`, written `"k": "1/5"`
  (loaded in lowest terms; whole numbers stay plain numbers):
  `base + trunc(k × quantity / per)` in 32 bits, toward zero as the game's
  `(int)` cast (a negative fraction rounds toward zero by choice; no game
  amount has one). Stacks scale the top and keep `per` (`times(n)`), so n
  stacks resolve as `trunc(n × k × quantity / per)`, not n truncated
  amounts: 2 stacks of 1/5 at max HP 78 give 31, not 30. A `k` that isn't a whole number or an `"a/b"` string
  is a load error (`0.5` used to load as 0). `OwnMaxHp` reads the user's
  max HP, and `HealOf` heals by an amount resolved when it runs (capped at
  max HP, nothing at 0 HP), so Blood Potion's "heal 1/5 of your max HP" is
  `{"HealOf": {"base": 0, "k": "1/5", "of": "OwnMaxHp"}}`. Neither has a
  net column (heals have none by design); the net's `k` columns read k/per.
  Amounts fixed when a monster's intent is set (Hexaghost's Divider) are
  not amounts: idea 103 in the owner's private tracker.
- **Statics are rows** (spec 4, built 2026-11-02): "while it exists,
  change this number" (`hooks::Static`: modifies damage dealt, damage
  taken or block gained; adds per stack or a multiply; optional
  condition). The damage pipeline's order is base, adds, multiplies,
  round down once, then replacements (spec 5), then block. The five
  built-in modifiers keep a hard-coded fast path that a test checks
  against their rows; debuff countdowns are `RoundEnd` hooks.
  The condition `Holds {side, power}` reads a power held by the owner
  (`Owner`) or by the attack's other creature (`Opponent`; false where
  there is none, as in a card's shown damage): Paper Phrog's helper
  multiplies the player's damage by 7/6 against a Vulnerable monster
  (x1.75 in all), Odd Mushroom's the damage the Vulnerable player takes
  by 5/6 (x1.25); the game's float chain equals the rational product
  rounded once (docs/specs/blocked-relics.md step 2).
- **Replacements are rows** (spec 5, built 2026-11-02): "if X would
  happen to the owner, do Y instead" (`hooks::Replacement`: damage taken,
  HP loss or a debuff landing; cancel, cap, add or multiply; then effects
  on the power). Artifact and Intangible are such rows. A power can react
  to every attack hit on its owner (`OwnerAttacked`) and target the
  attacker (Thorns).
- **After block** (docs/specs/after-block.md, built 2026-11-12): four
  more replacement events change the amount once block is removed, one
  pass each in the game's `damage` order, each only while the amount is
  above 0 (so a fully blocked hit touches none): `DealtAfterBlock` (the
  attacker's rows, attacks only: The Boot), `TakenAfterBlock` (every hit
  and HP loss: Buffer), `AttackedAfterBlock` (attacks only: Torii),
  `HpLossLast` (every: Tungsten Rod). "Attacks" are `Damage` hits (the
  game's `NORMAL`); `PlainDamage` (`THORNS`) and `LoseHp` / Poison
  (`HP_LOSS`) run only the two "every" passes. The amount left is the HP
  lost, which the HP-loss reactions see. The action `{"AtLeast": n}`
  raises an amount below `n` to `n`; `"upTo": n` on any replacement row
  makes it apply only to amounts of at most `n`. The binding records
  whether a bound power has such a row, so other fights skip the passes.
- **Draws and HP dealt** (docs/specs/ironclad-last-four.md steps 1-2,
  built 2026-11-14): the replacement event `Draw` acts on each draw
  request as it is made (`Cancel`: no cards, no shuffle; a draw asked for
  before the power arrived still resolves). Pack power `NoDraw` (debuff,
  gone at its owner's turn end) makes Battle Trance. Quantity `HpDealt`
  is the HP the user's latest damage effect took, summed over targets and
  hits, each hit capped at its target's HP (the game's
  `lastDamageTaken`); Reaper is `Damage` to all, then `HealOf` it. When a
  card's effect wins the fight, the card's later `Heal` / `HealOf` rows
  still run (no hooks), as the game's `clearPostCombatActions` keeps a
  `HealAction`; its other rows don't.
- **Decision points are built** (spec 6, 2026-11-02): `Choose` / `Done`
  actions, a card paused at a pick (discard from hand, return from the
  discard pile), always expanded by search; card replay (Burst) with the
  `OwnerPlaysCard` trigger.
- **The known top is built** (spec 7, 2026-11-02): Headbutt puts a card
  on top, known; a card shuffled in under it is a floater at the game's
  odds; the net reads `next_draw` and `known_later` piles.
- **Monster move selection is data** (spec 9, 2026-11-02): pattern rows
  making today's random calls in today's order; a net can read each
  monster's possible next moves as `pattern` rows (opt-in, below).
  Reactions stay engine code for now.
- **Per-copy overrides are built** (spec 8, 2026-11-02): a copy with its
  own numbers is a variant card (Rampage's damage grows on that copy);
  Retain is a keyword. The general sparse state representation waits for
  spec 10.
- **Upgrades are data in the card's entry** (`docs/specs/card-upgrades.md`,
  built 2026-11-10): `"upgrade": {<path>: <change>}` beside the effects,
  a path naming one number or keyword (`cost`, `exhaust`,
  `effects.0.Damage.amount`, `rows.0.effects.1.Block`, `turn_end.0...`),
  a number's change added at each upgrade (a constant, or an expression of
  `n`, the level reached: integers, `n`, `+`, `*`), a keyword set from
  level 1; cost floors at 0. `"max_level"` defaults to 1 (`null`: as far
  as the numbers stay in range; Searing Blow reaches 252). `AddCard`'s
  `"match_level": true` adds the card at the played card's level (Anger).
  An upgrade that changes how a card works is its own entry, which the
  base names with `"successor": "<id>"` (True Grit, FTL, Armaments); the
  card at level 1 is still called `X+`, and the successor's own id binds
  to the same card. Older files' `X` / `X+` pairs link by the name. Cost `-1` is X, `-2` unplayable (read
  through `CardDef::cost()`, `x_cost()`, `unplayable()`); older files'
  flags and `X` / `X+` pairs still load. Level 0 and 1 are a card's id
  pair, level 2 and up per-copy variants named `X+<n>`. A general upgrade
  (the rest site, Armaments) raises a card one level, never a status;
  `sts.upgrade_name` and `sts.base_name` give the names.
- **Cards carry tags** (Strike, Shiv); conditions and filters reference
  tags, never names.
- **Pool or set.** A *pool* is a list the game itself draws from: a
  class's card pool by rarity, the colorless pool, the potion pool, the
  boss pool. A *set* is a list we choose for training or testing: a
  training set, a held-out set, the gauntlet's offer set. A list that
  copies a game pool whole is still that pool. Older docs and code call
  both "pool"; new writing uses the two words, and code names change
  when a change touches them. "Pooled" (statistics) is a different word.
- **Sets are a training decision, not content** (`docs/specs/card-sets.md`,
  built 2026-11-09): which cards a training draws from is a named list of
  base card names in `configs/card-sets.json` (`ironclad`, `silent`,
  `check9`, `proving`), compiled into the engine and read by Rust and
  Python alike (`card_sets::get`, `sts.card_set`). A card definition says
  only what the card is and does, so adding a card never changes a set.
  The sets file is not a rules file (not in the solved DB's fingerprint).
- **Two traps noted by an outside reviewer (2026-10-26), both taken.**
  Multi-pick choices: past the node cap a pick is still expanded (never a
  leaf) but only along its first option, since the transposition cache
  does not bound picks (DiscardToTop and HandToTop keep order;
  ReturnFromDiscard ranges over the discard pile). The draw after is a
  leaf, and a large draw before the pick remains a leaf; see the umbrella. The known top
  prefix: don't sum position-tagged cards into one pile; bucket by draw
  turn (next draw, known later), since order inside a hand is irrelevant.

## The contract with the net

- **Named input columns.** Every column of a batch has a name, including
  the scalars that are positional today. A saved net stores its names in
  order and the normaliser's mean and std per name. Loading maps by name,
  so reordering never breaks a net and new columns are invisible until
  fine-tuned. For inference the loader gathers the batch's columns into
  the net's saved order (bit-identical per forward pass; permuting or
  padding the weights would change floating-point summation order); the
  zero-padded wider layer is for fine-tuning.
- **Structure is vocabulary too.** Row kinds (rows a format change adds
  are dropped for nets that don't list their kind; the series' kinds
  `static`, `countdown`, `replacement`, `pattern`, `rule` and `relic` are written
  only for a net whose layout lists one, decisions "Series row kinds are
  opt-in"), the power dimension
  set (fixed by the vocabulary, not by whether a power has hooks), and
  named pile slots (a pile a net doesn't know folds into its parent).
- **What a format change costs.** New row columns (trigger names,
  conditions) leave saved nets alone (their layout leaves the columns
  out), but they move every pin recorded at the default width: contract
  pins and tiny nets, `golden_rows`, lookahead names, curriculum digests,
  `ARRAYS_PIN`, `TRAIN_PIN`, `relic_pins` and the default part of
  `card_rules_pins`. Before re-pinning, check by column name that old
  columns are equal and the new ones are zero (the new build encoding the
  fixed set with the old layout gives the old pins' bytes); each pin file
  says how to rewrite it. A new effect scalar widens
  every card and intent vector and breaks the contract tiny nets (they
  have no saved layout), so put a new number in an existing row column
  (`condition_param`) where one fits. A column dropped from the default
  keeps a legacy read for nets whose layout names it (`set_layout`), and
  fine-tuned children keep it (`finetune.keep_legacy_columns`).
- **Nets saved under the contract always load.** The guarantee starts with
  the `contract` spec; earlier nets with a known layout are converted
  into it once by a script, checked bit-identical (the curriculum's
  final net becomes the Ironclad parent for the learning curve). A
  schema version changes only on a rename or a meaning change of an
  existing column; removing a column is allowed (old nets read zeros
  there). A major version, if ever, is the one case that may drop nets.
- **Entity shape.** Player, monsters and cards (later orbs, potions) are
  encoded through one path: scalars, rows, position. Built-in modifier
  dimensions (Artifact included) stay beside their new rows so old nets
  load unaffected. Both forward passes (`scripts/stsnet.py`,
  `py/src/net.rs`) read the new batch.
- **Warm start.** Old weights load into the wider layer (equal to the
  gathered net within float tolerance on old states), fine-tuning mixes a
  share of the original datasets into every batch against forgetting, and
  a learning curve (warm-started
  effects vs warm-started ids vs fresh, at 0 / 500 / 2k / 10k new games)
  is the gate. That curve is the project's generalisation thesis measured
  directly, and the only training the engine series ever needs.

## Monsters

Monsters are entities already; what's missing is that move selection is
Rust. Move patterns as rows (move, weight, conditions such as turn, last
moves, HP band, phase; reactions as hooks; `Spawn` with a slot rule) make a
new monster data, and let the net read what a monster can do next, which
Runic Dome makes required rather than nice. Migrated monsters make
today's random calls in today's order, so the golden games stay identical
and every recorded game (datasets, the bench's decision and puzzle files)
stays replayable: a different sequence of calls would change all of them
at identical odds. The pattern format is today's call shape (ordered
rows over a two-deep window of executed moves, one lazy 0..99 roll, a
`chance(p)` pair as the repeat-limit alternative), so there is no
distributional fallback: the data gives the same result with the same
RNG, and the golden test proves it. Monster state gains one scalar,
`phase`. Every spec's Tests section copies the umbrella's per-spec
checklist.

## Relics

A relic is its own entity in a fight (docs/specs/relics.md, built
2026-11-10; docs/specs/relic-entity.md, built 2026-11-11): the player
holds a list of relics, each with its hooks and a counter, acting at the
game's times. It is a content entry: a pack's `"relics"` list, or the
official `content/relics.json` (Burning Blood, the Ironclad's starter
relic). Pack relics are named `gen:<id>`.

- **An entry** has `id`; `rarity` (`starter`, `common`, `uncommon`,
  `rare`, `boss`, `shop`, `event`; stored for later drops); `hooks` (the
  power hook format: trigger, condition, effects); `counter` (where the
  fight starts its counter, default 0, 16 bits); `powers` (official or
  pack powers, `{"power", "amount"}` as monsters' `start_powers`:
  shorthand for a first `CombatStart` hook applying each to the player, in
  order, the game's `atBattleStart` relics such as Vajra or Bronze
  Scales); `fights` (the fight kinds it acts in: `hallway`, `elite`,
  `boss`; all three by default); `win_heal` (HP added to the
  combat-end heal); `potion_potency` and `potion_slots` (see "Potions"
  and "Potions made in a fight"); `draw_per_turn` (cards added to every
  turn's draw, default 0, a negative value counts as 0; Snecko Eye has 2);
  the rules (`relics::RelicRules`, docs/specs/blocked-relics.md step 1):
  `x_bonus` (added to an X card's X when it resolves, not paid, 0 to 10;
  Chemical X 2), `keeps_energy: true` (unspent energy carries into the
  next turn; Ice Cream), `plays_per_turn` (no card, a Double Tap copy
  included, is playable once this many were played this turn, 1 to 99;
  Velvet Choker 6) and `keeps_hand: true` (the hand isn't discarded at
  turn end: retained and kept cards stay, ethereal ones exhaust, a card
  with a turn-end effect such as Burn goes to the discard pile; Runic
  Pyramid);
  `heal_scale` (`[numerator, denominator]`, default `[1, 1]`: every heal
  of the player, the saves' and the combat-end heal included, is
  multiplied and rounded half up, relics in list order; monsters' heals
  are not; Magic Flower has `[3, 2]`, the game's `onPlayerHeal`;
  `CombatState::player_heal`, `win_heal_scaled`, which the bound, the
  heuristic and the net's value input read; no net row column).
  The keys are `relics::RELIC_KEYS`; any other is a load
  error (guard: `relic_keys_guard`). A name keeps one set of hooks per
  process.
- **The list.** `Player.relics` holds up to 16 relics (`RELIC_CAP`), each
  a relic id and an `i16` counter, in the order given; a 17th is an error
  naming the relic. Monsters hold none. A relic whose `fights` skips this
  fight's kind isn't held. The starter relic is the character's built-in
  heal, not on the list; naming it again adds an entry (and its heal
  again). The codec writes the list as section 7 (names and counters),
  only when it isn't empty, so a fight without relics encodes byte for
  byte as before; solved-DB keys follow the codec.
- **Hooks.** For one trigger the player's relics run first, in list
  order, then the player's powers. A relic hook acts as a power hook with
  one stack (raw `Block`; a pre-draw `Draw` joins the draw). The effects
  are the power hooks' (Apply, Block, Draw, GainEnergy, damage, ...),
  acting as the player's; powers a relic applies are real powers, using
  the player's powers (any number, as the game's) and removable as in
  the game.
- **Combat start**, two triggers with the game's names: `CombatStartPreDraw`
  (`atBattleStartPreDraw`, before the opening draw; its `Draw` joins it)
  and `CombatStart` (`atBattleStart`, after the opening draw and the block
  reset, before turn 1's post-draw and turn-start hooks). Both run once.
  The player's powers may use them too; monsters' powers holding them do
  nothing.
- **The counter.** The effects `SetCounter(n)` and `AddCounter(n)` (scaled
  by the trigger's count, as by `CardExhausted`) change the hook's own
  relic's counter; they load only in a relic hook (in a power, card or
  monster move they are load errors), and `RemoveSelf` / `ReduceSelf`
  don't load there. The conditions `{"CounterIs": n}` and
  `{"CounterAtMost": n}` test it (false in a power hook or a card row);
  `"NotFirstTurn"` holds after the combat's first turn (Pocketwatch: its
  counter counts the cards played since the last post-draw, as the
  game's does, and draws 3 when it is at most 3 and not on turn 1). A once-per-fight flag of the game's is the
  counter (Lantern's `firstTurn`, Centennial Puzzle's `usedThisCombat`,
  Red Skull's `isActive`); Ancient Tea Set uses the game's values (-2
  after a rest, the file's default, then -1).
- **Writing a relic.** Each relic writes its hooks at the trigger its game
  class uses (decompiled `aeubanks/sts`, `relics/<Name>.java`):
  `atBattleStart` is `CombatStart` (Anchor's block lasts the turn, Bag of
  Preparation's cards join the opening hand, Mark of Pain's Wounds go to
  the draw pile after it), `atTurnStart` is `OwnerTurnStart` (Mercury
  Hourglass, Brimstone, the energy relics), `wasHPLost` is `OwnerLostHp`
  (Centennial Puzzle, Runic Cube), `onExhaust` is `CardExhausted`
  (Charon's Ashes), `onUseCard` with its action queued behind the card is
  `CardPlayed by Owner` (Shuriken, Kunai, Nunchaku). The table of the
  first 23 is in docs/research/act1-relics-potions.md "Relic entity"; each
  relic row there names its test.
- **HP crossing half** (docs/specs/red-skull-strength.md, built
  2026-11-11; the game's `isBloodied`): the trigger `OwnerBloodied` fires
  once when HP loss takes the owner from above half its max HP to at most
  half (`2 × hp <= max_hp`), right after the loss and before its
  `OwnerLostHp` reactions (as the game's `damage` calls `onBloodied`);
  `OwnerUnbloodied` fires once when a heal takes it back above half. Both
  work for the player and monsters; a killing hit fires neither. The hook
  condition `OwnerHpAtMostHalf` reads the same line. Red Skull is built on
  them as the game's class: its counter is `isActive`; `CombatStart` at
  half HP or below gives 3 Strength when not active (written before hooks
  took two conditions: the start adds 2 to the counter at half and then
  tests 2 or 3), `OwnerBloodied` gives 3 when not active, `OwnerUnbloodied` takes
  3 when active. It is real Strength, so Heavy Blade's multiplier and
  Limit Break count it. The official power `RedSkull` is no longer used
  (its id and net column stay).
- **More fight words** (docs/specs/fight-vocabulary.md, built
  2026-11-12):
  - A hook's `"condition"` may be a list of two that must both hold, at
    most one carrying a number (the row's one `condition_param`); a net
    row sets both condition columns (Pen Nib: an Attack at counter 9).
  - `{"OwnerBlockIs": n}`: the owner has exactly `n` block (Orichalcum,
    checked at turn end before the powers' block).
  - `OpponentDied`: the player's, when a monster reaches 0 HP and another
    still lives, after that monster's `OwnerDied` (Gremlin Horn).
  - `CombatWon`: the player's, once when the fight is won, before the
    combat-end heal; heals and counter changes only (Meat on the Bone).
  - A `DebuffApplied` replacement may name one official power
    (`"power": "Weak"`): it acts only on that power and before every
    unfiltered replacement, as the game checks Ginger and Turnip before
    Artifact. Relics hold no replacements, so Ginger and Turnip give the
    helper pack powers `GingerWard` and `TurnipWard`. A net row writes
    the filter as the condition column `Applying(<power>)`.
  - `GainMaxHp(n)`: max HP and HP up by `n` (Fruit Juice; no net column).
  - `DrawPicked`, right after a `Pick` in the same row: draws as many as
    it took (the stage's `hit` counts them; Gambler's Brew).
  - A relic hook on `CombatStart` or `OwnerTurnStartPostDraw` may `Pick`
    (one per hook): the pick opens once the pass has run
    (`Stage::RelicPick`, codec stage tag 10, only while open), the hook's
    rest runs after `Done`, then the player's turn (Gambling Chip). A
    second relic pick in the same pass is skipped (none loaded has two).
  - After block (docs/specs/after-block.md; the words in "After block"
    above): The Boot, Torii and Tungsten Rod give the helper pack powers
    `TheBoot`, `Torii`, `TungstenRod`; Fossilized Helix gives the game's
    `Buffer` (a pack power any pack can apply: one stack absorbs one
    unblocked hit or HP loss).
- **The player applied a power** (docs/specs/act1-singles.md, built
  2026-11-13): trigger `OwnerApplied`, the player's hooks (relics, then
  powers) when a power the player applied to a monster lands, after the
  replacements (an Artifact cancel doesn't land); `Target::Opponent` is
  that monster. The condition `{"Applying": "<power>"}` (an official
  power) picks the power; it loads under `OwnerApplied` only. The powers
  an `OwnerApplied` hook applies don't fire it again. Champion Belt:
  `Applying Vulnerable` -> Apply Weak 1 `Opponent`; its Weak lands at
  once (the game's after the card's other actions; no Act 1 card tells
  them apart). A net row writes the trigger column `OwnerApplied` and the
  condition column `Applying(<power>)`.
- **A potion was used** (docs/specs/blocked-relics.md step 4): trigger
  `OwnerUsedPotion`, the player's hooks (relics, then powers) once a
  potion the player used has resolved, picks included, before its
  exhausts' reactions (the game's `onUsePotion`). A potion that ends the
  fight still fires it, after the combat-end heal (the game's queued
  `HealAction` survives `clearPostCombatActions`). Fairy in a Bottle's
  save is no use. Its hooks may only heal or change a counter (load
  error). Toy Ornithopter: Heal 5. The net has no column for it: a row
  writes the "other trigger" column.
- **Debuffs removed** (blocked-relics step 4): effect `RemoveDebuffs`
  removes every power the actor holds that is a debuff at its stacks
  (the test Artifact uses: Weak, Vulnerable, Frail, Entangled, Confused,
  LoseStrength, negative Strength or Dexterity, ...; Flex's Strength
  stays). No net column. Orange Pellets: the counter as a 3-bit set of
  card types played this turn (Attack 1, Skill 2, Power 4; cleared at
  `OwnerTurnStart`), 12 two-condition `CardPlayed` hooks set the bits,
  and at 7 a last hook removes the debuffs and clears the set, so a
  second set in a turn fires again, as in the game.
- **Curses and unplayable cards** (blocked-relics step 6): card type
  `"Curse"` (never in a pool or upgraded, as statuses; the net's card
  vector has no Curse column: all four type bits 0 mark one). The
  curses an Ironclad run can hold are pack cards in
  `act1-colorless.json` (outside its pool; Pride, which nothing gives,
  is left out). Card keys for cards held in hand: `"other_played":
  [effects]` (each copy held runs them when another card is played,
  before that card's effects, not at turn-end plays; Pain: `LoseHp` 1)
  and the card rule `"plays_per_turn": n` (while held, no card once n
  were played this turn; Normality 3). Effects: `LoseHpOf` (an Amount;
  Regret: `HandCards`), `ApplyAsMonster` (an `Apply` that counts as a
  monster's for `skips_first_round`: Doubt's Weak, Shame's Frail last
  into the next turn), `AddCopy {n, pile}` (only in a card's
  `exhausted`: a copy of that card; Necronomicurse). Quantity
  `CardsOfType: <type>` counts hand, draw and discard (Du-Vu Doll at
  `CombatStart`). Power rule `"plays_unplayable": <type>` (below) with
  `exhausts_played` makes Blue Candle (Curse; plus a `CardPlayed`
  hook's `LoseHp` 1) and Medical Kit (Status); a played unplayable card
  costs 0 energy and counts as a card played.
- **Saved from death** (docs/specs/would-die.md, built 2026-11-12): when
  an HP loss leaves the player below 1 HP, HP goes to 0 and a save runs
  before the death counts: the first held potion with `"trigger":
  "OwnerDied"` is used up (Fairy in a Bottle), else the player's
  `OwnerDied` hooks run, relics first, each skipped once HP is 1 or more
  (Lizard Tail: counter -1, `CounterIs -1` -> `HealOf` 1/2 of `OwnMaxHp`,
  `SetCounter -2`; the run layer carries the -2). A save's heal works
  from 0 and heals at least 1; a relic's `OwnerDied` hook may only heal
  or change its counter (load error). If HP is still below 1 the player
  is dead, HP as it was (no-death mode keeps going below 0). A saved
  player's bloodied state moves once, from the HP before the loss to the
  HP after the save; the loss's `OwnerLostHp` reactions and the
  attacker's `OwnerAttackHit` hooks run after the save (`state.rs`
  `save_from_death`, `lost_hp`, `attack`). A triggered potion is refused
  by `is_legal` too, so `step` can't drink it. No codec, stage or net
  column: a monster's `OwnerDied` is the same moment, where nothing heals.
  - A pack power a relic applies in a pass first fires on the next pass,
    as a power's does: one the `powers` shorthand gives at `CombatStart`
    misses that `CombatStart` (no content power has one), and Pen Nib's
    power isn't spent by the Attack that gave it.
- **The combat-end heal** is an amount the fight holds (`win_heal` on the
  combat state): the starter relic's at the start, plus each given relic's,
  raised during the fight by the `WinHeal` effect. Every reader (the fight's
  end, the bounds, the heuristic, the net's value input) reads it from the
  state; the bounds cap it at max HP while a `WinHeal` effect may still
  fire. The codec writes it (tag 6) only when it differs from the
  character's default.
- **From Python** a fight is given relics by name or as `(name, counter)`
  (the counter it starts at instead of the file's): `sts.Combat(...,
  relics=)`, `sts.Combat.versus(..., relics=, group=)` (no encounter, so
  `group` names the fight kind; default hallway), and the `"relics"` key
  of an `sts.run` dict spec. `Combat.relics` reads the held list back as
  `(name, counter)` pairs, in order. Unknown names, pack powers past the
  free slots, more than 16 relics and more distinct `powers` entries than
  a creature holds are errors naming the relic.
- **The net reads relics** through the opt-in row kind `relic`: each held
  relic's hooks in the power row format at one stack, marked
  `grant_relic`, with the row-only columns `relic_counter` (its counter
  now), `counter_set` / `counter_set_to` (a `SetCounter` in the hook and
  its value) and `counter_add` (its `AddCounter`s); `CounterIs`'s value is
  in `condition_param`. In ids mode (no rows) the opt-in kinds add
  `relic_<name>` player columns instead: a count per official relic, pack
  relics in `relic_unknown`. The powers a relic applies reach the power
  columns as any power. A net whose layout lacks the kind or the columns
  gets the input it had before.
- **Known limits**, named; no recorded fight reaches them:
  - Strike Dummy keeps a pack power (`StrikeDummy`, a static
    `DamageDealt` modifier): relics have no static modifiers.
  - Philosopher's Stone's `onSpawnMonster` (+1 Strength on a spawned
    monster: Slime Boss's and the large slimes' splits) has no trigger;
    split slimes don't get it.
  - Battle-start order is list order. In the game, `addToTop`
    battle-start relics (Vajra, Clockwork Souvenir, ...) act before the
    opening draw and `addToBot` ones (Gremlin Visage, Anchor, ...) after
    it; here all run at `CombatStart`. It shows only in combinations such
    as Clockwork Souvenir with Gremlin Visage listed first.
  - With `turn1_pre_draw` (not the game's order) turn 1's turn-start
    hooks run before the draw, so before `CombatStart`: a power given by
    the `powers` shorthand first acts at a turn start on turn 2 there. A
    power given by a `CombatStartPreDraw` hook acts on turn 1 in both
    orders.
  - Readers that see power hooks only (review of the build): the net's
    `rate_*` columns (`agent::hook_rates`) and next-draw size
    (`features.rs` `next_draw_size`) leave relic hooks out, and
    `projected_leaf` can't tell a once-only relic hook (`CounterIs` then
    `SetCounter`) from a repeating one. The turn-start leaf and the heal
    bound (`can_heal`) do see relic hooks.
  - The agents' damage estimates (`agent::incoming_damage`, intents
    minus block) leave out the after-block passes (Torii, Tungsten Rod,
    Buffer), as they leave out the player's Intangible cap; the search
    and `projected_leaf` play the engine and see them.
  - The heuristic's hand-made Vulnerable factors (`heuristic.rs`: a
    Vulnerable monster's effective HP at /1.5, the player's later damage
    at +50% per Vulnerable round) don't see Paper Phrog (x1.75) or Odd
    Mushroom (x1.25); intents, the board, the lookahead and the search
    read the engine's damage and do.
  - `CapHp` (Preserved Insect, Neow's Lament) has no net column, as heals
    have none; the net sees the lower HP it leaves.
  - A counter a caller passes is taken as given: Red Skull started at 1
    above half HP stays 1 (the game resets `isActive` at battle start).
  - Ids-mode `relic_<name>` columns cover official relics only (Burning
    Blood today); the Act 1 pack relics all count in `relic_unknown`.
- The run layer (the gauntlet) doesn't hold or hand out relics yet, nor
  carries counters between fights (R2): that comes with the headline
  change once Act 1's content is mostly done.

## Potions

A potion is held in a fight and used as an action that isn't a card play
(docs/specs/potions.md, built 2026-11-12; the game's `AbstractPotion` and
`potions/<Class>.java`). It is a content entry: a pack's `"potions"` list,
or the official `content/potions.json` (empty today). Pack potions are
named `gen:<id>`. The Act 1 potions loaded are in
`content/packs/act1-potions.json`, and Colorless Potion in
`content/packs/act1-colorless.json`; the list and what each needs are in
docs/research/act1-relics-potions.md "Potions loaded".

- **An entry** has `id`; `rarity` (`common`, `uncommon`, `rare`; stored
  for later drops); `potency` (the game's number, 0 for none, the
  default); and `effects` or `rows` in the card row format (conditions,
  targets, picks, random hits; a pack power in an effect loads as
  `ApplyPack`). The written amounts are the potion at its potency: Fire
  Potion is `PlainDamage` 20 at potency 20, Blood Potion `HealOf` 1/5 of
  `OwnMaxHp` at potency 20 (percent). The keys are `potions::POTION_KEYS`;
  any other is a load error (guard: `potion_keys_guard`). An entry with no
  effects, and a row condition `CounterIs` (a potion has no counter), are
  load errors. `"trigger": "OwnerDied"` makes a potion that is never a
  legal action and is used up as the player would die (Fairy in a Bottle,
  "Saved from death" under "Relics"): effects only, each `Heal` or
  `HealOf` (load errors otherwise); Sacred Bark scales it; its net row's
  trigger column is `OwnerDied`, not `Potion(Use)`; the explorer says it
  can't be drunk.
- **Escape and `fights`** (docs/specs/act1-singles.md section 4, Smoke
  Bomb). `"Escape"` in a potion's effects is the user's: the fight ends as
  won (`CombatWon` hooks, the combat-end heal, `Stage::Over { won: true }`)
  with `CombatState.escaped` set (codec section 10; Python
  `Combat.escaped`), the monsters at their HP. The key `fights` is the
  relic's list of fight kinds, here "usable in", hallway and elite always
  named, boss optional: a fight tells only a boss fight from the rest. A boss fight
  has a boss kind in a slot (`MonsterKind::is_boss`: a kind in any `boss`
  encounter, worked out at load), or the mark `CombatState.boss_fight`
  (codec section 11), which `give_potions` sets when a slot holds a boss
  and a held potion isn't usable in one, as a split child takes the
  boss's slot. A potion not usable here is not a legal action.
- **The list.** `Player.potions` holds up to 5 (`POTION_CAP`), sorted by
  name so the same potions give the same state in any order; copies are
  kept; a 6th is an error naming the potion. A fight is built without
  potions and given them with `CombatState::give_potions`. The codec
  writes the list as section 8 (names, in order), only when it isn't
  empty, so a fight without potions encodes byte for byte as before.
- **Using one** is `Action::UsePotion { slot, target }` (codec action tag
  4). It is legal on the player's turn when no pick is open, at 0 energy
  too; copies give one action (the first copy's slot); a targeted potion
  gives one per living monster. The potion actions come after the card
  plays and before `EndTurn`. The potion leaves the list first, then the
  stage `Stage::UsingPotion` (codec stage tag 9) runs its rows as a card's
  run: conditions, random hits through chance events, picks that pause for
  Choose and Done (Elixir).
- **Not a card**: no energy, hand, pile or play count changes, and no
  card hooks fire (`OwnerPlaysCard`, `CardPlayed`). Its `Block` is raw (no
  Dexterity, no Frail). Fire Potion's THORNS damage and Explosive Potion's
  ownerless NORMAL damage are `PlainDamage`: no Strength or Vulnerable,
  and Curl Up, Angry and Plated Armor don't react. Curl Up block from
  other damage waits until the use ends, as for a card; a potion killing
  the last monster ends the fight as won. `can_heal()` reads held potions
  and the one in use.
- **Potency and Sacred Bark.** A relic's `potion_potency` (default 1, at
  least 1) multiplies potions: `CombatState::potion_multiplier()` is the
  highest among held relics, so two Barks double once, as in the game.
  Sacred Bark has `potion_potency: 2` (`content/packs/act1-relics.json`).
  A potion with potency 0 (Elixir) isn't scaled (`potion_scale`). Scaling
  goes through `potions::scaled_effect`, which also scales a pack power's
  `ApplyPack` amount and random hits. A scaled fraction multiplies before
  truncating (`times(n)` keeps `per`, under "Rules"), as the game's float does: Blood Potion under
  Bark heals `trunc(2 × max HP / 5)`, equal to the game's
  `(int)(maxHealth * 0.4F)` at every max HP 1-999 (`float_parity`).
- **Holding a potion is worth nothing.** The heuristic and every net give
  a held potion no value, so search uses a potion whenever its effect
  helps this turn (`potion_search_game`: holding Fire, Block and Elixir
  against Jaw Worm, it drinks all three and wins). A value for keeping one
  matters once potions carry between fights (P2).
- **From Python**: `potions=` on `sts.Combat(...)` and
  `sts.Combat.versus(...)`, and the `"potions"` key of an `sts.run` spec;
  `Combat.potions` reads the list back in order. `sts.Action.potion(slot,
  target=None)` builds a use (`kind` "potion", `Action.slot`); action text
  is `Potion:<slot>[@<target>]` and a recorded game with uses replays.
  `board()["player"]["potions"]` lists them; `render()` adds a `Potions`
  line only when potions are held. The explorer words a potion ("Name ·
  Rarity potion", its effects in card wording, its potency) and an action
  ("Use Fire Potion → Jaw Worm").
- **The net reads potions** through the opt-in row kind `potion`: one row
  per row of each held potion, trigger `Potion(Use)`, its condition,
  `grant_own`, its effects at their effective amounts (Fire Potion reads
  20, 40 under Bark) and the row-only column `potion_potency` (its
  effective potency). Sacred Bark's relic row (trigger `Potion(Use)`,
  `grant_relic`) carries `potion_potency` 2, so a start-state value can
  tell a Bark start from a plain one. In ids mode the opt-in kinds add
  `potion_<name>` player columns per official potion (none yet) and
  `potion_unknown`. The default rows gained the two columns
  `trigger_Potion(Use)` and `potion_potency`, zero in every fight without
  potions; a net whose layout lacks them gets the input it had before.
- **Known limits**, named:
  - Replays (`combat_of` in the scripts) pass a record's potions but not
    its relics, so a recorded Sacred Bark game doesn't replay its
    doubling.
  - No potion is used outside a fight; monsters hold none; Toy
    Ornithopter and throwing a potion away are out; Potion Belt's slots
    are in a fight only ("Potions made in a fight").
- The run layer (the gauntlet) holds no potions, drops none and carries
  none between fights (P2), so no headline score moves.

## Turn start

Built 2026-11-10 (`docs/specs/turn-start-draw.md`). A power hook acts at
turn start through one of two triggers, named after the game's own hooks
(its decompiled code is the parity source: `rooms/AbstractRoom.java`
around line 255, `actions/GameActionManager.java` around line 446):

| Trigger | Runs | Game's name | Official / Act 1 content |
|---|---|---|---|
| `OwnerTurnStart` | the owner's turn start, **before** the draw | `atStartOfTurn`, `atTurnStart` | Poison, Berserk, Flame Barrier's removal, Mercury Hourglass, Brimstone, the energy relics, Lantern, Ancient Tea Set |
| `OwnerTurnStartPostDraw` | the owner's turn start, **after** the draw | `atStartOfTurnPostDraw`, `atTurnStartPostDraw` | Demon Form, Brutality (the start-of-combat relics use `CombatStart`, see "Relics") |
| `CombatStartPreDraw` | once, before the opening draw (player only) | `atBattleStartPreDraw` | Snecko Eye (Confused); the counter resets of Gambling Chip, Art of War and Pocketwatch |
| `CombatStart` | once, after the opening draw, before turn 1's post-draw and turn-start hooks (player only) | `atBattleStart` | Anchor, Bag of Preparation, Bag of Marbles, Philosopher's Stone, Mark of Pain's Wounds, Red Skull, every `powers` shorthand |

- **Turn 2 on**, the player's turn: turn count up, cards played reset,
  block to 0, energy to 3; the `OwnerTurnStart` hooks (they run as the
  monsters' rolls finish); if the fight is over, it stops with no draw;
  the turn's draw (5, plus owed draws, plus each held relic's
  `draw_per_turn`, such as Snecko Eye's 2); the `OwnerTurnStartPostDraw` hooks;
  then the player acts. A `Draw` from an `OwnerTurnStart` hook joins the
  turn's draw as one chance event (drawing n then 5 gives the same hands as
  drawing n + 5, hand limit included). Cards a pre-draw hook adds to the
  hand take hand space before the draw.
- **Turn 1**, as the game does it: the opening draw (5, plus innate cards,
  plus the character's first-turn draw, plus each held relic's
  `draw_per_turn`), then the `OwnerTurnStartPostDraw`
  hooks, then the `OwnerTurnStart` hooks. That is the game's order for
  every hook that adds to the back of its action queue. The game's
  front-of-queue hooks (Brimstone's Strength, Lantern's energy) land before
  its opening draw, but they only add Strength or energy, which land the
  same on either side, so no hook carries a front-of-queue mark.
- **`turn1_pre_draw`** plays turn 1 like every later turn (`OwnerTurnStart`
  hooks, the draw, `OwnerTurnStartPostDraw` hooks). Turn 1 is played while
  the fight is built, so it is a constructor argument, not state:
  `sts.Combat(..., turn1_pre_draw=False)`, `sts.Combat.versus(...)`, the
  `"turn1_pre_draw"` key of an `sts.run` dict spec and the runner's
  `GameSpec`. Default off; the codec doesn't change.
- **Monsters** have no draw: at a monster's turn start its hooks of both
  triggers run in one pass, in power-slot order.
- **Readers.** `@tsl1` (`turn_start_leaf`) projects both triggers while a
  monster's roll is pending, and only `OwnerTurnStartPostDraw` once the turn
  has started (the pre-draw hooks have run). The plain search leaf stops at
  the first chance event after EndTurn: a monster's roll if one rolls
  (before the turn starts), else the turn's draw (after the pre-draw hooks,
  so their energy and block are in it). `@lcb1` (`leaf_clear_block`)
  zeroes a leaf's block only before the turn's reset (a monster's roll
  pending); past it the block is the new turn's own. The projected
  leaf and
  `hook_rates` count both as once-a-turn hooks; the net's features write
  both into the one `OwnerTurnStart` column (owner: the split is "mostly a
  logic thing for effects that specifically need cards in hand").
- **Two draws in one pass.** A random `Draw` requested while another is
  still pending adds to it (`request_draw` in `engine/src/chance.rs`, since
  docs/specs/fight-vocabulary.md): Gremlin Horn on two deaths from one
  Cleave draws 2, and turn 1's post-draw and pre-draw hooks, which run in
  one pass, draw both amounts. Before, the second replaced the first.

### Content-file versions

Every content file has `"version"`: 1 or 2; any other value, or none, is a
load error.

- **Version 2** (the official card, monster, power, potion and relic
  files; `act1-ironclad.json`, `act1-potions.json`, `act1-relics.json`
  and `act1-colorless.json` in `content/packs/`; `scripts/gen_content.py`;
  `act1-monsters.json` and `content/encounters.json` are version 1): the triggers mean
  the above, so a generated turn-start power runs before the draw.
- **Version 1** (every saved pack under `runs/` and `data/`, test data,
  and the writers that only write monster powers or no powers:
  `gen_enemy_pack.py`, `analysis/mutate_monsters.py`,
  `analysis/mutate_cards.py`): `OwnerTurnStart` reads as
  `OwnerTurnStartPostDraw`, today's meaning before the split, so old packs
  load and play unchanged; `OwnerTurnStartPostDraw` in a version-1 file is
  a load error. Saved files are never rewritten.
- **Cards, version 1 and 2** (spec `card-rules`): a version-1 card's
  `only_attacks_in_hand: true` reads as `"playable_if": {"HandAll":
  "Attack"}` and `false` as nothing; `playable_if` in a version-1 file is
  a load error. A version-2 card with `only_attacks_in_hand` is a load
  error naming `playable_if`.

## Costs 0 this turn

One copy of a card can cost 0 for the rest of the turn (docs/specs/act1-singles.md,
the game's `setCostForTurn(0)`). Piles are counts of card ids, so the mark
is held beside the hand: `CombatState.free_in_hand`, the marked ids with
copies repeated (at most 10), always within the hand's counts.

- **Marking**: a `Pick` into the hand (`ReturnFromDiscard`,
  `ReturnFromExhaust`) with `"free_this_turn": true` marks each card it
  puts there (Liquid Memories); a `CopyInHand` pick (Dual Wield) marks
  its copies when every copy of the picked card in hand is marked (the
  game's `makeStatEquivalentCopy` keeps `costForTurn`); engine code calls
  `CombatState::mark_free_in_hand(card)` (discovery). A copy is marked
  only when its cost now is above 0 and it isn't X-cost or unplayable.
- **Cost and play**: `cost_of` is 0 while a copy is marked; playing the
  card plays the marked copy. Every other way a copy leaves the hand
  (`hand_remove`: discard, exhaust, random exhaust) takes unmarked copies
  first. An upgrade keeps the mark on the upgraded copy; variant
  renumbering carries it. Turn end clears every mark.
- **Codec**: section 9, only when a card is marked; a pick's
  `free_this_turn` is bit 1 of its `exact` byte. Every other state encodes
  as before.
- **The net** doesn't see the mark: a marked card reads as a hand card at
  its base cost (as `cost` reads the base cost under Corruption).
- **Known limits**: True Grit's random exhaust never takes the marked copy
  while an unmarked one is in hand (the game picks any copy); a card that
  goes to the discard pile from a full hand isn't marked (the game keeps
  its 0 until turn end).

## Play the top card

`PlayTop { n, exhaust }` (docs/specs/act1-singles.md; the game's
`PlayTopCardAction`: Distilled Chaos, Havoc) in a card or potion row takes
the draw pile's top `n` cards, one chance event each (`TakeTop`: the card
by counts or from the known top, then a uniformly random living enemy as
its target when it takes one), reshuffling the discard pile in when the
draw pile runs out and stopping when both are empty. The taken cards wait
in `CombatState.top_queue` (at most 6) and play from its front once the
card or potion that took them has finished, each in full (its picks and
chance events too) before the next:

- free, counted as played, with every play hook (`OwnerPlaysCard`,
  `CardPlayed`); an X-cost card plays at the energy it was taken at and
  spends none;
- a card that can't be played then (unplayable, a failed `playable_if`, a
  forbidden type, or its target dead) goes to the discard pile unplayed
  and uncounted, or exhausts when it would;
- with `exhaust` (Havoc) it exhausts once played (`InPlay.exhaust`).

Because every card is taken before any plays, a card's own draws and
shuffles don't reach the cards behind it. Sacred Bark doubles `n` on a
potion. The codec writes the queue as section 12 and `TakeTop` as chance
tag 6, only while used; `InPlay.exhaust` is bit 1 of the copy byte. The
net reads queued cards in the `playing` pile slot.

## Pools and discovery

Built 2026-11-12 (spec `docs/specs/discovery.md`). A pool is a list the
game draws random cards from (see "Pool or set").

- **Pools**: a pack's `"pools": {"<name>": [card names]}`: official names
  or pack entry ids, each once, loaded before or in the pack; a pool
  named again with other cards is a load error. The Ironclad pool
  (`content/packs/act1-ironclad.json`) is the game's in-combat list, and
  a test (`engine/tests/discovery.rs`) checks it against the game's
  cards minus those that don't load yet: a newly loaded Ironclad card
  goes into it.
- **`Discover`** `{"pool", "type"?, "offer": 3, "copies": 1, "free":
  false, "skip": false}`, in a card's or potion's effects only: `offer`
  different cards of the pool (of `type`), every combination alike, as a
  chance event (`ChanceEvent::Offer`); then a pick (`PickKind::Offered`,
  engine-internal: `Choose` an offered card, `Done` with `skip`), or the
  card taken at once when one is offered without `skip`. The `copies`
  (scaled by a potion's potency) go to hand while it holds fewer than 10,
  else to the discard pile; with `free` each copy put in hand gets the
  "Costs 0 this turn" mark. The offer is held in `CombatState.offer`,
  sorted by card id, only while open.
- **Binding**: a fight binds every pack card its potions' and deck's
  `Discover`s can offer (and theirs) at level 0 when it is given them, so
  slots stay fixed for the fight; more pack cards than
  `registry::MAX_CARD_SLOTS` (about sixteen thousand since
  docs/specs/sparse-piles.md) is an error. `registry::CARD_SLOTS` (40)
  only names the slots that keep their old card ids.
- **Net and codec**: no column, no codec bytes: an open offer counts as
  generated content (`has_generated`), so such a state has no encoding;
  the net reads the card taken.

## Potions made in a fight

Built 2026-11-13 (docs/specs/act1-singles.md section 5; the game's
`potions/EntropicBrew.java`, `AbstractDungeon.returnRandomPotion`,
`relics/PotionBelt.java`).

- **Potion slots**: `CombatState::potion_slots()` is 3
  (`potions::BASE_POTION_SLOTS`, Ascension 0) plus each held relic's key
  `potion_slots` (default 0, at least 0). Potion Belt has
  `potion_slots: 2` (`content/packs/act1-relics.json`). A fight may still
  be given more potions than slots (up to `POTION_CAP`).
- **`ObtainRandomPotions`** `{"except": [pack potion ids]}`, in a pack
  potion's effects only (a load error in a card, a hook or the official
  file): one chance event (`ChanceEvent::RandomPotion`) per empty slot
  (slots, capped at `POTION_CAP`, less the potions held; the slot of the
  potion in use counts as empty), each giving one potion of its potion
  pool: the potions of the same pack file less `except`, by rarity 65/25/10
  (`potions::RARITY_WEIGHTS`), then alike within a rarity
  (`PotionPool::outcomes`). An `except` id that isn't a potion of the pack,
  or a rarity with no potion left (the game would draw forever), is a load
  error. Pools are interned (`potions::potion_pool`): the same lists give
  the same index. Entropic Brew is `ObtainRandomPotions` except
  `["Fruit Juice"]`, potency 0 (Sacred Bark doesn't change it).
- **Binding**: a potion with it brings every potion of its pool into
  `registry::bind_potions` (theirs too), so the pack powers they apply and
  the cards their `Discover`s offer are bound when the fight is given it:
  a Speed Potion or an Attack Potion it makes works. That is every pack
  card of the Ironclad pool (33), all bound in the fight (up to
  `registry::MAX_CARD_SLOTS`; the first 40 slots, `CARD_SLOTS`, keep their
  old ids).
- **Net and codec**: no column (the net reads the potions made); a pending
  random potion counts as generated content (`has_generated`), as an open
  offer does. Named limit: the potion pool is the loaded pack, not the
  game's 33, so potions that don't load yet never come and the odds within
  a rarity shift.


## Random work in hooks

Built 2026-11-13 (docs/specs/blocked-relics.md step 5; the game's
`relics/DeadBranch.java`, `MummifiedHand.java`, `WarpedTongs.java`).

- **Effects a hook may hold**: `MakeRandom` (no `match_level`: there is no
  card in play), `ZeroCostRandom`, `ZeroCostRandomTurn` and
  `UpgradeRandom`, in any relic's or pack power's hook, and a
  `PlainDamage` on `RandomOpponent` (Juggernaut's THORNS hit, the game's
  `DamageRandomEnemyAction`; docs/specs/ironclad-last-four.md step 4),
  owed as `OwedKind::Hit { amount }` (stacks read when owed) and paid as
  `ChanceEvent::PlainHit` among the living enemies (no roll for one).
  A hit owed while a card is in play waits until the card's effects have
  run (the game's `addToBot`), so it lands after the card's damage and
  before the reactions that damage queued (Curl Up's block). Other random
  effects (random hits, `ExhaustRandom`, `PlayTop`, `Discover` outside a
  relic's `CombatStartPreDraw`) are still a load error in a hook.
- **The queue**: a hook can't pause for a chance event, so its random
  work joins `CombatState::owed` (`Owed`, at most `OWED_CAP` kinds of
  work, `n` times each) in the order it was owed, scaled by the hook's
  stacks and times (k cards exhausted: k rolls). `run` pays it one roll
  or pick at a time before anything else goes on, after `cost_rolls`
  (each is its own chance event; one with a single outcome is made at
  once); a finished fight drops it. A hook's `Draw` while work is owed
  joins the queue behind it (the game's queued `DrawCardAction`:
  Brutality's draw comes after Warped Tongs' upgrade). Work owed while a
  relic's pick or offer is open (`wait`) is paid once that relic's hook
  has run (Gambling Chip before or after Warped Tongs, in relic order).
- **At turn end**: End Turn pauses at `Stage::EndingTurn` while owed work
  is paid: part 1 after the player's turn-end hooks (before the hand's
  turn-end acts and discard), part 2 after the turn-end exhausts' hooks
  (Dead Branch's card stays in the hand for the next turn, as in the game
  where the add is queued behind the discard), before the monsters act.
  Work owed during the monsters' turn is paid once it ends, before the
  next round's rolls.
- **`ZeroCostRandomTurn`**: one random unmarked hand copy costing above 0
  this turn gets the "Costs 0 this turn" mark (`ChanceEvent::RandomFreeTurn`);
  no fallback to marked copies (Madness's `ZeroCostRandom` has one).
- **`UpgradeRandom`**: one random hand copy a general upgrade can raise
  (not a status, below its max level) is upgraded
  (`ChanceEvent::RandomUpgrade`); a marked copy and an unmarked one of the
  same card are different outcomes, and a marked copy stays marked.
- **Pool `"Class"`**: `MakeRandom`'s pool in a relic's hook may be
  `"Class"`, the loaded pool named as the fight's character
  (`registry::fight_pool`; Dead Branch). With no such pool loaded (a
  Silent fight today) nothing is made. A card or power naming it is a
  load error: the deck is bound before the character is known.
- **Binding**: the pool cards a relic's hook can make are bound with the
  relic (`bind_relics`, given the character); those of every bound pack
  power's hooks (the deck's, a relic's or potion's or monster's, or one
  applied by any of those) are bound until nothing more is
  (`bind_discovered`).
- **Search**: an End Turn leaf (no sampling past the turn) samples the
  owed work at `EndingTurn` with the turn's luck (`sample_rng`) until the
  monsters have acted, so leaves stand where they do without the work.
- **Net and codec**: no net column (the net reads the hand it leaves).
  Codec: stage tag 12 (`EndingTurn`), pending tags 9 and 10, section 15
  for the owed entries; owed `MakeRandom` rolls count as generated
  content (`has_generated`), as a pending roll does.
- **Block gains**: `Trigger::OwnerGainedBlock` fires the player's hooks
  once per block gain above 0 (after Dexterity, Frail and the other
  modifiers; `add_block`, which every player block site goes through, the
  game's `addBlock`), not for a monster's gain, and not again for block
  its own hooks give.
- **Named limits**: Work a monster's hook owes is paid
  after the monsters' turn, not at once (no Act 1 monster owes any).

## Card rules

Built 2026-11-10 (spec `docs/specs/card-rules.md`). Rules a power or a
card sets on cards, enforced by the engine (`state.rs` `can_play`,
`cost_of`, `exhausts_played`) and readable by the net:

- **Power rules:** `"forbids": <type>` (its owner can't play cards of
  that type; Entangled: Attack), `"sets_cost": {"type", "cost"}` (its
  owner's cards of that type cost at most `cost`, 0 to 9; X-cost and
  unplayable cards unchanged; Corruption: Skill 0), `"exhausts_played":
  <type>` (a played card of that type exhausts; Corruption: Skill),
  `"plays_unplayable": <type>` (its owner's unplayable cards of that
  type can be played, for 0 energy; Blue Candle: Curse). Each takes any
  card type (Attack, Skill, Power, Status, Curse).
  Official powers' rules are read as a pack power's (none has one yet).
- **Power fields** (`registry::PowerRules`, the `power_field` family;
  the net reads none): `"debuff": true` (applying it is a debuff,
  Artifact blocks it; `LoseStrength` from Flex and `LoseDexterity` from
  Speed Potion are, as the game's, so with Artifact the gain stays), `"debuff_if_negative": true` (a negative amount
  is: Strength, Dexterity), `"can_go_negative": true` (its amount can go
  below 0 in the engine: Strength, Dexterity; the game's `canGoNegative`
  also marks Wraith Form, but the engine stores WraithForm with the
  opposite sign to the game's, the game's -n being the engine's +n, so it
  has no flag; without it, official or pack, a negative application is the game's
  `ReducePowerAction`: floored at 0, nothing when not held, no debuff and
  no `OwnerApplied` hooks), `"skips_first_round": {"from_monster":
  true}` / `{"on_monster": true}` (landing fresh, it skips the end of
  that round: the monster-applied duration debuffs; Ritual), and,
  official powers only, `"attack_shape": {"split": n}` (a monster
  holding it attacks with n times the hits at base / n: Split Hits), and
  `"block_loss": n` (the most block its owner, the player, loses at their
  turn start, 0 to 999; the fewest among held powers wins: Barricade 0,
  Calipers' helper `CalipersWard` 15). A
  hook row may carry `"hp_loss_source": "Any"` (the `hook_field`
  family): its `LoseHp` is someone else's doing, as Poison's, so
  `OwnerLostHp Card` hooks (Rupture) don't fire on it; the default is
  `Card`. An `OwnerTurnEnd` or `RoundEnd` hook (a power's or a relic's)
  may carry `"acts_first": true`: the game's `addToTop`, so it acts
  before the hooks its turn-end pass ran earlier (Regeneration heals
  before Combust's HP loss; Orichalcum checks for block before an earlier
  relic's). Several such hooks act last-called first. The player's End
  Turn runs in the game's stages: a first pass of the relics'
  `OwnerTurnEnd` hooks (`onPlayerEndTurn`) and the powers' marked
  `"before_hand": true` (`atEndOfTurnPreEndTurnCards`: Metallicize,
  Plated Armor); then the hand's `turn_end` cards (Burn, Decay, Doubt,
  Regret, Shame); then a second pass of the powers' other `OwnerTurnEnd`
  hooks (`atEndOfTurn`: Combust, Regeneration); then the discard. A relic
  hook is `before_hand` unless its row says `false`; a power's only when
  it says `true`. Every monster's turn end with the round's end is one
  more pass. Official and pack powers read the same fields; no power name
  is matched in code for them.
- **Card play condition:** `"playable_if": <condition>`, the hook
  condition syntax: the card is playable only while it holds. The one
  condition made for it is `{"HandAll": <type>}`, every card in hand is
  of that type (Clash: Attack). An unplayable card with `playable_if` is
  a load error.
- **Keys.** The registry lists the keys a power and a card may carry,
  each as structure, rules and the generator's own metadata (read by
  nothing in play): `POWER_STRUCTURE_KEYS`, `POWER_RULE_KEYS`,
  `POWER_META_KEYS` and the `CARD_` lists in `engine/src/registry.rs`; any
  other key is a load error. The rule keys are the `power_rule` and `card_rule` families
  of `element_names()`, so each needs words in `content/wording.json`;
  `scripts/tests/test_card_rules.py` (the guard) fails when a rule key has
  no words or gives no row.
- **Rule rows** (row kind `rule`, opt-in like `static`): one row per rule.
  The "trigger" column names the rule (`Rule(Forbids)`, `Rule(SetsCost)`,
  `Rule(ExhaustsPlayed)`, `Rule(PlayableIf)`); the condition column holds
  the card type (`CardType(<type>)`) or the play condition
  (`HandAll(<type>)`); a cost cap's cost goes in `condition_param` (an
  effect scalar would widen every card and intent vector, which nets
  without a saved layout read). Power rule rows go where a power's static
  rows go (held powers and the rows an `Apply` grants); a card's
  `playable_if` row goes on the card's own rows.
- **The legacy column.** `only_attacks_in_hand` is no longer a default
  card column. When a net's layout names it (every net saved before the
  spec, the product net and the headline control among them),
  `set_layout` turns it back on and writes 1 for a card whose
  `playable_if` is `HandAll(Attack)`, else 0, so those nets read what they
  did (`scripts/tests/test_card_rules_pins.py`, product layout).

## Checked against

Gremlin Leader, Darkling, Writhing Mass, Awakened One, Time Eater, Spire
Shield and Spear: all fit with six additive atoms (death replacement with a
downed state, `Spawn` with a random kind, monster tags, `RerollIntent`,
`EndPlayerTurn`, facing) and no format change. Table in the umbrella.

## The series

Ten engine specs, each built and tested alone, none training a net:
contract → (warm-start, scripts) → amount-expressions → entity-shape →
static-modifiers → replacement-hooks → decision-points (Survivor) →
known-top (Headbutt) → per-copy-overrides (Rampage) → monster-patterns →
runtime-registry. Specs 6-9 change the state shape; the solver database
is retired at each fingerprint change and refilled once after the series.
Recorded games stay replayable throughout, since existing content plays
identically in every spec (spec 6 keeps the Silent stand-in starter as
the default; spec 9 keeps today's random calls). Each spec measures
speed before and after on the harnesses its change can touch (check 4,
search games/s, net self-play games/s, nodes per decision): no more than
10% slower per spec, 25% over the series, node counts identical on
existing content; the umbrella has the per-spec table. Then Defect.
Order in `docs/specs/queue.md`; it starts after `curriculum`.

## Decisions (owner, 2026-10-26)

- Rung 4 (play-out averages): no for now; it needs its own spec.
- Each new mechanic may require an engine update; data-driven doesn't
  remove that and isn't meant to.
- X-cost spends all current energy: a card property and an effect source,
  not a decision.
- Per-copy card state is the card's own modified numbers, not a play
  count (Armaments upgrading a Rampage mid-fight keeps the accumulated
  damage).
- A counter is never a bare number to the net.
- Known top of the draw pile is in: Headbutt, hand-to-top and Scry need
  it. A card shuffled into a pile with a known top becomes a floater (a
  known card at an unknown position, rolled at the draw, carrying how many
  known cards are certainly above it so a later push stays exact), not a
  dissolved prefix, which would change the game's odds (after the review).
- Body Slam's, Heavy Blade's and Perfected Strike's columns stay,
  computed from their expressions: they are training-pool cards (after
  the review).
- Each spec checks the heuristic bit-identical on the fixed state set; it
  is the bootstrap player, calibrator and reference builder (after the
  review). It stays blind to new row kinds through the series; it learns
  one only when content using it enters the round-0 pool.
- The net reads an amount expression as both its resolved value (the
  damage column) and its form (base, k, quantity) as columns beside it.
- No spec in the series trains a net; the one learning-curve run comes
  after the proving cards exist. The load guarantee covers nets saved
  under the contract only.
- The engine upgrade is a series of specs, not one.
- Spec 1 ships a converter for pre-contract nets of a known layout; no
  Ironclad net is trained for the baseline.
- Spec 9 has no distributional fallback; patterns reproduce today's
  random calls, and a monster may carry an internal `phase` byte.
- Each spec's tests follow the umbrella's per-spec checklist.
- The exact Silent proving cards are unverified against the wiki; review
  at the interviews.
