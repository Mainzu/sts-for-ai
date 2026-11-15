# Generated enemies bench, steps 1-2 (lane `generated-enemies-bench`)

Status: closed (2026-11-07, built and in use; steps 1-2 in 6e0fbd09; bench in use; decisions "Lane generated-enemies-bench closed (2026-11-07)", fact measurement/gen-enemies@table24).

Lane `generated-enemies-bench` (charter `kb get lane/generated-enemies-bench`;
decisions "Lane generated-enemies-bench opened"). Spec by the lane worker,
2026-11-07, confirmed under the mandate (operating.md, "Specs and builds").

## Why (goal 1)

Goal 1 is an AI that plays well on generated content, enemies included.
Every enemy novelty measured so far was an official power patched onto an
official monster (Strength, Ritual, Metallicize, SharpHide, Thorns,
WeakOnHit, ...): mechanics the net has seen on some monster. Block M5 made
a mechanic built from atoms (a power with a trigger and an effect) possible
as data on a pack monster. This spec lets the mutate bench put such a power
on the official elites it already replays, and plays the first 8 of 24
mechanics, each read beside a stat-only control about as hard. We'll know
it moved goal 1 by the table: per mechanic the net's drop beyond the
heuristic's minus the control's (`yardstick/novelty-read`), its se over
mechanics, and the charter's fail-fast rule (every first-batch cost within
2 se of zero: atoms the net knows cost it nothing zero-shot, the bench
waits for new atoms).

## Outcome and non-goals

Outcome: `mutate_monsters.py play --mods <gen mechanics and controls>`
plays official elite fights whose monsters carry a pack power, by the
heuristic and the 10-29 net one turn deep `@hpb0.01@tsl1`, and `read-gen`
gives the per-mechanic table.

