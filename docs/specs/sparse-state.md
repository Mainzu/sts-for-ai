# Sparse state: piles and powers as short sorted lists (runtime registry stage 5)

Status: closed (2026-11-06, built and in use; decisions "Sparse state built and landed: search +17.6%"); its pile layout was replaced by docs/specs/sparse-piles.md (2026-11-13).

Confirmed under the mandate (lane worker of `lane/runtime-registry`,
2026-11-06); decisions "Runtime registry stage 5 spec: sparse piles and
powers, sized from a census (on the owner's behalf, 2026-11-06)". Stage 5
of `docs/specs/runtime-registry.md`.

## Why (goals)

Goal 1 wants open-ended content: generated cards and powers, Act 1's
full card set, a second character. Today every card id costs the state 4
bytes (a count in each of 4 piles) and every power 12 bytes (an amount in
each of 6 creatures), whether a fight uses it or not; the state is 1,292
bytes, and Act 1's cards alone would add about 100 ids (+400 bytes).
Goal 2 runs on search, and about three quarters of a two-turn search
copies, hashes and compares whole states. Padding the piles by 576
bytes measured the price of size: one-turn search 1 thread -17.5% games/s,
16 threads -20.2%, two-turn median +13% time (below). A state sized by
what a fight holds instead of what content exists makes adding content
free for search speed and, by the same slope, makes today's search
faster. We'll know by `series_speed.py` (search games/s up, see
Verification) with golden games, codec encodings and H4 identical.

## Speed case (measured 2026-11-06, `two_turn_phases --census`)

Census over 1,040,766 states two-turn searches stored (100 roots from
elite and boss play, starter + 5 decks):

| per state | mean | p99 | max |
|---|---|---|---|
| distinct card ids in hand / draw / discard / exhaust | 1.5 / 3.4 / 5.4 / 0.9 | 4 / 7 / 9 / 2 | 6 / 8 / 9 / 2 |
| non-zero player powers | 2.4 | 5 | 6 |
| non-zero powers per monster in use | 0.2 | 1 | 4 |
| non-zero powers, all creatures | 3.1 | 6 | 8 |

