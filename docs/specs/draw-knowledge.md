# Draw knowledge: exact rules for the draw pile, and what the net is told

Status: building (2026-11-15, items 1-4 built: random-spot inserts go under the top card; `CombatState::next_draw` gives the next turn's start draw as (min, max); the net reads `next_draw_size` (the min), `next_draw_max`, and each known card's `draw_position` and each floater's `draw_above`; past the node cap a pick follows its first option. Items 5, 6 confirmed by the owner, not built yet; 6a dropped after its probe, 6b needs its own spec).

## Outcome

Every rule about where a card lands in the draw pile, how many cards the
next turn draws, and how many picks a search explores is exact for any
content, not only for today's cards. The net reads the known part of the
draw pile by position, and the next turn's draw from one engine function,
with a range where the turn hasn't decided it yet.

The project's first goal is generalization: a gap that only today's
content avoids is a bug now. Each item below is one such gap.

## 1. A card put at a random spot is never on top (rules fix)

The game: `MakeTempCardInDrawPileAction(card, n, randomSpot = true, ...)`
(Wild Strike's Wound, Reckless Charge's Dazed, Chrysalis, Metamorphosis)
goes through `CardGroup.addToRandomSpot`: an empty pile takes the card;
otherwise it is inserted at index `cardRandomRng.random(size - 1)`, so
uniformly among the slots under the current top card, never on top. (The
top is the list's last element.)

The engine today: with nothing known on top, the card becomes a plain
member of the pile and can be the next draw with probability 1/(n+1)
(`Top::add_floater` returns at once). With a known top, `add_floater`
places it with nothing certainly above it; only colorless step 3's
`add_floater_under` puts it under the top card.

The fix: a floater's `above` counts cards certainly above it, known or
not. "Under the top card" is a floater with `above` 1 whatever is known;
a draw takes it only once `above` reaches 0, and the existing rule (each
draw lowers every positive `above` by 1; otherwise uniform over the rest)
keeps the game's odds exactly. Every random-spot insert uses it.

**Cost:** Wild Strike and Reckless Charge are official cards in the deck
pools and the golden games, so `engine/tests/data/golden.txt` changes and
with it the rules version (kb `context/rules-version`): datasets, the
solved DB and recorded games from the old version stop replaying. That is
the owner's decision (below).

**As built (2026-11-14).** The spec's draw rule above (each draw lowers
every positive `above`; a floater with `above` 0 is next with chance
copies / pile size) is not exact once random-spot inserts and cards put
on top interleave: a randomized check against an exact enumeration of the
game's pile found two cases. So `Top` (`engine/src/state.rs`) keeps its
floaters oldest first, and:
- `above` counts the cards certainly above a floater once the floaters
  put in after it are left out. Drawing a card that is no floater lowers
  every positive `above`; drawing a floater lowers only those of the
  floaters put in after it (a Wound under an unknown top, then Headbutt's
  Bash, then a Wound under Bash: drawing the newer Wound leaves the older
  ones' unknown card above them).
- The next card (`CombatState::top_cards`, `engine/src/chance.rs`): from
  the newest floater to the oldest, one with `above` 0 is on top, when no
  newer one is, with chance copies / (pile size less every floater put in
  after it); the known head, or with only floaters known an even spread
  over the cards that are no floater, takes the rest. (An insert under
  the top never changes the top, so later inserts don't dilute an older
  floater's chance.)
- Neighbouring floaters with equal `above` are sorted by card and merged
  (their order can't matter), so equal knowledge is equal state. The
  codec writes them oldest first (section 1, the known count may be 0);
  states without floaters encode as before.

Sources, each checked in the jar: Wild Strike, Reckless Charge and Mark of
Pain (`MakeTempCardInDrawPileAction(card, n, randomSpot true, ...)`, so
`ShowCardAndAddToDrawPileEffect` calls `addToRandomSpot`), Chrysalis and
Metamorphosis (`MakeRandom` to the draw pile). `Effect::AddCard` to the
draw pile has no other source, so it always goes to a random spot.
Tests: one per source (`known_top.rs`, `act1_cards.rs`, `act1_relics.rs`,
`colorless.rs`) compares every next hand's odds with an enumeration of
`addToRandomSpot` (`tests/common` `game_draw_odds`), and
`known_top.rs` `random_sequences_keep_the_games_odds` does so after 400
random sequences of inserts, cards put on top and draws. Golden was
re-recorded once with only this change (139 of the 9,000 games and 352 proving
games moved): rules version `e47bcfcdb6b2777a`, no `SAME_RULES` entry.

Known limit: when the drawn card's kind is both a floater and a plain
card of the pile, the engine's outcomes still tell them apart (the
search knows which copy it drew; the odds of what follows are right on
average, but a decision could use the difference).

## 2. The next turn's draw, from one engine function

`CombatState::next_draw(&self) -> (min, max)`, the number of cards the
next turn's start draws:
- the base draw, the relics' `draw_per_turn`, the first turn's extra;
- every turn-start draw hook the player holds (relics and powers, before
  and after the draw), with its condition evaluated on the state, times
  stacks; Bag of Preparation's combat-start draw before the first turn;
- capped by the hand limit: 10 less the cards that will stay in hand
  (Retain, Runic Pyramid, a turn-end keep choice);
- `min` and `max` differ only where the turn hasn't decided: an open
  end-of-turn keep choice (Well-Laid Plans: `min` assumes the most kept,
  `max` the fewest) or a draw hook whose condition can still change this
  turn (Pocketwatch: its relic counter counts the cards played since the
  last post-draw, as the game's does, and its draw needs `CounterAtMost 3`
  and `NotFirstTurn`; plays only raise the counter, so while it is at most
  3 `min` leaves the 3 cards out and `max` counts them, and past 3 both
  leave them out). At an End Turn leaf they are equal.

The encoder's `next_draw_size` and every other reader use it; the
hand-written count in `py/src/features.rs` goes. Series-review fix A2 (the
hand-limit cap) is part of this item.

**As built (2026-11-15).** `engine/src/next_draw.rs`, by the build plan
`docs/research/build-plans-2026-11-14/draw-next-and-inputs.md` (it folds in
series-review fix A2: retained cards take the next hand's space). Tests:
`engine/tests/next_draw.rs`.

## 3. What the net reads of the known draw pile

- Each known card in the draw pile gets its position (1 = next card
  drawn) as a row input, so the order is readable: Headbutt's Rampage on
  top, Warcry's card, Frozen Eye's whole pile.
- The player inputs `next_draw_min` and `next_draw_max` replace
  `next_draw_size`.
- The `next_draw` and `known_later` piles stay (nets trained on them keep
  their meaning), split at `next_draw_min`.
- Floaters keep their encoding in the unknown draw pile, with their
  `above` as an input.
- Additive only: a net without the new inputs reads 0 for them.

**As built (2026-11-15).** `next_draw_size` keeps its name and place and
holds the min (older nets read it); `next_draw_max` follows `known_top`;
`draw_position` and `draw_above` are the card path's last columns. A layout
without them gets the merged entries, so older nets' batches are
byte-identical. Tests: `py/tests/test_sts.py` (`test_draw_positions`,
`test_next_draw_size_counts_retained_cards`).

## 4. Picks stay within the node cap (series-review fix D1)

As `docs/specs/series-review-fixes/D-loader.md` step 1 specifies: past the
node cap a paused pick expands its first option only, so an ordered pick
(DiscardToTop, HandToTop) can't run the search out of memory.

## 5. Readers that re-derive damage

The heuristic and the agents' incoming-damage estimates hand-compute
Vulnerable as x1.5 (`heuristic.rs`, `agent::incoming_damage`), so Paper
Phrog and Odd Mushroom (blocked-relics step 2) and any pack static on
damage taken are missed. They read the engine's attack-damage path, as
`move_attacks` did for monster damage (audit entry 5).

## 6. Any-number picks in search (Purity)

Design review: `docs/research/purity-search-designs-2026-11-13.md` (four
designs, three judges). Measured problem: kb `measurement/purity-search-cost`.

What the review found: pick sub-multisets already merge in the search's
memo. It also said the rest of the turn is searched again after each of
the pick card's 617 play points; that is wrong: the memo merges those
continuations too (Purity then Strike and Strike then Purity end on one
node), so the search's nodes are distinct states. And the turn's 34,867
distinct end states are real under afterstate equality, so no exact
design brings this turn under the 50,000-node cap. Two layers were
planned; 6a is dropped:

**6a. Play-last reduction (exact). Dropped (2026-11-14).** The memo
already merges the reordered lines, so 6a can only skip edges (applies
that would find an existing node), not nodes. The probe
`engine/tests/play_last_probe.rs` measured it on the hand below: the walk
with the rule reaches the same 74,092 states as the walk without it, its
(state, obligation) keys rise to 102,704, and its `apply_action` calls
rise from 249,179 to 562,820 (the check costs more than the edges it
skips). Plan and numbers:
`docs/research/build-plans-2026-11-14/purity-play-last.md`. The design as
written was: after the search plays a pick card P
(not at the root, so every root option keeps its exact value), the next
plain decision considers only End Turn and the actions that don't commute
with P. Commutation is checked by the engine, not a hand-kept table: an
action `a` is skipped when `a` was legal before P, and applying `a` before
P then replaying P's recorded picks gives exactly the state of applying
`a` after P, and P's resolution opened no chance event. The memo keys on
the state plus the pending obligation; end-of-turn states still merge by
afterstate. Sound for any content (a non-commuting action is kept, so
Sentinel, Feel No Pain, counters and ordered picks only weaken it).
That estimate (2.5-3x fewer nodes) was wrong for the reason above.

**6b. Pick ration (approximate; the step that addresses the cap, needs its own spec).** A pick
with more than 12 outcomes enumerates its outcomes off the tree, ranks
them with one function (`rank_exits(state, exits)`, the heuristic first;
a learned pick prior can replace it later without restructuring), and
keeps the best k plus "take nothing"; the others are dropped, never
scored as leaves. Picks with 12 or fewer outcomes take today's path, so
golden doesn't move.

**Measurement:** the Purity probe (nodes, cuts) with 6b; and
the regret of the chosen action against an uncapped exact search on a
set of pick-heavy turns. 6b is kept only if its regret is within noise.

## Owner decision (2026-11-13)

- **Item 1 is fixed now, changing the rules version.** Golden is
  re-recorded once, with only item 1's change in it; `registry.SAME_RULES`
  gets no entry (it is a rule change). Datasets, the solved DB and runs
  from the old version stop replaying: the next training generates new
  data. The headline control (kb `yardstick/headline-control`) and the
  one-turn controls (`yardstick/one-turn-controls`) are re-recorded under
  the new rules as queued jobs, and the kb facts point at the new files.

## Verification

- Item 1: a test per random-spot source (Wild Strike, Reckless Charge,
  Chrysalis) that the next draw is never the added card when the pile
  held one or more cards, and that the odds below match `addToRandomSpot`.
- Item 2: tests for each draw source, the hand cap with Retain and Runic
  Pyramid, and the range with an open choice.
- Item 3: encoder tests that positions match the known order; old nets
  load unchanged.
- Item 4: D-loader.md's reproduction stays within the cap's overshoot.
- Item 5: Phrog and Mushroom incoming damage equals the engine's.
