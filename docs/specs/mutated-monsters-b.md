# Mutated monsters, stage B: pattern modifiers (goal1-yardstick)

Status: closed (2026-11-04, built and in use; 3bab5d0; decisions "Mutated monsters stage B: three monster powers, unblocked Weak on hit, floor-halved split hits"; two-turn read 70ce1d70).

Confirmed under the mandate by the lane worker (2026-11-04, lanes
15483a05). Lane `goal1-yardstick`, first build step and first bench
(`decision/goal1-yardstick`, decisions "Goal-1 lane re-aimed at the
owner's yardstick").

## How it moves goal 1, and how we'll know

Goal 1's number on the owner's yardstick is the net's drop beyond each
modifier's measured difficulty, on boon + bane pairs over official
parents. Stage A covered state patches (HP, Strength, Metallicize,
Ritual, SharpHide, Thorns); there, two-turn search repaired the one
unseen-power cost (`measurement/mutated-monsters@stage-a`). The owner's
other two monster examples, "two half-damage hits" and "Weak on hit with
-20% damage", change how an enemy's attacks land, which the heuristic and
the leaf both read from intents; that is where the product may still
fail (results doc, stage A two-turn reading (3)). We'll know from the
same table as stage A: per modifier, the heuristic's and the two-turn
product's win and HP-lost change from the parent (difficulty), the
one-turn net's drop beyond the heuristic (novelty) and two minus one
(repair), 200 starts, paired by start. A two-turn novelty cost beyond
2 se on a pattern modifier is a goal-1 failure of the product and the
lane's next target; none means the enemies rung holds for patterns too.

## Outcome and non-goals

Outcome: three new official monster-usable powers the bench can put on
any enemy by state patch, and the stage B table played and read.

Non-goals: no official card or monster gets them (golden.txt and the
rules version stay as they are); no training; no generated (pack) power
for monsters (the registry binds generated powers through cards only);
no heuristic pricing of Weak on hit beyond what `attack_damage` gives
(the heuristic's blindness to it is part of what the bench measures, as
SharpHide's was).

## Behaviour

- **`DamageDown`**: while its stacks are > 0, the owner's attack damage
  is multiplied by 4/5 (a `DamageDealt` `Multiply(4, 5)` static, read by
  the data path: added to `GENERIC_STATICS`, so `attack_damage` falls to
  `interpret_attack_damage` when it is in play). Multiplies apply once,
  not per stack (like Weak). Rounded down once at the end, with the other
  multiplies.
- **`WeakOnHit`**: a hook power with a new trigger `OwnerAttackHit`
  (fires on the attacker after each attack hit that made its target lose
  HP, unless the combat is over; `Target::Opponent`/the hit target in the
  context). Its row: `OwnerAttackHit -> Apply Weak 1 per stack` to the
  target. Unblocked hits only (like the game's Envenom): block counters
  it, which is the mechanic the player has to learn. A 3-hit move that
  lands 3 times gives 3 Weak.
- **`SplitHits`**: no hook rows. When a monster holding it (stacks > 0)
  resolves an attack effect (`Damage { amount, hits }` or
  `RolledAttack`), it deals `2 x hits` hits of `amount / 2` (rounded
  down, before Strength; Strength and the multiplies apply per hit as
  usual). One shared helper gives (base, hits) for an attacker, and every
  place that prices a monster attack uses it: `state.rs` `deal` (the
  actual hits), `agent.rs` `intent_damage` and `move_damage`,
  `heuristic.rs` `move_damage`, and the features' intent
  `damage_single` / `hits_single` atoms. So intents show the split move
  and the leaf, the heuristic and the net read it. Player attacks are
  unchanged by it (monster-only, by a guard on `Who::Monster`).
- All three are appended at the end of `Power::ALL` (existing indices,
  codec bytes and `CODEC_VERSION` unchanged), so `sts.power_names()` and
  `mutate_monsters.py`'s ("power", name, amount) patch reach them with no
  script change. `SplitHits` and `DamageDown` go in `MODIFIER_POWERS`
  (the features read them as modifier columns); `WeakOnHit` is a hook
  power (`is_hook_power`), and `OwnerAttackHit` joins the features'
  `TRIGGERS`.
- Bench modifiers in `mutate_monsters.py` `MODS`: one-sided `weakhit1`,
  `dmg0.8`, `split`; the owner's pair `weakhit1-dmg0.8` ("Weak on hit with
  -20% damage"); `split` is itself the owner's trade (more hits, less
  each) and is read as one; stacks `weakhit1-dmg0.8+split` and
  `weakhit1-dmg0.8+thorns2-hp0.9` for the stacking axis. Balance is
  measured, not assumed: a pair far off its parent is retuned after the
  read (as `decision/mutated-pairs-retuned`).

## Fits with

- golden.txt byte-identical, so `registry.rules_version()` unchanged
  (`engine/tests/golden.rs`, existing).
- Codec: existing states encode to the same bytes (existing codec tests;
  `scripts/series_check.py` bit-identical heuristic, contract nets and old
  feature columns on its 4,703 states).
- Old nets keep loading and give the same outputs: the layout contract
  (`stsnet.py` contract load) gains columns, drops none;
  `scripts/tests/test_contract.py` and the pinned
  `scripts/tests/data/lookahead_off_names.json` (updated by name: new
  columns only, every old name kept in order).
- pack-every-atom (`engine/tests/packs.rs`): every official power with
  hooks or statics round-trips through `power_json` / `load_pack`, so the
  new trigger gets both a writer and a parser case.
- `ATTACKED_POWERS`-style fast-path guard for the new trigger (an
  `ATTACK_HIT_POWERS` list with a test, as `engine/tests/replacements.rs:18`
  checks `ATTACKED_POWERS`): official combats don't scan for it.
- Python name lists (`py/tests/test_sts.py` exact `hook_power_names`):
  updated to include `WeakOnHit`.
- Search speed: one-turn and two-turn searches on official content within
  noise of before (no new work unless a holder is in play).

**When in doubt:** prefer the game's existing timing and rounding (per-hit
Strength, multiplies once, round down at the end) over a new rule.

## Scope

May change: `engine/src` (powers, hooks, state, agent, heuristic,
registry trigger parse/write), `engine/tests`, `py/src` (features, names),
`py/tests`, `scripts/analysis/mutate_monsters.py` (MODS and the stale
"Thorns, which the engine lacks" comment), `scripts/tests`, the results
doc, decisions, this spec. Off limits: existing powers' behaviour, the
codec format, golden content, `solvedb` logic (its fingerprint changes by
itself, which is expected), training code, the gauntlet and the product.

## Decisions taken

In `docs/decisions.md`, "Mutated monsters stage B: three monster powers,
unblocked Weak on hit, floor-halved split hits (on the owner's behalf,
2026-11-04)".

## Outside assumptions

None beyond the engine: the effects named are this repo's own rules.

## Verification (tests first)

- `damage_down_multiplies_once`: monster with DamageDown 1 (and 3) hits
  the player for base 10 -> 8; with Weak too -> 10 x 3/4 x 4/5 = 6; with
  Strength 2 -> 9 (adds before multiplies); the fast path and
  `interpret_attack_damage` agree.
- `weak_on_hit_unblocked_only`: monster with WeakOnHit 1 and a 3 x 5
  move, player with 0 block -> Weak 3; with 12 block -> Weak 1 (only the
  third hit loses HP); WeakOnHit 2 doubles the Weak; no hook fires once
  the player dies.
- `split_hits_doubles_and_halves`: an 11 x 1 attack becomes 2 x 5; with
  Strength 2 -> 2 x 7; a 6 x 2 move -> 4 x 3; `intent_damage`,
  `agent::move_damage`, `heuristic::move_damage` and the features' intent
  atoms all report the split shape; a player attack is unchanged.
- `split_hits_with_sharp_hide`: a monster with SplitHits and SharpHide
  still answers each player attack once per hit (SharpHide unchanged).
- pack round-trip for `WeakOnHit`'s row (`packs.rs`).
- End-to-end: `mutate_monsters.py play --starts 5 --seeds 2 --players
  heuristic,one --mods weakhit1,dmg0.8,split,weakhit1-dmg0.8 --out
  <tmp>` runs and `read` prints a row for each modifier (no sign is
  required on 5 starts).

Don't guard: a monster with SplitHits and a 1-damage attack (0 x 2 is
fine); WeakOnHit on the player (no player content gets it).

