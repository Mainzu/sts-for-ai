# Monster lookahead columns: what each enemy does next, as effects

Status: closed (2026-11-01, read: decisions "Monster lookahead: no gain, stays off"; built 2026-10-31, columns kept off).

## Why (goals 1 and 2, and how we'll know)

Nets see each monster's current intent, but nothing about later moves, and
no kind column. On the 15 trained Act-1 encounters they cope: they read
the kind from max HP, powers and intent, their value isn't fooled before
big hits, and they beat the pattern-aware heuristic hardest on patterned
enemies. Two gaps are left. (1) Goal 1: on held-out cards and unseen
bosses the patterned elites and bosses lose their lead (Lagavulin +0.005,
Sentries -0.008, Hexaghost -0.042, Guardian -0.131), and a net can't read
an unseen monster's pattern from a fingerprint it never trained on. (2) At
one-turn End-turn leaves, random-AI monsters (Jaw Worm, slimes, lice, Nob:
78-100% of leaves) haven't rolled their next move, so the net sees the move
they just used. The heuristic already rolls the engine's own monster AI 4
moves ahead (`damage_rate`). Writing those rolled-forward moves as effects
columns works for any monster with a move distribution, including
generated monsters later (goal 1's custom content), and gives the value
net the information the heuristic has (goal 2).

How we'll know: three lean-recipe nets with the columns (`lean-look-s*`)
against threshold-rows step 5's three nets without them (`lean-thr-s*`),
same configs, seeds and shared round 0, paired on the same fights. Adopt
the columns as the default if held-out elite+boss gains >= 0.045 or
held-out Guardian >= 0.06, with train no worse than -0.015. Inside the MDE
everywhere: the columns stay off by default (spec 9 and Runic Dome want
the same input later), and we record that move patterns aren't the Act-1
bottleneck.

## Outcome and non-goals

Outcome: an encoder option `lookahead` that adds, per monster, the
expected effects of its next and second-next move, its expected damage and
hits per round over the next 4 moves, and a flag saying its shown intent is
stale; off by default, with every existing batch, pin and net unchanged.

Non-goals:
- No kind or id columns (option a in the research doc; no help for goal 1).
- No full move-pattern rules as data (spec 9; touches the fingerprinted
  `monsters.rs`). Spec 9 later only changes where the distribution comes
  from.
- No rows for future moves' hook powers (Sharp Hide etc. in a later move):
  they have no effect-mode dimension, as in today's intent columns; only
  the current intent writes granted rows.
- No change to the heuristic's play, the search, the rules or the solver.
- No new training recipe; the test reuses lean-thr's.

## Behaviour

**Rollout.** For a live, non-escaped monster in `slot`, a new engine
function `agent::lookahead(s, slot) -> Lookahead` rolls the monster's AI
forward 4 moves from its current move history, the same way
`heuristic::damage_rate` does today (state cloned, `moves` history swapped
per branch, `move_distribution` at each step, branches merged by history).
It returns the marginal move distribution at steps 1 and 2 and the 4-step
(damage, hits) rate per round, with the same `move_damage` (Strength,
Weak, before the player's Vulnerable) as `damage_rate`.

What "step 1" means: the first roll after the current history. When the
shown intent is the move the monster uses next, step 1 is the move after
it. When the shown intent is stale (the monster's roll is still pending:
a paused End-turn leaf, or `MonsterRolls` not yet at this slot), step 1 is
the pending roll itself. That one rule closes gap (2). The stale case is
`heuristic::intent_known(s, slot) == false`, moved to `agent.rs` as a
public function (the heuristic calls it there; no logic change).

Known approximation, same as the heuristic's: the rollout swaps only the
move history, so a future change of HP, Strength or mode inside those 4
moves isn't seen. Split and Mode Shift are covered by threshold rows.

**Columns** (monster path, effects and ids modes alike, only when
`lookahead` is on):
- `intent_pending`: 1 if the shown intent is stale, else 0.
- `look_rate_damage`, `look_rate_hits`: the 4-step rate.
- `next1_<effect dim>` and `next2_<effect dim>`: the probability-weighted
  sum of each possible move's effect vector at step 1 and step 2, encoded
  with the same `effects` function as the `intent_*` block. A
  `RolledAttack` in a future move uses the monster's current
  `rolled_damage` (approximation; only one Act-1 move rolls damage).
Dead or escaped monsters get zeros, as today. The columns come right after
the `intent_*` block, so dropping them gives back today's monster vector in
today's order.

**The option.** `sts.Features(..., lookahead=False)`. Off: the full layout
names, the batches and the encoder's work are exactly today's (the
rollout isn't run). On: the full layout gains the columns above.
- `stsnet`: when it builds `Features` for a saved net, it turns
  `lookahead` on if the net's monster columns name any lookahead column, so
  a lookahead net loads and plays anywhere.
- `learn.py`: config key `lookahead` (default false) builds the training
  encoder with it, and it enters the fit's config and the feature-cache
  key (the cache is already keyed by layout). Datasets store raw states,
  so the same datasets serve both arms.

Failure cases: a monster whose `move_distribution` is empty (a bug) gets
zeros in next1/next2 and a debug assertion; probabilities at each step sum
to 1 within 1e-6 (debug assertion).

## Fits with

- **The contract** (decisions "Contract as built"): every saved net's
  batches and outputs stay bit for bit. With `lookahead` off nothing
  changes at all. Existing `test_old_layout_unchanged` and the contract
  batch pins must pass unchanged; new `test_lookahead_off_unchanged` pins
  that `Features()`'s full-layout names and fixed-set batch hashes equal
  today's pins (passes on unchanged code).
- **Rules and solver**: no file in `solvedb`'s `RULE_FILES` changes
  (`agent.rs`, `heuristic.rs`, `py/src/features.rs` are outside), so the
  fingerprint, golden games and the solved DB stay. Check: fingerprint
  string equal to main's; `py/tests/test_sts.py` passes.
- **The heuristic**: moving `intent_known` must not change play. Check:
  the heuristic's tight2 result string (`tight_results.heuristic` in any
  r1 round.json) reproduces exactly on a 400-fight sample, and Rust tests
  pass.
- **Feature pins** (`golden_rows.npz`, `curriculum_pins.json`,
  `TRAIN_PIN`): untouched, because the default is off. A new pin for the
  on-layout is added (`lookahead_rows.npz`, a handful of states).
- **Speed**: off, the encoder on the fixed set stays within 3% of main's
  (best of 5). On, it is measured and reported; budget 25% of encoder time
  (the rollout shares one 4-step pass for next1, next2 and the rate). A
  round's minutes are reported against lean-thr's.
- **Threshold rows**: independent; both may be on. Build on merged main.
- **Data scaling** (`docs/specs/data-scaling.md`) may change the
  experiment default round-0 size. The lookahead test uses whatever
  lean-thr used (today: the night's shared round 0 at 20k per group), so
  the arms stay paired.

## When in doubt

Prefer old nets and default batches bit-identical over a neater layout,
and the heuristic's existing rollout over a new estimate.

## Scope

May change: `engine/src/agent.rs` (`lookahead`, `intent_known` moved in,
Rust tests), `engine/src/heuristic.rs` (only to import `intent_known`),
`py/src/features.rs` (option, columns), `py/src/lib.rs` (the constructor
argument), `scripts/stsnet.py` (set the option from a net's columns),
`scripts/learn.py` (config key), their tests and new pinned data, configs
`configs/lean-look-s{1,101,201}.json`, README features section, results
doc, `docs/decisions.md`.

Interfaces that may change: `Features` gains `lookahead`; new monster
column names (only with it on); new config key `lookahead`.

Off limits: the 8 rule files (`state`, `cards`, `monsters`, `powers`,
`hooks`, `effects`, `chance`, `character`), the solver and `solvedb`, the
codec, `stsnet`'s model architecture, `save`/`load`'s schema version,
existing nets, the job queue, existing pins.

Outside the repo: none.

## Decisions taken

1. Lookahead columns from the engine's own rollout, not kind ids and not
   spec 9 now (research doc options a / c).
2. Off by default behind an encoder option, not always on. It keeps every
   pin and every running or queued experiment (data scaling, lean-thr)
   unchanged; adopting it later is a default flip plus a re-pin.
3. Step 1 = first roll after the current history, plus an
   `intent_pending` flag, rather than replacing stale `intent_*` columns
   (which would change today's columns' meaning).

## Outside assumptions

- Training data stores raw states, re-encoded at fit time (confirmed for
  threshold-rows step 5, decisions "Threshold rows step 5"). Checked again
  in step 4: a lean-look r1 fit reads the same dataset ids as lean-thr r1.
- `move_distribution` from a swapped history is the AI's real next-move
  distribution for history-only AIs (all Act-1 random AIs). Checked in
  step 1's Jaw Worm test against sampled rolls (2,000 rolls, each move's
  share within 3 percentage points).

## Verification

Tests first (step 1):
- Rust `lookahead_rate_matches_damage_rate`: for Cultist, Jaw Worm, Slime
  Boss, Lagavulin, Gremlin Nob and Sentry starts, `lookahead`'s rate equals
  `damage_rate` within 1e-5. Fails before (no function).
- Python `test_lookahead_columns` (with `lookahead=True`): Cultist at the
  start (intent Incantation) has next1 = next2 = Dark Strike's effects
  (`damage_single` 6, `hits_single` 1), `intent_pending` 0. Slime Boss
  with intent Preparing has next1 = Slam (`damage_single` 35). A Jaw Worm
  state paused at an End-turn monster roll has `intent_pending` 1 and next1
  equal to `move_distribution`'s mix. A dead monster has zeros.
- Python `test_lookahead_off_unchanged` (above; passes before).
- Python `test_lookahead_net_roundtrip`: a tiny net trained with the
  option saves lookahead columns and reloads with them on; scores equal.
- Rust/Python: Jaw Worm sampled-roll check (outside assumption).

End to end: the three `lean-look-s*` jobs finish with r1 and r2
round.json; the measurement below.

MDE (3 seeds per arm, paired on shared round 0, seed sd as in the
research doc): overall ~0.015, hallway ~0.010, elite ~0.043, boss ~0.05,
per boss ~0.06. The data-scaling run measures seed sd with fresh round
0s; this test shares round 0 across arms, so the shared-round-0 sd
applies.

Measurement (step 6), against `lean-thr-s*` r2: tight2 per half x fight
type; `tight_bosses` per boss and half (Hexaghost and Guardian zero-shot);
named in advance: held-out Lagavulin, Sentries, Guardian. Rerun
`scripts/analysis/pattern_value_error.py` on the best lean-look net; one
ladder test of the best lean-look r2 net against the champion.

## Don't guard

Monsters with more than 2 alive-move branches per step beyond Act 1's;
probabilities that don't sum to 1 in release builds; a lookahead net
loaded by code built before this spec.

## Build steps

1. **Tests first.** The tests above. Check: the off-unchanged test passes
   on unchanged code; the rest fail. ~0 lines outside tests.
2. **Engine.** `agent::lookahead`, `intent_known` moved. Check: Rust tests
   pass (rate test included), fingerprint unchanged, golden games pass,
   heuristic tight2 sample reproduces. ~50 lines.
3. **Encoder.** The `lookahead` option, columns, skip when off. Check:
   step 1's Python tests pass except the roundtrip; contract tests and
   pins pass unchanged; off-speed within 3%; on-speed reported. ~80 lines
   in `features.rs`, a few in `lib.rs`. Rebuild main's `sts` in a queue gap
   or with the rename-aside trick (AGENTS.md).
4. **Python wiring.** `stsnet` sets the option from a net's columns;
   `learn.py` key; configs `lean-look-s*` = `lean-thr-s*` plus
   `"lookahead": true`. Check: roundtrip test passes; `test_setups` and
   `test_net` fast tests pass. ~20 lines.
5. **Long run (job queue, ~3 x 50 min, 6 threads; ~15-17 thread-hours):**
   `learn.py --config configs/lean-look-s*.json --round0
   2026-10-27-score+branch-s0-r0-bd9a1c3`. Needs: 1-4 and lean-thr done.
6. **Measure (after 5).** As above, into
   `docs/research/learned-play-results.md` "Monster lookahead"; adopt or
   keep off by the decision rule, recorded in `docs/decisions.md`.

Build plan: 6 steps, forks (steps 2-4), on Opus. Stop
point: step 6's adopt decision (the manager decides under the Away rules).
