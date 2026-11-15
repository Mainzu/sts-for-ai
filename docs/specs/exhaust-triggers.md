# Exhaust triggers (building block C2)

Status: closed (2026-11-07, built and in use; lane act1-content block C2; 80938019; checkpoint c2-built passed, landed 092b64c3).

Builds on C1 (`docs/specs/exhaust-cards.md`).

## Outcome

Something can happen when a card is exhausted: a power reacts to any of
its owner's exhausts, and a card can carry effects that run when that card
itself is exhausted. Dark Embrace, Feel No Pain and Sentinel (6 entries
with upgrades) then load from `content/packs/act1-ironclad.json` and play
as in the game.

**How it moves the goals.** Goal 1 asks for first-class custom content:
"whenever a card is exhausted" is one of the game's core trigger words,
and without it a designer's exhaust synergy can't be written; C1 gave the
exhaust actions, this gives them consequences, which is what makes
exhaust an archetype rather than a cost. Goal 2 needs the real Act 1 card
pool: these three are the payoff cards of Ironclad's exhaust deck. We'll
know by the lane's measure: blocked Ironclad cards drop from 18 to 15,
each new entry is checked against the wiki and sts_lightspeed in a test,
and the series checks hold (golden identical, `series_check` PASS,
`series_speed` at most +10%).

