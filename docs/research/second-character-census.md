# Second-character census: the Silent's cards against the engine

A code read at main b83e1f7 (2026-11-07), no engine change, no load test.
It uses the method of `docs/research/act1-inventory.md` with three classes:
(a) writable as pack data with today's vocabulary, (b) writable once a block
the Ironclad inventory already names lands, (c) needs a new block.

## Summary

Of the Silent's 75 cards, 47 are (a), 5 are (b) and 23 are (c). Twenty of
the 47 are already official cards in `content/cards.json` (the starter,
Neutralize, Survivor, the Shiv and Poison commons, Bouncing Flask, Accuracy,
Caltrops, Burst, Wraith Form), so they round-trip today. The other 27 can be
written as pack entries, most with a generated power the way Flame Barrier
and Berserk were written. All five (b) cards wait on C5 (cost changes), C7,
C9, C11 or C12. The 23 (c) cards need 13 new blocks. Ordered by the cards
each one unblocks (with partner blocks in brackets): D1 discard events, 4
(3 alone; Eviscerate also needs C5); D2 discard several cards at once, 4
(2 alone; 2 more with D3); Q three new quantities, 3; D3 Draw and AddCard by
an amount, 3 (1 alone; 2 with D2); P1 pack powers that apply or size pack
powers, 2; H1 picks from a power's hook, 2; then seven blocks with one card
each: V1 variants of pack cards (Glass Knife), A1 a "drawn" trigger on a
card plus AddCard of a pack card (Endless Agony), R1 a condition on the card
just drawn (Escape Plan), N1 a delayed copy of a picked card (Nightmare,
with C10), L1 a play condition "draw pile empty" (Grand Finale), X1 a death
hook that hits the owner's allies by its max HP (Corpse Explosion), and
potions (Alchemize). The question has a clear answer: yes. Today's
vocabulary covers 47 of 75 (63%). With the Ironclad's named blocks it
covers 52 of 75 (69%). Discard is the Silent's main gap: D1, D2 and D3
together hold 9 of the 23 (c) cards, much as C1 and C2 (exhaust) did for the
Ironclad.

## Cards

"Official" means the card is already in `content/cards.json`. Everything
else in (a) names the pack form. "Gen power" means a pack power (`powers`
in a pack) with the hooks given. Upgrades are second entries, as for the
Ironclad.

