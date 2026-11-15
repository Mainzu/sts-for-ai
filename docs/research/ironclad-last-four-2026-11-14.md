# The last four Ironclad cards: game behaviour and missing engine pieces (2026-11-14)

Research for `docs/specs/ironclad-last-four.md`. One reader per card read its class in the installed jar and the engine;
a skeptic per card re-read both and tried to refute it. Where they differ, the skeptic's correction wins unless the build session's own read shows otherwise.

## Battle Trance

- **Size:** S
- **Game:** Battle Trance (com.megacrit.cardcrawl.cards.red.BattleTrance). From the constructor `<init>`: cost 0, SKILL, RED, UNCOMMON, target NONE, baseMagicNumber 3. `upgrade()` calls upgradeMagicNumber(1), so the upgraded card draws 4. Cost does not change and the card does not exhaust.

`use(p, m)` queues two actions, both with addToBot, in this order:
1. `new DrawCardAction(p, magicNumber)`, which draws 3 (4 upgraded).
2. `new ApplyPowerAction(p, p, new NoDrawPower(p))`.

Because the draw is queued first, it resolves before No Draw exists, so the card's own draw always goes through.

NoDrawPower (com.megacrit.cardcrawl.powers.NoDrawPower):
- POWER_ID "No Draw", type DEBUFF, amount -1 (no stack count).
- Being a DEBUFF, it can be blocked by the player's Artifact (ApplyPowerAction checks "Artifact" on DEBUFF) and removed by debuff removal (Orange Pellets).
- `atEndOfTurn(isPlayer)`: when isPlayer, it queues addToBot `RemoveSpecificPowerAction(owner, owner, "No Draw")`. So it lasts until the end of the player's turn and never affects the next turn's draw.

How it works: DrawCardAction.update() checks `AbstractDungeon.player.hasPower("No Draw")` first, before the amount check, the deck/discard sizes and the shuffle. If the power is there, it flashes the power and calls endActionWithFollowUp(). The whole draw is cancelled: no cards, no shuffle, no onShuffle effects.

Every draw that goes through DrawCardAction is therefore cancelled for the rest of the turn: Pommel Strike, Shrug It Off, Dark Embrace and exhaust draws, Gambler's Brew, and so on. EvolvePower.onCardDraw also checks "No Draw" itself and queues nothing. The result is the same, since its DrawCardAction (addToBot) would be cancelled anyway.

Stacking: a second Battle Trance makes ApplyPowerAction call stackPower(-1), giving amount -2. This has no effect on play.
- **Missing in the engine:** The general word: a replacement event on draws. Add `Replaced::Draw` (JSON `"event": "Draw"`) to the existing replacement rows, accepting only `Replace::Cancel` (refuse Cap/Add/Multiply/AtLeast/upTo/power at load until content needs them). It means "if the owner (the player) would draw, the draw doesn't happen". This is a replacement on draws, the way the inventory's C9 describes it. It is not a one-card flag like `forbids`.

Engine changes:
1. Parsing. Add `Some("Draw") => Replaced::Draw` to `registry.rs` `parse_replacement`, and add "Draw" to the event-name list (~line 3252, in `element_names`). Add its words to `content/wording.json`; `engine/tests/wording.rs` will name any miss.
2. Firing. At the very top of `chance.rs` `request_draw(n)`, before `self.pending` is taken: if the player holds a power with a `Replaced::Draw` Cancel row, run that row's `then` and return. Leave any pending `ChanceEvent::Draw` untouched and skip `fire_shuffled`. This works because every in-combat draw already goes through `request_draw`: `Effect::Draw` in `do_effect`, `DrawPicked`, the owed `OwedKind::Draw`, and the `CardDrawn`/`CardExhausted` hooks.
   - Checking at request time, not at chance resolution, gives the game's order. Battle Trance's own Draw is requested before the Apply row runs, so it goes through. Evolve and Dark Embrace draws are requested after the card has resolved, so they are cancelled.
   - The turn-start draw needs no check, because the power is gone by OwnerTurnEnd.
   - Optionally keep a precomputed "powers with a Draw replacement" list, like `draw_hook_powers`, so draws don't scan every power.

Draft pack entries for content/packs/act1-ironclad.json, once the word exists:

