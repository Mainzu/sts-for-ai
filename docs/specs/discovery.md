# Discovery: choose 1 of 3 random cards (P3)

Status: closed (2026-11-12, built and in use; confirmed by the coordinator session; landed on main, f0d8665d; As built: docs/extending.md "Pools and discovery").

Rows and limits: `docs/research/act1-relics-potions.md` "Discovery".

## Outcome

Attack Potion, Skill Potion and Power Potion load from content files and
act as the game's classes: the game shows 3 different random cards of a
type from the class's pool, the player takes one or skips, and it goes
into hand costing 0 this turn. Infernal Blade (an Ironclad card blocked
on C11) loads with the same words: one random Attack, no choice.
Colorless Potion and Toolbox stay blocked on a new block, "colorless
cards": none of the game's 34 in-combat colorless cards loads today (see
"Colorless pool").
`docs/research/act1-relics-potions.md` "Missing building blocks" calls the
missing piece P3 discovery.

**How it moves the goals.** Act 1 (`decision/act1-finish`): 23 -> 26 of
33 potions; Ironclad cards 32 -> 33 of 40 the engine lacked (Infernal
Blade). Goal 1: two words a pack can use: a card pool and a `Discover`
effect (any pool, so the colorless spec only adds cards).

**Non-goals:** the run layer (R2, P2); card rewards, rarity weights and
shops (a pool here is only the list a fight draws from); the other
blocked Ironclad cards (C7-C10, C12-C14); Master Reality (a Watcher
power); the colorless cards, Colorless Potion and Toolbox (a later spec,
with a relic's `Discover` before the opening draw); the cost-0 mark
itself (the singles session's `free_in_hand`, built for C5).

## The game's behaviour

From the decompiled classes (AxorusMT/sts; paths under
`com/megacrit/cardcrawl/`; each test names its line):

- **The potions** (`potions/AttackPotion.java`, `SkillPotion`,
  `PowerPotion`, `ColorlessPotion`): common, no target, potency 1 (2 with
  Sacred Bark, `AbstractPotion.getPotency`). `use` queues
  `DiscoveryAction(CardType.ATTACK|SKILL|POWER, potency)`, or
  `DiscoveryAction(true, potency)` for colorless.
- **The offer** (`actions/unique/DiscoveryAction.java`): 3 cards drawn one
  at a time with `cardRandomRng`, a card whose `cardID` is already shown
  drawn again, so 3 different cards. Typed: from
  `AbstractDungeon.returnTrulyRandomCardInCombat(type)`; colorless: from
  `returnTrulyRandomColorlessCardInCombat()`. (The class regenerates the
  choices on every frame after the pick, which only spends RNG: not
  modelled.)
- **The lists** (`dungeons/AbstractDungeon.java` 964-1057, 1190, 1265):
  the class's common, uncommon and rare pools as one flat list (no rarity
  weighting), without HEALING-tagged cards (Ironclad: Feed, Reaper);
  colorless: the colorless cards of rarity uncommon or rare, not Status,
  without HEALING (Bandage Up): 34 cards. With everything unlocked, the
  Ironclad lists hold 28 Attacks, 28 Skills, 14 Powers.
- **Skip**: `customCombatOpen(cards, text, this.cardType != null)`: the
  typed potions may skip, Colorless Potion may not. A skip adds nothing;
  the potion is used up.
- **The pick**: the chosen card is copied (`makeStatEquivalentCopy`),
  twice for potency 2, each `setCostForTurn(0)`. One copy: to hand if the
  hand holds fewer than 10, else to the discard pile. Two copies: both to
  hand if hand + 2 <= 10; at 9, one to hand and one to discard; else both
  to discard. That is: each copy to hand while the hand holds fewer than
  10, else to discard.
- **Cost for the turn** (`cards/AbstractCard.java` 2484, 2522):
  `setCostForTurn` changes only a `costForTurn` of 0 or more (X-cost and
  unplayable cards keep theirs). `resetAttributes` puts it back:
  `AbstractRoom.endTurn` resets every card in hand, draw and discard pile
  at the end of the player's turn (a retained card too); a card reaching
  the discard or draw pile through its move animation (played, discarded,
  shuffled) and one exhausted are reset on arrival. A card put straight
  into the discard pile by a full hand (`ShowCardAndAddToDiscardEffect`
  adds the real card, animates a copy) keeps 0 until the turn ends.
- **Toolbox** (`relics/Toolbox.java`, shop relic): `atBattleStartPreDraw`
  queues `ChooseOneColorless`: 3 different colorless cards as above, not
  skippable, the card keeps its cost (no `setCostForTurn`), to hand with
  fewer than 10 cards else discard. `AbstractRoom` (258-259) runs the
  pre-draw relics, then queues the opening `DrawCardAction`: the choice
  comes before the opening hand is drawn.
- **Infernal Blade** (`cards/red/InfernalBlade.java`): skill, cost 1 (0
  upgraded), exhaust; one `returnTrulyRandomCardInCombat(ATTACK)`,
  `setCostForTurn(0)`, `MakeTempCardInHandAction` (discard when the hand
  is full).

## Behavior

### 1. Card pools as content

A pack may hold `"pools"`: names, each with a list of card names
(official names or pack card ids), each card at most once:

    "pools": {"Ironclad": ["Anger", "Armaments", ...]}

A pool is a list the game draws from (docs/extending.md "Pool or set"):
here the game's in-combat random list for a class (common, uncommon and
rare, HEALING cards left out, as `returnTrulyRandomCardInCombat` filters
them). A name that isn't a loaded card is a load error, so a pool lists
only cards that load; a pool named twice is a load error (as a power
redefined). The research doc names the game's cards still missing from
each pool, and a test checks each pool against the game's list minus
those named cards, so a card that starts loading must join its pool.

