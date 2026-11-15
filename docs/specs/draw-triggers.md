# Draw triggers (building block C3)

Status: closed (2026-11-09, built and in use; 51e84f7a, checkpoint c3-built passed; docs/research/act1-inventory.md "Block C3 as built"; decisions "Draw triggers: once per Status card").

Follows C2 (`docs/specs/exhaust-triggers.md`), whose shape it copies.

## Outcome

A power can react when its owner draws a Status card. Evolve and Fire
Breathing (4 entries with upgrades) then load from
`content/packs/act1-ironclad.json` and play as in the game.

**How it moves the goals.** Goal 1 asks for first-class custom content:
"whenever you draw a card of type X" is one of the game's trigger words
(Evolve, Fire Breathing, and later Curse and other-character cards), and
without it a designer can't turn Status cards from a cost into a payoff.
Goal 2 needs the real Act 1 card pool: these two are Ironclad's Status
payoffs (Wild Strike, Reckless Charge, Power Through, Sentries' Dazed).
We'll know by the lane's measure: blocked Ironclad cards drop from 13 to
11, each entry is checked against the wiki and sts_lightspeed in a test,
and the series checks hold (golden identical, `series_check` PASS,
`series_speed` at most +10%).

**Non-goals.** No change to official content, golden or the rules
version. No Draw (Battle Trance, block C9). The generator's vocabulary is
unchanged. No retraining, no headline read. The heuristic gives the new
trigger no value.

## Behavior

New pack vocabulary: a power hook `{"trigger": "CardDrawn", "condition":
{"CardType": "Status"}, "effects": [...]}` fires once for each Status card
its owner draws, by any draw (the turn's draw, a card's or a hook's
`Draw`, a draw owed by Dark Embrace). Cards put into the hand without a
draw (Power Through's Wounds, `AddCard` to hand) don't count, as in the
game. Amounts are per stack, as for every hook. Load refuses, with a
message: a `CardDrawn` hook whose condition is not `CardType Status` or
`CardType Curse` (only those draws are counted; a wider condition is a
later extension), and effects that pause other than `Draw` (picks, random hits, random
exhaust) or exhaust (`ExhaustHand`).

The four entries (numbers from sts_lightspeed `usePowerCard` and the
wiki, read 2026-11-09; both agree):

| Card | Cost | Type | Entry |
|---|---|---|---|
| Evolve | 1 / 1 | Power, Uncommon | Apply `Evolve` 1 / 2; hook `CardDrawn` Status: Draw 1 |
| Fire Breathing | 1 / 1 | Power, Uncommon | Apply `FireBreathing` 6 / 10; hooks `CardDrawn` Status and `CardDrawn` Curse: PlainDamage 1 to AllOpponents |

**Curse draws (added 2026-11-15, live run 72).** The game's
`FireBreathingPower.onCardDraw` fires on a Status or a Curse draw
(`EvolvePower` on Status only), and every A10+ deck holds Ascender's Bane.
A `CardDrawn` hook may name `CardType Curse`; a hook on both types is two
hooks, one per type (Fire Breathing's row). A second counter holds the
Curse cards drawn whose hooks haven't fired; it counts only while the
player holds a hook on Curse draws, fires after the draw's Status cards
the same way, is cleared with the combat, and is written by its own codec
tag (19) only when nonzero. Known difference: within one draw, Status
hooks fire before Curse hooks, where the game fires per card in draw
order; it matters only when an extra draw (Evolve) and a lethal Fire
Breathing hit share a batch. Rules version moved; cover game
`fire-breathing-curse` in golden.

Fire Breathing's damage is the game's `DamageAllEnemy` (THORNS type):
Strength, Weak and Vulnerable don't apply, block absorbs it, which is the
engine's `PlainDamage`. Build step 1 checks the damage type in
sts_lightspeed's `DamageAllEnemy`; a difference follows
`decision/parity-source` and goes into the inventory.

**When the hooks fire (the game's order).** sts_lightspeed's
`CardManager::draw` queues one reaction per Status card drawn at the
bottom of the action queue (`addToBot`), so the reactions run after the
whole draw and after the card in play. So:
- A counter holds the Status cards drawn whose hooks haven't fired. It
  counts only while the player holds a power with a `CardDrawn` hook, so
  official content never touches it (golden and every encoding stay the
  same).
- When the stage machine reaches the player's turn with the counter
  nonzero (after the card in play is placed and its exhaust triggers have
  fired, after the turn-start draw and hooks, after a paused draw
  resolves), the player's `CardDrawn` hooks fire once, unscaled, and the
  counter drops by one; this repeats until it is zero. One firing per
  card, as in the game: Fire Breathing hits once per Status (each hit is
  seen by per-hit hooks such as Angry), and Evolve's draws come one at a
  time, each of which may draw another Status and count again (the
  game's chain).
- A `Draw` inside a firing may pause as the existing `Draw` chance event;
  when it resolves, the remaining count fires on.
- Several `CardDrawn` powers fire in the order the player's powers hold
  them, all once per card.
- If a firing ends the combat (Fire Breathing kills the last enemy), the
  counter is cleared with the combat, as C2's counters are.

**State.** One counter, part of state equality and hashing; the codec
writes it only when nonzero (a new tag), so every existing encoding is
unchanged. A finished combat holds zero. Monsters never draw: a monster
holding a `CardDrawn` power never fires it.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Official content, rules version | golden identical; official files round-trip byte for byte | `golden.rs`, `official_files.rs` |
| C2's exhaust triggers | same results with no `CardDrawn` power held; Dark Embrace's draws count as draws | `exhaust_triggers.rs`, a new test |
| Codec | old encodings decode the same; a state with the counter nonzero round-trips | `codec.rs`, a new test |
| Chance / search / exact solver | outcome lists sum to 1; a draw from a firing is the existing `Draw` event; no decision point is offered with the counter nonzero | existing chance tests, a new test |
| Solver bounds | no new effect heals | `Effect::heals` |
| Net features (`py/src/features.rs`) | a net's stored layout gathers the same columns; the new trigger is a column of the full layout only | features tests; the product net's `layout_names` unchanged |
| Heuristic | estimates on existing content unchanged | `series_check` |
| Pack writer | the new trigger written and read back equal | round-trip of the 4 entries |
| Wording | `CardDrawn` named in `registry::element_names()` and `content/wording.json` | `engine/tests/wording.rs` |
| Speed | `series_speed` at most +10% | `scripts/series_speed.py` |

**When in doubt:** prefer the game's behaviour as sts_lightspeed codes it
over a neater engine rule, except where `decision/parity-source` says the
wiki decides.

## Scope

May change: `engine/src` (hooks, state, chance's draw bookkeeping,
registry parse, write and refusals, codec), `py/src` (features),
`engine/tests`, `content/packs/act1-ironclad.json`,
`content/wording.json`, `docs/research/act1-inventory.md`, this spec.
New JSON name `CardDrawn`; the codec gains a tag for the counter without
changing old ones.

Off limits: official content files and anything that changes golden;
`Action` and the decision interface; the generator; the heuristic's
values; training, gauntlet and run-layer scripts.

## Decisions taken

- (on the owner's behalf) Fire once per Status card, unscaled, not once
  with the count as C2 does: Fire Breathing's hits are per card in the
  game and per-hit hooks (Angry) see the difference; the cost is more
  small draw events for Evolve. Alternative: C2's scaled firing (fewer
  chance events, wrong hit count against per-hit hooks).
- (on the owner's behalf) Only Status draws are counted, and only while
  a `CardDrawn` power is held. Alternative: count every draw by type
  (general "whenever you draw an Attack", but a counter on every draw
  changes official states and their encodings; added when content needs
  it).
- (on the owner's behalf) Firing happens where the stage machine reaches
  the player's turn. Alternative: a firing point after each draw inside
  a card (closer to nothing in the game: the game also waits for the
  card).

## Outside assumptions

- Numbers and trigger rules as in the table and the firing rules above,
  read from sts_lightspeed `BattleContext.cpp` (`usePowerCard`,
  `drawCards`) and `CardManager.cpp` (`draw`) and the wiki.gg pages on
  2026-11-09 (the fandom wiki returned HTTP 402).
- `DamageAllEnemy` is unmodified (THORNS-type) damage that block
  absorbs: checked in step 1.

## Verification

Tests first (`engine/tests/draw_triggers.rs`, packs from
`act1-ironclad.json`):
- `evolve_draws_per_status`: Evolve held, the turn's draw takes 2 Dazed
  and 3 others from a known pile: 2 more cards drawn after the draw;
  Evolve+ draws 2 per Dazed; with a full hand nothing more is drawn.
- `evolve_chains`: a draw pile of only Dazed and one Strike with Evolve
  held keeps drawing until the Strike or the hand limit.
- `fire_breathing_hits_per_status`: Fire Breathing held, 2 Wounds drawn:
  two hits of 6 on every enemy (Fire Breathing+ 10), absorbed by block,
  unchanged by Strength and Vulnerable; killing the last enemy ends the
  combat with the counter at 0.
- `no_trigger_without_draw`: Power Through's Wounds into hand fire
  nothing; drawing non-Status cards fires nothing.
- `drawn_by_a_card_fires_after_it`: Pommel Strike drawing a Dazed with
  Fire Breathing held: the hit lands after Pommel Strike is discarded.
- Load refusals: a `CardDrawn` hook with condition `Always` or another
  type, or with a pick, is refused, each with a message.
- Codec, equality and hashing with the counter nonzero; existing
  encodings unchanged.
- A mutation check: firing once with the count (scaled) fails
  `fire_breathing_hits_per_status` against a per-hit hook, and counting
  without a held power changes golden.

End to end: a greedy player with the starter deck plus Evolve, Fire
Breathing, Wild Strike, Reckless Charge and Power Through beats Three
Sentries (Dazed) in most of 40 seeds, and a `CardDrawn` hook fired in
most games where a trigger power was played (a count over the games).

Don't guard: Curse cards; No Draw; run-layer rewards and upgrades for
pack cards; encodings from builds before this one beyond what `codec.rs`
already checks.

## Build steps

1. Write the tests above and the four pack entries; check the damage
   type in sts_lightspeed and write the source check into the inventory.
   Check: the tests compile against stubs and fail only on the missing
   behaviour; existing suites pass.
2. Engine: `Trigger::CardDrawn` (parse, write, refusals, wording), the
   counter in the draw bookkeeping (only with a held hook), firing at the
   player's turn one card at a time, equality, hashing, codec tag,
   clearing at the combat's end. Check: the draw-trigger tests and codec
   tests pass; golden identical; engine suites pass.
3. `py/src` features: the trigger column (full layout only), re-pins as
   C2 did. Check: features tests pass; the product net's `layout_names`
   unchanged.
4. End to end and series checks: the greedy check; `series_check` PASS;
   `series_speed` at most +10%; a sanity pair of the product on 20
   headline sequences (queued, old and new build) identical per
   sequence; inventory counts (blocked 13 -> 11). Check: all pass and are
   recorded in the inventory.

Build plan: 4 steps, one fork in the lane worktree, on Opus. No stop
points: every decision above is reversible.
