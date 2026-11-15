# Copies by value: wide card ids, piles that stack copies, no variant cap

Status: closed (2026-11-13, built and in use; steps a-c on main, d45a2e9c; kb measurement/sparse-piles@speed; Results section).

## Why (goals)

The owner leads Act 1 content (kb `decision/act1-owner-led`): every Act 1
relic and potion loading from content files and acting as the game's
class. Several entries change one copy of a card for the rest of the
combat: Snecko Oil and Snecko Eye give each card a random cost 0-3,
Madness, Chrysalis and Metamorphosis set a cost of 0, Enlightenment+ a
cost of 1. Today the engine can hold at most 4 such changed copies per
fight (with all 4 in use a fifth copy silently stays unchanged, which
breaks the rules), and every pack card a fight might meet takes one of
40 reserved card slots bound at fight start. Both limits come from one
cause: a card id is one byte. This spec makes a copy identified by what
it is (its card, its level, its own numbers), so equal copies are equal
by construction, both caps go away, and the cost-for-the-combat
change can be built with Snecko Oil and Snecko Eye as proving content.

We'll know it worked when: Snecko Oil (32 of 33 potions) and Snecko Eye
(57 of 141 relics) load and pass tests against their decompiled classes;
a fight holding more than 4 changed copies plays them all by the rules
(a test); a fight binds more than 40 pack cards (a test); and every pin
below is unchanged with `series_speed` within 10% of main.

## What the code is today (a mismatch with the brief)

The brief describes a pile as a dense array with one count per card id.
That stopped being true on 2026-11-06 (`docs/specs/sparse-state.md`,
kb `measurement/sparse-state@speed`): `Pile` (`engine/src/state.rs`) is
already a short list of (card id, count) sorted by id, capacity 40
(`PILE_CAP`), 81 bytes; only its debug text still prints the dense form.
So the list half of the target exists. What is still missing is the id:

- `CardId(u8)`. Ids: 128 official (`NUM_OFFICIAL_CARDS`, 64 kinds x base
  and `+`), then 8 pack-card slot pairs (128-143), 4 variant ids
  (`VARIANT_BASE` = 144-147), then 32 more slot pairs (148-211);
  `NUM_CARD_IDS` = 212, asserted below 256.
- A changed copy (a *variant*, `Overrides { damage, level }`) is interned
  process-wide but held through `Binding::variants: [u16; 4]`, sorted by
  value; adding or dropping one renumbers ids 144-147 in every pile, the
  known top, the free marks, the play queue and the card in play
  (`hold_variant`, `drop_unused_variants`, `renumber_variant`).
- A pack card's definition depends on the fight's power slots, so it is
  bound per fight to a slot id (`registry::bind`); discovery's and
  Entropic Brew's pools are bound up front, which is what pushed the
  slots from 32 to 40.

## Speed probe (measured before fixing the design)

`docs/specs/sparse-piles-probe.rs`, standalone (`rustc --edition 2021 -C
opt-level=3 -C target-cpu=native`, binary in `target/`). It models a
state as its piles plus filler, so today's layout totals 744 bytes (the
real `CombatState`), and times three things: one simulated turn of pile
work (draw 5 by sampling a count, scan the hand, play 4 to discard or
exhaust, reshuffle, discard the hand: about 20 pile operations); the
search's per-node clone + FxHash + equality on the whole state; and two
count lookups. All layouts run interleaved, 21 rounds, medians. The
machine was heavily loaded by other work (today's layout's turn took
563 ns here against 355 ns in a quieter earlier run), so only ratios
within one run are worth reading; the table is one run, 2026-11-13.

Layouts:
- **A**, today: ids `[u8; 40]`, counts `[u8; 40]` per pile.
- **B**: ids `[u16; 40]` (copy handles), counts `[u8; 40]`; order is the
  handle for a plain copy, a table-read key for a changed one.
- **B10**: B, with the hand at capacity 10 (`HAND_LIMIT`).
- **C**: inline value keys `[u32; 40]` (card u16 + parameters u16).
- **Au, B10u**: A and B10 hashing only the entries in use.
- **S64, S96**: the hand as B10u; draw, discard and exhaust share one
  list of 64 or 96 entries, sorted by pile and then by order, so each
  pile is a contiguous run; the three runs' lengths are kept; only the
  entries in use are hashed.