The Ironclad pool goes in `content/packs/act1-ironclad.json`: 28 Attacks,
24 Skills (missing Havoc, Warcry, Battle Trance, Dual Wield), 12 Powers
(missing Barricade, Juggernaut).

### 2. Effect `Discover`

    {"Discover": {"pool": "Ironclad", "type": "Attack", "offer": 3, "copies": 1, "free": true, "skip": true}}

- `pool`: a pool loaded before or in this pack, else a load error.
- `type` (optional): only the pool's cards of that type; without it,
  every card in the pool.
- `offer`: how many different cards are shown (3; 1 for a random card
  with no choice: Infernal Blade).
- `copies`: copies of the taken card; a potion's potency scales it
  (Sacred Bark: 2), as its other amounts.
- `free`: each copy costs 0 this turn (step 3).
- `skip`: the player may take none (`Done`).

Allowed in a card's or potion's effects; in a hook, a load error. A
relic's `Discover` (Toolbox) is the colorless spec's.

When it runs:
1. **The offer is a chance event** (`ChanceEvent::Offer`): `offer`
   different cards, uniformly over the filtered pool's combinations of
   that many (the game's draw-again-on-repeat gives the same
   distribution). With no more cards than `offer` in the filtered pool,
   all of them, no chance. Listed outcomes: the C(n, k) combinations at
   equal probability, `Large` past the limit (as a big draw).
2. **The pick is a decision**: the offer is held in the state sorted by
   card id (the screen's order isn't kept, so equal offers are equal
   states). Legal actions: `Choose(c)` for each offered card, and `Done`
   when `skip`. An offer of one card with `skip` false is taken at once,
   no decision.
3. **The card**: `copies` copies of the chosen card, each into hand while
   the hand holds fewer than 10 cards, else into the discard pile; with
   `free`, each copy put in hand is marked "costs 0 this turn" (step 3).
   Then the row goes on.

### 3. Costs 0 this turn: the singles session's mark

`free` uses the singles session's mark (built for Liquid Memories, C5,
landed on main before this spec wires it): `CombatState.free_in_hand`, a
sorted multiset of hand card ids that cost 0 this turn, entered through
`CombatState::mark_free_in_hand(card)`. As that design says: only a card
costing more than 0 (not X-cost, not unplayable) is marked, as the
game's `setCostForTurn` changes only a cost of 0 or more; a marked copy
is played before an unmarked one of the same card and kept last; the
marks clear at the end of the player's turn (the game's
`resetAttributes` in `AbstractRoom.endTurn`). How the net and the codec
read the mark is that design's.

