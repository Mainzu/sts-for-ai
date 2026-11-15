# HP weight in the outcome labels

Status: closed (2026-11-01, read: decisions "HP weight 2 passes; burst with HP weight queued").

## Outcome

Train nets whose labels price HP lost more heavily than 1% of a win per
HP, and measure whether they stop losing more HP than the heuristic at
run-like starting HP, without losing fights.

How it moves goal 2: a run is decided by HP carried from fight to fight,
not by near-death survival. The run-HP first check (ladder-v2,
`results/ladder/runhp/0001-0003.json`, 2026-11-01) found every net we
have losing 5.5-6.4 HP more per fight than the heuristic (champion 11.6
vs 5.6) at equal win rates (~0.98). A player that bleeds ~6 HP per fight
over ~15 Act-1 fights is far from Stockfish-level whatever its tight-fight
win rate. We'll know from `ladder.py runhp` against the heuristic, paired
by fight with the lean-thr control.

Non-goals: changing the engine's score, search's scoring of finished
combats, the tight-fight gate, the product champion; a turn-count
feature; switch 6 (HP histograms).

## Diagnosis (CPU-free plus one small replay)

- In fights both players win, the champion loses more HP than the
  heuristic in 55-59% of pairs and less in 11-14% (all three nets alike);
  median +2-3 HP, 90th percentile +15-19 HP.
- The gap sits in multi-monster hallways: exordium_thugs +12.5 HP,
  exordium_wildlife +11.3, lots_of_slimes +15.2 (heuristic 3-4 HP lost
  there). Nob, Lagavulin, Sentries +3-4 (lean-thr's Sentries +11.8);
  Cultist, louses, Slime Boss about level.
- Replay of 240 run-HP fights (2 threads): the champion takes **far more
  turns** where it bleeds: thugs 6.4 turns vs the heuristic's 3.8,
  wildlife 5.8 vs 3.4, lots_of_slimes 9.4 vs 3.6; Nob 3.9 vs 3.6 (similar
  turns, +2 HP). The nets drag multi-monster fights out and take chip
  damage each turn.
- Why: the label is 2 - HP lost / 100 on a win. At full HP a win is near
  certain, so all of the net's signal about a hallway is a few hundredths
  of the score, below its value error (val MSE ~0.13, rmse ~0.36 score).
  The heuristic models damage taken directly (`heuristic.rs`: `taken`,
  kill order that minimises it) on the same 1%-per-HP scale, so it plays
  fast. Raising the label's HP weight makes HP differences bigger relative
  to the outcome noise and raises their price.

## Behaviour

- Config key `hp_weight` (w > 0; absent: off, labels bit-identical). Every
  outcome label scores a win 2 - w x HP lost / 100, floored at
  `WIN_FLOOR` = 0.1 so a win stays above a loss (0); losses stay 0
  (`learn.hp_scale`). Applied when a dataset's examples are loaded
  (`learn.load_examples` → `weigh_hp`): `outcome`, `target` (equal to the
  outcome when loaded; the curriculum ladder then builds its rungs from
  the weighted outcome) and `opt_const` (an option's finished outcomes,
  weighted as one win at their mean score over the finished mass). The
  validation set is weighted the same, so val MSE is on the weighted scale.
- Search values of a net trained this way are already on the weighted
  scale, so rung 3 (`w_near` x search + (1 - `w_near`) x outcome) and the
  ranking order need no change.
- Known mismatch: search scores a finished combat with the engine's
  unweighted score (`state.rs` `score`), the net's leaves are weighted.
  A finished win is therefore valued at most (w - 1) x HP lost / 100 above
  where the net would put it. It only biases toward ending the fight this
  turn, which also saves HP; finished options among themselves still order
  by HP lost. Fixing it needs an engine option and a rebuild: out of scope.
- Not with switch 6, `teacher` or `rung4` (their values are unweighted):
  ValueError at `learn` start. The solved database isn't opened with
  `hp_weight` (its values are unweighted expected scores; lean configs use
  none today: rung counts `exact` 0). A reused round 0 (`--round0`) must
  have the same `hp_weight` (ValueError otherwise), so the arms train their
  own round 0 on the shared round-0 games.
- Datasets (games) don't depend on the key: round 0's games are shared
  with lean-thr; later rounds are played by the arm's own nets.

## The experiment

- Arms: `configs/lean-hpw2-s1/s101.json`, `lean-hpw4-s1/s101.json`:
  lean-thr's configs plus `hp_weight` 2 and 4. w = 2 makes a death (0)
  worth losing 100 HP, close to run-HP's death cost (start HP + 30); w = 4
  makes it 50 HP, the HP-heavier side. Control: lean-thr s1 / s101 r2
  (their round 0 is the night's shared round 0 with the same games and
  seed; the arms differ only in labels).
- Read: `ladder.py runhp <r2 model.pt> --pairs 2000` for each arm net and
  for lean-thr s101 r2 (lean-thr s1 r2 is run-HP 0003). Every run-HP run
  plays the same fights (block 6000 on), so arm and control pair by fight:
  saved HP = control's HP lost - arm's, per fight, mean over fights, then
  over the 2 seeds.
- Rule (pre-registered): an arm **passes** when it saves >= 2.0 HP per
  fight on the mean of its 2 seeds, each seed >= +1.0, its deaths per 2000
  fights are at most 20 more than the control's (1 point), and its tight2
  held-out lead (round.json, r2) is no more than 0.02 below the control's.
  Then: hp_weight joins the next product-candidate recipe (the champion's
  recipe with the passing w) and run-HP becomes part of the product tests.
  Both arms save < 1.0 HP: label weight doesn't fix the bleeding; next is
  depth's effect on run-HP (two-turn champion) or a turn/tempo feature.
  Between: report, add one seed to the better arm.
- Noise: run-HP se per run ~0.35 HP (2000 pairs, sd 12-14, pairing corr
  0.6-0.7); the three nets' run-HP spread is ~0.9 HP, so seed sd is likely
  ~0.5 HP and 2 seeds detect ~1.5 HP. The bar (2 HP, a third of the gap)
  is above that.

## Fits with

- `test_rounds.py`, `test_curriculum.py`: configs without the key train
  as before (`weigh_hp` returns the dataset untouched; `open_db`
  unchanged). Pinned by `test_hp_weight.py::test_off_leaves_examples_alone`.
- `test_hp_loss.py`: switch 6 unchanged; combining it with the key raises.
- `ladder.py`, `bench.py`, the gate: measure on unweighted engine scores,
  untouched.

## When in doubt

Prefer leaving the engine's score alone over making labels and search
perfectly consistent.

## Scope

May change: `scripts/learn.py` (label loading, checks, docstring), new
`scripts/tests/test_hp_weight.py`, new `configs/lean-hpw*.json`, this
spec, results doc and decisions. Off limits: Rust engine and binding,
`selfplay.py`, `train.py`, `stsnet.py`, `ladder.py`, existing configs.

## Decisions taken

- Weight in labels (Python), not in the engine's score (needs a rebuild;
  would change every measurement).
