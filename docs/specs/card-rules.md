# Card rules the net can read

Status: closed (2026-11-10, built and in use; owner-led session; 7cd83dc..f899398 on lane act1-content; docs/extending.md "Card rules"; decisions "Card rules the net can read, spec decisions").

As built: `docs/extending.md` "Card rules" (rules, keys, rule rows, the
legacy column) and "Content-file versions" (cards); Act 1 note:
`docs/research/act1-inventory.md` "Card rules for the net".

## Outcome

Every rule a power or card sets on cards is something the net can learn
and the explorer words: Entangled's `forbids`, Corruption's `sets_cost`
and `exhausts_played`, and Clash's play condition. Clash's condition stops
being a Clash-only card field and becomes a general one.

**Why.** The engine enforces these rules (`state.rs` `can_play`,
`cost_of`, `exhausts_played`), but `py/src/features.rs` reads none of
them: the net sees Entangled as a debuff that only removes itself, sees
Skills at their printed cost under Corruption, and never learns that they
exhaust. `forbids` has no words, so the explorer shows Entangled doing
nothing. The card field `only_attacks_in_hand` exists only for Clash
(false on every other card) and is a net column of its own.

**How it moves the goals.** Act 1 (`decision/act1-finish`): Red Slaver
and Corruption act on the net's inputs as they act on the fight. Goal 1:
generated content can use play conditions and card rules, and a net with
the new rows can learn them. Nothing on today's nets changes: the product
net, the headline control and every saved net read byte-identical inputs.

**Non-goals:** new card rules or play conditions beyond the four above
(Clash's is the only play condition); changing what any rule does in a
fight; the generator writing the new fields (a later idea).

## Behavior

### Rule rows (new opt-in row kind `rule`)

A row kind `rule`, appended to `ROW_KINDS` and opt-in like `static`,
`countdown`, `replacement` and `pattern` (`EXTRA_KINDS`: written with
`extra_rows`, or when a net's layout lists it). One row per rule:

| Source | Row "trigger" column | Condition column | Scalar |
|---|---|---|---|
| a power's `forbids` | `Rule(Forbids)` | `CardType(<type>)` | — |
| a power's `sets_cost` | `Rule(SetsCost)` | `CardType(<type>)` | `condition_param` = the cost |
| a power's `exhausts_played` | `Rule(ExhaustsPlayed)` | `CardType(<type>)` | — |
| a card's `playable_if` | `Rule(PlayableIf)` | the condition (`HandAll(<type>)`) | — |

Power rule rows go wherever a power's static rows go today (an entity's
held powers, and the rows a card or intent grants with its `Apply`,
`power_kind_rows`), with the same grant column. A card's `playable_if` row
goes on the card's own rows (grant `own`). The trigger names join the
default trigger vocabulary after the pattern trigger; the cost rides in
the row's `condition_param` (as built: an effect scalar would widen every
card and intent vector, which nets without a saved layout read); `HandAll(Attack|Skill|Power|Status)` join the
condition names. All are new row columns: a net whose layout lacks them
leaves them out (`set_layout`), so older nets are unchanged.

### Clash's play condition

