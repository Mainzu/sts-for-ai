# Act 1 single-entry blocks (R5, C5, C8, P5, P6, R14)

Status: closed (2026-11-13, built and in use; steps landed on main by act1-singles, act1-p5, act1-p6, act1-r14; last be76e88e; kb how/act1-relics-potion-mechanics, measurement/act1-relics-potions@files).

## Outcome

Eight more Act 1 entries load from content files and act as the game's
classes do: **Art of War, Pocketwatch, Champion Belt, Potion Belt**
(relics), **Liquid Memories, Distilled Chaos, Smoke Bomb, Entropic Brew**
(potions), and the blocked Ironclad card **Havoc** (with Havoc+), which
needs the same "play the top card" piece as Distilled Chaos. Each block in
`docs/research/act1-relics-potions.md` "Missing building blocks" that
these need is small and general: a designer can use each in any pack.

**How it moves the goals.** Act 1 (`decision/act1-finish`): 47 -> 51 of
141 relics, 23 -> 27 of 33 potions, and one of the eight blocked Ironclad
cards (C8). Goal 1: five new words a pack can use (a "costs 0 this turn"
mark on a pick, play the top card, the player escapes, random potions, a
trigger "the owner applied a power"). The net-format cost is one new zero
row column, paid in one re-pin.

**Non-goals:** the run layer (R2, P2): Smoke Bomb's lost rewards,
Entropic Brew drunk outside a fight, Potion Belt's slots between fights;
discovery (P3, its own session; it reuses this spec's mark); the
after-block stage (R12); the would-die replacement (R23); Snecko Eye and
Snecko Oil (random costs); Mummified Hand; any other entry.

## Behavior

Each section names the game's class it follows (decompiled
`aeubanks/sts`, read 2026-11-12; `decision/parity-source`).

### 1. Last turn's card counts: no engine change (Art of War, Pocketwatch)

Both relics fit today's relic counter and conditions; R5 needs no new
word.

