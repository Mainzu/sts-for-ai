# Threshold rows and held-card rows: effects features that see Mode Shift and Burn

Status: closed (2026-10-30, built and in use; rows in the default layout; read: decisions "Threshold rows: no transfer detected, layout stays").

## Why (goal 1, and how we'll know)

Goal 1 is play on content the nets never trained on. The clearest failure
so far is The Guardian on held-out cards: -0.131 lead (results doc "Boss
lead per boss"). Its mechanic, Mode Shift (once it has lost 30 HP it gains
20 block and its next move applies Sharp Hide), is invisible to effects
features. `ModeShift` is neither a modifier nor a hook power, so the encoder
drops it. Burn's turn-end damage (Hexaghost) is invisible too, because a
card's `turn_end` effects are not encoded.

A ModeShift column would only help a net that has trained on The Guardian.
The prior-art scan (`docs/research/unseen-mechanics.md`) found no method that
handles a new primitive zero-shot. Content seen in training only transfers
if it shares an encoding with the new content. So this spec writes the
mechanic as a **general primitive that content in the training set already
uses**: "when this monster has lost N more HP, these effects happen"
(a threshold row). The large slimes' split at half HP is that primitive, and
slimes (Acid/Spike Slime L, Slime Boss) are in every training pool. A net
that learns from slimes what a threshold row means can read The Guardian's
row without having trained on it.

How we'll know: nets trained on today's training encounters (no Guardian)
with the new features, compared paired against the same recipe without
them, on `tight_bosses` held-out Guardian cells. The baseline is -0.131.
With 3 seeds per arm, the minimum detectable effect on one boss's cells is
about 2.8 x 0.025 x sqrt(2/3) = 0.06. A gain of 0.06 or more on held-out
Guardian, with hallway, elite and train results within training luck, says
that shared primitives transfer. That is goal 1's claim and the case for
writing generated content in primitives. A flat result says a primitive the
net has seen in other content is not enough, which is also worth knowing
before the generated-cards work.

Burn has no training-pool twin (no training card deals damage while held at
turn end), so its row is expected to do nothing zero-shot. It's included
because it costs little, and it gives the coverage and generated-cards work
(Next 6) a primitive to generate.

## Outcome and non-goals

Outcome: effects-mode features describe (a) a monster's HP threshold (Mode
Shift and the slimes' split) as rows of a new row kind `threshold`, and (b)
a card's held-at-turn-end effects (Burn) as rows of a new row kind `held`
plus a new effect scalar. Every existing net encodes and scores exactly as
before.

Non-goals:
- No rules change. Combat behaviour, the solver, the codec, the solved
  database and its fingerprint stay as they are. The threshold is described
  by a read-only accessor; the rules keep their own code.
- Lagavulin's wake-on-hit is not encoded as a threshold. Losing Metallicize
  and being stunned have no effect primitive. Noted as a follow-up.
- No ids-mode change (ids mode already has a `power_ModeShift` column and no
  rows).
- The threshold's after-effects (the threshold rising by 10, Twin Slam
  returning to Offensive) are not encoded. The post-shift intents already
  encode Close Up's Sharp Hide through granted rows.
- No new training recipe. The measurement reuses the lean-loop recipe.

## Behavior

**Threshold rows (row kind `threshold`).** A new engine accessor,
`threshold::threshold(state, slot) -> Option<Threshold>` (engine/src/threshold.rs; built there, not in `monsters.rs`, because the rules fingerprint hashes `monsters.rs`), returns
`{ hp_to_go: i16, effects: &'static [Effect] }` for a live monster whose
behaviour switches after losing HP:
- The Guardian with `ModeShift` > 0: `hp_to_go` = ModeShift stacks; effects
  = `Block(DEFENSIVE_BLOCK)` followed by Close Up's move effects (Apply
  SharpHide 3 to itself).