Power:
{"id": "NoDraw", "debuff": true, "hooks": [{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": ["RemoveSelf"]}], "replacements": [{"event": "Draw", "action": "Cancel"}]}

Card (also add "Battle Trance" to the Ironclad pool):
{"id": "Battle Trance", "cost": 0, "type": "Skill", "effects": [{"Draw": 3}, {"Apply": {"power": "NoDraw", "amount": 1, "target": "Me"}}], "upgrade": {"effects.0.Draw": 1}}

The existing `"debuff": true` row already covers Artifact and Orange Pellets' RemoveDebuffs. OwnerTurnEnd + RemoveSelf matches the game's atEndOfTurn(isPlayer) removal; Rage and Entangled already use this pattern.

Tests to add:
- Battle Trance draws 3 and then a Pommel Strike draws 0.
- A draw needing a reshuffle still shuffles when it is Battle Trance's own draw, but never once No Draw is held.
- Evolve plus a drawn Status draws nothing after Battle Trance.
- Artifact cancels No Draw.
- Next turn draws 5.
- **Shares the piece with:** The same NoDrawPower serves the Silent's Bullet Time if Silent content is added. The new draw event also handles every other draw source while No Draw is held, with no change to those cards: Pommel Strike, Shrug It Off, Warcry's draw, Dark Embrace and Evolve hooks, Gambler's Brew, and the relic draws during the turn. It also opens `Replaced::Draw` for later draw-changing replacements; StS1 Act 1 needs none besides Cancel.
- **Risk:** Low.
1. Where the check goes. It must be at `request_draw` entry and must not consume `self.pending`. A check at chance resolution would wrongly cancel Battle Trance's own already-requested draw, because the request is pending while the Apply row runs. A check that drops the pending draw would lose cards the game had already drawn.
2. Stacks. The game's amount is -1 and stacking is meaningless. With amount 1, two Battle Trances give the engine stacks 2 instead of 1, so two afterstates that play identically stay distinct. The impact is small. Treating the power's stacks as "present or not" would fix it if that matters.
3. Draw estimates. agent.rs and heuristic.rs still value Effect::Draw at face value while No Draw is held. Only the search's estimates are affected; the rules stay correct.

No scratch files were created.

## Juggernaut

- **Size:** M
- **Game:** Juggernaut (com.megacrit.cardcrawl.cards.red.Juggernaut). Constructor: cost 2, POWER, RED, RARE, target SELF, baseMagicNumber 5. upgrade(): upgradeMagicNumber(2), so 5 becomes 7, and the cost stays 2. use(p,m): addToBot(ApplyPowerAction(p, p, new JuggernautPower(p, magicNumber), magicNumber)). Stacks add up like any power (amount N).

JuggernautPower.onGainedBlock(float blockAmount): if blockAmount > 0 it calls flash() and then addToBot(new DamageRandomEnemyAction(new DamageInfo(owner, amount, DamageType.THORNS), SLASH_HORIZONTAL)). It has no other hooks.

Who calls it: AbstractCreature.addBlock(int amount). For the player it first runs each relic's onPlayerGainedBlock(tmp). If tmp > 0 it then runs each of the owner's powers' onGainedBlock(tmp) in order, then every monster power's onPlayerGainedBlock, and only after that does currentBlock += floor(tmp). So the hook fires once per addBlock call with a positive amount, whatever the source: card GainBlockAction (Defend, Iron Wave, Shrug It Off, True Grit), Metallicize at turn end, relic block, and Entrench (DoubleYourBlockAction calls addBlock). A gain of 0 does not fire it. A gain of 8 fires one hit of N, not one per point of block.

DamageRandomEnemyAction.update(): it picks the target only when the action runs, with getMonsters().getRandomMonster(null, true /*aliveOnly*/, AbstractDungeon.cardRandomRng). If that returns null nothing happens. Otherwise it calls addToTop(new DamageAction(target, info, effect)). The DamageInfo is THORNS type and nothing calls applyPowers on it, so the damage is a flat N: Strength, Weak and Vulnerable do not change it, but enemy block absorbs it. This is the same damage type as the Thorns power.

Order: the hit is added to the BOTTOM of the action queue. During a card it therefore lands after all of that card's remaining actions, which use() queued earlier. Example: Iron Wave queues GainBlock and then Damage, so Juggernaut's hit comes after Iron Wave's damage. The target is rolled at that moment, from the enemies still alive. A THORNS hit is not a NORMAL attack, so Curl Up does not react to it. That makes the order observable: Iron Wave hits first and triggers Curl Up, and then Juggernaut's hit lands on the Curl Up block. At turn end the hit queues behind Metallicize's GainBlock and the other turn-end actions.
- **Missing in the engine:** Three general pieces. Each one is reusable, and none is specific to Juggernaut.

1. A new Trigger::OwnerGainedBlock (engine/src/hooks.rs), the game's onGainedBlock. It fires once for each block gain of the owner whose amount, after Dexterity, Frail and relic modifiers, is greater than 0. It must fire from every site where the player gains block in engine/src/state.rs: gain_block (line ~4461), the hook and turn-end Block sites (~2611, 2666, 2698, 3402, 3477), and an Entrench-style doubling. Block kept by turn-start retention is not a gain, so it does not fire. Hook effects are scaled by stacks, as Metallicize's are. One check: route every player block gain through a single function (gain_block or a new add_block) that fires the trigger, so no gain site can miss it. Later users: Wave of the Hand and other onGainedBlock powers.

2. A new Target::RandomOpponent (engine/src/effects.rs Target) for PlainDamage, meaning one living enemy picked at random, chosen when the hit is paid. Today's RandomDamage uses attack(), so Strength applies, and runs_outside_a_card (registry.rs ~2515) refuses it in hooks. Juggernaut's hit is THORNS, so it has to go through PlainDamage's path, the same one the Thorns power's PlainDamage uses. The wording for the new target goes in content/wording.json and registry::element_names().

3. Hooks owe the random target through the existing Owed queue (state.rs ~989). Add OwedKind::PlainHit { amount }, paid by request_random_hit with a plain flag. chance.rs random_hit currently calls self.attack outside a card, so ChanceEvent::RandomTarget needs a plain bool, or a separate RandomPlainTarget event; the codec needs the matching tag. The queue also needs an ordering rule: an entry owed while a card is in play waits until that card has fully resolved, as the game's addToBot does. That generalises the existing wait flag, which today only covers RelicPick and RelicOffer. Right now run_opts pays owed work before the card's next effect, which would put Juggernaut's hit before Iron Wave's own damage. At turn end the existing EndingTurn owed pause already covers Metallicize.

Draft once these exist. In content/powers.json:
{"id": "Juggernaut", "debuff": false, "hooks": [{"trigger": "OwnerGainedBlock", "condition": "Always", "effects": [{"PlainDamage": {"amount": 1, "target": "RandomOpponent"}}]}], "statics": [], "replacements": []}

In content/cards.json (pack card):
{"id": "Juggernaut", "cost": 2, "type": "Power", "class": "Ironclad", "exhaust": false, "ethereal": false, "retain": false, "innate": false, "tags": [], "effects": [{"Apply": {"power": "Juggernaut", "amount": 5, "target": "Me"}}], "rows": [], "turn_end": [], "upgrade": {"effects.0.Apply.amount": 2}}
- **Shares the piece with:** OwnerGainedBlock covers the other onGainedBlock users (Wave of the Hand for Watcher; any later block-reactive power or relic). Target::RandomOpponent on PlainDamage, paid through Owed, covers any hook that does flat random-target damage: Thorns-type random hits from relics and powers, and potions or relics that hit a random enemy outside a card. The rule that owed work waits for the card to finish is the general addToBot order for every hook that owes random work during a card, so it also corrects the timing of Dead Branch, Mummified Hand and Warped Tongs when they trigger mid-card (check this against their specs). Inventory blocker C13 goes away. C14 Reaper is separate (heal by unblocked damage).
- **Risk:** The biggest risk is ordering. Today the Owed queue pays right away, before the card's next effect. Changing it to wait until the card has resolved could alter the existing step-5 relics (Dead Branch, Mummified Hand, Warped Tongs) if their game timing differs, so verify each one against the jar before applying the rule to all of them. Another option is a per-entry flag that only new entries use. Every block site must fire the trigger: there are about six player block-gain paths in state.rs plus the fast-path block code in search.rs, agent.rs and heuristic.rs, and a miss gives silently wrong values. A hook that fires inside a block gain inside a hook needs its recursion bounded; the existing IN_OWNER_APPLIED-style guard is a model. The OWED_CAP of 8 could be exceeded by many block gains in one card, but entries of the same kind merge by n, and the hit amount is fixed per stack count. The amount must be read when the block is gained, not when the hit is paid, or Owed must store the amount. Hashing and the codec need the new owed kind and chance tag; states with no owed work must still hash as before. One unverified point: whether every monster on-hit power (Angry, Sharp Hide and others) ignores THORNS the way the engine's PlainDamage path does. Check this against the jar.

## Reaper

- **Size:** S
- **Game:** Reaper (com.megacrit.cardcrawl.cards.red.Reaper, read from the installed desktop-1.0.jar with javap).

Card data, from the Reaper constructor: cost 2, ATTACK, RED, RARE, target ALL_ENEMY. baseDamage 4, isMultiDamage = true, exhaust = true, and the HEALING tag. Reaper.upgrade calls upgradeDamage(1), so the upgraded card deals 5. Cost and exhaust do not change on upgrade.

Reaper.use queues two actions at the bottom: a VFXAction(ReaperEffect), then new VampireDamageAllEnemiesAction(p, multiDamage, damageTypeForTurn, NONE). AbstractPlayer.useCard then queues UseCardAction, which exhausts the card. That means the card exhausts before the heal described below.

VampireDamageAllEnemiesAction.update, in order:
1. Each player power's onDamageAllEnemies(damage[]) runs. No Act 1 Ironclad power uses it.
2. For each monster i in room order that is not isDying, has currentHealth > 0 and is not isEscaping: it calls m.damage(new DamageInfo(source, damage[i], NORMAL)). damage[i] is the card's multiDamage for that slot, so Strength, Weak, Vulnerable and the other card-damage modifiers apply per target. Then, if m.lastDamageTaken > 0, it adds it to a running total.
3. AbstractMonster.damage sets lastDamageTaken = Math.min(damageAmount, currentHealth). It does this after decrementBlock, onAttackedToChangeDamage, wasHPLost and onAttacked, and before HP drops. So each enemy counts the HP it actually lost: damage after block, capped at the HP it had left. Overkill and blocked damage give nothing.
4. If the total is above 0, it queues HealAction(source, source, total) at the bottom, after a WaitAction(0.3) when FAST_MODE is off. The heal goes through AbstractCreature.heal, so the player's relics onPlayerHeal apply (Magic Flower, the engine's heal_scale). It heals up to max HP. A total of 0 queues no heal.
5. If areMonstersBasicallyDead(), it calls GameActionManager.clearPostCombatActions. That method keeps HealAction, GainBlockAction and UseCardAction, and removes the rest. So when Reaper kills the last enemy, the heal still happens and changes the HP the fight ends on.

The HEALING tag keeps Reaper (and Feed) out of the in-combat random pools. engine/tests/discovery.rs already leaves both out ("no Feed, no Reaper"), so Reaper must not be added to the Ironclad pool in content/packs/act1-ironclad.json when it loads.

The FlyingOrbEffect loop (lastDamageTaken/2 orbs, at most 10) is visual only.
- **Missing in the engine:** Two general pieces are needed. Neither is specific to Reaper.

(1) A new Quantity::DamageDealt: the HP the user's most recent damage effect took from all its targets, summed over targets and hits, each hit capped at that target's HP before the hit. The game's per-hit value is lastDamageTaken = min(damage after block, currentHealth).
- State: a transient i16 field `dealt` in CombatState.
- Reset it to 0 when Damage, ScaledDamage, PlainDamage or RandomDamage starts for an actor.
- In State::attack (and in take_damage for plain damage), add lost.min(before.max(0)), where `before` is the target's HP before the hit. Note that take_damage now returns `lost` uncapped: the HP floor clamps HP, not the returned value. So the cap must be added here.
- Zero it in finish_card and at the end of a monster move. That way afterstates that differ only in a stale `dealt` still compare equal (docs/concept.md). It must stay in the hash while a card is mid-play, because a pick can pause between the damage and the read.
- Wiring: add it to the amount() parser in registry.rs ("DamageDealt"), to the quantity name list (registry.rs around line 3233), to State::quantity, and give it words in content/wording.json. The wording test catches a miss.
- The same word covers Wallop (BlockOf DamageDealt) and Shelled Parasite's Suck, a monster's HealOf DamageDealt on the player (that one is VampireDamageAction).

(2) A heal still runs after a kill ends the fight. Today the PlayingCard step `e =>` in state.rs calls check_over() after each effect. Once the last monster dies, the stage becomes Over and the card's later effects never run. Following clearPostCombatActions, the general rule is: when an effect wins the fight mid-card, the card's remaining Heal and HealOf rows still run before the result and score are fixed. Block and the rest are dropped, since they cannot change the score. Concretely: check_over() defers a win while the card in play has Heal or HealOf rows left; the loop runs only those, then ends the fight.

Draft entry for content/packs/act1-ironclad.json once (1) and (2) exist. Leave Reaper out of the "Ironclad" pool:
{"id": "Reaper", "cost": 2, "type": "Attack", "exhaust": true, "effects": [{"Damage": {"amount": 4, "hits": 1, "target": "AllOpponents"}}, {"HealOf": {"base": 0, "k": 1, "of": "DamageDealt"}}], "upgrade": {"effects.0.Damage.amount": 1}}

Tests to add:
- 4 damage to two enemies, one with 3 block and one with 2 HP. The total is 1 + 2 = 3 healed.
- A kill of the last enemy still heals.
- Magic Flower makes the heal x1.5.
- A heal of 0 when everything is blocked.
- Upgraded Reaper deals 5.

bound.rs already counts HealOf as healing (line 71), so no change is needed there.
- **Shares the piece with:** Quantity::DamageDealt is the general word for "an amount equal to the unblocked damage dealt". It works with HealOf (Reaper; Shelled Parasite's Suck as a monster move), BlockOf (Wallop) and ApplyOf. The rule that a heal still runs after a kill applies to any card or move that heals after dealing damage. It follows the game's clearPostCombatActions, which keeps HealAction. Nothing in it is specific to Reaper. It is not the same as Feed (C-code for a kill: max HP on a fatal hit) or Juggernaut (C13), but a later "on fatal" word could sit next to it in the same per-effect accumulator. The in-combat pool exclusion for HEALING already holds through the hand-listed pool and the discovery test.
- **Risk:** 1) Capping: take_damage returns `lost` without capping it at the HP the target had. If the cap is left out, overkill heals too much (for example, 4 damage into a 2-HP louse would heal 4 instead of 2).
2) Kill ordering: without piece (2), a Reaper that kills the last enemy silently loses its heal. That changes the score (2 - HP lost/100) and so what search and the solver choose. The deferred-win path must not let any non-heal effect run after the win, and must not fire combat-end hooks twice.
3) Stale `dealt` in hashing and equality: if it is not zeroed at card or move end, equal afterstates would hash differently and transposition merging would get worse.
4) Order versus exhaust: in the game, UseCardAction (the exhaust, which fires Feel No Pain and Dark Embrace) runs before the HealAction. In the engine, effects run before finish_card exhausts the card. This differs, but nothing in Act 1 depends on whether the exhaust or the heal comes first.
5) Hooks that change damage after block (Intangible, Torii-like rows on monsters) must already be applied before the value is counted. The engine's take_damage order matches the game here, so the count after after_block is right.
Nothing was written to the scratch folder, so there is nothing to clean up.

