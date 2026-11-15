# Colorless cards, Colorless Potion and Toolbox

Status: closed (2026-11-13, built and in use; steps 1-6 on main, d9597601; 25 colorless cards, Warcry, Colorless Potion, Toolbox; As built: docs/extending.md).

Research: two readers and eight skeptics checked every
game fact below against the installed jar (`desktop-1.0.jar`, `javap`;
kb `decision/parity-source`) and every engine claim against the code.

## Outcome

25 of the game's 34 in-combat colorless cards load from
`content/packs/act1-colorless.json` and act as the game's classes, with
Warcry (Ironclad, blocked since C7), Colorless Potion and Toolbox. That
moves Act 1 (`decision/act1-finish`) to 33 of 33 potions and one more
relic, and gives packs eight new words.

**Non-goals** (each needs a bigger engine piece; listed with it in
`docs/research/act1-relics-potions.md` "Missing building blocks"):
The Bomb (separate countdowns per card played: per-instance powers),
Panache (a counter on a power), Forethought (a known bottom of the draw
pile). Enlightenment,
once a Non-goal (a "costs 1 this turn" mark), loads since the colorless
build A (`CombatState::turn_costs` beside `free_in_hand`, effect
`CostAtMost`; docs/research/build-plans-2026-11-14/colorless-piles.md).
Every random pick in the hand (Madness, Mummified Hand, Warped Tongs,
True Grit) rolls over copy classes (`HandMark`: unmarked, each cost this
turn, marked 0), and Dual Wield's copy carries a cost-this-turn mark.
Secret Technique, Secret Weapon and Violence, once Non-goals (taking
cards out of the draw pile), load since the colorless build B: the pick
`DrawToHand`, the condition `DrawHas` (their `playable_if`), the effect
`TakeRandomFromDraw`, and `ChanceEvent::DrawInstance` / `TakeRandom`
(`CombatState::instance_outcomes`, `Top::without`:
docs/research/build-plans-2026-11-14/colorless-piles.md). A card taken
out of the draw pile keeps what the player knows of its order exact:
which copy left is a chance event when the copies differ in what is
known (a known head card, a floater, a plain card), and a floater's
knowledge gains a **slack** (docs/specs/draw-knowledge.md). Known
difference (accepted, as draw-knowledge item 1's search knowing which
instance went): Secret Technique and Secret Weapon take a uniformly
random copy of the chosen kind, as a player picking among identical grid
cards at random would; the game's grid puts the bottommost Skill (Attack)
of the draw pile always in its last slot, so a player could take that
copy on purpose and learn its kind, which the engine doesn't model.
Violence is the game's own rule (a shuffled sample without replacement).
Magnetism, once a Non-goal (a random card in a
power hook), loads since that piece landed (blocked-relics step 5;
docs/research/build-plans-2026-11-14/colorless-powers.md build A), and
so does Mayhem (build B: a power's `PlayTop` hook owes its takes behind
the turn start, `CombatState::owed_late`). Known difference: past 6
Mayhem stacks the takes stop at `TOP_QUEUE_CAP` (6), then one card plays,
one more is taken and so on, where the game takes all of them first; it
shows only when a played card changes the draw pile. Hand of Greed's
gold is the run layer's (R2); its combat part loads.

## The colorless pool

`AbstractDungeon.returnTrulyRandomColorlessCardInCombat`: uniform over
`srcColorlessCardPool` minus HEALING cards. That pool is every colorless
card that is not BASIC, SPECIAL or STATUS (`addColorlessCards`): 19
uncommon and 15 rare once Bandage Up (HEALING) is cut. Unlocks,
ascension and character don't change it.

The pack declares `"pools": {"Colorless": [...]}` with the loaded cards
only. Until all 34 load, its odds differ from the game's, as the Ironclad
pool's do today; `engine/tests/discovery.rs` checks it equals the game's
34 minus the cards that don't load, so a newly loaded card goes into it.

## The cards

Values from each class's constructor, `use()` and `upgrade()`. No
upgrade changes a cost unless named. "Successor" means an upgraded entry
named `<id>+` right after its base card, for an upgrade that changes more
than numbers or keywords (as True Grit+).

### Step 1: writable with today's words (15 cards and Colorless Potion)

