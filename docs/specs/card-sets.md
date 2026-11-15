# Card sets outside card definitions

Status: closed (2026-11-09, built and in use; lane act1-content, under the mandate; decisions "Card sets as built (on the owner's behalf, 2026-11-09)"; configs/card-sets.json).

## Outcome

Which cards a training may draw from (its pools) is written in a sets file
outside `content/`, not in the card definitions: `content/cards.json` says
only what a card is and does, and every pool, held-out set and test set is
a named list in `configs/card-sets.json`. Every result, dataset and pin
comes out identical.

**How it moves the goals.** Goal 1 (custom content as data): the official
cards file and a designer's pack get closer to one format (the official-only
fields shrink from `class`, `held_out`, `proving` to `class`), and adding a
card to content can no longer change a training pool without anyone
deciding it (today a new official Ironclad card joins every new dataset's
random decks). Pools become a training decision, made on purpose in one
place. We'll know by the checks: the four sets reproduce today's pools card
for card and in order (a pin test written before the change), golden games
and `rules_version()` unchanged, `GAMES_PIN` / `ARRAYS_PIN` / `TRAIN_PIN`
unchanged, and an old-format `cards.json` (with the flags) still loads.

**Non-goals** (owner, 2026-11-08):
- Changing which cards are in any pool.
- Moving the scripts' own sets into the file: `selfplay.HELD_OUT` /
  `HELD_OUT_ALL` / `TRAIN_POOL` (check 6), `bench_sets.py`, `granting.py`,
  `transfer.POOL_A` / `POOL_B` stay in the scripts. New code may put a set
  in the file; old code isn't moved.
- The `class` field (Ironclad / Silent / Colorless): it is content (the
  card's colour in the game), and stays in the card.
- Sets of pack cards (`gen:` names): the file names official cards only.
- Recording the sets file's hash in dataset or run meta.

## Behavior

### The sets file

`configs/card-sets.json`, built into the engine the way the content files
are (`include_str!`), so the Rust runner, the Rust tests and Python read the
same sets:

```json
{"version": 1,
 "sets": {
   "ironclad": ["Strike", "Defend", "Bash", "Anger", ...],
   "silent":   ["Silent Strike", "Silent Defend", "Neutralize", ...],
   "check9":   ["Go for the Eyes", "FTL", "Metallicize", "Demon Form", "Rage"],
   "proving":  ["Whirlwind", "Accuracy", "Wraith Form", "Caltrops", "Survivor",
                "Burst", "Hologram", "Headbutt", "Rampage", "Protect"]
 }}
```

(The exact names come from today's files; the build writes them by script,
not by hand.)

- A set is a plain list of **base** card names (owner: plain lists, not
  rules). A name brings its `+` card with it when one exists; statuses
  without a `+` (Wound, Slimed, Dazed) bring only themselves.
- A set is always used in the cards' own order (`CardId::all()`, the order
  of `content/cards.json`), whatever order the file lists them in. Random
  draws index into this order, so today's draws stay identical.
- Sets resolve once, on first use, to a list of card ids.
- Load errors, each naming the set and the card, panic on first use (as a
  bad content file does): a name that is no official card; a name ending
  in `+`; a name listed twice in one set; a missing or non-1 `version`.
  A card may be in several sets.
- The file is **not** a rules file: it isn't in the solved DB's
  fingerprint (`solvedb/src/fingerprint.rs`) or in `golden.txt`, so editing
  a pool never invalidates stored solves or the rules version.
- The file is read once per process; a snapshot under `sts-builds/` carries
  the copy from its own commit, built into its wheel.

### The four sets and what reads them

| Set | Today | Read by |
|---|---|---|
| `ironclad` | `deck_cards()`: Ironclad, not status, not held out, not proving (58 ids) | `deck_cards()`, `class_cards(Ironclad)`, `runner::group_specs`, `sts.make_specs` without a pool for Ironclad, `sts.deck_card_names()` |
| `silent` | `class_cards(Silent)` (30 ids) | `class_cards(Silent)`, `sts.make_specs` for Silent, `sts.class_card_names("silent")` |
| `check9` | `held_out_cards()` (10 ids) | `held_out_cards()`, `sts.held_out_card_names()` (and through it dataset meta `held_out_check9`, `bench_sets`, `granting`, `selfplay`) |
| `proving` | cards with `proving: true` (20 ids) | the fuzz test, the amounts test (no script reads it today) |