## Dual Wield

- **Size:** M
- **Game:** Dual Wield (com.megacrit.cardcrawl.cards.red.DualWield). Constructor `<init>`: cost 1, SKILL, RED, UNCOMMON, target NONE, baseMagicNumber = magicNumber = 1. upgrade(): upgradeMagicNumber(1), so 2 copies, and the upgrade description. Cost stays 1. use(): addToBot(new DualWieldAction(p, magicNumber)). The card has no other effects.

DualWieldAction.update() (actions.unique.DualWieldAction), first tick:
1. It goes through the hand and puts every card that fails isDualWieldable into cannotDuplicate. isDualWieldable(c) is true only when c.type is ATTACK or POWER, so Skills, Statuses and Curses can't be picked. Dual Wield itself is in play, not in the hand.
2. If every card in hand failed the test (none eligible, or an empty hand), the action ends and nothing happens.
3. If exactly ONE card is eligible (hand.size - cannotDuplicate.size == 1, counting every copy, so two Strikes means two eligible cards), there is no choice screen. The action adds addToTop(MakeTempCardInHandAction(c.makeStatEquivalentCopy())) dupeAmount times. The original card stays in hand.
4. Otherwise it removes the ineligible cards from the hand (hand.removeAll(cannotDuplicate)) and opens handCardSelectScreen.open(TEXT[0], 1, false, false, false, false): pick exactly 1 card, and zero isn't allowed. The branch at offset 255 (hand.size == 1 after removeAll) can't be reached, because case 3 already covers it.
5. After the pick (wereCardsRetrieved == false, offsets 330-436): for the selected card s, the action adds addToTop(MakeTempCardInHand(s.makeStatEquivalentCopy())) once to replace s, which the select screen took out of the hand, then adds dupeAmount more of the same. Then returnCards() puts the ineligible cards back on top of the hand right away, and selectedCards is cleared. So the picked card object is replaced by a stat-equivalent copy, and dupeAmount copies are added. In total the hand gains dupeAmount copies of the picked card.
6. Order: the actions are pushed with addToTop, so the dupes resolve first and the replacement last. They all run before anything else queued.

