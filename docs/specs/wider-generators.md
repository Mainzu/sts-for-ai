# Wider generated enemy grid (lane `wider-generators`, step 1)

Status: closed (2026-11-11, built and in use; wide grid and pack; lane closed go 2026-11-13: decisions "Lane wider-generators closed"; step 2b left unrun).

Lane `wider-generators` (charter `kb get lane/wider-generators`; decisions
"Lane wider-generators opened"). Spec by the lane worker, 2026-11-11,
confirmed under the mandate (operating.md, "Specs and builds").

## Why (goal 1)

Goal 1 asks for an AI that plays well on generated enemies and on custom
mechanics. `measurement/genpack-transfer@three-seeds` showed a net trained
from scratch on 18 generated mechanics cuts the zero-shot cost of 6 unseen
pairings of the same 4 triggers and 7 effects by 0.76. A custom mechanic
uses whatever atoms it needs, so the question underneath is whether the
cut holds on a much wider grid, and what a whole trigger or effect never
seen on an enemy costs. This step builds that grid as bench rows and as a
training pack. We'll know it moved goal 1 by step 2's read (the seed-1
generated-pack net on the new rows, held-out cost against pack-net-scratch
seed 1) and step 3's learn (cut 0.4+ at 2 se on the new held-out pairs).

## Outcome and non-goals

Outcome: `mutate_monsters.py play --mods gen-wide` plays the 76 new
mechanics on the official elite starts as the 24 old ones play;
`gen_enemy_pack.py --wide` writes `content/packs/gen-enemies-wide.json`
(the old 18 plus the new training mechanics on the same ten base
monsters); `genpack_cut.py --wide` reads the cut per group.

