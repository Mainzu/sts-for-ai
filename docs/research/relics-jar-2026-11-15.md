# Relics: jar reads for the combat and run parts (2026-11-15)

Read 2026-11-15 by the act1 relics session (a subagent decompiled the classes with `javap -c -p -constants` from the game's desktop-1.0.jar; offsets are bytecode offsets). Used for the combat parts of Busted Crown, Coffee Dripper, Cursed Key, Ectoplasm, Fusion Hammer, Sozu, Girya, Cultist Headpiece and Spirit Poop (`content/packs/act1-relics.json`), the Bottled relics, and the run-simulator spec's relic steps.

All 12 class names exist under com/megacrit/cardcrawl/relics/.

## Combat start order (AbstractPlayer / AbstractRoom bytecode)
1. `AbstractPlayer.preBattlePrep`: `CardGroup.initializeDeck(masterDeck)` (offset 145) -> hand/discard/exhaust cleared -> `energy.prep()` (210) -> monsters' usePreBattleAction (303) -> `applyPreCombatLogic()` (342) = relic `atPreBattle`.
2. `AbstractRoom.update` (offsets 247-319): `GainEnergyAndEnableControlsAction(energy.energyMaster)` (addToBottom, 247) -> `applyStartOfCombatPreDrawLogic()` (272) = relic `atBattleStartPreDraw` -> `DrawCardAction(gameHandSize)` (278) -> `EnableEndTurnButton` -> `applyStartOfCombatLogic()` (319) = relic `atBattleStart` (relics, then blights).
   So `atBattleStart` hooks (Girya, Bottled x3, CultistMask) are queued AFTER the DrawCardAction is queued; `atBattleStartPreDraw` runs before it. Girya's addToTop puts its actions at the front of the queue, i.e. they run before the opening draw action (draw action already in queue but addToTop goes ahead of it).
   Energy: opening energy = `energyMaster` read at offset 260 (energyMaster already includes +1 from boss relics).

## Bottled Flame / Bottled Lightning / Bottled Tornado
- IDs: "Bottled Flame", "Bottled Lightning", "Bottled Tornado". Tier UNCOMMON (ctor offset 5). No counter (uses `cardSelected` bool + public `card` field). Sound CLINK.
- Hooks overridden: onEquip, onUnequip, update, setDescriptionAfterLoading, atBattleStart, canSpawn, getCard, makeCopy, getUpdatedDescription.
- **In combat**: `atBattleStart` only does `flash()` + `addToTop(RelicAboveCreatureAction)` (offsets 1, 16). NO card is moved by the relic. The effect is in `CardGroup.initializeDeck` (called from `AbstractPlayer.preBattlePrep` before energy/pre-draw/draw):
  - Shuffle copy of master deck (`shuffleRng`, 20). For each card c: `if c.isInnate` -> list (64-76); else `if c.inBottleFlame || c.inBottleLightning || c.inBottleTornado` -> list (80-111); else placed in draw pile with `addToTop` (146).
  - Then every card in the list is `addToTop`ed on the draw pile (155-189) = bottled/innate cards sit on top, so the opening `DrawCardAction(gameHandSize)` draws them. (This is exactly innate treatment, flag-based, not relic-based: relic presence is not re-checked at combat start; the flag is cleared in `onUnequip`.)
  - If list.size() > `masterHandSize` (5) (193-202), `addToTurnStart(DrawCardAction(player, list.size() - masterHandSize))` (205-229) draws the overflow.
  - So all three bottled kinds are guaranteed in the opening hand, drawn by the normal turn-1 draw, i.e. AFTER pre-draw relics.
- **Outside combat**:
  - `onEquip` (Flame offset 12-111): if `masterDeck.getPurgeableCards().getAttacks().size() > 0` opens `GridCardSelectScreen` for 1 attack card (Lightning: `getSkills()`, Tornado: `getPowers()`); room phase set INCOMPLETE while choosing, COMPLETE after (update, 53-59). `update` (offsets 5-50) stores selected card in `this.card` and sets `card.inBottleFlame = true` (Lightning `inBottleLightning`, Tornado `inBottleTornado`). `getPurgeableCards` excludes Bottled-flagged/bad purge cards.
  - `onUnequip`: clears the flag on the master-deck copy (`getSpecificCard`, 14-27).
  - `canSpawn`: Flame: masterDeck has an ATTACK with rarity != BASIC (offsets 32-52); Lightning: same pattern with SKILL; Tornado: `CardHelper.hasCardType(POWER)` (3).
  - Flags are `AbstractCard.inBottleX` booleans; also referenced in classes: cards/AbstractCard, cards/CardGroup (initializeDeck, getGroupWithoutBottledCards, render*), characters/AbstractPlayer (bottledCardUpgradeCheck, 7154+), core/CardCrawlGame, events/shrines/Duplicator, events/shrines/FountainOfCurseRemoval (Flame/Lightning only), relics/DollysMirror, screens/MasterDeckViewScreen, screens/select/GridCardSelectScreen, saveAndContinue/SaveAndContinue + SaveFile. Tornado is not in FountainOfCurseRemoval. `bottledCardUpgradeCheck` re-bottles on upgrade of the card.
  - Deck edits: it only flags an existing card; no card added/removed. Not an energy/HP/gold effect.

## Girya
- ID "Girya", tier RARE, `counter` = number of lifts (initial `counter = 0`, ctor 14-16), `STR_LIMIT = 3`. Sound HEAVY.
- Hooks: atBattleStart, canSpawn, addCampfireOption.
- **In combat**: `atBattleStart` (0-61): `if counter != 0` -> `flash()`; `addToTop(ApplyPowerAction(player, player, new StrengthPower(player, counter), counter))` (11-43); `addToTop(RelicAboveCreatureAction)` (46-58). Strength = counter (0..3), applied at start of combat, runs ahead of the opening draw (addToTop).
- **Outside combat**: `addCampfireOption` (0-25) adds `LiftOption(counter < 3)` (usable only while counter < 3, i.e. cap 3 lifts). `LiftOption.useOption` adds `CampfireLiftEffect`; `CampfireLiftEffect.update` does `getRelic("Girya").counter += 1` at offset 73-78 (after flash), then RestRoom fadeIn. Lifting uses the campfire action for that rest site (one option per visit) like Rest/Smith.
  - `canSpawn` (0-84): false if `floorNum >= 48 && !Settings.isEndless`; counts relics that are PeacePipe, Shovel or Girya; spawns only if that count < 2.
  - Other classes holding "Girya": dungeons/AbstractDungeon (returnRandomNonCampfireRelic, 2100), helpers/RelicLibrary, relics/PeacePipe, relics/Shovel, screens/runHistory/RunPathElement, vfx/campfire/CampfireLiftEffect, ui/campfire/LiftOption (class ref).

## Busted Crown
- ID "Busted Crown", tier BOSS, no counter. Hooks: onEquip, onUnequip, changeNumberOfCardsInReward, updateDescription.
- **In combat**: `onEquip` `energy.energyMaster += 1` (offsets 7-12), `onUnequip` `-= 1`. Only effect in combat: +1 energy per turn (via energyMaster; no battle hook). Confirmed.
- **Outside**: `changeNumberOfCardsInReward(n)` returns `n - 2` (1-3): card rewards show 2 fewer cards (3 -> 1). Enforced via `AbstractRelic.changeNumberOfCardsInReward` called from reward generation; `RewardItem.claimReward` (offset 338-354) flashes it when opening the card reward screen. Classes with the string "Busted Crown": rewards/RewardItem, screens/custom/CustomModeScreen, trials/StarterDeckTrial.

## Coffee Dripper
- ID "Coffee Dripper", tier BOSS, no counter. Hooks: onEquip, onUnequip, canUseCampfireOption, updateDescription.
- **In combat**: energyMaster +1 on equip / -1 on unequip (offsets 7-12 / 7-12). Only effect. Confirmed.
- **Outside**: `canUseCampfireOption(opt)` (0-36): if `opt instanceof RestOption` (exact class name match) -> `opt.updateUsability(false)`; return false (rest/heal option disabled at campfires); otherwise true. Enforced in the relic itself, called by the campfire UI. No other class holds the string "Coffee Dripper".

## Cursed Key
- ID "Cursed Key", tier BOSS, no counter. Hooks: onEquip, onUnequip, justEnteredRoom, onChestOpen, updateDescription.
- **In combat**: energyMaster +1 / -1 (onEquip/onUnequip offsets 7-12). Only combat effect. Confirmed.
- **Outside**: `onChestOpen(boolean bossChest)` (0-48): if `!bossChest` -> `topLevelEffects.add(ShowCardAndObtainEffect(AbstractDungeon.returnRandomCurse(), ...))` (adds a random curse to the deck) + RelicAboveCreatureAction addToTop. `justEnteredRoom` only sets `pulse = true` when entering a TreasureRoom. The string "Cursed Key" also appears in characters/AbstractPlayer (starting relic list for the "Cursed Run" mod, offset 18). Chest opening is the only restriction.

## Ectoplasm
- ID "Ectoplasm", tier BOSS, no counter. Hooks: onEquip, onUnequip, canSpawn, updateDescription.
- **In combat**: energyMaster +1 / -1. Confirmed. (Also gold gain blocked everywhere, including in combat, see below.)
- **Outside (and in)**: enforced in `AbstractPlayer.gainGold(int)` (offsets 0-20): `if hasRelic("Ectoplasm") { getRelic().flash(); return; }` -> no gold from any source (rewards, events, relics) while owned. `loseGold`/spending is unchanged. `canSpawn`: `actNum <= 1` only (act 1 boss relic). Classes with "Ectoplasm": characters/AbstractPlayer, helpers/RelicLibrary.

## Fusion Hammer
- ID "Fusion Hammer", tier BOSS, no counter. Hooks: onEquip, onUnequip, canUseCampfireOption, updateDescription.
- **In combat**: energyMaster +1 / -1. Confirmed.
- **Outside**: `canUseCampfireOption(opt)` (0-36): `opt instanceof SmithOption` (exact class) -> `updateUsability(false)`, return false (no upgrade at campfires; shop/other upgrades unaffected). No other class holds the string.

## Sozu
- ID "Sozu", tier BOSS, no counter. Hooks: onEquip, onUnequip, updateDescription.
- **In combat**: energyMaster +1 / -1 (offsets 7-12). Only effect. Confirmed. Potions already held can still be used.
- **Outside (and in)**: potion obtaining is blocked at the source, each class checks `player.hasRelic("Sozu")` and flashes instead:
  - actions/common/ObtainPotionAction.update (offset 14-30; covers in-combat potion gain)
  - vfx/ObtainPotionEffect.update (3-21)
  - rewards/RewardItem.claimReward (147-166; potion reward is flashed and the claim returns true)
  - shop/StorePotion.purchasePotion (3-22; returns before charging gold)
  - potions/EntropicBrew.use (48-70; no slots filled)
  - events/city/KnowingSkull.obtainReward (130-)
  - helpers/RelicLibrary (registration)
  `AbstractPlayer.obtainPotion` itself has no Sozu check. Not blocked: using/discarding potions.

## Cultist Headpiece (class CultistMask)
- ID is `"CultistMask"` (class const), tier SPECIAL, no counter. Hooks: atBattleStart, getUpdatedDescription, makeCopy.
- **In combat**: `atBattleStart` (0-52): `flash()`; `addToBot(RelicAboveCreatureAction)` (16); `addToBot(SFXAction("VO_CULTIST_1A"))` (29); `addToBot(TalkAction(true, DESCRIPTIONS[1], 1.0f, 2.0f))` (49). Pure sound + speech bubble; no stats. Confirmed.
- **Outside**: none. Classes with "CultistMask": events/shrines/FaceTrader (a Face Trader reward), helpers/RelicLibrary.

## Spirit Poop
- ID "Spirit Poop", tier SPECIAL, no counter, class has only ctor, getUpdatedDescription, makeCopy. No hooks, no effect in or out of combat. Classes with the string: events/shrines/Bonfire (offering reward), screens/GameOverScreen (score-related check).

## Surprises
- All three Bottled relics' combat atBattleStart does nothing but a flash; the real effect lives in `CardGroup.initializeDeck` and is innate-style (card placed on top of draw pile before turn-1 draw; overflow draws are added at turn start if more than 5 innate/bottled cards).
- Ectoplasm blocks `gainGold` globally (also in-combat gold gains), not only at map/rewards.
- Sozu has no check in `obtainPotion`; blocking is spread over six callers.
- Coffee Dripper / Fusion Hammer restrictions live in the relics' own `canUseCampfireOption`, checked by the campfire UI; Girya's lift counter is incremented by `CampfireLiftEffect`, not the relic, and Girya is gone from the pool after floor 48 outside Endless.
- Cursed Key: curse only on non-boss chests (`onChestOpen(false)`), and nothing at shops/rewards.