## Build steps

1. Fits-with baseline on unchanged code: engine tests, `test_contract.py`,
   `test_sts.py`, series_check; all green.
2. `DamageDown` power, static row, `GENERIC_STATICS`; its test. (~25 lines)
3. Trigger `OwnerAttackHit` (hooks, firing in `state.rs` `attack` after
   `take_damage` when HP was lost, fast-path list, registry parse and
   json writer, features `TRIGGERS`), `WeakOnHit` power and row; tests.
4. `SplitHits`: the shared (base, hits) helper used by `deal` and the four
   readers; `MODIFIER_POWERS`; tests.
5. Python names and pinned lists; `mutate_monsters.py` MODS and stacks;
   wheel build and swap under `main-merge` (AGENTS.md gotchas;
   `jobs.py impact sts` recorded); fast suites; series_check bit-identical.
6. **Long run** (queue, pinned): heuristic and one turn 200 x 8 on the
   new modifiers (~20 min at 3 threads), then two turns 200 x 4 (~5 h at 3
   threads), both into `results/mutate/a.json`; read per the outcome
   section; checkpoint `stage-b-table`: every stage B modifier's two-turn
   win change at se <= 0.02 and a verdict recorded.

Build plan: 6 steps, in-session (or forks for 2-4), on Opus. Stop point:
none expected; the trigger's unblocked-only rule is recorded as a
reversible decision.

## Build notes (steps 1-5 built 3bab5d0, lanes 508170de, 2026-11-04)

- Step 6 queued: 0112 (heuristic and one turn, 200 x 8) then 0113 (two
  turns, 200 x 4), both after 0092 since all three append to
  `results/mutate/a.json` (0110 and 0111, first queued pinned to a commit without the build, were cancelled). Fold this spec once 0113 is read.
- Measured against the spec: series_check runs on 3,104 states today (the
  fixed set), not the 4,703 named under Fits with; it passed.
- Verification as built: Weak on hit uses the Guardian's Whirlwind (5 x 4,
  16 block -> Weak 1) and the split shape Twin Slam (8 x 2 -> 4 x 4) in
  place of the spec's 3 x 5 and 6 x 2 moves, which no Act-1 monster has.
  The features' split intent is tested in `test_mutate_monsters.py`.
- The default vocabulary grew, so the pins were re-pinned on purpose
  (decisions line ~581 precedent); old names kept in order.
- Open (review, optional): the lookahead's next1/next2 effect vectors and
  the pattern rows still show unsplit moves; Damage Down isn't seen by the
  heuristic's and the lookahead's damage rates (hand-coded Strength and
  Weak). Search speed on official content was not timed beyond a check
  too short to read; the hot-path changes are a power test in `deal` and
  `attack` and one more generic static to test in `attack_damage`.
