# Generated-power training arms: does training on many mechanics transfer?

Status: closed (2026-10-31, read: no transfer at this scale; results doc "Generated-power training arms", commit 56fa98fc).

## Why (goal 1)

Goal 1 is an AI that plays well on content it has never seen. The held-out
gap sits in power *mechanics* (Demon Form's turn start -> +Strength), and
the coverage pilot showed more training card kinds help held-out play with
falling returns. This spec asks the same question one level up: does
training on many generated power mechanics (trigger x effect pairs drawn
by `gen_content.py`) make the net play *unseen* mechanics better: the
generator's test-split powers, whose (trigger, effect) pairs no training
power has, and the official Demon Form? **How we'll know:** nets trained
with 16 or 128 generated train powers against the same recipe with none
(lean-thr, already trained), paired by cell and seed on the generated
bench. A lead that grows from 16 to 128 says content breadth is a lever
for goal 1 and generated content joins the training recipe; no lead says
new mechanics need a feature and an adaptation burst instead (prior-art
doc `unseen-mechanics.md`), and the next goal-1 work goes there.

## Outcome

Two training arms (16 and 128 generated train powers, 3 seeds each) and a
net-against-net read on a 12-fights-per-cell generated bench, with a
decision recorded.

Non-goals: a new budget/pricing for the generator (the first check found
the heuristic can price only Strength powers; that matters for realism
and for the heuristic as yardstick, not for this net-vs-net question);
new atoms, attacks/skills, monster content; a fresh round 0 with content
(arms reuse the night round 0 like lean-thr, so they pair with it at the
small shared-round-0 seed sd); changing any default.

## Behavior

**Arms.** `configs/lean-gen16-s{1,101,201}.json` and
`lean-gen128-s{1,101,201}.json` = `lean-thr-s*` plus `content:
{"seed": 2, "powers": 19}` (16 train powers) or `{"seed": 2, "powers":
176}` (128 train powers; the 19 are its prefix) and `content_share: 0.5`
(half the training decks hold 1-2 generated train-split power cards).
Run with `--round0 2026-10-27-score+branch-s0-r0-bd9a1c3`, like lean-thr,
so only rounds 1-2 see generated cards. Control: `lean-thr-s*` r2 (no
content), already trained.

**Bench.** `gen_powers_read.py build --seeds 12 --bench
data/bench/gen_powers12.json`: the same 326 held-out tight2 cells and the
same swapped generated test card per cell as the first check (same pick
seed), first 12 fights per cell instead of 4. The pack stays
`data/bench/gen_powers_pack.json` (seed 1, its 43 test powers); test-split
pairs are seed-independent, so no train power of either arm holds one.

**Play.** `gen_powers_read.py play --nets <run dirs> --bench ...` plays
each net (one-turn search at the agents' limit) on every fight and saves
`results/gen_powers/arms/<run id>.json` (per-fight won, bench path and
content hash); a net already saved is skipped.

**Read.** `gen_powers_read.py arms --control lean-thr --arms lean-gen16
lean-gen128`: for each arm, per seed index, the per-cell mean of arm
minus control, then the mean over seeds; se from the three seed means
(seed-to-seed spread holds both training luck and bench noise). Reported
on the generated set, the original set, the original Demon Form cells
(official unseen mechanic) and the original Metallicize cells
(contaminated: generated train powers hold turn end -> Block), and on the
generated set by fight type, lifetime and trigger.

**Official content.** `lean_read.py lean-gen16 lean-gen128 lean-thr`
(tight2 per half and fight type, arm minus lean-thr by hand) and
`boss_lead.py` for tight_bosses, as for other arms.

**Decision rule** (MDE: shared-round-0 seed sd ~0.007 on tight2 plus
bench noise ~0.006 per net at 12 fights x 326 cells -> se of a 3-seed
paired mean ~0.0075, MDE ~0.02):
- gen128 minus control on the generated set >= +0.02 and > 2 se, and the
  official train half >= -0.015: **transfer**. Content (128 powers, share
  0.5) joins the experiment recipe (lean configs), and the next goal-1
  spec is pricing plus wider mechanics (attacks/skills, debuffs on
  monsters).
- gen128 within +-0.02 of control: **no transfer at this scale**; goal-1
  work moves to per-mechanic features and adaptation (rate features
  result, a short fine-tune burst on a new mechanic).
- gen16 says whether a little content already does it (shape of the
  curve), not adoption.
- Demon Form cells are read alongside (MDE ~0.04 at 170 cells); a gain
  there is the strongest evidence, but it doesn't decide alone.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Registry-lite generator | `generate(seed, n)` deterministic; prefix property (the 16-power arm is a prefix of the 128) | `test_gen_content.py` + new test: seed 2 at 19 / 176 powers gives 16 / 128 train cards, 19 is a prefix |
| First check's bench | `gen_powers.json` and `first-check.json` unchanged; `build` with no flags writes the same file | new test: `build` default output equals the committed `gen_powers.json` |
| learn.py / selfplay | No behaviour change; configs only | `test_setups`, `test_net` (unchanged code) |
| Other arms' reads | `lean_read.py`, `boss_lead.py` unchanged | unchanged code |

## When in doubt

Prefer pairing over pooling (by cell, by seed index); prefer reporting a
slice over dropping it.

## Scope

May change: `scripts/analysis/gen_powers_read.py` (flags `--seeds`,
`--bench`; commands `play`, `arms`), new configs `configs/lean-gen*`,
`data/bench/gen_powers12.json` (new), `results/gen_powers/arms/`,
tests under `scripts/tests/`, docs (results doc, decisions, README line).

Off limits: engine and Python bindings, `learn.py`, `selfplay.py`,
`gen_content.py` behaviour, `data/bench/gen_powers.json` and the pack,
existing configs.

## Decisions taken (also in docs/decisions.md)

- Control is lean-thr (no new control runs); arms reuse the night round 0.
- Packs from generator seed 2 (not the bench's seed 1), sized to exactly
  16 / 128 train powers, nested.
- content_share 0.5.
- Read net against net; the heuristic is not the yardstick here.

## Outside assumptions

None.

## Verification

Tests first:
- `test_gen_content.py::test_arm_packs`: `generate(2, 19)` has 16 train
  cards, `generate(2, 176)` has 128, and the first 19 powers are equal.
- `scripts/tests/test_gen_powers_read.py`: `build` with defaults writes a
  file equal to `data/bench/gen_powers.json`; `--seeds 12` gives the same
  cells and cards with 12 fights each; the `arms` pairing on a hand-made
  3-cell, 2-seed input returns the hand-computed means and se.

End to end: the six arm runs (long), `play` on 9 nets, `arms` read, written
into the results doc with the decision.

## Don't guard

Bench sizes other than 4 and 12; arms other than these two; runs other
than r2.

## Build steps

1. Tests (above); configs `lean-gen{16,128}-s{1,101,201}`. Check: test
   `test_arm_packs` passes; config diff vs lean-thr is only `name`,
   `content`, `content_share`.
2. **Long run (~3.5 h single-file):** queue the six arm runs. Their read
   (step 4) needs them; step 3 doesn't.
3. `gen_powers_read.py` flags and commands; build the 12-fight bench;
   queue `play` on the three lean-thr r2 nets. Check:
   `test_gen_powers_read.py` passes; a `--limit 3` smoke of `play` and
   `arms`.
4. After step 2: `play` on the six arm nets, `arms` read, `lean_read.py`,
   `boss_lead.py`; results doc section and decision.

Build plan: 4 steps, in-session, on Opus. No stop points
expected.