Named limit: a copy that goes to the discard pile from a full hand isn't
marked (the game keeps it at 0 until the turn ends, so one returned to
hand the same turn would cost 0 there).

### 4. The entries

- **Attack Potion** (common, potency 1): `Discover` Ironclad `Attack`,
  offer 3, copies 1, free, skip.
- **Skill Potion**, **Power Potion**: the same, `Skill`, `Power`.
- **Infernal Blade** (Ironclad skill, cost 1, `+` cost 0, exhaust):
  `Discover` Ironclad `Attack`, offer 1, copies 1, free, no skip. It
  joins the Ironclad pool (Skills 24 of 28).
- Not in this spec (the colorless spec): **Colorless Potion** (`Discover`
  Colorless, offer 3, copies 1, free, no skip) and **Toolbox** (a
  `CombatStartPreDraw` relic `Discover` Colorless, not free, no skip,
  before the opening draw).

The class pool is the Ironclad's (the one character with a pool); a
later character's pack names its own pool in its own potions.

### 5. Binding the pools' cards

A pack card can be in a fight only once it has a slot (`Binding`). When a
fight is given potions, and for the deck's own cards, every pack card a
held `Discover` can offer (its pool filtered by type) is bound after the
deck's cards, with the pack powers it applies, as a potion's pack powers
are now. Binding at the start, not when offered, keeps the slot order
fixed for the fight (equal states, equal bytes) and keeps the registry
lock out of search. More than 32 pack cards in all (`CARD_SLOTS`) is an
error naming the entry: the whole Ironclad pack is 33 cards with
Infernal Blade, so only a deck of every pack card plus a held Skill
Potion could reach it (a named limit; a colorless pack adds to it).

### 6. The net, the codec, the search

- **The net: no new column.** The offer is a short decision whose
  afterstates (the chosen card in hand) the net already reads.
  `Discover` adds no effect column (as `DrawPicked`): card and potion
  vectors keep their width, the contract tiny nets keep loading, no pin
  moves.
