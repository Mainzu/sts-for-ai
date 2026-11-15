# Fickle enemy, first form (lane `fickle-enemy`, step 1)

Status: closed (2026-11-10, built and read, fail: decisions "Lane fickle-enemy closed"; measurement/fickle-enemy@table).

**How it moves goal 1, and how we'll know.** Goal 1's monsters rung asks
what new kinds of enemy cost the net. Card-played punishments are the
costliest trigger class so far (+1.62 HP per elite fight,
`measurement/gen-enemies@table24`); a punishment whose card type changes
every turn tests whether the net follows a rule that moves. Step 2's
bench read (net minus heuristic minus the stat-only control, per opening
and parent) says it: an opening costing 1.0 HP or more at 2 se is a new
costly row for goal 1's table (lane go), every opening within 1.0 HP is a
fail.

## Outcome

Each official Act 1 elite on the generated-enemies bench can carry a
"fickle" mechanic: during the player's turn it names one card type; each
card of that type the player plays gives it 1 Strength. At the enemy's
turn start the named type moves on in the fixed cycle Attack -> Power ->
Skill -> Attack, and the type that just ended costs it 5% of its max HP
(rounded up) for an Attack or Skill turn, or heals it 5% for a Power
turn. The bench plays the three openings as three modifiers
`FE-Attack`, `FE-Power`, `FE-Skill`.

Non-goals: the random form (a random type each turn: hooks refuse chance
today); a net input column for the new atoms (the layout stays); the
heuristic reading them; retuning amounts.

## Behaviour

- **Heal atom.** `{"Heal": n}`: its user gains n HP, never above max HP
  (dead creatures don't heal). Scaled by stacks like `LoseHp`.
  `Effect::heals` is true for it. Pack cards, hooks and monster moves may
  use it. Its words are in `content/wording.json`. In the net's features
  it has no column (as `ApplyPack`): the 10-29 net doesn't see it.
- **A pack power's hook may apply a pack power** (`Apply` naming one
  loaded before, or anywhere in the same pack, so a cycle of three can
  refer forward). It runs as `ApplyPack` does in a monster move. Binding a
  pack power to a fight (a monster's start power, a move's apply, a card's
  apply, `with_monster_power`) also binds every pack power its hooks
  apply, transitively; more than `POWER_SLOTS` is the usual error.
- **One pass, no chain.** In one run of an owner's hooks, a pack power
  the owner didn't hold when the pass began doesn't fire (otherwise
  Attack -> Power -> Skill would all advance in one turn start, by slot
  order). Official powers are unaffected, so golden is identical.
- **The fickle powers** (`scripts/analysis/mutate_monsters.py`,
  `fickle_pack()`): for each type T in Attack, Power, Skill and each n in
  1..20, a power `FE-<T>-<n>`: a `CardPlayed` by Opponent hook with
  condition `CardType(T)` giving 1 Strength to Me, and an `OwnerTurnStart`
  hook: `LoseHp n` (T Attack or Skill) or `Heal n` (T Power), then
  `RemoveSelf`, then `Apply FE-<next T>-<n>` 1 to Me. Plus `Curiosity`
  (Power cards) and `FE-AttackEnrage` (Attack cards), the plain one-type
  forms, as data in the same pack (unused by the read).
- **The patch** `("fickle", T)`: every living monster gets 1 stack of
  `FE-T-n` with n = ceil(0.05 x its max HP) at the first decision.
  Lagavulin asleep wakes on that HP loss as on any (the game's rule): an
  Attack or Skill opening wakes it at its first turn start; reported per
  parent, not corrected.
- Opening per fight: the read plays every fight with each of the three
  openings (paired), not one opening drawn from the start seed; the
  seeded form is their average (decision below).

## Fits with

- Golden replay identical (`engine/tests/golden.rs`, rules version
  unchanged): official content never applies a pack power from a hook.
- Wording: `engine/tests/wording.rs` names any element without words.
- Existing packs load unchanged; the GE pack (`gen_pack()`) unchanged, so
  the explorer pin (`scripts/tests/test_explore.py`) stays.
- `with_monster_power` tests (`test_mutate_monsters.py`) keep passing.
- Monster-move `ApplyPack` (Red Slaver) unchanged (`monster_packs.rs`).

**When in doubt:** prefer a refused pack over a silently different rule.

## Scope

Engine (`effects.rs`, `bound.rs`, `registry.rs`, `state.rs`), `py/src`
(the features match arm only), `content/wording.json`,
`scripts/analysis/mutate_monsters.py`, their tests. Off limits: the codec,
net layouts, official content, `gen_pack()`'s powers.

## Decisions

- Three fixed-opening modifiers instead of one seeded pick: the measure
  is per opening, and three paired reads of every fight cost 3x a seeded
  one but need no per-opening sample split (decisions entry).
- Per-n powers (n in 1..20) because stacks scale every amount in a hook:
  one power can't hold Strength 1 and LoseHp n at once.

## Verification

- `engine/tests/fickle.rs::heal_atom_heals_up_to_max`: a pack power with
  `OwnerTurnStart: Heal 5` on a monster at max-10 HP gains 5; at max-2
  gains 2.
- `engine/tests/fickle.rs::pack_power_hook_applies_pack_power`: a
  three-power cycle on a monster; after each monster turn start it holds
  exactly the next power (one step per turn, not three), HP changed by
  the ended turn's amount; a hook naming an unknown pack power is refused.
- `test_mutate_monsters.py::test_fickle_cycle`: on Gremlin Nob, `FE-Attack`
  opening: playing Strike gives 1 Strength, Defend none; after the end of
  turn the monster holds `FE-Power-n` and lost n HP (n = ceil(0.05 max)).
- End to end: `mutate_monsters.py play --groups elite --mods
  FE-Attack,FE-Power,FE-Skill --starts 20 --seeds 2 --players
  heuristic,one` finishes and `read-gen` prints the three rows.

## Build steps

1. Engine: Heal atom (parse, scale, heals, run, JSON, element name,
   wording) and its test. Check: `cargo test` green, golden unchanged.
2. Engine: pack hooks apply pack powers (two-pass names, binding closure,
   one-pass rule, effect JSON) and its test. Check: `cargo test` green.
3. Bench: `fickle_pack()`, the `fickle` patch, the three mods, test;
   rebuild `sts`. Check: the Python test and the end-to-end smoke.
4. Step 2 of the lane (long run, queued): the bench read job.