**Non-goals.** No change to official content, golden or the rules
version. The random-content generator's vocabulary is unchanged. No
retraining, no headline read (pack content is outside every training
pool). No relics with exhaust triggers (Dead Branch, Charon's Ashes: step 4
of the lane). Corruption stays blocked (C5). The heuristic gives the new
trigger no value (as for every trigger it doesn't know today).

## Behavior

New pack vocabulary:

| JSON | What it does |
|---|---|
| hook `{"trigger": "CardExhausted", "condition": "Always", "effects": [...]}` | On a power: fires for each card its owner exhausts, from any pile or from play, by any route (a card's own exhaust flag, ethereal at turn end, `ExhaustHand`, `ExhaustRandom`, an `ExhaustFromHand` pick). Amounts are per stack, as for every hook. |
| card field `"exhausted": [...]` | On a card: effects that run each time a copy of this card is exhausted. |

The six entries (base / upgraded; numbers from the wiki, checked against
sts_lightspeed in build step 1):

| Card | Cost | Type | Entry |
|---|---|---|---|
| Dark Embrace | 2 / 1 | Power | Apply `DarkEmbrace` 1; power hook `CardExhausted`: Draw 1 |
| Feel No Pain | 1 | Power | Apply `FeelNoPain` 3 / 4; power hook `CardExhausted`: Block 1 (raw block, as every hook's: Dexterity and Frail don't apply, the game's GainBlockAction) |
| Sentinel | 1 | Skill | Block 5 / 8; `exhausted`: GainEnergy 2 / 3 |

**When the triggers fire (the game's order).** In the game, a power's
exhaust reaction is queued at the bottom of the action queue, behind the
card in play and behind that card's move to its pile. So:
- Exhausts while a card is in play (its effects, its picks, its random
  exhaust, its own exhaust flag) are counted; the hooks fire once the card
  has been placed (discard or exhaust pile), before the next decision or a
  replayed copy, with amounts multiplied by the count. Burning Pact with
  Dark Embrace draws 2 and then 1; with an empty draw pile, the Burning
  Pact just discarded can be the card drawn.
- Firing once with the count gives the same fight as firing per card for
  the allowed effects (a draw of n equals n draws of 1 from the same
  pile; raw block adds). So `CardExhausted` hooks must have condition
  `Always`, and their effects may not exhaust (no loops) or pause (no
  picks, random hits): both refused at load with a message.
- At turn end, ethereal cards are exhausted with the rest of the hand's
  placement; the hooks fire right after, before the monsters act (Feel No
  Pain's block counts against their attacks). In the game, Dark Embrace's
  draws there land after the hand was discarded and stay in hand for the
  next turn; the engine adds them to the next turn's draw instead (a draw
  owed to the next turn start). The difference: cards the monsters put
  into the piles in between can be drawn in the engine; in Act 1 they go
  to the discard pile, so it shows only when the draw pile runs out.
- Exhausts at other times outside a card (a hook's `ExhaustHand`) fire
  right after the hooks that caused them: after turn-start hooks, or with
  the turn-end firing above.
- C1's count-then-exhaust order (Second Wind, Fiend Fire read `HandCards`
  before their `ExhaustHand`) stays correct: triggers fire after the card,
  so nothing they do changes a count the card reads (the re-check C1's
  spec asked for).

**Card `exhausted` effects** run at once, when that copy lands in the
exhaust pile, once per copy (the game adds Sentinel's energy at the top
of the queue). They may hold only `GainEnergy` and `Block` (neither can
pause or end the combat); anything else is refused at load. Block there
is a card's block (Dexterity and Frail apply). A Sentinel exhausted at
turn end gains energy that the turn start then resets, as in the game.

**State.** Two counters: cards exhausted whose hooks haven't fired yet
(nonzero only while a card is in play, which can pause at a pick or a
chance event), and draws owed to the next turn start (nonzero only from
turn end to the next draw, across the monsters' chance events). Both are
part of state equality and hashing, and the codec writes them only when
nonzero, so every existing encoding is unchanged.

Monsters never exhaust: a monster holding a `CardExhausted` power never
fires it.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Official content, rules version | golden identical; every official file round-trips byte for byte (the writer emits `exhausted` only when non-empty) | `golden.rs`, `official_files.rs` |
| C1's exhaust cards | same results with no trigger power held | `exhaust.rs` |
| Codec | old encodings decode the same; a state with either counter nonzero round-trips (checked on an official state with the counters set, as C1 did) | `codec.rs`, new tests |
| Chance / search / exact solver | outcome lists sum to 1; a draw from a trigger is the existing `Draw` event | existing chance tests, new tests |
| Solver bounds | no new effect heals | `Effect::heals` (no catch-all arm) |
| Net features (`py/src/features.rs`) | a net's stored layout gathers the same columns; the new trigger and the card `exhausted` rows are columns of the full layout only | features tests; the product net's `layout_names` unchanged |
| Heuristic | estimates on existing content unchanged | `series_check` |
| Pack writer | the new hook trigger and card field written and read back equal | round-trip of the 6 entries |
| Slot limits | Dark Embrace and Feel No Pain are pack powers: a fight still holds at most 8 pack cards and 8 pack powers | `registry.rs` (unchanged) |
| Speed | `series_speed` at most +10% | `scripts/series_speed.py` |

**When in doubt:** prefer the game's behaviour as sts_lightspeed codes it
over a neater engine rule, except where `decision/parity-source` says the
wiki decides.

## Scope

May change: `engine/src` (hooks, state, registry parse and write, codec,
features of hooks), `py/src` (features), `engine/tests`,
`content/packs/act1-ironclad.json`, `docs/research/act1-inventory.md`,
this spec. New JSON names as above; the codec gains a tag for the
counters without changing old ones.

Off limits: official content files and anything that changes golden;
`Action` and the decision interface; the generator; the heuristic's
values; training, gauntlet and run-layer scripts.

## Decisions taken

- (on the owner's behalf) The hooks fire after the card is placed, once
  with the count, not per card as each exhaust happens: the game's queue
  order, and it never pauses inside `ExhaustHand`. Alternative: fire
  inline per card (simpler, but a draw could pause in the middle of an
  effect and would come before the card's own later effects, unlike the
  game).
- (on the owner's behalf) A turn-end draw from a trigger is owed to the
  next turn's draw, not drawn before the monsters act. Alternative: a new
  stage between the player's turn end and the monsters' moves where the
  draw can pause (faithful, but changes the turn's stage sequence for a
  difference that shows only when the draw pile runs out).
- (on the owner's behalf) Card `exhausted` effects are limited to
  `GainEnergy` and `Block`. Alternative: the full hook vocabulary (needs
  pausing and combat-end handling inside `ExhaustHand`; no content needs
  it).

## Outside assumptions

- The cards' costs, numbers and types as in the table: checked against
  the wiki's Ironclad card list and sts_lightspeed (`Cards.h`,
  `BattleContext.cpp`) in build step 1; a difference follows
  `decision/parity-source` and goes into the inventory.
- sts_lightspeed queues Dark Embrace's draw and Feel No Pain's block at
  the bottom of the action queue and Sentinel's energy at the top; Feel
  No Pain's block is raw. Checked in step 1; if its turn-end order
  differs from the above (for example the drawn cards are discarded), the
  build follows it where that needs no pause and writes the difference
  into the inventory.

## Verification

Tests first (`engine/tests/exhaust_triggers.rs`, packs from
`act1-ironclad.json`):
- `feel_no_pain_blocks_per_exhaust`: with Feel No Pain played (3), Burning
  Pact choosing Bash gives 3 block (Dexterity 2: still 3); Fiend Fire with
  4 cards in hand gives 15 (4 + itself); Feel No Pain+ gives 4 per card;
  two Feel No Pains stack.
- `dark_embrace_draws_after_the_card`: Dark Embrace held; Burning Pact
  choosing Strike ends with 2 + 1 cards drawn; with draw and discard
  empty, True Grit+ choosing Defend draws True Grit+ back from the
  discard; with a full hand nothing more is drawn.
- `fiend_fire_count_unchanged`: Dark Embrace and Fiend Fire with 4 other
  cards: 4 hits, then 5 cards drawn.
- `ethereal_at_turn_end`: Feel No Pain and Dark Embrace held, Dazed in
  hand at end of turn: 3 block before the monster's attack; the next
  turn's draw is 6.
- `sentinel_energy_on_exhaust`: Burning Pact choosing Sentinel gives 2
  energy (Sentinel+ 3); playing Sentinel gives 5 block and no energy;
  Fiend Fire with 2 Sentinels in hand gives 4 energy.
- Load refusals: a `CardExhausted` hook with a condition other than
  `Always`, or with `ExhaustHand` or a pick, is refused; a card
  `exhausted` holding `Damage` is refused; each with a message.
- Codec, equality and hashing with either counter nonzero; existing
  encodings unchanged.
- A mutation check: firing before the card is placed, and per-stack
  scaling dropped, each fail a test.

End to end: a greedy player with the starter deck plus Dark Embrace, Feel
No Pain, Sentinel, Burning Pact, True Grit and Second Wind (6 pack cards)
beats a Jaw Worm in 40 of 40 seeds, and the triggers fired in most of
them (a count over the games). Built: 40 of 40 won; a trigger power was held at an
exhaust in 15 of 40, which is every game where greedy played one (the
heuristic gives the powers no value, so it plays them only when nothing
scores higher); the test's bar is 12.

Don't guard: run-layer card rewards and upgrades for pack cards (the
inventory's "Left for later"); exhaust relics; encodings from builds
before this one beyond what `codec.rs` already checks.

## Build steps

1. Write the tests above and the six pack entries; check every number and
   the queue order against the wiki and sts_lightspeed and write the
   result into the inventory. Check: the tests compile against stubs and
   fail only on the missing behaviour; existing suites pass.
2. Engine: `Trigger::CardExhausted` (parse, write, load refusals), the
   unfired counter in `exhaust_card`, firing after the card is placed and
   after turn-start hooks, equality and codec tag. Check: the Feel No
   Pain, Dark Embrace and Fiend Fire tests and the codec tests pass;
   golden identical.
3. Turn end (firing after the hand's placement, the owed draw) and the
   card `exhausted` field (parse, write, refusals). Check: the ethereal
   and Sentinel tests and the refusals pass; official files round-trip.
4. `py/src` features: the trigger column and the card `exhausted` rows
   (full layout only). Check: features tests pass; the product net's
   `layout_names` unchanged; a gauntlet sanity run of the product on 20
   headline sequences (queued, about 20-35 min each, old and new build)
   is identical per sequence.
5. End to end and series checks: the greedy check; `series_check` PASS,
   `series_speed` at most +10%; inventory counts updated (blocked
   18 -> 15). Check: all pass and recorded in the inventory.

Build plan: 5 steps, one build subagent in the lane worktree (steps 1-3
share one engine context), on Opus. No stop points: every decision above
is reversible.
