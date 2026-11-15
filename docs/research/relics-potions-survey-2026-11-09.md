# Relics and potions in sts_lightspeed: a survey for act1-content (2026-11-09)

Research agent's report for the navigator (run 2026-11-09 13:55, recovered from its log). Web pages read are listed at the end; relic effect lines come from the agent's knowledge of the game, not checked against a page.

## 1. How sts_lightspeed does it (C++, read on GitHub)

The engine has no general hook system. Relic presence is stored as two 64-bit bitsets (`relicBits0/1`) in `include/combat/Player.h`. Each call site checks `hasRelic<RelicId::X>()` directly. Seven relic counters carry across fights, as int8 fields in Player.h: happyFlower, incenseBurner, inkBottle, inserter, nunchaku, penNib and sundial. Player.h also holds a Necronomicon per-turn flag and an Orange Pellets `bitset<3>` of card types played. `BattleContext::updateRelicsOnExit` writes the counters back to the run state.

Where relics are checked, with roughly how many relics each place uses:

| Hook point (file) | Relics |
|---|---|
| `BattleContext::initRelics` (combat start; `src/combat/BattleContext.cpp`) | about 60 |
| `Player::applyStartOfTurnRelics` / `...PostDrawRelics` (`src/combat/Player.cpp`) | 12 / 2 |
| `onUseAttackCard` / `onUseSkillCard` / `onUsePowerCard` / `onAfterUseCard` | 9 / 4 / 4 / 1 |
| `callEndOfTurnActions` (end of turn) / `afterMonsterTurns` | 5 (Orichalcum, Stone Calendar...) / 1 (Calipers) |
| `onShuffle` | 3 (Abacus, Sundial, Melange) |
| `triggerAndMoveToExhaustPile` (exhaust) | 2 (Dead Branch, Charon's Ashes) |
| `Player::attacked` / `hpWasLost` / `wouldDie` / `heal` | 2 / 5 / 3 (Lizard Tail, Sacred Bark+Fairy, Mark of the Bloom) / 3 |
| `Player::damage`/`loseHp`, `gainGold`, `rechargeEnergy` | Tungsten Rod; 2; Ice Cream |
| `Monster::die` / `attacked` / `calculateDamageToPlayer` / `attackedUnblockedHelper` (`src/combat/Monster.cpp`) | Gremlin Horn, Specimen / Hand Drill / Paper Krane, Odd Mushroom / The Boot |
| `calculateCardDamage` | Strike Dummy, Wrist Blade, Paper Phrog |
| `debuffEnemy` (`include/combat/BattleContext.h`) | Champion Belt |
| `isCardPlayAllowed`, `discardAtEndOfTurn`, `executeActions`, `obtainPotion`, `init` | Velvet Choker, Runic Pyramid, Unceasing Top, Sozu, Snecko Eye |
| `updateRelicsOnExit` (after combat) | 12 (counters, plus Burning Blood, Black Blood and Meat on the Bone heals) |

I did not find Toy Ornithopter in the combat files I read.

**Potions** live in `BattleContext.h` as `std::array<Potion,5> potions`, with `potionCount` and `potionCapacity = 3`. `drinkPotion(idx, target)` frees the slot first and then switches on the potion, queuing actions to the bottom of the action queue. It does not touch `cardsPlayedThisTurn`, the card queue or the hand, so a potion is not a card play. Sacred Bark is a `hasBark ? x : y` choice in every case. Only Fear, Fire, Poison and Weak need a target (`potionRequiresTarget`, `include/constants/Potions.h`). Fairy is never drunk (it asserts if you try) and fires in `wouldDie` instead. Smoke Bomb does nothing in `drinkPotion`; its escape is handled elsewhere.

## 2. Relics an Ironclad can meet in Act 1

Classes: **P** = power with existing hooks, **PC** = power plus a counter, **OUT** = out of combat, **NEW** = needs a new kind of hook or rule. P\* means the hook exists but a new effect is needed. To stay under the word limit I grouped names by class instead of giving one line per relic; the effect is given only where the class isn't obvious.

| Pool | P | PC | OUT | NEW |
|---|---|---|---|---|
| Starter (1) | – | – | Burning Blood (heals after combat) | – |
| Common (33) | Akabeko, Anchor, Bag of Marbles, Bag of Preparation, Blood Vial, Bronze Scales, Lantern, Oddly Smooth Stone, Orichalcum, Preserved Insect\*, Vajra (11) | Tea Set, Art of War, Centennial Puzzle, Happy Flower, Nunchaku, Pen Nib\* (needs a double-damage effect) (6) | Ceramic Fish, Dream Catcher, Juzu, Maw Bank, Meal Ticket, Omamori, Potion Belt, Regal Pillow, Smiling Mask, Strawberry, Tiny Chest, War Paint, Whetstone (13) | The Boot (raises small hits to 5), Toy Ornithopter (on potion use), Red Skull (HP at or below 50%) (3) |
| Uncommon (30) | Horn Cleat, Mercury Hourglass, Pantograph, Self-Forming Clay, Mummified Hand\* (5) | Ink Bottle, Kunai, Letter Opener, Ornamental Fan, Shuriken (5) | Darkstone, Feather, 3 Eggs, Matryoshka, Meat on the Bone, Pear, Question Card, Singing Bowl, Courier, White Beast (12) | Blue Candle (curses playable), Bottled Flame/Lightning/Tornado (card starts in hand), Gremlin Horn (enemy death), Strike Dummy, Sundial (shuffle), Paper Phrog (Vulnerable 75%) (8) |
| Rare (28) | Bird-Faced Urn, Captain's Wheel, Du-Vu Doll\*, Fossilized Helix (Buffer), Thread and Needle, Stone Calendar (6) | Girya, Incense Burner, Pocketwatch (3) | Mango, Old Coin, Peace Pipe, Prayer Wheel, Shovel, Wing Boots (6) | Calipers, Dead Branch, Charon's Ashes (exhaust), Gambling Chip (choice), Ginger, Turnip, Ice Cream, Lizard Tail (death prevention), Torii, Tungsten Rod, Unceasing Top (empty hand), Champion Belt (on applying Vulnerable), Magic Flower (13) |
| Shop (17) | Clockwork Souvenir, Sling of Courage, Brimstone (3) | Orange Pellets (1) | Cauldron, Dolly's Mirror, Lee's Waffle, Membership Card, Orrery, Prismatic Shard, Frozen Eye (only shows information) (7) | Chemical X, Hand Drill (enemy block broken), Medical Kit, Strange Spoon, Abacus (shuffle), Toolbox (choice) (6) |
| **Boss** (22; after the Act 1 boss, or from Neow's swap at floor 0) | Busted Crown, Coffee Dripper, Cursed Key, Ectoplasm, Fusion Hammer, Philosopher's Stone, Runic Dome, Slaver's Collar, Sozu, Mark of Pain, Runic Cube (11) | – | Astrolabe, Black Star, Calling Bell, Empty Cage, Pandora's, Tiny House, Black Blood (7) | Runic Pyramid, Sacred Bark, Snecko Eye, Velvet Choker (4) |
| **Act 1 events** (10) | Gremlin Visage, Warped Tongs\* (upgrade a card) | Neow's Lament (3 fights) | Golden Idol, Spirit Poop, Cultist Headpiece, Face of Cleric, N'loth's Hungry Face, Ssserpent Head (Face Trader masks) | Odd Mushroom |

**Counts for the pools Act 1 offers (109 relics):**

| Class | Count | Share |
|---|---|---|
| OUT | 39 | |
| P | 25 | |
| PC | 15 | |
| NEW | 30 | |
| P + PC + OUT | 79 | 72% |
| P + PC, among the 70 that act in combat | 40 | 57% |

Among commons alone, which are the most frequent drops, 17 of the 20 combat relics are P or PC. Boss relics: 11 P, 0 PC, 7 OUT, 4 NEW.

## 3. Potions

Not every base-game potion is open to the Ironclad. The game has 42 potions; the Ironclad pool is the 30 shared ones plus Blood Potion, Elixir and Heart of Iron, so 33.

| Rarity | C | CX |
|---|---|---|
| Common (17) | Block, Blood\* (needs a Heal effect), Dexterity, Energy, Explosive, Fear, Fire, Flex, Speed, Strength, Swift, Weak (12) | Attack, Skill, Power, Colorless (choose 1 of 3), Blessing of the Forge (upgrade the hand) (5) |
| Uncommon (9) | Ancient (Artifact), Essence of Steel, Liquid Bronze, Regen\* (4) | Distilled Chaos (play top 3), Duplication (play next card twice), Elixir and Gambler's Brew (choose from hand), Liquid Memories (choose from discard) (5) |
| Rare (7) | Cultist (Ritual), Heart of Iron (2) | Entropic Brew (makes potions), Fairy (revive), Fruit Juice (max HP), Smoke Bomb (escape), Snecko Oil (randomise costs) (5) |

**Counts:** 18 C and 15 CX. Weighted by drop rarity (65/25/10), about 60% of drops are C. If one "choose a card" effect is added, 7 of the CX potions become C, bringing the total to 25 of 33.

## Verdict

**H1 holds if out-of-combat relics count as cheap; it is about 57/43 if you look only at relics that act in combat.** Most relics weighted by how often they appear (commons, and the energy boss relics) fit "power plus hooks plus at most one counter". sts_lightspeed itself needs only 7 counters that carry across fights. The 30 exceptions fall into four groups:
- **Damage and heal modifiers:** Boot, Torii, Tungsten Rod, Paper Phrog, Odd Mushroom, Strike Dummy, Magic Flower, and Pen Nib's double damage.
- **Rule changes:** Ginger, Turnip, Ice Cream, Runic Pyramid, Calipers, Velvet Choker, Blue Candle, Medical Kit, Chemical X, Snecko Eye, Sacred Bark.
- **New triggers:** shuffle, exhaust, enemy death, potion use, death prevention, empty hand, applying a debuff, breaking block.
- **Choice screens:** Gambling Chip, Toolbox, and the three Bottled relics, which need a mark on one card instance.

Small new effects behind P\*: Heal, Vigor-style temporary Strength, double damage, a cost change, upgrade a card, and percent-HP loss for Preserved Insect.

**H2 is half true (18 of 33).** The card model fits on its own terms: lightspeed confirms potions aren't card plays and only 4 take a target. The exceptions are mainly "choose a card" effects (7), plus revive, escape, max HP, play top cards, and making new potions. Things to model beyond "a 0-cost card":
- A potion stays usable when card play is blocked (Velvet Choker, Normality).
- Fairy is passive.
- Smoke Bomb is barred in boss fights.
- Sozu blocks getting potions, and Sacred Bark doubles their effect.

## Sources opened
- https://github.com/gamerpuppy/sts_lightspeed
- https://api.github.com/repos/gamerpuppy/sts_lightspeed/git/trees/master?recursive=1
- https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/include/combat/Player.h
- https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/include/combat/BattleContext.h
- https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/src/combat/BattleContext.cpp
- https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/src/combat/Player.cpp
- https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/src/combat/Monster.cpp
- https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/src/combat/Actions.cpp
- https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/src/combat/CardManager.cpp
- https://raw.githubusercontent.com/gamerpuppy/sts_lightspeed/master/include/constants/Potions.h
- https://slaythespire.wiki.gg/wiki/Relics
- https://slaythespire.wiki.gg/wiki/Events

The fandom Relics page returned HTTP 402. The wiki.gg Relics page gives names and rarities but no effects, so the relic effect lines come from my own knowledge of the game and were not checked against a page.