**Art of War** (`relics/ArtOfWar.java`): `atPreBattle` sets `firstTurn`
and `gainEnergyNext`; `atTurnStart` gives 1 energy when `gainEnergyNext &&
!firstTurn`, then clears `firstTurn` and sets `gainEnergyNext`; `onUseCard`
of an Attack clears `gainEnergyNext`. So turn 1 never gains, and turn N+1
gains when turn N played no Attack. The counter is `gainEnergyNext`
without the first turn (1: gain at the next turn start):
- `CombatStartPreDraw` -> SetCounter 0 (the game's reset; runs before
  turn 1's turn-start hooks in both turn-1 orders);
- `OwnerTurnStart`, `CounterIs 1` -> GainEnergy 1;
- `OwnerTurnStart` -> SetCounter 1;
- `CardPlayed by Owner`, Attack -> SetCounter 0.

A Double Tap copy or an Attack played by Distilled Chaos or Havoc counts
(the game's `onUseCard` fires for them).

**Pocketwatch** (`relics/Pocketwatch.java`): `onPlayCard` counts every
card played (copies and autoplayed cards included, `GameActionManager`
~235); `atTurnStartPostDraw` draws 3 when the count is at most 3 and it
isn't the first turn, then resets the count. The engine's
`cards_played_this_turn` is the same count and still holds the turn's
total at turn end, so the relic decides at turn end and draws after the
next turn's draw:
- `CombatStartPreDraw` -> SetCounter 0;
- `OwnerTurnEnd`, `CardsPlayedThisTurnBelow 3` -> SetCounter 1 (the
  condition leaves out one card, the card in play, as written for card
  rows such as FTL; at turn end no card is in play, so it reads "at most 3
  played");
- `OwnerTurnStartPostDraw`, `CounterIs 1` -> Draw 3;
- `OwnerTurnStartPostDraw` -> SetCounter 0.

### 2. A "costs 0 this turn" mark (Liquid Memories; shared with P3)

The game's `setCostForTurn(0)` on one copy of a card. Piles are counts of
card ids, so the mark is held beside the hand:

- **State.** `CombatState.free_in_hand`: the ids of hand cards that cost
  0 this turn, copies repeated, sorted, at most `HAND_LIMIT` (10).
  Always a sub-multiset of the hand. Empty in every fight that never uses
  the word.
- **Marking.** A `Pick` with `"free_this_turn": true` marks each card it
  puts into the hand. A copy is marked only when its cost now
  (`cost_of`) is above 0 and it isn't X-cost or unplayable (the game's
  `setCostForTurn` changes only `costForTurn >= 0`; a card already at 0
  stays 0, since no effect raises a cost in a fight, so the mark would
  change nothing). A card that doesn't reach the hand (hand full) isn't
  marked: a copy that goes to the discard pile from a full hand loses it,
  where the game keeps its 0 until turn end (a named limit).
- **Entry point** `CombatState::mark_free_in_hand(card)`: marks one copy
  of `card` in the hand by the rules above (cost now above 0, not X, not
  unplayable, a copy left unmarked); the pick key calls it, and P3's
  discovery calls it when a discovered card enters the hand.
- **Cost.** `cost_of(card)` is 0 while a marked copy of the card is in
  the hand.
- **Playing** a card with a marked copy plays the marked copy (it costs 0
  and the mark goes). Any other way a copy leaves the hand (discard,
  exhaust, onto the draw pile, a random exhaust) takes an unmarked copy
  first: the marks are cut back to the hand's count. Keeping the free
  copy is never worse for the player; the one place it differs from the
  game is True Grit's random exhaust, which here never takes the marked
  copy (a named limit).
- **Upgrades** (Armaments, Blessing of the Forge) move the mark to the
  upgraded id: the game's `upgradeBaseCost` keeps `costForTurn` 0.
- **Turn end** clears every mark (the game's `AbstractRoom.endTurn`
  calls `resetAttributes` on every pile).

**Liquid Memories** (`potions/LiquidMemories.java`,
`BetterDiscardPileToHandAction(potency, 0)`): potency 1 (Sacred Bark 2):
`Pick ReturnFromDiscard` n 1, exact, `free_this_turn`. With fewer cards in
the discard than n, the game takes them all without a choice; the engine's
exact pick takes the same cards.

**For P3** (discovery): this session builds the mark and lands it alone
first; P3's discovery calls `mark_free_in_hand` for the chosen card.
Infernal Blade (C5 with C11) is P3's.

### 3. Play the top card of the draw pile (Distilled Chaos, Havoc)

The game (`potions/DistilledChaosPotion.java`, `PlayTopCardAction`,
`GameActionManager` ~183-292): the potion queues `potency` (3, Bark 6)
`PlayTopCardAction`s, each with a random living monster chosen at use.
Each action takes the top card of the draw pile (reshuffling the discard
in if the draw pile is empty; nothing if both are empty) and queues it to
autoplay. All the cards are taken before any plays (the actions run
before the card queue), then they play in order:
- free: no energy spent; an X-cost card's X is the energy when it was
  taken, and spends none (`AbstractPlayer.useCard` sets `freeToPlayOnce`);
- counted as played, with every play hook (`onPlayCard`, `onUseCard`);
- a card that can't be played then (unplayable Status, a failed
  `playable_if` such as Clash, an Attack while Entangled, or its target
  dead) goes to the discard pile with no effect and isn't counted;
- then it goes where a played card goes (discard, exhaust, a Power out of
  the fight); with Havoc's flag it exhausts.

**New effect `PlayTop { n, exhaust }`** (card rows and potion rows; not
in relic hooks): takes `n` cards, one chance event each (the card, from
the known top if any, else by counts; then its target, uniform among the
monsters living now, when the card targets one and more than one lives).
The taken cards wait in **`CombatState.top_queue`** (card, target, X,
exhaust; at most 6, the most one use can take, Bark included). Once the
card or potion that took them has finished (its card placed), the stage
machine plays the queue from its front as above, each card resolving in
full (its picks and chance events too) before the next. A fight that ends
clears the queue. Potency scales `n` (`potions::scaled_effect`).

**Distilled Chaos**: potency 3, `PlayTop` 3. **Havoc** (`cards/red/Havoc.java`,
`PlayTopCardAction(random monster, true)`): cost 1, `PlayTop` 1 with
exhaust; Havoc+ costs 0. Both go in the existing packs.

### 4. The player escapes (Smoke Bomb)

The game (`potions/SmokeBomb.java`): usable only when no monster in the
room is a boss (the dead ones count: Slime Boss stays in the list after
its split) and none has BackAttack (Act 3; out); the player escapes and
`AbstractRoom.endBattle` runs as for a win: Meat on the Bone's
`onTrigger` and `onVictory` (Burning Blood) still heal; only the reward
screen is empty (`smoked`, `AbstractRoom` ~327).

- **Effect `Escape` in a potion**: the existing monster word, now the
  player's in a potion row (the user escapes). The fight ends as won:
  `CombatWon` hooks, then the combat-end heal, then `Stage::Over { won:
  true }`, with the new flag `CombatState.escaped` set. Monsters keep
  their HP.
- **Boss monsters**: a monster kind is a boss when it appears in a
  `boss`-group encounter (official or pack), worked out at load. A fight
  is a boss fight when any slot, alive or dead, holds a boss.
- **Potion key `fights`** (as a relic's, here "usable in"): Smoke Bomb
  has `["hallway", "elite"]`; it isn't a legal action in a boss fight (it
  stays held).
- **Readers**: everything that reads a win reads an escape as one (the
  search's terminal value is the HP left plus the heal). Python adds
  `Combat.escaped`. The run layer holds no potions (P2), so no gauntlet
  run meets it; pricing an escape's lost rewards is P2's job (named
  limit).
- **Amendment (built, coordinator 2026-11-13): the boss-fight mark.** The
  engine's split puts a split child in the boss's own slot, so after
  Slime Boss splits no slot holds it. `CombatState.boss_fight` is set as
  the potions are given when a slot holds a boss and the player holds a
  potion not usable in a boss fight (with P6: or a potion maker,
  `ObtainRandomPotions`); its codec tag is written only when set, so
  every other state's bytes stay. A boss fight is the mark or a slot
  holding a boss now. A potion `fights` names hallway and elite, boss
  optional (a fight tells only a boss fight from the rest). Named limit: a potion
  that arrives mid-fight in some other way, after the split, is drinkable;
  no Act 1 content does that.

### 5. Potions made in a fight (Entropic Brew, Potion Belt)

The game (`potions/EntropicBrew.java`): in combat, one
`ObtainPotionAction(returnRandomPotion(true))` per potion slot, queued, so
the slot the Brew left is filled too and full slots are skipped.
`returnRandomPotion(true)` (`AbstractDungeon` ~809): rarity by a 0-99
roll (common below 65, uncommon below 90, else rare), then uniform among
the class's potions of that rarity, never Fruit Juice (`limited`).
Sacred Bark doesn't change it (the loop reads `potionSlots`, not potency).

- **Potion slots**: 3 (Ascension 0), plus each held relic's new key
  `potion_slots`. **Potion Belt** (`relics/PotionBelt.java`, +2 slots):
  `potion_slots: 2`; its run-layer part (carrying 5) is P2. Giving a
  fight more potions than slots stays allowed (no caller breaks); the
  Brew then fills none.
- **New effect `ObtainRandomPotions { except }`** (potion rows only):
  one chance event per empty slot, each giving one potion from the
  potion pool (the game's class potion pool, `PotionHelper.getPotions`;
  docs/extending.md "Pool or set"): here the potions of the Brew's own
  pack file, less the names in `except`, weighted 65/25/10 by rarity and
  uniform within one. A rarity with no potion in the potion pool is a
  load error (the game would loop forever). **Entropic Brew**: potency 0,
  `ObtainRandomPotions` except `["Fruit Juice"]`.
- **Binding**: a fight given a potion with this effect binds the pack
  powers of every potion in the potion pool too
  (`registry::bind_potions`), so Speed Potion or Essence of Steel can
  arrive and work.
- The potion pool is the loaded pack, not the game's 33: until the rest
  of the 33 load, the unloaded ones never come (named limit; the odds
  within a rarity shift).
- **Amendment (built, coordinator 2026-11-13): 40 card slots.** The Brew's
  pool holds Attack, Skill and Power Potion, so a fight given it binds
  every pack card of the Ironclad pool: 33 once Havoc joined it, past the
  32 card slots (docs/specs/pack-slots.md). The discovery spec's limit
  ("more than 32 is an error") was reachable only by a deck of every pack
  card plus a held Skill Potion until Havoc made the pool alone pass it; it
  is a gap the discovery build should have hit. `registry::CARD_SLOTS` is
  now 40: card ids 196 -> 212 (below a byte), slots 0-31 keep their ids,
  so no codec byte, golden line or net input moves (net widths come from
  the card list, not the id count). Test: `act1_singles.rs`
  `every_ironclad_pack_card_and_the_brew_bind` (every Ironclad pack card
  in the deck, the Brew given, each potion it makes drunk). More than 40
  pack cards in a fight is an error.
- **Amendment (built): the boss-fight mark's maker half** (section 4's
  amendment). A boss fight holding a potion whose `ObtainRandomPotions`
  pool holds a potion not usable in a boss fight carries the mark, so a
  Smoke Bomb the Brew makes after Slime Boss splits isn't legal
  (`a_smoke_bomb_it_makes_after_a_split_isnt_legal`).

### 6. Trigger `OwnerApplied` (Champion Belt)

The game (`ApplyPowerAction.java` ~105, `relics/ChampionsBelt.java`):
when the player applies Vulnerable to another creature that has no
Artifact, the relic queues 1 Weak on it from the player.

- **Trigger `OwnerApplied`**: the player's hooks (relics, then powers),
  when a power the player applied to another creature lands (after the
  replacements: Artifact's cancel means it didn't land, the game's
  `!hasPower("Artifact")`). `Target::Opponent` is that creature, as for
  `OwnerAttackHit`. Applications made by an `OwnerApplied` hook don't
  fire it again.
- **Condition `{"Applying": "<power>"}`**: the power being applied is
  this one (true only under `OwnerApplied`; a load error under any other
  trigger). It is the net's existing condition column `Applying(<power>)`
  from the fight vocabulary.
- **Champion Belt**: `OwnerApplied`, `Applying Vulnerable` -> Apply Weak
  1 `Opponent`. It fires for Bash, Thunderclap, Uppercut, Shockwave, Bag of
  Marbles and Fear Potion alike (every source is the player).
- The Weak lands at once; the game's lands after the card's other
  actions. No Act 1 card tells them apart (a debuff after the Vulnerable
  on the same target can't meet a fresh Artifact); named.

### Content format and wording

New words: the pick key `free_this_turn`, `PlayTop`, the potion key
`fights`, `Escape` in a potion, `ObtainRandomPotions`, the relic key
`potion_slots`, `OwnerApplied`, `Applying`. Each in
`registry::element_names()` with its words in `content/wording.json`.
Entries go in `content/packs/act1-relics.json`, `act1-potions.json` and
`act1-ironclad.json`.

### State and codec

Three new state parts, each written by the codec under a new tag only
when it isn't empty: `free_in_hand`, `top_queue`, `escaped`. Every other
state's bytes are unchanged. (Tags are numbered after rebase onto
whatever the other three sessions landed.)

### The net

- New row column: trigger `OwnerApplied` (one zero column per mode).
  `Applying(<power>)` exists.
- Cards in `top_queue` are written in the existing `playing` pile slot.
- No column for `free_this_turn`, `PlayTop`, `ObtainRandomPotions` or
  `potion_slots` (as `HealOf`): card and potion vectors keep their width,
  so the contract tiny nets keep loading. A marked card reads as a hand
  card at its base cost (the net's `cost` column is the base cost already,
  docs/specs/cost-changes.md); a net that sees the mark is a later inputs
  lane, for P3's potions too. `Escape` already has its effect column.
- Existing nets' inputs in their layouts are byte-identical; default-width
  pins move by the one added zero column.

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden, rules version | byte-identical, unchanged | golden test |
| Fights without the new words | identical play and codec bytes | `relic_baseline`, `codec` pins |
| Existing nets | byte-identical inputs in their layouts; `series_check` PASS | product-layout pins, `series_check` |
| Default-width pins | old columns equal by name, the new one zero | re-pin per `docs/extending.md` |
| Picks, potions | existing picks and potion uses unchanged | `potion_use`, `decisions` |
| P3's discovery | one mark for both | P3's tests on the mark |
| Search speed | `series_speed` at most 10% slower | job (last step) |

## When in doubt

The game's decompiled class over the research doc's line; an unchanged
fight without the new words over anything else.

## Scope

May change: hooks (trigger, condition), effects, the pick, the stage
machine (top queue, escape), card cost (`cost_of`), potion legality and
binding, relic keys, registry parse, key lists, element names, wording,
the official writer, `py/src/features.rs`, `py/src/lib.rs` (`escaped`),
the three Act 1 pack files, tests, docs, facts.

Off limits: `golden.txt`; existing nets' inputs in their layouts; configs,
yardsticks, controls; the gauntlet and run layer; saved packs and data.

## Decisions taken (coordinator session, 2026-11-12)

- The mark's form, shared with P3: `free_in_hand` beside the hand, set
  by a pick key `free_this_turn` or `mark_free_in_hand`, the marked copy
  played first and kept last, cleared at turn end; no net column. Chosen
  over a per-copy card variant (no slot cap, works in official fights).
  This session builds it; P3 uses it.
- The mark and Liquid Memories land alone, first (a codec tag only for a
  non-empty mark, no row column, no re-pin); the rest lands after, the
  re-pin on top of R12's.
- Havoc joins the C8 step (one card more for the same piece).
- Smoke Bomb stays in: its fight part is small (an existing word, a flag,
  a potion key); the reward cost waits for P2.
- Potion Belt's `potion_slots` comes with Entropic Brew (it is how a fight
  knows its slot count).