| Card | Cost | Type, rarity | Effects | Upgrade |
|---|---|---|---|---|
| Swift Strike | 0 | Attack, U, tag Strike | Damage 7 | +3 |
| Flash of Steel | 0 | Attack, U | Damage 3, Draw 1 | Damage +3 |
| Finesse | 0 | Skill, U | Block 2, Draw 1 | Block +2 |
| Good Instincts | 0 | Skill, U | Block 6 | +3 |
| Dramatic Entrance | 0 | Attack, U, exhaust, innate | Damage 8 to all | +4 |
| Blind | 0 | Skill, U | Weak 2 to one enemy | successor: Weak 2 to all |
| Trip | 0 | Skill, U | Vulnerable 2 to one enemy | successor: to all |
| Panacea | 0 | Skill, U, exhaust | Artifact 1 to self | +1 |
| Master of Strategy | 0 | Skill, R, exhaust | Draw 3 | +1 |
| Purity | 0 | Skill, U, exhaust | exhaust up to 3 chosen hand cards (0 allowed) | up to 5 |
| Hand of Greed | 2 | Attack, R | Damage 20 | +5 |
| Panic Button | 0 | Skill, U, exhaust | Block 30, then NoBlock 2 to self | Block +10 |
| Discovery | 1 | Skill, U, exhaust | Discover Ironclad, offer 3, free, no skip | not exhaust |
| Jack of All Trades | 0 | Skill, U, exhaust | Discover Colorless, offer 1 | successor: two Discovers (independent, may repeat) |
| Colorless Potion | - | potion, common | Discover Colorless, offer 3, free, no skip | potency: copies |

- **NoBlock** (pack power): debuff (Artifact blocks it), RoundEnd
  ReduceSelf 1, static BlockGained Multiply num 0 den 1. In the game it
  zeroes card block only (`applyPowersToBlock`), as Frail scales only
  card block; the step checks the engine's potion, relic and power Block
  paths skip the static as they skip Frail, and fixes any that don't.
- **Purity**: an any-number hand pick of up to 5 can blow up search
  memory (`docs/specs/series-review-fixes/D-loader.md`); the step
  measures one search on a 10-card hand at n 5 and reports it.
- Colorless Potion's game class is read in the step (potency, skip,
  rarity) before writing it.

### Step 2: three conditions (Impatience, Dark Shackles, Sadistic Nature)

- `Condition::HandNone(type)`: no card of that type in hand, checked when
  the row is reached (the card in play has left the hand, as in
  `ConditionalDrawAction`). Impatience: row HandNone Attack: Draw 2 (+1).
- `Condition::TargetLacks(power)`: the chosen target holds none. Dark
  Shackles (exhaust, 9, +6): first the row TargetLacks Artifact: apply
  pack power **Shackled** n, then Strength -n (the game reads
  `hasPower(Artifact)` at play, before its own Strength -n spends it).
  Shackled: OwnerTurnEnd Apply Strength +stacks to self, RemoveSelf; not a
  debuff (the audit's owner note: a signed buff, so Sadistic Nature needs
  no "not Shackled" exception).
- `Condition::ApplyingDebuff` for `OwnerApplied` hooks: the applied power
  is a debuff, or `debuff_if_negative` with a negative amount. Sadistic
  Nature (Power, 0, 5, +2): pack power, OwnerApplied ApplyingDebuff:
  PlainDamage stacks to the target. Known gap kept: `IN_OWNER_APPLIED`
  stops a debuff applied inside another OwnerApplied hook from firing it.

### Step 3: random cards made, not offered (Chrysalis, Metamorphosis, Transmutation)

The game rolls each card on its own (repeats allowed); `Discover`'s offer
draws different cards, so these get their own effect.

`Effect::MakeRandom { pool, type?, n: Amount, pile: Hand|Draw, zero_cost,
free, match_level }`: n independent uniform rolls of the pool, each a
chance event; to hand (overflow to discard) or to the draw pile at a
random spot that is never the top (`addToRandomSpot`: uniform over the
slots under the current top; with a known top, under it); `zero_cost`
sets the copy's combat cost to 0 when above 0 (`registry::Overrides.cost`;
X and unplayable keep theirs); `free` is the this-turn mark;
`match_level` upgrades the copy when the card played is upgraded.

