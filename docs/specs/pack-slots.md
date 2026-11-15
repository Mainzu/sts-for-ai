# More pack cards and powers per fight (building block S1)

Status: closed (2026-11-07, built and in use; amended to 40 card slots 2026-11-13, be76e88e; decisions "act1-content: next block S1").

## Outcome

Amended 2026-11-13: 40 card slots (docs/specs/act1-singles.md section 5,
Entropic Brew's pool); slots 0-31 keep the ids below.

A fight can hold up to 32 distinct pack cards and 24 pack powers (today 8
and 8, `engine/src/registry.rs` `SLOTS`), so a deck made of pack content
(a full Act 1 Ironclad deck using the 25 written pack cards, later a
character made of data) binds and plays in one fight.

**How it moves the goals.** Goal 1 asks for first-class custom content: a
new character is a card pool of 75 cards, and its decks hold 10 to 30
distinct cards; with 8 slots no deck made of data can be played at all, so
the custom-content half of goal 1 can't be measured. It is also the first
of the review's steps between today's packs and a character made of data,
and it unblocks the next ones (pack content in `gauntlet.py`'s decks and
offers needs decks with more than 8 pack cards). Goal 2 needs the real Act
1 pool in fights: of the 75 Ironclad cards 25 are pack entries, and an
Ironclad deck mixing them can't bind today. We'll know: a test binds and
plays a deck of 32 distinct pack entries (every C1, C2 and step-3 card
with the starter deck) to an end with greedy play, the binding error moves
from 9 to 33 cards and 25 powers, and the series checks hold (golden
identical, `series_check` PASS, `series_speed` at most +10%).

**Non-goals.** No change to official content, golden, the rules version or
any official encoding. No upgrade links (a separate block), no
`gauntlet.py` flags, no burst vocabulary widening. Per-copy variants stay
at 4. No retraining or headline read: nothing official changes.

## Behavior

- `SLOTS` splits into `CARD_SLOTS = 32` and `POWER_SLOTS = 24`.
  `Power::GEN` grows from 8 to 24 generated powers (`Gen0`..`Gen23`), so
  `NUM_POWERS` = 30 + 24 = 54 (the held mask holds 64; 10 left for new
  official powers).
- **Card ids stay where they are.** Slots 0-7 keep ids 128-143 (a pair per
  slot: base, then the unused `+` id), the 4 variants keep ids 144-147
  (`VARIANT_BASE` unchanged, so the codec's variant bytes and every stored
  state holding a variant read the same); slots 8-31 take ids 148-195.
  `NUM_CARDS` = 196 (card ids are a byte). One pair of helpers maps slot to
  id and back; every site that does the arithmetic uses them.
- Binding more than 32 pack cards, or more than 24 pack powers (deck and
  monsters together), is the same error as today with the new numbers.
- Everything else is as today: a slot holds one pack entry ("X" and "X+"
  are two entries), slots fill from 0, a pack power the deck already holds
  shares its slot.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Golden and the rules version | identical | `engine/tests` golden test |
| Codec (states with variants, official states) | bytes unchanged | codec tests; a new test: a variant-holding state encodes to the same bytes as on main (pinned bytes) |
| Features (full layout, product net's stored layout) | official states encode the same; the product net gathers the same names | `series_check` (heuristic and product bit-identical) and the contract pins |
| Debug text of states | generated power slots shown only when used | golden |
| Existing pack tests (registry, packs, monster_powers, exhaust triggers, act1 cards, Python content pack) | pass; the "nine cards must not bind" tests become 33 cards / 25 powers | updated in step 2 |
| Search speed | at most +10% slower | `series_speed` |

## When in doubt

Prefer stable ids and encodings over tidy numbering.

## Scope

May change: `engine/src/registry.rs`, `powers.rs`, `cards.rs`, `state.rs`,
`codec.rs` (only where they compute slot ids or size arrays), the engine and
Python tests named above, `py/src` only for a constant or an error message,
the inventory doc, `docs/decisions.md`. Off limits: official content files,
golden, the features layout, the net, `scripts/` except tests.

## Decisions taken

- 32 card slots and 24 power slots (alternatives: 16/16, which a full
  Ironclad Act 1 deck mixing written entries can outgrow; 61/34, the most
  the byte ids and the 64-bit mask allow, which leaves no room for new
  official powers and widens every state's binding most). The numbers are
  constants; raising them later is a one-line change plus this spec's
  checks.
- Ids of slots 0-7 and the variants kept (alternative: renumber so the
  variants follow all slots, which changes the codec's bytes for every
  stored state with a variant).
- The binding stays in the state by value (it grows from 40 to 120
  bytes). If `series_speed` reads more than the +10% bar, step 4 moves the
  card and power slots behind an interned reference (the variants, which
  change mid-fight, stay by value) and measures again.

## Outside assumptions

None beyond the engine: no game numbers change.

## Verification

Tests first (step 1, pass on main):
- `variant_state_bytes_are_pinned`: a Strike variant held in a combat
  encodes to a pinned byte string.
Then (step 2):
- `binds_thirty_two_pack_cards`: a deck of 32 distinct pack entries from
  `act1-ironclad.json` binds; 33 fails with "more than 32 generated cards".
- `binds_twenty_four_pack_powers`: 24 distinct pack powers bind (a pack
  written in the test), 25 fail; deck and monster powers together count.
- `slot_ids_round_trip`: every slot's id maps back to its slot; ids
  144-147 are variants, never slots.
- End to end: `greedy_plays_decks_of_them_to_an_end` plays one deck of 32
  entries plus the starter deck to an end on 10 seeds (today it splits the
  entries into decks of 8).
- Series checks at landing: golden identical, `series_check` PASS,
  `series_speed` at most +10%.

## Don't guard

Decks of more than 32 pack cards (an error, as today), pack powers on a
`Power` beyond `Gen23`.

## Build steps

1. Pinned variant-bytes test; passes on main.
2. Split `SLOTS`, grow `Power::GEN` to 24, add the slot/id helpers, move
   every slot-id site to them; update the limit tests and the act1 test.
   Check: engine suites (all but solve) pass, golden identical.
3. Build the wheel; Python suites touching packs, features and nets pass;
   `series_check` PASS against main. Check: those outputs.
4. `series_speed` main against the build (interleaved). Check: at most
   +10%; if over, intern the slot arrays (Decisions) and re-measure.

Build plan: 4 steps, in-session, on Opus. No stop points expected.