- **Engine:** a new hook condition `HandAll(CardType)`: every card in the
  player's hand is of that type. A card gains `playable_if:
  Option<Condition>` (`CardDef`); `can_play` checks it with the hook
  condition evaluator. `only_attacks_in_hand` leaves `CardDef`.
- **Content format:** a card's `"playable_if": <condition>` (the hook
  condition syntax; Clash: `{"HandAll": "Attack"}`). In a version-2 file,
  `only_attacks_in_hand` is a load error naming `playable_if`; in a
  version-1 file, `only_attacks_in_hand: true` reads as
  `playable_if: {"HandAll": "Attack"}` and `false` as nothing, and
  `playable_if` is a load error. `content/cards.json` (version 2, written
  by `official_files()`) drops the field from every card and gives Clash
  `playable_if`. An unplayable card with `playable_if` is an error, as
  with `only_attacks_in_hand` today.
- **Net columns:** `only_attacks_in_hand` leaves the default card columns.
  When a net's layout names it (the product net, the headline control and
  every net saved before this spec), the encoder writes it as before: 1
  for a card whose `playable_if` is `HandAll(Attack)`, else 0 (a legacy
  read). Other `playable_if` conditions reach only the new rows.

### Wording and the guard

- `content/wording.json` and `registry::element_names()`: `power_rule`
  gains `forbids`; `card_rule` gains `playable_if`; `condition` gains
  `HandAll`. The explorer words all four rules from the file (Entangled,
  Corruption, Clash).
- **Guard test:** the power and card keys the parser accepts are listed
  once in the registry (`POWER_KEYS`, `CARD_KEYS`; a key outside the list
  is a load error). A test fails when a rule key (any key that isn't
  structure: id, effects, hooks, rows and so on, each marked) has no words
  in `wording.json`, or produces no `rule` row (power rules and
  `playable_if`) or column (the card flags with a column today). So the
  next field like `forbids` can't land unread.

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden, rules version | `golden.txt` byte-identical, `rules_version()` unchanged | golden test |
| Today's nets | byte-identical feature arrays in their layouts | `card_rules_pins` (step 1), `series_check` PASS on the product net |
| Default features (no extra rows) | unchanged except the dropped `only_attacks_in_hand` card column | `card_rules_pins` (step 1, its default-layout part re-pinned in step 3 with the column gone) |
| Saved version-1 packs | load and play as today, Clash included | `turn_start_pins` (`v1_pack_replays_unchanged`), new v1 Clash test |
| Fights | Entangled, Corruption, Clash play as today | `act1_packs.rs`, `cards.rs` Clash tests |
| Codec, solved DB keys | encodings unchanged | codec tests |
| Search speed | `series_speed` at most 10% slower | job (step 4) |

## Scope

May change: `engine/src/registry.rs` (keys, parse, versions, official
writer, element names), `engine/src/cards.rs` (`CardDef`),
`engine/src/hooks.rs` (`Condition::HandAll`), `engine/src/state.rs`
(`can_play`, `condition_holds`), `py/src/features.rs` (rule rows, names,
the legacy column), `content/cards.json`, `content/wording.json`,
`scripts/explore.py`, readers of `only_attacks_in_hand` (tests, test
data copies, README), docs.

Off limits: the codec's encodings; `golden.txt`; any existing net's input
(byte-identical in its layout); configs, yardsticks and controls; the
gauntlet and run layer; saved packs and data on disk.

## Decisions taken (owner, 2026-11-10)

- Entangled's and Corruption's rules become something the net learns, as
  one opt-in row kind (owner: Entangled's forbid rule should be something
  the net learns, and Corruption has the same problem).
- `only_attacks_in_hand` leaves the card format for a general play
  condition; existing nets keep the column as a special read for their
  version (owner).

## Verification

Written first (step 1, passing on unchanged code): `card_rules_pins`
(feature arrays, default layout and the product net's layout, on fixed
states holding Entangled, Corruption and Clash in hand and piles).

Then:
- `rule_rows`: with extra rows, Entangled gives one `Rule(Forbids)` row
  with `CardType(Attack)`, Corruption a `Rule(SetsCost)` row with
  `condition_param` 0 and a `Rule(ExhaustsPlayed)` row, both `CardType(Skill)`,
  Clash a `Rule(PlayableIf)` row with `HandAll(Attack)`; without extra
  rows, none.
- `playable_if`: Clash plays only with an all-Attack hand (as today); a
  pack card with `playable_if: {"HandAll": "Skill"}` likewise.
- `card_versions`: version 1 maps `only_attacks_in_hand`; version 2
  refuses it; version 1 refuses `playable_if`.
- `legacy_clash_column`: a layout naming `only_attacks_in_hand` reads 1
  for Clash and 0 elsewhere.
- `rule_keys_read` (the guard).
- End to end: golden identical, `series_check` PASS, `series_speed`
  within 10%, explorer words Entangled, Corruption and Clash.

## Build steps

1. **Pins** on unchanged code: `card_rules_pins`; decisions into
   `docs/decisions.md`. Check: passes.
2. **Rule rows** for the three power rules: the kind, names, scalar,
   rows; `forbids` wording; the key lists and the guard (power side).
   Check: `rule_rows` (power part), `card_rules_pins`, wording, guard.
3. **Clash:** `HandAll`, `playable_if`, versions, official files, the
   card rule row, the legacy column, readers. Check: `playable_if`,
   `card_versions`, `legacy_clash_column`, `rule_rows` (Clash part), the
   guard (card side), golden, `card_rules_pins` (its product-layout part
   unchanged; default-layout part re-pinned without the column),
   `series_check`.
4. **Speed and docs:** `series_speed` job (old: this spec's commit; new:
   step 3's; `bench.exe` and `search_speed.exe` copied out of release
   builds), `docs/extending.md` (rule rows, `playable_if`, versions),
   inventories, the lane fact. Check: `series_speed` within 10%.

## Build plan

4 steps, forks, Opus. No stop point.