- w = 2 and 4, 2 seeds each, fresh round 0 per arm (the shared one is
  unweighted).
- Floor 0.1 for wins: at w = 4 a win losing >= 47.5 HP floors; rare at run
  HP (hallways start at 56-80 HP, most wins lose < 20).

## Outside assumptions

None beyond the run-HP harness (ladder-v2, reviewed and merged 5d9ad83).

## Verification

`scripts/tests/test_hp_weight.py`:
1. `test_off_leaves_examples_alone`: no key → the same object, unchanged.
2. `test_outcomes`: [0, 2.0, 1.9, 1.5, 1.2] at w 3 → [0, 2, 1.7, 0.5, 0.1].
3. `test_targets_and_outcomes_weighed`: outcome and target both weighted.
4. `test_opt_const`: a chance option with finished mass 0.5 at 1.9 (const
   0.95) → 0.85 at w 3; others untouched.
5. `test_unsupported_combinations`, `test_round0_must_match`: ValueErrors.
6. `test_smoke_learn` (end to end, ~3 min): a tiny two-round run with
   w 3; round 0's label scale is 0; its loaded outcomes equal
   `hp_scale` of the unweighted load; a reused round 0 of another weight
   is refused.

Don't guard: w < 1 (allowed, just softer), mixed win/loss finished
outcomes in one chance option (approximated, rare).

## Build steps

1. Tests 1-5 and `weigh_hp` / `hp_scale` / checks in `learn.py`; wire into
   `load_examples`, `open_db`, `learn`.
2. Smoke test 6; configs.
3. **Long run:** the 4 learn jobs (~40 min each with their own round 0),
   then 5 run-HP reads (~2 min each). Read per the rule.