Bytes today: 4 piles 608 (148 card ids, padded to 152), 6 power blocks
504 (38 powers x 2 + 8), the rest 180. Headline decks
(`yardstick/headline-control`'s file) hold at most 13 distinct card ids
after 11 floors; a full three-act deck may reach about 35.

Size slope (base vs piles padded +144 slots each, 1,292 -> 1,868 bytes,
same trees, `target/ss-*` in the lane worktree): `series_speed.py` 7
interleaved runs: clone 37.7 -> 69.9 ns, random combats -6.0%, search 1
thread -17.5%, 16 threads -20.2%; `two_turn_phases 100` real search,
4 interleaved pairs: time ratios 1.00, 1.13, 1.13, 1.90 (a loaded machine:
a gauntlet job ran throughout).

Expected: the layout below is about 850 bytes (piles 4 x 81, power
blocks 6 x about 58; -440, -34%). On the slope, one-turn search about
+15-20% games/s and two-turn about -10% time,
minus what the list lookups cost over direct indexing (unmeasured until
built; the build's speed check decides).

## Outcome

`Pile` and `Powers` keep their methods and meaning, but hold only the
entries in use, sorted by id, in fixed-capacity inline arrays, so the
state's size no longer grows with the number of cards and powers that
exist. Non-goals: `CardId` stays `u8` (widening it is its own change when
content passes 256 ids); the registry stays one per process
(`decision/registry-first`); no change to the codec's format, the
features, the nets or Python's API.

## Behavior

- **Pile:** up to `CAP` entries of (card id, count), sorted by id, count
  > 0, unused entries all zero, plus a length. `add` inserts in order or
  adds to the entry; `remove` subtracts and deletes the entry at 0 (the
  entries after it shift down, the freed one zeroed). `count`, `iter`
  (id order, as today), `nth`, `len`, `is_empty`, `add_pile`,
  `remove_pile`, `clear`, `from_cards` keep their results. One capacity
  for all four piles, `PILE_CAP = 40` (a whole three-act deck's distinct
  ids fit in one pile; the hand's limit of 10 cards needs no smaller
  type). Adding a 41st distinct id panics with the pile, the card and the
  capacity named: a state that big is a bug or new content to size for.
- **Powers:** up to `POWER_CAP` entries of (power, amount), sorted by
  power, amount != 0, unused entries zero, a length, and the
  `just_applied` bits kept per power as today (`[u32; 2]`). `get` scans;
  `add` inserts or adds, and an amount reaching 0 deletes the entry (as
  today's amount 0 means "absent"; `clear` likewise). `POWER_CAP = 12`
  for every creature (max seen 6 on the player, 4 on a monster). Overflow
  panics like a pile's.
- **Equality and hashing** stay derived over the whole struct: the
  zeroed unused entries make equal contents equal bytes.
- **Debug text** prints the dense form it prints today (counts per id up
  to the official ids, all ids when a reserved one is used; amounts per
  power likewise), so the codec golden file and every debug dump read
  the same.
- **Codec:** reads and writes through `Powers`' methods (today it takes
  `amounts` and `from_parts` an array); its bytes don't change.
- Hash values change, so a `HashMap<CombatState, _>`'s iteration order
  changes: the search's tables don't read it; the solver's
  `MemoryStore::iter` does (the order a game's solved states are offered).
  Its contents stay equal as a set; build step 1 lists every reader of
  that order and pins the behaviour it must keep.

## Fits with

- Golden games and proving sets: identical (`cargo test`, golden.txt
  byte-identical; `context/rules-version` unchanged).
- Codec encodings: identical for every state (existing codec round-trip
  and golden tests).
- Heuristic and contract nets: bit-identical on the series states
  (`scripts/series_check.py` PASS).
- Search: H4 identical (`two_turn_phases 100 --check` on main's build and
  the new one, byte-identical files).
- Python features, `sts.Combat` piles and powers: unchanged (Python
  suites that touch them: test_features, test_render, test_contract).
- Solver store order: the readers found in step 1 keep their results
  (sets equal; any order-dependent output pinned by a test written in
  step 1 on the unchanged code, then held).

**When in doubt:** prefer identical results over speed; prefer a panic
with a named capacity over a silent truncation.

## Scope

May change: `engine/src/state.rs` (`Pile`), `engine/src/powers.rs`
(`Powers`), the codec's power read/write calls, engine tests and
examples, docs (README's state layout lines, this spec, decisions).
Off limits: the codec's byte format, `CardId`'s width, the registry's
scope, search and solver algorithms, Python APIs, features, nets,
`content/*.json`.

## Decisions taken (provisional, in docs/decisions.md)

1. Per-pile and per-creature inline lists (each `Pile`/`Powers` stays a
   self-contained value with its methods), over one combat-wide card
   table shared by the piles (smaller, but every pile call would need the
   table: an API change across the engine) and over spill-to-heap lists
   (states stop being `Copy`-cheap).
2. Capacities 40 per pile and 12 per creature, fixed at compile time;
   overflow panics.
3. `CardId` stays `u8`; the registry stays per process.

## Outside assumptions

- Rust's derived `Hash`/`Eq` on arrays of plain integers hash and compare
  the raw bytes (a slice write): the slope measurement relies on it, and
  the census tool's numbers stand as measured.

## Verification

Tests first (step 1, passing on today's code):
- `engine/tests/sparse.rs::pile_ops`: from_cards of a mixed list, add,
  remove to zero, add_pile/remove_pile, nth across entries, iter order,
  len; expected values computed from a dense reference in the test.
- `sparse.rs::powers_ops`: add to zero deletes, clear, just_applied
  through add/clear, `clear_round_flags`.
- `sparse.rs::equal_contents_equal_states`: two piles (and power blocks)
  reached by different add/remove orders compare and hash equal.
- `sparse.rs::overflow_panics` (after the change only: `#[should_panic]`
  at 41 distinct ids, 13 powers).
- Step 1's solver-order readers test (named there).
End to end: golden identical, `series_check.py` PASS, H4 identical, and
`series_speed.py` (11 interleaved runs, old main build vs new) shows
search 1 thread at least +5% games/s with random combats no worse than
-10%; `two_turn_phases --census` reports the new size.

## Don't guard

Content past 256 card ids; more than 5 monsters; reading old saved
states (the codec format is unchanged, so there are none to migrate).

## Build steps

1. Tests above (except overflow) on today's code; list the readers of
   `MemoryStore::iter`'s order and pin each with a test. Check: they pass.
2. `Powers` as a sorted list; codec through methods. Check: cargo test,
   golden identical, codec tests, sparse.rs.
3. `Pile` as a sorted list, Debug in the dense form. Check: as step 2,
   plus `series_check.py` PASS and H4 identical.
4. Speed and size: `series_speed.py` 11 runs vs main's build,
   `two_turn_phases --census`, the Python suites that read piles and
   powers. Check: the bars in Verification. If search is not faster,
   stop: record the numbers, don't land.
5. Docs: README layout lines, results in decisions, the census line.

Build plan: 5 steps, forks, on Opus. Stop point: step 4 (speed below the
bar means the lever doesn't pay; record and drop).

## Results (built 2026-11-06, lane sparse-state)

Built as specified with one change to `Powers`' layout: the first build
(sorted ids and amounts, `get` scanning the list) cost random combats
about 17% (bench medians over 15 interleaved rounds; the new `Pile`
alone cost nothing measurable), because hook and damage code asks every
creature for powers it doesn't hold. `Powers` now keeps a held-power
bitmask (`held: [u32; 2]`, power `p` at bit `p`) and the amounts in power
order; an entry's index is the number of held powers below it
(popcount), so `get` is a bit test and a popcount, and the id array is
gone. Behaviour, equality (the mask is derived from the contents) and
the overflow panic are as specified. `Pile` is the sorted list as
specified; its overflow message names the card and `PILE_CAP` but not
the pile (a `Pile` doesn't know which pile it is).

Sizes: `CombatState` 1,292 -> 744 bytes (-42%); 4 piles 608 -> 324;
6 power blocks 504 -> 240; one monster 52 bytes (`two_turn_phases 100
--census`; the census figures are unchanged: max 9 distinct ids in a
pile, 6 powers on the player, 4 on a monster).

Checks, against main at 1ad4938 (after rebasing over act1-content C1):
- `cargo test --release` green (39 binaries), `golden.txt` unchanged;
  `engine/tests/sparse.rs` 5 tests (pile and power ops against dense
  references, equal contents equal and equal-hashing, both overflows).
- H4: `two_turn_phases 100 --check` byte-identical (200 lines).
- `series_check.py` PASS (3,104 states; heuristic and product net
  bit-identical, old columns equal; main's module built at 1ad4938 vs
  this one).
- Python suites on the new module: test_contract, test_lookahead,
  test_gen_powers_read, test_gen_content, test_mutate_monsters,
  test_net, 67 passed (`test_features`/`test_render` named above don't
  exist).
- Solver store order: no reader depends on it (step 1; only
  `engine/tests/solve.rs` reads `MemoryStore::iter`, with `.all`).
- `series_speed.py`, 11 interleaved runs, medians, main's build vs new:
  search 1 thread 475.2 -> 558.6 games/s (+17.6%, new faster in 10 of 11
  pairs), 16 threads 1,300.6 -> 1,761.8 (+35.5%), random combats
  2.68M -> 3.04M per minute (+13.3%), clone 26.5 -> 20.7 ns. Another
  job ran throughout; interleaving shares that load.

README has no state-layout lines, so it is unchanged.
