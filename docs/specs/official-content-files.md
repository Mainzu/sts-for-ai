# Official content as files (runtime registry stage 4)

Status: closed (2026-11-06, built and in use; 19e64ce3-4986a40b, Rust tables removed f0e2fb22; decisions "Runtime registry stage 4 spec: official content as compiled-in files"; stage 4 landed 251b05b4).

Stage 4 of `docs/specs/runtime-registry.md`, confirmed under the mandate
by the lane worker of `lane/runtime-registry` (2026-11-06). The owner's
answers are `decision/registry-first`: the files become the source after
this stage, and the Rust tables go once the files are checked equal;
speed budget +10% per stage.

## Outcome

Every official card, power definition and monster lives in
`content/cards.json`, `content/powers.json` and `content/monsters.json`
(the pack format), which the engine embeds at build time and loads on
first use through the same parser as a generated pack; the hand-written
Rust tables are gone, so adding or changing official content is a file
edit, and the rules fingerprint hashes the files.

Non-goals: new content (Act 1 is the next lane, `act1-content`); the
behaviour that is still code stays code, keyed by the official handle
(the `Power` and `CardKind` enums, `MonsterKind` 0-18, move-id
constants, `Power::is_debuff`, the lice's rolls, Lagavulin's sleep,
Hexaghost's Divider and Inferno, The Guardian's Mode Shift); reading
content from disk at run time (the files are compiled in); the state
representation (stage 5); the codec, golden file and rules version.

**How it moves goal 1 and how we'll know.** Goal 1 asks for first-class
custom content; today official content is Rust and generated content is
data, read by two code paths that can drift. After this stage official
content is data read by the pack parser, so every official card is proof
that the parser covers it, Act 1 enters as file edits
(`decision/registry-first`), and a card that can't be written names a
missing building block. We'll know by the lane's measure: 128 official
cards, 30 powers and 18 monsters loaded from the files and checked equal
to the tables (before the tables go), golden identical, series_check
PASS and series_speed within +10%.

## Behavior

