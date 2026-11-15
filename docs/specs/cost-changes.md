# Cost changes in combat (building block C5)

Status: closed (2026-11-09, built and in use; c4931ef6, checkpoint c5-built passed; docs/research/act1-inventory.md "Block C5 as built"; decisions "C5 cost changes: one HP-loss counter and two power fields").

Follows C3 (`docs/specs/draw-triggers.md`), whose shape it copies.

## Outcome

A card's cost can change during a combat: a card can cost less for each
time its owner lost HP this combat, and a power can set the cost of every
card of a type and exhaust those cards when played. Blood for Blood and
Corruption (4 entries with upgrades) then load from
`content/packs/act1-ironclad.json` and play as in the game.

**How it moves the goals.** Goal 1 asks for first-class custom content:
"costs less when ..." and "cards of type X cost 0" are among the game's
commonest card and power words (Blood for Blood, Corruption, later
Masterful Stab, Eviscerate, Force Field, Snecko-like effects), and without
an effective cost a designer can't write any of them. Goal 2 needs the
real Act 1 card pool: Corruption is one of Ironclad's strongest rares and
the centre of the exhaust decks C1 and C2 built for. We'll know by the
lane's measure: blocked Ironclad cards drop from 11 to 9, each entry is
checked against the wiki and sts_lightspeed in a test, and the series
checks hold (golden identical, `series_check` PASS, `series_speed` at most
+10%, sanity pair identical).

**Non-goals.** No change to official content, golden or the rules
version. No "costs 0 this turn" for one card (Infernal Blade, block C11
with C5): every cost change here applies to all copies of a card alike,
so piles stay counts of card ids. No Masterful Stab (costs more), no
Snecko Eye. The generator's vocabulary is unchanged. No retraining, no
headline read. The heuristic's estimates keep the base cost; the net's
`cost` column keeps the base cost (a net seeing effective costs is a
later inputs lane).

## Behavior

**Effective cost.** `CombatState::cost_of(card)` is the cost every
reader uses (legality, the energy spent, the greedy agent): the card's
base cost, minus its HP-loss reduction (below), floored at 0; then, if
the player holds a power whose `sets_cost` names the card's type and the
cost is above that power's value, that value. X-cost and unplayable cards
are never changed (as sts_lightspeed's `cost > 0` guard and the wiki's
Weekly 44 note).

**Cost less per HP loss (Blood for Blood).** New card field
`"cost_less_per_hp_loss": true`: the card costs 1 less for each time the
player lost HP this combat. A time is one HP-loss event with more than 0
HP lost, any source (attack damage past block, Bloodletting, Offering,
Hemokinesis, Brutality, Combust): the engine's `lost_hp` for the player,
as sts_lightspeed's `Player::hpWasLost` (`++timesDamagedThisCombat`).
A hit fully blocked or reduced to 0 doesn't count.
- **Per copy (the game's `updateCardsOnDamage` -> `tookDamage`).** Each
  loss drops by 1 (floored at 0) the cost of every copy in the hand, draw
  and discard piles, as a changed copy at that combat cost
  (docs/specs/sparse-piles.md); a copy in play (limbo: Sharp Hide's thorns
  while it is being played) and the exhaust pile keep theirs. Free marks
  and known-top ids follow their copies. An upgrade moves the copy's cost
  by the upgrade's change, floored at 0 (`BloodForBlood.upgrade`: a cost
  below 4 becomes cost - 1), so it keeps its drops.
- **State.** The counter `times_lost_hp` (the game's
  `damagedThisCombat`) stays only for copies made in the fight, counted
  only when the fight's binding holds a card with the field (official
  content never touches it: golden and every encoding stay the same),
  capped at the largest base cost among those cards. Part of equality and
  hashing; the codec writes it only when nonzero, under a new tag.
- **Copies made mid-combat** (`makeCopy`: Infernal Blade, Discovery, potion
  picks) start at their cost less the counter; a stat-equivalent copy (Dual
  Wield) keeps its source's cost.