## Outside assumptions

The decompiled game (aeubanks/sts, read 2026-11-12): the relic, potion
and card classes named above, `ApplyPowerAction`, `PlayTopCardAction`,
`NewQueueCardAction`, `GameActionManager`, `AbstractPlayer.useCard`,
`AbstractCard` (`setCostForTurn`, `canUse`, `hasEnoughEnergy`),
`AbstractRoom` (`endTurn`, `endBattle`, `smoked`), `AbstractDungeon`
(`returnRandomPotion`), `PotionHelper` (65/25); each test names its line.

## Verification

Written first, passing on unchanged code: `relic_baseline`, the codec
pins, the product-layout pins.

Then, in `act1_relics.rs`, `act1_potions.rs` or a new `act1_singles.rs`:
- Art of War: turn 1 never gains; a turn with only Skills gives +1 energy
  at the next turn start (4 energy); a turn with an Attack doesn't; a
  caller's counter 1 doesn't give turn 1 energy; with `turn1_pre_draw`
  the same.
- Pocketwatch: 3 cards on turn 1 -> turn 2's hand is 8; 4 cards -> 5;
  turn 1's hand is 5; a Double Tap copy counts.
- Liquid Memories: Strike in discard returns at cost 0 (play it at 0
  energy); the mark goes at turn end (the card costs 1 next turn); with
  two Strikes in hand, one marked, playing one spends 0 and the other
  costs 1; a discard pick takes the unmarked copy; Sacred Bark returns 2;
  hand full: nothing; Whirlwind returned stays X-cost; the state with a
  mark round-trips through the codec; `mark_free_in_hand` marks nothing
  for a 0-cost, X-cost or unplayable card, nor past the copies in hand.