| Card | Type | Rarity | Class | Vocabulary or block needed |
|---|---|---|---|---|
| Strike | Attack | Basic | a | official (Silent Strike) |
| Defend | Skill | Basic | a | official (Silent Defend) |
| Neutralize | Attack | Basic | a | official |
| Survivor | Skill | Basic | a | official (proving): Block 8, Pick DiscardFromHand 1 |
| Acrobatics | Skill | Common | a | Draw 3, Pick DiscardFromHand 1 |
| Backflip | Skill | Common | a | official |
| Bane | Attack | Common | a | Damage 7; row TargetHas Poison -> Damage 7 |
| Blade Dance | Skill | Common | a | official (AddCard Shiv 3 to Hand) |
| Cloak and Dagger | Skill | Common | a | official; the upgrade adds 2 Shivs |
| Dagger Spray | Attack | Common | a | official |
| Dagger Throw | Attack | Common | a | Damage 9, Draw 1, Pick DiscardFromHand 1 |
| Deadly Poison | Skill | Common | a | official |
| Deflect | Skill | Common | a | official |
| Dodge and Roll | Skill | Common | a (doubt) | Block 4; gen power: OwnerTurnStart -> Block 1 per stack, RemoveSelf. The next-turn block is raw, so it is exact only without Dexterity or Frail (see doubts) |
| Flying Knee | Attack | Common | a | Damage 8; gen power: OwnerTurnStart -> GainEnergy 1 per stack, RemoveSelf |
| Outmaneuver | Skill | Common | a | the same gen power as Flying Knee, 2 / 3 stacks |
| Piercing Wail | Skill | Common | a (doubt) | gen power, debuff, to AllOpponents: static DamageDealt Add -1 per stack; OwnerTurnEnd -> RemoveSelf; exhaust. Not written as Strength (see doubts) |
| Poisoned Stab | Attack | Common | a | official |
| Prepared | Skill | Common | a | Draw 1, Pick DiscardFromHand 1 (upgrade: 2 and 2) |
| Quick Slash | Attack | Common | a | official |
| Slice | Attack | Common | a | official |
| Sneaky Strike | Attack | Common | c | D1: a condition "a card was discarded this turn" for the GainEnergy 2 row |
| Sucker Punch | Attack | Common | a | official |
| Accuracy | Power | Uncommon | a | official (proving) |
| All-Out Attack | Attack | Uncommon | c | D2: DiscardRandom, a random discard from hand (like ExhaustRandom) |
| Backstab | Attack | Uncommon | a | Damage 11; innate; exhaust |
| Blur | Skill | Uncommon | b | C12 block kept at turn start, here for one turn (Block 5 then a gen power) |
| Bouncing Flask | Skill | Uncommon | a | official (RandomApply Poison 3 x3) |
| Calculated Gamble | Skill | Uncommon | c | D2 DiscardHand and D3 Draw by the number discarded |
| Caltrops | Power | Uncommon | a | official (proving; Thorns) |
| Catalyst | Skill | Uncommon | c | Q: a quantity "the target's stacks of a power" for ApplyOf Poison (k 1, or 2 when upgraded); exhaust |
| Choke | Attack | Uncommon | a (doubt) | Damage 12; gen power on the target: CardPlayed by Opponent -> LoseHp 1 per stack on Me; OwnerTurnStart -> RemoveSelf |
| Concentrate | Skill | Uncommon | a | Pick DiscardFromHand 3 exact (upgrade 2), GainEnergy 2 |
| Crippling Cloud | Skill | Uncommon | a | Apply Poison 4 and Weak 2 to AllOpponents; exhaust |
| Dash | Attack | Uncommon | a | Damage 10, Block 10 |
| Distraction | Skill | Uncommon | b | C11 a random card of a type into hand, and C5 its cost 0 this turn; exhaust |
| Endless Agony | Attack | Uncommon | c | A1: a per-copy "drawn" trigger (the card side of C3) and AddCard of a pack card (a copy of itself); AddCard takes official cards only |
| Escape Plan | Skill | Uncommon | c | R1: a row condition on the card just drawn (type Skill). C3's power trigger could only approximate it |
| Eviscerate | Attack | Uncommon | c | D1 a discards-this-turn counter, read by C5 (cost by a counter) |
| Expertise | Skill | Uncommon | c | D3 Draw by an amount: 6 - HandCards (7 when upgraded) |
| Finisher | Attack | Uncommon | c | Q: a quantity "Attacks played this turn" for ScaledDamage hits |
| Flechettes | Attack | Uncommon | c | Q: a quantity "cards of a type in hand" (HandCards has only `except`) |
| Footwork | Power | Uncommon | a | Apply Dexterity 2 to Me |
| Heel Hook | Attack | Uncommon | a | Damage 5; row TargetHas Weak -> GainEnergy 1, Draw 1 |
| Infinite Blades | Power | Uncommon | a | gen power: OwnerTurnStart -> AddCard Shiv 1 to Hand; the upgrade is innate |
| Leg Sweep | Skill | Uncommon | a | official |
| Masterful Stab | Attack | Uncommon | b | C5 cost by a counter (HP losses this combat, Blood for Blood's counter with the sign flipped) |
| Noxious Fumes | Power | Uncommon | a | gen power: OwnerTurnStart -> Apply Poison 1 per stack to AllOpponents |
| Predator | Attack | Uncommon | a | Damage 15; gen power: OwnerTurnStart -> Draw 1 per stack, RemoveSelf |
| Reflex | Skill | Uncommon | c | D1: per-copy `discarded` effects (Draw 2), as C2's `exhausted`; unplayable |
| Riddle with Holes | Attack | Uncommon | a | Damage 3, hits 5 |
| Setup | Skill | Uncommon | b | C7 a pick from hand to the top of the draw pile, and C5 its cost 0 until played |
| Skewer | Attack | Uncommon | a | x_cost; ScaledDamage 7, hits EnergySpent |
| Tactician | Skill | Uncommon | c | D1: per-copy `discarded` effects (GainEnergy 1); unplayable |
| Terror | Skill | Uncommon | a | Apply Vulnerable 99; exhaust |
| Well-Laid Plans | Power | Uncommon | c | H1: a pick at turn end from a power's hook, of a new kind "retain" (the `retain` flag exists per card, not as a choice) |
| A Thousand Cuts | Power | Rare | a (doubt) | gen power: OwnerPlaysCard -> PlainDamage 1 per stack to AllOpponents |
| Adrenaline | Skill | Rare | a | GainEnergy 1, Draw 2; exhaust |
| After Image | Power | Rare | a (doubt) | gen power: OwnerPlaysCard -> Block 1 per stack (raw, as the game's); the upgrade is innate |
| Alchemize | Skill | Rare | c | potions (none in the engine); its fight value is the potion |
| Bullet Time | Skill | Rare | b | C9 no more draws this turn, and C5 every card in hand costs 0 this turn |
| Burst | Skill | Rare | a | official (proving) |
| Corpse Explosion | Skill | Rare | c | X1: a monster's OwnerDied hook that damages the owner's allies (AllOpponents is the player for a monster), by a quantity "the owner's max HP"; near M6's ally target |
| Die Die Die | Attack | Rare | a | Damage 13 to AllOpponents; exhaust |
| Doppelganger | Skill | Rare | c | P1: ApplyOf of a pack power (refused at load today) sized by EnergySpent; x_cost; exhaust |
| Envenom | Power | Rare | a | gen power: OwnerAttackHit -> Apply Poison 1 per stack to Opponent (unblocked hits, the game's rule) |
| Glass Knife | Attack | Rare | c | V1: GrowDamage on a pack card. `registry::variant_index` returns None for a generated base, so GrowDamage -2 would load and do nothing |
| Grand Finale | Attack | Rare | c | L1: a play condition "the draw pile is empty" (like `only_attacks_in_hand`) |
| Malaise | Skill | Rare | a | x_cost; ApplyOf Strength {base 0, k -1, of EnergySpent} and ApplyOf Weak {k 1}; the upgrade has base -1 and 1; exhaust |
| Nightmare | Skill | Rare | c | N1: a power that holds a picked card and adds 3 copies next turn; needs C10 (copy a picked card) as well |
| Phantasmal Killer | Skill | Rare | c | P1: a turn-start hook that applies a pack power (double damage for that turn); a pack power's hook can't apply a pack power today |
| Storm of Steel | Skill | Rare | c | D2 DiscardHand and D3 AddCard Shiv (Shiv+ when upgraded) by the number discarded |
| Tools of the Trade | Power | Rare | c | H1: a DiscardFromHand pick from a turn-start hook (picks run only while a card resolves) |
| Unload | Attack | Rare | c | D2: DiscardHand with `except` Attack (as ExhaustHand has) |
| Wraith Form | Power | Rare | a | official (proving) |

Counts by rarity: Basic 4 (a 4); Common 19 (a 18, c 1); Uncommon 33 (a
17, b 4, c 12); Rare 19 (a 8, b 1, c 10).

## New blocks, ordered by cards unblocked

| Block | What it adds | Cards |
|---|---|---|
| D1 discard events | per-copy `discarded` effects (as C2's `exhausted`) and a count of discards this turn, read as a condition and by C5 | Reflex, Tactician, Sneaky Strike; Eviscerate with C5 (4) |
| D2 discard several at once | DiscardHand (all, or all but a type) and DiscardRandom (a chance event), with the number discarded as a quantity | Unload, All-Out Attack; Calculated Gamble, Storm of Steel with D3 (4) |
| Q new quantities | Attacks played this turn; cards of a type in hand; the target's stacks of a power | Finisher, Flechettes, Catalyst (3) |
| D3 Draw and AddCard by an amount | `Draw` and `AddCard` take an `Amount` | Expertise; Calculated Gamble, Storm of Steel with D2 (3) |
| P1 pack powers that apply or size pack powers | a pack power's hook may apply a pack power; ApplyOf may name a pack power | Phantasmal Killer, Doppelganger (2) |
| H1 picks from a power's hook | a pause at turn start or turn end, plus a "retain" pick kind | Tools of the Trade, Well-Laid Plans (2) |
| V1 variants of pack cards | GrowDamage on a generated base | Glass Knife (1) |
| A1 per-copy "drawn" trigger, AddCard of pack cards | the card side of C3; `AddCard` names a pack card | Endless Agony (1) |
| R1 the card just drawn as a condition | a row reads the type of the card a Draw drew | Escape Plan (1) |
| N1 delayed copies | a power that holds a card id and adds copies next turn (with C10) | Nightmare (1) |
| L1 draw-pile-empty play condition | a card flag like `only_attacks_in_hand` | Grand Finale (1) |
| X1 a death hook on the owner's allies | an ally target for a monster's hook, and the owner's max HP as a quantity | Corpse Explosion (1) |
| potions | a potion resource in the fight | Alchemize (1) |

Q is counted as one block of three small additions to C4's quantity
vocabulary; counted apart they make 15 blocks, each Q item one card. The
Ironclad blocks the (b) cards use: C5 (Masterful Stab, Distraction, Setup,
Bullet Time, and Eviscerate in (c)), C7 (Setup), C9 (Bullet Time), C11
(Distraction), C12 (Blur), C10 (Nightmare in (c)). C5 is the one the Silent
leans on most: it would unblock Masterful Stab alone, and three more
cards together with C7, C9 and C11.

## Method and doubts

What I read: `engine/src/effects.rs` (Effect, Quantity, Target, PileKind,
PickKind), `hooks.rs` (Trigger, Condition, statics, replacements),
`powers.rs`, `registry.rs` (`parse_effect`, `parse_hook`, `condition`,
`amount`, `parse_card_as`, `variant_index`, `runs_outside_a_card`),
`state.rs` (turn start order, `end_turn`, `quantity`, `grow_damage`, the
attack-hit hooks), `character.rs` (the Silent exists: 70 HP, the
first-turn draw of 2, a starter with a Defend in Survivor's place), the
official `content/cards.json` and `powers.json`, `content/packs/`, and
`engine/tests/packs.rs` (a card applying a pack power to the opponent is
tested). The card list and texts come from slaythespire.wiki.gg's "Silent
Cards" page (fetched 2026-11-07; 75 cards: 4 basic, 19 common, 33 uncommon,
19 rare, Burst among the rares). Costs and upgrade numbers were not checked
against sts_lightspeed. That check belongs to the step that writes a pack,
as for the Ironclad. Nothing here was loaded, so an (a) is a reading of the
vocabulary, not a load.

What the code settled:
- The player's turn start sets block to 0, draws, then runs OwnerTurnStart
  hooks. So "next turn" gen powers (Flying Knee, Outmaneuver, Predator,
  Dodge and Roll) fire after the draw. That is the game's timing for
  Predator. Infinite Blades' Shiv comes after the draw here and before it in
  the game, which matters only for a full hand.
- AddCard is allowed in a hook (only picks and random effects are refused
  there), so Infinite Blades loads. AddCard takes official cards only, which
  is fine for Shiv and Shiv+ and blocks Endless Agony.
- `ApplyOf` of a pack power is refused at load (C4's decision), and a pack
  power's hook may not apply a pack power. That is the whole of P1.
- `variant_index` refuses a generated base, so a pack Glass Knife's
  GrowDamage would do nothing. It also does not floor at 0, which the game
  does.

Uncertain classifications:
- **Dodge and Roll (a):** the game stores the next-turn block computed with
  Dexterity and Frail at play time. A constant Apply gives raw block, so the
  entry is exact only without Dexterity or Frail. Footwork is a Silent card,
  so the gap is reachable. A strict reading puts it in (c) under P1 plus a
  "this card's block" quantity.
- **Piercing Wail (a):** the game applies -6 Strength and a restoring power
  that it skips under Artifact. A pack can't express "skip under Artifact"
  for the second power. So the entry is a debuff gen power with a static -1
  damage per stack, which Artifact cancels whole, and it is removed at the
  monster's turn end. It should hit the same damage. Any reader of a
  monster's Strength would differ, and I found none for monsters.
- **Choke (a):** a monster-side CardPlayed hook with LoseHp runs before the
  card's effects (only Damage and PlainDamage hooks wait for the card), and
  the engine files that HP loss as `Card` (the owner's own). The totals match
  the game's. The order inside a card differs.
- **A Thousand Cuts, After Image (a):** OwnerPlaysCard fires before the
  card's effects and not for Burst's replayed copy. The game's A Thousand
  Cuts fires after the card. Whether either counts Burst copies in the game
  is unchecked.
- **Concentrate (a):** an exact pick of 3 with fewer than 3 other cards in
  hand. I assume the pick ends when nothing is left to pick (Effect::Pick is
  "skipped when there is nothing to pick"), and I did not trace that.
- **Acrobatics, Dagger Throw, Prepared (a):** Draw (a chance event) then a
  pick in one card. The stage keeps the effect index, so play resumes after
  the draw. Burning Pact has the reverse order, and no content has Draw
  before Pick today.
- **Escape Plan (c):** C3's "card drawn" power trigger with a Skill
  condition could approximate it (a power that fires once and is removed at
  turn end). It would also fire on later draws that turn, so I counted it as
  needing R1.
- **Alchemize (c):** potions are a run-level resource like Feed's max HP. If
  the charter treats it as off in fights, the card is an empty exhaust card
  and would count as (a).