- **D**: dense `[u8; 256]`, the pre-2026-11-06 layout, for reference.
- "param 0.3": 30% of the deck's distinct copies are changed copies (a
  Snecko-heavy fight), so inserts read the order table.

Ratios to A for decks of 5 / 15 / 25 distinct copies (10 / 25 / 35
cards); lower is faster:

| layout | state bytes | turn's pile work | clone+hash+eq | 2 counts |
|---|---|---|---|---|
| A today | 744 | 1.00 (563 / 681 / 842 ns) | 1.00 (389 / 441 / 442 ns) | 1.00 |
| B | 908 | 1.02 / 1.04 / 0.95 | 1.21 / 1.30 / 1.23 | 0.83 / 1.09 / 1.03 |
| B, param 0.3 | 908 | 1.10 / 1.21 / 0.98 | 1.25 / 1.30 / 1.21 | 0.72 / 1.03 / 1.48 |
| B10 | 818 | 1.01 / 1.05 / 1.06 | 1.27 / 1.26 / 1.18 | 0.66 / 0.91 / 0.93 |
| C inline values | 1,236 | 0.99 / 1.03 / 1.14 | 1.67 / 1.54 / 1.71 | 0.98 / 1.58 / 1.04 |
| Au | 744 | 1.08 / 1.04 / 1.00 | 0.88 / 0.74 / 0.80 | 0.83 / 1.08 / 1.56 |
| B10u | 818 | 1.11 / 1.13 / 1.09 | 0.94 / 0.90 / 0.95 | 0.75 / 0.95 / 1.09 |
| B10u, param 0.3 | 818 | 1.12 / 1.21 / 1.00 | 0.97 / 0.98 / 0.93 | 0.99 / 1.37 / 0.81 |
| **S64** (chosen) | 648 | 1.13 / 1.26 / 1.11 | **0.66 / 0.74 / 0.72** | 0.57 / 1.00 / 1.13 |
| S64, param 0.3 | 648 | 1.20 / 1.37 / 1.27 | 0.70 / 0.68 / 0.72 | 0.63 / 1.13 / 1.12 |
| S96 | 744 | 1.22 / 1.31 / 1.13 | **0.74 / 0.75 / 0.83** | 0.74 / 0.98 / 0.71 |
| S96, param 0.3 | 744 | 1.41 / 1.36 / 1.35 | 0.76 / 0.71 / 0.68 | 0.66 / 0.94 / 0.82 |
| D dense | 1,444 | 4.62 / 3.99 / 3.28 | 1.86 / 1.82 / 1.76 | 0.62 / 0.94 / 0.87 |

The count column swings by up to 1.5x between neighbouring rows (a 6-8 ns
operation on a loaded machine); read it as "about equal".

What it says:
- With a separate list per pile, the id width costs only through size:
  clone + hash + equality grows 1.2-1.3x for B (+164 bytes) and 1.5-1.7x
  for inline values (C, +492 bytes). C is out.
- Hashing only the entries in use (tails are zero by invariant, so equal
  piles still hash equally) is a win on its own (Au: 0.74-0.88x), and
  with a 10-entry hand it pays for the wider ids (B10u: 0.90-0.95x).
- Sharing one list between draw, discard and exhaust is the fastest at
  the search's per-node work (S64: 0.66-0.74x, state 648 bytes, 96 fewer
  than today) and slower at moving cards (1.11-1.26x; 1.20-1.37x with
  changed copies), because an insert or removal shifts the entries of the
  piles stored after it. S96 has today's size and gains less (0.74-0.83x).
- Which matters more: a search node does one clone + hash + equality and
  only a few pile operations (playing a card is one removal and one
  insert); the probe's turn is about 20. Weighting the turn by 3/20
  estimates the per-node cost of S64 at about 0.75-0.85 of today, and of
  B10u at about 0.95-1.0. That weighting is a guess; `series_speed` at
  step (a) decides.
- The probe covers piles only. The other card ids in the state (known top
  16 + 8 floaters, free marks 10, play queue 6, offer 3, card in play)
  add about 45 bytes more at u16; they get the used-only hash too.