- Distilled Chaos: draw pile [Strike, Defend, Bash] on top -> all three
  play free, energy unchanged, cards played +3; a draw pile of 1 with a
  discard of 2 takes the one, reshuffles, takes two more, and the first
  card can't come back; Pommel Strike's draw doesn't draw the queued
  cards; a target killed by the first card wastes a later targeted card
  (to discard, not counted); a Wound goes to discard unplayed; Whirlwind's
  X is the energy at use and spends none; Bark plays 6; Havoc exhausts
  the card it plays; a queued True Grit+ opens its pick and the queue
  continues after `Done`; the open queue round-trips through the codec;
  `greedy_action` and the search finish fights holding it.
- Smoke Bomb: in a hallway fight the use ends the fight, `escaped`, won,
  HP kept plus Burning Blood's 6 (and Meat on the Bone's 12 at half HP);
  not a legal action against Slime Boss, nor after its split.
- Entropic Brew: holding only the Brew, use gives 3 potions (the odds of
  one slot sum to 1: 65/25/10 by rarity, uniform within, no Fruit Juice);
  with 2 others held it gives 1; with Potion Belt it fills 5 - held; a
  Speed Potion it makes works (its pack power is bound).
- Champion Belt: Bash on Jaw Worm gives 2 Vulnerable and 1 Weak;
  Thunderclap on three Louses gives each 1 Weak; Bash on a Sentry with
  Artifact 1 gives neither (Artifact goes); Shockwave on that Sentry: Weak
  3 blocked, Vulnerable 3 lands, Belt's Weak 1 lands; Bag of Marbles with
  the Belt gives every monster 1 Weak; a monster's Vulnerable on the
  player gives nothing.