- `class_cards(class)` returns the set named after the class in lower case,
  or nothing if the file has none (no caller asks for Colorless today; it
  would return Shiv / Shiv+ today and nothing afterwards; this is the one
  visible difference, and no code reaches it).
- New: `card_sets::get(name) -> Option<&'static [CardId]>` and
  `card_sets::names()` in the engine; `sts.card_set(name)` (a list of
  names; an unknown name is a `KeyError` naming the known sets) and
  `sts.card_set_names()` in Python.
- The three old Python helpers stay with the same names and results (owner:
  keep them as the default sets' names); scripts don't change. New code
  calls `sts.card_set`.
- `gauntlet.upgradable` keeps reading `sts.deck_card_names()`, so held-out
  cards stay non-upgradable at the rest site, as today (identical results
  win). C6's step 7 replaces that use with `upgrade_name`.

### Card definitions and the files

- `CardDef` loses `held_out` and `proving`. `OFFICIAL_CARD_FIELDS` becomes
  `["class"]`.
- `content/cards.json` is rewritten without the two fields (by
  `export_content`, so it stays canonical).
- The official loader **accepts and ignores** `held_out` and `proving` (owner):
  an old-format official file (C6's fixture copy, an older checkout) loads
  to the same definitions; the sets file alone decides pools.
- Packs keep refusing `held_out` and `proving` with today's message
  ("field \"held_out\" is for official content only"), and refuse `class`
  as today.
- `official_card_json` writes no pool fields.
- The rules version stays (`golden.txt` unchanged). The solved-DB
  fingerprint changes, as for any edit to `cards.rs`, `registry.rs` or
  `cards.json` (every engine block does this; `db/` stays, decision
  db-kept).

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Engine pools (`deck_cards`, `class_cards`, `held_out_cards`) | Same ids, same order | new `engine/tests/card_sets.rs::pools_pinned` (literal lists, step 1) |
| Python helpers | `deck_card_names`, `class_card_names("silent")`, `held_out_card_names` return the same lists in order | new `py/tests/test_sts.py::test_card_pools_pinned` (step 1) |
| Golden games, rules version | Identical | existing `engine/tests/golden.rs`, `py/tests/golden.py` (its `KNOWN_CARDS` uses `held_out_card_names`) |
| Datasets and cache arrays | `GAMES_PIN`, `ARRAYS_PIN` unchanged | existing `test_no_content_is_bit_identical` |
| Training | `TRAIN_PIN` unchanged | existing `test_train_unchanged` |
| Engine benches and random decks | `group_specs` / `make_specs` draw the same decks | existing `engine/tests/determinism.rs`; new `pools_pinned` covers the pool |
| Bench sets, granting, two-turn round, setups | Same decks | existing `test_bench.py`, `test_granting.py`, `test_two_turn_round.py`, `test_setups.py`, `test_net.py` pool checks |
| Proving content | In no deck pool, not in check9 | existing `proving_cards_in_no_pool` (switched to the `proving` set) |
| Old-format official file | Loads to equal definitions | new `old_flags_load_and_are_ignored` against a fixture copy of today's `cards.json` (step 1) |
| Packs | Still refuse `held_out`, `proving`, `class` | existing `engine/tests/official_files.rs` loop |
| Canonical content file | `export_content` round-trips | existing canonical-file test |
| Nets with `held_out_check9` in meta | Load as before (meta is a name list, untouched) | existing net-load tests |
| Pinned jobs | Unaffected (their snapshot carries its own engine) | `jobs.py impact sts` recorded in each commit |
| C6 (card upgrades) | Its step-1 fixture is taken after this lands, from the file without flags | C6's own tests; note in C6's spec |

## When in doubt

Prefer identical results over a cleaner model of pools.

## Scope

May change: the engine's card and registry code (`CardDef`, the official
loader, `official_card_json`), a new engine module for sets, the runner's
default pool, the Python binding's pool helpers and two new functions,
`content/cards.json` (the two fields dropped), the new
`configs/card-sets.json`, engine and Python tests (the flag-reading tests
switch to sets), a test fixture copy of today's `cards.json`, docs (README's
official-only fields, `docs/extending.md`,
C6's spec note, `docs/decisions.md`).

Off limits: which cards are in any set; the scripts' own sets and every
script under `scripts/` (they keep calling the old helpers); the pack format
(packs keep refusing the fields); `golden.txt` and `golden_proving.txt`;
the codec, feature layout and net inputs; `solvedb/src/fingerprint.rs`'s
file list.

Outside the repo: nothing.

## Decisions taken (provisional, into docs/decisions.md)

- Card pools live in `configs/card-sets.json`, built into the engine, read
  by Rust and Python alike. Alternatives: Python only (the engine's default
  pools change), or each training config listing its own pool.
- A set is a plain list of base names, used in card order; adding content
  never changes a pool. Alternative: rules (class minus other sets).
- The old helpers stay as the default sets' names. Alternative: replace
  every caller with `sts.card_set`.
- The official loader accepts and ignores the old flags. Alternative: check
  them against the sets file.
- Builds before C6.
- The sets file is not part of the rules fingerprint.

## Outside assumptions

None: everything is inside the repo. (`include_str!` across the crate
boundary already works for `content/`, and maturin builds the binding from
the workspace, so `configs/` is reachable the same way. Step 2's build
proves it.)

## Verification

Tests written first (step 1, passing on today's code):
- `engine/tests/card_sets.rs::pools_pinned`: `deck_cards()`,
  `class_cards(Silent)`, `held_out_cards()` and the flag-`proving` cards,
  as names, equal literal lists recorded from today's code (58, 30, 10, 20
  names, in order).
- `py/tests/test_sts.py::test_card_pools_pinned`: the three helpers equal
  the same literal lists.
- `engine/tests/card_sets.rs::old_flags_load_and_are_ignored`: a fixture
  copy of today's `cards.json` loads through the official parser to
  definitions equal, field by field, to the embedded file's (today: the
  same file).

