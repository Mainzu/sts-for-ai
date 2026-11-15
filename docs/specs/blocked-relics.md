# Blocked Act 1 combat relics

Status: confirmed (2026-11-13, by the act1 manager session (owner chose "blocked combat relics" next); not built yet).

Research: `docs/research/blocked-relics-2026-11-13.md`. Five readers read
every relic's class in the installed jar and the engine code, and a skeptic
per group re-read both. Each step's session reads its relics' entries there
first: the game facts, the draft entries and the skeptics' corrections are
not repeated here.

## Outcome

All 25 Act 1 relics that are blocked by a combat engine piece load from
`content/packs/act1-relics.json` and act as the game's classes, plus the
Ironclad card Barricade (it shares Calipers' piece). Act 1 relics go from
59 to 84 of 141 (`docs/INDEX.md`); Ironclad cards from 70 to 71 of 75.

**Non-goals:**
- Out-of-combat parts and counters carried between fights (R2, the run
  layer): Neow's Lament's 3 uses and Sundial's shuffle count start from the
  caller's counter, as Pen Nib's does today.
- Which curses can enter a deck (events, Cursed Key): step 6 adds the Curse
  type and the curses Act 1 content can put in a combat deck, nothing more.

## Steps

Each step lists its relics and the engine piece; sizes from the research.
Steps are independent except where named, so they can be built in parallel
sessions, each in its own worktree.

### Step 1: relic statics and turn-boundary rules (S each)

- **Chemical X**: relic key `x_bonus` 2: X-cost cards act as if 2 more
  energy were spent (the `EnergySpent` quantity), not more energy paid.
- **Ice Cream**: relic key `keeps_energy`: unspent energy carries into the
  next turn.
- **Velvet Choker**: relic key `plays_per_turn` 6 (+1 energy per turn): a
  card is not playable once 6 have been played this turn.
- **Runic Pyramid**: the hand isn't discarded at turn end (ethereal cards
  still exhaust; Burn, Regret and Decay still act: see the skeptic's note).
- **Calipers** and **Barricade**: a rule for block lost at the player's
  turn start (`block_loss`: Calipers 15, Barricade keeps all). Barricade is
  a pack power from the Ironclad card (cost 3, 2 upgraded).

### Step 2: combat-start HP and Vulnerable statics (S)

- `Effect::CapHp`: a direct HP write (no HP-loss hooks, no bloodied, as the
  game's field write). **Preserved Insect** (elite fights: HP to 75% of max
  when above it; the gate is the room's elite flag), **Neow's Lament**
  (every monster to 1 HP, counter 3; hook order so one fight spends one).
- `StaticCondition::Holds { side, power }`: **Paper Phrog** (Vulnerable on
  a monster x1.75), **Odd Mushroom** (Vulnerable on the player x1.25), each
  as a helper pack power, as Strike Dummy. The hand-computed readers named
  in the research (heuristic, agent incoming damage) read the engine's
  helper or are listed as known gaps.

### Step 3: the shuffle trigger (M)

`Trigger::Shuffled` (the player's relics): every place the game calls
`onShuffle` (empty-draw reshuffle, and the double fire the research found
when a draw needs more than draw plus discard). **Sundial** (counter, every
3rd: +2 energy), **The Abacus** (6 block). Deep Breath's `onShuffle`
(colorless step 4 left it waiting) fires here too.

### Step 4: potions, healing and debuffs (S-M)

- `Trigger::OwnerUsedPotion`: **Toy Ornithopter** (heal 5).
- Relic key `heal_scale` [3, 2]: **Magic Flower** (heals in combat x1.5,
  rounded as the game rounds).
- `Effect::RemoveDebuffs`: **Orange Pellets** (an Attack, a Skill and a
  Power played this turn: remove the player's debuffs; once per turn).

### Step 5: random work owed by hooks (M; audit #13 and #29's narrow case)

A small queue of random work a hook owes, turned into a chance event before
anything else, as `cost_rolls` is today. **Dead Branch** (on exhaust: a
random class card to hand, `MakeRandom` from colorless step 3),
**Mummified Hand** (on a Power played: a random hand card costs 0 this
turn), **Warped Tongs** (turn start: upgrade a random hand card). The
loader's refusal of random effects in hooks (`runs_outside_a_card`) lifts
for these effects only.

### Step 6: curses and unplayable cards (M)

- `CardType::Curse`, and the curses an Act 1 combat deck can hold, as
  official cards with their combat effects (the research lists them).
Built 2026-11-14: the 13 curses an Ironclad run can hold (Pride left out:
no event, relic or `getCurse` gives it), in `act1-colorless.json`; tests
`act1_relics` curses_load_as_their_classes to du_vu_doll.

- **Du-Vu Doll**: +1 Strength per curse in the deck at combat start
  (a quantity counting cards of a type).
- A rule making unplayable cards of a type playable at cost 0: **Blue
  Candle** (curses; playing one loses 1 HP and exhausts it), **Medical Kit**
  (statuses; exhausts). The loader's `playable_type` widens accordingly.

### Step 7: three event triggers (M each)

- `Trigger::OpponentBlockBroken`: **Hand Drill** (Vulnerable 2 to that
  monster), fired where the game's `brokeBlock` is, the exact-break case
  included.
- `Trigger::OwnerHandEmpty`: **Unceasing Top** (draw 1 when the hand is
  empty during the player's turn).
- **Strange Spoon**: a 50% chance event when a card would exhaust; on a
  hit it goes to the discard pile instead.
Built 2026-11-14: relic key `exhaust_save` [1, 2] and
`ChanceEvent::ExhaustSave` (a card Havoc can't play rolls too, as the
game's `UseCardAction`); `block_broken` per monster, fired after the card
or potion, after each monster's move and at the turn's end. Unceasing
Top's "No Draw" check waits for a No Draw power (none in the engine yet).
Tests `act1_relics` hand_drill to step7_relics_load_with_their_rarity.

### Step 8: Frozen Eye (L; behaviour fixed by `docs/specs/rules-engine-upgrade.md`)

The information principle there: a random outcome is rolled when the
player can see it. With Frozen Eye the whole draw pile is visible, so the
known-top prefix covers the whole pile ("Consequences": "the prefix
covering the whole pile"):
- A reshuffle (and the combat's opening shuffle) is one chance event over
  the pile's orderings, rolled and known at once; search samples it (it
  is divergent), the solver may enumerate it.
- Every draw after it is deterministic; a card added to the draw pile
  takes a rolled, known position (the game's random spot).
- `TOP_KNOWN` (16) and the codec's known count grow to hold a whole pile;
  existing encodings stay byte-identical.
- The net reads it as the `next_draw` pile (the next turn's draw, a bag)
  and the `known_later` pile (every later known card, one bag with no
  order), as the format section there says. A net without those piles
  (the product net has 5 piles) reads both folded into `draw`
  (`features.rs` `PILE_PARENTS`), so it sees nothing of the order: the
  relic's gain then comes from the search's exact draws only. The step
  does not change the encoding.

### Step 9: Runic Dome (M-L; behaviour fixed by `docs/specs/rules-engine-upgrade.md` "Information principle")

+1 energy per turn, and intents hidden: with the relic held, the monster's
move roll moves from the start of the player's turn to the moment the
monster acts. End Turn pauses at the roll before the monsters act, so this
turn's incoming damage is inside the chance leaf; move history stays
visible, so repeat limits and phases condition on known state and the
deferred roll has the early roll's distribution (keep today's random calls
in today's order so golden stays identical without the relic). The
evaluator estimates the hidden move from the monster's move patterns:
the `lookahead` encoder columns (`docs/specs/monster-lookahead.md`, built,
off by default) are the existing input for that; whether a net reads them
in Dome fights is the step's call, measured, not assumed. Hand-computed
readers (intent damage, the heuristic) must not read a move the player
can't see: list each and what it reads instead.

## Rules for every step

- Each new word in `registry::element_names()` with words in
  `content/wording.json`; re-record the explorer's wording pin and check
  the diff is new entries only.
- Each relic and Barricade gets a test against its class (numbers, timing,
  order) in `engine/tests/act1_relics.rs` (Barricade in the Ironclad
  tests); the skeptics' corrections are part of what the tests pin.
- Golden files must not change. If a step would change them, it stops and
  reports to the manager session.
- New state fields or chance events append codec bytes; existing encodings
  stay byte-identical.
- Owner's test budget: debug engine tests covering the change plus golden;
  no full suite, no release tests, no speed checks. `CARGO_BUILD_JOBS=2`;
  never `cargo fmt`.
- Landing: rebase on main, lock `act1-release`, one release wheel,
  `jobs.py impact sts` in the commit, swap main's `sts`, push; then the
  docs index (`scripts/docs_index.py --write`) and kb
  `measurement/act1-relics@files`.

## Verification

Done when the 25 relics and Barricade load with passing tests, golden is
unchanged, and `docs/INDEX.md` shows 84 of 141 relics and 71 of 75 cards.
