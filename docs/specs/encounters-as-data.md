# Encounters as data (building block E1)

Status: closed (2026-11-08, built and in use; lane act1-content block E1; e7d60d47, inventory 6a940e82; checkpoint e1-encounters passed, fe1bc2e9).

## Outcome

An encounter (its group and how its monsters are rolled per slot) is an
entry of a content file: the 17 official encounters load from a new
`content/encounters.json` and play exactly as today, and a content pack
can add encounters made of official and pack monsters, played by name
(`gen:<id>`) everywhere an encounter name is taken today.

**How it moves the goals.** Goal 1's first-class custom content needs the
fight itself as data: a new monster is only playable today through
`Combat.versus` with a fixed list, never as an encounter the run layer,
the runners and the benches can draw. The generated-enemies batch 1 read
(measurement/gen-enemies@batch1) found the novelty costs sit in the
interaction of a modifier with its encounter, so a generator that composes
encounters needs them as data. For the lane (goal 2's real Act 1) it is the
step between the five pack monsters and the real encounters: the Blue
Slaver encounter is written now, and Gremlin Gang, Red Slaver and the full
Exordium Thugs follow as pack entries once M6 and M7 land. We'll know: the
official encounters roll the same monsters with the same random draws
(a frozen-reference test over many seeds, golden identical, `series_check`
PASS), the Blue Slaver encounter plays from `act1-monsters.json` through
`sts.Combat(deck, "gen:Blue Slaver")` and `sts.run` specs, and
`series_speed` is at most +10%.

**Non-goals.** No official encounter changes (Exordium Thugs keeps its
Cultist-or-Looter second slot; the full one is a pack entry later). `ALL`
(15) and `ADDED` (2) keep their members and order, so group specs,
`encounter_names()`, golden games and bench sets don't move. No pack
encounter in `gauntlet.py`'s pools (a later block, as G1 was for cards).
No Gremlin Gang, Red Slaver or full Exordium Thugs entry yet (they need
Shield Gremlin, M6, and Red Slaver, M7). No net or feature change: the
encounter is not a net input.

## Behavior

- `Encounter` becomes a one-byte handle, `pub struct Encounter(pub u8)`,
  with the 17 official encounters as associated consts of today's names
  (`Encounter::JawWorm`, ..., the `MonsterKind` pattern), so every caller
  compiles unchanged. Official encounters are numbered 0-16 in today's
  enum order; pack encounters take the next numbers in load order for the
  process's life, up to 255.
- `name()`, `group()` and `roll_monsters(rng)` read the encounter's
  definition: official ones from `content/encounters.json` (compiled in, a
  fourth official file parsed by `parse_official`, order checked against
  the consts as cards and monsters are), pack ones from the table.
  `from_name` finds official names and `gen:<id>` of loaded packs.
- File format: `{"encounters": [{"id": "exordium_thugs", "group":
  "hallway", "monsters": [<slot>, ...]}]}`; in a pack the same entries
  under the pack's `encounters` key (version 1 still). A slot is:
  - a monster name (an official game name such as `"Jaw Worm"`, or
    `"gen:<id>"` of a pack monster loaded before or earlier in the same
    pack): one monster;
  - `{"one_of": [[<slot>, ...], [<slot>, ...], ...]}`: draws
    `rng.below(n)` for n options, then expands the chosen list in place;
  - `{"draw": k, "from": [<name>, ...]}`: k monsters without replacement,
    each by `rng.below(remaining)` over the remaining list in order, the
    pick removed (the game's gremlin spawn).
  Slots expand left to right, depth first, which is the order today's code
  draws in (`vec![first, second]` evaluates in order).
- Today's helpers become data: `any_louse` is `{"one_of": [["Red Louse"],
  ["Green Louse"]]}`; Small Slimes is one `one_of` of two pairs; Exordium
  Thugs' first slot is `{"one_of": [[<any louse>], [<medium slime>]]}`.
- Load checks (a pack is refused whole, as today): id unique in the file
  and redefinition rules as for monsters; group one of `hallway`, `elite`,
  `boss`; every monster name known; `one_of` with at least one option;
  `draw` with 1 <= k <= the list's length; the most slots any roll can
  produce (splits included, `slots_needed`) at most `MAX_MONSTERS`; at
  least one monster in every roll. Unknown keys in an entry are an error.
- Python: `sts.Combat(deck, "gen:<id>")` and `sts.run` specs
  take pack encounter names (they already go through `Encounter::from_name`);
  `GameSpec` and the run paths are unchanged. `encounter_names()` stays the
  official 15. New `sts.encounter_group(name)` returns `"hallway"`,
  `"elite"` or `"boss"` for any known name (the gauntlet's later block
  needs it to place pack encounters).
- The pack writer (`monster_json`'s neighbour) gets `encounter_json`, so a
  test can round-trip the official file.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Golden games and the rules version | identical | golden test |
| Official rolls (`roll_monsters`) | same monsters and the same number of draws for every official encounter and seed | new `official_rolls_frozen` (step 1, passes on today's code) |
| `ALL`, `ADDED`, `every()`, `encounter_names()`, group specs | same members and order | existing runner and Python tests; `official_rolls_frozen` checks names and groups |
| Pack loading (cards, powers, monsters) | packs without `encounters` load as today; the content hash is the text's | existing pack tests |
| `CombatState::new_bound`, `new_vs`, `Combat.versus` | unchanged signatures and behaviour | engine suites |
| Two-turn workers and `gauntlet.py --pack` | a pack loaded in the workers makes its encounters playable there too (same `load_pack`) | covered by the existing G1 worker test; no new code |
| Official features and the product net | identical | `series_check` (heuristic and product bit-identical) |
| Speed | `roll_monsters` reads a small tree once per combat | `series_speed` at most +10% |

## When in doubt

Prefer today's draw order and the existing monster-pack rules over a new
rule.

## Scope

May change: `engine/src/monsters.rs` (the handle, the consts, the def
type), `engine/src/registry.rs` (official file, pack key, parser, writer),
`content/encounters.json` (new), `content/packs/act1-monsters.json` (one
encounter entry), `py/src/lib.rs` (`encounter_group`, a name lookup that
sees packs), engine and Python tests, the inventory doc, the
`how/`-facts this changes, `docs/decisions.md`. Off limits: official
monster, card and power files; golden; the net and features;
`scripts/` other than tests; `gauntlet.py`'s pools.

## Decisions taken

- A one-byte handle with associated consts rather than keeping the enum
  and adding a separate pack-encounter type (alternative: an
  `enum Encounter { Official(..), Pack(u8) }`, which every `match` on the
  enum would have to learn; the handle is the pattern `MonsterKind`
  already uses and leaves the ~230 call sites untouched).
- A small slot grammar (`one_of`, `draw`) rather than weighted choices
  (alternative: `{"weights": [...]}`); every Act 1 encounter is uniform,
  and weights can be added as a third node when content needs them.
- The full Exordium Thugs as a later pack entry, not a change to the
  official one (alternative: fix the official encounter, which changes
  the golden games, the rules version and every control file).

## Outside assumptions

- Blue Slaver encounter: one Blue Slaver, a hallway fight (the game's
  "Blue Slaver" in Exordium's strong pool). Gremlin Gang (for the later
  entry): 4 drawn without replacement from Mad, Mad, Sneaky, Sneaky, Fat,
  Fat, Shield, Wizard (`MonsterHelper.spawnGremlins`). Checked in build
  step 1 against sts_lightspeed's encounter tables where they cover it;
  a mismatch is noted in the inventory doc, the game's rule kept.

## Verification

- `official_rolls_frozen` (engine, step 1): a test-only copy of today's
  `roll_monsters` match; for each of the 17 encounters and seeds 0-999,
  the loaded definition's roll gives the same kinds, and the `Rng`'s next
  value afterwards is equal (same number of draws); names and groups
  equal today's.
- `official_encounters_round_trip`: `content/encounters.json` written back
  by `encounter_json` and re-parsed gives equal definitions.
- `pack_encounter_plays`: a pack with a monster and an encounter of it
  plus an official monster loads; `Encounter::from_name("gen:<id>")`
  rolls both; a combat plays to an end with the heuristic.
- `pack_encounter_refusals`: unknown monster, bad group, `draw` k over the
  list, a roll over `MAX_MONSTERS` slots (with a splitting monster), an
  empty `one_of`, an unknown key, a redefinition: each refused with
  nothing loaded.
- `draw_without_replacement`: `{"draw": 4, "from": 8 names}` never repeats
  a list position and, over 4,000 seeds, each position is picked about
  half the time (within 4 se).
- Python `test_packs.py` (or its neighbour): `sts.Combat(starter,
  "gen:Blue Slaver")` after loading `act1-monsters.json`; an `sts.run` spec
  with that name; `encounter_group` for an official, a pack and an
  unknown name (error).
- End to end: golden identical; `series_check` PASS against main;
  `series_speed` main against the build at most +10%.

## Don't guard

Encounters with more than 255 entries in a process; packs that define an
encounter and its monsters in the wrong order (refused as an unknown
monster, the message is enough); weights.

## Build steps

1. Check the outside assumptions; write `official_rolls_frozen` against
   today's enum (passes on unchanged code). Check: it passes.
2. The handle and consts, the def type, `content/encounters.json`, the
   official parse and `encounter_json`; remove the Rust match and helpers.
   Check: engine suites (all but solve) pass, `official_rolls_frozen` and
   the round trip pass, golden identical.
3. The pack `encounters` key with its checks, `from_name` over packs, the
   `draw` node. Check: `pack_encounter_plays`, `pack_encounter_refusals`,
   `draw_without_replacement` pass; existing pack tests pass.
4. Python `encounter_group`, the Blue Slaver encounter in
   `act1-monsters.json`, the Python test; build the wheel; Python suites
   touching packs and runs pass; `series_check` PASS against main.
5. `series_speed` main against the build as a queued job (the 0454
   pattern). Check: at most 10% slower.

Build plan: 5 steps, in-session, on Opus. No stop points expected.