- **The codec: no change.** An open offer counts as generated content
  (`has_generated`; a pool's index is process-local), so a state with one
  has no codec encoding; every other state encodes as before. The mark's codec bytes
  are the singles session's.
- **Search and agents**: the offer is a chance event as a draw is, the
  pick a decision as any `Pick` (`legal_actions`): `greedy_action`, the
  search and the solver need nothing beyond the stage.
- **The heal bound**: `Discover` heals when a card it can offer heals
  (followed as `AddCard` is).

### Colorless pool

None of the game's 34 in-combat colorless cards loads (the engine's
colorless cards are statuses and Shiv, which the game leaves out). From
a read of the engine's words (an estimate, each to be checked when
written):
- **Writable now or with this spec's words (about 15):** Swift Strike,
  Flash of Steel, Finesse, Good Instincts, Dramatic Entrance, Blind,
  Trip, Panacea, Master of Strategy, Purity, Hand of Greed (its gold is
  the run layer's), Panic Button and The Bomb (pack powers), Discovery
  (`Discover` Ironclad, no type, free, no skip) and Jack of All Trades
  (`Discover` Colorless, offer 1).
- **Needing new words (about 19):** Mind Blast (draw pile size), Impatience
  (no Attack in hand), Dark Shackles (Strength lost this turn), Deep
  Breath (discard into draw), Enlightenment, Madness, Forethought,
  Chrysalis, Metamorphosis (cost changes: C5's kin), Apotheosis (upgrade
  every pile: C6's kin), Magnetism (random card in a power's hook: R28),
  Mayhem (C8), Secret Technique, Secret Weapon, Violence (from the draw
  pile), Thinking Ahead (hand to the top of the draw pile), Transmutation
  (X random cards), Panache (every 5th card this turn), Sadistic Nature
  (a debuff applied by the owner: R14's kin).

The research doc names this block "colorless cards" with this split. A
colorless pack would go in `content/packs/act1-colorless.json` with the
`Colorless` pool; Colorless Potion and Toolbox (with a relic's
`Discover` before the opening draw) load with it.

### Content format and wording

New words: `pools`, `Discover` (with `pool`, `type`, `offer`, `copies`,
`free`, `skip`). Each in `registry::element_names()` with its words in
`content/wording.json`. The offered pick is engine-internal (not a
content `PickKind`) and needs no word. The official writer writes
`Discover`.

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden, rules version | byte-identical, unchanged | golden test |
| Fights without the new words | identical play and codec bytes | `relic_baseline`, `codec` pins |
| Existing nets | byte-identical inputs; no pin moves | the pin tests unchanged, `series_check` |
| Picks | card, potion and relic picks unchanged | `potion_use`, `fight_vocabulary`, `decisions` |
| Search speed | `series_speed` at most 10% slower | job (last step) |

## When in doubt

The game's decompiled class over the research doc's line; an unchanged
fight without the new words over anything else.

## Scope

May change: effects (`Discover`), the pack loader (pools), the binding
(pool cards), the stage machine and actions (the offer), chance events,
the heal bound, the official writer, key lists, element names, wording,
the Act 1 pack files, tests, docs, facts; calls to the singles session's
mark.

Off limits: `golden.txt`; nets and their inputs; `py/src/features.rs`
beyond a match arm; configs, yardsticks, controls; the gauntlet and run
layer; saved packs and data; the mark itself (the singles session's).

## Decisions taken (coordinator session, 2026-11-12)

1. Colorless Potion and Toolbox stay blocked on a new block "colorless
   cards" (34 cards; about 15 writable, 19 needing words), its own spec,
   with the relic `Discover` before the opening draw. `Discover` stays
   general (any pool).
2. Skill and Power Potion count as loaded, their pools short of the
   blocked Ironclad cards (4 Skills, 2 Powers), the gap named in the
   research doc; the pool test makes each newly loaded card join.
3. Infernal Blade is in this spec (the `offer` field).
4. The cost-0 mark is the singles session's `free_in_hand`, not a
   per-copy variant. Singles lands it alone on main first; this spec
   builds pools and `Discover` meanwhile, then rebases onto it and wires
   `free`. A copy sent to the discard pile by a full hand isn't marked
   (a named limit).
5. No format change: no net column, codec tag or stage byte; no re-pin.

Expensive to reverse: the content words (`pools`, `Discover` and its
fields) once packs use them.

## Outside assumptions

The decompiled game (AxorusMT/sts, read 2026-11-12): the classes named in
"The game's behaviour". Every card unlocked (the game's pool depends on
unlocks).

## Verification

Written first, passing on unchanged code: `relic_baseline`, the codec
pins, the product-layout pins.

Then, in `act1_potions.rs`, `act1_cards.rs` or a new `discovery.rs`:
- pools: the Ironclad pool equals the game's list minus the named
  missing cards; an unknown name, a name twice and a pool redefined are
  load errors; a `Discover` naming an unknown pool, or in a hook, is one.
- the offer: 3 different cards, each of the type; over many samples
  every pool card of the type appears and none other (no Feed or
  Reaper); `chance_outcomes` lists C(n, 3) equal combinations for a
  small test pool; a pool of 3 gives no chance event; a test pool of
  another name works.
- Attack Potion: the taken card is in hand at cost 0, plays for 0 this
  turn and costs its own cost next turn; `Done` adds nothing; Whirlwind
  stays X; Sacred Bark gives 2 copies; with 9 in hand one copy to hand
  and one to discard, with 10 both to discard (unmarked, the named
  limit).
- Skill and Power Potion: offers of their type only; with Corruption a
  discovered Skill costs 0 and exhausts.
- Infernal Blade: one random Attack at cost 0, no decision; exhausts.
- equal hands reached by different offers are equal states.
- `greedy_action` and the search finish a fight with each potion; the
  heal bound with a test pool holding a healing card.
- wording: every new word has its text.

## Build steps

1. Pins first (as Verification's first line).
2. Pools in the loader, the Ironclad pool, the pool test.
3. `Discover`: parse, the offer chance event, the offered pick, binding
   the pools' cards, the heal bound, wording; Attack, Skill, Power
   Potion; Infernal Blade (`free` not wired yet).
4. Rebase onto the singles session's mark; wire `free` to
   `mark_free_in_hand`; the cost tests.
5. Research doc rows and the "colorless cards" block, facts;
   `series_speed` job.
