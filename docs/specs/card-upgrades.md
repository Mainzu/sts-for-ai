# Card upgrades as data (building block C6)

Status: closed (2026-11-10, built and in use; owner-led session; docs/research/act1-inventory.md "Block C6 as built", decisions "Card upgrades as built"; Amendment 1 (successor) built too).

The owner's design (explorer session, 2026-11-08); this spec settles its
open points.

## Outcome

A card says in its own entry what an upgrade changes, and how many times it
can be upgraded, so the engine and the run layer can upgrade any card:
Armaments upgrades cards in combat, Searing Blow upgrades without limit, and
the gauntlet's rest site can upgrade pack cards. Today every upgrade is a
second card entry ("Bash" / "Bash+"), and pack cards can't be upgraded at
all.

**How it moves the goals.** Goal 1 (custom content as data): a designer
writes one entry per card, and most upgrades are a line of number changes.
Goal 2 (the real Act 1): Armaments and Searing Blow's repeats load from the
pack, and the run layer's rest site works with pack cards. We'll know by
the lane's measure: the blocked count drops by one (Armaments), Searing
Blow's levels match the wiki in a test, and the series checks hold (golden
identical, `series_check` PASS, `series_speed` at most 10% slower).

**Non-goals** (owner, 2026-11-08): Apotheosis and other upgraders outside
Act 1's Ironclad cards; curses (the engine has no Curse type yet; when it
gets one, curses follow the status rule below); relics that upgrade cards;
training a net on levels; any change to how the rest-site chooser decides
(it gets the new names and nothing else). No new net input column for the
level. Hexaghost's Inferno stays the code it is.

## Behavior

### The format

One entry per card. Beside today's fields an entry may have:

| Field | Meaning | Default |
|---|---|---|
| `"upgrade": {<path>: <change>, ...}` | What each upgrade changes. | none: the card has no upgrade by changes |
| `"max_level": <n>` or `"max_level": null` | Highest level; `null` means no limit (Searing Blow). | 1 with an `upgrade` block, 0 without |

A **path** names one number or keyword of the entry:
- `"cost"`;
- a keyword: `"exhaust"`, `"ethereal"`, `"innate"`, `"retain"`;
- a number inside an effect: `"effects.<i>.<Effect>.<field>"`, e.g.
  `"effects.0.Damage.amount"`, `"effects.1.Apply.amount"`,
  `"effects.0.Damage.hits"`, `"effects.0.ScaledDamage.amount.k"`, and the
  same for `"rows.<r>.effects.<i>..."`, `"turn_end.<i>..."` and
  `"exhausted.<i>..."`. A bare-number effect is its own field:
  `"effects.0.Block"`, `"effects.1.Draw"`.

A **change** is:
- for a number, an amount added at each upgrade: a plain number (`2`,
  `-1`), or a string expression of `n`, the level being reached
  (`"n + 3"`). The expression language is integer constants, `n`, `+` and
  `*`, with the usual precedence and nothing else (no parentheses,
  division or other names). The value at level L is the base value plus
  the change at n = 1, 2, ..., L.
- for a keyword, the value it takes from level 1 on (`"exhaust": false`).
  It doesn't flip back and forth at higher levels.

Bounds: cost can't go below 0. The bound is the field's, not the card's:
each step clamps at it. No other number has a bound (Disarm's -2 can
become -3).

**Cost, X and Unplayable** (owner, 2026-11-08, as the game encodes them):
`cost` holds a card's energy cost, or `-1` for an X-cost card or `-2` for
an unplayable one. The `x_cost` and `unplayable` fields go away, so a card
that is both can't be written. In the engine, `CardDef`'s cost is private
behind three methods: `cost()` (the energy to pay: 0 for X and unplayable
cards, as every cost reader sees today), `x_cost()` and `unplayable()`.
No reader sees a raw -1 or -2 (the energy check in `state.rs` compares cost
to energy, and -2 would pass it). The net's `cost`, `x_cost` and
`unplayable` columns are computed from the methods, unchanged. Old-format
files still load: `x_cost: true` becomes -1 and `unplayable: true` -2
(both true is a load error). A cost change in an `upgrade` block on an X
or unplayable card is a load error.

Examples:

```json
{"id": "Bash", "cost": 2, "type": "Attack", "effects": [{"Damage": {"amount": 8, "hits": 1, "target": "Opponent"}}, {"Apply": {"power": "Vulnerable", "amount": 2, "target": "Opponent"}}],
 "upgrade": {"effects.0.Damage.amount": 2, "effects.1.Apply.amount": 1}}
{"id": "Seeing Red", "cost": 1, "type": "Skill", "exhaust": true, "effects": [{"GainEnergy": 2}], "upgrade": {"cost": -1}}
{"id": "Limit Break", "cost": 1, "type": "Skill", "exhaust": true, "effects": [...], "upgrade": {"exhaust": false}}
{"id": "Searing Blow", "cost": 2, "type": "Attack", "effects": [{"Damage": {"amount": 12, "hits": 1, "target": "Opponent"}}],
 "upgrade": {"effects.0.Damage.amount": "n + 3"}, "max_level": null}
```

Searing Blow: 12, 16, 21, 27, 34 at levels 0-4 (the wiki's formula
12 + n(n+7)/2).

**Generated cards that follow the level.** `AddCard` gains an optional
`"match_level": true`: the added card takes the level of the card being
played, capped at the added card's own max level. Anger is
`{"AddCard": {"card": "Anger", "n": 1, "pile": "Discard", "match_level":
true}}`, so Anger adds Anger and Anger+ adds Anger+. The same flag covers
cards whose upgrade upgrades what they make (Storm of Steel's Shivs, Alpha
/ Beta / Omega, Transmute), outside Act 1 today. Without the flag the
added card is the one named, at level 0, as today (Immolate+ still adds a
plain Burn). The loader resolves the flag into today's `AddCard` of the
right id for each level's definition, so the engine and the net's columns
see exactly what they see today. A level-2-or-higher copy is a variant; with
every variant slot in use it is added at level 1. (Owner, 2026-11-08: a
flag on the added card, not a rule that a card naming itself means a
copy.)