- wording: every new word has its text.

## Build steps

Who builds each step (coordinator session, 2026-11-13: the owner split
singles up): steps 1-4 and the queue's part of step 8 by the act1-singles
session; step 5 by act1-p5, step 6 by act1-p6, step 7 and its row column
in step 8 by act1-r14, each from this spec on main in its own worktree.

1. Pins first (as Verification's first line).
2. The mark, `mark_free_in_hand` and `free_this_turn` (state, codec,
   cost, picks, upgrades, turn end); Liquid Memories. Land alone; tell P3
   the hash.
3. Art of War and Pocketwatch (content only).
4. `PlayTop` and `top_queue` (chance event, stage machine, codec);
   Distilled Chaos, Havoc, Havoc+.
5. `Escape` in a potion, `escaped`, boss kinds, the potion key `fights`;
   Smoke Bomb. **Built** (session act1-p5, 2026-11-13; with the
   boss-fight mark, section 4's amendment).
6. `potion_slots`, `ObtainRandomPotions`, the potion pool's binding;
   Entropic Brew, Potion Belt. **Built** (session act1-p6, 2026-11-13;
   with 40 card slots and the boss-fight mark's maker half, section 5's
   amendments).
7. `OwnerApplied`, `Applying`; Champion Belt. **Built** (session
   act1-r14, 2026-11-13).
8. Net: the queue in the `playing` slot (act1-singles); the trigger
   column, re-pinned by column name on top of current main (act1-r14);
   `series_check`.
9. Research doc rows, facts; `series_speed` job.
