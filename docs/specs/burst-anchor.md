# Burst anchor: a retention term for fine-tune bursts

Status: closed (2026-11-08, built; checkpoint anchor failed: decisions "Lane pack-retention closed (2026-11-08)"; kb measurement/burst-anchor@gen-b1).

Lane `pack-retention` step 2 (kb `lane/pack-retention`).

## Outcome

A fine-tune burst can be held near its parent's weights, so a pack's
burst keeps what the parent knew (the TurnEnd-Frail x Lagavulin and
Lagavulin-parent leaks, `measurement/pack-chain@gen-b1`) while it still
learns the pack's big cost (AttackLoss-Damage x Nob).

Non-goals: distillation toward the parent's outputs (a second option the
charter names; see Decisions), new reads, changes to the guard or the
table.

## How it moves goal 1, and how we'll know

Goal 1 is first-class custom content: a pack of new mechanics should
ship a net that plays the new content better and the old content no
worse. Today every burst net on gen-b1 gets worse on Lagavulin, so the
chain ships nets at the guard's bar. If an anchored arm brings both
Lagavulin cells within 1 HP of zero-shot at both seeds and keeps 8.0 HP
or more of the Nob cut (the charter's go), the chain gets a burst
setting that keeps old content, and step 3 confirms it on fresh starts.
The gen-b1 table per arm and seed tells us.

## Behaviour

- `train.train(..., anchor=λ)`: with a warm start and λ > 0, each batch's
  loss adds λ x (sum over every parameter of (θ - θ0)²), θ0 the start
  net's weights as `train` receives them (after `stsnet.widen`, so the
  widened columns anchor to their initial values). λ = 0 or absent: the
  loss is unchanged, bit for bit. λ without a start net: refused.
- `finetune.py` config key `anchor` (default 0) passes λ to `train`;
  refused with `start: fresh`.
- `family.py` pack arms: arm keys other than `games` and `parents` go
  into that arm's burst configs, so a pack file can hold
  `{"a003": {"games": 99, "anchor": 0.003}}`.
- Scale: the gen-b1 g99 bursts moved the weights by a summed squared
  drift of 9-21 (192k parameters, parent's own sum of squares 459) at a
  training loss near 0.12; λ = 0.01 makes the penalty at that drift about
  equal to the loss. Arms λ = 0.003 and 0.03 bracket it a factor of
  about 3 each way.

## Fits with

- Bursts without `anchor` (every existing config): unchanged loss;
  pinned by `test_anchor_zero_is_unchanged` (new) and the existing
  `test_warm_start.py` / `test_finetune_gen.py` suites.
- Pack expansion of existing pack files: unchanged configs (no extra
  keys); pinned by `test_pack_queues_the_chain` (existing) and
  `test_pack_arm_keys_reach_config` (new).
- A config change under an existing burst job is refused
  (`test_pack_config_change_refused`, existing): adding arms to a new pack
  file doesn't touch gen-b1's or gen-b1-heur's configs.

When in doubt: prefer a smaller change to `train.train` over a general
regulariser framework.

## Scope

May change: `scripts/train.py` (the `anchor` argument), `scripts/finetune.py`
(the config key and its docstring), `scripts/family.py` (`pack_config`'s arm
keys), their tests, a new pack file `configs/packs/gen-b1-anchor.json`, and
docs. Off limits: the read, the table, the guard, `stsnet`, the engine.

## Decisions

- L2 toward the parent's weights (L2-SP), not distillation toward the
  parent's outputs: a few lines in `train`, no extra forward pass, and on
  the burst's own positions distillation pulls back the Nob cut as directly
  as the leak. Reversible: distillation can be a later arm if the anchor
  fails. (On the owner's behalf; in docs/decisions.md.)
- Net teacher (the pack default) for the anchored arms: step 1's heuristic
  teacher at seed 1 lost the Nob cut (-2.51), so the anchor works on the
  teacher that learns it.

## Verification

- `test_anchor_zero_is_unchanged`: two tiny warm-start trainings with the
  same seed, `anchor` absent and `anchor=0`, give identical weights.
- `test_anchor_pulls_toward_start`: the same tiny warm-start training with
  `anchor=10` ends with a smaller summed squared drift from the start
  weights than with `anchor=0`.
- `test_anchor_refuses_fresh`: `anchor` > 0 without `start` raises.
- `test_pack_arm_keys_reach_config`: a pack arm `{"games": 99, "anchor":
  0.003}` writes `"anchor": 0.003` into both seeds' configs; an arm
  without it has no `anchor` key.
- End to end: `family.py queue configs/packs/gen-b1-anchor.json --dry-run`
  shows 4 bursts with the anchors in their configs, 4 reads and a table,
  base reused.

## Build steps

1. `train.train` anchor and its three tests; `finetune.py` key. Check:
   the new tests and `test_warm_start.py` pass.
2. `family.py` arm keys and its test; the pack file. Check: test_family
   passes; the dry run above.
3. Queue the chain (long run, ~5.8 thread-h). Its table is the
   checkpoint `anchor` (go: an arm with both Lagavulin cells within 1 HP
   of zero-shot at both seeds and the Nob cut 8.0 or more).
