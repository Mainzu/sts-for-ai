# Ascension in combat (target A20)

Status: built (2026-11-14, on main; left: the bridge's first run above A0, and the gauntlet's reward choosers still project rests at 80 max HP; kb how/ascension).

Research: `docs/research/ascension-act1-2026-11-14.md`: every read of
`AbstractDungeon.ascensionLevel` in the Act 1 monster classes and the shared
combat classes of the installed jar, with A0 and ascended values, class,
method and offset; a skeptic per group re-read them (97 monster reads and the
shared ones all confirmed; two misses added below).

## Outcome

A combat takes an ascension level (default 0). At A20 every Act 1 monster,
elite and boss acts as the game's class does at A20; A0 is byte-for-byte
today's engine (golden unchanged, no rules-version change). The real-game
bridge passes the game's level; the gauntlet and trial fights can be given
one. The gauntlet's headline setting stays A0.

**Scope (owner, 2026-11-14):** A20 is the target. Every game check is a
threshold (`ascensionLevel >= N`), so the engine keeps the level as a
number with rows keyed by a minimum level, which costs nothing extra;
only A0 and A20 are tested and checked. Run-start effects are applied for
A20 only.

**Non-goals:** run-layer ascension (map elites A1, act heal A5, boss gold
A13, shop prices A16, the A20 double boss, Note for Yourself); Acts 2-3
monsters; the Looter's stolen gold (no gold in combat).

## 1. The level on the combat

`CombatState.ascension: u8`, set once where every constructor ends
(`new_with_turn1`); 0 for every existing caller. It is part of the state
(two fights at different levels differ). The codec writes it only when
nonzero, as an appended trailer, so every existing encoding stays
byte-identical.

## 2. Monster numbers by level, as data

Each monster row in `content/monsters.json` and
`content/packs/act1-monsters.json` gains `"ascension": [{"from": N, ...}]`:
rows that override, from level N up, the fields the research names: `hp`,
move effects (by move and effect index), `start_powers`, `start_block`,
`pattern` rows, `split`, and rolled ranges. Rows apply in order of `from`,
so A20 takes all of them. The loader resolves one monster definition per
(kind, level) on first use and caches it; `Monster::def()` reads the one
for the state's level. A pack monster gets the same field.

Code that holds an ascension-dependent number moves to data:
- the lice's bite and Curl Up rolls (`monsters.rs` `louse::setup`): a
  rolled-range field (bite 5-7 -> 6-8 at A2; Curl Up 3-7 -> 4-8 at A7,
  9-12 at A17);
- The Guardian's Close Up in `threshold.rs` (`GUARDIAN_SHIFT`, Sharp Hide 3,
  4 at A19): read the resolved definition's move;
- The Guardian's Mode Shift threshold (30, 35 at A9, 40 at A19; also HP
  240 -> 250 at A9): `guardian::THRESHOLD` in `monsters.rs` duplicates the
  JSON start power; one source, the data.

A test reads the research table and checks every A20 value of every Act 1
monster against the resolved definition, so a miss is named.

## 3. Run-start effects for a fight started from scratch (A20)

The bridge reads these from the game; only fights the engine builds itself
need them (gauntlet, trial fights, benches):
- potion slots 2 instead of 3 (A11): a combat-level cap the engine applies
  from the level;
- the deck gets Ascender's Bane (A10): the deck builders add it when given
  an ascension of 10 or more;
- starting HP and max HP: A14 lowers max HP by the character's loss
  (Ironclad 5: 80 -> 75), then A6 starts at round(0.9 x max HP) (Ironclad
  A20: 68); the HP defaults use them.

## 4. Python

`Combat(..., ascension=0)`, `Combat.versus`, `Combat.from_view(...,
ascension)` (the bridge passes the game's level), the bench and ladder
fight spec key `"ascension"`, and `gauntlet.py --ascension N` (default 0;
trial fights for card picks face the same level).

## Verification

- A0: golden unchanged; every existing test passes unchanged.
- A20: the research-table test above for every Act 1 monster; one fight per
  elite and boss checked move by move against the jar's A20 AI (Nob's
  Anger, Lagavulin, Sentries, Hexaghost, Slime Boss, The Guardian).
- Codec: an A20 state round-trips; an A0 state's bytes are unchanged.

## As built

- **Rows.** `"ascension": [{"from": N, <field>: <change>}]` on a monster
  entry, official or pack. A change to an object changes it field by field
  (a one-key object naming another variant replaces it: a pattern row's
  `then`), a change to a list given as an object changes its items by index
  (`"moves": {"2": {"effects": {"0": {"Damage": {"amount": 8}}}}}`), anything
  else replaces (a whole `pattern`, Fat Gremlin's three effects). The fields:
  `hp`, `start_block`, `start_powers`, `rolled_attack`, `rolled_powers`,
  `moves`, `pattern`. `split` and the moves count can't change by level (a
  state's move ids and split slots hold at every level): a load error.
- **Resolved at load**, not on first use: one definition per row (per
  distinct `from`), so a bad row is a load error; `MonsterKind::def_at(level)`
  takes the last row at or below the level, `Monster::def()` reads the
  monster's own `ascension` (every monster holds its combat's).
- **Rolls as data.** `rolled_attack: [min, max]` (`RolledAttack`'s damage)
  and `rolled_powers: [{"power", "amount": [min, max]}]` (official powers),
  rolled in that order at the start of combat (`Monster::roll`). The lice
  keep `"code": "louse"` for their worded behaviour; their setup code is gone.
- **The level** is `monsters::Ascension(u8)`: it hashes to nothing at 0, so
  every A0 state hashes, encodes (codec section 18 only above 0) and prints
  as before. The move caches key on it.
- **Run start.** `Character::run_start_hp(level)`; Python `sts.run_start(character,
  ascension)` gives HP, max HP, potion slots and `deck_adds` (Ascender's Bane
  from A10). A fight at A10 or more loads `content/packs/act1-colorless.json`
  in its process, so a deck naming `gen:Ascender's Bane` binds in any worker.
- **Python.** `Combat(..., ascension=0)`, `Combat.versus(..., ascension=0)`,
  `Combat.ascension`, `Combat.from_view(view, seed, group, ascension=None)`
  (default: the view's `ascension`, written by `view()` only above 0; the
  bridge's observed view carries the game's level), the `run` spec key
  `"ascension"` (bench and ladder fights through `bench.run_specs`, two-turn
  fights through `depth_paired`), `gauntlet.py play --ascension N`
  (setting absent at 0; every fight and trial fight at N; the sequences
  start at the level's HP and max HP with its deck adds).
- **Checks.** `engine/tests/ascension.rs`: the research table at A20 as a
  table in the test (one row per research row, the Looter's gold left out),
  one fight per elite and boss move by move, the lice rolls, the run start,
  potion slots and the codec; A0 is `golden.rs` (unchanged).
- **Left as found (A0, separate from ascension):** the research's A0
  mismatches (Red Slaver's post-Entangle roll 50 for the game's 55, Gremlin
  Wizard's HP 23-25 for 21-25, the Acid Slimes' Tackle-row chance 0.5 for
  0.4) stay; the A17 rows build on the engine's A0 rows.