Non-goals: pack copies of official monsters (the official elites keep
their code-defined moves; a pack power is added at the first decision);
moves that apply pack powers (M5b); hallway fights (the bench's starts are
elites and bosses; elites only here, where every player wins about 0.99
and HP lost carries the read); two turns deep; the adapted column (step 4
of the charter); the codec (states with pack content still don't encode).

## Behaviour

- **A pack power on a live combat's monster.** `Combat.with_monster_power(slot,
  power, n)` accepts a loaded pack power's id when `power` is not an
  official power name. The copy's binding gains the power after the ones
  already bound (`registry::bind_power`, shared with `bind_monsters`: a power
  already bound keeps its slot, a new one takes the next free slot; more
  than `POWER_SLOTS` (24) is a `ValueError`), and monster `slot` gets `n` stacks of it. An
  unknown name stays a `ValueError`. Official names behave as today.
- **`Combat.with_seed(seed)`**: a copy whose RNG is `Rng::new(seed)`, the
  same RNG `Combat.decode(bytes, seed)` gives, so a state replayed through
  `with_seed` plays exactly as through `decode`.
- **Mechanics (the rule, fixed in code before any fight).** Triggers (owner
  the monster): `OwnerTurnStart`, `OwnerTurnEnd`, `CardPlayed {by: Opponent}`,
  `OwnerLostHp {from: Attack}`. Effects: Strength to Me, Block, Damage to
  AllOpponents (one hit, scaled by the monster's Strength and Weak), PlainDamage
  to AllOpponents, Weak, Vulnerable, Frail to AllOpponents. The 28 pairs minus
  the four pairs official training monsters hold (`gen_content.OFFICIAL_TRAIN_PAIRS`:
  turn end -> Strength Ritual, turn end -> Block Metallicize, attack HP loss
  -> Block Curl Up, opponent's card -> Strength Enrage) are the 24 mechanics.
  Each is a pack power `GE-<trigger>-<effect>` with one hook, condition
  Always, the effect at 1 per stack; the bench gives every living monster
  `k` stacks: `k = 1` on the per-card and per-hit triggers (they fire several
  times a turn) and on the debuffs and Strength; on the turn triggers Block 4,
  Damage 3, PlainDamage 3. The first batch is 2 mechanics per trigger, the
  first two of each trigger's list ordered by sha256 of the name.
- **Controls (stat-only ladder).** `c-hp0.8`, `c-hp1.25`, `c-hp1.5`,
  `c-hp2`, `c-str1`, `c-str2`, `c-str3`, `c-hp1.25-str1`, `c-hp1.5-str2`,
  `c-hp2-str3`, plus the parent: existing patch kinds (HP scale, Strength).
  Ladder order (the tie order, "smaller change" first): parent, c-hp0.8,
  c-hp1.25, c-str1, c-hp1.5, c-str2, c-hp1.25-str1, c-hp2, c-str3,
  c-hp1.5-str2, c-hp2-str3 (`LADDER` in code).
  A mechanic's control is the ladder entry (parent included) whose
  heuristic mean HP lost over the same starts and seeds is nearest the
  mechanic's (ties: the smaller change), chosen by the read from the
  heuristic only, so the net's games never pick the control. A mechanic
  harder or easier for the heuristic than every entry by more than 2 HP is
  marked "outside the ladder" and read against the nearest end.
- **Bench play.** Variants become `Combat` objects instead of bytes: the
  official patches as today (encode, patch, decode), then pack patches with
  `with_monster_power` on every living monster; each seed's play-out is
  `variant.with_seed(s)`. Parent and official-patch results stay
  bit-identical to the current code. The pack powers are loaded with
  `sts.load_content` (JSON text built from the rule) whenever a `gen`
  mechanic is named; the file's settings record the pack's hash.
- **`read-gen <file>`** (elite rows): per mechanic, the heuristic's and the
  net's wins and mean HP lost (a loss costs the whole entry HP), the chosen
  control, and the novelty cost `(net - heur)_mech - (net - heur)_control`
  in HP lost, with its se from per-start differences (seeds averaged in a
  start, starts the unit). Then the table's mean and se over mechanics
  (the mechanic as the sample unit), the count of costs beyond 2 se, and
  the fail-fast verdict. Also printed per elite encounter.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| `bind_monsters` (pack monsters' start powers) | same slots and errors | `engine/tests/monster_powers.rs` (7 tests) |
| `with_monster_power` official names | unchanged | `scripts/tests/test_mutate_monsters.py` existing; new official-name case |
| mutate bench official mods and parent | bit-identical results | new test: a 2-start, 2-seed play of parent + `str1` + `sharp2` equals the bytes path |
| `decode(b, seed)` | unchanged | new test: `decode(b).with_seed(s)` plays as `decode(b, s)` |
| features (effects mode) | pack powers on monsters encode as rows | new test: the 10-29 net plays a fight with a `GE-` power without error, and its leaf differs from the parent's |
| codec | refuses pack content | existing `engine/tests/codec.rs` |
| golden, rules version | unchanged | `cargo test` golden |

## When in doubt

Prefer the bench's existing paths and the binding's existing checks over
new mechanisms; prefer an error over a silent drop.

## Scope

May change: `engine/src/registry.rs` (bind_power, pack power lookup),
`py/src/lib.rs` (`with_monster_power`, `with_seed`), their tests
(`engine/tests/monster_powers.rs`, `scripts/tests/test_mutate_monsters.py`),
`scripts/analysis/mutate_monsters.py`, this spec, the lane's results doc
`docs/research/generated-enemies.md`.

Off limits: official content (`content/*.json`), golden data, the rules
version, the codec format, feature layout, `SLOTS`, other benches'
outputs.

## Decisions taken

- Pack powers on official monsters in a live combat, not pack copies of
  the official elites (alternatives: copy Gremlin Nob, Lagavulin and the
  Sentries into a pack, which needs their sleep, Enrage and Artifact as data
  and a check that each copy plays as the code; or new pack monsters only,
  which leaves the bench's starts and its known parents). The charter's
  "official parent's HP and moves with one pack power" is met exactly.
- The 24 mechanics are the full grid of non-official pairs over 4 triggers
  and 7 effects (alternatives: sampling from `gen_content`'s generator,
  which is player-side, with Draw and Energy; or a hand pick). The grid is
  the rule fixed before any fight.
- Controls chosen by the heuristic's HP lost from a fixed ladder, not
  retuned after reading (the stage-A retune is what rule (a) warns about).

## Outside assumptions

None beyond the engine: hooks run for a monster owner as for the player
(M5's Angry test); `AllOpponents` from a monster is the player (checked by
a new test per effect kind).

## Verification

Tests first:
1. `bind_power_reuses_and_fills` (Rust): binding a power already bound keeps
   its slot; a 25th distinct power (past `POWER_SLOTS`) errors.
2. `test_with_monster_power_pack` (Python): on `Combat(starter, "cultist")`
   at its first decision, `GE-OwnerTurnStart-PlainDamage` with 3 stacks on
   slot 0: after ending the turn the player has lost 3 HP more than the
   parent's play-out on the same seed; Block on `CardPlayed(Opponent)` and
   Strength on `OwnerLostHp(Attack)` reach the monster after a Strike; Weak on
   `CardPlayed(Opponent)` puts Weak on the player after a card.
3. `test_with_seed_matches_decode`: same results from `play_on` on both.
4. `test_bench_bytes_path_identical`: parent + `str1` + `sharp2`, 2 starts
   2 seeds, heuristic: equal to the rows from the bytes code (golden rows
   computed on the unchanged code in step 1).
5. `test_gen_mechanics_rule`: 24 names, no official pair, 2 per trigger in
   the first batch, stable across runs.
End to end: `play --starts 30 --groups elite --seeds 2 --players heuristic,one
--net <10-29>@tsl1 --mods <batch 1 and the ladder>` runs, and `read-gen`
prints the table.

## Don't guard

Pack powers on bosses (the bench can name them, nothing breaks); more than
one pack power per monster (rule gives one).

## Build steps

1. Engine and Python bridge: `bind_power`, `with_monster_power` for pack
   ids, `with_seed`; tests 1-3. Check: `cargo test --release` (golden
   identical), the new Python tests on a dev build.
2. Bench: mechanics rule, ladder, Combat-object variants; tests 4-5 (test 4's
   rows recorded from the unchanged code first). Check: those pass and the
   end-to-end play runs.
3. `read-gen`. Check: it prints the table on the end-to-end file; a
   synthetic file with a known cost reads it back.
4. (Long run, about 100 min.) Queue batch 1: `play --starts 1000 --groups
   elite --seeds 16 --players heuristic,one --net <10-29>@tsl1 --mods
   <batch 1, ladder>` with the predictions written first into the results
   doc.

Build plan: 4 steps, in-session, on Opus. No stop
points expected.