MakeTempCardInHandAction.update: a copy that arrives while the hand holds 10 cards goes to the discard pile (addToDiscard; the bipush 10 check). Example: Dual Wield+ with 9 cards in hand. After the pick, 8 remain; the two dupes fill it to 10, and the replacement of the original goes to the discard pile. The resulting state is the same as "hand gains min(n, 10 - size) copies and the rest go to the discard pile", because every copy is stat-equivalent. The constructor also upgrades the copy when the player has MasterRealityPower and the card isn't a Status or Curse. That's Watcher content and doesn't matter for Ironclad.

AbstractCard.makeStatEquivalentCopy copies these fields: timesUpgraded (by calling upgrade()), name, target, upgraded, baseDamage, baseBlock, baseMagicNumber, cost, costForTurn, isCostModified, isCostModifiedForTurn, misc, freeToPlayOnce and the bottle flags. So copies keep upgrades, combat-cost changes (Madness, Snecko), Rampage's grown damage and a cost-0-this-turn mark.
- **Missing in the engine:** Two general pieces are missing. Neither is specific to Dual Wield.

(1) A type filter on any Pick. Add `of: TypeMask` (a u8 bitset over CardType, default = all types) to Effect::Pick and to state.rs `Pick`. pick_source (state.rs ~1899) drops candidates whose def().ty isn't in the mask, the same way UpgradeFromHand drops cards that can't be upgraded. Dual Wield needs Attack|Power. The filter fits any later "choose an X card" card: Secret Technique and Secret Weapon (by type from the draw pile), Nightmare, and Forethought or Setup variants.

