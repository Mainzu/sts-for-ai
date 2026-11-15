# Act 1 inventory: relics and potions against the engine

Step 4's opening read of `lane/act1-content` (2026-11-09, lane worker),
written the way step 1 was for monsters and cards
(`docs/research/act1-inventory.md`). No engine change. A code read of this
worktree at c3730f4 and of sts_lightspeed `master` at 7476a81 (2024-08-10).

**Against the charter and the survey.** `lane/act1-content` (rev 8) and
`docs/research/relics-potions-survey-2026-11-09.md` (written the same day,
in parallel, from the agent's knowledge) name the atoms differently; this
file's labels are its own. The charter's R1 (a relic kind as a permanent
player power plus the run's relic list) is this file's R1 with R2; the
charter's R2 (a counter carried across fights) is this file's R4; the
charter's P1 (potion slots and the reserved UsePotion action) is this
file's P1 with P2; the charter's P2 (choose-a-card) is this file's P3
discovery. Counts differ: the survey counts 109 relics, this file 141 (the gap
isn't reconciled entry by entry; this file includes the full shop and boss
pools, 10 event relics and each Face Trader face); both count 33 potions. Where the two
disagree on an effect, this file's line comes from sts_lightspeed's code
and the survey's from memory.

Sources:
- **The engine**: `engine/src/hooks.rs` (Trigger, Condition, Static,
  Replacement), `effects.rs` (Effect, Quantity), `registry.rs`
  (`load_pack`, `parse_power`, `parse_hook`, `parse_effect`, `condition`,
  `element_names`), `state.rs` (turn start, combat end), `character.rs`,
  `powers.rs`, `codec.rs`, `content/powers.json`,
  `content/packs/act1-ironclad.json`; the run layer in
  `scripts/gauntlet.py`, `scripts/run_value_unit.py` and
  `scripts/action_text.py`.
- **sts_lightspeed** (gamerpuppy, C++): the pools in
  `include/constants/RelicPools.h` and `Potions.h` (the task names
  `RelicIds.h` and `PotionIds.h`; on master the files are `Relics.h` and
  `Potions.h`), the fight effects in `src/combat/BattleContext.cpp`,
  `Player.cpp`, `Monster.cpp`, `include/combat/Player.h` and
  `BattleContext.h`, the out-of-combat effects, Neow and events in
  `src/game/GameContext.cpp`, `Deck.cpp` and `Shop.cpp`.
- **The wiki** (slaythespire.wiki.gg): its `Relics` and `Potions` list
  pages. They give names, rarities and patch notes but no effect text, so
  the wiki confirms the lists and two numbers (below), not the effects.

Numbers are the game's at Ascension 0, as sts_lightspeed codes them. Where
it doesn't code an effect (marked **unverified**), the number is the game's
card text as I know it. Where the sources disagree:
- **Blood Potion**: the wiki says it heals 20% of max HP since Patch 2.0
  (an older note says 25%). sts_lightspeed heals 40% without Sacred Bark and
  20% with it (`hasBark ? 20 : 40`), which looks inverted. 20% is used here.
- **Snecko Oil**: the wiki's patch notes say "draws 3 cards (Patch 34)";
  sts_lightspeed draws 5. Settled at 5 by the decompiled class
  (`potions/SneckoOil.java` 42 in Li-Binghui/MySlayTheSpire, `getPotency`
  returns 5; aeubanks/sts alike; 2026-11-13).
- sts_lightspeed doesn't implement Smoke Bomb, Mummified Hand or Toy
  Ornithopter (`// todo` or no code), and marks Blood Vial `// todo not
  correct`.
- sts_lightspeed applies Brimstone both at battle start and at every turn
  start (`BattleContext.cpp` 126, `Player.cpp` 497). The game's text is "at
  the start of your turn" only, so turn 1 may get it twice in
  sts_lightspeed (**unverified** which is right).

Classes (as in step 1, adapted to two layers):
- **present**: the engine has it today (as code or as a power);
- **writable**: its whole effect is a fight effect, and it can be written as
  a pack power with today's triggers, conditions and effects once the base
  relic atom R1 exists (for potions: P1);
- **writable, out-of-combat part blocked**: its fight part is writable as
  above, and a part outside the fight needs a run-layer atom;
- **blocked**: its fight part needs a missing atom;
- **out of combat only**: it acts only in the run layer (map, rewards, rest,
  shop, events) and needs a run-layer atom;
- **no effect**: nothing to express.

A "writable" here is a reading of the vocabulary, not a load: the step that
writes the entries loads each one in a test.

## What the engine has

- **No relic type.** `engine/src/` has no relic: case-insensitive search
  finds "relic" only in comments: `character.rs` line 1 ("starting HP,
  starter deck, card pool and relic") and the doc comments on
  `Character::Ironclad` and `Silent`; `powers.rs` 55 (`RedSkull`, "the Red
  Skull relic as a power; no card grants it"); `hooks.rs` 149
  (`OwnerHpAtMostHalf`, "Red Skull").
- **Starter relics are character code.** Burning Blood is
  `Character::win_heal()` (6, `state.rs` `BURNING_BLOOD_HEAL`), added on a
  won combat in `state.rs` (the `Stage::Over` branch) and read by
  `bound.rs`, `heuristic.rs` and `py/src/lib.rs`, `net.rs`. Ring of the
  Snake (Silent) is `first_turn_draw()` (2).
- **Potions are only reserved.** `codec.rs` reserves action tag 4
  `UsePotion` ("Reserved, not written yet"). `scripts/action_text.py`
  parses `Potion:<slot>[@target]` and raises `NotSupported` on replay. There
  is no potion slot, potion list or use. (At c3730f4; P1 is built since
  2026-11-12, docs/specs/potions.md: `UsePotion` is action tag 4 and
  `action_text` replays it.)
- **The player starts every fight with no powers.** Monsters have
  `start_powers` and `start_block` (`monsters.rs` 168, `registry.rs` 937);
  the player has neither. A pack power reaches the player only when a card
  applies it.
- (At c3730f4, for the three relic bullets above; R1 is built since
  2026-11-10 and the relic entity since 2026-11-11, see "R1 as built" and
  "Relic entity": `engine/src/relics.rs` holds `RelicSpec` and `Relics`,
  the player carries `relics` (`state.rs`), Burning Blood is data in
  `content/relics.json` (`win_heal` 6, which `Character::win_heal` reads),
  and a relic's `powers` give the player powers at combat start.)
- **Turn start order** (`state.rs`, `Stage::StartTurn` then `TurnStarted`):
  `turn += 1`, `cards_played_this_turn = 0`, block to 0, energy to
  `ENERGY_PER_TURN` (3, a constant), draw 5 (+ owed draws, + innate cards
  on turn 1), then the player's `OwnerTurnStart` hooks. So a hook at turn
  start runs after the draw and after block is reset: a turn-1 `Block 10`
  lasts the turn (as Anchor's combat-start block does), and a turn-1 `Draw`
  adds to the opening hand. (As read; since the turn-start split, below,
  `OwnerTurnStart` runs before the draw and `OwnerTurnStartPostDraw`
  after.)
- **Vocabulary a relic or potion can use** (`element_names()`):
  - triggers: `OwnerTurnStart`, `OwnerTurnEnd`, `CardPlayed` (Owner/Opponent),
    `OwnerLostHp` (Attack/Card/Any), `OwnerDied`, `RoundEnd`,
    `OwnerAttacked`, `OwnerPlaysCard`, `OwnerAttackHit`, `CardExhausted`,
    `CardDrawn` (Status only);
  - conditions: `Always`, `CardType`, `TargetIntendsAttack`, `TargetHas`,
    `CardsPlayedThisTurnBelow`;
  - statics: `DamageDealt`, `DamageTaken`, `BlockGained`, with Add or
    Multiply, under `Always`, `CardInPlayTagged` (Strike, Shiv) or
    `OwnerHpAtMostHalf`;
  - replacements: `DamageTaken` (before block), `HpLoss` (`LoseHp`, Poison),
    `DebuffApplied` (every debuff, no filter by kind), with Cancel, Cap, Add
    or Multiply;
  - effects: `Damage`, `PlainDamage`, `Block` (raw in a hook), `Draw`,
    `GainEnergy`, `LoseHp`, `Apply` (official powers in hooks; a hook may
    not apply a pack power), `ApplyOf`, `AddCard`, `Pick`, `ReplayCard`,
    `RemoveSelf`, `ReduceSelf`, `RandomDamage`, and the rest. Picks and
    random effects run only while a card resolves (`runs_outside_a_card`).
- **No max HP, gold, curse or cost-change effect.** `CardType` has no
  Curse (Attack, Skill, Power, Status). (Corrections after R1: `Effect::Heal`
  exists since 2b9c918, fickle-enemy step 1, see "R1 as built";
  `Effect::GainMaxHp` since 94d7f9b4, fight vocabulary (Fruit Juice);
  `Effect::RandomizeCost` since 1ce482e8, sparse-piles (Snecko Oil, Snecko
  Eye). Gold and curses are still missing.)
- **Out-of-combat hooks in the run layer** (`gauntlet.run`): a fixed
  11-floor chain (3 easy, 2 hard, elite, 2 hard, elite, hard, boss) with HP
  carried; `reward` (3 card offers after each won fight before the boss,
  more after elites with `elite_offers`); `rest_hook` (before the boss: heal
  30% of max HP or upgrade a card by name); `mid_rest` (a heal after floor
  K); `remove_hook` (one removal after the first elite's reward, "a shop
  proxy"); `path_hook` (fight the elite or a hard hallway instead). Max HP
  is one number per run (`MAX_HP = 80`). No gold, shop, potions, relics,
  events, chests, ? rooms, map choice, Neow or curses. Pack cards carry
  their upgrade in their pack entry since C6 ("Block C6 as built" in
  act1-inventory.md), so `upgrade()` upgrades them through
  `sts.upgrade_name` too (`gen:Searing Blow+` -> `gen:Searing Blow+2`) once
  the pack is loaded.

## Counts

How many relics and potions load and what blocks each missing one is in
docs/INDEX.md "Act 1 coverage" (generated from
docs/research/act1-missing.json and content/). The counts below are the
opening read's (2026-11-09), before any relic or potion loaded.

- Relics: 1 starter, 33 common, 30 uncommon, 28 rare, 22 boss, 17 shop (the
  Ironclad pools of `RelicPools.h`, with Red Skull, Paper Phrog,
  Self-Forming Clay, Magic Flower, Charon's Ashes, Champion Belt, Black
  Blood, Mark of Pain, Runic Cube and Brimstone as the Ironclad-only ones),
  and 10 event relics an Act 1 run can meet.
- Writable once the base atom exists: **31 relics** in a fight (21 whole,
  10 with an out-of-combat part still blocked), plus the 2 present ones,
  which also need R1 to be granted. **18 potions**.
- Blocked: 60 relics in a fight, 46 relics only out of combat, 15 potions.
- Every relic also needs R2 (the run layer holds relics and hands them out)
  and every potion P2 (the run layer holds potions and drops them). These
  are counted once, not per entry.

Every pool relic can drop in Act 1: `relicCanSpawn` limits some by floor
(Tiny Chest 35, Wing Boots and Matryoshka 40, the 48s and Preserved Insect
52: all after Act 1), by deck (the Bottled relics need a non-basic card of
their type, Bottled Tornado any Power) or by starter (Black Blood needs
Burning Blood). Boss relics reach Act 1 through the Act 1 boss chest (used
from Act 2's first floor) and Neow's boss swap. Neow can also give a random
common or rare relic and Neow's Lament (`GameContext.cpp` 2316-2377).

## Relics

### Starter (1)

| Relic | Effect (numbers) | When | Class | How or what's missing |
|---|---|---|---|---|
| Burning Blood | heal 6 HP at the end of a won combat | combat end | **loaded** (`relics.rs` `burning_blood_from_data`) | `content/relics.json`, `win_heal` 6 (the fight's heal amount, R1 as built) |

### Common (33)

| Relic | Effect (numbers) | When | Class | How or what's missing |
|---|---|---|---|---|
| Whetstone | on pickup, upgrade 2 random Attacks | out (pickup) | out of combat | R36 deck edits (random upgrade; pack cards need C6's upgrade link) |
| The Boot | unblocked attack damage you deal of 1-4 becomes 5 | fight | **loaded** (`act1_relics.rs` `after_block_relics`) | `powers` shorthand: pack power `TheBoot`, a `DealtAfterBlock` replacement `AtLeast 5` (`Boot.java` `onAttackToChangeDamage`, after the monster's block and Intangible) |
| Blood Vial | heal 2 HP at the start of each combat | fight | **loaded** (`act1_relics.rs` `counter_and_heal_relics`) | relic hook (`atBattleStart`): `CombatStart` -> `Heal` 2 |
| Meal Ticket | heal 15 HP when you enter a shop | out (shop) | out of combat | R33 gold and shop |
| Pen Nib | every 10th Attack played deals double damage | fight, counter across combats | **loaded** (`act1_relics.rs` `two_conditions_block_and_death_relics`) | relic hooks (`onUseCard`): `CardPlayed by Owner` Attack AddCounter 1; `CounterIs 10` -> counter 0; [Attack, `CounterIs 9`] -> Apply pack power `PenNib` (static `DamageDealt` Multiply 2, `CardPlayed by Owner` Attack -> `RemoveSelf`); `CombatStart` `CounterIs 9` -> Apply `PenNib`; carried counter is the caller's (R2) |
| Akabeko | 8 Vigor at combat start (the first Attack deals 8 more) | fight | **loaded** (`act1_relics.rs` `after_the_card_relics`) | `powers` shorthand: `CombatStart` Apply 8 of the pack power `Vigor` (static `DamageDealt` Add 1 per stack; `CardPlayed by Owner` Attack -> `RemoveSelf`) |
| Lantern | +1 energy on turn 1 | fight | **loaded** (`act1_relics.rs` `turn_one_relics`) | relic hook (2026-11-11): `OwnerTurnStart`, `CounterIs 0` -> `GainEnergy` 1, counter 1 (the game's `firstTurn`) |
| Regal Pillow | heal 15 more when you rest | out (rest) | out of combat | R34 rest options (the gauntlet's `rest()` is a fixed 30%) |
| Bag of Preparation | draw 2 more cards at combat start | fight | **loaded** (`act1_relics.rs` `turn_one_relics`) | relic hook: `CombatStart` -> `Draw` 2 (the game's `atBattleStart`, after the opening 5) |
| Ancient Tea Set | after a rest site, +2 energy on the next combat's turn 1 | fight (set at rest) | **loaded** (`act1_relics.rs` `turn_one_relics`) | relic hook: file counter -2 (the game's value after a rest); `OwnerTurnStart`, `CounterIs -2` -> `GainEnergy` 2, counter -1; the run layer passes -1 when no rest came before |
| Smiling Mask | the shop's card removal costs 50 gold | out (shop) | out of combat | R33 |
| Potion Belt | +2 potion slots | fight and out | **loaded** (`act1_singles.rs` `entropic_brew_fills_every_empty_slot`) | `content/packs/act1-relics.json`: `potion_slots: 2` (docs/specs/act1-singles.md section 5); carrying 5 potions between fights is P2 |
| Preserved Insect | elites start at 75% of their max HP | fight start | blocked | R10 a combat-start change of monster HP |
| Omamori | negate the next 2 curses you obtain | out | out of combat | R29 curses |
| Maw Bank | +12 gold per floor climbed, until you spend gold in a shop | out | out of combat | R33 |
| Art of War | +1 energy at turn start if no Attack was played last turn (never turn 1: `atPreBattle` sets `firstTurn`) | fight | **loaded** (`act1_singles.rs` `art_of_war`) | counter as `gainEnergyNext`: reset at `CombatStartPreDraw`, `OwnerTurnStart` at 1 gains, then set 1; an Attack's `CardPlayed` sets 0 (docs/specs/act1-singles.md) |
| Toy Ornithopter | heal 5 HP whenever you use a potion (**unverified**: not in sts_lightspeed) | fight and out | blocked | P1, R7 heal, P7 a "potion used" trigger |
| Ceramic Fish | +9 gold whenever you add a card to your deck | out | out of combat | R33 |
| Vajra | 1 Strength at combat start | fight | **loaded** (`act1_relics.rs` `starting_official_powers`) | `powers` shorthand: `CombatStart` Apply Strength 1 |
| Centennial Puzzle | the first time you lose HP in a combat, draw 3 | fight | **loaded** (`act1_relics.rs` `open_check_a_hook_draws_in_the_monsters_turn`) | relic hook: `OwnerLostHp`, `CounterIs 0` -> `Draw` 3, counter 1 (the game's `usedThisCombat`) |
| Strawberry | +7 max HP | out (pickup) | out of combat | R32 max HP |
| Happy Flower | every 3 turns, +1 energy (counter carries across combats) | fight | **loaded** (`act1_relics.rs` `counter_and_heal_relics`) | relic hooks (`atTurnStart`): `OwnerTurnStart` AddCounter 1; `CounterIs 3` -> `GainEnergy` 1, counter 0; the counter carried between fights is the caller's (R2) |
| Oddly Smooth Stone | 1 Dexterity at combat start | fight | **loaded** (`act1_relics.rs` `starting_official_powers`) | `powers` shorthand: `CombatStart` Apply Dexterity 1 |
| War Paint | on pickup, upgrade 2 random Skills | out (pickup) | out of combat | R36 |
| Bronze Scales | 3 Thorns at combat start | fight | **loaded** (`act1_relics.rs` `starting_official_powers`) | `powers` shorthand: `CombatStart` Apply Thorns 3 |
| Juzu Bracelet | no monster fights in ? rooms | out (map) | out of combat | R37 map and rooms |
| Dream Catcher | when you rest, you may add a card to your deck | out (rest) | out of combat | R34, R35 card rewards |
| Nunchaku | every 10 Attacks played, +1 energy (counter carries across combats) | fight | **loaded** (`act1_relics.rs` `after_the_card_relics`) | relic hooks (`onUseCard`, its action queued behind the card): `CardPlayed by Owner` `CardType Attack` AddCounter 1; `CounterIs 10` -> `GainEnergy` 1, counter 0; carried counter is the caller's (R2) |
| Tiny Chest | every 4th ? room is a treasure room | out (map) | out of combat | R37 |
| Orichalcum | at turn end with 0 block, gain 6 block | fight | **loaded** (`act1_relics.rs` `two_conditions_block_and_death_relics`) | relic hook (`onPlayerEndTurn`): `OwnerTurnEnd`, `OwnerBlockIs 0` -> `Block` 6, before the powers' turn-end block (the class's `trigger` field is set nowhere else) |
| Anchor | 10 block at combat start | fight | **loaded** (`act1_relics.rs` `turn_one_relics`) | relic hook: `CombatStart` -> `Block` 10 (after turn 1's block reset, so it lasts the turn as the game's does) |
| Bag of Marbles | 1 Vulnerable to all enemies at combat start | fight | **loaded** (`act1_relics.rs` `turn_one_relics`) | relic hook: `CombatStart` -> `Apply` Vulnerable 1 `AllOpponents` (Sentries' Artifact cancels it, as in the game) |
| Red Skull (Ironclad) | +3 Strength while HP is at most 50% | fight | **loaded** (`act1_relics.rs` `starting_official_powers`, `red_skull.rs`) | relic hook, real Strength (`RedSkull.java`): counter is `isActive`; `CombatStart` at half HP or below +3; `OwnerBloodied` at 0: +3, counter 1; `OwnerUnbloodied` at 1: -3, counter 0; Heavy Blade and Limit Break count it |

### Uncommon (30)

| Relic | Effect (numbers) | When | Class | How or what's missing |
|---|---|---|---|---|
| Bottled Tornado | on pickup, choose a Power; it starts every combat in your hand | out (pickup) + fight | writable, out-of-combat part blocked | an innate variant of the card (the `innate` flag exists); the choice needs R36 |
| Sundial | every 3 shuffles, +2 energy | fight | blocked | R4, R24 a shuffle trigger |
| Kunai | every 3 Attacks in one turn, 1 Dexterity | fight | **loaded** (`act1_relics.rs` `after_the_card_relics`) | relic hooks: `OwnerTurnStart` counter 0; `CardPlayed by Owner` Attack AddCounter 1; `CounterIs 3` -> Dexterity 1, counter 0 (after the card: the 3rd Attack itself doesn't get it, as in the game) |
| Pear | +10 max HP | out | out of combat | R32 |
| Blue Candle | curses are playable; playing one exhausts it and costs 1 HP | fight | blocked | R29 curses, R44 unplayable cards made playable |
| Eternal Feather | entering a rest site, heal 3 per 5 cards in the deck | out (rest) | out of combat | R34 |
| Strike Dummy | Strike cards deal 3 more damage | fight | **loaded** (`act1_relics.rs` `every_turn_and_triggered_relics`) | `powers` shorthand with the pack power `StrikeDummy` (kept: relics have no static modifiers): static `DamageDealt` Add 3 under `CardInPlayTagged` Strike |
| Singing Bowl | at a card reward, may take +2 max HP instead | out (rewards) | out of combat | R35, R32 |
| Matryoshka | the next 2 non-boss chests hold 2 relics | out (chests) | out of combat | R37 |
| Ink Bottle | every 10 cards played, draw 1 (counter carries across combats) | fight | **loaded** (`act1_relics.rs` `after_the_card_relics`) | relic hooks: `CardPlayed by Owner` Always AddCounter 1; `CounterIs 10` -> `Draw` 1, counter 0; carried counter is the caller's (R2) |
| The Courier | the shop restocks and is 20% cheaper | out (shop) | out of combat | R33 |
| Frozen Egg | Powers added to the deck are upgraded | out | out of combat | R35 (and C6 links for pack cards) |
| Ornamental Fan | every 3 Attacks in one turn, 4 block | fight | **loaded** (`act1_relics.rs` `after_the_card_relics`) | as Kunai, `Block` 4 (raw) |
| Bottled Lightning | as Bottled Tornado, a Skill | out + fight | writable, out-of-combat part blocked | innate variant; R36 |
| Gremlin Horn | when an enemy dies, +1 energy and draw 1 | fight | **loaded** (`act1_relics.rs` `two_conditions_block_and_death_relics`) | relic hook (`onMonsterDeath`): `OpponentDied` (another monster still lives) -> `GainEnergy` 1, `Draw` 1 |
| Horn Cleat | at the start of turn 2, 14 block | fight | **loaded** (`act1_relics.rs` `counter_and_heal_relics`) | relic hooks (`atBattleStart` counter 0; `atTurnStart`): `CounterIs 1` -> `Block` 14, counter -1; `CounterIs 0` -> counter 1 |
| Toxic Egg | Skills added to the deck are upgraded | out | out of combat | R35 |
| Letter Opener | every 3 Skills in one turn, 5 damage to all enemies | fight | **loaded** (`act1_relics.rs` `after_the_card_relics`) | as Kunai on Skills, `PlainDamage` 5 `AllOpponents` (THORNS) |
| Question Card | card rewards offer 1 more card | out (rewards) | out of combat | R35 |
| Bottled Flame | as Bottled Tornado, an Attack | out + fight | writable, out-of-combat part blocked | innate variant; R36 |
| Shuriken | every 3 Attacks in one turn, 1 Strength | fight | **loaded** (`act1_relics.rs` `after_the_card_relics`) | as Kunai, Strength 1 |
| Molten Egg | Attacks added to the deck are upgraded | out | out of combat | R35 |
| Meat on the Bone | at the end of a won combat with HP at most 50%, heal 12 | combat end | **loaded** (`act1_relics.rs` `combat_won_relics`) | relic hook (`onTrigger` in `AbstractRoom.endBattle`, before `onVictory`): `CombatWon`, `OwnerHpAtMostHalf` -> `Heal` 12, before Burning Blood's 6 |
| Darkstone Periapt | +6 max HP whenever you obtain a curse | out | out of combat | R29, R32 |
| Mummified Hand | when you play a Power, a random card in hand costs 0 this turn (**unverified**: sts_lightspeed `// todo`) | fight | blocked | C5 cost changes, R28 random effects in a hook |
| Pantograph | heal 25 HP at the start of boss combats | fight | **loaded** (`act1_relics.rs` `counter_and_heal_relics`) | relic hook: `CombatStart` -> `Heal` 25; `fights` boss (the game checks for a boss monster) |
| White Beast Statue | potions always drop after combat | out (rewards) | out of combat | P1, P2 |
| Mercury Hourglass | at turn start, 3 damage to all enemies | fight | **loaded** (`act1_relics.rs` `every_turn_and_triggered_relics`) | relic hook: `OwnerTurnStart` -> `PlainDamage` 3 `AllOpponents` |
| Self-Forming Clay (Ironclad) | whenever you lose HP, 3 block next turn | fight | **loaded** (`act1_relics.rs` `counter_and_heal_relics`) | relic hook (`wasHPLost`): `OwnerLostHp` Any -> Apply 3 of the pack power `NextTurnBlock` (`OwnerTurnStart` -> `Block` 1 per stack, `RemoveSelf`; the game's `NextTurnBlockPower`) |
| Paper Phrog (Ironclad) | Vulnerable enemies take 75% more damage, not 50% | fight | blocked | R15 a static condition on a power the target holds (Multiply 7/6 on top of Vulnerable's 3/2, if the multiplies compose exactly before the one rounding) |

### Rare (28)

| Relic | Effect (numbers) | When | Class | How or what's missing |
|---|---|---|---|---|
| Ginger | you can't become Weak | fight | **loaded** (`act1_relics.rs` `debuff_filter_relics`) | `powers` shorthand: pack power `GingerWard`, a `DebuffApplied` replacement filtered to Weak -> Cancel, before Artifact (`ApplyPowerAction.java` ~132) |
| Old Coin | +300 gold | out | out of combat | R33 |
| Bird-Faced Urn | heal 2 HP whenever you play a Power | fight | **loaded** (`act1_relics.rs` `counter_and_heal_relics`) | relic hook (`onUseCard`, `addToTop`): `OwnerPlaysCard` `CardType Power` -> `Heal` 2 |
| Unceasing Top | with no cards in hand during your turn, draw 1 | fight | blocked | R22 a trigger "hand empty" |
| Torii | unblocked attack damage of 2-5 to you becomes 1 | fight | **loaded** (`act1_relics.rs` `after_block_relics`) | pack power `Torii`: `AttackedAfterBlock`, `upTo 5`, `Cap 1` (`Torii.java` `onAttacked`; attacks only, after Buffer) |
| Stone Calendar | at the end of turn 7, 52 damage to all enemies | fight | **loaded** (`act1_relics.rs` `counter_and_heal_relics`) | relic hooks: `CombatStart` counter 0; `OwnerTurnStart` AddCounter 1; `OwnerTurnEnd` `CounterIs 7` -> `PlainDamage` 52 `AllOpponents` (THORNS) |
| Shovel | dig at rest sites for a relic | out (rest) | out of combat | R34 |
| Wing Boots | ignore map paths 3 times | out (map) | out of combat | R37 |
| Thread and Needle | 4 Plated Armor at combat start | fight | **loaded** (`act1_relics.rs` `every_turn_and_triggered_relics`) | `powers` shorthand: `CombatStart` Apply 4 of the pack power `PlatedArmor` (a real power: `OwnerTurnEnd` -> `Block` 1 per stack, `OwnerLostHp` Attack -> `ReduceSelf` 1) |
| Turnip | you can't become Frail | fight | **loaded** (`act1_relics.rs` `debuff_filter_relics`) | as Ginger: `TurnipWard`, Frail |
| Ice Cream | unspent energy carries to the next turn | fight | blocked | R19 energy kept between turns |
| Calipers | at turn start lose only 15 block | fight | blocked | R20 block kept in part (C12's kin) |
| Lizard Tail | once per run, when you would die, heal to 50% of max HP | fight | **loaded** (`act1_relics.rs` `lizard_tail`) | relic hook (`AbstractPlayer.damage` below 1 HP, after any Fairy): counter -1; `OwnerDied`, `CounterIs -1` -> `HealOf` 1/2 of `OwnMaxHp`, `SetCounter -2` (used up; the run layer carries -2, R2) |
| Prayer Wheel | normal fights give a second card reward | out (rewards) | out of combat | R35 |
| Girya | rest-site option "lift" (up to 3 times); 1 Strength per lift at combat start | out (rest) + fight | writable, out-of-combat part blocked | R1 with Strength n; the lift needs R34 |
| Dead Branch | when you exhaust a card, add a random card to hand | fight | blocked | R28 random card in a hook (C11) |
| Du-Vu Doll | 1 Strength per curse in the deck at combat start | fight | blocked | R29 (with curses, R1 with Strength n) |
| Pocketwatch | if you played 3 or fewer cards in a turn, draw 3 more next turn | fight | **loaded** (`act1_singles.rs` `pocketwatch`) | decided at `OwnerTurnEnd` (`CardsPlayedThisTurnBelow 3`, which leaves out a card in play, so "at most 3") into the counter; drawn at `OwnerTurnStartPostDraw` (docs/specs/act1-singles.md) |
| Mango | +14 max HP | out | out of combat | R32 |
| Incense Burner | every 6 turns, 1 Intangible (counter carries across combats) | fight | **loaded** (`act1_relics.rs` `counter_and_heal_relics`) | relic hooks: `OwnerTurnStart` AddCounter 1; `CounterIs 6` -> Apply Intangible 1 Me (the official power: one round, as `IntangiblePlayerPower`), counter 0; carried counter is the caller's (R2) |
| Gambling Chip | at the start of each combat (turn 1, after the draw), discard any cards and draw that many | fight | **loaded** (`fight_vocabulary.rs` `gambling_chip`) | relic hooks: `CombatStartPreDraw` counter 0 (`activated` reset); `OwnerTurnStartPostDraw`, `CounterIs 0` -> counter 1, Pick `DiscardFromHand` any number, `DrawPicked` (the pick opens once the pass has run, `Stage::RelicPick`) |
| Peace Pipe | rest-site option: remove a card | out (rest) | out of combat | R34 |
| Captain's Wheel | at the start of turn 3, 18 block | fight | **loaded** (`act1_relics.rs` `counter_and_heal_relics`) | as Horn Cleat, counting to 3: `Block` 18 |
| Fossilized Helix | 1 Buffer: prevent the next HP loss from damage | fight | **loaded** (`act1_relics.rs` `fossilized_helix_gives_buffer`) | `powers` shorthand: pack power `Buffer` 1, `TakenAfterBlock` -> Cancel, then `ReduceSelf 1` (`BufferPower.java` `onAttackedToChangeDamage`: every hit and HP loss past block) |
| Tungsten Rod | lose 1 less HP every time you lose HP | fight | **loaded** (`act1_relics.rs` `after_block_relics`) | pack power `TungstenRod`: `HpLossLast`, `Add -1` (`TungstenRod.java` `onLoseHpLast`, every loss, last) |
| Magic Flower (Ironclad) | healing in combat is 50% more | fight | blocked | R7, R47 a heal modifier (whether it raises Burning Blood: **unverified**) |
| Charon's Ashes (Ironclad) | whenever you exhaust a card, 3 damage to all enemies | fight | **loaded** (`act1_relics.rs` `every_turn_and_triggered_relics`) | relic hook: `CardExhausted` -> `PlainDamage` 3 `AllOpponents` |
| Champion Belt (Ironclad) | whenever you apply Vulnerable, also apply 1 Weak | fight | **loaded** (`act1_relics.rs` `champion_belt`) | relic hook `OwnerApplied`, `Applying Vulnerable` -> Apply Weak 1 `Opponent` (`ApplyPowerAction.java` ~105, `ChampionsBelt.java`: only when the Vulnerable lands, no Artifact; docs/specs/act1-singles.md) |

### Boss (22)

Ten boss relics give +1 energy per turn. In a fight that is the Berserk
pack power (`OwnerTurnStart` -> `GainEnergy` 1), given by R1. Their
downside is usually out of combat.

| Relic | Effect (numbers) | When | Class | How or what's missing |
|---|---|---|---|---|
| Fusion Hammer | +1 energy; no upgrades at rest sites | fight + out (rest) | writable, out-of-combat part blocked | energy power; R34 |
| Velvet Choker | +1 energy; at most 6 cards played per turn | fight | blocked | R6 a play limit per turn (`forbids` takes a card type, not a count) |
| Runic Dome | +1 energy; enemy intents hidden | fight | blocked | R25 hidden intents (the observation, not the state) |
| Slaver's Collar | +1 energy in elite and boss fights | fight | **loaded** (`act1_relics.rs` `energy_relics_and_fight_kinds`) | relic hook: `OwnerTurnStart` -> `GainEnergy` 1; `fights` elite and boss |
| Snecko Eye | draw 2 more each turn; Confused (a drawn card's cost is random, 0-3) | fight | **loaded** (`snecko.rs` `snecko_eye_draws_seven_and_rolls_each_drawn_card`) | relic key `draw_per_turn` 2; `CombatStartPreDraw` -> `Apply` the pack power Confused (`CardDrawn` Always -> `RandomizeCost` Drawn); docs/specs/sparse-piles.md step (c) |
| Pandora's Box | transform every Strike and Defend | out (pickup) | out of combat | R36 (transform) |
| Cursed Key | +1 energy; a curse from each non-boss chest | fight + out | writable, out-of-combat part blocked | energy power; R37, R29 |
| Busted Crown | +1 energy; card rewards offer 2 fewer | fight + out | writable, out-of-combat part blocked | energy power; R35 |
| Ectoplasm | +1 energy; you can't gain gold | fight + out | writable, out-of-combat part blocked | energy power; R33 |
| Tiny House | on pickup 1 potion, 50 gold, +5 max HP, 1 card, upgrade 1 random card | out (pickup) | out of combat | P2, R33, R32, R35, R36 |
| Sozu | +1 energy; you can't obtain potions | fight + out | writable, out-of-combat part blocked | energy power; P2 |
| Philosopher's Stone | +1 energy; all enemies start with 1 Strength | fight | **loaded** (`act1_relics.rs` `energy_relics_and_fight_kinds`) | relic hooks: `CombatStart` -> `Apply` Strength 1 `AllOpponents`; `OwnerTurnStart` -> `GainEnergy` 1 (spawned monsters don't get the Strength: no spawn trigger) |
| Astrolabe | on pickup transform 3 cards, then upgrade them | out | out of combat | R36 |
| Black Star | elites drop a second relic | out (rewards) | out of combat | R37 (R2 for the drop) |
| Sacred Bark | potion effects doubled | fight (and out for Fruit Juice) | loaded | `content/packs/act1-relics.json` (docs/specs/potions.md step 5): `potion_potency: 2`, potions with potency above 0 at double |
| Empty Cage | on pickup remove 2 cards | out | out of combat | R36 (the gauntlet's `remove()` removes one card by name at one floor) |
| Runic Pyramid | you don't discard your hand at turn end | fight | blocked | R21 hand kept at turn end |
| Calling Bell | on pickup the curse Curse of the Bell and 3 relics (common, uncommon, rare) | out | out of combat | R29, R2 |
| Coffee Dripper | +1 energy; you can't rest (heal) at rest sites | fight + out | writable, out-of-combat part blocked | energy power; R34 |
| Black Blood (Ironclad) | replaces Burning Blood: heal 12 at the end of a won combat | combat end | **loaded** (`act1_relics.rs` `every_relic_loads_with_its_rarity`) | `win_heal` 6, on top of the character's 6 (Burning Blood is the character's, not a held relic) |
| Mark of Pain (Ironclad) | +1 energy; 2 Wounds in the draw pile at combat start | fight | **loaded** (`act1_relics.rs` `energy_relics_and_fight_kinds`) | relic hooks: `OwnerTurnStart` -> `GainEnergy` 1; `CombatStart` -> `AddCard` Wound 2 to the draw pile (after the opening draw, as the game's `atBattleStart`) |
| Runic Cube (Ironclad) | whenever you lose HP, draw 1 | fight | **loaded** (`act1_relics.rs` `open_check_a_hook_draws_in_the_monsters_turn`) | relic hook: `OwnerLostHp` -> `Draw` 1 |

### Shop (17)

| Relic | Effect (numbers) | When | Class | How or what's missing |
|---|---|---|---|---|
| Sling of Courage | 2 Strength at the start of elite fights | fight | **loaded** (`act1_relics.rs` `energy_relics_and_fight_kinds`) | `powers` shorthand: `CombatStart` Apply Strength 2; `fights` elite |
| Hand Drill | whenever you break an enemy's block, apply 2 Vulnerable (`Monster.cpp` 433) | fight | blocked | R40 a trigger "block broken" |
| Toolbox | at combat start choose 1 of 3 random colorless cards into hand (not skippable, cost unchanged, before the opening draw) | fight | **loaded** (`act1_relics.rs` `toolbox`) | `content/packs/act1-colorless.json` (it names that pack's Colorless pool; docs/specs/colorless-cards.md step 6): a `CombatStartPreDraw` hook's `Discover` Colorless, offer 3, not free, no skip; the offer opens once the pre-draw pass has run (`Stage::RelicOffer`), the opening draw follows the pick |
| Chemical X | X-cost cards act as if 2 more energy was spent | fight | blocked | R41 a bonus to `EnergySpent` |
| Lee's Waffle | +7 max HP and heal to full | out | out of combat | R32 |
| Orrery | choose and add 5 cards to the deck | out | out of combat | R35 |
| Dolly's Mirror | duplicate a card in the deck | out | out of combat | R36 |
| Orange Pellets | play a Power, an Attack and a Skill in one turn: remove all your debuffs | fight | blocked | R5, R42 an effect "remove the owner's debuffs" |
| Prismatic Shard | card rewards include other colors' cards | out (rewards) | out of combat | R35 |
| Clockwork Souvenir | 1 Artifact at combat start | fight | **loaded** (`act1_relics.rs` `starting_official_powers`) | `powers` shorthand: `CombatStart` Apply Artifact 1 |
| Frozen Eye | you see the draw pile in order | fight | blocked | R26 a known draw order (the engine's draw pile is unordered; draws are chance events) |
| The Abacus | whenever you shuffle, 6 block | fight | blocked | R24 |
| Medical Kit | Status cards become playable and exhaust when played | fight | blocked | R44 |
| Cauldron | on pickup, 5 random potions to choose from | out | out of combat | P2 |
| Strange Spoon | a card that would exhaust goes to the discard pile instead 50% of the time | fight | blocked | R45 a chance replacement on exhaust |
| Membership Card | shop prices 50% off | out (shop) | out of combat | R33 |
| Brimstone (Ironclad) | at turn start, 2 Strength to you and 1 Strength to all enemies | fight | **loaded** (`act1_relics.rs` `every_turn_and_triggered_relics`) | relic hook: `OwnerTurnStart` -> `Apply` Strength 2 `Me`, `Apply` Strength 1 `AllOpponents` |

### Event relics an Act 1 run can meet (10)

Act 1's events (`Events.h`, `Act1::events`) are Big Fish, The Cleric,
Dead Adventurer, Golden Idol, Wing Statue, World of Goop, The Ssssserpent,
Living Wall, Hypnotizing Colored Mushrooms, Scrap Ooze and Shining Light;
its shrines are Match and Keep, Golden Shrine, Transmogrifier, Purifier,
Upgrade Shrine and Wheel of Change. One-time events that can appear in
Act 1 (`canAddOneTimeEvent`): Ominous Forge, Bonfire Spirits, Face Trader
(Acts 1-2), The Divine Fountain (with a curse), Lab, Note for Yourself,
We Meet Again, The Woman in Blue (with 50 gold). Big Fish, Dead Adventurer,
Scrap Ooze, Wheel of Change and We Meet Again give a random pool relic,
which is already in the tables above. The Woman in Blue and Lab give pool
potions. The relics only events give:

| Relic | From | Effect (numbers) | When | Class | How or what's missing |
|---|---|---|---|---|---|
| Neow's Lament | Neow | enemies in your next 3 combats have 1 HP | fight start | blocked | R10, with a run counter |
| Golden Idol | Golden Idol event | +25% gold | out | out of combat | R33 |
| Odd Mushroom | Hypnotizing Colored Mushrooms | Vulnerable makes you take 25% more damage, not 50% | fight | blocked | R15 (Multiply 5/6 on `DamageTaken` while the owner holds Vulnerable) |
| Warped Tongs | Ominous Forge | at turn start (after the draw), upgrade a random card in hand for the combat | fight | blocked | C6 upgrade in combat, R28 |
| Spirit Poop | Bonfire Spirits (offering a curse) | none (-1 score) | none | no effect | nothing to write |
| Cultist Headpiece | Face Trader | none (talks like a Cultist) | none | no effect | nothing to write |
| Face of Cleric | Face Trader | +1 max HP after each combat | out | out of combat | R32 |
| Gremlin Visage | Face Trader | 1 Weak at combat start | fight | **loaded** (`act1_relics.rs` `starting_official_powers`) | `powers` shorthand: `CombatStart` Apply Weak 1 to the player |
| N'loth's Hungry Face | Face Trader | the next non-boss chest is empty | out (chests) | out of combat | R37 |
| Ssserpent Head | Face Trader | +50 gold when you enter a ? room | out | out of combat | R33, R37 |

## Potions

The Ironclad's pool (`PotionPool::potionPool[0]`, 33): 3 Ironclad-only
(Blood Potion, Elixir, Heart of Iron) and 30 shared. Potions drop after
combats, and come from the shop, Neow ("3 small potions"), The Woman in
Blue, Lab and Cauldron. The player has 3 slots at Ascension 0; Potion Belt
adds 2. Using a potion is not playing a card: no `OwnerPlaysCard` or
`CardPlayed` hook fires, and its block is raw (`GainBlockAction`: no
Dexterity or Frail), as a hook's `Block` is today. Fire and Explosive
Potion deal non-attack (THORNS-type) damage, the engine's `PlainDamage`.
Fear, Fire and Weak Potion take a target (`potionRequiresTarget`); in the
game Poison Potion does too, but it's the Silent's.

| Potion | Rarity | Effect (numbers) | When | Class | How or what's missing |
|---|---|---|---|---|---|
| Blood Potion (Ironclad) | common | heal 20% of max HP (sources disagree, see the top) | fight and out | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); R7 (the heal amount is writable since fractional-amounts: `HealOf` 1/5 of `OwnMaxHp`); P1 |
| Elixir (Ironclad) | uncommon | exhaust any number of cards in hand | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Pick` `ExhaustFromHand`, `exact` false (P1 must resolve like a card row, where picks may run) |
| Heart of Iron (Ironclad) | rare | 6 Metallicize | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Apply` Metallicize 6 `Me` |
| Block Potion | common | 12 block | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Block` 12, raw |
| Dexterity Potion | common | 2 Dexterity | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Apply` Dexterity 2 |
| Energy Potion | common | +2 energy | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `GainEnergy` 2 |
| Explosive Potion | common | 10 damage to all enemies | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `PlainDamage` 10 `AllOpponents` |
| Fire Potion | common | 20 damage to a target | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `PlainDamage` 20 `Opponent` |
| Strength Potion | common | 2 Strength | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Apply` Strength 2 |
| Swift Potion | common | draw 3 | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Draw` 3 |
| Weak Potion | common | 3 Weak to a target | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Apply` Weak 3 `Opponent` |
| Fear Potion | common | 3 Vulnerable to a target | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Apply` Vulnerable 3 `Opponent` |
| Attack Potion | common | choose 1 of 3 random Attacks (or skip); it costs 0 this turn | fight | **loaded** (`discovery.rs`) | `content/packs/act1-potions.json`: `Discover` Ironclad `Attack`, free, skip; the pool's 28 Attacks are the game's |
| Skill Potion | common | as Attack Potion, Skills | fight | **loaded** (`discovery.rs`) | `Discover` Ironclad `Skill`; the pool holds 25 of the game's 28 Skills (Warcry, Battle Trance, Dual Wield don't load) |
| Power Potion | common | as Attack Potion, Powers | fight | **loaded** (`discovery.rs`) | `Discover` Ironclad `Power`; the pool holds 12 of the game's 14 Powers (Barricade, Juggernaut don't load) |
| Colorless Potion | common | as Attack Potion, colorless cards (not skippable) | fight | **loaded** (`colorless.rs`) | `content/packs/act1-colorless.json` (docs/specs/colorless-cards.md step 1): `Discover` Colorless, free, no skip; the pool holds 25 of the game's 34 colorless cards (steps 1 to 5) (`discovery.rs` names the rest) |
| Flex Potion | common | 5 Strength, lose 5 at turn end | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Apply` Strength 5, `Apply` LoseStrength 5 (as Flex) |
| Speed Potion | common | 5 Dexterity, lose 5 at turn end | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Apply` Dexterity 5 and a pack power LoseDexterity (`OwnerTurnEnd` -> `Apply` Dexterity -1, `RemoveSelf`) |
| Blessing of the Forge | common | upgrade every card in hand for the combat | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); C6 |
| Regen Potion | uncommon | 5 Regen: heal 5 at turn end, 1 less each turn | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); R7 (then a pack power: `OwnerTurnEnd` -> Heal 1 per stack, `ReduceSelf` 1) |
| Ancient Potion | uncommon | 1 Artifact | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Apply` Artifact 1 |
| Liquid Bronze | uncommon | 3 Thorns | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Apply` Thorns 3 |
| Gambler's Brew | uncommon | discard any cards, draw that many | fight | **loaded** (`fight_vocabulary.rs` `gamblers_brew`) | `content/packs/act1-potions.json`: Pick `DiscardFromHand` any number, `DrawPicked` |
| Essence of Steel | uncommon | 4 Plated Armor | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); the Plated Armor pack power (Thread and Needle's) |
| Duplication Potion | uncommon | this turn, your next card is played twice | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); pack power: `OwnerPlaysCard` Always -> `ReplayCard`, `ReduceSelf` 1; `OwnerTurnEnd` -> `RemoveSelf` (Double Tap for any type) |
| Distilled Chaos | uncommon | play the top 3 cards of your draw pile | fight | **loaded** (`act1_singles.rs` `distilled_chaos_plays_the_top_three_free`) | `content/packs/act1-potions.json`: `PlayTop` 3 (potency 3; Bark 6); all taken before any plays, each target chosen when taken (docs/specs/act1-singles.md) |
| Liquid Memories | uncommon | return a card from discard to hand; it costs 0 this turn | fight | **loaded** (`act1_singles.rs` `liquid_memories_returns_a_card_at_cost_0`) | `content/packs/act1-potions.json`: Pick `ReturnFromDiscard` n 1 (potency 1; Bark 2) with `free_this_turn` (docs/specs/act1-singles.md) |
| Cultist Potion | rare | 1 Ritual | fight | loaded | `content/packs/act1-potions.json` (docs/specs/potions.md step 5); `Apply` Ritual 1 `Me` (Ritual's `OwnerTurnEnd` -> Strength 1) |
| Fruit Juice | rare | +5 max HP | fight and out | **loaded** (`act1_potions.rs` `fruit_juice`) | `content/packs/act1-potions.json`: `GainMaxHp` 5 (potency 5; Sacred Bark 10); the run layer doesn't carry the max HP out yet (P2) |
| Snecko Oil | rare | draw 5, then each card in hand gets a random cost 0-3 for the combat | fight | **loaded** (`snecko.rs` `snecko_oil_draws_five_then_rolls_each_card_in_hand`) | `content/packs/act1-potions.json`: `Draw` 5 (potency 5; Bark 10), `RandomizeCost` Hand; docs/specs/sparse-piles.md step (c) |
| Fairy in a Bottle | rare | when you would die, heal to 30% of max HP (used up; not drunk by hand) | fight | **loaded** (`act1_potions.rs` `fairy_in_a_bottle`) | `content/packs/act1-potions.json`: `"trigger": "OwnerDied"` (never a legal action, the class's `canUse()` false), `HealOf` 3/10 of `OwnMaxHp`, potency 30 (Bark 60) |
| Smoke Bomb | rare | escape a non-boss combat (no rewards) (`potions/SmokeBomb.java`; sts_lightspeed `// todo`) | fight | **loaded** (`act1_potions.rs` `smoke_bomb_escapes_a_hallway_fight_as_won`) | `content/packs/act1-potions.json`: `Escape` with `fights` hallway and elite; the fight ends as won with `escaped` set, held in a boss fight (docs/specs/act1-singles.md); the lost rewards wait for P2 |
| Entropic Brew | rare | fill every empty slot with random potions | fight and out | **loaded** (`act1_singles.rs` `entropic_brew_fills_every_empty_slot`, `one_slot_odds`, `a_potion_it_makes_works`) | `content/packs/act1-potions.json`: `ObtainRandomPotions` except `["Fruit Juice"]` (potency 0); its potion pool is the pack's loaded potions; drunk outside a fight is P2 |

### Potions loaded (potions spec, step 5)

21 potions load from `content/packs/act1-potions.json`, each checked
against its game class in `engine/tests/act1_potions.rs` (the decompiled
`potions/<Class>.java`), and Sacred Bark (`potion_potency: 2`) joins
`content/packs/act1-relics.json`. Read from the classes: Explosive Potion
deals NORMAL damage but with no owner and a pure damage matrix
(`DamageAllEnemiesAction(null, createDamageMatrix(10, true), NORMAL)`),
so like Fire Potion's THORNS damage it takes no Strength or Vulnerable and
no Curl Up, Angry or Plated Armor reacts: both are `PlainDamage`. Blood
Potion's potency is 20 (`BloodPotion.java`), which settles the note at the
top. Blessing of the Forge is `ArmamentsAction(true)`, the engine's
`UpgradeHand`, so it loads. Duplication's power loses one at the end of
the round in the game (`atEndOfRound`); the pack power loses one at the
player's turn end, the same while no card plays in the monsters' turn.

Colorless Potion loads since colorless cards step 1 (docs/specs/colorless-cards.md).
Snecko Oil loads since the cost for the combat (below). Gambler's Brew and Fruit
Juice load since the fight vocabulary (below), Liquid Memories since the
"costs 0 this turn" mark, Smoke Bomb since the player's escape and
Distilled Chaos since `PlayTop` (docs/specs/act1-singles.md), Attack,
Skill and Power Potion since discovery, Entropic Brew since potions made
in a fight (below).

## Missing building blocks, ordered by entries unblocked

The base atoms, needed by every entry of their kind:
- **R1 a relic slot holding pack powers at combat start**: the fight spec
  (`sts.run`) takes the player's starting powers (official or pack, with
  amounts), as monsters' `start_powers` do, and the codec and binding carry
  them. A turn-1-only effect is a power that ends with `RemoveSelf`.
- **R2 relics in the run layer**: the gauntlet holds a relic list per
  sequence, hands relics out (elite reward, chest, shop, boss chest, Neow,
  events), and passes each relic's powers to each fight (for some, only in
  elite or boss fights).
- **P1 a potion slot and a Use action** (built 2026-11-12,
  docs/specs/potions.md; docs/extending.md "Potions"): slots in the combat
  state, the reserved `UsePotion` (codec tag 4, action text
  `Potion:<slot>[@target]`) as a legal action, which resolves the potion's
  effect list like a card row (targets, picks) but isn't a played card.
- **P2 potions in the run layer**: carried across fights, dropped after
  combats, bought, and given by events.

| Block | Unblocks | Entries alone | Entries with partners |
|---|---|---|---|
| R1 (with R2) relic slot holding powers at combat start (built: see "R1 as built"; R2 not built) | the 21 writable relics, the fight parts of the 10 energy, Bottled and Girya relics, and Red Skull's grant | 31 | 33 with the 2 present |
| P1 (with P2) potion slot and a Use action (built: 21 potions and Sacred Bark loaded with P1, all 33 potions load now with later blocks; P2 not built) | the 18 writable potions; Sacred Bark | 19 | all 33 potions, Toy Ornithopter, Potion Belt, White Beast Statue, Cauldron |
| R36 out-of-combat deck edits (random upgrade, transform, duplicate, choose a deck card) | Whetstone, War Paint, Pandora's Box, Astrolabe, Empty Cage, Dolly's Mirror, Bottled Flame, Lightning, Tornado | 9 | 10 (Tiny House) |
| R33 gold and shop | Meal Ticket, Smiling Mask, Maw Bank, Ceramic Fish, The Courier, Old Coin, Membership Card, Golden Idol; Ectoplasm's downside | 9 | 11 (Ssserpent Head, Tiny House) |
| R35 card-reward changes | Question Card, Prayer Wheel, Frozen/Toxic/Molten Egg, Orrery, Prismatic Shard; Busted Crown's downside | 8 | 11 (Dream Catcher, Singing Bowl, Tiny House) |
| R34 rest-site options | Regal Pillow, Eternal Feather, Shovel, Peace Pipe; Girya, Fusion Hammer, Coffee Dripper's out-of-combat parts | 7 | 8 (Dream Catcher) |
| R5 card counts by type this turn and last turn (built: all 6 load) | Art of War, Kunai, Shuriken, Ornamental Fan, Letter Opener, Pocketwatch | 6 | 7 (Orange Pellets, with R42) |
| R37 map, rooms and chests | Juzu Bracelet, Tiny Chest, Matryoshka, Wing Boots, Black Star, N'loth's Hungry Face | 6 | 8 (Cursed Key's downside with R29, Ssserpent Head with R33) |
| R7 heal effect (C14's healing) (built: all 5 load) | Blood Vial, Bird-Faced Urn, Pantograph, Blood Potion, Regen Potion | 5 | 9 (Lizard Tail, Magic Flower, Toy Ornithopter, Fairy in a Bottle) |
| R32 max HP changes | Strawberry, Pear, Mango, Lee's Waffle, Face of Cleric, Fruit Juice | 6 | 9 (Singing Bowl, Darkstone Periapt, Tiny House) |
| P3 discovery (built: Attack, Skill, Power Potion load; see "Discovery") | Attack, Skill, Power Potion; Infernal Blade | 3 | 3 |
| Colorless cards (the game's 34 in-combat colorless cards as a pack and its `Colorless` pool; a relic's `Discover` before the opening draw) (built: both load; Toolbox since step 6) | Colorless Potion, Toolbox | 2 | 2 |
| R4 a counter across turns and combats, firing every N (built: all 4 load) | Happy Flower, Nunchaku, Ink Bottle, Incense Burner | 4 | 6 (Pen Nib with R16, Sundial with R24) |
| R12 after-block replacement on HP loss and damage dealt (built: all 4 load) | The Boot, Torii, Tungsten Rod, Fossilized Helix | 4 | 4 |
| R3 turn-number condition (built: all 3 load) | Horn Cleat, Captain's Wheel, Stone Calendar | 3 | 3 |
| R29 curses (a Curse card type, curses in the run) | Omamori, Du-Vu Doll | 2 | 6 (Blue Candle, Darkstone Periapt, Calling Bell, Cursed Key's downside) |
| C5 cost changes in combat (built: this turn and for the combat; Snecko Eye, Snecko Oil and Liquid Memories load, docs/specs/sparse-piles.md) | Liquid Memories | 1 | 4 (Mummified Hand still needs R28) |
| R28 random effects in a hook (random card, random upgrade, random hand card) (built: docs/specs/blocked-relics.md step 5; Dead Branch, Mummified Hand, Warped Tongs and the colorless Magnetism load) | Dead Branch (with C11), Magnetism | 1 | 3 (Mummified Hand with C5, Warped Tongs with C6) |
| R8 combat-end heal by relic, with an HP condition (built: both load) | Meat on the Bone, Black Blood (and Burning Blood out of code) | 2 | 3 |
| R10 combat-start change of monster HP | Preserved Insect, Neow's Lament | 2 | 2 |
| R13 replacement filtered by power kind (built: both load) | Ginger, Turnip | 2 | 2 |
| R15 static condition on a power held (target or owner) | Paper Phrog, Odd Mushroom | 2 | 2 |
| R27 a pick outside a card, with an amount from the pick count (built: both load) | Gambling Chip, Gambler's Brew | 2 | 2 |
| R23 death replacement (built: docs/specs/would-die.md) | Lizard Tail, Fairy in a Bottle (with R7, built) | 2 | 2 |
| R24 shuffle trigger | The Abacus | 1 | 2 (Sundial with R4) |
| R44 unplayable cards made playable | Medical Kit | 1 | 2 (Blue Candle with R29) |
| C6 upgrade in combat (step 1's) (built: Blessing of the Forge loads) | Blessing of the Forge | 1 | 2 (Warped Tongs with R28) |
| R16 trigger after the owner's card resolves (built: Akabeko loads) | Akabeko | 1 | 2 (Pen Nib with R4) |
| R6, R11 (built), R14 (built), R17 (built), R18 (built), R19, R20, R21, R22, R25, R26, R40, R41, R45 | Velvet Choker, Gremlin Horn, Champion Belt, Orichalcum, Self-Forming Clay, Ice Cream, Calipers, Runic Pyramid, Unceasing Top, Runic Dome, Frozen Eye, Hand Drill, Chemical X, Strange Spoon | 1 each | 1 each |
| C8, P5 (built: the escape), P6 (built: Entropic Brew and Potion Belt load; see "Potions made in a fight") | Distilled Chaos, Smoke Bomb, Entropic Brew | 1 each | 1 each |
| R42, R47, P7 | none alone | 0 | Orange Pellets, Magic Flower, Toy Ornithopter |

Notes on the counts:
- The relics' weight is outside the fight: 46 relics act only in the run
  layer, and 10 more have an out-of-combat part. The run layer has none of
  gold, shop, chests, ? rooms, map choice, max HP changes or curses; it has
  a card reward, one rest site before the boss (plus an optional mid-run
  heal), one removal and the elite-or-hallway choice. In the opening read,
  fights alone gained 31 relics from R1, 6 more from R5 and 4 each from R4
  and R12; all of these load now.
- Six atoms are shared with step 1's card blocks: R7 is C14 (healing),
  R20 is C12's kin (block kept), R28 includes C11 (random card into hand),
  and C5, C6 and C8 appear as themselves. Building C5 and C6 for the cards
  also opens part of the relic and potion list.
- A new atom (trigger, condition, effect) goes in
  `registry::element_names()` with its words in `content/wording.json`
  (`engine/tests/wording.rs` names a miss), and most change the codec: R1's
  starting powers, R4's counters, P1's slots.
- Checks still to run before writing entries: whether two static
  multiplies compose exactly before the single rounding (Paper Phrog, Odd
  Mushroom), and the sources' disagreements listed at the top. The
  hook-draw check (Centennial Puzzle, Runic Cube;
  `engine/tests/act1_relics.rs`
  `open_check_a_hook_draws_in_the_monsters_turn`) and Art of War's turn-1
  behaviour (`engine/tests/act1_singles.rs`) are done.

## R1 as built (2026-11-10, owner-led session)

Spec `docs/specs/relics.md`; lane `act1-content`, commits fec883a (spec) to
this section's. The run layer (this file's R2) is not built: the gauntlet
doesn't hold or hand out relics until the headline change after Act 1
(owner, 2026-11-10).

- **Relics loaded: 23 of 141.** The 21 writable relics and Red Skull in
  `content/packs/act1-relics.json` (15 pack powers of its own, e.g.
  `RelicEnergy`), each marked **loaded** in the tables above with the
  `engine/tests/act1_relics.rs` test that checks it; Burning Blood in the
  official `content/relics.json`.
- **The combat-end heal** is an amount the fight holds (`win_heal`),
  started from the starter relic, raised by given relics and by the new
  `WinHeal` effect (Self Repair's kind), read by every heal reader; the
  bounds cap it at max HP while a `WinHeal` may still fire; codec tag 6
  only when it differs from the character's default. Fights without relics
  are unchanged: golden identical, `series_check` PASS on 3,104 states,
  step 1's pins (`scripts/tests/test_relic_pins.py`).
- **Open checks, both pass:** a `Draw` from an `OwnerLostHp` hook in the
  monsters' turn draws (Centennial Puzzle: turn-2 hand 8, once; Runic Cube
  6, each time); turn-1 hooks land after the opening draw (Bag of
  Preparation: hand 7; Mark of Pain's Wounds in the draw pile, not the
  opening hand).
- **Deviations from the game:**
  - Red Skull was the `RedSkull` static (+3 per hit at HP at most half),
    not real Strength: Heavy Blade's multiplier and Limit Break didn't count
    it. Fixed 2026-11-11 (docs/specs/red-skull-strength.md): real Strength
    at the game's HP crossings.
  - Ancient Tea Set gives +2 energy in any fight it is given to; giving it
    only after a rest is the caller's (later the run layer's) job.
  - Turn-start relics (Mercury Hourglass, Brimstone, Lantern) fired after
    the draw, the game's before it: fixed by the turn-start split below.
  - A creature holds at most 12 powers (`POWER_CAP`): relics whose
    distinct starting powers pass it are an error naming the relic
    (`bind_relics`), where the game has no cap.
- **Speed:** `series_speed` job 0804 (fec883a against step 4's dfc6948,
  25 runs, order swapped every other run, 4 threads, queue busy alongside;
  record `jobs/done/0804-series-speed.json`, log
  `logs/jobs/0804-series-speed.log`) passes: per-run ratio medians, new
  over old, random combats/min +8.9%, search 1 thread -4.1%, search 16
  threads +8.2%, all within the -10% bar. Steps 5-6 changed only the
  relic path (`bind_relics`) in engine code since.
- **Newly writable** (`Effect::Heal`, 2b9c918, after this file's read):
  Blood Vial (turn-1 Heal 2), Bird-Faced Urn (Heal 2 on playing a Power),
  Pantograph (Heal 25 on turn 1, `fights: ["boss"]`); Regen Potion now
  needs only P1. Blood Potion also needed a share of max HP, which `Heal`'s
  fixed number can't say: since fractional-amounts (2026-11-11) it's
  `HealOf` 1/5 of `OwnMaxHp`, and it too needs only P1. Self-Forming Clay may be writable too
  (the same commit lets pack hooks apply pack powers): not checked.

## Turn-start timing (2026-11-10, owner-led session)

Spec `docs/specs/turn-start-draw.md` (the behavior is in
`docs/extending.md` "Turn start"); lane `act1-content`, commits 3459a46 (spec) to this
section's. A turn-start hook now runs where the game runs it, from the
game's decompiled code (`AbstractRoom.java` ~255, `GameActionManager.java`
~446):

- **Before the draw** (`OwnerTurnStart`, the game's `atTurnStart`):
  Mercury Hourglass, Brimstone, the energy relics (`RelicEnergy`), Lantern,
  Ancient Tea Set. Moved from after the draw. On turn 2 on, Mercury
  Hourglass killing the last monster ends the fight with no draw.
- **After the draw** (`OwnerTurnStartPostDraw`, the game's
  start-of-combat relics on turn 1): Anchor, Bag of Preparation, Bag of
  Marbles, Philosopher's Stone's Strength, Mark of Pain's Wounds. Unchanged
  in effect (they ran after the opening draw before too).
- **Turn 1** runs the post-draw hooks, then the pre-draw ones, after the
  opening draw, as the game's back-of-queue hooks; `turn1_pre_draw` makes
  turn 1 like the others. Brimstone's and Lantern's front-of-queue timing
  lands the same state, so they carry no mark.
- Relics not loaded yet go by the game's class: Blood Vial and
  Pantograph (`atBattleStart`, so post-draw); Pocketwatch, Warped Tongs,
  Gambling Chip (`atTurnStartPostDraw`, post-draw); Art of War and Happy
  Flower (`atTurnStart`, pre-draw).
- **Known limit:** one hook pass keeps one pending random draw
  (`chance.rs` `request_draw`), so a second random `Draw` in the same pass
  replaces the first; on turn 1 the post-draw and pre-draw hooks share a
  pass. No loaded relic or card draws on both sides.
- Checks: `engine/tests/game_turn_order.rs` (Bag of Preparation 7 cards;
  Mark of Pain's Wounds not in the opening hand; a pre-draw hand card
  leaves room for 4 drawn from turn 2 on, 5 on turn 1; Mercury Hourglass's
  kill with no draw), `turn_start_order.rs`, the 22 `act1_relics.rs` tests
  unchanged, golden identical.

## Relic entity (step 4, 2026-11-11, owner-led session)

Spec `docs/specs/relic-entity.md`, step 4: the 23 relics are their own
entity (`Player.relics`), each writing its hooks at the trigger of its
game class (decompiled `aeubanks/sts`, `relics/<Name>.java`, read
2026-11-11; the order of `AbstractRoom.java` ~231-246 and
`AbstractPlayer.java` `applyStartOfCombatLogic` / `applyStartOfTurnRelics`).
No helper power is left except `StrikeDummy` (a static modifier: relics
have no statics); Thread and Needle applies the pack power `PlatedArmor` (a real power, as the game's), not a relic-only helper.

| Relic | Game method | Now |
|---|---|---|
| Vajra, Oddly Smooth Stone, Bronze Scales, Clockwork Souvenir, Thread and Needle, Sling of Courage, Gremlin Visage | `atBattleStart` (ApplyPowerAction) | `powers` shorthand: `CombatStart` Apply to Me |
| Anchor, Bag of Preparation, Bag of Marbles, Mark of Pain's Wounds | `atBattleStart` | `CombatStart` Block 10 / Draw 2 / Vulnerable 1 to all / 2 Wounds in the draw pile |
| Philosopher's Stone | `atBattleStart` (`addPower` Strength 1 on each monster), `onEquip` energy | `CombatStart` Strength 1 to all enemies; `OwnerTurnStart` GainEnergy 1 |
| Slaver's Collar, Mark of Pain | `beforeEnergyPrep` / `onEquip` (+1 `energyMaster`) | `OwnerTurnStart` GainEnergy 1 |
| Lantern | `atTurnStart` while `firstTurn` | `OwnerTurnStart`, `CounterIs 0`: GainEnergy 1, counter 1 |
| Ancient Tea Set | `atTurnStart` on the first turn when `counter == -2` (set by `onEnterRestRoom`), then -1 | file counter -2; `OwnerTurnStart`, `CounterIs -2`: GainEnergy 2, counter -1 |
| Mercury Hourglass, Brimstone | `atTurnStart` | `OwnerTurnStart` (as before) |
| Centennial Puzzle | `wasHPLost` once (`usedThisCombat`) | `OwnerLostHp`, `CounterIs 0`: Draw 3, counter 1 |
| Runic Cube | `wasHPLost` | `OwnerLostHp`: Draw 1 |
| Charon's Ashes | `onExhaust` | `CardExhausted`: 3 to all enemies |
| Red Skull | `atBattleStart` (if bloodied and not `isActive`), `onBloodied`, `onNotBloodied` | counter = `isActive`; `CombatStart` at half or below adds 2, then 2 gives +3 (counter 1) and 3 sets 1; `OwnerBloodied` at 0: +3, counter 1; `OwnerUnbloodied` at 1: -3, counter 0 |

- **Against today's play** (`engine/tests/relic_baseline.rs`, 72 fights
  of the 23 relics plus a control, greedy, recorded at 6079d84 before the
  spec's steps): re-recorded, the only differences are the helper powers
  gone from the player's power list (530 lines). With those names taken
  out the two recordings are identical line for line: no relic plays
  differently in these fights.
- **Where they could differ** (no recorded fight reaches it):
  - Red Skull no longer double-counts when the player crosses half before
    `CombatStart` (`red_skull.rs` `no_double_count`, a pre-draw HP loss).
  - Any 16 pack relics (RELIC_CAP) fit one fight together (no helper powers take the
    player's 12 power slots); the starting-power cap check counts only the
    `powers` shorthand now.
  - Ancient Tea Set's counter is the game's: a caller passing -1 (no rest
    before the fight) turns it off, which the run layer (R2) will do.
- **Known limits, named:**
  - Philosopher's Stone's `onSpawnMonster` (+1 Strength on each spawned
    monster, `actions/common/SpawnMonsterAction.java` ~43: Slime Boss's and
    the large slimes' splits) has no trigger in the engine; split slimes
    don't get it (as before).
  - In the game, `addToTop` battle-start relics (Vajra, Clockwork
    Souvenir, ...) act before the opening draw and `addToBot` ones
    (Gremlin Visage, Anchor, ...) after it; here all run at `CombatStart`
    in list order. It shows only in combinations such as Clockwork
    Souvenir with Gremlin Visage listed first (the game's Artifact blocks
    the Weak whatever the order).
  - With `turn1_pre_draw` (not the game's order) turn 1's turn-start
    hooks run before the draw, so before `CombatStart`: a power a relic's
    `powers` gives first acts at a turn start on turn 2 there. A power
    given by a `CombatStartPreDraw` hook acts on turn 1 in both orders
    (`turn_start_order.rs` gives its powers that way).

## Counter relics (2026-11-12, owner session)

Loaded 17 more relics from `content/packs/act1-relics.json` with no engine
change: 40 of 141 load now (39 pack relics and Burning Blood). Each row
above names its test (`engine/tests/act1_relics.rs` `counter_and_heal_relics`
and `after_the_card_relics`), read from the decompiled
`relics/<Name>.java` (AxorusMT/sts). Three blocks in the table "Missing
building blocks" turned out to be smaller than it says:
- **R3 (turn number) and R4 (counter firing every N), in-fight part:** the
  relic counter (`SetCounter`, `AddCounter`, `CounterIs`; relic-entity
  step) is both. Carrying a counter between fights (Happy Flower,
  Nunchaku, Ink Bottle, Incense Burner) is the caller's starting counter:
  R2's job when the run layer comes.
- **R16 (a trigger after the owner's card resolves):** it exists. For the
  player, `CardPlayed by Owner` fires once the card has resolved (Rage;
  `state.rs` `card_resolved`), copies from Double Tap included, as the
  game's `UseCardAction` calls `onUseCard` for them.
- **R5 (card counts by type this turn):** a counter reset at
  `OwnerTurnStart` covers Kunai, Shuriken, Ornamental Fan and Letter
  Opener. Art of War and Pocketwatch read last turn's count: still R5.
- **R7 heal:** `Heal` (Blood Vial, Bird-Faced Urn, Pantograph).
- Self-Forming Clay: a relic hook applies the pack power `NextTurnBlock`.
- Black Blood: `win_heal` 6 on top of the character's 6 (R8 not needed).

Still out, newly named: **Pen Nib** needs a hook with two conditions (an
Attack *and* counter 9): with one condition, a Skill played at counter 9
would apply Pen Nib again. Not written: Happy Flower's and Incense
Burner's `counter == -1` branch (add 2, not 1); nothing in a fight sets
-1, and the caller passes the starting counter.

The relic baseline (`engine/tests/relic_baseline.rs`) re-recorded: the
old 23 relics' fights are unchanged line for line, new sections added.

## Fight vocabulary (2026-11-12, owner session)

Spec `docs/specs/fight-vocabulary.md` (branch `fight-vocab`, c5bf088 spec
to this section's commit). Seven words the engine lacked, each from the
decompiled class: a hook with two conditions, `OwnerBlockIs`,
`OpponentDied`, `CombatWon`, a debuff filter on `DebuffApplied`,
`GainMaxHp`, `DrawPicked` with a relic's pick (`Stage::RelicPick`). They
load **Pen Nib, Orichalcum, Gremlin Horn, Ginger, Turnip, Meat on the
Bone, Gambling Chip** (47 of 141 relics: 46 pack relics and Burning
Blood) and **Fruit Juice, Gambler's Brew** (23 of 33 potions). The
blocks they close: R6's kin for Pen Nib (two conditions), R17
(Orichalcum), R11 (Gremlin Horn), R13 (Ginger, Turnip), R8 (Meat on the
Bone), R32's in-fight part (Fruit Juice), R27 (Gambling Chip, Gambler's
Brew).

- A pack power a relic applies in a pass now first fires on the next
  pass, as a power's always did (Pen Nib's power isn't spent by the 9th
  Attack). One the `powers` shorthand gives at `CombatStart` misses that
  `CombatStart`; no content power has a `CombatStart` hook, and the relic
  baseline's old fights are identical.
- Net: 33 new zero row columns per mode (two triggers, `OwnerBlockIs`,
  `Applying(<power>)` for 30 powers); `series_check` PASS, the product net
  bit-identical.
- Review fix: a random `Draw` requested while another is pending now adds
  to it (it replaced it): Gremlin Horn on two deaths from one Cleave draws
  2. One recorded relic fight changes toward the game (Runic Cube vs Slime
  Boss, seed 3: two hits in one monsters' turn now draw both cards);
  golden is unchanged.
- Known limits: a second relic pick in one pass is skipped (none loaded
  has two); `GainMaxHp` and `DrawPicked` have no net column (as `HealOf`);
  Meat on the Bone's heal above half runs `OwnerUnbloodied` hooks after the
  fight ended (Red Skull's Strength drops in the finished state, its
  counter stays 1; as the game's `heal` calls `onNotBloodied`).

## Saved from death (2026-11-12, act1-r23 session)

Spec `docs/specs/would-die.md` (branch `claude/act1-r23-bc1c82`), read from
the decompiled `AbstractPlayer.damage` (below 1 HP: HP to 0, then a held
Fairy in a Bottle, else an unused Lizard Tail; no Mark of the Bloom check,
an Act 3 event relic outside this list). The player's `OwnerDied` is that
moment: a held potion with `"trigger": "OwnerDied"` is used up first, else
the player's `OwnerDied` hooks run, and a player at 1 HP or more after
them lives. Loads **Lizard Tail** (48 of 141 relics) and **Fairy in a
Bottle** (24 of 33 potions). No codec, stage or row column: nothing
re-pinned.
Landed e65da2d..786f2da (spec, steps 1-2, step 3, kb): engine 557 and
sts-py 8 pass (release), series_check PASS (3104 states); `jobs.py impact
sts`: none; main's `sts` swapped to this code's wheel.

- R7 (heal) was already built: Blood Vial, Bird-Faced Urn, Pantograph,
  Blood Potion and Regen Potion loaded before this. Its two other partners
  stay blocked elsewhere: Magic Flower (R47 a heal modifier; in the game it
  would raise these saves' heals too), Toy Ornithopter (P7).
- Named limits: a saved player's bloodied state moves once, from before
  the loss to after the save; the game runs `onBloodied` before the save
  and `onNotBloodied` inside its heal, the same net change for Red Skull.
  "Once per run" is Lizard Tail's counter (-2 used), carried by the caller
  until R2; the Fairy's slot likewise until P2.

## After block (2026-11-12, session act1-r12)

Spec `docs/specs/after-block.md` (branch `claude/act1-r12-017561`). R12
built: four replacement events that change the amount once block is
removed, one per hook point of the game's `AbstractPlayer.damage` /
`AbstractMonster.damage` (`onAttackToChangeDamage`,
`onAttackedToChangeDamage`, `onAttacked`, `onLoseHpLast`), each only
while the amount is above 0; the action `AtLeast` and the row range
`upTo`. They load **The Boot, Torii, Tungsten Rod, Fossilized Helix**
(52 of 141 relics, with Lizard Tail landed first), with the game's `Buffer` as a pack power. R12 is
closed.

- `LoseHp` and Poison go through the game's `damage` too (`LoseHPAction`,
  `PoisonLoseHpAction`): Buffer absorbs them and Tungsten Rod takes 1 off
  them; Torii and The Boot act on attacks only (`NORMAL`), not on
  `PlainDamage` (`THORNS`: Bronze Scales, Mercury Hourglass, Burn).
- The Boot acts after a monster's Intangible: an Intangible monster hit
  for 1 takes 5, as in the game.
- Net: six new zero row columns per mode (the four events as replacement
  triggers, the condition `AmountAtMost`, the row-only `replace_at_least`).
- Known limit: the agents' damage estimates leave the passes out (as they
  leave out the player's Intangible).

## The player escapes (2026-11-13, session act1-p5)

Spec `docs/specs/act1-singles.md` section 4. P5 built: the monster word
`Escape` is the user's in a potion row, the potion key `fights` ("usable
in", as a relic's "acts in") and the boss kinds, worked out at load (a
kind in any `boss`-group encounter, official or pack). It loads **Smoke
Bomb** (`potions/SmokeBomb.java`): in a hallway or elite fight the fight
ends as won (`CombatWon` hooks, then the combat-end heal: Meat on the
Bone's 12 at half HP, then Burning Blood's 6) with `CombatState.escaped`
set (Python `Combat.escaped`); the monsters keep their HP. In a boss
fight it isn't a legal action.

- The engine's split writes a child into the boss's slot, so a fight
  remembers it is a boss fight by a mark, `boss_fight`, set as the
  potions are given when a slot holds a boss and a held potion isn't
  usable in a boss fight. The codec writes `escaped` (tag 10) and the
  mark (tag 11) only when set: every other state's bytes are unchanged.
- No row column: `Escape` already has its effect column.
- Known limits: a potion that arrives mid-fight other than by a potion
  maker, after a boss split, is drinkable (no Act 1 content does that);
  `fights` names hallway and elite, boss optional; the lost rewards wait for
  P2 (the run layer holds no potions).

## Discovery (2026-11-12, act1-p3 session)

Spec `docs/specs/discovery.md` (branch `claude/act1-p3-ce2cda`), read
from the decompiled `DiscoveryAction`, the four potions, `Toolbox` with
`ChooseOneColorless`, `AbstractDungeon.returnTrulyRandomCardInCombat` and
`AbstractCard.setCostForTurn` / `resetAttributes`. A pack's `pools` names
the lists the game draws random cards from; the Ironclad pool
(`content/packs/act1-ironclad.json`) is the game's in-combat list
(common, uncommon and rare, HEALING-tagged Feed and Reaper left out), 28
Attacks, 25 Skills, 12 Powers. The effect `Discover` shows 3 different
cards of a pool (by type) as a chance event, every combination alike;
taking one (or skipping, where the game lets you) is a decision; the
copies (2 with Sacred Bark) go to hand while it holds fewer than 10, else
to the discard pile, costing 0 this turn when `free` (the singles
session's `free_in_hand` mark). Loads **Attack, Skill and Power Potion**
and **Infernal Blade** (`offer` 1: a random Attack, no choice). No codec,
stage byte or row column: nothing re-pinned.
Landed b80f493..a72dc7a (spec, steps, review fixes, rebase fixes): engine
and sts-py 601 pass (debug), Python pin and explorer tests 110 pass,
series_check PASS (3526 states, the product net); `jobs.py impact sts`:
none; main's `sts` swapped to a72dc7a's wheel. Review fixes: an open
offer counts as generated content (no codec encoding even with an
all-official pool); a deck's pool cards bind in slot order.

- The pools' gaps, named and checked by `discovery.rs`
  `the_ironclad_pool_is_the_games_less_the_missing_cards` (a card that
  starts loading must join; Havoc joined as it loaded): Skills Warcry,
  Battle Trance, Dual Wield; Powers Barricade, Juggernaut.
- Named limits: a copy sent to the discard pile by a full hand isn't
  marked free (the game keeps it at 0 until the turn ends); a fight binds
  every pack card its discoveries can offer (33 with Havoc; 40 card slots
  since Entropic Brew, see "Potions made in a fight"); the game's
  pools depend on unlocks (all unlocked here).
- **Colorless cards**, a new block: none of the game's 34 in-combat
  colorless cards loads (35 uncommon and rare colorless cards, Bandage Up
  left out as HEALING). About 15 are writable with today's words or
  `Discover`: Swift Strike, Flash of Steel, Finesse, Good Instincts,
  Dramatic Entrance, Blind, Trip, Panacea, Master of Strategy, Purity,
  Hand of Greed (its gold is the run layer's), Panic Button, The Bomb,
  Discovery, Jack of All Trades. About 19 need words: Mind Blast,
  Impatience, Dark Shackles, Deep Breath, Enlightenment (loads since the colorless build A), Madness,
  Forethought, Chrysalis, Metamorphosis (C5's kin), Apotheosis (C6's
  kin), Magnetism (R28; loads since R28), Mayhem (C8; loads since the colorless build B), Secret Technique, Secret Weapon,
  Violence, Thinking Ahead, Transmutation, Panache, Sadistic Nature
  (R14's kin). Colorless Potion and Toolbox load with that pack.

## The player applied a power (2026-11-13, session act1-r14)

Spec `docs/specs/act1-singles.md` section 6. R14 built: the trigger
`OwnerApplied` (the player's hooks, relics then powers, when a power the
player applied to a monster lands after the replacements) and the
condition `{"Applying": "<power>"}`, loadable under that trigger only.
Loads **Champion Belt** (55 of 141 relics, with Art of War and
Pocketwatch landed first). R14 is closed.

- It fires for every source the player owns: cards (Bash, Thunderclap,
  Uppercut, Shockwave), relic hooks (Bag of Marbles at combat start) and
  potions (Fear Potion). An Artifact cancel doesn't land, so it gives
  nothing; the powers an `OwnerApplied` hook applies don't fire it again.
- Known limit: the Belt's Weak lands at once, the game's after the card's
  other actions; no Act 1 card tells them apart.
- Net: one new zero row column per mode (trigger `OwnerApplied`); the
  condition reuses `Applying(<power>)`.

## Potions made in a fight (2026-11-13, act1-p6 session)

Spec `docs/specs/act1-singles.md` section 5, read from the decompiled
`potions/EntropicBrew.java` (one `ObtainPotionAction` per slot, full ones
skipped), `AbstractDungeon.returnRandomPotion` (a 0-99 roll: common below
65, uncommon below 90, else rare; uniform within; `limited` leaves Fruit
Juice out) and `relics/PotionBelt.java`. Loads **Entropic Brew** and
**Potion Belt**. The relic key `potion_slots` adds slots to the 3 of
Ascension 0; the potion effect `ObtainRandomPotions` gives one random
potion of its potion pool (the pack's potions less `except`) per empty
slot, each a chance event. A fight given the Brew binds every potion of
its pool (their pack powers, their discoveries' cards): every pack card
of the Ironclad pool, 33 since Havoc joined it, so a fight now has 40
card slots (was 32; ids of slots 0-31 unchanged). A boss fight holding
the Brew carries the boss-fight mark, so a Smoke Bomb it makes after
Slime Boss splits isn't drinkable. No codec bytes, stage byte or row
column: nothing re-pinned.

- Named limits: the potion pool is the loaded pack, not the game's 33
  (Colorless Potion and Snecko Oil never come until
  they load, and the odds within their rarities shift); Potion
  Belt's slots matter only in a fight until the run layer carries potions
  (P2).

## Batch speed check after R12 (2026-11-13)

Job 0965 (`jobs/done/0965-bash.json`, log `logs/jobs/0965-bash.log`):
series_speed of 68f3d7b (main after the after-block landing, measured by
0942) against 51fa94e2 (main after Entropic Brew), 25 runs each with the
order swapped. It covers the costs-0 mark, Art of War and Pocketwatch,
`PlayTop`, Smoke Bomb, discovery, Champion Belt, Entropic Brew and the 40
card slots. Search 1 thread -5.9% (per-run median -6.6%), 16 threads -5.2%
(median -6.4%), random combats +1.6%, clone 23.3 -> 15.8 ns. Worst -6.6%,
inside the 10% bar: pass.

## A cost for the combat: Snecko Oil and Snecko Eye (2026-11-13, session sparse-piles)

Spec `docs/specs/sparse-piles.md` step (c), on the copies-by-value piles
of steps (a) and (b). Read from the decompiled classes in
Li-Binghui/MySlayTheSpire (aeubanks/sts alike): `potions/SneckoOil.java`
34-42 (draw 5, then `RandomizeHandCostAction`),
`actions/unique/RandomizeHandCostAction.java` 23-29 and
`powers/ConfusionPower.java` 32-39 (a card whose cost is 0 or more rolls
`cardRandomRng.random(3)`, 0-3 alike; a roll equal to its cost changes
nothing, any other sets `cost` and `costForTurn` to it), and
`relics/SneckoEye.java` 22 and 34 (`masterHandSize += 2`, Confused at
`atPreBattle`). Loads **Snecko Oil** (32 of 33 potions) and **Snecko Eye**
(57 of 141 relics). C5's cost for the combat is in: a copy's own cost is
one of its numbers (`Overrides::cost`), interned by value.

- Words: the effect `RandomizeCost` ("Hand": each card in hand; "Drawn":
  the card drawn, only in a `CardDrawn` hook with condition `Always`), the
  relic key `draw_per_turn`, the pack power Confused. Each waiting copy
  rolls in its own chance event (`ChanceEvent::RandomCost`, 4 outcomes
  alike), queued in `CombatState::cost_rolls` with its free mark.
- An upgrade that changes a card's cost resets a cost for the combat to the
  new one (`upgradeBaseCost`, `cards/AbstractCard.java` 890-900); one that
  doesn't keeps it.
- Codec: pending tag 7, trailer section 14 (the waiting copies), section
  13's cost flag; existing bytes unchanged. A fight holding Snecko Eye
  binds a pack power, so it isn't encoded (as every such fight).
- Named limits: a roll happens after the effect that drew the card (the
  game's during the draw); Confused's `freeToPlayOnce = false` has no
  engine counterpart (no card here sets it); a rolled Blood for Blood still
  costs less for HP lost before the roll (the game's rolled cost forgets
  them); Entropic Brew's pool now holds Snecko Oil (its rare odds shift).


## Toolbox: a relic's offer before the opening draw (2026-11-13, colorless step 6)

Read from the installed jar (`javap`): `relics/Toolbox` is SHOP tier;
`atBattleStartPreDraw` queues `ChooseOneColorless` (`addToBot`). That
action offers 3 different cards of `returnTrulyRandomColorlessCardInCombat`
(`customCombatOpen(..., false)`: no skip), makes no free copy (no
`setCostForTurn(0)`, unlike `DiscoveryAction`), and puts the taken card in
hand below 10 cards, else in the discard pile. Loads **Toolbox** (59 of
141 relics).

- Words: `Discover` is allowed in a relic's `CombatStartPreDraw` hook only
  (`registry.rs`). It opens `Stage::RelicOffer` once the pre-draw pass has
  run (other relics' pre-draw hooks first, as Snecko Eye's Confused);
  the offer's chance event and pick land in that stage, the hook's rest
  runs after the pick, then `StartTurn` makes the opening draw.
- Codec: stage tag 11; existing bytes unchanged. A fight holding Toolbox
  binds pack cards, so it isn't encoded (as every such fight).
- Toolbox lives in `content/packs/act1-colorless.json`, not
  `act1-relics.json`: it names that pack's Colorless pool, which loads
  after `act1-ironclad.json`.
- Search: the stage is turn 1's only, so no leaf meets it; it is on the
  leaf rule's "block is the new turn's" list anyway. `awaiting_action` is
  true at its open pick (it has a pick).
- Named limit: under `turn1_pre_draw` (the constructor's option), a pick
  drops the option, so turn 1's `OwnerTurnStart` hooks run once after the
  opening draw instead of before it.
- Test: `engine/tests/act1_relics.rs` `toolbox`.