Non-goals: new feature columns (Heal, BlockAlly and OwnerBloodied have none
in the seed-1 net's vocabulary, so a read of them would measure blindness);
bosses in the pack (`measurement/genpack-reach@bosses` went); new monster
moves or whole generated monsters; engine changes.

## Behaviour

- **The grid (fixed in code before any fight).** Triggers, the monster the
  owner: the old four (TurnStart, TurnEnd, OppCard, AttackLoss) plus
  RoundEnd, Attacked (`OwnerAttacked`, every attack hit on it), AttackHit
  (`OwnerAttackHit`, its attack hit made the player lose HP), OppAttack and
  OppSkill (`CardPlayed` by the opponent with condition `CardType` Attack
  or Skill). Effects: the old seven (Strength to Me, Block, Damage and
  PlainDamage to AllOpponents, Weak, Vulnerable, Frail to AllOpponents)
  plus StrDown and DexDown (Strength or Dexterity -1 to AllOpponents),
  Artifact (to Me), Wound (one Wound into the player's discard pile) and
  Dazed (one Dazed into the draw pile). 9 x 12 = 108 pairs minus the old
  bench's four official pairs and four more an official power's hook holds
  (OppSkill-Strength Enrage, OppAttack-PlainDamage Sharp Hide,
  Attacked-PlainDamage Thorns, AttackHit-Weak WeakOnHit): 100 mechanics,
  the old 24 unchanged (names, powers, stacks) and 76 new.
- **Stacks:** the old rule: Block 4, Damage 3, PlainDamage 3 on the turn
  triggers (TurnStart, TurnEnd, RoundEnd), else 1.
- **Split of the new 76.** Whole trigger held out: every Attacked pair (11).
  Whole effect held out: every other Wound pair (8). Held-out pairs: of the
  remaining 57, those whose sha256 of the name is 0 mod 4. The rest train.
  The old 6 held-out stay held out, the old 18 train. Every held-out
  pair's trigger and effect appear in some training pair.
- **Pack.** `gen_enemy_pack.py --wide`: the old writer's copies (stacks by
  hash in max(1, k // 2) .. 2k, `GP <id>` encounters as one `one_of` over
  the mechanics) over the old 18 plus the 40 new training mechanics, 58.
  The engine holds at most 236 pack monsters (`MonsterKind` is a u8;
  `MONSTER_CAPACITY` in `engine/src/registry.rs`), so 58 x 10 copies don't
  fit: every mechanic rides both elites (Gremlin Nob, Sentry) and one of
  the four single-base hallways (Cultist, Jaw Worm, two Fungi Beasts,
  Looter), dealt in turn in sha256 order; the slime and mixed hallways stay
  official. 174 copies; generated shares 4/18 of hallways (the old pack
  8/22) and 2/5 of elites (as before). The old pack file stays
  byte-identical.
- **Bench powers.** `gen_pack()` writes the 100 powers; the old 24 keep
  their JSON, so the old pack's power entries still equal the bench's.
- **Read.** `genpack_cut.py --wide --pair <base> <genpack>`: pooled novelty
  cost and cut per group (new held-out pairs, whole trigger, whole effect,
  new training, old held-out, old training), the fail-fast line (the
  genpack file's new held-out pooled cost under 1 HP beyond parent) and a
  per-mechanic table of the held-out groups.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| old 24 rows | same names, stacks and power JSON; same play | `test_gen_mechanics_rule` (existing); the one-off replay check against `results/mutate/gen-gp201-tsl1-all24.json` (Verification 2) |
| `gen-enemies-train.json` | byte-identical | `test_file_is_the_writers_output` (existing) |
| `gen-batch1`, `read-gen`, `compare` | unchanged | existing `test_mutate_monsters.py` |
| `genpack_cut.py` without `--wide` | unchanged output | existing use; the old path untouched |

## When in doubt

Prefer the old bench's and old writer's rules over new ones; prefer an
error over a silent drop.

## Scope

May change: `scripts/analysis/mutate_monsters.py` (grid, split, aliases),
`scripts/gen_enemy_pack.py` (`--wide`), `scripts/analysis/genpack_cut.py`
(`--wide`), their tests, the new pack file, a learn config
`configs/widepack40k-s1.json`, this spec, `docs/research/generated-enemies.md`.
Off limits: the engine, official content, feature layout, the old pack
file's bytes, golden data.

## Decisions taken

- Whole held-out trigger Attacked and whole held-out effect Wound: atoms
  whose input columns are trained elsewhere (Flame Barrier's
  `OwnerAttacked` on the player; Sentry's and the slimes' status cards into
  the discard pile) but never on a generated enemy power. Alternatives:
  AttackHit and DexDown, whose columns no content trains (the read would
  measure an untrained column: blindness, already known).
- Died and Bloodied left out: a kill that ends the fight drops Died's
  effect (probe: 0 of 6 seeds differ on Cultist), Bloodied has no column in
  the seed-1 net.

## Outside assumptions

None beyond the engine (hooks on a monster owner fire for these triggers;
probe 2026-11-11 on Cultist, every trigger and effect but Died changed
some play-out).

## Verification

Tests first:
1. `test_wide_grid_rule`: 100 mechanics; the old 24 equal `GEN`; no pair in
   the official set; split sizes 11 / 8 / held-out pairs / train; every
   held-out pair's trigger and effect in some training pair; stable.
2. Old rows replay (a one-off check, the 0885 file lives in the main
   checkout's data): with the 100 powers loaded, 8 elite starts of
   GE-TurnStart-Block, GE-OppCard-Weak and GE-AttackLoss-Damage plus parent,
   heuristic, 8 seeds, equal the 0885 file's heuristic rows (done: 32 of 32);
   `test_wide_mechanics_fire` checks each new trigger and effect changes
   the state or a play-out.
3. `test_wide_pack`: the writer's output equals the file; powers equal the
   bench's; monsters = 3 x training count (174); every encounter loads and plays
   to the end on random actions; shares as the old pack's.
4. `test_wide_cut`: a synthetic pair of files with a known cost per group
   reads back.
End to end: `play --starts 30 --groups elite --seeds 2 --players
heuristic,one --net <seed-1 genpack>@tsl1 --mods gen-wide` runs, and
`genpack_cut.py --wide` prints the groups.

## Build steps

1. Grid and split in `mutate_monsters.py`, `gen-wide` alias; tests 1-2.
2. Wide pack writer and file; test 3.
3. `genpack_cut.py --wide`; test 4; end to end.
4. (Long run, step 2 of the charter, about 3 h each at 3 threads.) Queue the
   two plays (seed-1 genpack net, pack-net-scratch seed 1) on 675 elite
   starts x 4 seeds, the read rule in their notes.

Build plan: 4 steps, in-session, on Opus. No stop
points expected.

## Amendment 1 (charter rev 2, 2026-11-11)

From decisions "After the big-picture review of 2026-11-11".
- **Which content trains each whole held-out atom's column**: see
  Decisions taken above. Attacked's `trigger_OwnerAttacked` row is trained
  by Flame Barrier (player power, `content/packs/act1-ironclad.json`). Wound's
  columns `add_discard` and `added_unplayable` are trained by the status
  cards that Sentry and the slimes add to the discard pile. No generated
  enemy power trains either.
- **Row kinds of the step-3 learn**: `configs/widepack40k-s1.json` sets no
  `row_kinds`, the same as genpack40k-s1, so it gets the default kinds the
  seed-1 generated-pack net was saved with: `triggered`, `threshold`, `held`
  (its `meta.row_kinds`). There are no pattern rows and no lookahead.
- **Step 2b (to build, descriptive, about 1.5 thread-h)**: the seed-1
  generated-pack net @tsl1 on the 6 old held-out rows, first with the
  rows' trigger column zeroed and then with the effect column zeroed,
  against its unablated file (`results/mutate/gen-gp1-tsl1-all24.json`,
  same starts and seeds). The read is how much of the 0.76 cut rides on
  the atom's name. Needs an evaluator option that zeroes named feature
  columns for hook rows. Built next session; nothing queued waits on it.