- A monster with a `split_move`, alive, whose intent isn't already the split
  move and with 2*hp > max_hp: `hp_to_go` = hp - max_hp / 2 (integer
  division; the smallest loss with 2*(hp - L) <= max_hp); effects = the
  split move's effects (`Split`).
- Otherwise `None`.

For each monster with a threshold, the encoder writes one row of kind
`threshold` on that monster's entity:
- trigger `OwnerLostHp(Any)`, an existing trigger name;
- a new condition name `HpLostReaches`, with `condition_param` = `hp_to_go`;
- grant `own`;
- the effect vector of `effects`. A hook-power `Apply` among them (Sharp
  Hide) has no dimension in effects mode, as everywhere else. Its hooks are
  written as further `threshold` rows with grant `me`, scaled by the amount,
  with the same condition and param. This is the same convention as an
  intent's granted rows.

The rows are written right after that monster's other rows, so dropping
every `threshold` row gives back today's row stream in today's order.

**Held rows (row kind `held`).** For a card whose `turn_end` is non-empty,
the card's precomputed rows gain one row of kind `held`: trigger
`OwnerTurnEnd` (existing name), condition `Always`, grant `own`, and the
effect vector of `turn_end`. The card's pile pooling already tells the net
whether the card is in hand, which is where it fires.
`PlainDamage { target: Me }` encodes as a new effect scalar
`damage_plain_self`. Every other `PlainDamage` stays `damage_plain`. Today
only Burn and Burn+ use the `Me` target; the build checks this with a grep
and a test. The card vector also adds `turn_end`'s effects, as it already
adds conditional rows' effects ("every effect; the rows say when").

**Old nets.** Every saved net lists its own `row_kinds` (`["triggered"]`)
and `columns`. The gather drops rows of kinds a net doesn't list and
columns it doesn't name (`damage_plain_self` in cards, intents and rows,
`condition_HpLostReaches` in rows). Old nets therefore get bit-identical
batches and outputs. New nets trained after the change save the new kinds
and columns.

**Row kinds in the net.** The model doesn't see `row_kind`; it pools every
kept row the same way. A threshold row is still distinguishable by its
condition column, and a held row by its trigger on a card. Nothing changes
in `stsnet`'s model.