(2) A pick that copies the chosen card: `PickKind::CopyInHand`, with the copy count `copies: u8` stored on Pick and Effect::Pick. It can't use `n`, because `n` is how many cards are picked. On Choose(c), the card stays in hand and the hand gains `copies` copies of c (the same CardId, so the variant carries upgrades, combat cost and Rampage damage), with the overflow going to the discard pile through the existing AddCard PileKind::Hand path (state.rs ~3629).

The cost-0-this-turn mark: when every copy of c in hand is marked (the rule upgrade_in_hand uses at state.rs ~3748), add the copies first, then call mark_free_in_hand on each one that stays in hand. This matches the game, where makeStatEquivalentCopy copies costForTurn.

The run loop needs one more case, like the Armaments case at state.rs ~2511: when the filtered source has a single distinct candidate, the pick resolves at once (the game's no-screen branch). When no card is eligible, the existing "nothing to pick" path skips the effect.

Work to wire it up:
- registry.rs Pick loader: parse "of" as a list of type names and "copies" (at least 1, a load error on any kind other than CopyInHand). Add CopyInHand to the element_names "pick" list at registry.rs:3234, and add "of" and "copies" too if fields are listed there.
- content/wording.json: an entry for CopyInHand, e.g. "choose {of} card in your hand and add {copies|copy} of it into your hand".
- codec.rs: a pick kind byte of 9, plus a copies byte and an `of` byte. Older encodings stay unchanged.
- py/src/features.rs:1150: a `pick_copy` column, or no column, as HandToTop has.
- extending.md: document it in the costs-0 section and the picks section.

Draft card JSON once these exist:
{"id": "Dual Wield", "cost": 1, "type": "Skill", "effects": [{"Pick": {"kind": "CopyInHand", "n": 1, "exact": true, "of": ["Attack", "Power"], "copies": 1}}], "upgrade": {"effects.0.Pick.copies": 1}}
- **Shares the piece with:** The type filter (`of` on Pick) is useful for every "choose an <type> card" pick. In other characters' and colorless sets that includes Secret Technique and Secret Weapon (draw pile), Nightmare's choice, and type-restricted Forethought, Setup and Meditate variants. It can also express the existing UpgradeFromHand-style eligibility in a general way. CopyInHand with `copies` covers any "add N copies of a chosen hand card" (Nightmare would also need a delay until next turn). Among Act 1 Ironclad cards only Dual Wield uses it. It reuses AddCard's hand-overflow path and the mark_free_in_hand rule that upgrade_in_hand already follows. Battle Trance (C9), Juggernaut (C13) and Reaper (C14) share nothing with this card.
- **Risk:** 1. The cost-0-this-turn mark. Choose(c) picks by CardId, so when the hand holds both a marked and an unmarked copy of c, the player can't choose to copy the marked one. In the game that choice gives copies+1 marked cards. With the proposed rule (copy unmarked unless every copy of c is marked), the engine only produces the "picked the unmarked one" outcome. This is the same kind of limit already listed in extending.md for True Grit and HandToTop. Also, a copy that overflows into the discard pile loses its mark (an existing known limit).
2. Format changes. The codec gets a new pick kind byte and extra bytes. The net features need a decision on whether to add a column, because a new column changes the layout. Pinned jobs aren't affected, but any saved-state reader must accept kind 9.
3. The single-candidate auto-resolve must compare distinct CardIds (and marks), not counts. The game opens the screen for two identical Strikes, but the result is the same, which is fine under the afterstate rule.
4. Overflow equivalence holds only because every copy is stat-equivalent. A future per-instance state beyond the free mark (e.g. a per-copy counter held outside the CardId) would need to be carried onto the copies too.
5. Master Reality (Watcher) would upgrade the copies. If that is ever modelled, it must apply on this path as well as on AddCard.

## Skeptic checks

The skeptics' verdicts, in the order the checks finished.

- **confirmed.** I tried to refute the research and could not. The game facts hold, Battle Trance's piece is missing, and size S is right. I have two small improvements to the design and one note.

Game facts checked against the jar with javap:
- BattleTrance `<init>`: cost 0, SKILL, RED, UNCOMMON, target NONE, magic number 3.
- BattleTrance `upgrade()` calls upgradeMagicNumber(1).
- BattleTrance `use()`: addToBot(DrawCardAction(p, magicNumber)) first, then addToBot(ApplyPowerAction(p, p, NoDrawPower(p))).
- NoDrawPower `<init>`: ID "No Draw", DEBUFF, amount -1.
- NoDrawPower.atEndOfTurn(isPlayer): when isPlayer is true, it addToBot's RemoveSpecificPowerAction(owner, owner, "No Draw").
- DrawCardAction.update(): after clearing the draw history, its first check is hasPower("No Draw"), which leads to flash() and endActionWithFollowUp(). That check comes before the amount check, the pile sizes and the shuffle, so no cards are drawn and no shuffle happens.

Engine facts checked:
- Nothing for No Draw exists today. act1-inventory.md lists Battle Trance as C9 and still missing.
- Every draw goes through `chance.rs` `request_draw`. The callers are the turn-start draw (state.rs ~2770), `OwedKind::Draw` (~3342) and `Effect::Draw` in do_effect (~3566).
- DrawPicked also goes through it: state.rs ~2532 calls do_effect(Effect::Draw(hit)). That is correct for the game, because Gambler's Brew queues a DrawCardAction.
- Pack powers already accept `replacements` and `debuff` (POWER_STRUCTURE_KEYS, registry.rs:1969).
- Entangled (act1-monsters.json) uses OwnerTurnEnd plus RemoveSelf, the pattern the draft power copies.
- `parse_replacement` (registry.rs:2103) and the `replacement_event` list in element_names (~3252) are where "Draw" goes. Its words also go in wording.json.
- Checking at request time gives the game's order, Evolve included. Battle Trance's own draw is requested, and may be left pending, before the Apply row runs. A drawn Status then fires Evolve, whose request comes after No Draw is applied and is cancelled. That matches the game: Evolve checks before No Draw exists and queues a draw, and that draw is cancelled once No Draw is applied.

Improvements:
1. Don't write a separate loop. Reuse the existing generic `replaced(owner, event, amount)` (state.rs:4191). At the top of `request_draw`, put `if self.replaced(Who::Player, Replaced::Draw, n as i16).is_none() { return; }` before `self.pending` is taken. `replaced_of` already scans REPLACEMENT_POWERS plus the pack powers, runs `then` and returns None on Cancel. It would also make Cap, Add and the other actions work on draws for free, so refusing them at load is optional.
2. The research says the turn-start draw "needs no check". The check at the top of `request_draw` will run there anyway. That is harmless, because the power is gone by then.

Note: the risks the research lists (stacks 1 vs the game's -1 making afterstates differ, and the agent and heuristic still valuing draws while No Draw is held) are real and minor. I created no scratch files.

- **partly.** Nearly all of it holds up when I re-read the jar and the engine. One game fact is wrong: the Curl Up example.

**Confirmed in the jar**
- **Juggernaut card:** the constructor sets cost 2, POWER, RED, RARE, SELF and baseMagicNumber 5. `upgrade()` calls `upgradeMagicNumber(2)`. `use()` addToBots an `ApplyPowerAction` with `JuggernautPower`.
- **`JuggernautPower.onGainedBlock(float)`:** if the amount is above 0 it calls `flash()`, then addToBots a `DamageRandomEnemyAction` with `DamageInfo(owner, amount, THORNS)`. The amount is read at the moment of the gain.
- **`DamageRandomEnemyAction.update()`:** it calls `getRandomMonster(null, true, cardRandomRng)`. If that returns null nothing happens; otherwise it addToTops a `DamageAction`.
- **`AbstractCreature.addBlock(int)`:** relic `onPlayerGainedBlock` runs first. If the amount is still above 0, the owner's powers' `onGainedBlock` run, then every monster power's `onPlayerGainedBlock`, and only then `currentBlock += floor`. One addition: the relic and power calls both sit inside the `if (isPlayer)` branch, so a monster's own `onGainedBlock` never fires. The trigger should be player-only, or say that it is.
- **THORNS against monster powers (the open question in "risk"):** `AngryPower.onAttacked` ignores HP_LOSS and THORNS. `PlatedArmorPower.wasHPLost` ignores HP_LOSS and THORNS. `MalleablePower.onAttacked` needs NORMAL. `CurlUpPower.onAttacked` needs NORMAL. `SharpHidePower` reacts to cards being played (`onUseCard`), not to hits. Those ones agree with a plain, non-attack path. Still unchecked: damage reactions that don't look at the damage type, such as the Guardian's Mode Shift counter and the slime split threshold.

**Wrong: the Curl Up example**
The research says Juggernaut's hit "lands on the Curl Up block". The jar shows the reverse.
- `IronWave.use` addToBots GainBlock, Wait, VFX, then Damage.
- When the GainBlock runs, Juggernaut's `DamageRandomEnemyAction` is addToBot'd behind Iron Wave's queued Damage.
- When Iron Wave's Damage hits, `CurlUpPower.onAttacked` addToBots ChangeState, GainBlockAction and RemoveSpecificPower. Those go behind Juggernaut's hit, which is already queued.
- So Juggernaut's hit lands before Curl Up's block exists. The target is rolled after Iron Wave's damage, and the hit is not reduced by Curl Up.

The ordering rule the research proposes (the hit waits until the card's queued work is done, but not until reactions to that work are done) gives this correct result. The example and any test built from it should expect the hit to land before Curl Up's block.

**Confirmed in the engine**
- `Trigger` in `engine/src/hooks.rs` has no OwnerGainedBlock.
- `Target` in `engine/src/effects.rs` has no random target. It has only Opponent, AllOpponents, Me and Attacker.
- `OwedKind` (`engine/src/state.rs` ~989) has Make, ZeroCost, FreeTurn, Upgrade and Draw, and no hit.
- `runs_outside_a_card` (`engine/src/registry.rs` ~2515) refuses RandomDamage in hooks.
- `ChanceEvent::RandomTarget { amount }` exists, and `chance.rs` `random_hit` is at ~345.
- The player block sites match the list: `gain_block` at 4461, plus raw `player.block +=` at 2611, 2666, 2698, 3402 and 3477.
- The timing claim is correct. Card effects advance one at a time through `Stage::PlayingCard { next }` inside `run_opts`, and `run_opts` pays `owed.front()` before every stage step unless `wait` is set during RelicPick or RelicOffer (state.rs ~2439). So without the new wait-for-card rule, the hit would land before Iron Wave's damage.

**Size**
M and the three general pieces look right. No one-card hack is needed.

I created no scratch files, so there is nothing to clean up.

- **partly.** I checked the game facts against the jar and they all hold. Reaper's constructor sets cost 2, baseDamage 4, isMultiDamage and exhaust, and upgrade calls upgradeDamage(1). Reaper.use queues addToBot(VampireDamageAllEnemiesAction). VampireDamageAllEnemiesAction.update does the following in order:
- runs each player power's onDamageAllEnemies;
- skips monsters that are isDying, have currentHealth<=0 or are isEscaping;
- calls m.damage, then adds lastDamageTaken when it is above 0;
- if the total is above 0, queues WaitAction(0.3) unless FAST_MODE, then HealAction;
- if areMonstersBasicallyDead, calls clearPostCombatActions, which keeps HealAction, GainBlockAction and UseCardAction.

AbstractMonster.damage sets lastDamageTaken = Math.min(damageAmount, currentHealth) with no guard (offset 415-423), after onAttacked and before HP drops. So a fully blocked hit resets it to 0, and no stale value leaks. The engine facts also hold: Reaper is not in any pack, take_damage returns `lost` uncapped (state.rs:4243-4258), and the PlayingCard `e =>` arm calls check_over() after each effect (state.rs:2629-2633). The "missing" verdict and size S stand.

Three corrections to the design:

(1) The accumulator's scope is unsafe. State::attack (state.rs:4152) runs the target's OwnerAttacked hooks inline, through run_hooks_with during the hit. Thorns (powers.json:27) and FlameBarrier (act1-ironclad.json:4) answer with PlainDamage on the attacker. The design keeps one `dealt` field that is reset whenever Damage, PlainDamage and the other damage effects start. If a monster holding Thorns or a Flame-Barrier-like power is hit by Reaper, the nested PlainDamage resets or pollutes the player's running total. Thorns is a general power, so the generated enemies can carry it. In the game, Thorns' damage is a separate queued action and never touches the monsters' lastDamageTaken. The general fix:
- reset `dealt` at the start of each card or move effect row, in the PlayingCard loop or the monster move loop, not inside do_effect;
- count only hits whose source is that row's actor;
- or save and restore `dealt` around nested hook runs.

(2) The engine already has a rule that a heal runs after the win: check_over (state.rs:2958-2990). For a potion that ends the fight (Toy Ornithopter), it runs player_hooks_outside(OwnerUsedPotion) after the combat-end heals, citing the same clearPostCombatActions. Extend that path to the card's remaining Heal/HealOf rows rather than adding a new "defer the win" state. Running the heal before or after the combat-end heals gives the same HP, since both are capped at max HP. Two traps on this path:
- check_over calls finish_card before it, and the proposal zeroes `dealt` in finish_card. Read `dealt`, or run the rows, before zeroing it.
- heal() runs the OwnerUnbloodied hooks, so after the win use a heal that runs no hooks (like save_heal / the direct HP set).

(3) The name DamageDealt is already used as a Modifies value (registry.rs:2071, wording.json "modifies" section). The wording sections are separate, so the test will not fail, but the same word with two meanings is confusing. Use a distinct name such as HpDealt or UnblockedDealt.

Minor: the claims about Wallop and Shelled Parasite reuse are not Act 1. Nothing was written to the scratch folder.

- **confirmed.** I tried to refute the research and could not. The game facts match the jar and the gap is real. Size M holds. A few wiring details are missing from the plan, and one doc is out of date.

Game facts, re-read with javap:
- DualWield.<init> sets baseMagicNumber=1. upgrade() calls upgradeMagicNumber(1). use() calls addToBot(DualWieldAction(p, magicNumber)).
- DualWieldAction.update:
  - Offsets 64-92: if cannotDuplicate.size == hand.size, the action ends.
  - Offsets 93-196: if hand.size - cannotDuplicate.size == 1, it calls addToTop(MakeTempCardInHandAction(makeStatEquivalentCopy)) dupeAmount times and the original stays in hand.
  - Offsets 199-247: otherwise it runs removeAll(cannotDuplicate), then open(TEXT[0], 1, false, false, false, false).
  - Offsets 330-436: per selected card, one replacement copy plus dupeAmount copies, all through addToTop. Then returnCards() runs and selectedCards is cleared.
- isDualWieldable is true only for ATTACK or POWER.
- MakeTempCardInHandAction.update checks hand size against 10 (bipush 10) and sends overflow to addToDiscard.
- makeStatEquivalentCopy copies timesUpgraded (by calling upgrade), baseDamage, baseBlock, baseMagicNumber, cost, costForTurn, isCostModified(ForTurn), misc, freeToPlayOnce and the bottle flags.
- The overflow arithmetic is right: the hand gains min(n, 10 - size) copies and the rest go to the discard pile. One small point: returnCards puts the ineligible cards back before the copies arrive, so the hand order differs from the start. The engine's hand is an unordered count of cards, so this doesn't matter.

The piece is missing, as claimed:
- PickKind (effects.rs:127) has no copy kind.
- Effect::Pick { kind, n, exact, free } has no type filter.
- pick_source(kind) (state.rs:1899) filters only per kind.
- The pack has no Dual Wield.
- The codec pick kinds are 1-6 and 8, with 7 being Offered and never written. So 9 is the next free byte, as proposed.
- The single-candidate precedents exist at state.rs:2511 (Armaments) and state.rs:2519 (HandToTop).
- The upgrade_in_hand rule for the cost-0-this-turn mark is at state.rs:3748, as cited.
- AddCard's hand path at state.rs:3629 does the min(10 - len, n) split.

Details the plan should add:
1. AddCard (state.rs:3618) and take_offered (state.rs:2280) both increase `self.created`. solve.rs:280 reads that counter (`s.created < TURNS`), so the CopyInHand copies must increase it too. Going through AddCard does this; adding cards to the hand directly would not.
2. Precedent for the field name: Discover already has `copies: u8`, and the Offer struct (state.rs:642) holds copies and free. take_offered (state.rs:2278-2292) already adds copies to the hand with overflow and the cost-0 mark. Reusing that loop or AddCard keeps the logic in one place. The Offer itself can't be reused for the hand, because it holds only 3 cards.
3. Codec: Reader::pick refuses flags > 3. Putting `of` on every Pick needs a new flag bit (or a byte written only for some kinds) so that older encodings stay byte-identical. The Debug impl for Pick (state.rs:673) prints `free` only when set, so that recorded debug text stays the same. The new fields `of` and `copies` should follow that pattern.
4. Pile room: deck_fits counts min(k, 3) entries per card from the deck. Copying a card the deck holds once can grow it to 3 pile entries, which uses up MADE_ROOM (12). Anger already does the same, so this is a limit that already exists, but it belongs in the risk list.
5. The single-candidate auto-resolve is optional. One forced Choose reaches the same afterstate, so it only removes a decision point (like Armaments). It is not needed for correctness.

Mismatch: docs/research/act1-inventory.md (lines 105 and 143) still lists Warcry (C7) as missing. The pack has Warcry, using PickKind::HandToTop, at content/packs/act1-ironclad.json:50.

Scratch folder deleted.