- Measured at step (a): search about 1.0x of main (jobs 0974, 0985), not
  the estimated 0.75-0.85; state 816 bytes, not the estimated ~690. The
  shared list saved the 96 bytes it was meant to and the widened known
  top, free marks and play queue added 52, as estimated; the miss is the
  base: the probe took today's state as 744 bytes, but relics and potions
  had grown it to 860 by the build, so the net 44 bytes is 5% of the
  state, not the probe's 13%. The 3/20 weighting of pile work per node
  was a guess.

## Design

### A copy and its handle

A *copy* is a card as one physical card holds it: its card (an official
card, or a pack card by its slot in this fight), its level, and its own
numbers for the combat. `CardId` becomes `u16`, a handle to a copy:

- `0..128`: official cards at level 0 and 1 with no own numbers, the ids
  of today (`kind * 2 + upgraded`).
- `128..PARAM_BASE` (`PARAM_BASE` = `0x8000`): plain pack cards, by this
  fight's slot. Slots 0-39 keep today's ids (128-143 and 148-211);
  slot 40 and up continue from 212 (`slot_card(k) = 212 + 2(k - 40)`),
  base then `+` as today. Ids 144-147 (today's variants) stay unused.
- `PARAM_BASE..`: a *changed copy*, interned process-wide by value:
  key (base handle, the base's definition address, `Params`), the same
  key `variant_index` uses today. `Overrides` (the name kept; called `Params` in this spec) grows:
  `level` (2 and up, beyond the id pair), `damage: Option<i16>` (grown,
  Rampage), `cost: Option<i8>` (a cost for the combat, new), and room
  for more fields. Its definition (base definition with the numbers
  replaced, named `Base{damage=13/combat}` as today) is built once at
  interning and cached in the table, so `Binding::def` stays a table
  read.

Equal copies get equal handles because interning is by value, so a pile
of (handle, count) stacks equal copies and equal piles are equal bytes:
the afterstate rule (`docs/concept.md`) holds with no renumbering. A
changed copy whose numbers equal its level's own numbers is the plain
copy (interning normalises: `Params` hold only differences), because
the two play identically: the game's `isCostModified` only changes the
card's colour on screen, and an upgrade treats them alike. A card whose
upgrade changes its cost calls `upgradeBaseCost`, which sets `cost` to
the new base whatever it was (`cards/AbstractCard.java` 710-720 in
aeubanks/sts, 890-900 in Li-Binghui/MySlayTheSpire, identical); a card
whose upgrade doesn't change its cost keeps `cost`, which for a
normalised copy equals the plain copy's.

The interned table: lock-free reads (an append-only array of
`OnceLock`, as today's variant table); writes under a mutex, with a
per-thread cache in front, since Snecko Eye interns on every draw and
search runs 16 threads. Capacity 32,768 changed copies per process; a
process that needs more stops with an error naming the bound (today a
full table silently leaves the copy unchanged).

### Pile order

Order matters: drawing maps a random index to a card through the pile's
order (`Pile::nth`, `chance.rs`), so the order is part of every seeded
game. To keep every pin, the order is today's id order, extended:
- a plain copy sorts by its handle;
- every changed copy sorts where today's variants sit (after the official
  cards and slots 0-7, before slot 8), and among themselves by value:
  (base handle, level, damage, cost), which for today's variants is
  today's `variant_key` order.

This placement (changed copies between slot 7 and slot 8, ids 144-147
left unused) is kept on purpose, not by accident: pile order decides
which card a seeded draw takes, so moving changed copies elsewhere
changes `golden.txt`'s proving games, the rules version hashed from the
golden games and the solved DB's replays.

### Pile layout (S64; S96, then B10u, the fallbacks)

The hand is its own list: `[u16; 10]` handles and `[u8; 10]` counts
(`HAND_LIMIT` bounds its entries). Draw, discard and exhaust share one
list of 64 entries (`PILE_CAP`; `[u16; 64]` handles, `[u8; 64]` counts,
the three piles' lengths): sorted by pile, then by the pile order above,
so each pile is a contiguous run and iterates exactly as a pile of its
own would. The runs are stored exhaust, draw, discard (the pile that
changes least first, so inserts shift fewer entries); storage order is
internal and no pile's own order depends on it. `state.draw()` reads a
pile, `draw_mut()` changes it and `set_draw(...)` replaces it, through
small view types that know which run they work on. Equality checks
compare handles only; an insert reads the order key (`handle << 48` for a
plain copy, one table read for a changed one). `Hash` covers only the
entries in use.

Why shared, and why 64: the probe puts the shared list ahead at the
search's per-node work (S64 0.66-0.74x of today, S96 0.74-0.83x), and a
single pile may use every entry the others leave, at the price of
slower card moves (an insert or removal shifts the runs stored after
it). The fight-start check below keeps 64 from capping real decks. Step
(a) first landed S96 (main 8f5f3ecb, series_speed -4.3% / -4.1%); the
coordinator then chose S64 with the owner. If S64's `series_speed`
against main shows no clear gain at search games/s, an S96 bench is
built and compared before choosing; B10u (a separate 40-entry list per
pile, a 10-entry hand, used-only hash) stays the last fallback. The rest
of the spec doesn't change.

### What goes away and what stays

- Gone: `Binding::variants`, `VARIANTS`, `VARIANT_BASE` as an id range,
  `hold_variant`, `drop_unused_variants`, `renumber_variant`, every
  `map_cards` used for renumbering, the "all variant slots in use, the
  copy stays unchanged" branches (`grow_damage`, `upgrade_in_hand`), and
  `NUM_CARD_IDS <= 256`. `CARD_SLOTS` = 40 becomes a growable slot list:
  `Slots::cards` a `Vec` in the interned slot set.
- Stays, and why:
  - **Per-fight slots for pack cards.** The brief asked for a pack card
    by its definition with no per-fight slot. A pack card's definition
    is per fight anyway (its effects name this fight's power slots), and
    its order in a pile is its slot order (first appearance in the deck,
    then pools); a fight-free order would reorder every pile holding two
    pack cards and change the pack pins (Python pins, `relic_baseline`).
    What the slots cost today is the cap, and that goes. Pools are still
    bound at fight start, which keeps slot order canonical; with no cap
    that costs one bigger interned slot set.
  - **64 entries across draw, discard and exhaust, checked at fight
    start by entries, not cards.** An entry is one kind of copy in one
    pile with its count (5 Strikes in the discard pile are one entry). A
    kind with `k` copies can take at most `min(k, 3)` entries, one per
    pile, so a deck's cards take at most the sum of that over its kinds
    (`state::entries_needed`): 60 Strikes take 3, 40 distinct cards 40.
    A fight is refused at start (`CombatState::new_with_turn1`, and as an
    error in `registry::bind`) when that sum plus `MADE_ROOM` = 12
    entries for cards the fight makes (statuses, made and discovered
    copies: about four kinds in each pile) passes 64; the refusal names
    `PILE_CAP` and `MADE_ROOM`. `MADE_ROOM` is a fixed allowance, not a
    count of what this fight can make; a fight that still overflows
    mid-fight panics naming `PILE_CAP`. Content that splits copies by
    their own numbers on draw (Snecko Eye's Confused, from step (c))
    breaks the per-kind count, so with a splitter held the check bounds
    the cards outside the hand instead: at most 64 - 8 = 56. Today's
    bound is 40 entries per pile.
  - 10 entries in the hand: `HAND_LIMIT`, the game's own limit.
  - 24 generated-power slots (`POWER_SLOTS`): unrelated, untouched.
  - Changed copies per encoded state: at most 111 (see codec).

### Codec (`engine/src/codec.rs`)

The DB's keys (`db/`, not rebuildable). No byte changes for any state
the codec encodes today; `CODEC_VERSION` stays 1.

- An official plain copy writes its byte as today (`< 128`).
- Changed copies: the state's distinct changed copies (piles, known top,
  play queue, free marks, card in play) sorted by the pile order above
  get ranks 0, 1, ...; a copy writes `144 + rank`, as today's variant ids
  do. A state whose changed copies are all grown damage at their base's
  own level writes trailer section 2 exactly as today (count, then base
  byte and zigzag damage per copy). Any other changed copy (a level 2+
  official card, a cost for the combat) writes the new section 13
  instead: count, then per copy base byte, level, a flag byte (bit 0
  damage, bit 1 cost), then the numbers flagged. At most 111 changed
  copies (`144 + rank <= 255`); more panics with the bound named.
- Pack cards still aren't encoded (`has_generated`), as today.
- `encode_action` and `decode_action` (`solvedb/src/rows.rs`) take the
  state, so a played or picked changed copy writes its rank byte as
  today's variant id did.
- The new chance event for a random cost (step c) takes pending tag 7.

### Net features (`py/src/features.rs`)

No layout changes. An official plain copy reads its precomputed vectors
by handle, as today. A changed copy goes through the generated path, as
a variant does today: its vector, rows and held rows come from its own
definition, so a cost for the combat is simply its `cost` column, a
grown damage its effect's amount. The `Ids` card representation maps
every handle outside the vocabulary to the "other" column, as today's
variant ids are. Tables indexed by card id (`card_index`, `card_vecs`)
are indexed only for official handles. Existing nets' inputs are
identical byte for byte because no state they see changes.

### Pins

Golden games (`engine/tests/data/golden.txt` and the rules version
hashed from it), `golden_proving.txt` (Rampage variants included),
`codec_golden.txt`, `relic_baseline.txt`, `potion_free_legal.txt`, the
turn-start pins and every Python pin: unchanged at every step, because
pile order, codec bytes, names and features are unchanged for all
existing content. Debug text keeps today's dense form for official
cards and slots; changed copies (today printed at ids 144-147, in no
recorded text) print as a separate `changed` list only when present.

### Every reader of card ids, and what it becomes

| reader | today | becomes |
|---|---|---|
| `Pile` | `u8` ids, 40 entries per pile | `u16` handles; hand 10 entries; draw, discard and exhaust share 64; used-only hash |
| `Binding` | slot set + `variants[4]` | slot set only (growable); `def` reads the changed-copy table for handles from `PARAM_BASE` |
| `Binding::def`, `is_bound` | slot or variant lookup | official / slot / changed-copy table; `is_bound` checks the handle's range |
| `registry::upgraded` | `Upgraded::Id` or `Variant(idx)` | returns the upgraded copy's handle (interned when changed) |
| `grow_damage` (Rampage), `upgrade_in_hand`, `upgrade_hand` | renumber, may silently skip | replace the copy's handle; never skip |
| known top (`Top`) | `u8` known and floaters | `u16`; used-only hash |
| card in play, `TopQueue`, `Offer` | `u8` | `u16` |
| `free_in_hand` (`FreeMarks`) | `u8`, renumbered | `u16`, never renumbered; a random cost on a marked copy removes its mark (the game sets `costForTurn` to the new cost) |
| picks, `Action::Choose/Play` | `CardId(u8)` | `CardId(u16)`; codec writes rank bytes |
| discovery pools (`docs/specs/discovery.md`) | bound up front under the 40 cap | bound up front, no cap |
| Python `sts` API, action text | names from `def` (`Rampage{damage=13/combat}@0`) | same; new numbers print in fixed order: `Strike{cost=0/combat}`, `Rampage{damage=13/combat,cost=2/combat}` |
| `Combat.step` named card check | `is_bound` | same, on the wider handle |
| explorer (`scripts/explore`, `content/wording.json`) | names and words | same; the new effect and power get words |
| features | official tables, variants generated | same split by handle range |

## Build order

Each step lands on main on its own, keeps every pin, and is checked by
the engine tests in debug (`cargo test -p sts-engine`, `cargo test -p
sts-py`, `CARGO_BUILD_JOBS=2`), one release wheel under the
`act1-release` lock for the Python pins, `scripts/tests/test_explore.py`
and `series_check`.

**(a) Wide handles and the shared layout, zero behaviour change.**
`CardId(u16)`; the 10-entry hand and the shared 64-entry list for draw,
discard and exhaust; used-only `Hash` for piles, `Top` and `FreeMarks`;
every `u8` card field widened; codec writes through a card-to-byte map
(official byte or `144 + rank`); variants still held as today (4, with
renumbering), now at handles `144-147`; the fight-start check on deck
by entries (above). Check: every pin identical; no test, pin or job
deck refused; `size_of::<CombatState>()` reported; one `series_speed`
through the job queue against main (bar: search games/s within 10% of
main; with no clear gain, an S96 bench compared; B10u last). Value alone: the id space is no
longer a byte, the state is smaller, and the used-only hash.

**(b) Copies by value; the caps go.** Changed copies become interned
handles from `PARAM_BASE` with the pile order above; renumbering and
`Binding::variants` removed; `Overrides` holds the numbers; normalising
interning; card slots growable. Check: pins identical; new tests: 6
grown Rampages in one fight all grow by the rules; Armaments+ upgrading
a hand of 5 changed copies; a fight binding 50 pack cards; codec round
trips for a level-2 official copy (section 13) and for 5 grown Rampages
(section 2 bytes as today's form, ranks 0-4).

**(c) A cost for the combat; Snecko Oil and Snecko Eye.** `Params::cost`;
an effect that gives each card in hand a random cost 0-3 for the combat
(Snecko Oil: one chance event per hand card, 4 equal outcomes, cards
whose cost is below 0 skipped) and the power that does it to each drawn
card (Confused, Snecko Eye's, with its +2 draw); the upgrade rule for a
copy with a changed cost from the game's `upgradeBaseCost`; words in
`content/wording.json` and `registry::element_names()`. Each read from
the decompiled `SneckoOil`, `SneckoEye`, `ConfusionPower`,
`RandomizeHandCostAction` and `AbstractCard`, two copies compared, file
and line cited; Snecko Oil's draw count (5, marked unverified in
`docs/research/act1-relics-potions.md`) settled there. Proving content:
Snecko Oil (potions 32 of 33), Snecko Eye (relics 57 of 141). Unblocked
words, no loads (the colorless pack doesn't exist): Madness, Chrysalis,
Metamorphosis (cost 0 for the combat), Enlightenment+ (cost 1).
`series_speed` again at the end, bar 10%. Known cost: Snecko Eye
multiplies a draw's chance outcomes by up to 4 per card; exact
enumeration of a 7-card draw under it is large, and search samples
draws as today.

## Expensive to reverse (for the coordinator)

1. **Codec section 13 and the rank bytes.** Existing bytes don't change,
   but once rows with changed copies other than grown damage land in
   `db/`, section 13's layout is fixed for good (the DB isn't
   rebuildable). Today no DB row has one.
2. **Normalising a changed copy that equals its card back to the plain
   copy.** It decides which states are equal, so it shapes DB keys and
   search tables; undoing it later splits states that were one.
3. **Keeping per-fight slots and today's order (changed copies between
   slot 7 and slot 8).** Cheap now; moving to a fight-free order later
   re-records every pack pin and `relic_baseline`.
4. **Action text for the new numbers** (`{cost=N/combat}`, fixed field
   order): a Python contract that logs and replays will hold.
5. **One chance event per card for a random cost** (pending tag 7):
   shapes search trees and codec bytes for Snecko states.

Not expensive: the pile layout (shared or per pile), the 10-entry hand,
used-only hashing, the fight-start entries check, the 32,768 bound (all
internal; nothing stored depends on them).

## Cleanup

The probe writes `target/pile_probe.exe` and `.pdb`: build output,
removed by `cargo clean` or by deleting them. Its source stays as
`docs/specs/sparse-piles-probe.rs` for re-measuring.

## Results

**Step (a), first landing** (S96, main 8f5f3ecb, 2026-11-13; replaced
by S64, below):
- `size_of::<CombatState>()` 912 bytes against main's 860 (e44c3d42; the
  744 in the probe section is the 2026-11-06 size, before relics and
  potions grew the state). The piles take the same bytes as before (one
  292-byte shared list and a 32-byte hand against four 81-byte piles);
  the +52 is the other widened card ids: the known top +32 (its
  floaters pad to 4 bytes), the free marks +11, the play queue +7, the
  offer +3.
- `series_speed` (job 0971, 25 interleaved runs, on a heavily loaded
  machine: 1-thread search ran at about 200 games/s against about 500 on
  a quiet one): search 1 thread per-run ratio median -4.3% (medians
  219.0 -> 195.9, -10.5%), 16 threads -4.1% (997.5 -> 987.8, -1.0%);
  random combats -9.7%; clone 37.0 -> 50.3 ns. Within the 10% bar on
  the per-run ratios, the read the series uses
  (kb `measurement/series-speed@order`), so B10u is not needed.
- Pins: engine tests in debug (88 targets), golden games, codec golden,
  `relic_baseline`, turn-start pins unchanged; `series_check` PASS on
  3,104 states (heuristic and every old feature column identical); the
  Python pins, contract, explorer and explorer-pin tests pass (109).

**Step (a), S64** (replaces S96, 2026-11-13):
- `size_of::<CombatState>()` 816 bytes (main before sparse-piles 860,
  S96 912): the shared list 196 bytes.
- `series_speed` job 0974, S64 against e44c3d42 (before sparse-piles),
  loaded machine: search per-run ratio 1 thread +3.8% (medians 187.5 ->
  188.4), 16 threads +3.1% (768.8 -> 764.8); random combats -10.8%;
  clone 37.9 -> 64.8 ns. No clear gain at search (one 25-run read has an
  se of about 4-5%), so S96 was benched against it.
- Job 0985, S96 (main d08ef5a4) against S64: search per-run 1 thread
  +0.8%, 16 threads +0.4% for S64; random combats -1.0%; clone +12.4%
  faster. Equal at search; S64 stays (smaller state, faster clone, and
  the coordinator's choice).
- Pins as for S96: engine tests in debug (89 targets) unchanged;
  `series_check` PASS on 3,104 states; Python pins, contract and
  explorer tests pass (109).

**Step (c)** (cost for the combat, Snecko Oil and Snecko Eye, 2026-11-13):
- `Overrides::cost` (interned by value; the card's own cost normalises to
  the plain card; named `Strike{cost=0/combat}`, damage first:
  `Rampage{damage=13/combat,cost=2/combat}`); an upgrade that changes a
  card's cost resets it (`upgradeBaseCost`), one that doesn't keeps it.
- Effect `RandomizeCost` "Hand" (Snecko Oil) and "Drawn" (only a
  `CardDrawn` hook with condition `Always`: Confused); the waiting copies
  in `CombatState::cost_rolls` (one entry per copy with its free mark,
  sorted), rolled one at a time by `ChanceEvent::RandomCost` (4 outcomes
  alike) as soon as the stage machine runs; a different roll moves the
  copy to its cost and ends its mark. Relic key `draw_per_turn` (Snecko
  Eye's 2). Innate cards in the opening hand are rolled too (the game
  draws them).
- Codec: pending tag 7; trailer section 14, the waiting copies with their
  marks (not in the spec's first draft: the queue is state); section 13's
  flag bit 1 for a cost. Existing bytes unchanged.
- Named limits: a roll happens after the effect that drew the card (the
  game's during the draw; no current card reads a drawn card's cost in
  the same effect list); Confused's `freeToPlayOnce = false` has no
  engine counterpart; a rolled Blood for Blood still costs less for HP lost
  before the roll; Entropic Brew's pool now holds Snecko Oil.

**Final speed** (after step (c), 5240b8fb against e44c3d42, main before
sparse-piles): two `series_speed` jobs on a heavily loaded machine, each
stopped early. Job 1007 stopped at run 17 when the old build's
`search_speed.exe` aborted (0xC0000409, low memory); job 1013 at
run 23 when the new `bench.exe` failed its own floor of 100,000 random
combats a minute (151,538 at run 22, the machine's load; three clean runs
by hand after). The completed runs, 16 and 22 interleaved pairs:

| job | search 1 thread | search 16 threads | random combats | clone |
|---|---|---|---|---|
| 1007 (16 pairs) | +0.7% | +2.7% | -8.9% | +10.8% faster |
| 1013 (22 pairs) | +3.6% | +1.8% | -4.4% | +14.9% faster |

(per-run ratio medians). Search is level with main before the change,
inside the 10% bar; no third job was run on the shared CPU.