**Type cost and exhaust (Corruption).** New pack power fields, parallel
to `forbids`:
- `"sets_cost": {"type": "Skill", "cost": 0}`: while the owner holds the
  power, cards of that type with an effective cost above `cost` cost
  `cost`.
- `"exhausts_played": "Skill"`: while the owner holds the power, a card
  of that type the player plays exhausts instead of going to the discard
  (through `exhaust_card`, so C2's exhaust triggers fire: Feel No Pain,
  Dark Embrace). Decided where the played card is placed; a card that
  already exhausts exhausts once. A replayed copy (goes to no pile) is
  unchanged.
- Both read the held power only (stacks don't matter): a second
  Corruption adds a stack and changes nothing, as the wiki says. A
  monster holding such a power is unaffected (monsters play no cards).
- Load refuses, with a message: a `sets_cost` type other than Attack,
  Skill or Power, a cost below 0 or above 9; an `exhausts_played` type
  other than those three.

The four entries (numbers from sts_lightspeed `BattleContext.cpp`,
`Cards.h` and wiki.gg, read 2026-11-09; both agree):

| Card | Cost | Type | Entry |
|---|---|---|---|
| Blood for Blood | 4 / 3 | Attack, Uncommon | Damage 18 / 22 to one target; `cost_less_per_hp_loss` |
| Corruption | 3 / 2 | Power, Rare | Apply `Corruption` 1; power `sets_cost` Skill 0, `exhausts_played` Skill |

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Official content, rules version | golden identical; official files round-trip byte for byte | `golden.rs`, `official_files.rs` |
| Legality and energy | every existing card costs its base cost; X-cost cards spend all energy | existing state tests, a new test |
| C1/C2 exhaust and triggers | same results with no `exhausts_played` power held; Corruption's exhausts fire `CardExhausted` hooks | `exhaust.rs`, `exhaust_triggers.rs`, a new test |
| Entangled (`forbids`) | still forbids its type regardless of cost | existing test |
| Codec | old encodings decode the same; a state with the counter nonzero round-trips | `codec.rs`, a new test |
| Solver bounds | no new effect heals | `Effect::heals` |
| Net features (`py/src/features.rs`) | a net's stored layout gathers the same columns; new fields are columns of the full layout only | features tests; the product net's `layout_names` unchanged |
| Heuristic | estimates on existing content unchanged | `series_check` |
| Pack writer | the new fields written and read back equal | round-trip of the 4 entries |
| Wording | new names in `registry::element_names()` and `content/wording.json` | `engine/tests/wording.rs` |
| Speed | `series_speed` at most +10% | `scripts/series_speed.py` |

**When in doubt:** prefer the game's behaviour as sts_lightspeed codes it
over a neater engine rule, except where `decision/parity-source` says the
wiki decides; and prefer a rule that applies to all copies of a card over
per-copy state.

## Scope

May change: `engine/src` (state's cost reader and its callers, the
counter, registry parse, write and refusals, codec, the greedy agent),
`py/src` (features), `engine/tests`, `content/packs/act1-ironclad.json`,
`content/wording.json`, `docs/research/act1-inventory.md`, this spec. New
JSON names `cost_less_per_hp_loss`, `sets_cost`, `exhausts_played`; the
codec gains a tag for the counter without changing old ones.

Off limits: official content files and anything that changes golden;
`Action` and the decision interface; the generator; the heuristic's
values; training, gauntlet and run-layer scripts.

## Decisions taken

- (on the owner's behalf) One combat-wide counter of HP-loss events, not
  a cost per card copy: piles stay counts, and it matches the wiki on
  copies made mid-combat; the cost is the Exhume difference above.
  Alternative: per-copy costs (sts_lightspeed's way; changes every pile's
  representation, needed later for C11's "costs 0 this turn").
- (on the owner's behalf) The counter exists only when the binding holds
  a card that reads it, capped at the largest such base cost.
  Alternative: always count (simpler, but changes every official state's
  equality and encoding, and splits states that play the same).
- (on the owner's behalf) Corruption as two power fields, like `forbids`,
  not as statics or a hook: cost and pile placement aren't numbers the
  static stages modify, and a hook would fire after placement.
  Alternative: a `CardCost` static with a type condition plus a
  `CardPlayed` hook that exhausts the card in play.

## Outside assumptions

- Numbers and rules as in the table and above, read from sts_lightspeed
  (`BattleContext.cpp` `useAttackCard`, `usePowerCard`, `useCard`;
  `CardManager.cpp` `onTookDamage`, `onBuffCorruption`, `draw`;
  `Player.cpp` `hpWasLost`; `Cards.h` costs from a summary, not verbatim)
  and wiki.gg on 2026-11-09 (fandom returned HTTP 402). Step 1 re-checks
  the two `Cards.h` cost lines and records the source check in the
  inventory.

## Verification

Tests first (`engine/tests/cost_changes.rs`, packs from
`act1-ironclad.json`):
- `blood_for_blood_costs_less_per_loss`: base 4 (upgraded 3); after one
  unblocked monster hit 3; after Bloodletting 2; after a hit fully
  blocked still 2; never below 0 after 6 losses; playable with 0 energy
  at cost 0 and spends exactly its effective cost.
- `counter_capped_and_off_without_card`: with Blood for Blood bound, 5
  and 7 losses give equal states (cap 4); a fight without the card never
  moves the counter (official starter vs Jaw Worm: state equal to a
  build without the field, codec bytes unchanged).
- `corruption_skills_cost_zero_and_exhaust`: with Corruption held,
  Defend costs 0 and goes to the exhaust pile; Shrug It Off with
  Corruption exhausts once; an Attack still costs its cost and is
  discarded; Feel No Pain gives block for each Corruption exhaust.
- `corruption_leaves_x_and_unplayable`: an X-cost Skill (a test card)
  still spends all energy; an unplayable Skill stays unplayable.
- `second_corruption_changes_nothing`: two Corruptions played equal one
  in cost and placement.
- Load refusals: `sets_cost` with type `Status` or cost 10,
  `exhausts_played` with `Curse`, each with a message.
- Codec, equality and hashing with the counter nonzero; existing
  encodings unchanged.
- A mutation check: reading `def.cost` instead of `cost_of` in legality
  fails `blood_for_blood_costs_less_per_loss`.

End to end: a greedy player with the starter deck plus Blood for Blood,
Bloodletting, Corruption, Feel No Pain and Shrug It Off beats a Jaw Worm
in most of 40 seeds, Blood for Blood played below its base cost in most
games where it was played, and a Skill exhausted by Corruption in most
games where Corruption was played (counts over the games).

Don't guard: per-copy costs and "this turn" costs; Masterful Stab;
Strange Spoon; run-layer rewards for pack cards; encodings from builds
before this one beyond what `codec.rs` already checks.

## Build steps

1. Write the tests above (against stubs: the fields parse and do
   nothing) and the four pack entries; re-check the costs in
   sts_lightspeed's `Cards.h` and write the source check into the
   inventory. Check: the tests compile and fail only on the missing
   behaviour; existing suites pass.
2. Engine: `cost_of` and its callers (legality, energy, greedy), the
   counter (bound only with the field, capped, equality, hashing, codec
   tag), the two power fields (parse, write, refusals, wording),
   `exhausts_played` in `finish_card`. Check: the cost-change and codec
   tests pass; golden identical; engine suites pass.
3. `py/src` features: the new fields as columns of the full layout only,
   re-pins as C3 did. Check: features tests pass; the product net's
   `layout_names` unchanged.
4. End to end and series checks: the greedy check; `series_check` PASS;
   `series_speed` at most +10% (queued, `--threads 4`); a sanity pair of
   the product on 20 headline sequences (queued, old and new build)
   identical per sequence; inventory counts (blocked 11 -> 9). Check: all
   pass and are recorded in the inventory.

Build plan: 4 steps, forks in the lane worktree, on Opus. No stop
points: every decision above is reversible.