Added with the sets (step 2):
- Each set from `configs/card-sets.json` equals its pinned list.
- Load errors: unknown name, `+` name, duplicate, bad version, each with
  the set and card in the message (parsing a test string, not the file).
- `sts.card_set("check9") == sts.held_out_card_names()`; `sts.card_set("x")`
  raises `KeyError` listing the four names.

End-to-end (last step): the full test suite (`cargo test`, `pytest py/tests
scripts/tests`) passes, with golden, `ARRAYS_PIN`, `GAMES_PIN`, `TRAIN_PIN`
and `rules_version()` unchanged and no pin re-recorded.

## Don't guard

- Two sets overlapping (allowed).
- A set holding a status or a proving card (allowed; a choice for the file).
- Sets for characters that don't exist yet.
- The sets file changing while a process runs (read once).

## Build steps

No long runs.

1. **Pins and fixture.** Record today's four pools as literal lists into
   `engine/tests/card_sets.rs` and `py/tests/test_sts.py`; copy today's
   `content/cards.json` to `engine/tests/data/cards_old_flags.json`; write
   the three step-1 tests. Check: they pass on unchanged code.
2. **Sets file and module.** Write `configs/card-sets.json` from today's
   pools (a one-off script, not kept); a `card_sets` engine module (parse,
   resolve in card order, load errors, `get`, `names`); `sts.card_set`,
   `sts.card_set_names`. Nothing reads the sets yet. Check: step-2 tests;
   each set equals its flag-derived pool.
3. **Switch the readers and drop the flags.** `deck_cards`, `class_cards`,
   `held_out_cards` and the tests that read `def().proving` / `held_out`
   read sets; `CardDef` loses the fields; `OFFICIAL_CARD_FIELDS` is
   `["class"]` with the official loader ignoring the two old keys;
   `official_card_json` drops them; `export_content` rewrites
   `content/cards.json`. Check: step-1 pins; `official_files.rs`; golden
   identical; `rules_version()` unchanged; `cargo test` green.
4. **Python side and docs.** Rebuild the wheel (AGENTS.md swap rule;
   `jobs.py impact sts` first); the three helpers unchanged in name and
   result; README's official-only fields, `docs/extending.md`, a line in
   C6's spec that its fixture is taken from the flag-free file. Check: the
   Python pin test, `test_no_content_is_bit_identical`, `test_train_unchanged`,
   the bench / granting / setups / two-turn tests.
5. **Full suite** (test-runner): everything green, no pin re-recorded;
   decisions recorded; commit each step with `jobs.py impact` in its
   message.

## Build plan

Mode: forks (5 steps, one fork each; steps 4-5 may share one). Model: Opus
5.5. Stop points: none expected; step 3 stops and asks
if dropping the fields needs a change to the pack format or any pinned
number.