- Chrysalis (2, Skill, R, exhaust): MakeRandom Ironclad Skill n 3 (+2) to
  Draw, zero_cost. Metamorphosis: the same with Attack.
- Transmutation (X, Skill, R, exhaust): MakeRandom Colorless n
  EnergySpent to Hand, free, match_level. Chemical X isn't loaded, so X
  is the energy spent.

### Step 4: pile words (Thinking Ahead, Warcry, Mind Blast, Deep Breath, Apotheosis)

- `PickKind::HandToTop` (exactly n, automatic when the hand holds n or
  fewer; nothing when empty): the card goes on top as a known top
  (`Top::push`). Thinking Ahead (0, Skill, R, exhaust; upgrade not
  exhaust): Draw 2, HandToTop 1. Warcry: its class values, read in the
  step.
- `Quantity::DrawPileSize`, no net column. Mind Blast (2, -1 upgraded,
  Attack, U, innate): ScaledDamage DrawPileSize, a normal attack.
- `Effect::ShuffleDiscardIntoDraw`: the discard pile joins the draw pile,
  the known top and floaters are forgotten (the game reshuffles the whole
  pile). Deep Breath (0, Skill, U): it, then Draw 1 (+1). The `onShuffle`
  relic hook (fired once, only with a non-empty discard) waits for R24,
  as the natural reshuffle does.
- `Effect::UpgradeAll`: every upgradable card in hand, draw, discard and
  exhaust (not the card in play), remapping known-top and floater ids
  (`Top::map_cards`). Apotheosis (2, -1 upgraded, Skill, R, exhaust).

### Step 5: Madness

`Effect::ZeroCostRandom`: one random hand card with cost this turn above
0 (else with cost above 0) costs 0 for the combat (`Overrides.cost`),
its this-turn mark cleared; a chance event by copies, as ExhaustRandom.
Madness (1, 0 upgraded, Skill, U, exhaust).

### Step 6: Toolbox

Relic, shop: at battle start before the opening draw, Discover Colorless,
offer 3, not free, no skip (class read in the step). Hooks refuse
Discover today (`registry.rs` `runs_outside_a_card`); allow it in a
relic's `CombatStartPreDraw` hook only, with a pause that resumes the
turn start: a resume field on `Stage::RelicPick` (Gambling Chip's pause)
or a new stage, with its codec bytes appended. The offer's chance event
and pick land in that stage; the opening draw follows the pick.

## Rules for every step

- Each new word goes in `registry::element_names()` with words in
  `content/wording.json`; `engine/tests/wording.rs` names any miss.
  Re-record the explorer's wording pin (`scripts/tests`) and check its
  diff is only new entries; explorer text bans parentheses.
- Golden files must not change (`git diff --exit-code engine/tests/data`).
- Each card gets a test against its class's numbers and order
  (`engine/tests/colorless.rs`), base and upgraded.
- Owner's test budget: debug engine tests covering the change plus
  golden; no full suite, no release testing, no speed checks.
- `CARGO_BUILD_JOBS=2`; never `cargo fmt`.
- Landing: rebase on main, take lock `act1-release`, build one release
  wheel, `jobs.py impact sts` in the commit, swap main's `sts`, push.
  Steps touch the same pack file and registry: land one at a time and
  rebase onto the last landing.
- Update `docs/research/act1-relics-potions.md` (Colorless Potion,
  Toolbox), `docs/research/act1-inventory.md` (Warcry), kb
  `measurement/act1-relics@files` when counts move.

## Docs this spec corrects

- `docs/extending.md` "Pools and discovery": the per-fight pack-card
  limit is `registry::MAX_CARD_SLOTS` (thousands since sparse-piles), not
  40; `CARD_SLOTS` only names the slots that keep their old ids.
- `docs/specs/discovery.md` "Colorless pool": cost changes are built
  (`Overrides.cost`); this spec replaces that section's split.

## Verification

Done when the pack loads 25 colorless cards, Warcry, Colorless Potion
and Toolbox, each with a passing test; the pool test passes; golden is
unchanged; `docs/research/act1-relics-potions.md` shows Colorless Potion
and Toolbox loaded with their tests.