- **Files.** `content/cards.json` (`{"version": 1, "cards": [...]}`, 128
  entries in `CardId` order: each `CardKind` then its upgrade, `id` the
  card's name as today, e.g. `Strike`, `Strike+`), `content/powers.json`
  (30 entries in `Power::ALL` order, `id` the variant name; powers with no
  hooks, statics or replacements have empty lists), `content/monsters.json`
  (18 entries for kinds 1-18 in kind order, `id` the game's name as
  `monster_kinds` takes it, e.g. `Jaw Worm`; `None` stays built in). Written by the
  existing serialisers (`card_json`, `power_json`, `monster_json`), one
  entry per line, so a diff shows one card per line.
- **Official-only fields.** A card entry carries `"class"` (`Ironclad`,
  `Silent`, `Colorless`), `"held_out"` and `"proving"` (the pool flags
  `deck_cards`, `class_cards` and `held_out_cards` read). A monster entry may carry `"code": "louse" |
  "lagavulin" | "hexaghost" | "guardian"`: it attaches that monster's
  setup function and permits the effects only code can drive
  (`RolledAttack`, Hexaghost's and The Guardian's moves). A
  generated pack using any of these fields is refused, as today's load checks refuse
  those effects.
- **Load.** On first use (a `OnceLock`, before any def is read), the engine
  parses the three embedded files with the pack parser into `&'static`
  definitions. Card names resolve in two passes (all names first, then
  effects), so a card adding another card finds it. Checks, each a panic
  naming the entry (the files are part of the build, so a bad file is a
  build bug): entry count and order equal to the enums and kinds; ids
  unique; `debuff` equal to `Power::is_debuff(p, 1)`; every load check a
  pack gets.
- **Readers.** `CardId::def`, `CardId::from_name`, `hooks::hooks`,
  `hooks::statics`, `hooks::replacements` and `MonsterKind::def` read the
  loaded definitions for official handles; generated ones read the
  registry as today.
- **Tables removed.** The `CARDS` array and its builders, the per-power
  hook, static and replacement constants and their `match`es, and the
  monster definition table (moves, patterns, start powers) are deleted.
  Kept as code: the handles, move-id constants, setup functions,
  `has_code`, `is_debuff`, and the kind-keyed special code in `state.rs`.
- **Export.** `cargo run -p sts-engine --example export_content` rewrites
  the three files from the loaded definitions (before the tables go: from
  the tables). A test fails when the files differ from what the export
  would write (byte for byte, LF), so hand edits stay in the canonical
  form.
- **Fingerprint.** `solvedb`'s `RULE_FILES` gains the three files
  (`strip_code` applies; JSON has no comments, so it drops whitespace
  outside strings). The fingerprint value changes, as every rules-file
  edit does; `content_tables()` (the codec's name orders) is unchanged.

## Fits with

- Golden games (`engine/tests/golden.rs`) identical; codec bytes for
  official states unchanged (`engine/tests/codec.rs`); rules version
  unchanged (golden.txt untouched).
- Heuristic, contract nets and feature batches bit-identical
  (`scripts/series_check.py` dump/compare, main's `sts` vs this build,
  `--cards` over every card class's cards so all 128 are covered).
- Packs: generated cards, powers and monsters load and play as before
  (`engine/tests/packs.rs`, `monster_packs.rs`, `registry.rs`); generated
  monster kinds still start at 19.
- The round-trip tests (`every_official_card_round_trips`,
  `every_official_power_round_trips`, `official_monsters_round_trip`)
  keep passing: after the switch they compare a pack copy against the
  file-loaded definitions.
- Card name lists (`deck_cards`, `class_cards`, `held_out_cards`,
  `starter_deck`) and Python's name lookups unchanged.
- Fingerprint tests (`solvedb/tests/fingerprint.rs`): the files count as
  rules (a changed file, a new fingerprint); loaded packs still don't.
- Speed: `scripts/series_speed.py` H1 and H2 within +10% (the `OnceLock`
  read per def lookup).
- Pinned snapshots and wheels: nothing reads `content/` at run time.

## When in doubt

Prefer a file that says exactly what the engine does over a smaller
file; prefer keeping a part as code over a file field only the official
files may use (the four `code` names are the exception).

## Scope

May change: `content/` (new), `engine/src/cards.rs`, `powers.rs`,
`hooks.rs`, `monsters.rs` (the tables, the readers), `engine/src/registry.rs`
(the official loader, the `code` field, the serialisers'
output form), `engine/examples/export_content.rs` (new), engine tests
(new `engine/tests/official_files.rs`, the round-trip tests),
`solvedb/src/fingerprint.rs` (`RULE_FILES`) and its test, docs
(`README.md` content section, `docs/specs/runtime-registry.md`,
`docs/decisions.md`, this spec). Interfaces: the pack format gains the
official-only fields (cards' `class`, `held_out`, `proving`; monsters' `code`).

Off limits: codec format and `CODEC_VERSION`, golden.txt and the rules
version, the enums' variants and order, `MonsterKind` numbers, features
and net layouts, encounters, gauntlet and dataset formats, Python's API,
`scripts/` other than tests.

## Decisions taken (also in docs/decisions.md)

- Files compiled in (`include_str!`) and parsed on first use.
  Alternatives: read from a path at run time (edits without a rebuild,
  but every pinned snapshot, wheel and test would need the path; a
  missing file fails at run time); generate Rust from the files in a
  `build.rs` (no run-time cost, but a second reader of the format beside
  the pack parser, which is what goal 1 wants one of). The fallback if
  the speed check fails is to copy the loaded definitions into a plain
  `static` array read without the `OnceLock` check, then `build.rs`.
- Three files, one per content kind, in the pack format. Alternative:
  one official pack (one file is a long diff to read; three keep each
  kind's order check local).
- Code-backed monsters go in the file with a `code` name. Alternative:
  keep them in Rust (the stage would leave five monster tables, and the
  next Act 1 boss would face the same split).
- `is_debuff` stays code (its Strength and Dexterity rule depends on the
  sign); the file's `debuff` is checked against it.

## Outside assumptions

None: everything is inside the engine.

## Verification

Tests first (`engine/tests/official_files.rs` unless named):
- `files_equal_tables` (written in step 2, removed with the tables in
  step 4): every card, power and monster loaded from the files equals the
  table field by field (cards as `same_card`, powers' hooks, statics,
  replacements and debuff, monsters as `official_monsters_round_trip`
  plus setup function and `code`); prints the counts 128, 30, 18.
- `files_are_canonical`: exporting the loaded definitions gives the
  files byte for byte.
- `file_order_checked`: a cards file with two entries swapped, a powers
  file missing one, a monsters file with a wrong id each panic naming the
  entry (the loader's check function called on the text, not the
  embedded file).
- `official_fields_refused_in_packs`: a generated pack card with
  `class`, `held_out` or `proving`, and a pack monster with `code`, are
  each refused, naming the field.
- `fingerprint_tracks_content` (`solvedb/tests/fingerprint.rs`): changing
  a number in a content file's text gives a new fingerprint; whitespace
  doesn't.
End to end: `cargo test` (golden included), `series_check.py` compare
PASS against main's `sts` with `--cards` covering all cards,
`series_speed.py` within +10%.

## Don't guard

Hand-edited files that are valid but non-canonical (the canonical test
catches them); the cost of parsing at first use (milliseconds, once per
process).

## Build steps

1. **Serialise everything.** `card_json` writes the pool fields and
   `monster_json` code-backed monsters with `code` (both only when asked
   for the official form); the parser accepts the official-only fields from the
   official loader only and refuses them in packs; `export_content` writes the three
   files; commit them. Tests: `official_fields_refused_in_packs`, the round-trip
   tests unchanged. Check: `cargo test` green; files written.
2. **Loader beside the tables.** Parse the embedded files on first use
   with the order checks; nothing reads it yet. Tests: `files_equal_tables`,
   `file_order_checked`, `files_are_canonical`. Check: `cargo test` green,
   the counts 128, 30, 18 printed.
3. **Switch the readers.** `def`, `from_name`, `hooks`, `statics`,
   `replacements` read the loaded definitions. Check: `cargo test` green
   (golden identical); release examples copied out and `series_speed.py`
   (main's vs this, 5 runs) within +10%, else the fallback in Decisions
   before going on.
4. **Remove the tables.** Delete the Rust tables; `files_equal_tables`
   goes with them (its job is done; the round-trip and canonical tests
   stay); `RULE_FILES` gains the files; `fingerprint_tracks_content`.
   Check: `cargo test` green in `engine` and `solvedb`.
5. **Series checks.** Wheel built into `target/pyroot`; `series_check.py`
   dump/compare PASS; `series_speed.py` 11 interleaved runs within +10%.
   Minutes, not hours.

Build plan: 5 steps, in-session, on Opus. Stop point: step
3's speed check (the fallback is in Decisions; a fail of both is a park).