**Unique upgrades keep today's way.** A card whose upgrade changes how it
works (True Grit+ picks the card to exhaust; True Grit's is random) keeps
a separate `"X+"` entry, and the name is the link: an entry `"X"` with no
`upgrade` block and an entry `"X+"` has `"X+"` as its one upgrade (max
level 1). This is also what every old-format file means, so stored packs
read the same.

Load errors, each naming the card: a path that names no number or keyword
of the entry; an expression outside the language; a cost below -2; a cost
change on an X or unplayable card; an old-format card with both `x_cost`
and `unplayable`; an unplayable card with on-play effects (`effects` or
`rows`) or `only_attacks_in_hand`; a Power with `exhaust` (these never
fire: an author's mistake); both an `upgrade` block
and an `"X+"` entry; `max_level` other than 1 with an `"X+"` entry; a
number past the engine's range (i16; cost i8) at a level the card can
reach. With `max_level: null` the range check stops at the level cap
below.

### Levels in the engine

Speed and old records come first (owner, 2026-11-08), so the card ids stay
as they are:
- Level 0 and level 1 are today's id pair (`CardId::new(kind, upgraded)`
  for official cards, a slot's base and `+` id for pack cards). The loader
  expands an entry into the two definitions the pair holds today. Every
  card at level 0 and 1 plays exactly as now.
- Level 2 and up (only Searing Blow in Act 1) is a per-copy variant, as
  Rampage's grown damage is: `Overrides` gains a level, and the variant's
  definition is the card's definition at that level (with Rampage's damage
  override on top, if any). Variants become possible on pack cards, keyed
  so equal copies are equal states in every process (as the per-copy
  overrides review fixed for official ones).
- The level is capped at 255 (a byte). With all 4 variant slots of a fight
  in use, an upgrade that needs a new variant doesn't happen, the same rule
  as Rampage's growth today (a test pins it).
- Names: level 0 `Name`, level 1 `Name+`, level N >= 2 `Name+N`
  (`gen:Searing Blow+3`). A variant that also has overrides shows them as
  today (`Rampage+{damage=13/combat}`). `Bash+` in any record still means
  Bash at level 1.

### Upgrading

- **A general upgrade** (the rest site, Armaments) raises a card one level
  if it is below its max level and is not a Status (later: not a Curse
  either). So it never makes a status worse.
- **A special upgrade** (Hexaghost's Inferno) may upgrade statuses. Inferno
  stays its code: it swaps Burn for Burn+ as today. Burn's upgrade is
  written as data (`turn_end` damage 2 to 4) so its two definitions come
  from one entry.
- **Armaments** (pack card; numbers from the wiki, checked against
  sts_lightspeed in its build step): cost 1, Skill, Block 5, then the
  player picks one card in hand that a general upgrade can raise, and it
  is upgraded for the rest of the fight. No pick when no card qualifies;
  the pick is made at once when one distinct card qualifies (picks are by
  card, as every pick is). Armaments+: Block 5, upgrade every qualifying
  card in hand. New vocabulary: `{"Pick": {"kind": "UpgradeFromHand", "n":
  1, "exact": true}}` and `"UpgradeHand"`.
- Upgrading in a fight: a level-0 copy becomes its pair's level-1 id; a
  copy at level 1 or more of a card with a higher max level becomes a
  variant one level up; a Rampage variant keeps its grown damage on the
  upgraded card (decision of 2026-10-26: per-copy state is the card's own
  numbers).

### The run layer

- `sts` gains `upgrade_name(name)` (the name one general upgrade makes, or
  `None`) and `base_name(name)` (the name without `+` or `+N`), for
  official and `gen:` names.
- `gauntlet.upgrade` and `gauntlet.upgradable` use them: pack cards with an
  upgrade are upgradable at the rest site, and `gen:Searing Blow+` becomes
  `gen:Searing Blow+2`. Readers that strip `+` to find a card's base
  (`gauntlet.py`, `granting.py`, `selfplay.py`) use `base_name`, so `+N`
  names don't break them.
- `gauntlet.py --pack` offers stay the pack's base entries (entries not
  ending in `+`, so True Grit+ isn't offered as a base).

### Versions and stored data

- The rules version (sha256 of `golden.txt`) does **not** change: the
  golden games stay identical. (The brief expected a change; with today's
  id pair kept, there is none.)
- The solved-DB fingerprint changes, as it does for every block that edits
  engine rule files or `content/cards.json`. `db/` stays (decision
  `db-kept`).
- Pinned snapshots load their own `sts` and aren't affected. Ladder caches
  are keyed by the `.pyd` hash, so a new wheel misses them as any build
  does.
- The rewritten `act1-ironclad.json` gets a new content hash (as every
  card the lane adds gives it). Records naming the old hash replay from the
  pack store's copy, which still loads (old format kept). A read with the
  rewritten pack against a control made with the old one needs `--vary
  pack`, as for any pack change.

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Official loader (`registry.rs`, `content/cards.json`) | The rewritten file loads to definitions equal, field by field, to today's file (cost compared through `cost()`, `x_cost()`, `unplayable()`) | new `upgrade_format_matches_old_cards` against a fixture copy of today's file (build step 1) |
| Pack loader, act1-ironclad | The rewritten pack's cards equal today's pack's, base and `+` | new `pack_upgrades_match_old_pack` (fixture copy, step 1) |
| Old-format packs in the pack store | Load and bind as today; `gen:X+` names its own entry | existing `engine/tests/packs.rs`; new old-fixture load test (step 1) |
| Golden games, rules version | Identical; `rules_version()` unchanged | existing golden test |
| Heuristic and product net | Bit-identical on the fixed state set | `series_check` PASS |
| Net features (effects and ids modes) | Every old column equal on golden rows, lookahead rows, curriculum and content_selfplay arrays; Armaments' new effect columns are zero on old content (as C1-C4) | existing array pins; re-pinned only for the new columns |
| Per-copy variants (Rampage) | Growth and the full-slot rule as today; slots ordered by value | existing variant tests; new upgraded-Rampage test |
| Hexaghost's Inferno | Burns become Burn+ as today | golden (Hexaghost games) |
| Codec | Official states encode to the same bytes; generated states still refused | existing codec tests |
| `gauntlet.upgrade` / `upgradable` / rest sim | Same choices for official decks | existing `test_gauntlet.py`; new tests for `gen:` and `+N` |
| Name readers stripping `+` | Same base for every name they meet today | new `base_name` unit test over every official and pack name |
| Search speed | `series_speed` at most 10% slower at 1 and 16 threads | job (step 8) |

## When in doubt

Prefer leaving today's ids, states and columns untouched over a more
general level model.

## Scope

May change: the content loaders and their parsing (`engine/src/registry.rs`,
`cards.rs`), variants (`Overrides`, interning, names), the effect
vocabulary for Armaments (effects, picks, `state.rs` where picks resolve),
the cost readers (`state.rs`, `heuristic.rs`, `agent.rs`), the Python
binding's name helpers, card info and features for the two new atoms
(`py/src`), `content/cards.json`, `content/packs/act1-ironclad.json`,
`scripts/gauntlet.py`, `scripts/granting.py`, `scripts/selfplay.py`'s base
name reads, engine and Python tests, test fixtures, `docs/extending.md`
(the upgrade rule), `README.md` (card names), the inventory doc. Formats it
may change: the card entry (new optional fields, `AddCard`'s `match_level`); variant names
(`+N`); the codec's variant section only if official variants gain a level
(none can in Act 1).

Off limits: the codec's existing bytes; the golden games; existing net
input columns and their meaning; the search; Hexaghost's code; the
rest-site chooser's decision rule; the gauntlet's settings fields and
`MATCH_FIELDS`; the pack store's hashing. Outside the repo: nothing.

## Decisions taken (provisional; `docs/decisions.md`)

- Upgrades are data in the card's entry: paths beside the effects, a
  number change added per upgrade (a constant or an expression of the level
  reached: constants, `n`, `+`, `*`), a keyword set from level 1, cost
  floored at 0, `max_level` default 1, `null` for no limit. Alternative:
  `up` written inside each effect (touches every effect's parser).
- Level 0 and 1 keep today's id pair; level 2 and up are per-copy
  variants. Alternative: a level byte per copy in every pile (changes the
  state, every encoding and search speed).
- No level column for the net: the card's numbers show the upgrade, and
  Armaments is judged on the state after it. Alternative: a `level` column
  (re-pins every array for one card's benefit).
- X-cost and Unplayable are negative costs (-1, -2), read only through
  `CardDef` methods, so a card can't be both; pointless combinations
  (unplayable with on-play effects or `only_attacks_in_hand`, a Power with
  `exhaust`) are load errors. Alternative: keep the two booleans and refuse
  both at load (same protection, the bad state still writable).
- `held_out` and `proving` aren't this spec's: `docs/specs/card-sets.md`
  (confirmed, built first) moves them out of card definitions, so this
  build's rewrite of `cards.json` starts from files without them.
- `AddCard` gains `match_level`: the added card takes the played card's
  level, capped at its own max level (Anger, Storm of Steel's Shivs,
  Alpha / Beta / Omega). Alternative: an `AddCopy` form for a copy of
  the card itself (covers Anger only).
- A unique upgrade stays a separate `"X+"` entry, linked by its name.
- General upgrades skip statuses; only special effects (Inferno) upgrade
  them.
- The official cards file and the act1-ironclad pack are rewritten into
  the new form, checked equal to the old definitions.
- Lane order: C6 comes right after M6+M7 in `act1-content`'s block order.

## Outside assumptions

- Searing Blow's damage is 12 + n(n+7)/2 at level n and its upgrade has no
  limit (wiki; sts_lightspeed's `SEARING_BLOW`). Checked by the level test.
- Armaments: cost 1, Block 5, upgrade one card in hand / all cards in hand
  when upgraded; can't pick a card that can't be upgraded (wiki;
  sts_lightspeed). Checked in step 6's test against those sources.
- Every other base/`+` pair in today's files differs only in numbers and
  keywords, except Anger (copy of itself) and True Grit (structure):
  measured 2026-11-08 by diffing every pair in `content/cards.json` and
  `act1-ironclad.json`. Step 1's equality tests re-check it.

## Verification

Tests written first (build step 1, passing on today's code):
- `upgrade_format_matches_old_cards`: the fixture copy of today's
  `cards.json` loads; every definition's fields dumped (step 4 compares
  the rewritten file's dump to it).
- `pack_upgrades_match_old_pack`: the same for `act1-ironclad.json`.
- An old-format pack fixture loads and `bind(["gen:Searing Blow+"])` plays
  16 damage.

Tests for the feature:
- Expression parser: `"n + 3"` at n = 1..4 gives 4, 5, 6, 7; `"2*n+1"`
  gives 3 at n = 1; `"(n)"`, `"n/2"`, `"m"` are load errors.
- Searing Blow at levels 0-4: damage 12, 16, 21, 27, 34; `gen:Searing
  Blow+3` binds and plays 27.
- Cost bound: a test card cost 0 with `"cost": -1` stays 0 at level 1.
- Keyword: Limit Break exhausts at level 0, not at level 1.
- `match_level`: Anger adds Anger, Anger+ adds Anger+; a test card at
  level 2 adding Searing Blow with the flag adds a level-2 copy; a test
  card at level 1 adding Wound with the flag adds Wound (max level 0);
  Immolate+ (no flag) adds Burn.
- Load errors: each case listed under the format.
- Armaments: a hand of Strike, Bash+, Wound and Searing Blow+ offers picks
  Strike and Searing Blow+ only; picking Searing Blow+ gives a level-2
  variant; Armaments+ upgrades Strike and Searing Blow+ and leaves Bash+
  and Wound; a hand with only Bash+ and Wound has no pick; Rampage grown
  to 13 and upgraded keeps 13 and grows by 8.
- Full variant slots: with 4 variants held, upgrading Searing Blow+2
  leaves it at level 2.
- Cost sentinels: Whirlwind (X) has `cost()` 0 and `x_cost()`; Wound has
  `cost()` 0 and `unplayable()`; an old-format entry with `x_cost: true`
  loads as -1; each new load error (both flags, cost change on X, unplayable
  with effects or `only_attacks_in_hand`, Power with `exhaust`, cost -3)
  refuses the card by name; `sts` card info still reports `cost`,
  `x_cost`, `unplayable` as today.
- Names: `upgrade_name` of `Bash` is `Bash+`, of `Bash+` is `None`, of
  `Wound` is `None`, of `gen:Searing Blow+` is `gen:Searing Blow+2`;
  `base_name("gen:Searing Blow+12")` is `gen:Searing Blow`.
- Gauntlet: `upgradable` of a deck with `gen:Flame Barrier` and
  `gen:Searing Blow+` lists both.

End to end: `gauntlet.py play heuristic --start starter --rewards sim
--rest sim --pack content/packs/act1-ironclad.json` on 6 sequences runs,
and at least one rest site upgrades a `gen:` card (the run's floor rows
show it); golden identical; `series_check` PASS.

## Don't guard

- Levels past 255, or numbers past i16 at levels nobody reaches (load
  check covers reachable levels up to the cap).
- Curses (no Curse type yet).
- Upgrades of cards in the exhaust pile or in play (Armaments reads the
  hand only).
- An upgrade that changes a card's type, target or conditions (a unique
  upgrade: separate entry).

## Build steps

1. **Fixtures and pinning tests.** Copy today's `content/cards.json` and
   `act1-ironclad.json` to test fixtures; write the three step-1 tests.
   Check: they pass on unchanged code. (Card sets is built: the cards
   fixture is taken from the flag-free `cards.json`, without `held_out`
   and `proving`; `engine/tests/data/cards_old_flags.json` is card-sets'
   own fixture, not this one.)
2. **Upgrade expressions and paths.** A pure function: (entry, level) ->
   entry at that level: path lookup, the expression parser, keyword set,
   cost bound, `match_level` resolution. Check: the parser, bound, keyword and
   load-error tests.
3. **Cost sentinels and load checks.** `CardDef`'s cost private behind
   `cost()`, `x_cost()`, `unplayable()`; every reader switched (about ten:
   `state.rs`'s energy check and spend, the heuristic, `agent.rs`, the
   features, the Python card info); the loaders map the old flags to -1 /
   -2 and refuse the new load errors. Check: the cost-sentinel tests;
   golden identical; feature arrays identical; `series_check` heuristic
   bit-identical.
4. **Loaders and the rewrite.** Official and pack loaders accept
   `upgrade` / `max_level` / `match_level` and the `"X+"` link, and expand an
   entry into its id pair. Rewrite `cards.json` and the pack (a one-off
   script, not kept). Check: the step-1 equality tests pass on the
   rewritten files; golden identical; `rules_version()` unchanged.
5. **Levels 2 and up.** `Overrides` gains the level; variants on pack
   cards; `+N` names in `bind` and in the Python helpers (`upgrade_name`,
   `base_name`); Searing Blow written with `max_level: null`. Check: the
   Searing Blow, names and full-slot tests; existing variant tests.
   Stop point: if keying variants on pack cards needs a change to the
   binding's layout or the codec, ask before going on.
6. **Armaments.** `UpgradeFromHand` pick and `UpgradeHand` effect, the
   general-upgrade rule, their feature columns (zero on old content);
   Armaments / Armaments+ in the pack, checked against the wiki and
   sts_lightspeed. Check: the Armaments and Rampage tests; arrays re-pinned
   with every old column equal (as C1-C4). Stop point: if the new columns
   change any old column, stop.
7. **Run layer.** `gauntlet.upgrade` / `upgradable` through `sts`;
   `base_name` in the readers that strip `+`. Check: the gauntlet and
   `base_name` tests; existing `test_gauntlet.py`; the end-to-end run.
8. **Series checks** (long: a `series_speed` job, ~5 min alone but it
   waits for idle cores; plan its thread count as the lane's stall note
   says). `series_check` PASS, `series_speed` at most 10% slower; record
   both in the inventory doc with the new blocked count. Check: the job
   record under `jobs/done/`.

## Build plan

Mode: forks (8 steps, one fork each). Model: Opus 5.5.
Stop points: step 5 (variants on pack cards) and step 6 (feature columns).
Built by the `act1-content` lane worker after M6+M7.

## Amendment 1 (2026-11-10, approved by the owner): a unique upgrade names its successor

Owner, after the build: an entry names its non-trivial upgrade explicitly,
instead of the engine finding it by the name `X+`.

**Behavior.**
- An entry may have `"successor": "<id>"`: the entry with that id (in the
  same file) is this card at level 1. A card with a successor has max
  level 1, and no `upgrade` block.
- The successor's id can be any id. In names the level-1 card is still
  `X+` (records, `bind`, `sts.upgrade_name`, the rest site), and binding
  the successor's own id (`gen:<successor id>`) gives that same card (the
  same slot, level 1), so one card never has two identities.
- A successor entry is only a level of its base: the gauntlet's `--pack`
  offers and `pack_names` skip entries named as a successor (instead of
  skipping ids that end in `+`; the same set for today's pack).
- Load errors, each naming the card: a successor id that names no entry;
  a successor named by two entries; a successor with its own `upgrade`,
  `successor` or `max_level` (no chains: a second unique upgrade is a later
  spec); a card with both `successor` and `upgrade`; a successor with
  `max_level` other than 1 on its base.
- Older files keep loading as now: an entry `X` without `upgrade` or
  `successor`, beside an entry `X+`, is linked by the name. The writer and
  the rewritten files use `successor`: `content/cards.json` (FTL) and the
  act1 pack (True Grit, Armaments).

**Fits with.** Old-format packs: `upgrades_old_pack.rs` unchanged and
passing. The pinning tests (`upgrade_format_matches_old_cards`,
`pack_upgrades_match_old_pack`) pass on the files rewritten with
`successor`. Golden, rules version, feature arrays and `series_check`
unchanged (the definitions are the same; only how an entry points to its
upgrade changes).

**Verification.** First a failing test: an entry `PrA` with `"successor":
"PrA Sharp"` binds `gen:PrA+` to `PrA Sharp`'s definition, and `gen:PrA
Sharp` to the same card id. Then: each load error above refuses the card
by name; `sts.upgrade_name("gen:True Grit")` is still `gen:True Grit+`;
`pack_pools` offers the same 32 base cards; `official_files` canonical.

**Scope.** `engine/src/registry.rs` (parse, `levels`, `pack_level`, the
official layout, the writer), `content/cards.json`,
`content/packs/act1-ironclad.json`, `scripts/gauntlet.py` (`pack_pools`,
`pack_names`), engine and Python tests, `docs/extending.md`.

**Later, not now** (owner, 2026-11-10): branching upgrades (a list of
successors, the rest site choosing among them) extend this field
additively; an upgrade in combat would take the first branch. No level
field on a successor: its level follows from the link.

**Steps.** 1. The failing test. 2. Parse and link `successor` (packs and
the official layout), the load errors. 3. Writer and the two files
rewritten; old-name linking kept for older files. 4. Gauntlet offers;
engine and gauntlet tests; `series_check` (expected identical).