Failure cases: a threshold with `hp_to_go` <= 0 is a bug. The accessor
returns `None` for it, and a debug assertion fires. A vocabulary without
`HpLostReaches` (an old net's `known_conditions`) sends the condition to
`condition_unknown`. That only matters if a net lists the `threshold` kind
without the condition, which can't happen through `save`.

## Fits with

- **The contract** (decisions.md "Contract as built"): old nets'
  batches and outputs stay bit for bit. New test
  `test_old_layout_unchanged`: `sts.Features` with the layout saved in
  `scripts/tests/data/contract/` (or the converted s1 r10 net's meta)
  encodes the fixed set to the pinned hashes. It passes on today's code and
  must keep passing.
- **Rules**: golden games (`py/tests/test_sts.py`) and the solved-DB
  fingerprint unchanged (`sts.SolvedDb().fingerprint` read-only, main's
  build vs the worktree's). The accessor agrees with the rules. New Rust test
  `threshold_matches_rules`: for The Guardian at a few ModeShift values and
  for Acid/Spike Slime L and Slime Boss at a few HP values, losing
  `hp_to_go - 1` HP doesn't switch the move and losing `hp_to_go` does (and
  for The Guardian, block rises by DEFENSIVE_BLOCK).
- **`test_modifier_list`**: `MODIFIER_POWERS` unchanged; ModeShift stays
  off the power dimensions. The comment changes from "unencoded" to
  "encoded as threshold rows".
- **Feature pins**: `golden_rows.npz`, contract batch hashes,
  `scripts/tests/data/curriculum_pins.json`, `test_net`'s `TRAIN_PIN`. The
  full-layout batches change on states with a threshold monster or a Burn.
  Re-pinned in build step 4 with an additivity check (below).
- **Training data**: whether `learn.py` datasets store raw states
  (re-encoded at train time) or encoded batches decides whether round 0 can
  be reused in the measurement (build step 5 checks it before the long run).
- **Speed**: rows add a handful per state with a large slime or The
  Guardian. Encoder time on the fixed set must stay within 5% (contract H3
  budget was 10%).

## When in doubt

Prefer old nets bit-identical over a neater encoding, and a primitive that
training content shares over one named after a single power.

## Scope

May change: `engine/src/threshold.rs` (new, outside the rules fingerprint: the read-only `threshold` accessor
and its Rust tests), `py/src/features.rs` (row kinds, condition name, scalar,
rows), `py/src/lib.rs` only to expose names if needed, the feature and
contract tests and their pinned data, `scripts/tests/data/curriculum_pins.json`,
README's features section, the results doc, `docs/decisions.md`, configs
for the measurement (`configs/lean-thr-s{1,101,201}.json`).

Interfaces that may change: new row kinds `threshold` and `held` in
`row_kinds`, new condition name `HpLostReaches`, new effect scalar
`damage_plain_self` (full-layout column lists grow).

Off limits: combat rules (`state.rs`, `hooks.rs`, `cards.rs` behaviour,
`powers.rs`), the solver and `solvedb`, the codec, the net architecture in
`stsnet.py`, `save`/`load`'s schema (stays 1: only additions), existing nets
and their converted files, the job queue.

Outside the repo: none. The worktree's venv lives beside the worktree
(gitignored path), not in the system Python.

## Decisions taken (provisional, to copy into docs/decisions.md on confirmation)

1. Threshold as a general row primitive shared with the slimes' split,
   not a `power_ModeShift` column. Alternative: add ModeShift to
   `MODIFIER_POWERS` (one column on player, monster and apply blocks;
   simplest, also additive), rejected because no training content has
   ModeShift, so it can't help zero-shot. A second alternative is to move
   the rules themselves to data (a threshold table that `state.rs` reads).
   It's cleaner for custom content, but it touches rules and the solved-DB
   fingerprint, so it's left for the rules-engine series.
2. New row kinds rather than new triggers. Kinds are the contract's
   existing extension point and keep old nets bit-identical. The
   alternative, encoder-only trigger names such as `HeldAtTurnEnd`, would
   reach old nets as `trigger_unknown` rows and change their outputs.
3. `damage_plain_self` as a new scalar rather than adding a target to
   `damage_plain`. It keeps today's columns' meaning.
4. Build in a git worktree with its own venv and Cargo target. Main's `sts`
   is in use by the job queue for ~8 h. Merge and rebuild main in a queue gap.

All reversible: additive columns and kinds. Nothing saved under the new
layout is read by old code, and new nets can be retrained.

## Outside assumptions

- Slimes are in the training pools of the lean recipe (training
  encounters include large slimes and Slime Boss). Checked in step 1 by
  counting threshold rows in a sample of round 0's training states:
  expected > 0, and at least a few percent of states.
- Python `venv` + `pip install` of main's frozen requirements works offline
  from pip's cache or online (torch CPU wheel ~200 MB). Checked in step 0.

## Verification

Tests first (step 1, on the unchanged code):
- `test_old_layout_unchanged` (Python): the fixed set encoded under the old
  layout (full-layout names of today, `row_kinds=["triggered"]`) equals
  today's pinned batch hashes. Passes before and after.
- `test_threshold_rows` (Python, fails before): a Guardian start state has
  one `threshold` row on its entity with `condition_param` 30 and `block`
  20, plus Sharp Hide granted rows with grant `me`; after 12 damage, param
  18; after the shift, no threshold row. An Acid Slime L at 65/65 HP has a
  row with param 33 (65 - 32); after it splits, none. A Cultist has none.
- `test_held_rows` (Python, fails before): a state with Burn in hand has
  one `held` row on Burn's card entry with trigger `OwnerTurnEnd` and
  `damage_plain_self` 2 (Burn+ 4); Burn's card vector has
  `damage_plain_self` 2; Sharp Hide and Combust rows still use
  `damage_plain`.
- `threshold_matches_rules` (Rust, step 2).

End-to-end: a net trained on round 0 data with the new features (tiny,
the `test_net` training fixture) saves `row_kinds` with all three kinds,
reloads, and gives identical outputs in torch and Rust on Guardian states
(the contract's two-forward-pass check, extended to the new kinds).

## Don't guard

- Don't add a fallback that writes ModeShift as a column too. One encoding.
- Don't validate `hp_to_go` against rules at encode time (the Rust test does
  that once).
- Don't handle monsters with two thresholds; none exists.

## Build steps

0. **Worktree and venv.** `git worktree add` a branch `threshold-rows`;
   create its own venv, install main's `pip freeze`, `maturin develop`
   there (Cargo target inside the worktree). Run the compile as a job
   (`jobs.py add --threads 4`) or when a heavy slot is free. Check:
   `import sts` in the worktree venv loads the worktree's build (path), and
   `py/tests/test_sts.py` passes there. ~0 lines.
1. **Tests first.** The three Python tests above, plus the slime-coverage
   count (outside assumption). Check: `test_old_layout_unchanged` passes
   and the two new tests fail on unchanged code; the count is > 0.
2. **Engine accessor.** `threshold::threshold` and `threshold_matches_rules`.
   Check: Rust tests pass, golden games unchanged, fingerprint string equal
   to main's. ~40 lines.
3. **Encoder.** Row kinds, condition name, scalar, threshold and held rows.
   Check: the step 1 tests pass, `test_old_layout_unchanged` still passes,
   and `test_contract` passes except the full-layout batch pins. Encoder
   time on the fixed set is within 5% of main's (best of 5). ~80 lines in
   `features.rs`.
4. **Re-pin with additivity checks.** Re-pin `golden_rows.npz`, contract
   batch hashes, `curriculum_pins.json`, `TRAIN_PIN`. Before writing each,
   check: (a) under the old layout every old hash comes back; (b) the
   states whose full-layout batch changed are exactly those with a
   threshold monster or a Burn card (list them). Fast suites pass
   (`test_contract`, `test_features`/golden, `test_net` without training
   tests). The slow suites (`test_curriculum`, `test_rounds`) go through
   the job queue. Then merge to main and rebuild main's `sts` in a queue
   gap (no job importing `sts`), per AGENTS.md.
5. **Long run (job queue, ~3 x 45 min, or ~3 x 60 min if round 0 must be
   retrained):** three lean-recipe nets with the new features,
   `lean-thr-s{1,101,201}` = `lean-s*` configs plus the new layout. First
   check whether round 0's dataset can be re-encoded. If it can, reuse it;
   if not, retrain round 0 for both arms' comparison and say so. Needs: all
   above.
6. **Measure (after 5).** Paired against `lean-s*` r2 nets on the same
   fights: `tight_bosses` per boss and half (primary: held-out Guardian,
   baseline -0.131, MDE ~0.06), `tight2` per fight type (control: within
   training luck; report slime encounters separately, since their
   encoding changed too). Secondary: the value probe. For the Guardian
   decisions in those fights, take the net's value at the last decision
   before the shift and the first after it, and compare the drop with the
   play-outs' mean final-score drop; report it per arm. Write the results
   doc section and the decision note. If the result passes, ladder-test the
   best new net.

## Build plan

> Build plan: 7 steps (0-6), forks for steps 2-4 (in the worktree),
> in-session for 0, 1, 5, 6, on Opus. Stop point: step 5's
> round-0 question (reuse vs retrain changes the comparison), decided by
> the manager.
