# Learned play: results

## Step 1: teacher sizing (2026-10-24)

Search + heuristic at several depths on the evaluation bench
(`scripts/teacher_sizing.py`, results in `results/teacher_sizing.json`).
Decision quality is on the bench's contested decisions (reference best −
worst ≥ 0.05) against the cached reference search; strength is the tight
fights. Limit 16 (the agents') everywhere; brackets are 95% intervals.
Compute: ms per saved decision (one thread) and tight-fight games per second
(all threads).

| Half | Search | regret (contested) | ranking (contested) | win | ms / decision | games / s |
|---|---|---|---|---|---|---|
| train | 1 turn, sample_k 0 (agents) | 0.056 [0.039, 0.075] | 0.899 [0.881, 0.919] | 0.528 [0.488, 0.567] | 0.4–2.0 | 150–680 |
| train | 1 turn, sample_k 2 / 4 / 8 | identical to the row above | | | | |
| train | 2 turns, sample_k 0 | identical to the row above | | | | |
| train | 2 turns, sample_k 1 | 0.037 [0.025, 0.049] | 0.913 [0.897, 0.929] | 0.467 [0.428, 0.507] | 40–44 | 4.2–5.2 |
| train | 2 turns, sample_k 2 | 0.026 [0.015, 0.038] | 0.935 [0.920, 0.949] | 0.528 [0.488, 0.567] | 115–117 | 2.0–2.9 |
| train | **2 turns, sample_k 4** | **0.023 [0.013, 0.035]** | **0.942 [0.927, 0.956]** | 0.520 [0.480, 0.559] | 67–108 | 2.3–3.0 |
| held-out | 1 turn, sample_k 0 (agents) | 0.037 [0.023, 0.053] | 0.918 [0.900, 0.935] | 0.496 [0.455, 0.538] | 0.4–2.0 | 150–680 |
| held-out | 2 turns, sample_k 1 | 0.038 [0.025, 0.054] | 0.906 [0.889, 0.922] | 0.440 [0.399, 0.482] | 40–44 | 4.2–5.2 |
| held-out | 2 turns, sample_k 2 | 0.030 [0.020, 0.042] | 0.918 [0.901, 0.934] | 0.465 [0.424, 0.507] | 115–117 | 2.0–2.9 |
| held-out | **2 turns, sample_k 4** | **0.019 [0.011, 0.030]** | **0.934 [0.918, 0.949]** | 0.480 [0.439, 0.522] | 67–108 | 2.3–3.0 |

Timings come from three runs and vary up to ~2× between them (CPU load); the
ranges show all of them. The third run (2026-10-24, after the bench fixes in
`2cc01ca`, including the option-grouping guard) reproduced every regret,
ranking and win-rate number exactly; only timings changed.

Reading:

- **Sampling or a second turn alone does nothing.** A second turn only takes
  effect with `sample_k > 0` (the next turn's draw is a large random event;
  `engine/src/search.rs`), and at one turn sampling only reaches large
  in-turn random events, which the tight fights never hit. Those rows are
  byte-identical to one-turn search.
- **Two turns with sampling decide better:** with sample_k 4, contested
  regret falls from 0.056 to 0.023 (train, intervals apart) and from 0.037
  to 0.019 (held-out, barely overlapping); ranking rises on both halves.
- **It doesn't play better.** Tight-fight win rate is flat or lower (0.520
  vs 0.528 train, 0.480 vs 0.496 held-out; sample_k 1 is clearly worse).
  Possible causes (not checked): the heuristic scores the end of the second
  turn after a few sampled draws, so leaf noise grows with depth, and the
  50k node cap may cut two-turn trees short.
- **Bias warning:** the reference is itself a two-turn sampling search
  (limit 32, sample_k 8, three seeds), so two-turn searches agree with it
  partly by construction. The regret gain is an upper bound on the real
  decision gain.
- **Cost:** about 100× one-turn search per decision and 2–3 tight-fight games
  per second on all threads. Today's training set (30,000 full-HP games,
  128 s at one turn) would take several hours with this teacher.

Chosen deeper teacher (switch 5): **2 turns, sample_k 4, limit 16**; see
`docs/decisions.md`.

## Amendment 1, A3: self-play depth (2026-10-24)

Net-guided self-play speed with the effects net (`models/value_effects.pt`),
full-HP mixed train-deck encounters, all threads, games per second; the machine
was shared, so timings vary ~2x between runs.

| Search | normal | no-death | play vs one turn, sample_k 0 |
|---|---|---|---|
| 1 turn, sample_k 0 (agents) | 5.0–12.1 | 3.7–8.4 | – |
| 1 turn, sample_k 2 / 4 / 8 | 5.0–10.7 | 7.8–10.1 | identical (300 of 300 games) |
| 2 turns, sample_k 1 | 0.28 | 0.30 | not measured |
| 2 turns, sample_k 4 | 0.20 | 0.21 | not measured |
| heuristic, 1 turn | 150–310 | 130–230 | – |

A 20-minute round at two turns would hold ~110 games per encounter group, so
the self-play search is one turn, limit 16, for every round
(`learn.SELFPLAY_SEARCH`; `docs/decisions.md`).

## Speed profile (2026-10-25, dev machine)

- Search + heuristic: ~80-135 games/s on one thread, ~300-430 on all threads (4-5x):
  mixed core types and turbo limit scaling; it isn't lock
  contention. mimalloc adds 15-40%.
- The Rust net costs ~17 us per scored state (LTO + target-cpu=native).
  Batching or register-tiling its layers was slower (37 and 200 us/state):
  the inputs are sparse and skipping zeros wins.
- Training is overhead-bound: ~35 ms per 512-state batch, the same with 1-8
  torch threads, so parallel runs (`--jobs`) use the idle cores.
- Other projects on the dev machine can slow a sweep ~3x (B4's dev machine attempt);
  timings taken while it's shared are noisy.

## Amendment 3 sweep and why rounds don't improve (2026-10-26)

Sweep `runs/sweep-2026-10-26.md`: score config, 2 seeds, varied setups,
1,079 games per group per round (round 0 never retired, so `n_late` was
never used), 10 rounds each (the gate was never met), 56 min with
`--jobs 2`. Final nets 0.475 / 0.445 tight-fight win (train / held-out)
against the heuristic's 0.528 / 0.496; B4's score config was 0.458 / 0.445.

Tight-fight win, both seeds and halves pooled (2,320 games per round):
r1 0.460, r3 0.487, r5 0.492, r7 0.474, r10 0.461. Paired on the same
specs (search is deterministic per spec; replayed, matching round.json):
r5 - r1 +0.032 +- 0.015, r10 - r5 -0.031 +- 0.015, r10 - r1 +0.001 +- 0.016;
every round below the heuristic (r5 -0.021 +- 0.017, r1 and r10 -0.05).
The paired intervals hold the bench specs' noise only, not training noise
(seeds of one round agree on 88% of specs, differ by up to 0.02 in win rate),
and r5 was picked as the peak after looking, so the rise-then-fall is a
small effect at the edge of the noise. The firmer finding is the plateau.

Self-play on varied setups (500 per group, same specs, one-turn search):

| agent | explore 0: win / score / HP lost when won | explore 0.05: win / score / HP lost when won |
|---|---|---|
| heuristic | 0.797 / 1.510 / 9.6 | 0.590 / 1.103 / 12.5 |
| round-0 net | 0.818 / 1.490 / 17.2 | 0.734 / 1.268 / 27.0 |
| s0 r1 | 0.807 / 1.498 / 13.7 | 0.726 / 1.301 / 20.6 |
| s0 r5 | 0.816 / 1.523 / 12.7 | 0.733 / 1.309 / 21.1 |
| s0 r10 | 0.810 / 1.515 / 12.4 | 0.731 / 1.298 / 22.1 |

- Greedy self-play strength is flat from round 1 to 10 (score 1.50-1.52, at
  the heuristic's 1.51): the rounds stop improving the policy almost at once.
- Exploration (softmax at temperature 0.05) costs every net ~8 points of win
  rate and ~0.21 score in the very games whose outcomes are the labels. The
  playing nets pick a non-best option at 56% of decisions in every round
  (many exact ties: the median best-to-second gap is ~0); 19% of picks give
  up more than 0.01 of value and 5.7% more than 0.05, ~0.16 per game by the
  net's own values. This doesn't drift across rounds.
- So each net learns the values of its noisy self-play policy: on heuristic
  play (validation states) every round's net undervalues mid- and high-HP
  states by ~0.08-0.10 against the real outcomes, where the round-0 net
  (trained on greedy heuristic games) is calibrated (MSE 0.150 vs 0.17-0.18).
  Greedy search over values of an exploring policy is an improvement step
  toward the best noisy policy, not the best greedy one: a plateau.
- On tight-fight states (low HP) calibration shows no trend across rounds;
  outcome noise dominates (MSE 0.70-0.85 at ~50% win).
- Nets at explore 0 win more varied fights than the heuristic (0.81 vs 0.80)
  but lose more HP when winning (12-13 vs 9.6), the trade the score asks for;
  on the tight fights, which start at the heuristic's calibrated low HP, they
  still win 2-5 points less.

Next amendment candidates, by what they target: labels from near-greedy
play (lower temperature, or explore only at a few decisions per game and
label only states after the last exploratory move); keeping the best net as
the generator (a champion that a new net must beat on the tight fights)
instead of always the last; a larger window or replay buffer of earlier
rounds (the owner allows a higher memory cap).

## Curriculum night (2026-10-28)

Sweep `runs/sweep-2026-10-28.md`: the curriculum (docs/specs/curriculum.md
with Amendments 1-2), score config with branches, 2 seeds, varied setups,
1,048 games per group per round, `--jobs 1 --free 7.0`. Round 0 (shared)
75.7 min; seed 0 ran 21:34-00:32 and, after a solver stall (below), 02:18-03:51;
seed 1 03:51-07:01. Both seeds ran all 10 rounds: the gate was never met.

Tight-fight win, both seeds pooled (train and held-out averaged), against
the heuristic's 0.512 (0.528 / 0.496):

| round | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 0.497 | 0.523 | 0.516 | 0.519 | 0.516 | 0.510 | 0.499 | 0.512 | 0.508 | 0.507 |
| held-out | 0.494 | 0.501 | 0.514 | 0.526 | 0.507 | 0.506 | 0.500 | 0.514 | 0.504 | 0.493 |

- **Level with the heuristic, from round 2 on.** The 2026-10-26 sweep
  (outcome and search labels, no curriculum) plateaued below it (pooled
  0.46-0.49, every round under); this one plateaus at it (0.50-0.52). The
  final nets: s0 0.508 / 0.476, s1 0.534 / 0.511 (train / held-out).
- **The gate can't be met by a small lead.** It needs the net's 95%
  interval wholly above the heuristic's on both halves; with ~550 fights
  per half each interval is about +-0.042, so the net must lead by about
  0.085. The best round led by 0.035 (s1 r4 held-out, 0.531).
- **The trusted zone never moved past 1.** Every round verified horizon 0
  (regret ~0.0000-0.0003) and failed horizon 1 (0.013-0.043 against
  `regret_max` 0.01; 140-175 puzzles counted). So rung 3 search labels were
  used only within one turn of the end (~66-70k examples a round); the rest
  of the value labels were outcomes (~77k) and the exact draws (~9.2k
  decisions a round, 20% of the value weight).
- **Round 0 left the window early**, at s0 r5 and s1 r2, when the nets
  reached the heuristic on both halves (Amendment 3 of learned-play); s0
  dipped two rounds later (r7 0.489 / 0.478) and recovered.
- **Solver stall.** Seed 0's round-6 solve step sat in one `sts.solve` for
  95+ min: the node budget didn't count the outcomes listed at a random
  event (a draw from a varied deck has thousands). Fixed by bounding
  children listed at 16 per node of the budget (normal solves list at most
  4.4; fab0394); the round redid its solve step in 17.5 min and later steps
  stayed within 11-17 min. Before the fix the solve steps ran 15-55 min.
- `db/train.sqlite` grew to 0.97 GB (3.5M rows) over the night.

Open for the review: what the curriculum needs to move horizon 1 (more
exact labels near the end, a looser `regret_max`, or more puzzles at
horizons 1-2 so the test is less noisy), and whether the gate should
compare paired win rates on the same specs (the 2026-10-26 analysis
measured paired intervals of about +-0.015) instead of two independent
intervals.

**Paired gate on the night's nets (learned-play Amendment 5, 2026-10-28).**
All 20 round nets replayed on the tight fights (each replay matched its
round.json win rate) and compared spec by spec with the heuristic. Per half
the paired 95% interval is about +-0.03 (vs +-0.085 needed before): the
players disagree on roughly one fight in six. No round meets it. Held-out
leads mostly sit at +0.01 to +0.025, the training-card half at -0.04 to
+0.02; the best, s1 r4 held-out +0.035 [-0.000, +0.070], misses by a hair
while its training half is -0.016. So the nets are level with the
heuristic, not hidden winners: the old gate wasn't what held them back.

## Exact-only experiment (2026-10-28)

Spec `docs/specs/exact-only.md`; `python scripts/exact_only.py`, 26 min.
Two nets trained from scratch on exact values only, from `db/train.sqlite`:
120k decision rows (60k at `turns_left` 1-3, 60k at 0; dull ones skipped,
leaving 57k), held out by key hash. A: decision states valued, afterstates
ranking-only (333k examples). B: A plus each option's state paused at a
random event (End turn's, before the draw: what one-turn search scores)
valued at the option's exact value (377k examples, 102k valued). The
paused states needed no extra solving: an option's exact value is that
state's. Solving every chance outcome instead was measured at ~90 min for
60k rows.

**Bench puzzles, mean regret per horizon** (dull skipped, 95% bootstrap):

| evaluator | h0 | h1 | h2 | h1 vs heuristic |
|---|---|---|---|---|
| A | 0.007 | 0.051 [0.024, 0.081] | 0.111 | -0.009 [-0.045, 0.023] |
| B | 0.016 | 0.053 [0.024, 0.086] | 0.080 | -0.007 [-0.042, 0.028] |
| night s1 r10 | 0.000 | 0.030 [0.010, 0.056] | 0.072 | -0.029 [-0.075, 0.011] |
| heuristic | 0.000 | 0.060 [0.027, 0.096] | 0.032 | - |

**Held-out training-db decisions scored the same way** (600 per
`turns_left`, one-turn search pick vs the exact values):

| turns_left | A | B | night s1 r10 | heuristic |
|---|---|---|---|---|
| 1 | 0.006 [0.002, 0.013] | 0.006 [0.003, 0.012] | 0.014 | 0.026 |
| 2 | 0.012 | 0.010 | 0.015 | 0.010 |

**Static value MSE, held-out rows** (decision states / paused states at
`turns_left` 1): A 0.011 / 0.092, B 0.010 / 0.017, night 0.031 / 0.054
(training rows alike). Tight fights paired against the heuristic: A -0.22 /
-0.17, B -0.17 / -0.11 (train / held-out); expected, they never saw an
early-fight position.

**Reading.**
- **The net can learn one-turn-out values.** On held-out database
  positions both exact-only nets pick at 0.006 regret one turn out, under
  the zone's 0.01 and better than the night's net (0.014) and the
  heuristic (0.026). So not a capacity limit (the spec's explanation 3).
- **B fixes the paused states' values** (MSE 0.017 vs A's 0.092) but that
  doesn't change the picks: A and B pick alike. The search's ranking among
  siblings matters, not the leaves' absolute values (explanation 2 is
  real at the value level, not at the pick level).
- **It doesn't carry to the bench puzzles** (0.05 vs the night's 0.03),
  and the exact-only nets even err at horizon 0 there, where the night's
  net and the heuristic don't. Not settled: whether the held-out rows leak
  (split by position, so they share games with training rows) or the
  bench's positions (search + heuristic play on calibrated tight specs)
  differ from the training database's (self-play on varied setups). A
  check on the bench games' other walked positions (`db/solved.sqlite`,
  never trained on) tells them apart.
- **That check: the bench's positions are a harder population.** 600
  non-dull decisions per `turns_left` from `db/solved.sqlite`, scored the
  same way: at 1, A 0.060, B 0.047, night 0.028, heuristic 0.082; at 2, A
  0.020, B 0.023, night 0.014, heuristic 0.025. Every evaluator does worse
  there than on the training database's positions, the heuristic too (0.026
  to 0.082), so it isn't only leakage: tight-fight positions are harder
  than the self-play positions the database holds. The exact-only nets
  lose the most (10x, the night's net 2x): they learned the database's
  population. A likely cause, from the night's walks
  (`runs/slow-solves-2026-10-28.md`): 70% of walked games gave no position,
  stopping at their last decision because one option leads into a long
  fight the solver can't finish, so the database keeps only positions with
  short futures.

## Solver bounds, measured (2026-10-28)

Spec `docs/specs/solver-bounds.md`, step 5. The 75 walked games of the
night's two slowest solve steps re-walked with bounds into a fresh empty
database (colder than the night's, which held earlier rounds' rows), 6
threads at idle priority, against the night's own walks of the same games:

| round | games with no position | positions | positions 1+ turns out | time |
|---|---|---|---|---|
| s0 r8, night | 54 of 75 | 89 | 41 | 14.4 min |
| s0 r8, bounds | **0** | **577** | **384** | **5.2 min** |
| s1 r5, night | 52 of 75 | 55 | 11 | 8.8 min |
| s1 r5, bounds | **0** | **373** | **198** | **7.0 min** |

Positions per horizon with bounds: s0 r8 193 / 131 / 53 / 34 / 166 (0, 1,
2, 3, 4+), s1 r5 175 / 107 / 34 / 17 / 40; the night's: 48 / 18 / 12 / 3 /
8 and 44 / 11 / 0 / 0 / 0. 16 of 150 walks now reach their game's first
decision. Soundness on the bench puzzles (every 10th, 198 that both solves
finish): decision values equal to 1e-15, every exact option equal, every
bounded option's exact value at or under its bound; 64 of them had a
bounded option, and the bounded solves took 12 s against 34 s.

So the walks stop being cut off at the last decision: every game now gives
positions, 5-7x as many in all and 9-18x as many one turn or more from the
end, which is the population the exact-only experiment found missing.

## Exact-only experiment, rerun on positions walked with bounds (2026-10-28)

The same experiment (`scripts/exact_only.py`, both arms, 60k + 60k rows,
same seeds) on a fresh database, `db/bounds.sqlite`: 525 of the night's
self-play games (75 each from s0 r1-r4 and s1 r1-r3) walked back with
solver bounds in 63 min at below-normal priority, 7,080 positions and 1.7M
solved states. It holds 357k decision states one turn from the end, 384k
two and 96k three (`db/train.sqlite`: 175k, 65k, 9k). Valued examples:
A 101k, B 133k (first run 57k, 102k); 61 min.

**Bench puzzles, mean regret** (dull skipped, 95% bootstrap):

| evaluator | h0 | h1 | h2 | h3 |
|---|---|---|---|---|
| A, first run | 0.007 | 0.051 | 0.111 | 0.119 |
| B, first run | 0.016 | 0.053 | 0.080 | 0.086 |
| **A, bounds** | 0.004 | 0.038 [0.016, 0.070] | 0.068 | 0.084 |
| **B, bounds** | 0.004 | 0.043 [0.017, 0.074] | **0.030** [0.005, 0.064] | 0.057 |
| night s1 r10 | 0.000 | 0.030 [0.010, 0.056] | 0.072 | 0.050 |
| heuristic | 0.000 | 0.060 | 0.032 | 0.065 |

**The bench games' other positions** (`db/solved.sqlite`, 600 non-dull
decisions per `turns_left`, every option exact, one sample for all five):

| turns_left | new A | **new B** | old A | old B | night | heuristic |
|---|---|---|---|---|---|---|
| 1 | 0.053 | **0.028** [0.018, 0.042] | 0.055 | 0.044 | 0.031 | 0.094 |
| 2 | 0.031 | **0.032** [0.020, 0.046] | 0.044 | 0.037 | 0.031 | 0.060 |

**Reading.**
- **Training on the positions bounds unlock closes the gap.** Arm B, which
  never saw an early-fight position or a game outcome, now picks as well
  as the night's net on the bench games' positions one and two turns out
  (0.028 / 0.032 against 0.031 / 0.031); the first run's B was 0.044 /
  0.037 there. On the bench puzzles it is the best evaluator at horizon 2
  (0.030; the night's net 0.072) and within the noise of the night's net
  at horizon 1. So the first run's failure was mostly the database's
  population, not the net.
- **The paused states matter now.** In the first run A and B picked alike;
  here B is clearly better one turn out (0.028 against A's 0.053 on the
  bench games' positions). With long-fight positions in the data, the
  value of the state right after End turn (what search scores) is what
  separates good picks.
- **Still not a player:** tight fights paired against the heuristic are
  -0.12 / -0.11 for B (it never saw an early position). Exact labels near
  the end have to be combined with the rest of the curriculum, not used
  alone.

## Curriculum Amendment 3, one-round check (2026-10-29)

`scripts/round_check.py`: the night's last round (s1 r10: its window, the
frontiers of the nets that played it, seed 1) retrained with the
amendment's exact labels (paused states, the draw split half at the last
turn and half one turn out or more) against a copy of `db/bounds.sqlite`,
compared with s1 r10's own net. Below-normal priority; results in
`runs/round-check/cap*/results.json`.

| | cap 150k | cap 400k | night s1 r10 |
|---|---|---|---|
| exact value examples (decisions + paused states) | 79k | 210k | 9.2k |
| training | 7 min | 23 min | |
| val MSE | 0.1641 | 0.1555 | 0.1642 |
| bench puzzles h1 | 0.027 | 0.022 | 0.030 |
| bench puzzles h2 | 0.025 | 0.046 | 0.072 |
| bench games' positions, 1 turn out | 0.024 | 0.022 | 0.031 |
| bench games' positions, 2 turns out | 0.036 | 0.028 | 0.031 |
| frontier | 1 | 1 | 1 |

Paired against s1 r10 (new - night, 95% interval):

| | cap 150k | cap 400k |
|---|---|---|
| positions, 1 turn out | -0.007 [-0.019, 0.004] | -0.009 [-0.020, 0.001] |
| positions, 2 turns out | +0.005 [-0.004, 0.015] | -0.002 [-0.010, 0.004] |
| puzzles h2 | -0.047 [-0.108, -0.000] | -0.026 [-0.075, 0.005] |
| tight fights, train / held-out | -0.011 [-0.037, 0.014] / +0.009 [-0.018, 0.036] | -0.015 [-0.042, 0.013] / -0.011 [-0.041, 0.019] |

Tight fights against the heuristic (Amendment 5's lead): 150k -0.005 /
+0.024, 400k -0.008 / +0.004, s1 r10 +0.007 / +0.015.

**Verdict: neither cap passes.** Both are level one turn out (a little
better, the interval just reaching 0) and neither is clearly better two
turns out on the bench games' positions; the bench puzzles' h2 gain at
150k (0.025 against 0.072) rests on ~100 puzzles and doesn't show on the
600 positions. The tight fights don't move.

**Reading.**
- More exact labels near the end help the net's picks there a little, and
  the 400k net fits the validation set better, but none of it reaches the
  tight fights: those are decided over whole fights, and the labels further
  from the end are still single game outcomes.
- The trusted zone can't grow from this. `regret_max` 0.01 at horizon 1 is
  out of reach for every net measured (best: 0.022), so rung 3 stays
  within one turn of the end whatever the exact labels do.
- One round is a limited test: a night would retrain every round with the
  growing database. But this check retrained with ~8x the exact labels the
  night's round had, and the tight-fight lead didn't change.

**Frontier 2 (`--frontier 2`, cap 150k).** Both datasets labelled as if
their players' trusted zones reached two turns from the end (rung 3 out to
distance 2: 94k search labels against 70k, 52k outcomes against 76k).
Bench games' positions 0.032 / 0.032 one and two turns out (paired with
s1 r10: +0.001 [-0.011, 0.012], +0.002 [-0.007, 0.010]); bench puzzles
h1 0.024, h2 0.030; tight-fight lead -0.016 / +0.020. No better than
150k at frontier 1, and a little worse one turn out (0.032 against 0.024).
Loosening `regret_max` alone wouldn't help.

**Tight fights at 100 seeds per cell** (the bench's 116 calibrated cells,
11,600 fights, ~20 s per player; the bench uses 10 seeds). Heuristic
0.506 / 0.501 (train / held-out), so the calibration still holds. Lead
over the heuristic, fights paired, 95%:

| net | train | held-out |
|---|---|---|
| night s1 r10 | +0.009 [-0.001, 0.018] | -0.009 [-0.020, 0.001] |
| night s1 r4 | +0.013 [+0.003, 0.023] | -0.022 [-0.033, -0.011] |
| check, 150k | +0.014 [+0.005, 0.024] | -0.016 [-0.027, -0.005] |
| check, 400k | +0.017 [+0.007, 0.027] | -0.031 [-0.041, -0.020] |
| check, frontier 2 | +0.004 [-0.006, 0.014] | -0.024 [-0.034, -0.013] |

- Every net is a little ahead on the training cards and a little behind on
  the held-out ones; more exact labels push both further (400k: +0.017 /
  -0.031). s1 r4's +0.035 held-out lead on the 10-seed set was noise.
- Those intervals treat every fight as independent, but the 100 fights of
  a cell share their deck, encounter and HP. Averaged per cell first, the
  interval is about +-0.02-0.03 (s1 r10: +0.009 [-0.012, 0.029] over 61
  cells, -0.009 [-0.034, 0.016] over 55). With few cells, the number of
  cells limits the certainty, not the seeds: more seeds per cell can't
  narrow it below that.

## Tight fights v2 (2026-10-29)

`docs/specs/tight-fights-v2.md`: `data/bench/tight2.json`, the rounds'
tight fights from now on. Cells are a drawn deck (3-15 extra cards;
held-out decks with at least 2 held-out cards) x one encounter, each at the
start HP where search + heuristic wins ~50%; 20 seeds per cell; intervals
over cells.

**Calibration** (`calibration2.json`, 8 threads, 4.6 h with other work
sharing the machine, then a 6-min top-up): 2,305 cells tried, 1,110 kept,
963 left out (most still won at 1 HP, or "steep": the win rate jumps past
the band between neighbouring HPs). Cultist and two_louse are the easy
ones: 82-90% of their decks still win at 1 HP, so the first run's 6 redraw
batches left them short and the top-up (`--topup2`) filled them. With v1's
family cells, 616 train cells (12,320 fights) and 610 held-out cells
(12,200). Median start HP 5-6.

**Calibration holds on fresh seeds:** search + heuristic wins 0.497
[0.488, 0.507] on train, 0.506 [0.496, 0.515] on held-out (per-cell).

**The night's nets and the check nets** (`runs/tight2/rescore.json`):
lead over the heuristic, paired, interval over cells (95%).

| net | train | held-out |
|---|---|---|
| s0 r5 | +0.020 [+0.012, +0.029] | +0.003 [-0.006, +0.012] |
| s0 r6 | +0.021 [+0.012, +0.029] | +0.003 [-0.006, +0.011] |
| s0 r7 | +0.009 [+0.002, +0.017] | -0.012 [-0.021, -0.003] |
| s0 r8 | +0.025 [+0.017, +0.032] | +0.005 [-0.004, +0.013] |
| s0 r9 | +0.018 [+0.010, +0.025] | +0.003 [-0.005, +0.011] |
| s0 r10 | +0.013 [+0.005, +0.022] | -0.004 [-0.013, +0.005] |
| s1 r1 | +0.020 [+0.011, +0.028] | +0.007 [-0.002, +0.016] |
| s1 r2 | +0.033 [+0.026, +0.041] | **+0.013 [+0.004, +0.022]** |
| s1 r3 | +0.019 [+0.012, +0.027] | +0.004 [-0.004, +0.013] |
| s1 r4 | +0.027 [+0.020, +0.035] | **+0.011 [+0.002, +0.020]** |
| s1 r5 | +0.016 [+0.008, +0.023] | +0.000 [-0.008, +0.009] |
| s1 r6 | +0.016 [+0.008, +0.024] | +0.003 [-0.006, +0.011] |
| s1 r7 | +0.022 [+0.014, +0.031] | **+0.013 [+0.004, +0.021]** |
| s1 r8 | +0.023 [+0.016, +0.031] | +0.003 [-0.005, +0.012] |
| s1 r9 | +0.010 [+0.002, +0.018] | -0.010 [-0.019, -0.001] |
| s1 r10 | +0.027 [+0.019, +0.035] | **+0.010 [+0.001, +0.018]** |
| check, 150k | +0.023 [+0.015, +0.031] | +0.008 [-0.001, +0.017] |
| check, 400k | +0.025 [+0.017, +0.033] | -0.003 [-0.012, +0.006] |
| check, frontier 2 | +0.022 [+0.014, +0.030] | +0.008 [-0.001, +0.017] |

- **Size: passes.** The per-cell half-width is 0.0083 at the median,
  0.0094 at most (the spec's limit 0.012; stop point 0.015). Counting
  fights as independent would give ~0.006: a cell's fights aren't.
- **Every net is ahead on the training cards** (+0.009 to +0.033, all
  clear of 0). On the held-out cards most are level, and **four meet the
  gate** (bold): s1 r2, r4, r7, r10, all from seed 1. The old set
  couldn't see a lead this size.
- **The passes are close.** Before the top-up (which gave every held-out
  cell new test seeds and added 20 cells) the same nets read +0.010,
  +0.008, +0.008, +0.002 on held-out, and only s1 r2 passed: new seeds
  alone move a held-out lead by about 0.004 (one sd of the seed part,
  0.36 / sqrt(12,200) = 0.003). Seed 1's nets lead seed 0's on held-out
  by about 0.006 on average (+0.005 against 0.000).
- More exact labels still don't help: the 400k check net is the furthest
  behind on held-out of the three checks.
- **Time:** 24,520 fights take a net 207 s at the median (118/s) and
  the heuristic 155 s, with other work loading the machine. The sweep
  now plays every seed each round (~4 min; `MONO_MIN` 5): thinning to fit
  2 min would keep 7 of 20 seeds a cell, and by the measured spread
  (between cells sd 0.06-0.08 of the lead; within a cell 0.35-0.36 per
  fight) the held-out interval would widen to ~0.013.

## Rung 4 check: play-out averages as labels (2026-10-29)

`docs/specs/rung4-check.md`, `scripts/rung4.py`. Rung 4 labels a position
that would take the game's ending (rung 5) with the average of the ending
and K games played on from it by the net that played the game
(`sts.play_on`, fresh chance seeds). Same quantity as the ending, less
noise.

**Pre-check** (`runs/rung4/precheck.json`; 2,000 rung-5 positions from s1
r10's own games, 400 per distance band, 16 play-outs each by s1 r9's net,
2.4 min):

| | ending - play-out mean | σ² (one ending's noise) | err² (net vs its play's average) |
|---|---|---|---|
| overall | -0.015 [-0.032, +0.003] | 0.133 | 0.097 [0.086, 0.110] |
| 1 turn out | -0.049 [-0.078, -0.023] | 0.061 | 0.086 [0.056, 0.121] |
| 2 | -0.022 [-0.056, +0.011] | 0.096 | 0.095 [0.069, 0.125] |
| 3 | -0.002 [-0.036, +0.031] | 0.135 | 0.084 [0.065, 0.104] |
| 4-5 | -0.020 [-0.064, +0.027] | 0.172 | 0.092 [0.070, 0.116] |
| 6+ | +0.019 [-0.029, +0.066] | 0.199 | 0.129 [0.102, 0.158] |

- **Play-outs reproduce the games.** Per band the ending is biased,
  because a band is defined by when the game actually ended: a paused
  End-turn state one turn from the end is one where the player then died,
  while play-outs from it can survive (and games that lasted long are
  ones the player survived: +0.019 at 6+). Weighted by the bands' shares
  of all rung-5 examples the gap is -0.013 [-0.031, +0.005]. Paused states
  were checked exactly: decoding one and resolving chance with seed s
  gives the same state as decoding its decision state and taking the
  action (150 states x 5 seeds, all identical).
- **The net is clearly off from its own play's averages** (err² 0.08-0.13
  in every band, against 0.13 of noise in one ending), so there was
  something to fix. 269 play-outs/s on 8 threads: K = 12 fits the hour.

**One-round check** (`runs/rung4/check.json`): s1 r10's round retrained
twice against `db/bounds-check.sqlite`, A with the night's labels, B with
rung 4 at K 12 on its 76k rung-5 examples (play-outs: 53 min).

| | A (endings) | B (rung 4) |
|---|---|---|
| val MSE (single endings) | 0.177 | 0.150 |
| training (early stopping) | 4 min | 16 min |
| err² on the pre-check's positions | 0.099 [0.088, 0.111] | 0.046 [0.039, 0.054] |
| lead over the heuristic, train | +0.009 [+0.001, +0.017] | +0.027 [+0.019, +0.035] |
| lead over the heuristic, held-out | -0.003 [-0.012, +0.006] | **+0.013 [+0.004, +0.021]** |

**B - A, paired per cell: train +0.018 [+0.012, +0.023], held-out +0.016
[+0.010, +0.021]. Passes** (the spec's rule: above 0 on held-out, not
below on train). B meets the gate on its own.

- Less noisy labels cut the net's error against its own play's averages
  (0.099 to 0.046) and let training run 4x longer before validation stops
  it. The err² gap flatters B somewhat: both arms trained on the
  pre-check's positions, and B's labels there reuse 12 of the 16
  pre-check play-out seeds (the review simulates up to ~0.015 of the 0.053
  gap from that). The pass rule uses the tight fights, which this doesn't
  touch.
- **Caveat: the baseline.** A is weaker than the night's own s1 r10 net
  (same config; paired per cell: train -0.018 [-0.024, -0.011], held-out
  -0.012 [-0.018, -0.007]) and B is level with it (-0.000 [-0.006,
  +0.006], +0.003 [-0.002, +0.009]).

**Rerun against the night's own database** (`runs/rung4-nightdb/`).
`db/train.sqlite` is the night's database (2,893,615 states + 607,446
trivial rows = the 3,501,061 s1 r10 recorded); `bounds-check` is the
bounds-walked copy, half the states. Same check, same play-out caches:

| | A (endings) | B (rung 4) |
|---|---|---|
| exact lookups / drawn | 204 / 9,262 (night: 204 / 9,224) | same |
| val MSE | 0.171 (night: 0.164) | 0.151 |
| training | 7 min | 8 min |
| err² on the pre-check's positions | 0.078 | 0.052 |
| lead, train / held-out | +0.021 / +0.003 | +0.027 / +0.008 |

**B - A: train +0.006 [+0.0005, +0.012], held-out +0.005 [-0.0004,
+0.011]: fails the spec's rule, narrowly.**

- **The first check's +0.017 was mostly the database.** On the
  bounds-walked copy, A stopped training after 4 minutes and came out
  weak; rung 4 mostly made up for that. On the night's own setup, rung 4
  helps a little: about +0.005 on both halves, err² down by a third.
- **Retraining is noisy.** Against nearly the night's own data (38 more
  exact draws, after the database's later cost repair and compaction), A
  lands at val MSE 0.171 against the night's 0.164 and a lead lower by
  ~0.007. One retrain per arm can't separate a 0.005 effect from that
  training noise.

**Over training seeds** (Amendment 1; `runs/rung4-nightdb/check.json`,
`db/train.sqlite`, K 12, training seeds 1, 101, 201; 41 min):

| seed | val MSE A / B | err² A / B | lead A, train / held-out | lead B, train / held-out | B - A train | B - A held-out |
|---|---|---|---|---|---|---|
| 1 | 0.171 / 0.151 | 0.078 / 0.052 | +0.021 / +0.003 | +0.027 / +0.008 | +0.006 [+0.001, +0.012] | +0.005 [-0.000, +0.011] |
| 101 | 0.168 / 0.155 | 0.092 / 0.077 | +0.011 / -0.012 | +0.008 / -0.017 | -0.003 [-0.009, +0.004] | -0.005 [-0.013, +0.002] |
| 201 | 0.157 / 0.152 | 0.076 / 0.065 | +0.020 / -0.001 | +0.020 / +0.005 | -0.000 [-0.005, +0.005] | +0.006 [+0.001, +0.011] |

**Averaged over seeds, per cell: train +0.001 [-0.002, +0.004],
held-out +0.002 [-0.002, +0.006]. Rung 4 fails.**

- **Rung 4 gives cleaner values but no better play.** At every seed it
  lowers val MSE and the net's error against its own play's averages, but
  the tight-fight lead doesn't move. The tight fights aren't limited by
  how accurately the net values positions under its own play.
- **Training luck is as large as the effects we've been chasing.** A's
  lead varies by sd 0.006 (train) / 0.0075 (held-out) across training
  seeds; the per-cell intervals only cover the fights' noise. The four
  night nets that narrowly clear the gate on tight fights v2 (held-out
  lower ends +0.001 to +0.004) are within this spread, and so were the
  earlier single-retrain comparisons (Amendment 3's caps, frontier 2).

## Seed check: do the night's gate passes hold up? (2026-10-29)

`scripts/seed_check.py` (`docs/specs/seed-check.md`, idea #65): the four
10-28 night rounds whose net clears the gate on tight fights v2 (s1 r2,
r4, r7, r10) retrained at training seeds 1, 101, 201, each against its own
database (`db/train.sqlite` cut at its `db_rows`; r10 reuses the rung-4
check's arm A). Rung counts (search / outcome / exact) equal each round's
own in all nine new retrains; the heuristic's replay equals the stored
fights. 107 min. Results `runs/seed-check/check.json`.

| round | averaged lead train | averaged lead held-out | sd over seeds train / held-out | night net train / held-out | holds up |
|---|---|---|---|---|---|
| r2 | +0.027 [+0.020, +0.034] | +0.006 [-0.002, +0.014] | 0.006 / 0.004 | +0.033 / +0.013 | no |
| r4 | +0.020 [+0.014, +0.027] | +0.003 [-0.006, +0.011] | 0.007 / 0.005 | +0.027 / +0.011 | no |
| r7 | +0.012 [+0.005, +0.020] | -0.004 [-0.013, +0.004] | 0.003 / 0.003 | +0.022 / +0.013 | no |
| r10 | +0.017 [+0.010, +0.024] | -0.003 [-0.011, +0.005] | 0.006 / 0.008 | +0.027 / +0.010 | no |

Per seed, held-out leads: r2 +0.009 / +0.002 / +0.008; r4 +0.008 /
-0.001 / +0.001; r7 -0.003 / -0.007 / -0.003; r10 +0.003 / -0.012 /
-0.001.

**No round holds up: the night does not meet the gate.** The passes were
training luck, and the curriculum is flat on this measure.

- **Train cards yes, held-out cards no.** Every round's averaged train
  lead is clearly above 0 (+0.012 to +0.027); no round's held-out lead
  is. The nets beat search + heuristic on the cards they trained on and
  are level with it on held-out cards. What limits the gate is
  generalisation to unseen cards, not label quality (rung 4, Amendment
  3's labels and frontier 2 didn't move it either).
- **Later rounds aren't better.** Held-out by round: r2 +0.006, r4
  +0.003, r7 -0.004, r10 -0.003; train likewise peaks at r2. Rounds past
  2 add nothing measurable.
- **The night nets sit above every retrain of their round** (held-out
  +0.010 to +0.013 against retrain means of -0.004 to +0.006). That is
  what picking them for passing predicts: the best of ~20 rounds by a
  noisy score, with sd ~0.005, lands ~1.5-2 sd high. The retrains also
  draw a slightly different 50k of exact examples (compaction, see the
  spec), which can't be told apart from that here.
- **The spread undercounts the luck.** A round's three retrains share one
  exact draw (`exact_order`'s fixed seed over the compacted database), so
  their sd covers the training seed only, not which exact examples were
  drawn. The whole luck of a retrain is larger, and the night-vs-retrain
  gap may be partly draw luck. That only makes a hold-up harder, so the
  verdict stands. (Point raised by the 22:07 manager run.)

## Warm start on Silent: the learning curve (2026-10-30)

`scripts/curve.py` (spec `docs/specs/warm-start.md`, now folded), full
table in `results/warm-start/curve.json`. Three starts fine-tuned on
Silent games at 0 / 500 / 2,000 / 10,000 games, 3 training seeds each,
replay share 0.5 of Ironclad data: `warm_effects` (from
`models/value_effects.pt`), `warm_ids` (from `models/value_ids.pt`, same
training data, ids features) and `fresh_effects` (random init). Judged on
Silent value MSE (1,000 test games per tier) and the calibrated Silent
tight set (tier A, tier B; ~0.5 for the heuristic by construction). Run
time 5,426 s over two processes (B's ids cells were cached first); 0
stalls in every cell but one stall in one fresh 2,000-game cell.

**Gate: FAIL.** The thesis was that effects features transfer better than
ids after fine-tuning. `warm_effects - warm_ids` Silent MSE is -0.0021 to
0.0000 at every size and tier, every interval crosses 0, and every row is
within training luck (seed sd 0.0014-0.0052). The floor rows pass (size 0
vs random: +0.38 tier A, +0.30 tier B).

Means over 3 seeds (win = tight-set win rate):

| start | games | MSE A | MSE B | MSE Ironclad | win A | win B | tight2 train win |
|---|---|---|---|---|---|---|---|
| warm_effects | 0 | 0.099 | 0.294 | 0.057 | 0.506 | 0.438 | 0.479 |
| warm_ids | 0 | 0.130 | 0.337 | 0.058 | 0.482 | 0.377 | 0.428 |
| fresh_effects | 0 | 1.154 | 1.052 | 1.039 | 0.122 | 0.133 | 0.197 |
| warm_effects | 500 | 0.070 | 0.100 | 0.058 | 0.499 | 0.481 | 0.466 |
| warm_ids | 500 | 0.072 | 0.102 | 0.058 | 0.481 | 0.483 | 0.448 |
| fresh_effects | 500 | 0.078 | 0.115 | 0.135 | 0.469 | 0.459 | 0.436 |
| warm_effects | 2,000 | 0.065 | 0.093 | 0.056 | 0.494 | 0.485 | 0.460 |
| warm_ids | 2,000 | 0.066 | 0.093 | 0.056 | 0.498 | 0.496 | 0.431 |
| fresh_effects | 2,000 | 0.066 | 0.101 | 0.119 | 0.488 | 0.470 | 0.442 |
| warm_effects | 10,000 | 0.057 | 0.088 | 0.057 | 0.541 | 0.517 | 0.480 |
| warm_ids | 10,000 | 0.058 | 0.088 | 0.056 | 0.536 | 0.512 | 0.456 |
| fresh_effects | 10,000 | 0.057 | 0.091 | 0.128 | 0.487 | 0.472 | 0.439 |

What it says:
- **Effects features help only with zero Silent data.** Unchanged parents:
  effects MSE 0.099 / 0.294 vs ids 0.130 / 0.337, and win +0.024 (A) and
  +0.060 (B, interval 0.041-0.079). Once fine-tuned on even 500 games
  the two are the same. For goal 1 the zero-shot row is the one that
  matters (new content arrives without games), so the effects encoding
  earns its keep there and nowhere else; tier B (cards further from
  Ironclad's) shows the larger zero-shot gap.
- **Warm start beats fresh at every size on play, not on MSE.** At
  10,000 games tier-A MSE is equal (0.057 both), yet warm wins +0.054
  (0.038-0.070) on A and +0.045 on B. Value MSE misses what decides play;
  another reason the champion ladder (Next 3) judges by play.
- **No forgetting.** Warm nets keep Ironclad MSE at the parent's 0.057
  and tight2-train win at 0.46-0.48 (parent 0.479); fresh nets train on
  Silent games only (no replay), so their Ironclad MSE stays 0.12-0.14.
- **Fine-tuning barely beats the heuristic on Silent.** Best is 0.54 / 0.52
  on sets calibrated to ~0.5 for the heuristic; Silent's seed sd here
  is ~0.03 in win rate, so read the win columns as direction only.
- Cost note: both processes played the 30,000-game "both" set (a cache
  race, ~10 min wasted); the job queue now keeps one run per job.

## Boss lead per boss (tight-bosses step 3; job 0015, read 18:05 by manager run 17:33)

`scripts/analysis/boss_lead.py`, output `results/bosses/lead.json`. The
seed-check round-2 retrains (seeds 1, 101, 201) against the heuristic on
`tight_bosses` (Hexaghost, The Guardian: 37 cells per boss and half, 20
seeds each) and on tight2's Slime Boss cells, paired by fight. Lead =
mean of the three nets minus heuristic; interval over cells. MDE for a
3-seed mean against a fixed player: ~2.8 x 0.022 / sqrt(3) = 0.036 train,
~0.040 held-out (boss seed sd 0.022 / 0.025).

| half | boss | heuristic | nets | lead [95%] | per seed |
|---|---|---|---|---|---|
| train | Slime Boss (trained on) | 0.509 | 0.646 | **+0.137** [+0.104, +0.170] | +0.139 +0.145 +0.128 |
| train | Hexaghost (unseen) | 0.526 | 0.595 | **+0.069** [+0.025, +0.113] | +0.084 +0.077 +0.047 |
| train | The Guardian (unseen) | 0.501 | 0.569 | **+0.068** [+0.011, +0.125] | +0.036 +0.057 +0.111 |
| held-out | Slime Boss | 0.466 | 0.539 | **+0.073** [+0.020, +0.126] | +0.094 +0.055 +0.070 |
| held-out | Hexaghost | 0.480 | 0.438 | -0.042 [-0.119, +0.035] | -0.032 -0.059 -0.034 |
| held-out | The Guardian | 0.478 | 0.347 | **-0.131** [-0.193, -0.069] | -0.136 -0.154 -0.103 |

What it says:
- **Unseen boss with known cards: the nets keep half their lead.** On train
  cards the two new bosses give +0.07 each against Slime Boss's +0.14, all
  three seeds positive. Some of what the nets learned on Slime Boss is
  general boss play, not Slime Boss alone. That also answers the review's
  worry that the boss lead was only the heuristic's weakness on Slime Boss:
  the heuristic is no worse on the new bosses (0.50-0.53, calibrated near
  0.5 like Slime Boss), and the nets still lead there.
- **Unseen boss and unseen cards together: the nets lose,** clearly on The
  Guardian (-0.131, all seeds below -0.10), not significantly on Hexaghost.
  Unseen cards alone don't do it (held-out Slime Boss +0.073), nor does the
  unseen boss alone. The two gaps compound. For goal 1 this is the most
  direct evidence so far: generalising to new content fails when two kinds of
  novelty meet.
- The Guardian is the boss whose mechanic (Mode Shift: a damage counter
  that flips it into a defensive mode with Sharp Hide) the effects features
  can't see at all (decisions.md "Act-1 bosses merged"). Hexaghost's Burn
  turn-end damage is also unencoded, and it sits between the two. A net
  that can't see the counter can't plan around the shift; the heuristic
  doesn't see it either, but doesn't rely on learned patterns that the
  shift breaks. Hypothesis, not tested: encoding Mode Shift should close
  most of the Guardian gap. Test: give ModeShift a feature dimension and
  re-run on the same cells with nets trained... which needs Guardian in
  training, so the cleaner test is a probe of the net's value before and
  after the shift.
- **On the new bosses the lead grows with start HP** (cell lead vs cell HP:
  correlation +0.54 / +0.09 train Guardian / Hexaghost, +0.50 / +0.44
  held-out); Slime Boss shows none (-0.15 / 0.00). Held-out Hexaghost cells
  starting at <= 20 HP (14 cells): lead -0.19. Low HP plus unfamiliar
  content is where the nets fall apart, which fits Next 5's low-HP
  coverage gap.
- Card-level slices (cells holding a given card) are 4-9 cells each, too
  noisy to name a culprit; Demon Form appears among the worst cards in
  both held-out new-boss slices, a scaling power whose pay-off comes late.

## Champion ladder, first three tests (jobs 0020-0022; read 22:10 by manager run 22:08)

`ladder.py test`, fresh stratified fights (not the tight-fight cells), one-turn
search, SPRT with H1 lead >= 0.01, alpha = beta = 0.05. Results in
`results/ladder/tests/000{1,2,3}.json`.

| test | candidate vs champion | verdict | pairs | lead | held-out | train |
|---|---|---|---|---|---|---|
| 0001 | r2 s1 vs heuristic | pass, promoted | 1,150 | +0.037 | +0.011 [-0.017, +0.038] | +0.064 [+0.031, +0.098] |
| 0002 | r2 s101 vs r2 s1 | fail | 1,305 | -0.013 | -0.009 | -0.017 |
| 0003 | r2 s201 vs r2 s1 | fail | 4,090 | -0.000 | +0.002 | -0.002 |

By fight type in 0001: boss +0.132 (train +0.21, held-out +0.05), elite
+0.068 (train +0.144, held-out -0.009), hallway +0.020.

- The r2 s1 net is the first champion. Its win is the train half
  (strength); its held-out lead (+0.011, interval across 0) only clears the
  held-out rule's floor of -0.005. Same picture as the seed check: strong on
  training cards, level on unseen ones. The lead here is bigger than on
  tight fights (+0.027 / +0.006 averaged over seeds) because the ladder's
  fights are not tuned to a 50% win rate and include bosses, where the nets
  lead most.
- Stop points fit the replay: a lead of 3.7x d1 stops early (1,150 pairs);
  a true null wanders to 4,090; a slightly worse seed fails at 1,305. The
  two same-recipe seeds don't beat the champion, as expected for seed
  twins (seed sd ~0.007).
- Not yet checked: the boss lead against the heuristic with two-turn search
  (see the depth-pilot doc: two-turn heuristic gains +0.09-0.10 on bosses,
  close to the champion's held-out boss lead). Next ladder candidates:
  rung-4 B, the best lean r2 net, and an ensemble evaluator.

## Lean loop: no solve step, and a low-HP start slice (jobs 0023-0028; read 23:20 by manager run 22:08)

`docs/specs/lean-loop.md`: rounds 1-2 from the night's shared round 0, no
solve step and (since the bosses merge emptied the current database
version) no exact labels at all; `lean-lowhp` also starts 25% of later
self-play games at 1-8 HP. Each run (two rounds) took ~45-50 min with two
running at once. r2 leads over the heuristic on tight2, mean over three
seeds (sd over seeds), from `scripts/analysis/lean_read.py`:

| half | slice | seed check r2 (solve + DB) | lean | lean-lowhp |
|---|---|---|---|---|
| train | all | +0.027 (0.006) | +0.017 (0.012) | +0.022 (0.006) |
| train | hallway | +0.006 | -0.005 | +0.003 |
| train | elite | +0.067 | +0.054 | +0.056 |
| train | boss | +0.137 | +0.139 | +0.125 |
| held-out | all | +0.006 (0.004) | +0.002 (0.011) | +0.001 (0.002) |
| held-out | hallway | -0.002 | -0.005 | -0.003 |
| held-out | elite | +0.012 | +0.005 | -0.005 |
| held-out | boss | +0.073 | +0.064 | +0.054 |
| held-out | start HP 1-8 | -0.001 | -0.006 | -0.004 |

Reading:
- **Dropping the solve step and the database costs little, if anything.**
  lean-lowhp is 0.005 below the seed check on train (about 1 se of the
  difference), lean 0.010 (~1.3 se); held-out is level. Below the spec's
  MDE (~0.016), so "no loss" isn't proven either: the bound is that the
  solve step buys at most ~0.02 on train. Boss and elite leads, where the
  nets' strength lives, are kept. Exact labels at round 2 were not what
  made these nets strong.
- **The low-HP slice does not help where it was aimed.** Held-out fights
  starting at 1-8 HP: -0.004 against lean's -0.006. On train it lowers the
  seed spread (sd 0.006 vs 0.012) and lifts hallway a little (+0.008,
  ~1 se). Not enough to call; it doesn't hurt.
- One lean seed is an outlier (train sd 0.012 is twice the seed check's),
  so judging recipes on fewer than three seeds stays unsafe.
- What it changes: new experiments use the lean recipe (no solve step), as
  the threshold-rows spec's step 5 already does. `learn.py`'s defaults stay
  until a run judged on the ladder confirms it.

## Coverage pilot: training card kinds 4 / 10 / 21 (jobs 0029-0037; read 00:20 2026-10-31 by manager run 00:07)

`docs/specs/coverage-pilot.md`; read with `scripts/analysis/coverage_read.py`.
Round-1 lead over the heuristic on tight2, mean over 3 seeds (seed sd in
brackets). Each cover arm has a fresh 5,000-per-group round 0 per seed;
`lean` is the lean loop's r1 (20,000 per group, one shared round-0 net).

| half | fights | cover4 | cover10 | cover21 | lean (20k) |
|---|---|---|---|---|---|
| train | all | -0.054 (0.005) | -0.023 (0.020) | -0.010 (0.017) | +0.022 (0.014) |
| train | hallway | -0.066 | -0.027 | -0.027 | +0.004 |
| train | elite | -0.028 | -0.019 | +0.014 | +0.054 |
| train | boss | +0.006 | +0.014 | +0.098 | +0.132 |
| held-out | all | -0.074 (0.011) | -0.039 (0.033) | -0.025 (0.014) | +0.003 (0.011) |
| held-out | hallway | -0.076 | -0.031 | -0.026 | -0.000 |
| held-out | elite | -0.075 | -0.068 | -0.039 | -0.003 |
| held-out | boss | -0.054 | -0.029 | +0.025 | +0.063 |

Reading:

- **Coverage pays, with falling returns.** Held-out lead rises 4 -> 10
  kinds by +0.035 (beyond the MDE even at the larger seed sd below) and
  10 -> 21 by +0.014 (within noise): per doubling of kinds, about +0.025
  then +0.013. Not flat, so generated content moves ahead of the fidelity
  specs (Next 6), but it is not a large lever at this data size.
- **It raises both halves equally.** Train minus held-out is 0.020 /
  0.016 / 0.015 (lean 0.019). More kinds made the nets stronger overall
  (the train half is mostly unseen for cover4 too), not specifically
  better at generalising. Breadth beat depth at fixed data: cover4 sees each
  kind ~5x as often and is worst everywhere.
- **Data size looks bigger than coverage.** cover21 is the lean recipe at
  5k round-0 games instead of 20k; lean leads it by +0.032 train / +0.028
  held-out, more than the whole 10 -> 21 step. But lean's three seeds share
  one round-0 net, so that gap could hold some round-0 luck and it ran on
  the old layout: `docs/specs/data-scaling.md` (jobs 0045-0057, 5k / 20k /
  40k, fresh round 0s) tests it.
- **Seed sd with fresh round 0s is about twice the old figure.** cover21's
  sd is 0.017 / 0.014 (train / held-out), cover4's 0.005 / 0.011, against
  0.0066 / 0.0076 measured with a shared round 0 (seed check). Earlier
  MDEs used the smaller number; comparisons that also vary round 0 need
  ~2x the seeds. cover10's large sd (0.020 / 0.033) includes subset luck
  (one seed's 10 kinds did much better: -0.004 held-out).
- Boss leads track data, not coverage: train bosses +0.006 / +0.014 /
  +0.098 / +0.132, so most of the nets' boss lead appears only past 10 kinds
  and grows with data.

## Round 0 vs round 1 on tight2 (job 0041b; read 03:00 2026-10-31 by manager run 02:07)

`score_r0.py read cover4 cover10 cover21`: lead over the heuristic of each
run's r0 and r1 net, mean over 3 seeds per arm, r1 - r0 per seed in brackets.

| arm | train all r1-r0 | held-out all r1-r0 | held-out elite | held-out boss |
|---|---|---|---|---|
| cover4 | +0.017 [+0.007 +0.052 -0.007] | +0.015 [+0.009 +0.044 -0.007] | +0.029 | -0.003 |
| cover10 | +0.006 [+0.022 +0.009 -0.012] | +0.015 [+0.025 +0.030 -0.010] | +0.046 | +0.026 |
| cover21 | +0.024 [+0.049 +0.018 +0.004] | +0.025 [+0.054 +0.016 +0.006] | +0.021 | +0.008 |

Reading:
- One self-play round adds about +0.016 (train) / +0.018 (held-out) over
  round 0, positive in 7 of 9 seeds on held-out; with a per-seed sd of
  ~0.02, the 9-run mean has se ~0.007, so ~2.5 se. Not within 0.01, so
  **self-play rounds stay in the recipe** (Next A's rule). The gain is
  largest on elites (+0.02-0.05); bosses move least.
- Spread between seeds of the *same* arm at r0 is large (cover21 held-out
  raw win rate 0.417 / 0.459 / 0.491), bigger than the r0 -> r1 gain:
  round-0 luck is the biggest single noise source, which the data-scaling
  read (paired by seed index) should account for.
- The night r0 (0.521 / 0.512 raw win rate) is above every cover r0 (it
  trained on 20k games, all kinds): consistent with the data-size lever.

## Demon Form probe (job 0041c; read 03:00 2026-10-31 by manager run 02:07)

`scripts/analysis/demon_form_probe.py`: 156 held-out boss fights whose deck
holds Demon Form (4 per cell, 39 cells: Hexaghost, The Guardian from
`tight_bosses`, Slime Boss from tight2), each played by the heuristic and
the three seed-check r2 nets with one-turn search. "Gain" = best
Demon-Form option's value minus best other option's, on the heuristic's
first offer of Demon Form in each fight (same states for every evaluator).

| player | won | DF played in fights offered | DF share of offers | gain on first offer (mean) | would play at first offer |
|---|---|---|---|---|---|
| heuristic | 0.442 | 65% | 41% | -0.007 | 41% |
| r2 s1 | 0.250 | 12% | 6% | -0.147 | 6.5% |
| r2 s101 | 0.276 | 17% | 8.5% | -0.089 | 6.5% |
| r2 s201 | 0.276 | 14% | 7% | -0.138 | 6.5% |

Won by boss: Hexaghost heuristic 0.54 vs nets 0.07-0.11; Guardian 0.39 vs
0.17-0.22; Slime Boss 0.45 vs 0.39-0.45.

Reading:
- **The nets under-play Demon Form badly.** On the same states the heuristic
  would play it 41% of the time; the nets 6.5%, and they value it 0.09-0.15
  below their best alternative (score scale 0-2), far outside noise. All
  three seeds agree. When a net does play it, it wins 0.53-0.71 (confounded
  by which fights those are, so only suggestive).
- This is the review's "under-playing" branch: the net doesn't turn "turn
  start -> +Strength per stack" into its worth over the rest of the fight.
  The effects-mode rows *show* the hook, so it is a valuation (rate x
  remaining turns) problem, not a visibility one. Next: the hook_rates
  feature columns (outcome units per turn per power), with this probe as
  the first check of any fix (a fixed net should move its gain toward the
  heuristic's and play share toward ~40%).
- Hexaghost is where it costs most (0.07 vs 0.54): a long fight where
  scaling pays most. The Guardian's held-out gap (-0.13) is largely this.
- Goal 1 meaning: one specific unseen mechanic (a per-turn self buff) is
  systematically undervalued. Registry-lite's split deliberately keeps
  turn start -> +Strength as a *test* mechanic, so its benchmark will show
  whether training on other generated per-turn powers fixes this zero-shot.

## Generated powers, first check (registry-lite step 6; read 2026-10-31)

Bench `data/bench/gen_powers.json`: the 326 held-out tight2 cells whose
deck holds Metallicize or Demon Form (the check-9 cards of Power type; Go
for the Eyes, FTL and Rage are attacks/skills), first 4 fights per cell.
Each cell has a twin with that card (all copies; one kind, seeded, where
both are present) swapped for a generated *test-split* power card from
`data/bench/gen_powers_pack.json` (gen_content seed 1, 128 powers, 43 test;
content hash a109d85da96b0095). Champion = seed-check r2 s1; both players
one-turn search at the agents' limit. 2608 fights per player, 3 min wall
on 4 threads. Script `scripts/analysis/gen_powers_read.py`, result
`results/gen_powers/first-check.json`. Leads are champion minus heuristic,
se over cells.

| set | type | cells | heuristic | champion | lead (se) |
|---|---|---|---|---|---|
| original | hallway | 240 | 0.496 | 0.507 | +0.011 (0.011) |
| original | elite | 63 | 0.484 | 0.480 | -0.004 (0.036) |
| original | boss | 23 | 0.489 | 0.489 | +0.000 (0.067) |
| generated | hallway | 240 | 0.460 | 0.484 | +0.024 (0.011) |
| generated | elite | 63 | 0.385 | 0.413 | +0.028 (0.031) |
| generated | boss | 23 | 0.304 | 0.380 | +0.076 (0.062) |
| **paired gen - orig** | all | 326 | -0.058 | | **+0.021 (0.011)** |

By swapped card: Demon Form cells +0.025 (0.013, n 170), Metallicize
+0.016 (0.017, n 156). Generated set by lifetime: permanent +0.091
(0.024), this turn +0.048 (0.023), used up +0.000 (0.019), wearing down
+0.009 (0.021). By trigger: card played +0.083 (0.020, 57 cells), lost HP
from attacks +0.075 (0.045), turn end +0.020 (0.023), turn start +0.000
(0.027, 61 cells). The 53 cells whose generated power holds the test pair
turn start -> +Strength (Demon Form's mechanic): heuristic 0.429, champion
0.434, lead +0.005 (0.027).

What it says:
- **The champion does not lag the heuristic on generated powers; it leads
  a little more there (+0.021, ~2 se).** MDE at this size is about 0.03
  overall (2.8 se), 0.08 on Demon Form-like cells, 0.2 on boss cells.
- **But that lead is mostly the heuristic's blind spot, not the net's
  skill.** Swapping in a generated card cost the heuristic 0.058 (boss
  -0.185) while the champion lost less. The generator's budget prices a
  card by the heuristic's own `hook_rates` value, and that is nonzero only
  for powers that grant Strength (all 6 priced test cards hold turn start
  -> +Strength, with gains equal to Inflame's and Demon Form's); 84% of the
  test cards are unpriced, i.e. the heuristic values them at about zero.
  The champion's largest leads are exactly on mechanics the heuristic can't
  see (card-played triggers, lost-HP triggers, permanent powers), so this
  reads as "the heuristic is a weak yardstick on generated content", not
  "the net generalises".
- **On the one mechanic both see, the gap the official Demon Form shows is
  not reproduced here at 4 fights x 53 cells** (+0.005, se 0.027). The
  original-set boss lead (0.000) also doesn't show the -0.17 Demon Form
  boss gap from the coverage read, but this is one net, 4 fights per cell
  and Metallicize mixed in, so neither number contradicts it.
- **Cost matching failed for Demon Form:** the generator prices no test
  card at 3 energy (nothing reaches 0.276 / 3 per energy in range), so
  Demon Form's twin is a 2-cost card. Generated cards are cheaper and, by
  the heuristic's results, weaker.
- For goal 1: this check can't separate "net generalises" from "heuristic
  undervalues new mechanics". The training-arms spec should therefore
  compare nets with each other (0 / 16 / 128 generated train powers) on
  this bench, paired by cell, rather than against the heuristic; and the
  generator's budget needs a price that doesn't come from `hook_rates`
  (e.g. measured win-rate gain of the card in a fixed deck) before "budget
  in range" means anything for non-Strength powers.

## Threshold rows: lean-thr vs lean (jobs 0042-0044, 0044c; read 06:40 2026-10-31 by manager run 02:07)

Three `lean-thr-s*` nets (threshold rows in the features, merged layout)
against the three `lean-s*` nets (old layout), same configs, seeds and
shared round 0, all at r2. The spec's question: do threshold rows learned
from the slimes' split transfer to The Guardian's Mode Shift, which no
training fight has? Bar: held-out Guardian gain >= 0.06 (MDE with 3 seeds).

`tight_bosses` (job 0044c, 20 fights per cell), lead over the heuristic
averaged over seeds, and lean-thr minus lean paired per seed (s1 s101 s201):

| half | boss | lean | lean-thr | thr - lean | per seed |
|---|---|---|---|---|---|
| train | Hexaghost | +0.055 | +0.056 | +0.001 | -0.046 +0.018 +0.031 |
| train | Slime Boss | +0.139 | +0.130 | -0.008 | -0.021 +0.010 -0.014 |
| train | Guardian | -0.017 | +0.033 | +0.050 | -0.053 +0.164 +0.039 |
| held-out | Hexaghost | -0.068 | -0.047 | +0.021 | -0.007 +0.041 +0.030 |
| held-out | Slime Boss | +0.064 | +0.072 | +0.007 | -0.027 +0.032 +0.017 |
| held-out | **Guardian** | -0.166 | -0.128 | **+0.038** | -0.035 +0.126 +0.023 |
| held-out | all bosses | -0.052 | -0.031 | +0.022 | -0.023 +0.065 +0.023 |

`tight2` control (lean_read.py, earlier this run): train +0.004, held-out
+0.003, novelty slices all within noise.

Reading: the held-out Guardian gain, +0.038 (se across seeds ~0.047),
is under the bar and inside training luck; one seed (s101) carries most
of it, and the same seed is +0.164 on train Guardian too, so it reads as
a better net overall rather than a Mode Shift effect. No held-out
Guardian cell holds Demon Form, so the planned split by Demon Form is
empty. Nothing got worse: every row is within noise and the sign is
mostly positive. So threshold rows didn't show transfer from slimes to
the Guardian at this size of test; the layout stays (it is merged and
costs nothing measurable). The secondary value probe (net value drop
across the shift vs play-outs) was not run. Not ladder-tested (didn't
pass).

## Rate features: lean-rates vs lean-thr (jobs 0049b-d, 0052a1/a2, 0054z3; read 12:10 2026-10-31 by manager run 7328b322)

The arm is lean-thr plus the encoder's `rates` columns (each power's worth
per turn), one config key different, same round 0, three seeds. Spec rule
(`docs/specs/rate-features.md`): adopt if held-out boss gains >= 0.06 and
train is no worse than -0.015.

**Against the rule.** `tight2` (from the 10:03 run): held-out boss +0.055
per seed [+0.076 +0.030 +0.060], held-out all +0.009, train all +0.001,
train elite -0.022. `tight_bosses` (20 fights per cell), rates minus thr
paired per seed:

| half | boss | thr | rates | diff | per seed (s1 s101 s201) |
|---|---|---|---|---|---|
| train | Hexaghost | 0.582 | 0.594 | +0.012 | +0.055 +0.009 -0.030 |
| train | Slime Boss | 0.639 | 0.655 | +0.015 | +0.029 -0.004 +0.021 |
| train | Guardian | 0.534 | 0.426 | **-0.109** | -0.001 -0.204 -0.120 |
| train | all bosses | | | -0.027 | +0.028 -0.066 -0.043 |
| held-out | Hexaghost | 0.433 | 0.440 | +0.007 | -0.012 +0.007 +0.027 |
| held-out | Slime Boss | 0.537 | 0.593 | +0.055 | +0.076 +0.030 +0.060 |
| held-out | Guardian | 0.350 | 0.353 | +0.003 | +0.042 -0.024 -0.008 |
| held-out | all bosses | | | +0.022 | +0.035 +0.004 +0.026 |

So the rule fails on both counts (held-out bosses +0.022 / +0.055 < 0.06;
train bosses -0.027 < -0.015). Rates stay off by default.

**Split by whether the deck holds Demon Form** (the mechanic the spec
targeted; only held-out decks hold it), rates minus thr:

| half | boss | decks | fights | diff | per seed |
|---|---|---|---|---|---|
| held-out | Hexaghost | Demon Form | 140 | **+0.202** | +0.150 +0.300 +0.157 |
| held-out | Hexaghost | other | 600 | -0.038 | -0.050 -0.062 -0.003 |
| held-out | Guardian | Demon Form | 320 | **+0.126** | +0.137 +0.091 +0.150 |
| held-out | Guardian | other | 420 | **-0.090** | -0.031 -0.112 -0.129 |
| held-out | Slime Boss | Demon Form | 320 | **+0.124** | +0.159 +0.050 +0.162 |
| held-out | Slime Boss | other | 500 | +0.011 | +0.022 +0.018 -0.006 |
| train | Guardian | (none hold it) | 740 | **-0.109** | -0.001 -0.204 -0.120 |

**Demon Form probe, with the right control.** The 10:03 probe compared
lean-rates against the seed-check nets (an older recipe); job 0054z3 ran
the same probe on the lean-thr nets. Same 156 held-out Demon Form fights:

| player | won | Demon Form share of offers | never played when offered | gain at heuristic's first offer |
|---|---|---|---|---|
| heuristic | 0.442 | 41% | 35% | -0.007 |
| lean-thr s1 / s101 / s201 | 0.295 / 0.397 / 0.269 | 8% / 13% / 7% | 83% / 73% / 86% | -0.140 / -0.094 / -0.116 |
| lean-rates s1 / s101 / s201 | 0.449 / 0.494 / 0.436 | 34% / 40% / 32% | 43% / 35% / 44% | -0.021 / -0.047 / -0.037 |

Reading:
- **The feature does what it was built for.** With each power's per-turn
  worth as columns, the nets now play Demon Form about as often as the
  heuristic (32-40% of offers vs 41%), value it close to their best
  alternative, and win Demon Form fights at the heuristic's level (+0.10
  to +0.17 per seed over lean-thr; Hexaghost Demon Form fights +0.20).
  All three seeds agree; this is far outside training luck. It is the
  first feature to move play on an unseen mechanic by this much (goal 1).
- **But it costs about -0.1 on Guardian fights without Demon Form, on
  both halves** (train -0.109, held-out -0.090; two of three seeds carry
  it, s1 is flat on train). Hexaghost without Demon Form also dips
  (-0.038 held-out). Slime Boss is fine. The loss sits in decks holding
  power cards (train -0.114 with any power, -0.077 without; held-out
  -0.112 vs 0.000), which points at the nets mis-timing power cards
  against the Guardian, not at wrong rate values: no Guardian power
  feeds `hook_rates` (Mode Shift is a threshold row, Sharp Hide isn't a
  turn hook).
- Net effect on the spec's averages is small because the gain is confined
  to the 20-40% of boss decks that hold Demon Form.

### Where the Guardian cost comes from (decision diff; job 0054z5, read 12:25 by a fork of manager run 7328b322)

Checks first. On real Guardian states with rates on, the Guardian's own
`rate_*` columns are all zero (no Guardian power feeds `hook_rates`);
the player's columns hold sensible values for its own powers. The
always-on `turns_left_est` is not out of range either: at fight start it
is median 16.4 on the Guardian, 17.5 on Hexaghost and 20.7 on the
training half's Slime Boss. Power-card timing is ruled out
(`results/probes/guardian_powers-rates.json`: lean-rates plays the
same powers as often and as early as lean-thr). So the cost is not a
wrong input value; it is a different learned policy.

`scripts/analysis/decision_diff.py`: 174 Guardian fights without Demon
Form (`tight_bosses`, both halves, 3 per cell). The lean-thr net plays;
at each decision its lean-rates twin (s101, s201) and the heuristic
search the same state. Out of 11,131 decisions the two nets' first
actions differ in 1,204 (10.8%). The heuristic sides with thr in 637,
with rates in 479, neither in 88. Split by the Guardian's mode:

| Guardian mode | differ | heuristic sides thr | sides rates |
|---|---|---|---|
| offensive (Mode Shift up) | 719 | **484** | 195 |
| defensive (Sharp Hide) | 485 | 153 | **284** |

Who attacks when one net attacks and the other doesn't (heuristic's side):

| situation | heuristic sides thr | sides rates |
|---|---|---|
| thr attacks, offensive, <= 15 damage left to the shift | **81** | 26 |
| thr attacks, offensive, > 15 left | 100 | 56 |
| rates attacks, offensive, > 15 left | 92 | 21 |
| thr attacks into Sharp Hide | 21 | **163** |
| rates attacks into Sharp Hide | 82 | 10 |

Reading (heuristic agreement is a proxy, not ground truth, and the states
come from thr's own play):
- In defensive mode the rates nets are *better*: they stop attacking into
  Sharp Hide where thr and not the heuristic would.
- In offensive mode they are worse, and most clearly just before the
  shift: with <= 15 damage left to Mode Shift, the rates net blocks or
  ends its turn (attack -> skill 64, attack -> end turn 46 of 190) where
  thr and the heuristic push the attack through. The shift costs the
  Guardian a turn (it goes defensive and stops its big hits), so
  hesitating there loses tempo; the remaining offensive disagreements
  look like plain noisier attack/block choices (Strike <-> Defend is the
  top pair both ways).
- Most likely cause: a training-outcome shift in how the net reads the
  threshold row near its threshold, not a rates bug. The rates columns
  change the input every state, so the two nets settle differently on
  things neither was trained on (the Guardian is unseen; only slime
  splits taught threshold rows), and this pair lands worse on "cross the
  threshold now".
- Fix to test: (1) two-turn search with the rates nets on these fights
  (the fallback player): depth sees what the shift buys and should remove
  the near-threshold hesitation; if it does, rates can be adopted under
  two-turn play or via distillation. (2) The same diff on Slime Boss near
  its split threshold (a training boss): if the rates nets hesitate there
  too, it is a threshold-row learning problem worth a feature
  ("damage to threshold / damage per turn"), not a Guardian quirk.

## Data scaling: 5k / 20k / 40k round-0 games (jobs 0045-0057; read 14:40 2026-10-31 by a manager run)

Configs differ only in `n_train` (games per group, round 0 and round 1);
same `seed`, `train_seed`, `round0_seed`, so arms pair by seed index. r1
nets on tight2, net won-share differences paired per seed, mean (se over
seeds):

| comparison | seeds | half | all | hallway | elite | boss |
|---|---|---|---|---|---|---|
| 20k - 5k | 5 | train | +0.015 (0.004) | +0.010 | +0.033 | +0.026 |
| 20k - 5k | 5 | held-out | +0.011 (0.006) | +0.009 | +0.021 | +0.009 |
| 40k - 20k | 3 | train | +0.013 (0.004) | +0.007 | +0.024 | +0.043 (0.011) |
| 40k - 20k | 3 | held-out | +0.009 (0.003) | +0.005 | +0.009 | +0.043 (0.025) |
| 40k - 5k | 3 | train | +0.024 (0.007) | +0.013 | +0.052 | +0.058 |
| 40k - 5k | 3 | held-out | +0.012 (0.006) | +0.007 | +0.018 | +0.052 (0.011) |

Means over s1/s101/s201: train 0.492 / 0.503 / 0.516, held-out 0.488 /
0.491 / 0.500 (5k / 20k / 40k).

Reading:
- **The slope doesn't flatten.** Per doubling of games, 5k -> 20k gives
  ~+0.006-0.008 and 20k -> 40k ~+0.009-0.013. Bosses gain most from the
  last doubling (+0.043 on both halves, though held-out's se is 0.025).
  Held-out gains are smaller than train's, as with every lever so far.
- Cost is about linear in games: a run takes ~20 min at 5k, ~25-35 at
  20k, ~65-75 at 40k (two jobs sharing the machine, with paging at times).
- Pairing is partial, not exact: `selfplay.make_specs` draws decks from one
  generator across groups, so only the first group's games are a prefix of
  the bigger set; later groups' decks differ. The seed-index pairing still
  shares the net's init and round seeds.
- Next: 80k, 3 seeds (0057a9a-c, ~150 min each), and r0 scoring of all
  three sizes (0061). If 80k - 40k is again ~+0.01, data volume is the
  cheapest steady lever we have and the default `n_train` should rise.

## Generated-power training arms: no transfer at this scale (jobs 0057a1-a6, 0051b, 0057a6c5; read 16:35 2026-10-31 by manager run bb961751)

Spec `docs/specs/gen-training-arms.md`. Arms = lean-thr plus 16 or 128
generated train powers (`content_share` 0.5, night round 0), 3 seeds each,
r2 nets; control = lean-thr r2, paired by seed and cell. Bench
`data/bench/gen_powers12.json`: 326 held-out cells, 12 fights each, each
cell played once with its original power card (Demon Form or Metallicize)
and once with a generated *test-split* power card, whose (trigger, effect)
pair no training power has. Raw: `results/gen_powers/arms.json`,
`results/gen_powers/arms/gen_powers12/`.

| arm minus control | generated set | original set | Demon Form cells (170) |
|---|---|---|---|
| gen16 | -0.004 (se 0.012) [+0.019 -0.017 -0.015] | -0.006 (se 0.011) | -0.001 (se 0.011) |
| gen128 | -0.006 (se 0.010) [+0.013 -0.011 -0.020] | -0.012 (se 0.014) | -0.005 (se 0.017) |

**Rule (spec): gen128 within +-0.02 of control -> no transfer at this
scale.** Nothing grows from 16 to 128 either.

Why I believe it and what it says:
- The per-seed pattern [+, -, -] is the same in both arms and on both the
  generated and the original set, so it is the control's seed luck
  (lean-thr s1 sat -0.020 below lean on tight2 held-out), not the arms.
  Taking generated minus original *within* each arm cancels it: gen128
  +0.006 [-0.003 +0.014 +0.006], gen16 +0.002 [+0.003 +0.003 -0.001].
  Training on generated mechanics buys at most ~0.01 on unseen generated
  mechanics relative to known cards: not zero-shot transfer.
- Content got in: the arm runs carry the 19 / 176-power pack
  (`content.json`, `content_hash` in round.json) and their own datasets;
  they even train on one more dataset than the control.
- Small slices, not decisive (cells 7-34, se 0.01-0.02): turn-end powers
  +0.013, "OwnerLostHp from Card" +0.023, a turn-end + lost-HP combination
  +0.060 in both arms; card-played triggers -0.024, lost-HP-from-attack
  -0.018. Permanent-lifetime powers -0.019 (se 0.008). No family stands
  out enough to chase.
- A cost on original elites: tight2 (round.json) gen128 minus lean-thr,
  elites -0.043 train / -0.047 held-out [~0, -0.05, -0.09], bosses level
  (+0.006 held-out); the bench's elite group agrees (-0.040, se 0.029).
  Generated cards take deck slots in half the training decks, so the net
  sees the real elite decks less often; within noise per seed but
  consistent. Another reason not to add content to the recipe as is.
- Boss lead (job 0057a6e, `results/bosses/lead-lean-gen.json`, paired
  with `lead-lean-thr.json` fight by fight, arm minus lean-thr per seed):
  every boss within ~1.5 se of 0 on both halves except held-out
  Hexaghost, gen128 -0.046 (se 0.019) [-0.08 -0.05 -0.01], gen16 -0.029.
  Hexaghost is the Demon Form boss, so generated powers didn't teach the
  nets to value it either (if anything the reverse).

What changes: content breadth at this scale is not a goal-1 lever. This
matches the prior-art scan (`docs/research/unseen-mechanics.md`: no method
handles a new primitive zero-shot) and the rate-features result (a
per-mechanic feature fixed Demon Form by +0.10-0.20). Goal-1 work moves
to per-mechanic features plus a short adaptation burst (fine-tune on a
new mechanic's games), per the spec's "no transfer" branch.

## Rate features on 5 seeds: the Guardian cost is real but smaller (jobs 0057a6a-d, 0057a7a; read 16:58 2026-10-31 by manager run bb961751)

Two more paired seeds (s301, s401) of lean-thr and lean-rates, boss lead
in `results/bosses/lead-rates-seeds2.json`, joined with
`lead-lean-rates.json` / `lead-lean-thr.json` fight by fight (the first
three seeds reproduce the table above exactly). Rates minus thr, 5 seeds
(s1 s101 s201 s301 s401), split by whether the deck holds Demon Form:

| half | boss | decks | fights | mean (se) | per seed |
|---|---|---|---|---|---|
| train | Guardian | (none hold it) | 740 | **-0.082 (0.043)** | -0.001 -0.204 -0.120 -0.116 +0.032 |
| train | Hexaghost | other | 740 | +0.023 (0.016) | +0.055 +0.009 -0.030 +0.050 +0.031 |
| train | Slime Boss | other | 800 | -0.003 (0.014) | +0.029 -0.004 +0.021 -0.011 -0.051 |
| held-out | Guardian | Demon Form | 320 | **+0.118 (0.020)** | +0.137 +0.091 +0.150 +0.053 +0.156 |
| held-out | Guardian | other | 420 | **-0.052 (0.029)** | -0.031 -0.112 -0.129 -0.005 +0.014 |
| held-out | Hexaghost | Demon Form | 140 | **+0.167 (0.038)** | +0.150 +0.300 +0.157 +0.064 +0.164 |
| held-out | Hexaghost | other | 600 | -0.028 (0.012) | -0.050 -0.062 -0.003 -0.023 -0.002 |
| held-out | Slime Boss | Demon Form | 320 | **+0.118 (0.021)** | +0.159 +0.050 +0.162 +0.106 +0.109 |
| held-out | Slime Boss | other | 500 | -0.002 (0.011) | +0.022 +0.018 -0.006 -0.004 -0.038 |

Reading:
- The Demon Form gain holds on all 5 seeds and all three bosses (+0.12 to
  +0.17).
- The Guardian cost shrinks from ~-0.10 to -0.08 train / -0.05 held-out,
  each ~1.8-1.9 se, same sign on both halves; 3 of 5 seeds carry it, 2
  are flat. Likely real, about half a Demon Form gain, and confined to one
  boss (Hexaghost without Demon Form -0.028 is the only other dip).
- Per the review (2026-10-31b), the hunt for a feature fix stops here. Next
  question: does two-turn search remove the hesitation before Mode Shift?
  Queued 0057a6i: rates and thr r2 nets of s101 / s201 / s301 (the seeds
  with the cost) play train Guardian fights at one and two turns, 4 per
  cell (`results/depth/guardian-train-<run>.json`). Read: (rates two -
  thr two) vs (rates one - thr one), paired by seed. If depth closes the
  gap, the cost is a horizon problem, and rates plus depth (or distilled
  depth) is the combination to test on the adoption rule.

## Two first checks from the review (fork of manager run bb961751, 16:55 2026-10-31)

Scripts and outputs in that session's scratchpad (`topk.py`, `meff.py`;
not kept). Both bars fail.

**Top-3 root pruning (review rank 2).** 448 horizon >= 1 puzzles
(`data/bench/puzzles.json`; the analysts' 443 came from a time limit).
Baselines reproduce: regret heuristic one-turn 0.0314, net one-turn
0.0189, net two-turn 0.0061 (champion net; no search hit the node cap).
Choosing by two-turn value among one-turn's top 3 gives **0.0046, lower
than full two-turn**; the exact best option was in one-turn's top 3 in 48
of 49 net errors. But puzzles have a median of 4 root options, so pruning
to 3 saves ~nothing (1.12M vs 1.12M nodes, estimated by re-searching
each kept child; the API can't filter root options, that needs a filter
in `engine/src/search.rs`). So: no speed case on endgames (mid-fight
states with more options untested), but a *quality* hint that matches the
prior-art point (penalise search for overriding the policy): limiting
two-turn's overrides to one-turn's top few may beat the plain fallback
player. Cheap to test once the root filter exists.

**Simulated power effects (review rank 6).** For each of the 43 test
powers: starter deck + 2 copies of the card, 5 encounters x 40 seeds, no
death, greedy player always vs never playing it; delta = HP left
difference. Correlation with the card's swap cost (9-net mean 0.048, sd
0.062): **-0.25** (rank -0.18), right sign, far below the 0.5 bar. The
card's energy cost alone correlates -0.48. The weak part is the crude
policy; the swap cost is stable across nets (seed-to-seed corr 0.875). A
measured-effects feature isn't justified on this evidence; a fairer
measure would need search play on the bench's real decks.

## Ladder: no newer recipe beats the 10-29 champion (job 0057a6f, tests 0004-0015; read 17:05 2026-10-31 by manager run bb961751)

Each net against the champion (`runs/2026-10-29-seed-check-r2-s1-1a789b2`,
night recipe r2 with the solve step), `ladder.py test --no-promote`, SPRT
d1 0.01 (`results/ladder/log.jsonl`, `results/ladder/tests/`). Lead =
candidate minus champion on the ladder's paired pool; se ~0.006-0.010 at
these stop sizes.

| nets | leads | mean |
|---|---|---|
| data40k r1 s1 / s101 / s201 | -0.026 -0.014 -0.018 | -0.019 |
| lean-thr r2 s1 / s101 / s201 / s301 / s401 | -0.032 -0.013 -0.007 -0.018 -0.016 | -0.017 |
| lean-distil r2 s1 | -0.030 | |
| cover21 r1 s1 / s101 / s201 | -0.071 -0.059 -0.058 | -0.063 |
| (earlier) champion's own seed twins s101 / s201 (tests 0002-0003) | -0.013 -0.000 | -0.007 |

All 12 fail. Reading, with care:
- The champion is a best-of-3 pick, so its recipe's average sits ~0.007
  below it. Against that average, lean-thr is ~-0.010 and data40k r1
  ~-0.012: both recipes look about 0.01 *weaker* than the 10-29 night
  recipe, not stronger. Their tight2 leads agree in direction (lean_read:
  seedcheck-r2 +0.027 train / +0.006 held-out, lean-thr +0.021 / +0.005).
- That fits the lean-loop read ("no solve step loses at most ~0.01-0.02,
  not detected"): the ladder now suggests the loss is real, ~0.01. So
  the exact-label / solve-step machinery may be worth ~0.01 after all;
  the review's "labels never moved play" is about variants of it, not
  about having it. Not proven: per-net se ~0.006-0.01, and the ladder's
  pool weighs bosses more than tight2.
- data40k is only r1 with a fresh round 0 (the champion is r2 on the
  night's round 0). More data isn't yet a stronger product; the lean
  recipe's experiment gains are relative to lean, not to the champion.
- Distillation s1 is -0.030 (one seed; its interim tight2 read was
  mixed). Read s101 / s201 the same way.
- cover21 is far weaker (-0.06), as its tight2 read said.

What changes: experiments keep comparing within the lean recipe (cheap,
paired), but anything meant to become the product must also beat the
champion on the ladder. A recipe that beats lean by +0.01 merely catches
up with the night recipe.

## Ids twin s1 and distillation s101 (read 18:10 2026-10-31 by manager run c3a3a6dc; interim, not results)

**Ids twin** (job 0057a6g, `ids5k-s1` = `data5k-s1` with `mode: ids`, same
round-0 games, own round-0 net). r1 tight2, paired per fight against
`data5k-s1` r1, mean of cell means (se within this one seed only):

| half | hallway | elite | boss | all |
|---|---|---|---|---|
| train | +0.002 (0.003) | -0.058 (0.017) | +0.011 (0.018) | -0.010 (0.005) |
| held_out | -0.003 (0.004) | -0.088 (0.016) | -0.023 (0.019) | -0.022 (0.005) |

Below the 0.05 gap that decides alone, so s101 / s201 run (0057a8z1/z2).
The shape is the point to check: ids loses on elites on *both* halves,
so if it holds, the effects encoding helps elite play in general, not
only on unseen cards (held-out costs more, -0.088 vs -0.058). Ids mode ran
without errors on held-out cards.

**Distillation s101** (0057a7) against `lean-thr-s101` r2, tight2 paired
means: train hallway +0.000, elite -0.019, boss +0.004; held-out hallway
-0.007, elite -0.025, boss -0.026. s1 was +0.020 / +0.016 on elites, so
two seeds average ~0 on elites (bar: +0.01 for the scale-up spec). Teacher
49 min this round, 22% overrides. Ladder test 0016: fail, lead -0.013
(train boss -0.18, held-out boss +0.07, both wide). s201 (0057a8) decides
the 3-seed read, but the scale-up looks unlikely.

## Ids twin (3 seeds), distillation (3 seeds), rate nets at two turns on the Guardian (read 20:20 2026-10-31 by manager run 44869c1c)

**Ids twin** (`ids5k-s<seed>` vs `data5k-s<seed>`, r1 tight2, paired per
fight, mean of cell means per seed; jobs 0057a6g, 0057a8z1/z2):

| half | hallway | elite | boss | all |
|---|---|---|---|---|
| train | -0.010 [+0.002 -0.035 +0.004] | -0.034 [-0.058 -0.033 -0.010] | -0.010 [+0.011 -0.060 +0.018] | -0.015 |
| held_out | -0.014 [-0.003 -0.037 -0.000] | **-0.075** [-0.088 -0.074 -0.062] | -0.040 [-0.023 -0.112 +0.015] | -0.028 |

Pre-registered rule (elites <= -0.04 on both halves): held-out holds on
every seed, train misses (-0.034, one seed -0.010). Reading: the effects
encoding earns its keep, and more on unseen cards than on training cards
(held-out elite cost about twice train's). This is the first test of the
effects-vs-ids thesis at current strength; it supports it. Ids stays a
control only.

**Distillation** (`lean-distil` vs `lean-thr`, r2 tight2, 3 seeds):
elites -0.030 train [+0.020 -0.019 -0.090] / -0.035 held-out [+0.016
-0.025 -0.095]; all -0.009 / -0.015. s201's teacher looked normal (22%
overrides, 455 cuts, 100 min). Fails the +0.01 bar; ladder s201 fails
(train elite -0.18, elite -0.125 [-0.21, -0.04]). **Distillation as built
is closed**: no search-labelled scale-up.

**Rate nets at two turns, train Guardian** (job 0057a8z, 148 fights per
net, per-cell 4, fallback player, `results/depth/guardian-train-*.json`):

| seed | thr one | thr two | rates one | rates two | rates-thr one | rates-thr two | gap closes |
|---|---|---|---|---|---|---|---|
| s101 | 0.608 | 0.696 | 0.419 | 0.649 | -0.189 | -0.047 | +0.142 (se 0.057) |
| s201 | 0.601 | 0.682 | 0.419 | 0.655 | -0.182 | -0.027 | +0.155 (0.064) |
| s301 | 0.480 | 0.709 | 0.365 | 0.689 | -0.115 | -0.020 | +0.095 (0.061) |

Two-turn search removes most of the rate nets' Guardian cost on every
seed (mean gap -0.162 at one turn, -0.031 at two). This fits the
hesitation found by the decision diff: looking one more turn ahead sees
Mode Shift's payoff that the rate nets misprice. Together with the
novelty slice (net-leaf depth gains most on unseen power cards), depth
looks like a general repair for mis-priced mechanics. Since the rates'
Demon Form gain came at one turn, rates + depth may pass the adoption rule
the one-turn nets failed: queued 0057a8z4 (rates vs thr, two turns, all
bosses, both halves, s101/s201/s301; read as rates2 - thr2 per seed,
paired per fight, against the spec's held-out boss >= +0.06 bar). Caveat:
these Guardian fights are train cells; the per-net one-turn numbers here
(148 fights) are noisier than the 5-seed boss-lead read.

## Rates vs thr under two-turn search, held-out bosses (job 0057a8z4 held-out half; read 22:20 2026-10-31 by manager run 5cbfc037)

lean-rates minus lean-thr r2 nets, seeds s101 / s201 / s301, tight_bosses
held-out (Hexaghost, The Guardian), 4 per cell, paired by (cell, seed);
`scripts/analysis/rates_depth_read.py held_out`. Won rate:

| slice | one-turn | two-turn |
|---|---|---|
| all (n 888) | +0.012 (se 0.018) | +0.033 (se 0.015) |
| Hexaghost (444) | +0.023 (0.023) | +0.005 (0.020) |
| The Guardian (444) | +0.002 (0.027) | +0.061 (0.022) |

Per seed, two-turn all: +0.047 / +0.047 / +0.003. The rule (decisions
"Distillation closed; rates retested under depth") needs held-out boss
>= +0.06: **fails, rates stay off** whatever the train half shows. Two
things worth keeping: at two turns the rate nets *gain* on the held-out
Guardian (+0.061), so depth does more than remove their hesitation; and on
this sample one-turn Guardian shows no cost (+0.002), unlike the earlier
5-seed -0.05, so that cost was partly seed luck. Hexaghost, where Demon
Form fights showed the rate gain at one turn, gains nothing at two turns:
depth already finds what the rate columns price. The fight-level se
ignores training-seed luck (3 seeds).

Train half (read 23:00 2026-10-31, `rates_depth_read.py train`), same
pairing: all one-turn -0.073 (se 0.018), two-turn +0.001 (0.016);
Hexaghost +0.016 / +0.034; The Guardian -0.162 (0.028) / -0.032 (0.023).
Per seed two-turn all: -0.020 / -0.003 / +0.027. The train Guardian cost at
one turn reproduces the earlier -0.16 exactly, and two-turn search again
removes most of it (as on the Guardian-only run). The spec's train bar
(>= -0.015) passes at two turns, but the held-out bar failed, so the
verdict stands: rates stay off.

## Ensemble of the champion and its seed twins, one turn, on the ladder (job 0057a8z5a, test 0018; read 23:00 2026-10-31 by manager run 5cbfc037)

Mean-of-scores ensemble (`docs/specs/ensemble-evaluator.md`) of
`seed-check-r2-s1/s101/s201` vs the champion (s1 alone), `ladder.py test
--no-promote`: **fail**, 4,274 pairs, lead +0.0019 (SPRT accepted "no
+0.01 lead"). Held-out +0.007 [-0.003, +0.017], train -0.003; by group
elites +0.016, bosses -0.007, hallways -0.001. The twins alone were
-0.013 / -0.000 against the champion (tests 0002-0003), so the ensemble
gains ~+0.006 over its members' mean: real-sized for an ensemble of
same-recipe nets, but under the ladder's 0.01. Rule (a) not met: the
one-turn ensemble is not the product candidate. Held-out elites +0.030
[-0.004, +0.063] is a post hoc slice; the two-turn run (0057a8z9, held-out
elites and bosses, pre-registered) is the test that counts for the
ensemble's main purpose.

## Oracle arm on tight2 (jobs 0057a8z5-z7; read 00:10 2026-11-01 by manager run 048566e9; side read, not the rule's)

The oracle arm (lean-thr plus the generated bench's own 43 test powers in
training, share 0.5) is judged on `gen_powers12` (job 0057a8z8b; the first
try, 0057a8z8, failed because the runner's bash has no `ls`). Its tight2
numbers from round.json, net minus heuristic, r2, 3 seeds, paired per seed
with lean (`lean_read.py lean-oracle lean-thr`):

| slice | oracle - lean (per seed) | thr - lean (per seed) | oracle - thr |
|---|---|---|---|
| train elite | -0.022 [+0.046 -0.024 -0.086] | +0.007 | -0.029 |
| train boss | -0.003 | -0.008 | +0.005 |
| held-out elite | -0.009 [+0.042 +0.000 -0.070] | +0.009 | -0.018 |
| held-out boss | +0.052 [+0.052 +0.024 +0.078] | +0.007 [-0.027 +0.032 +0.017] | +0.044 [+0.079 -0.008 +0.061] |
| held-out all | -0.001 | +0.003 | -0.004 |

Reading: overall level, as with the gen arms. Generated content again costs
on elites (train -0.03, the gen arms' ~-0.04), and seed s201 is the worst on
both halves. The one gain is held-out bosses (+0.044 over thr, two of three
seeds; 820 fights, about 1.5 to 2 se), and it is *not* on Demon Form fights
(demon_form slice +0.005). Post hoc and inside training luck at 3 seeds
(MDE ~0.03-0.04 on a 820-fight slice); noted, not acted on. If the bench read
passes, check whether the 43 test powers resemble the held-out bosses'
mechanics (Hexaghost's Burn / Inferno, Guardian's Mode Shift) before calling
it transfer.

## Ensemble of three seed nets under two-turn search (job 0057a8z9; read 02:15 2026-11-01 by manager run 048566e9)

Two-turn fallback player, held-out elites and bosses, per-cell 8 (1336
fights), sample_k 4, cap 400k. Evaluator: the mean score of the champion and
its two seed twins (`seed-check-r2-s1/s101/s201`), paired per fight with the
champion alone (`paired-net-held_out-cap400k-fallback.json`, same fights and
seeds; checked cell and seed match row by row). Won, ensemble minus champion:

| slice | n | two-turn | one-turn (same file's `one` arm) |
|---|---|---|---|
| all | 1336 | **+0.008 (se 0.007)** | +0.021 (se 0.008) |
| elite | 1008 | +0.012 (se 0.008) | +0.018 (se 0.009) |
| boss (Slime Boss) | 328 | -0.003 (se 0.015) | +0.030 (se 0.017) |
| Gremlin Nob | 336 | +0.012 | +0.009 |
| Lagavulin | 336 | +0.024 (se 0.017) | +0.036 (se 0.020) |
| Three Sentries | 336 | +0.000 | +0.009 |

Spec rule (b): within +-0.02 -> **no change**; the champion alone stays the
two-turn player's evaluator. Overrides 3579 vs 3465, cuts 1352 vs 1413.
Run took 161 min against a 360 min estimate (3x inference is small next to
the tree).

What it says: at one turn the ensemble helps on these fights (+0.021, ~2.6
se; matches the ladder's held-out elite +0.030, while the ladder's overall
+0.002 is diluted by hallways), but under two-turn search most of it is gone
(+0.008). Depth and averaging repair overlapping errors: both cut the leaf
value's noise and over-estimation, which is what the prior-art sources
predicted for ensembles, and two-turn search already removes much of it.
So leaf-noise fixes stack poorly with depth; a better leaf has to be better
in a different way (sees what the net mis-prices, e.g. new mechanics) to
add. Min-over-members (the follow-up if the mean helped) is not run.

## data80k s1, interim (job 0057a9a; read 02:25 2026-11-01 by manager run 048566e9; one seed, not a result)

tight2 r1, paired per fight with data40k-s1 r1 (same train_seed and
round0_seed; per-fight se only, training luck sd ~0.010 / 0.013 not in it):
train all +0.008 (hallway +0.016, elite -0.011, boss -0.020); held-out all
+0.024 (hallway +0.023, elite +0.036, boss +0.006). Ladder (test 0019)
against the 10-29 champion: **fail**, lead -0.018 (held-out -0.016, train
-0.020, bosses -0.11 on 75 pairs), the same as data40k r1's -0.019. So more
round-0 games still lift the lean r1 net against its own recipe, but don't
close its gap to the champion (night recipe: solve step on, r2). s101
(0057a9b) decides the slope; the champion-candidate question in Next 1
(night recipe at 80k) stays open.

## Two-turn search: sample size and an offline gate (job 0057a8z8c; read 02:50 2026-11-01 by manager run 048566e9)

`scripts/analysis/sample_agree.py`, champion net, held-out elites and
bosses (1 fight per cell, every 3rd decision, cap 400k): 847 decisions
probed (583 elite, 264 boss), each searched two turns deep twice at
sample_k 4 (two sample seeds) and once at sample_k 16
(`results/depth/sample-agree-held_out.json`).

- **Ties:** on 54% of decisions one-turn search's top two options have
  exactly equal value (different orders that end in the same state, or
  options that don't matter). So an "override" can be a tie-break; real
  overrides (to an option one-turn values lower) are 14.3% of decisions
  (16.6% counting tie-breaks). Earlier override shares (12.7% etc.) count
  both.
- **Sample size (Rubin's check):** the two k4 seeds pick options of
  different value on 5.8% of decisions; 82% of real overrides survive a
  reseed; k16 differs from k4 on 5.4% and overrides about as often (15.3%).
  So sample_k 4 is not badly under-sampled: roughly a fifth of overrides
  are sampling noise. A sample_k 8 win test could move at most a few
  percent of decisions; not queued (expected effect under the MDE).
- **Offline gate (framing 2) by one-turn's top-2 gap:** real overrides by
  gap: tied 37% of overrides (54% of decisions, override rate 10%), gap <=
  0.01 16% (5% of decisions, rate 46%), 0.01-0.05 21% (11%, rate 27%), >
  0.05 26% (30%, rate 12%). Overrides happen at every gap, so a gap gate
  saves little: skipping search where the gap is > 0.05 saves 30% of the
  searches and loses 26% of the overrides. Not worth a build; a gate would
  need another signal (e.g. tied tops are cheap to skip only if the
  overrides there are worthless, unknown). Median one-turn value given up by
  a real override: 0.048.

What it changes: the two-turn player's knobs (sample_k, gating) are not
where its next gain is. Leaf quality and new mechanics remain.

## Oracle arm on the generated-power bench (job 0057a8z8b; read 02:45 2026-11-01 by manager run 048566e9)

`gen_powers_read.py arms --bench data/bench/gen_powers12.json --control
lean-thr --arms lean-oracle` (`results/gen_powers/oracle.json`): nets
trained on the bench's own 43 test powers, minus lean-thr, 326 cells x 12
fights, paired by cell and seed, 3 seeds:

- generated set **+0.001 (se 0.012)** [+0.026 -0.010 -0.012]; original set
  -0.004; generated bosses +0.014, elites +0.001, hallways +0.000.

Rule (decisions "Oracle arm"): below +0.03 -> the bench (or share 0.5)
can't show learning on these powers; fix the bench before any more
generated-content tests. So the gen-arm null ("no transfer") is not
evidence either way.

Why the bench is blind: every net wins ~0.04 less with the generated card
than with the original (thr orig 0.488-0.529 vs gen 0.450-0.481; oracle the
same gap, -0.035 to -0.041), so the oracle doesn't play its own powers
better. Only ~13% of paired fights change outcome when the card is swapped,
and some of that is just a different draw. The decks hold one copy of the
power in 15 cards, at 1-6 HP (tight2 cells): the card is often not drawn or
not decisive. First fix tried: `build --copies 3` (Strikes, then Defends,
become copies of the swapped card in both sets; `data/bench/gen_powers12c3.json`),
replaying the same six nets (job 0057a8z8d). Read: oracle - thr on the
generated set >= +0.03 -> the 3-copy bench can show learning and becomes
the adaptation-burst bench; below -> the oracle nets didn't learn these
powers (share 0.5 of training content spread over 43 powers is ~1% per
power); next would be a single-power oracle (one power, high share).

**3-copy bench read (job 0057a8z8d, 03:00 2026-11-01;
`results/gen_powers/oracle-c3.json`):** oracle - thr on the generated set
**+0.013 (se 0.009)** [+0.031 +0.007 +0.002], original set +0.001; bosses
+0.064 (se 0.008, 23 cells, all seeds), elites +0.024, hallways +0.005;
wearing-down powers +0.024 (all seeds). The bench is more sensitive (paired
fights that change outcome with the swap: ~20% vs ~13%; generated minus
original ~-0.08 vs -0.04), and the oracle's gain is specific to the
generated set, but it stays under the +0.03 bar. So the oracle nets learned
their 43 powers only a little: the arm is too diluted (share 0.5 over 43
powers, ~1% of games per power), not blind. The 3-copy bench replaces
`gen_powers12` for generated-power tests; the next test concentrates the
training on few powers (decisions "Oracle arm read").

## data80k vs data40k, 2 seeds (jobs 0057a9a / 0057a9b; read 04:30 2026-11-01 by a fork of manager run 68e81bce)

r1 nets on tight2, net won-share differences paired per seed (same
`train_seed` / `round0_seed`), mean [s1, s101]:

| comparison | half | all | hallway | elite | boss |
|---|---|---|---|---|---|
| 80k - 40k | train | +0.004 [+0.008, +0.000] | +0.005 | +0.000 | +0.004 |
| 80k - 40k | held-out | +0.003 [+0.024, -0.019] | +0.004 | +0.008 | -0.027 [+0.006, -0.060] |
| 40k - 20k, same 2 seeds | train | +0.012 | +0.008 | +0.016 | +0.036 |
| 40k - 20k, same 2 seeds | held-out | +0.009 | +0.009 | +0.004 | +0.026 |

Levels (train / held-out): 40k s1 0.513 / 0.481, s101 0.517 / 0.517;
80k s1 0.521 / 0.506, s101 0.518 / 0.498.

Ladder against the 10-29 champion: s1 test 0019 fail -0.018 (earlier
read), s101 test 0020 **fail -0.024** (699 pairs; elites -0.063, bosses
-0.065, hallways -0.010).

Reading:
- **The slope flattens at 80k** (or drops below what 2 seeds can see):
  +0.003-0.004 per half, against +0.009-0.013 for the doubling before on
  the same seeds. MDE at 2 seeds is ~0.03, so this is "no detectable gain",
  not "zero"; but the rule was "again ~+0.01", and it isn't.
- The two seeds disagree on held-out (+0.024 / -0.019). 40k s101 was the
  best 40k seed (held-out 0.517), so some of s101's drop is that net's
  luck regressing, not 80k hurting.
- s101's round-0 net stopped early (best epoch 4 of 7, val MSE 0.1370 vs
  s1's 0.1317 after 15 epochs): early stopping on a noisy val curve is one
  more source of seed luck at this size.
- Timing: s101 took 63 min (round-0 epochs ~45 s); s1 took 172 min with
  round-0 epochs of 5-8 min, 7-10x slower on the same-size dataset (both
  127 MB, 240k games), while it shared the machine with the two-turn
  ensemble job (0057a8z9) and paging. The 150-min estimate came from s1's
  kind of run; uncontended 80k is about an hour.
- Neither 80k net closes the gap to the champion (night recipe: solve step,
  r2); both ladder leads match data40k r1's -0.019.

## Generated-power arms on the 3-copy bench (job 0057a8z8e; read 04:35 2026-11-01 by a fork of manager run 68e81bce)

`gen_powers_read.py arms --bench data/bench/gen_powers12c3.json --control
lean-thr --arms lean-gen16 lean-gen128` (`results/gen_powers/arms-c3.json`),
r2 nets, 326 cells x 12 fights, paired by cell and seed, 3 seeds:

| arm minus lean-thr | generated set | original set | generated - original | generated bosses (23) |
|---|---|---|---|---|
| gen16 | +0.005 (se 0.005) [+0.014 +0.002 -0.001] | -0.006 (0.007) | +0.011 | +0.016 (0.017) |
| gen128 | +0.004 (se 0.009) [+0.020 +0.003 -0.011] | -0.011 (0.012) | +0.015 | +0.042 (0.018) |
| oracle (earlier read) | +0.013 (se 0.009) [+0.031 +0.007 +0.002] | +0.001 | +0.012 | +0.064 (0.008) |

Reading:
- On the 3-copy bench the arms trained on *other* generated powers gain
  about as much over the original set as the oracle, which trained on the
  bench's own test powers: generated minus original +0.011 / +0.015 vs the
  oracle's +0.012. So what the bench sees in the oracle is mostly general
  familiarity with generated content (cost and deck-slot effects, playing
  odd power cards at all), not learning of the specific powers. Power-
  specific learning at share 0.5 over 43 powers is below the bench's reach.
- Bosses lean the same way in all three arms (+0.016 / +0.042 / +0.064),
  ordered by how much generated content the net saw; small cells (23).
- Consistent across both arms and all seeds: card-played triggers lose
  (-0.027 / -0.032), "OwnerTurnEnd + OwnerLostHp" combinations gain
  (+0.083 / +0.107, 7 cells). Both are slices of the same few cells; not
  chased.
- The original set again costs the arms a little (-0.006 / -0.011;
  Metallicize cells -0.019 / -0.025): content takes deck slots in training.
- Fits the adaptation-burst spec's design: its rule reads target-card gain
  minus other-card gain *within the same nets*, which removes this generic
  familiarity effect. A plain "burst net minus champion on target cells"
  would have counted it as learning.

## Monster lookahead, 2 seeds (jobs 0058 / 0059; read 04:40 2026-11-01 by a fork of manager run 68e81bce)

lean-look (lookahead columns on) minus lean-thr, r2 nets, tight2, paired
per fight by seed (shared round 0). se is over cells and ignores seed
spread, so it is too small: the two seeds disagree by far more than it.
Script: scratchpad `look_read.py` (bits from round.json `tight_results`,
grouped by `data/bench/tight2.json`).

| slice | train | held-out | seeds (held-out) |
|---|---|---|---|
| all | +0.005 (0.003) | +0.004 (0.003) | +0.017 / -0.009 |
| elites + bosses | +0.019 (0.008) | +0.020 (0.007) | +0.060 / -0.020 |
| Gremlin Nob | -0.007 (0.011) | -0.014 (0.010) | -0.024 / -0.005 |
| Lagavulin | +0.013 (0.018) | +0.021 (0.016) | +0.033 / +0.008 |
| Sentries | +0.045 (0.015) | +0.059 (0.014) | +0.179 / -0.061 |
| Slime Boss | +0.025 (0.014) | +0.013 (0.010) | +0.050 / -0.024 |

- Rule (spec: held-out elites + bosses >= +0.045, train >= -0.015; the
  2026-11-01 review asked to read only the Lagavulin and Nob slices, bar
  +0.04 over 2 seeds, set by the manager since none was written): fails.
  Lagavulin +0.021, Nob -0.014; elites + bosses +0.020.
- s1 gains on every elite/boss slice, s101 loses on most: the spread
  between seeds (held-out elites+bosses +0.060 vs -0.020) is the whole
  signal. The Sentries +0.059 is one seed (+0.179).
- Speed: the learn runs took 27 / 23 min (s1 / s101) against lean-thr's
  35 / 21 min, so the ~2.9x slower encoding doesn't show in wall time.
- Verdict: no gain detected on the target slices; lookahead stays off.
  s201 (0060) finishes but isn't needed for this verdict.

## Run-HP first check (jobs 0059c1-c3; read 04:55 2026-11-01 by manager run 68e81bce)

`ladder.py runhp`, 2000 pairs per net against the heuristic, one-turn
search, start HP drawn at run-like levels (hallways 70-100% of max, elites
and bosses 40-100%), score = heuristic's HP lost minus the net's (death =
start HP + 30). Positive: the net loses less.

| Net | Score (HP per fight) | HP lost net / heuristic | Wins net / heuristic | Hallway | Elite | Boss |
|---|---|---|---|---|---|---|
| champion (10-29) | -5.99 [-6.71, -5.27] | 11.58 / 5.60 | 0.983 / 0.984 | -7.3 | -3.5 | +0.2 |
| data40k s1 r1 | -6.38 [-7.04, -5.71] | 11.97 / 5.60 | 0.982 / 0.984 | -6.1 | -8.7 | -2.3 |
| lean-thr s1 r2 | -5.48 [-6.08, -4.88] | 11.08 / 5.60 | 0.978 / 0.984 | -5.2 | -7.4 | -2.3 |

- Pre-registered rule: score -2 HP or worse with the interval excluding 0
  means HP efficiency is a real goal-2 gap. **All three nets pass it by a
  wide margin**: they lose about twice the HP the heuristic does, at the
  same win rate. Train and held-out halves agree (-5.4 to -6.6).
- Why, likely: the label prices HP at 1% of a win (`real_score` = 2 - HP
  lost / 100), and tight fights (median start HP 3-5 on hallways) reward
  only survival. The nets learned to win, not to win cheaply. Over an Act
  of ~15 fights, 6 HP per fight is ~90 HP: the difference between reaching
  the boss healthy and dying on the way.
- The run-HP order (lean-thr, champion, data40k) doesn't match the
  ladder's (champion, lean-thr, data40k), but the intervals overlap.
- Next: an HP-weight label arm judged on run-HP (spec in progress,
  `docs/specs/hp-weight.md`).

## Ladder replay of test 0004 at fixed n (job 0059c4)

data40k s1 r1 against the champion on fresh blocks (test 0021): fixed-n
6000 lead -0.028 (held-out -0.032, train -0.024), against -0.026 where
test 0004's SPRT stopped at 847 pairs. Rule: -0.02 or lower, the early
read stands. So stopping-point leads were not inflated here, and the
shared champion draw didn't bias this verdict.

## Adaptation burst, 3 seeds (jobs 0059b1-b4; read 04:58 2026-11-01 by manager run 68e81bce)

Champion fine-tuned ~10 min (s1 9 min incl. games; s101 / s201 2-7 min
reusing them) on 4000 games per group of varied setups holding 1-2 of 8
target generated power cards, played by the champion, with 50% replay of
heuristic-played varied games. Read on `gen_powers12c3`, paired with the
champion by fight (`results/gen_powers/burst8.json`):

| Part | cells | burst minus champion | seeds |
|---|---|---|---|
| target cards | 87 | +0.049 (0.005) | +0.058 +0.047 +0.043 |
| other generated | 239 | +0.013 (0.001) | +0.013 +0.015 +0.013 |
| original (official powers) | 326 | +0.037 (0.005) | +0.030 +0.046 +0.036 |
| **contrast target - other** | | **+0.036 (0.015)** | +0.046 +0.032 +0.031 |

By group, target / other: elites +0.165 / +0.062, bosses +0.106 / +0.056,
hallways +0.013 / -0.003.

- Rule: contrast >= +0.04 and >= 2 se works; under +0.02 doesn't; between:
  report and run 2 more seeds. +0.036 (2.4 se) is **between**, but every
  seed is positive and on elites the burst's own cards gain +0.10 more than
  other cards. The burst does teach its powers; the bar is narrowly missed.
- **Surprise: the burst nets beat the champion in general.** Original
  fights +0.037, and on the ladder (tight2, one turn) burst8 s1 passes
  (test 0022, fixed-n 6000 lead +0.011: held-out +0.017, elites +0.041)
  and s101 passes (test 0023, +0.011: held-out +0.018, elites +0.031).
  These are the first nets to beat the 10-29 champion. Hallways are level;
  the gain is on elites and bosses and on held-out cards.
- Open: is it the generated cards, or just a warm fine-tune on fresh
  net-played varied games (expert-iteration-like: data from the champion's
  own play, warm start, replay)? Control bursts with no cards (`burst0`,
  0059d1/d2) are running; then ladder them.

## Burst control: the gain comes from the generated powers (jobs 0059d1-d6; read 05:20 2026-11-01 by manager run 68e81bce)

`burst0` = the same fine-tune with no generated cards (varied setups
played by the champion, same game seed, replay as before), 2 seeds. On
`gen_powers12c3` against the champion (scratchpad script
`burst0_read.py`, burst8 restricted to the same 2 seeds for a fair look):

| Part | burst0 | burst8 |
|---|---|---|
| original fights | -0.003 | +0.038 |
| other generated | -0.007 | +0.014 |
| target cards | +0.004 | +0.053 |
| target - other | +0.010 (0.011) | +0.039 (0.016) |

Ladder: burst0 s1 fails (test 0026, fixed-n 6000 lead -0.005); burst8 s1
/ s101 passed (+0.011 each). So a warm fine-tune on the champion's own
games does nothing by itself; **games holding 8 generated power cards
make the champion better on official-card fights too** (elites +0.03-0.04,
held-out +0.017 on tight2). A likely reading: concentrated, varied power
cards teach the net to price "a power now, payoff later" in general, which
is where the nets were weakest (Demon Form probe). This is the first
training change since 10-29 that beats the champion, and it costs ~10 min.

Caveats: burst8 trained on the bench's own test-split powers, so the
3-copy bench is contaminated for it; a burst on 8 train-split powers
(`burst8tr`, queued 0059d9*) checks the general gain without that. Test
0024/0025 ids were left `.pending` by two ladder tests that crashed on a
torn champion cache (fixed: per-process temp file, tolerant read).

**Promoted:** `results/ladder/champion.json` now names burst8 s1
(previous: the 10-29 net), on test 0022's pass.

## HP weight: w = 2 passes (run-HP 0006-0008; read 06:45 2026-11-01 by a scheduled manager run)

Arms are lean-thr plus `hp_weight` (spec `docs/specs/hp-weight.md`),
paired by fight with lean-thr of the same seed (run-HP 0003 for s1, 0004
for s101; all runs play the same 2000 fights at run-like start HP):

| Arm | HP lost | saved vs control (se) | deaths arm / control | tight2 held-out lead, arm - control |
|---|---|---|---|---|
| hpw2 s1 | 8.49 | +2.59 (0.24) | 31 / 44 | +0.025 |
| hpw2 s101 | 8.14 | +2.29 (0.23) | 34 / 33 | -0.016 |
| hpw4 s1 | 9.40 | +1.68 (0.25) | 41 / 44 | +0.003 |
| hpw4 s101 | (0059e4 running) | | | |

- **w = 2 passes the pre-registered rule**: mean +2.44 HP saved (bar 2.0),
  each seed >= +1.0, no more deaths, held-out lead mean +0.004 (bar: no
  worse than -0.02). Gains are broad: train +3.0, held-out +1.5 to +2.2;
  Sentries +5 to +8, wildlife +3 to +6, lots_of_slimes +3 to +5, Lagavulin
  +4, Nob +2 to +3.5; jaw worm, cultist, small slimes level.
- w = 4 (one seed so far) saves less than w = 2: the effect isn't monotone
  in w. A guess: at w 4 more wins hit the 0.1 floor and the outcome noise
  grows, so the net learns less of the order between wins.
- The nets still lose ~2.5-2.9 HP more than the heuristic per fight (8.1-8.5
  vs 5.6): w = 2 closes about half the gap.
- Next (per the spec): hp_weight 2 joins the product recipe. Cheapest form:
  the champion's own burst with weighted targets (`finetune.py` key
  `hp_weight`, added this run), `burst8hp2-s1/s101` queued (0059a1/a2),
  read against burst8 s1 / s101 run-HP (0005 / 0059a3) and on the ladder.

## Burst with HP weight promoted; train-split bursts (read 06:45 2026-11-01, manager 5f767652)

**burst8hp2** = burst8 (same games, cards, seeds) with targets weighted
`hp_weight` 2 (`finetune.py`). Paired by fight with burst8 of the same
seed on run-HP (0011 vs 0005, 0012 vs 0009):

| Seed | HP lost burst8 -> hp2 | saved (se) | deaths | ladder fixed-n 6000 vs burst8 s1 |
|---|---|---|---|---|
| s1 | 11.25 -> 8.21 | +3.05 (0.24) | 37 -> 31 | +0.006 (test 0029, SPRT pass) |
| s101 | 9.39 -> 8.06 | +1.33 (0.17) | 33 -> 29 | -0.000 (test 0030) |

Mean +2.19 HP saved (bar 2.0), ladder no worse (bar -0.005): rule passes,
**burst8hp2 s1 is the champion** (`champion.json`). By type: s1 hallways
+2.9, elites +4.6, bosses -0.4; s101 +1.3 / +1.2 / +1.9. The two burst8
seeds themselves differ by 1.9 HP (11.25 vs 9.39), so seed spread in run-HP
is ~2 HP, much more than the hp-weight spec's ~0.5 guess; read single-seed
run-HP numbers loosely. The champion still loses 8.2 HP per fight vs the
heuristic's 5.6.

Also: lean-hpw4 s101 saves +2.00 (0010 vs 0004; s1 +1.68): w 4 mean
+1.84, "between", below w 2's +2.44. w 2 stays.

**Train-split bursts (burst8tr, 8 train-split generated cards, from the
10-29 net):** ladder against burst8 s1 fixed-n -0.012 / -0.011 (tests
0028, 0031), so about level with the 10-29 net on tight2 (hallways -0.013,
elites level). On `gen_powers12c3` against the 10-29 net (none of their
cards is on the bench):

| | unseen generated cards | original cards | gen. elite / boss | orig. elite / boss |
|---|---|---|---|---|
| burst8tr | +0.014 (s1 +0.017, s101 +0.012) | +0.013 | +0.085 / +0.082 | +0.054 / +0.107 |
| burst8 | +0.014 (non-target) | +0.038 | +0.065 / +0.051 | +0.062 / +0.196 |
| burst0 (no cards) | -0.004 | -0.003 | +0.036 / +0.011 | -0.011 / -0.022 |

So a burst on *some* generated power cards lifts play on *other, unseen*
generated power cards by ~+0.018 over the no-card control, mostly on
elites and bosses (+0.05 to +0.08): the first transfer to unseen
mechanics we have measured (goal 1), 2 seeds sharing one game set.
burst8's extra gain on original cards (+0.038 vs +0.013), and its ladder
pass, did not come back with other cards: either burst8's test-split
cards happen to teach more, or the ladder pass (+0.011, two seeds sharing
one card and game set) was partly luck. The ratchet / 16 / 32-card bursts
(0059g*, fresh card sets) will tell.

## Ratchet and more cards per burst (tests 0032-0039, run-HP 0014-0021; read 07:40 2026-11-01, manager 5f767652)

Ladder against the champion (burst8hp2 s1), fixed-n 6000 lead, and run-HP
(champion 8.21 HP lost per fight):

| Net | from | ladder s1 / s101 | HP lost s1 / s101 |
|---|---|---|---|
| ratchet8trhp2 (hp_weight 2, 8 fresh cards) | champion | -0.005 / +0.003 | 7.42 / 7.21 |
| ratchet8tr (no HP weight) | burst8 s1 | -0.005 / +0.001 | 9.46 / 10.28 |
| burst8tr (8 cards; for reference, vs burst8 s1) | 10-29 | -0.012 / -0.011 | |
| burst16tr | 10-29 | -0.013 / -0.012 | 9.49 / 11.06 |
| burst32tr | 10-29 | -0.023 / -0.009 | 10.87 / 10.09 |

- **Ratchet: no win-rate gain** (both seeds level with the champion), so a
  second burst doesn't stack on the first. With hp_weight it saves a little
  more HP (+0.79 / +1.00 vs the champion, se 0.17), likely a second dose
  of the same weighting. Not promoted (the ladder rule needs a pass).
- **More cards per burst: no ladder gain**; 32 is if anything worse.
- On `gen_powers12c3` (vs the 10-29 net, none of the cards on the bench),
  unseen generated cards: burst8tr +0.014, burst16tr +0.019, burst32tr
  +0.018 (every seed +0.012 to +0.023; burst0 -0.004); originals +0.013 /
  +0.030 / +0.020; bosses +0.08 to +0.15 on both card kinds. **The transfer
  to unseen generated powers holds over three card sets and six nets.**
- Why bench gains but ladder doesn't: the bench is elite/boss fights with a
  power card in the deck; the ladder is ~73% hallways, where bursts are
  level or slightly worse (-0.002 to -0.024). Bursts teach power pricing,
  which matters in long fights with powers, and cost a little elsewhere.
  burst8's original ladder pass (+0.011) is the outlier among 5 card sets.
- So for goal 1 the burst is a working adaptation tool (generated powers
  -> unseen generated powers, and it fixes power-heavy boss fights); for
  the product ladder it's spent. Next burst work, if any: hallway replay
  share up, or bursts on boss/elite setups only.

## Run-HP at two turns, burst8 s1 (run-HP 0013 vs 0005; read 09:05 2026-11-01, manager 4440e145)

burst8 s1 (no HP weight) under the fallback two-turn player against its
own one-turn run-HP, the same 2,000 fights paired by (cell, seed); HP saved
= one-turn lost minus two-turn lost (scratchpad `runhp_pair.py`):

| Slice | n | HP saved | win |
|---|---|---|---|
| all | 2000 | -0.55 (se 0.33) | +0.006 |
| boss | 132 | +0.97 (1.59) | +0.038 |
| elite | 411 | +0.88 (0.90) | +0.019 |
| hallway | 1457 | -1.09 (0.35) | +0.000 |
| held-out / train | 996 / 1004 | -0.05 / -1.04 | |

By encounter the hallway loss sits on multi-monster fights:
Exordium Wildlife -8.73 (se 1.85), Three Louse -3.59 (1.02), Large Slime
-2.72 (1.19); gains on Looter +3.97 (0.56), Gremlin Nob +3.04 (1.22).
Two-turn overrides one-turn on 16-37% of decisions (Wildlife 37%, the
most), so depth changes many hallway moves, not few.

- Pre-registered rule (decisions "Run-HP at two turns"): saved < 1.0 HP
  means the bleeding isn't a search-depth problem. **-0.55: fails.**
- Caveat that limits the reading: burst8 s1's leaf values were trained
  without HP weight, so they score winning, which is near-certain in
  hallways. Deeper search then optimises a value that is flat there and
  can't be expected to save HP; the overrides on Wildlife are moves the
  leaves are indifferent to. The test that decides is 0059h2: the
  HP-weighted champion (burst8hp2 s1) at two turns, paired with 0011.

## Run-HP at two turns, HP-weighted champion, and where the HP goes (run-HP 0022 vs 0011, tempo probe; read 09:50 2026-11-01, manager 4440e145)

**Depth with HP-weighted leaves.** burst8hp2 s1 under the fallback
two-turn player vs its own one-turn run-HP (0011), 2,000 fights paired:
saves **+0.59 HP (se 0.19)**, win +0.002; elites +1.74 (0.62), hallways
+0.39 (0.14), bosses -0.86 (1.43). Three Sentries +2.9, Nob +2.2, Looter
+1.9; Exordium Wildlife -2.4 (0.82) again. With HP in the leaves depth
saves a little (burst8 s1, no HP weight: -0.55), but the rule's bar is
1.0 and the gap to the heuristic is 2.6: **fails; depth is not the HP
lever.** The product's run-HP stays measured at one turn.

**Where the 2.6 HP go** (`scripts/analysis/tempo_probe.py`, the same
2,000 run-HP fights, champion and heuristic one-turn, turns recorded;
`results/probes/tempo-burst8hp2-s1.json`; reproduces 0011's 8.21 / 5.60):

| Slice | HP lost heur / net | turns heur / net | HP lost per turn heur / net |
|---|---|---|---|
| hallway (1457) | 0.50 / 2.85 | 3.21 / 3.12 | -0.09 / 0.56 |
| elite (411) | 16.02 / 21.26 | 5.21 / 5.79 | 2.76 / 3.24 |
| boss (132) | 29.34 / 26.71 | 8.36 / 8.14 | 2.08 / 1.97 |

- **Hallways (70% of the gap): the net is faster, not slower.** It wins
  in fewer turns on 11 of 12 hallway encounters (Looter 2.55 vs 2.99,
  Jaw Worm 2.36 vs 2.58) and takes more damage per turn on all of them:
  it races, trading HP for speed, where the heuristic blocks. The
  earlier note "drags multi-monster hallways out" (from the hp_weight-0
  nets) does not describe the current champion.
- **Elites: slower and more damage per turn** on Three Sentries (7.17 vs
  6.36 turns) and Lagavulin (6.30 vs 5.63); Nob nearly level.
- **Bosses (Slime Boss): the net is better** (-2.6 HP).
- hp_weight 4 saved no more than 2, so stronger weighting isn't the fix.
  The net sees each monster's `intent_damage` and its own block, but not
  the unblocked total (a sum and a max(0, ·) it must learn); the
  heuristic computes exactly that (`heuristic.rs` `unblocked_now`). So a
  cheap next spec for hallways: an `unblocked_incoming` scalar (sum of
  intent damage minus block, floored at 0), off by default, judged on
  run-HP hallways. A tempo / turn-count feature would target the wrong
  thing in hallways; it may still help on Sentries / Lagavulin.

## The nets don't price HP: no start-HP column (HP price probe; 10:20 2026-11-01, manager 1474ae6a)

`scripts/analysis/hp_price_probe.py`: 600 run-HP pool fights (block 6000
on, the `ladder.py runhp` fights) played by each net at one turn; 3
decision states per fight (HP > 12); the player's current HP lowered by
3 / 6 / 10 by patching the state's bytes (start HP unchanged); the net's
static value read. Value drop per HP of current HP (se ~0.0000-0.0002 on
hallways, 1,308 states; ~0.001 on bosses, 120):

| net | label's price (w / 100) | all | hallway | elite | boss |
|---|---|---|---|---|---|
| champion burst8hp2 s1 (w 2) | 0.020 | 0.0023 | 0.0010 | 0.0039 | 0.0113 |
| 10-29 net (w 1) | 0.010 | 0.0022 | 0.0005 | 0.0047 | 0.0133 |
| lean-hpw2 s1 r2 (w 2) | 0.020 | 0.0020 | 0.0007 | 0.0035 | 0.0110 |
| lean-thr s1 r2 (w 1) | 0.010 | 0.0017 | 0.0001 | 0.0035 | 0.0142 |

(d = 3; d = 6 and 10 alike.) At a fixed start HP each HP lost now is lost
at the end, so the label's price of an HP is about w / 100 x P(win), more
near death. In hallways (P(win) ~0.99) every net prices HP 10-100x below
its label; where HP buys survival (bosses) the price is closer.

Why: the score counts HP lost from the combat's start, but no column
holds the start HP, and training games start at a random 10-100% of max
HP (`selfplay.VARIED`). In a safe state, a higher current HP mostly means
"started higher", which doesn't change the score, so the fit gives
current HP almost no weight there. HP weight 2 raised the hallway price
0.0001 -> 0.0007 and saved ~2.4 HP per fight; the label's price would be
30x that. This explains the tempo probe's picture: search trades HP for
damage at a tiny fraction of the HP's real price, so the nets race and
under-block in hallways while the heuristic, which counts damage taken at
1% per HP directly, blocks.

What it changes: the planned `unblocked_incoming` column can't help (one-
turn leaves are after End turn: the monsters have already hit and the HP
column shows the loss; the net just doesn't price it). The fix is a
`start_hp` player column (spec `docs/specs/start-hp.md`), so HP lost is
one linear step from two columns. Four arms queued (decisions "Start-HP
column").
Outputs: `results/probes/hp_price-{champ,n1029,hpw2,thr}.json/.txt`.

## HP bonus at the leaves closes the HP gap with no training (10:35-11:00 2026-11-01, manager 1474ae6a)

Zero-training check of the probe's diagnosis (`scripts/analysis/hp_bonus_runhp.py`):
the champion (burst8hp2 s1) plays the 2000 run-HP fights at one turn with
its leaf value plus c x (HP - start HP), optionally times its value / 2
(~P(win), "scaled": the label's HP price is w / 100 x P(win)). Start HP is
read through the new `start_hp` encoder column. Paired by fight with run-HP
0011 (the same net without bonus; c = 0 reproduces it exactly).

| player | HP lost | saved (se) | hallway | elite | boss | wins (vs base, +/- fights) |
|---|---|---|---|---|---|---|
| champion (0011) | 8.21 | | 2.85 | 21.26 | 26.71 | 0.985 |
| heuristic | 5.60 | | 0.50 | 16.02 | 29.34 | 0.984 |
| c 0.005 | 5.94 | +2.27 (0.16) | 0.69 | 18.33 | 25.36 | 0.981 (+3/-10) |
| c 0.01 | 5.52 | +2.69 (0.17) | 0.27 | 17.97 | 24.65 | 0.981 (+2/-10) |
| c 0.02 | 5.79 | +2.42 (0.22) | 0.26 | 19.03 | 25.65 | 0.973 (+2/-25) |
| **c 0.01 scaled** | **5.46** | **+2.75 (0.16)** | 0.29 | 17.72 | 24.36 | **0.984 (+4/-6)** |
| c 0.02 scaled | 5.50 | +2.71 (0.20) | 0.16 | 18.64 | 23.58 | 0.979 (+4/-15) |

(HP lost counts a death as start HP + 30, the run-HP rule.) A first try
with a bare c x HP lost 2.95 HP on 100 fights: search scores finished
combats with the engine's own score, so an uncentred bonus made every
unfinished leaf look ~0.5 better than winning now, and the player dragged
fights out.

Reading: the diagnosis holds. Giving search the HP price the net lacks
removes the whole gap to the heuristic (hallways 2.85 -> 0.29 HP, below the
heuristic's 0.50) in every group and both halves. Unscaled bonuses cost
wins on bosses and elites (they double-count where the net already prices
HP through survival); scaling by the net's win estimate removes that cost
at c 0.01. Selection caveat: 5 settings tried on the same fights; the
pick's margin over its neighbours is small, its gain over the base is ~17
se. Not yet checked: fresh fights, tight fights (the ladder), two-turn
play. Outputs `results/probes/hp_bonus-champ-c*.json/.txt`.

Confirmation (11:05, Rust `NetEvaluator` `hp_bonus`, player spec
`<net>.pt@hpb0.01`): on the same fights the Rust bonus plays like the
Python one on 99.95% of fights (run-HP 0023: +2.75 saved vs 0011). On
**fresh fights** (block 9000, run-HP 0024 champion vs 0025 champion with
bonus): 5.43 HP lost vs 8.23, **saved +2.80 (se 0.15)**; heuristic 5.75;
hallways -0.01 vs 2.88 (heuristic 0.35), elites 17.12 vs 20.34, bosses
29.04 vs 29.50 (+0.46, se 0.99); wins -0.002 (+2/-6 fights). Tight-fight
ladder, fixed n 6000 (test 0041): lead -0.0012 (held-out -0.0007, train
-0.0017; 19 vs 26 discordant fights): on tight fights, where start HP is
low and the net prices HP through survival, the bonus barely changes
play. Promoted (decisions "HP bonus promoted"). Bosses gain least: the
next HP lever is there and on elites.

## Where the HP gap is left after the bonus (run-HP 0023-0025 by encounter; read 12:20 2026-11-01, manager f3fd4dee)

Per encounter, the champion `@hpb0.01` against the heuristic (score =
heuristic's HP lost minus the champion's, a death costing start HP + 30;
0025 fresh fights block 9000, 0023 block 6000, ~130 pairs per encounter):

| encounter | 0024 bare | 0025 bonus | 0023 bonus | wins champ / heur (0025) |
|---|---|---|---|---|
| slime_boss | +5.00 (se 1.86) | +5.46 (1.92) | +5.01 (2.08) | 0.811 / 0.742 |
| gremlin_nob | -1.70 (0.65) | -1.46 (0.94) | -2.01 (0.92) | 0.963 / 0.985 |
| lagavulin | -5.85 (1.07) | -2.87 (0.91) | -3.46 (1.08) | 0.978 / 0.978 |
| three_sentries | -6.46 (1.01) | -0.15 (0.91) | +0.39 (0.81) | 0.993 / 0.986 |
| hallways (11) | -0.15 to -4.68 | -0.31 to +0.79 | -0.30 to +0.80 | all ~1.000 |

What it says:
- The bonus fixes the hallways (every hallway encounter now within ±0.8)
  and Three Sentries (-6.5 -> 0). What's left sits on two elites:
  **Lagavulin (~-3 HP per fight on both fight sets)** and **Gremlin Nob
  (~-1.7 HP and ~1.5-2 points fewer wins on both sets)**.
- The run-HP pool's only boss is Slime Boss (tight2 has no Hexaghost or
  Guardian), where the champion leads by ~+5 HP and +7 points of wins. So
  "bosses gain least from the bonus" (+0.46) only means Slime Boss was
  already won by the net; the pool can't see the other two bosses. The
  gauntlet (spec `gauntlet.md`) plays all three.
- Not acted on yet: two-turn run-HP with the bonus (0059l9) shows whether
  depth fixes these two elites (net-leaf depth's biggest gain was
  Lagavulin, +0.128 wins on tight_bosses-like fights). If Lagavulin and
  Nob stay negative at two turns, a decision diff on them (where the net
  and the heuristic choose differently, as `decision_diff.py` did for the
  Guardian) is the next probe.

## Act-1 gauntlet: first check and HP-price sweep (0059l4a-l4f; read 16:30 2026-11-01, manager)

500 sequences (250 per half), 11 fights with HP carried over (spec
`gauntlet.md`), the champion `burst8hp2-s1` at HP bonus c against the
heuristic, paired by sequence (`gauntlet.py read`):

| player | clear | minus heuristic (se) | elite-1 deaths | elite-2 deaths | boss deaths | boss win given reached |
|---|---|---|---|---|---|---|
| heuristic | 0.596 | | 1 | 49 | 128 | 0.70 |
| champion bare | 0.448 | -0.148 (0.019) | 8 | 112 | 95 | 0.70 |
| c 0.005 | 0.580 | -0.016 (0.016) | 10 | 65 | 106 | |
| **c 0.01** | **0.616** | **+0.020 (0.016)** | 12 | 53 | 99 | 0.76 |
| c 0.02 | 0.608 | +0.012 (0.018) | 14 | 46 | 105 | |
| c 0.04 | 0.482 | -0.114 (0.020) | 46 | 39 | 144 | |

(Elite 1 is floor 6, elite 2 floor 9, the boss floor 11; train half clears
~0.08-0.16 less than held-out for every player.)

What it says:
- The shape works: clear rates sit at 45-62%, inside the spec's 10-90%.
- **c = 0.01 stays** (pre-registered rule: a c must beat it by >= +0.04 and
  2 se; none does). The bonus is worth +0.17 clears over the bare net, the
  per-fight HP gap closed earlier showing up at run level.
- The champion with the bonus is level with the heuristic on clears
  (+0.020, se 0.016; 500 more sequences are running to tighten it). It
  wins bosses more often given it reaches them (0.76 vs 0.70, at the same
  HP at the boss, 65.8 vs 66.0) but dies more on elites, most of all on
  the **first** elite at high HP (12 vs 1).
- **Gremlin Nob punishes the bonus.** Replaying the elite-floor losses
  reproduces each as a real death in 7-22 turns (not the 100-turn stall
  limit). Early-elite deaths grow with c (8 / 10 / 12 / 14 / 46), mostly
  Nob at 57-80 HP. A probe (`scripts/analysis/nob_probe.py`, the 180
  gauntlet sequences whose first elite is Nob, all at 70 HP,
  `results/probes/nob-probe.json`) shows why: skills played per fight
  heuristic 1.32, bare net 1.68, c 0.01 2.28, c 0.04 4.13; wins 0.994 /
  0.983 / 0.972 / 0.833. Nob gains Strength for every skill the player
  plays, so a price on HP lost *this turn* buys block now and pays later
  in Nob's damage, which one-turn search sees only as Nob's Strength in the
  leaf state, priced by the net. This is the bonus's known weakness (a
  short-horizon price), and a test case for the survival-score arms (their
  nets predict HP lost from now, so they should price Nob's Strength).

## Start-HP arms read (run-HP 0030-0035 vs 0003/0006/0007/0026-0028; read 16:35 2026-11-01, manager)

Saved HP per fight (control's HP lost minus the arm's, 2000 paired fights,
`start_hp_read.py`), tight2 held-out win from round.json:

| arm | vs bare control | vs control + bonus | arm + bonus vs control + bonus | held-out win (control) |
|---|---|---|---|---|
| start-hpw2 s1 | +3.42 (0.17) | -0.26 (0.14) | +0.23 (0.14) | 0.515 (0.518) |
| start-hpw2 s101 | +1.56 (0.17) | -1.79 (0.16) | -0.66 (0.16) | 0.492 (0.509) |
| start (w 1) s1 | +4.70 (0.27) | -0.82 (0.19) | +0.63 (0.18) | 0.501 (0.492) |

Deaths arm - control: +9 / +7 / -9 (bare), within the rule's +20.

What it says:
- The start-HP column works as the spec predicted: start-hpw2 saves +2.49
  HP on the mean of 2 seeds (each > 0), held-out within 0.02 (s101 -0.017,
  close to the edge): **the spec's rule passes**. The probe's mechanism (no
  start-HP column, so HP priced 10-100x too low) is confirmed by training.
- But it does not beat the search-time bonus on the same nets (-0.3 to
  -1.8 HP), and on top of the bonus it adds nothing (+0.23 / -0.66 /
  +0.63). The two fix the same thing; the bonus needs no retraining and
  works on the existing champion. So the column stays off by default and
  the champion is **not** burst with it (decisions "Start-HP column passes
  but the bonus stays").
- The w 1 arm's second seed (0059l8) is parked: the question it answers
  (is HP weight 2 still needed with the column?) no longer leads anywhere.

## Depth on generated powers: not content-specific (0059l3/l4; read 16:25 2026-11-01, manager)

`gen_powers_read.py depth` on `gen_powers12c3` elites and bosses (86 cells,
2,064 fights per player), two-turn minus one-turn wins, generated twin vs
original card in the same cell:

| leaves | gain on generated | gain on original | contrast (se) |
|---|---|---|---|
| 10-29 net | +0.109 | +0.104 | +0.005 (0.024) |
| heuristic | +0.026 | +0.023 | +0.003 (0.019) |

Pre-registered rule: |contrast| < 0.015 means depth's gain isn't
content-specific; that's the reading. Depth gains ~+0.10 for the net
everywhere on these fights (bosses +0.14-0.16, elites +0.08-0.10), four
times what it gains for the heuristic here. So depth is a general repair
of the net's short-horizon errors, not a special fix for new mechanics;
the earlier novelty slice (fights with an unseen official power card gain
more, +0.076 vs +0.012, replicated on fresh fights at +0.096) compared
fights, while this compares a generated card with the original it
replaces in the same fight, and finds no extra gain for the generated one. Per-trigger slices are
small (1-18 cells) and not read.

## Ladder replay under a trinomial GSPRT (manager fork, 16:57 2026-11-01)

Review 2026-11-01b direction 6, offline (`scripts/analysis/gsprt_replay.py`,
output `results/ladder/gsprt-replay.json`). Each of the 39 ladder tests is
replayed in its recorded pair order (d = cand - champ in {-1, 0, +1}) under
a trinomial generalised SPRT: outcome shares fitted by maximum likelihood
with the mean held at 0 (H0) and at D1 = 0.01 (H1), fishtest's 1e-3
pseudo-count per outcome, the ladder's ALPHA = BETA = 0.05. Where a test
played fixed-n pairs after it stopped, the GSPRT carries on through them
(same fights, same order) to find its own stopping point.

Verdicts: **none changes sign.** On the 36 tests where both rules decide,
the GSPRT gives the same verdict and needs 56,122 pairs against the
ladder's 55,431 (+1.2%). The ladder's normal-form LLR takes the variance
around the observed mean, which is a little smaller than the variance
under H0 or H1, so it stops slightly early; the GSPRT is the exact
likelihood ratio. Tests whose stopping point moves by more than ~50 pairs
or whose verdict isn't reached:

| test | candidate | recorded | discordant | GSPRT |
|---|---|---|---|---|
| 0001 | 10-29 net vs heuristic | pass @ 1,150 | 147 | pass @ 1,330 |
| 0008 | lean-thr s101 | fail @ 1,349 | 109 | no decision by 1,500 (lead -0.013) |
| 0013 | cover21 s101 | fail @ 575 | 74 | fail @ 617 |
| 0015 | distil s1 | fail @ 771 | 71 | fail @ 820 |
| 0018 | seed-check s201 (rerun) | fail @ 4,274 | 194 | fail @ 4,327 |
| 0020 | data80k s101 | fail @ 699 | 49 | fail @ 756 |
| 0040 | champion `@hpb0.01` (fresh fights) | fail @ 200 | 0 | no decision by 500 |
| 0041 | champion `@hpb0.01` (fixed-n run) | fail @ 200 | 2 | fail @ 4,090 |

0040 / 0041 are the near-clone case: the ladder's variance floor (1e-6)
turns 0 or 2 discordant pairs into an LLR of -5000 or -3, an instant
"fail". The GSPRT stays near 0 until discordant pairs pile up, and on 0041
it still fails, at 4,090 pairs: the bonus is not 0.01 better at tight2
wins, which matches the fixed-n read (-0.0012).

Gauntlet c sweep as a sequential test (each c against c = 0.01, paired by
sequence index in order, H1 = +0.04, the sweep's bar): bare fails at
sequence 73, c 0.005 at 73, c 0.02 at 288, c 0.04 at 122. So each sweep
point needed 73-288 sequences, not 500: a gauntlet SPRT would cut a sweep
like this to about a third. The champion `@hpb0.01` against the heuristic
over the pooled 1,000 sequences (H1 = +0.03) reaches no decision (lead
+0.018, 126 discordant), consistent with "level, maybe slightly ahead".

Reading: should `ladder.py` switch? **Not urgently.** On the tests run so
far the normal form never gave a wrong verdict, and the GSPRT costs about
1% more pairs. Its one real gain is at near-clones (search-time constants,
an evaluator setting), where the ladder's verdict after 200 pairs means
nothing; for those, either switch the LLR to the GSPRT (a small change in
`llr` / `decide`) or keep testing them on fixed-n, run-HP and the gauntlet
as now. Recommended: switch the LLR to the trinomial GSPRT with the
current D1 and MIN_FIGHTS when `ladder.py` is next touched (it is the exact
test and removes the -5000 artefact), and give the gauntlet a sequential
mode on discordant sequences for sweeps.

## Enemy-Strength price: fixes Nob, costs bosses (nob_probe + gauntlet 0059l7q1; read 17:10 2026-11-01, manager)

Spec `enemy-strength-price.md`. Step A (`nob_probe.py`, 180 first-elite
Nob fights at 70 HP, `results/probes/nob-probe-esp.json`), champion
`@hpb0.01` plus `@esp<k>`:

| k | Nob wins | skills per fight |
|---|---|---|
| 0 (champion + bonus) | 0.972 | 2.28 |
| 0.01 | 0.972 | 1.79 |
| 0.02 | 0.978 | 1.46 |
| 0.04 | 0.994 | 1.06 |
| heuristic | 0.994 | 1.32 |

k 0.04 qualifies (wins >= 0.985, skills <= 1.8). Step B, gauntlet
sequences 0-499 paired with the champion + bonus: clears 0.596 vs 0.616,
**-0.020 (se 0.009)**; level with the heuristic (+0.000). Deaths by
encounter: Nob 23 -> 20, but Hexaghost 46 -> 52, the Guardian 38 -> 41,
Sentries 22 -> 24; HP at the boss 63.3 vs 65.3. **Fails** the rule.

What it says: the price buys Nob, but over a run it costs more elsewhere.
The champion attacks where it blocked, against every monster that gains
Strength (the Guardian and Hexaghost too), and reaches the boss with 2 HP
less. Nob was a small share of the gauntlet's deaths (23 of 194); the real
losses are bosses and the second elite. A flat price on enemy Strength is
too blunt: a Strength point is worth as many HP as hits are left, which a
constant can't know. The code stays (off by default); the learned route
(survival-score arms) and depth are the fixes left to test.

## Two-turn + HP bonus loses HP in easy hallways: the floored finish score (run-HP 0036 vs 0023 / 0022; read 18:40 2026-11-01, manager 86979d83)

Run-HP 0036: the champion `@hpb0.01` playing two-turn (fallback, sample_k
4, max_nodes 400k) vs the heuristic, same 2000 fights (block 6000) as 0022
(two-turn, no bonus) and 0023 (one-turn + bonus). HP lost 5.84 vs the
heuristic's 5.60 (score -0.25 HP [-0.66, +0.16]), wins level (0.984).
Paired against the other two (`start_hp_read.py`, HP saved = control's
loss minus the arm's):

| arm vs control | all | hallway | elite | boss |
|---|---|---|---|---|
| two+bonus vs one+bonus (0023) | -0.39 (se 0.17) | **-0.93 (0.11)** | **+1.46 (0.53)** | -0.21 (1.47) |
| two+bonus vs two bare (0022) | +1.78 (0.15) | +1.25 (0.13) | +3.27 (0.45) | +3.02 (1.19) |

Per encounter (HP lost, two+bonus / one+bonus / two bare / heuristic): the
loss is in the *easy* hallways, where the bonus barely moves two-turn play:
cultist -2.08 / -3.23 / -2.02 / -2.43, two_louse -1.50 / -2.77 / -1.47,
small_slimes -0.95 / -1.94 / -0.93, looter 0.45 / -0.80 / 0.77, jaw_worm
0.47 / -1.42 / 0.76 (negative: healed above the start HP). In hard hallways
the bonus helps two-turn a lot (lots_of_slimes 6.76 -> 4.81, large_slime
4.57 -> 2.05). Elites gain from depth (Lagavulin 17.90 vs 20.59 one-turn,
Sentries 17.47 vs 18.38, Nob 13.33 vs 14.09); Slime Boss level (21 deaths
each).

Why: search scores a finished combat with the engine's score, `2 -
max(0, start HP - end HP) / 100`, with end HP after Burning Blood's +6 and
no bonus. In a won fight, damage up to the heal costs nothing; an
unfinished leaf pays c x f per HP. Two-turn search reaches many more wins
inside its horizon (kill on turn 2 after taking turn 1's hits), so it takes
up to 6 HP for a faster kill. Matches the outcome shape: one-turn + bonus
ends 14.1% of hallways with no damage taken, two-turn + bonus 6.6%; fights
ending 1-6 HP down after the heal's room: 49.6% vs 52.1%. Over a run that HP
is real (the heal would have raised HP). Fix: spec `end-hp-bonus.md`
(`@hpe<c>`, the same "HP after the coming heal" price on both leaf kinds).

What it changes: depth's elite gain (+1.46 HP over one-turn, on top of the
bonus) is real and is where the gauntlet's deaths are, but the hallway loss
eats it over a run. The two-turn gauntlet (0059l7r3a/b, `@hpb`) is the
"before" measurement; `@hpe` two-turn reads next.

## Two-turn search: where the time goes (profile 20:10-21:30 2026-11-01, manager 9623e125)

Method: py-spy (`--native`) on a symbol build of `sts` (release + debug
info, `target/prof`) playing the champion `@hpb0.01` two-turn on gauntlet
elite / boss / hard fights (sequences 900+, HP 60), plus
`engine/examples/two_turn_phases.rs` (the tree rebuilt with a timer per
step, heuristic leaves, 150 elite and boss states from heuristic play).

- **Net leaves, before the fix (3,000 samples):** tree building 52%
  (hashing whole 1 KB `CombatState`s with SipHash 25%, table growth
  `reserve_rehash` 19%, `apply_action` 10%), leaf scoring 47% (encoding
  12%, the net's layers ~30%). With heuristic leaves the split is about the
  same: the heuristic estimate costs as much per leaf as the net (~125 us).
- **Heuristic leaves (Rust example):** the heuristic's estimate is 76% of
  the time (~180 us per leaf); tables 17%; stepping 5%.
- **The cost is concentrated.** Over 197 decisions, 10% of decisions take
  88% of the time (p50 23 ms, p99 6 s, max 26 s); three_louse took 61 of
  81 s in 10 decisions (~39k leaves each: the louses' random damage and
  Curl Up multiply chance outcomes).
- **Fast tables (spec `fast-search-tables.md` step 1):** an Fx-style hasher
  on `memo` / `leaf_index`. Results bit-identical (150 heuristic-leaf
  searches and 200 + 40 net-leaf searches dumped and compared). Tree alone
  (flat leaves): 21.3 -> 11.6 us per node (1.84x). Whole search: 1.13x with
  heuristic leaves; with net leaves the profile shares move (hashing 25% ->
  9%, growth 19% -> 10%, net 47% -> 58%), i.e. ~1.2x; wall-clock and cycle
  timings while the gauntlet jobs ran varied up to 2x for one build, so the
  measured gain (~1.1-1.2x) misses the spec's 1.3x bar. Kept: free and
  exact.
- **What's left, net leaves (after the fix, louse decisions):** leaf
  scoring ~100% of the sample there: the net's layers ~65% (per-card and
  per-hook-row MLPs ~40%, head ~16%), encoding 33%, half of it vector
  regrowth (`finish_grow` in `Encoder::encode`). Most cards' and rows'
  inputs repeat across a search's leaves, so caching their layer outputs
  within one `evaluate` call (exact) is the next speed lever, with a
  `reserve` in the encoder.
- **Net leaf cache (spec `net-leaf-cache.md`):** `Net::forward` computes
  each distinct hook row's and card's layer output once per call; the
  encoder reserves its buffers; the Fx hasher moved to `engine/src/fxhash.rs`.
  Option values bit-identical (40 fixed gauntlet states, champion two-turn,
  dumped against both earlier builds; engine dump unchanged). Min-of-3
  cycle counts, alternated 3x: 10.3 -> 6.6 Gcycles (**1.57x**, every pair
  agrees). With the table fix, net-leaf two-turn search is ~1.9-2x faster
  than the 2026-11-01 morning module.
- **Heuristic rate cache (decisions "Heuristic rate cache built"):**
  `damage_rate` was 93.5% of the heuristic's leaf estimate (the monster
  move walk redone at every leaf; `two_turn_phases --parts`). Cached per
  (kind, slot, moves), bit-identical: heuristic-leaf two-turn search
  **5.1x** faster; the tree is now most of a heuristic-leaf decision.

## Novelty cost sits past the one-turn horizon (post hoc slice of 0059l3/l4; 22:15 2026-11-01, manager)

`scripts/analysis/gen_timing_slice.py` on the first generated-bench depth
read (`gen_powers12c3`, elite + boss, 86 cells; the 10-29 net and the
heuristic, one turn and the fallback two-turn player). Cells are sliced by
when the swapped test card's power fires. Numbers are generated twin minus
original, se over cells, then over the 9-13 distinct cards per class (each
card sits in 1-4 cells, so the card se is the honest one).

| class (cells) | net depth gain | net - heuristic, one turn | net - heuristic, two turns |
|---|---|---|---|
| turn start (16) | **+0.141** (0.053) | **-0.214** (0.078) | -0.078 (0.056) |
| card played (19) | -0.088 (0.051) | +0.206 (0.053) | +0.070 (0.035) |
| turn end (18) | -0.023 (0.052) | +0.060 (0.065) | +0.060 (0.064) |
| lost HP (33) | +0.008 (0.037) | +0.101 (0.046) | +0.119 (0.031) |
| turn start - card played, over cards | **+0.200** (0.098) | -0.433 (0.115) | -0.181 (0.064) |

Raw win rates (net one turn, generated / original): turn start 0.318 /
0.578, card played 0.281 / 0.469; heuristic one turn 0.594 / 0.641 and
0.254 / 0.649.

What it says:
- **The whole-bench null hid a split.** Depth's extra gain on generated
  cards is +0.005 over all cells (the "not content-specific" read above),
  but +0.14 on powers that fire at the owner's turn start and -0.09 on
  powers that fire on the owner's card plays. The heuristic's own depth
  gain shows no such split (-0.05, se 0.10).
- **Why it fits the horizon.** A one-turn leaf stops at the next turn's
  draw request (`state.rs`: block and energy reset, then the draw, then
  `OwnerTurnStart` hooks), so a turn-start power has paid nothing yet at
  any leaf: the net must price it from its power columns, and on an
  unseen (trigger, effect) pair it can't. A card-played power pays inside
  the turn, so the leaf already shows its block or damage. Two-turn search
  plays through the next turn start and sees the payoff.
- **Caveats.** Post hoc, one net, chosen after the 11-01b review's
  GainEnergy hint (a subset of the turn-start cells). The heuristic prices
  10 of the 16 turn-start cards and none of the others, so the
  net-minus-heuristic columns mix the net's error with the heuristic's
  pricing; the net's own depth gain is the clean column. Turn-start test
  cards are mostly energy / Strength / Vulnerable effects and "used up";
  timing and effect kind are not separated (the pack has only ~10 test
  cards per class).

**Pre-registered replication (job 0061, queued 22:15):** the same net on
fresh fights (`data/bench/gen_powers8c3f12.json`: tight2 held-out fights
12-19 per cell, cards re-drawn with pick seed 7; built by the new
`gen_powers_read.py build --first --pick-seed`). Read with
`gen_timing_slice.py results/gen_powers/depth/gen_powers8c3f12-2026-10-29-seed-check-r2-s1-1a789b2-elite_boss.json`.
**Pass: net depth gain, turn start minus card played, >= +0.10 over cells
and > 0 over cards.** It re-uses most of the same cards, so a pass
replicates over fights, not over cards. Pass: depth is the custom-content
fix for powers that pay later, and a cheap one-turn variant becomes worth
a spec (score each leaf after the player's deterministic turn-start hooks,
a "turn-start peek"; it double-counts known permanent turn-start powers by
one firing, so it needs its own check). Fail: the split was slice noise.

## Two-turn champion on the gauntlet, before the end-HP fix (0059l7r3a/b; read 22:30 2026-11-01, manager)

The champion `@hpb0.01` with the fallback two-turn player on the 500
gauntlet sequences, halves merged into
`results/gauntlet/champion-hpb0.01-two.json`; paired against the one-turn
champion (`...-hpb0.01-bd6d62.json`) with `gauntlet.py read`.

| | two-turn | one-turn | diff |
|---|---|---|---|
| clears, all | 0.640 | 0.616 | **+0.024** (se 0.016) |
| train / held-out | 0.552 / 0.728 | 0.528 / 0.704 | +0.024 / +0.024 |
| vs heuristic (0.596) | | | +0.044 (se 0.016) |
| HP at boss (387 reach both) | 65.2 | 66.0 | -0.8 |

Per floor kind (win rate given reached; HP lost in won fights, after the
Burning Blood heal): easy 1.000 / 1.000, 0.38 / 0.18 HP; hard 0.988 / 0.988,
2.78 / 2.31 HP; elite 0.948 / 0.934, 14.3 / 15.4 HP; boss 0.764 / 0.757.
Deaths at the first elite (floor 6) fall 12 -> 2, at Gremlin Nob 23 -> 15;
boss deaths are unchanged (99 / 99).

What it says:
- **Under the +0.03 bar** (decisions "Review 2026-11-01b"), and the shape is
  the one the run-HP read (0036) predicted: depth wins elites (Nob too,
  where the one-turn bonus fed Enrage) but leaks ~0.2-0.5 HP per hallway
  to the floored finish score, so it reaches the boss 0.8 HP lower and
  bosses gain nothing. Depth's one-fight boss gains (+0.09 on tight sets)
  don't show here.
- This is the "before" run. The `@hpe` fix's two-turn run-HP read
  (0059l7r3a2) is running; on a pass the `@hpe` two-turn gauntlet runs and
  is read against this file and the one-turn champion.

## Two-turn run-HP with the end-HP bonus passes (0059l7r3a2 = run-HP 0038; read 00:15 2026-11-02, manager c3513fb5)

`ladder.py runhp <champion>@hpe0.01 --two-turn --pairs 1000` against the
heuristic, and paired against the two-turn `@hpb0.01` run (0036, first
1000 fights) with `start_hp_read.py`:

| slice | HP saved, `@hpe` - `@hpb` (two turns) | deaths, arm - control |
|---|---|---|
| all (1000) | **+1.24** (se 0.11) | -2 |
| hallway (728) | **+1.41** (0.09) | 0 |
| elite (206) | +0.87 (0.41) | -2 |
| boss (66) | +0.56 (0.25) | 0 |

Spec rule (`end-hp-bonus.md`): hallways save >= +0.5 HP with no more
deaths: **passes**. Against the heuristic the two-turn `@hpe` champion
loses 4.63 HP per fight vs 5.70 (+1.07, CI [+0.57, +1.56]) at the same
win rate (0.984); the one-turn `@hpb` champion was 5.4 vs 5.75. So the
floored finish score was the whole hallway leak: with it fixed, depth now
saves HP instead of costing it (hallways +0.74 over the heuristic). The
`@hpe` two-turn gauntlet halves (a7/a8) were already running and continue.

## Silent zero-shot number and depth on Silent (0059l7r3a3-a6; read 00:20 2026-11-02, manager c3513fb5)

`depth_paired.py --bench tight_silent --policy fallback --max-nodes 400000
--per-cell 3`, hallway + elite + boss, champion `@hpb0.01` and heuristic on
each half, one turn and two turns, fights paired by index (same specs,
checked). Half A decks: starter + 5 tier-A cards (Neutralize, Backflip,
Blade Dance, ...); half B: at least 2 of the 5 are Poison cards (Deadly
Poison, Poisoned Stab, Bouncing Flask). se clustered by deck cell (3
fights per cell); clustering barely changes them.

| half, group | champ - heur, one turn | champ - heur, two turns | champ depth gain | heur depth gain |
|---|---|---|---|---|
| A all (216 / 72 cells) | **+0.139** (0.038) | -0.009 (0.026) | +0.019 (0.025) | **+0.167** (0.034) |
| A elite (90) | +0.278 (0.068) | -0.044 (0.052) | -0.011 (0.044) | **+0.311** (0.060) |
| B all (312 / 104 cells) | **-0.083** (0.025) | +0.074 (0.022) | **+0.151** (0.027) | -0.006 (0.016) |
| B elite (90) | -0.189 (0.065) | +0.167 (0.057) | **+0.322** (0.056) | -0.033 (0.043) |
| pooled (528 / 176 cells) | +0.008 (0.023) | +0.040 (0.017) | +0.097 (0.019) | +0.064 (0.018) |

Elite win rates: A one turn champ 0.656 / heur 0.378, two turns 0.644 /
0.689; B one turn 0.367 / 0.556, two turns 0.689 / 0.522.

Sanity: the halves mirror each other (on each half only one player gains
from depth), and the jobs straddled the 22:52 `sts` swap, so 12 elite
fights per half were replayed with both the old and the new module: all
24 one-turn and two-turn results match the files exactly. The data is
sound; the mirror is the deck tiers.

What it says:
- **Zero-shot new character: the champion is level with the heuristic at
  one turn (+0.008 pooled), ahead at two turns (+0.040, se 0.017).** The
  pooled number hides two opposite halves; the warm-start parent read
  +0.024 / +0.060, so the current champion is better on tier A and worse
  on Poison decks than that older net.
- **Poison's value lies mostly past the one-turn leaf, and depth repairs
  it.** The one-turn leaf stops at the owner's next draw, after the
  monsters' turn, so it already sees the first Poison tick; the rest of
  the stack (n-1, n-2, ...) pays later and the net must price it from its
  columns. On Poison decks the champion's one-turn play loses -0.19 on
  elites to the heuristic (which prices Poison by hand) and two-turn
  search lifts it by +0.32, to 0.689; the heuristic gains nothing there.
  This matches the generated turn-start powers ("Novelty cost sits past
  the one-turn horizon"), now on a real unseen mechanic. It was named as
  the expected horizon case before the run (manager.md, 22:10), with no
  numeric bar, so it is not a pre-registered pass; it raises the prior
  for the 0061 replication.
- On tier A the heuristic is the weak one-turn player on elites (0.378)
  and depth repairs it (+0.31). (An earlier line here said both players
  end at 0.689 on elites; that is a coincidence across halves: heuristic
  0.689 on A, champion 0.689 on B. Pooled at two turns the champion leads,
  about 0.667 vs 0.606 on elites, +0.040 overall; corrected after the
  2026-11-02 review.)
- For goal 1: a "turn-start peek" (one owner turn-start step at the
  leaf) would cover the generated turn-start powers but not Poison, whose
  value runs over several turns; depth covers both. So the general fix for
  mis-priced unseen mechanics is depth itself (cheaper depth), with the
  peek only as a narrow, cheaper case; 0061 decides whether the peek spec
  is worth writing.

## Two-turn champion with the end-HP bonus on the gauntlet: passes (0059l7r3a7/a8; read 01:45 2026-11-02, manager c3513fb5)

`gauntlet.py play <champion>@hpe0.01 --two-turn`, sequences 0-249 (a7)
and 250-499 (a8), merged into `results/gauntlet/champion-hpe0.01-two.json`
(settings identical, seed 20261101), `gauntlet.py read` paired by sequence:

| vs | clears (A / B) | A - B (se) | train | held-out | HP at boss |
|---|---|---|---|---|---|
| one-turn champion `@hpb0.01` | 0.676 / 0.616 | **+0.060** (0.016) | +0.068 (0.023) | +0.052 (0.021) | 68.5 / 65.3 |
| two-turn champion `@hpb0.01` | 0.676 / 0.640 | +0.036 (0.012) | +0.044 (0.018) | +0.028 (0.014) | 67.7 / 63.8 |
| one-turn heuristic | 0.676 / 0.596 | +0.080 (0.015) | +0.084 (0.022) | +0.076 (0.019) | 67.9 / 64.8 |

Deaths by floor (two-turn `@hpe` / one-turn champion): first elite
(floor 6) 2 / 12, floor 7-8 2 / 9, second elite (floor 9) 33 / 53, floor
10 18 / 19, boss 107 / 99. More sequences reach the boss (445 vs 407;
corrected 02:40 from "393 vs 368", which was 500 minus boss deaths, by the
2026-11-02 review's skeptics), and the boss is won at the same rate per
arrival (0.760 vs 0.757): depth's gain is HP kept and elites survived,
cashed in at the boss. Second elite per arrival 0.933 vs 0.889. By
encounter the big drops are Gremlin Nob (10 / 23), Three Sentries
(11 / 22) and Lagavulin (14 / 20).

Rule (manager.md, pre-registered 22:35 2026-11-01): clears >= +0.03 over
the one-turn champion: **passes** at twice the bar, both halves
positive. The end-HP fix is worth +0.036 on top of two-turn `@hpb` (the
"before" read +0.024 was under the bar), matching run-HP 0038: the HP
two-turn search no longer gives away in hallways arrives at the elites.
Sanity: the step from `@hpb` to `@hpe` at two turns is the size the HP
numbers predict (about +3-4 HP at the boss), not a jump from nowhere; the
two halves agree.

What it changes: goal 2's headline player is now two-turn search with the
champion net and `@hpe0.01` (decisions "Two-turn @hpe is the product
player"). It costs ~130 min per 250 sequences at 3 threads, ~50x one-turn,
so cheaper depth is now worth more than any one-turn training change. The
heuristic two-turn anchor (0059l7r3b1) says how much of depth's gain the
heuristic gets too, i.e. the net's real headroom.

## Gauntlet protocol replay: sequential end-HP with a clears guard (02:20 2026-11-02, manager c3513fb5)

`scripts/analysis/gauntlet_protocol.py` (review 2026-11-02 rank 2): for
every pair of gauntlet files on the same sequence book, a normal SPRT on
paired end-HP (boss HP left if cleared, else 0), H0 0, H1 +1.5 HP, alpha
= beta = 0.05, first look at 50 sequences, in sequence order; a pass is
turned into a fail if the paired clears difference so far has z <= -2.
Compared with the fixed-n verdict on clears (better at z >= 2).

- 67 of 81 ordered pairs agree; leaving out the half-vs-merged self pairs,
  every disagreement is one of two kinds: clears level but end-HP z >= 2
  (SPRT passes: end-HP is the more sensitive statistic), or clears better
  by a small amount whose end-HP gain is under the 1.5 HP H1 (SPRT fails,
  e.g. `@hpb0.01` over `@esp`: +0.020 clears, +1.08 HP). No pass went to
  a player that was worse on clears; the guard never had to fire.
- Stopping points for the decisions that mattered: two-turn `@hpe` vs
  one-turn `@hpb` pass at 108 sequences (fixed-n used 500), vs two-turn
  `@hpb` at 119, vs the heuristic at 109; `@hpb0.01` vs the bare net at
  54. Level pairs run to the end (open at 500) or fail at 50-440.
- c = 0.04 vs c = 0.01 (end-HP -2.44) fails, as it must.

Read: the protocol keeps every verdict's direction and costs ~1/4 to 1/5
of the sequences for real effects, so it is adopted for goal-2 reads
(decisions "Gauntlet protocol"). H1 = +1.5 HP corresponds to roughly
+0.02-0.03 clears in these pairs.

## Training since 10-29 did not reach the gauntlet: the 10-29 net is ahead (0059l7r3b2, b25, b26; read 02:10 2026-11-02, manager c3513fb5)

Review 2026-11-02 rank 1: the one-turn gauntlet (sequences 0-499, same
book) of the 10-29 net (`runs/2026-10-29-seed-check-r2-s1-1a789b2`, the
ladder's champion before burst8 and burst8hp2) with the HP bonus, against
the current champion (burst8hp2 s1) with the same bonus:

| c (HP bonus) | 10-29 net clears | champion clears |
|---|---|---|
| 0.005 | **0.640** | 0.580 |
| 0.01 | 0.634 | **0.616** |
| 0.02 | 0.602 | 0.608 |
| 0.04 | - | 0.482 |

At c = 0.01, paired: 10-29 minus champion +0.018 clears (se 0.016),
end-HP +1.82 (z 3.2; the protocol passes at 120 sequences); HP at the
boss 67.5 vs 65.1. The 10-29 net dies less on elites (first elite 4 vs
12, second 40 vs 53) and more at the boss (125 vs 99). Best c against
best c: 0.640 vs 0.616. One turn deep the 10-29 net is level with the
champion searched two turns deep with `@hpb` (0.634 vs 0.640, -0.006).
Against the one-turn heuristic: +0.038 clears (z 2.1).

What it says:
- **The training gains since 10-29 (burst8 +0.011 and burst8hp2 +0.006
  on tight2, burst8hp2's -2.2 HP per fight on bare run-HP) don't survive
  at run level once search prices HP; they reverse.** The bare-net HP
  saving duplicates what the bonus already does (as the start-HP arms
  found), and the burst fine-tunes cost something the gauntlet sees and
  tight2 does not. My first guess, that the HP-weighted net plus the
  bonus double-counts HP, is not supported: the champion's best c is not
  lower than the 10-29 net's.
- Caveat: one sequence book (0-499; c was tuned on it), one seed of each
  net, so part of the gap could be the champion's own seed luck. The
  burst8hp2 promotion was decided on tight2 and run-HP, both of which
  this shows to be the wrong yardstick for goal 2.
- Product candidate: the 10-29 net two turns deep with `@hpe0.01`, first
  250 sequences queued (0059l7r3b35), read with the gauntlet protocol
  against `champion-hpe0.01-two-a.json`; if it passes, confirm on
  sequences 500-999 before changing the product player.

## Horizon replication passes (0059l7r3a9; read 03:05 2026-11-02, manager c3513fb5)

`gen_timing_slice.py` on the fresh-fight bench (`gen_powers8c3f12`, the
10-29 net, elite + boss), the rule pre-registered in "Novelty cost sits
past the one-turn horizon":

| class | net depth gain, generated - original (cells) | (cards) |
|---|---|---|
| turn start | +0.118 (se 0.057), 17 cells | +0.088 (0.079), 6 cards |
| card played | -0.156 (0.054), 24 | -0.155 (0.063), 8 |
| turn end | -0.042 (0.042), 21 | -0.070 (0.052), 8 |
| lost HP | -0.057 (0.042), 24 | -0.017 (0.037), 11 |
| **turn start - card played** | **+0.274 (0.079)** | **+0.243 (0.101)** |

Rule: >= +0.10 over cells and > 0 over cards: **passes**. It replicates
over fights, not over cards (mostly the same test cards). With the Silent
read (Poison decks: depth +0.32 on elites) the pattern is: unseen
mechanics whose value lands after the one-turn leaf are mis-priced one
turn deep and repaired by depth. New in both reads: depth gains *less* on
generated card-played powers than on the originals (-0.09, now -0.16),
i.e. two-turn search does worse with a generated card-played power than
with its original. Not explained yet; a decision diff on those cells is
the next goal-1 probe.

What it changes: the product already searches two turns, so the
"turn-start peek" (a one-turn variant) would only make goal-1 screening
cheaper; it stays an idea, not a spec, until a one-turn read needs it.

## Rollout ceiling probe (0059l7r3b27-b29b; read 03:05 2026-11-02, manager c3513fb5)

`scripts/analysis/rollout_probe.py` (dfacaa5): at each decision of a
replayed gauntlet fight, each legal action is played to the fight's end
n times from fresh-RNG copies by the one-turn champion `@hpb0.01`; the
best mean of won x (1 + 0.01 x end HP) is played. Fights replay the
recorded ones exactly (8 checked). Never-cleared = the 117 sequences no
gauntlet file clears (129 before the 10-29 net files joined), each
replayed at the product's fatal fight and entry HP; cleared = 30 boss
fights the product (two-turn `@hpe`) won.

| n | never-cleared won | cleared (sanity) won | s per fight |
|---|---|---|---|
| 16 | 3 / 117 | 23 / 30 | 2 / 15 |
| 64 | 7 / 117 (6%) | 27 / 30 | 7 / 52 |

- The sanity set says the rollout player is still a bit weaker than the
  product on bosses: all 3 losses at n 64 are Hexaghost at 80 HP (6 of 7
  at n 16), so the one-turn champion is a poor play-out policy there.
- The fatal fights: 69 of 117 at the boss, 30 at the floor-9 elite
  (Lagavulin, Nob, Sentries), entered at median 36 HP (boss: median 46,
  vs 80 for boss fights the product wins).
- Read against the review's bar (> 30% = real headroom, < 10% = near the
  ceiling): under 10% and only slowly rising with n (3 -> 7). The fatal
  fight is rarely savable; the losses are decided earlier, by HP spent
  on the way and by the deck. Caveats: the probe player is not stronger
  than the product on bosses, and it only replays the fatal fight, not
  the whole sequence. So "no headroom in the fatal fight", not "no
  headroom in combat". Goal-2 effort moves toward HP kept on the way
  (elites) and deck decisions (card rewards), per the review's branch.

## Heuristic two-turn anchor, first half; early stop checked (0059l7r3b3, b355, b361; read 04:20 2026-11-02, manager 61d75983)

**Anchor (sequences 0-249, interim; b4 plays 250-499).** The heuristic
two turns deep clears 0.612, against 0.572 one turn deep (+0.040, se
0.022) and 0.648 for the product player (burst8hp2 champion `@hpe0.01`,
two turns; -0.036, se 0.021). Paired end-HP: heuristic two-turn minus
product -2.84 HP (z -3.3; the protocol says fail at n 85), minus
heuristic one-turn +1.58 (z 1.8, open). Deaths by floor, heuristic
two-turn vs product: elite 2 (floor 9) 22 vs 19, boss 60 vs 59; the gap
is spread thin, with HP at the boss 63.2 vs 67.2 where both reach it. So
at equal depth the net adds about as much as depth adds to the heuristic
(+0.04 clears each), and its edge is mostly HP carried to the boss. That
is the "near 0.60" case of the queue's rule: the net is worth improving,
and HP on the way stays the lever. Check after b4: does the half
0.612 / 0.648 hold on 250-499?

Timing: b3 took 70 min against its 220 min estimate (the heuristic rate
cache, a1c4788, plus the fast tables). Heuristic two-turn estimates can
be cut to about a third.

**Early stop, real check (b355).** The 10-29 net `@hpb0.01` one turn
deep, `--against heuristic-bcbb0e.json`: it stopped after 3 blocks with
pass at n 149, the replay's verdict on the full 500, and its 150 rows are
byte-equal to `net1029-hpb0.01.json`'s first 150. 1.5 min instead of
~5.

**Starter deck, no rewards (b361):** 0 of 500 clear; deaths at the first
and second elite (Lagavulin 157, Sentries 119, Nob 51), 2 reach the boss.
That is the floor the card-reward choosers start from (b362-b365 next).

## 10-29 net two turns deep beats the product player (0059l7r3b35; read 05:45 2026-11-02, manager 61d75983)

Sequences 0-249, both `@hpe0.01` two turns deep: the 10-29 net clears
0.672 vs the burst8hp2 champion's 0.648 (+0.024, se 0.021); paired end-HP
+2.37 HP (z 3.1), **protocol pass at n 125** (clears guard fine). Against
the heuristic two turns deep: +0.060 clears, end-HP +5.2 (pass at n 94).
Deaths: fewer at elite 2 (16 vs 19) and floor 10 (4 vs 8); bosses level
(60 vs 59); HP at the boss 69.4 vs 66.1. Same story as one turn deep
(0.640 vs 0.616): the burst / HP-weighted training since 10-29 cost run
level. Screened on 0-249 (the book `@hpe` was tuned on), so it is
confirmed at fixed n on 500-749 before the product changes: b38a
(champion) and b38b (10-29 net), queued 05:45, ~2.5 h each.

## Bias audit, slice 1: the leaf under-prices enemy Strength ~4x and Poison 2-6x (0059l7r3b37; read 05:45 2026-11-02, manager 61d75983)

Spec `docs/specs/bias-audit.md` (`scripts/analysis/bias_audit.py`): 300
decision states from gauntlet elite and boss fights; each perturbed on one
living enemy by patching the encoded state (re-encode checked), then the
champion net's static value (leaf) vs 32 common-seed play-outs by the
one-turn champion `@hpb0.01`, both on the label scale (w 2). Unperturbed
levels agree (leaf 1.378, play-outs 1.404). Change from the perturbation,
leaf / play-out (ratio, se):

| perturbation | leaf | play-out | ratio |
|---|---|---|---|
| enemy Strength +2 | -0.021 | -0.082 | 0.25 (0.03) |
| enemy Strength +4 | -0.046 | -0.167 | 0.27 (0.03) |
| Poison +3 | +0.017 | +0.027 | 0.65 (0.10) |
| Poison +6 | +0.012 | +0.074 | 0.17 (0.02) |

Strength: the ratio is 0.15-0.43 on every elite and boss with signal
(Slime Boss barely reacts either way), so the leaf sees about a quarter of
what enemy Strength costs: ~0.011 per point against ~0.042 in play-outs.
Poison: the leaf is not monotone (+6 moves it *less* than +3) while
play-outs scale with the stack, so the net reads Poison as a small fixed
bonus, not damage over turns. Both name a bias at many se (spec bar:
ratio < 0.5 at 2 se).

What it changes:
- It explains two earlier results: depth helps Silent's Poison decks most
  (+0.32 on elites, results "Silent number"): two turns see a turn of
  Poison ticks the leaf ignores; and `@esp0.04` (a hand price of 0.04 per
  Strength point, scaled by win chance) was about the right size (gap
  ~0.03 per point) yet lost -0.020 clears at run level, so a correct-sized
  price on top of this leaf doesn't buy clears by itself (it fed block
  over damage on bosses).
- Both are **effects over future turns** (Strength hits each turn, Poison
  ticks each turn): the same family as the novelty cost on turn-start
  powers (horizon replication). The leaf's horizon, not missing features,
  is the common cause. A fix candidate prices the next N monster turns
  (Strength x expected hits, Poison as its remaining damage), or trains
  the leaf on two-turn values; either is a goal-1 fix too (generated
  powers that act each turn).
- Next slices (spec): own Vulnerable / Weak turns, block, next turn's
  energy, power stacks; and the same audit on the 10-29 net (b35 says it
  plays better at run level: does it price these better?).

## Card rewards: deck choice is a goal-2 lever as big as depth (0059l7r3b361-b365; read 06:30 2026-11-02, manager 75ea2a19)

Spec `docs/specs/card-rewards.md` (folded into decisions "Card rewards are
a goal-2 lever"). The 10-29 net `@hpb0.01`, one turn deep, 500 sequences;
after each won non-boss fight 3 seeded offers from the half's pool;
choosers skip / random / sim (each option scored by 8 one-turn fights of
the next floor's pool, common seeds). First offers are identical across
files (500 / 500), so pairs are clean. cell-sim is 450 / 500 (still
running at the read; the table row is its final 500).

| start | chooser | clears | vs | clears diff (se) | end-HP diff (se) |
|---|---|---|---|---|---|
| starter | skip | 0.000 | | | |
| starter | random | 0.364 | skip | +0.364 (0.022) | +10.1 (0.7) |
| starter | sim | 0.548 | random | **+0.184 (0.027)** | +6.5 (0.9) |
| cell | skip | 0.634 | | | |
| cell | random | 0.822 | skip | +0.188 (0.023) | +7.7 (1.0) |
| cell | sim | 0.870 | random | +0.048 (0.019) | |

**Rule passes by ~7 se** (sim - random +0.184 vs the +0.05 bar, both
halves: train +0.232, held-out +0.136). Card rewards become a goal-2
workstream.

Why it works: from the starter deck the sim chooser cuts deaths at the
first elites by half (floors 6-10: 57 vs 134) and reaches the boss with
62.9 HP vs 55.3; boss deaths fall less (168 vs 184). It skips 24% of
offers (8-42% by floor) and favours cheap damage and block (Clash, Anger,
Shrug It Off, Carnage, Cleave); random always takes a card. Held-out
offers are held-out cards the net never trained on, and the gain there
is still +0.136.

What it changes:
- **Deck choice moves clears more than anything play has gained** (depth
  +0.060, the HP bonus +0.02-0.17): even a crude, one-floor-myopic
  chooser adds +0.18 from the starter and +0.05 on top of random from a
  built deck. The ceiling probe's "losses are decided before the fatal
  fight" now has a named cause we can act on.
- **The cell gauntlet overstates a run.** Its pre-built cell decks clear
  0.634 with no rewards; a starter deck plus a sim chooser reaches 0.548.
  A real Act 1 starts from the starter deck, so the headline setting
  should move to `--start starter --rewards sim` once the chooser is
  less myopic (decisions "Card rewards are a goal-2 lever").
- The chooser looks only at the next floor: a card that pays in long
  fights (Inflame, Demon Form, Metallicize) is judged on a hallway. Boss
  deaths barely moved (168 vs 184), where such cards matter most. Next:
  score options against the next floor *and* the boss pool.
- It adds weight to the owner's open simulator decision: rewards,
  removal, upgrades and shops are where a run layer earns clears.

## Sim chooser with a boss horizon passes: +0.155 clears (0059l7r3b37c; read 06:40 2026-11-02, manager 75ea2a19)

Spec `docs/specs/sim-boss.md`. The 10-29 net `@hpb0.01`, one turn, from
the starter deck; each option also scored by 8 one-turn fights against
the boss pool at post-rest HP. `--against` today's sim: **protocol pass
at n 162** (stopped at 200). Clears 0.695 vs 0.540 (+0.155, se 0.042),
both halves (+0.150 train, +0.16 held-out). Boss deaths 44 vs 69 of 200;
elite deaths 13 vs 20. HP at the boss is *lower* (60.3 vs 63.0), so the
gain is the deck, not HP: it skips less (14% vs 24% of offers) and takes
scaling cards plain sim rarely did (Spot Weakness 86 vs ~0, Inflame 79 vs
37, Combust 69, Rupture 45 in the first 150 sequences).

Fair? The boss pool has 3 bosses, so 8 draws nearly always include the
sequence's real boss. The real game shows the Act boss on the map, so a
chooser that plans for it is legitimate; it does not see the boss's seed.

Starter deck to here: skip 0.000, random 0.364, sim 0.548, sim-boss 0.695
(near the cell decks with sim, 0.870, and above the cell decks with no
rewards, 0.634). Rule passes: goal 2's headline moves to `--start starter
--rewards sim --sim-boss` (decisions "Sim-boss passes: new headline
setting").

## Bias audit on the 10-29 net: it prices Strength and Poison worse, yet plays better (0059l7r3b37b; read 06:40 2026-11-02, manager 75ea2a19)

Same 300 states and play-outs as slice 1, with the 10-29 net as leaf and
policy. Ratios (leaf / play-out delta): Strength +2 0.17 (0.02), +4 0.18
(0.02) against the champion's 0.25 / 0.27; Poison +3 0.04 (0.03), +6 0.08
(0.01) against 0.65 / 0.17. Bosses are worst (Strength ~0.11, Poison ~0).
So the net that beats the champion at run level prices these
future-turn effects *less* well. The bias is real for both nets but does
not explain the run-level gap between them; it is a goal-1 / horizon
issue (depth repairs it), not why burst8hp2 lost to the 10-29 net.

## Run value: what an HP is worth by floor (Next Q4; offline, 2026-11-02)

`scripts/analysis/run_value.py` fits, per gauntlet floor k, P(clear | HP at
the start of floor k) over the sequences alive there (logistic, numpy),
plain and with a deck-strength covariate (logit of the cell's clear rate
over the *other* sequences of that cell). "Price" = adjusted dP/dHP at the
floor's median HP divided by P(clear | alive at k): one more HP at the end
of the fight before floor k, in units of winning that fight, the same
units as the search's flat price c = 0.01. Bootstrap se over sequence
indices (200 draws, shared across floors so ratios pair). Floors 1-3 start
at ~80 HP almost always (Burning Blood refills), so they have no spread to
fit and floor 4 is the reference.

Pools: one-turn cell start `@hpb` (burst8hp2 c 0.005 / 0.01 / 0.02 / 0.04,
10-29 net c 0.005 / 0.01 / 0.02; 7 files, 500 sequences each); two-turn
cell `@hpe` (champion two + two-c, 10-29 net two-a + two-c; 4 files);
one-turn starter + rewards (10-29 net, random / sim / sim-boss; 3 files).

| floor | kind | price one-turn cell | price two-turn cell | price starter+rewards |
|---|---|---|---|---|
| 4 | hard | 0.016 (0.004) | 0.014 (0.004) | 0.033 (0.004) |
| 5 | elite | 0.014 (0.003) | 0.020 (0.003) | 0.034 (0.004) |
| 6 | hard | 0.013 (0.003) | 0.019 (0.003) | 0.037 (0.003) |
| 7 | hard | 0.011 (0.002) | 0.016 (0.002) | 0.034 (0.003) |
| 8 | elite | 0.010 (0.002) | 0.014 (0.002) | 0.034 (0.003) |
| 9 | hard | 0.008 (0.001) | 0.011 (0.002) | 0.027 (0.002) |
| 10 | boss (after rest) | 0.005 (0.001) | 0.009 (0.001) | 0.025 (0.002) |
| ratio boss / floor 4 | | 0.33 (0.09) | 0.60 (0.22) | 0.76 (0.12) |

(n per floor ~3,000-3,500 / ~1,000 / ~1,000-1,200; median HP falls from
~78 at floor 4 to ~44-49 at floor 9, then ~58-73 after the rest. Full
table with plain and adjusted slopes: run the script.)

Read:
- **Shape.** On the headline setting (starter + rewards) the price is flat
  across floors (0.76-1.13 of floor 4's). On cell starts one turn deep it
  falls ~3x from floor 4 to the boss (0.33, se 0.09: just beyond 2x at 2
  se); two turns deep the fall is 0.60 (se 0.22), not beyond 2x. HP late
  in the act is worth less there because the survivors mostly clear
  anyway (P(clear | alive) rises 0.60 -> 0.72).
- **Level.** The fitted price is 1.4-3.5x the search's c = 0.01, and ~3x
  on the starter setting. Don't read that as "raise c": the c sweep
  (results "Act-1 gauntlet: first check and HP-price sweep") found c 0.02
  / 0.04 no better on cell starts, and the slope is confounded upward.
- **Confounding.** HP at a floor tracks how strong the deck and the play
  are. Adding the cell-strength covariate halves the cell pools' slope
  (e.g. floor 6: 0.0169 -> 0.0082), so most of the plain slope was deck
  strength; what's left still carries within-cell deck luck (rewards
  diverge decks on the starter setting, where the covariate does nothing
  because every sequence starts with the same deck) and fight luck. The
  numbers are upper bounds on the causal worth of an HP, the starter ones
  most of all.
- **The boss fight's own end HP is worth 0 on the gauntlet** (the run
  ends there), while the search prices it at c like any fight; in a real
  run it carries into Act 2, so this is a gauntlet artefact, not a fix.

Decision rule (manager Q4: try a floor-dependent leaf price if the price
differs > 2x by floor): **not met on the headline setting** (flat) and
only borderline on one-turn cell starts, so a flat leaf HP price stays.
Not built, a cheap screen if wanted: a c sweep (0.02 / 0.03) on the
starter + rewards setting, where the fitted level is highest; the
confounding above makes a gain uncertain.

## Run-level seed noise (twins b37d-f, 2026-11-02)

Review 2026-11-02b rank 2: the verdict "training since 10-29 didn't reach
run level" rested on one net per recipe. Seed twins played the one-turn
cell gauntlet `@hpb0.01`, sequences 0-499 (same sequences, paired):

| net | clears | end-HP |
|---|---|---|
| 10-29 recipe s1 | 0.634 | 24.54 |
| 10-29 recipe s101 | 0.634 | 23.97 |
| 10-29 recipe s201 | 0.620 | 24.18 |
| burst8hp2 s1 (champion) | 0.616 | 22.72 |
| burst8hp2 s101 | 0.614 | 23.58 |

Twin minus twin, paired over 500 sequences: clears 0.000 / -0.014 /
-0.014 / -0.002 (se ~0.014 each), end-HP -0.57 / -0.36 / +0.22 / +0.87
(se ~0.43). The twins differ by no more than the fight luck of one paired
read, so the training-seed sd at run level is small: ~0.4 HP end-HP and
~0.01 clears (from 3 + 2 nets, rough).

Recipe means: 10-29 clears 0.629, end-HP 24.23; burst8hp2 clears 0.615,
end-HP 23.15. Gap +1.08 HP end-HP (se ~0.38 from the seed spread, ~2.8 se)
and +0.014 clears (~2 se). So the verdict stands, at about half the
single-seed size (+1.82): the burst/HP-weight recipe since 10-29 costs
about 1 HP of end-HP at run level, which tight2 and the ladder couldn't
see.

MDE for a run-level training read (500 sequences, 3 seeds per arm, one
turn): ~2.8 x 0.42 x sqrt(2/3) = ~1.0 HP end-HP, ~0.02 clears. A recipe
change expected to move end-HP by less than ~1 HP doesn't run at 3 seeds.

## 10-29 net two turns deep: confirmed on 500-749, product net changes (b38a/b; read 10:20 2026-11-02, manager 14d5db36)

Pre-registered confirmation of the b35 pass (0-249) at fixed n on fresh
sequences 500-749, cell gauntlet, both two turns deep `@hpe0.01`:

| | 10-29 net | burst8hp2 champion | diff (se) |
|---|---|---|---|
| clears | 0.724 | 0.672 | +0.052 (0.021) |
| end-HP | 30.73 | 27.72 | +3.01 (0.74), z 4.1 |
| HP at boss (222 reach both) | 70.5 | 67.3 | |

Train half +0.056, held-out +0.048: both halves. Deaths: the gain is
before the boss (floors 6-10: 13 vs 26; Lagavulin 4 vs 7, Sentries 2 vs
6, Nob 2 vs 4); boss deaths are level (56 / 56). So the 10-29 net is the
better HP keeper on elites at two turns too, and the rule (not worse on
clears or end-HP) passes by a wide margin. Two-turn gain over the 10-29
net's own one-turn play is not on these sequences (no one-turn file on
500-749); on 0-249 it was +0.032 clears.

## Rest-site chooser fails: 16 boss fights per option over-pick upgrades (b37g; read 10:20 2026-11-02)

`--rest sim` against the headline file (10-29 net one turn `@hpb0.01`,
starter + rewards sim + sim-boss), early-stopped by the protocol at n 50:
fail, end-HP -1.22 (se 0.54), clears 0.680 vs 0.720.

Only the 10 of 50 sequences that upgraded differ (the 39 heals match the
control row for row, as they must; 1 had nothing to upgrade). Those 10:
2 clears lost (Bash+ at 74 HP, Spot Weakness+), none gained; one picked
Uppercut+ at 19 HP over a heal to 43 (both lost). The likely cause is
selection noise: heal competes with ~6-9 upgrade options on 16 shared-seed
fights each, so the best-scoring upgrade wins by luck often (winner's
curse); the boss outcome at 16 fights has se ~0.12 in win rate. The
expected gain was small anyway: in this gauntlet the one rest site sits
right before the boss, where HP is worth most, and only sequences near
full HP have a cheap upgrade. Not pursued (decisions "Rest-site chooser
closed"); a margin rule or 64+ fights per option is the fix if rest sites
come back with a real map.

## Re-rank of newer nets on the gauntlet (Q1; b37i; read 10:20 2026-11-02)

One turn `@hpb0.01`, cell gauntlet, sequences 0-499, each paired against
the 10-29 net (`net1029-hpb0.01.json`: clears 0.634, end-HP 24.54).
Seed sd at run level ~0.4 HP end-HP (twins), so a single net's diff
needs ~1 HP to mean anything.

| net | end-HP diff (se) | clears diff (se) | tight2 mean (train, held-out) |
|---|---|---|---|
| burst8 s1 | +0.82 (0.55) | +0.012 (0.016) | n/a |
| lean s1 r2 | -0.51 (0.42) | +0.002 (0.015) | 0.510, 0.512 |
| data40k s1 r1 | -0.80 (0.49) | -0.016 (0.015) | 0.513, 0.481 |
| data80k s1 r1 | -1.86 (0.52) | -0.022 (0.017) | 0.521, 0.505 |
| lean-thr s1 r2 | -1.98 (0.47) | -0.042 (0.015) | 0.501, 0.492 |
| cover21 s1 r1 | -2.70 (0.48) | -0.020 (0.015) | 0.475, 0.471 |

No newer net beats the 10-29 net at run level; burst8 (no HP weight) is
level, and the HP-weighted burst8hp2 champion was -1.1 over seeds (twins
section). Rank correlation with tight2 over the five nets that have a
round.json: Spearman ~0.6, carried by cover21 being last on both;
data80k is best on tight2 and fourth here. So tight2 picks the wrong net
for run-level play, and more round-0 data (40k, 80k) costs end-HP at run
level although it helped tight2. Product candidates are screened on the
gauntlet from now on (the gauntlet protocol already says so for goal-2
reads).

## One-turn gauntlet: 8 threads barely beat 3 (Q7; b2z1/b2z2, 2026-11-02)

The same 100 headline sequences (10-29 net one turn `@hpb0.01`, starter +
rewards sim + sim-boss), rows identical to the 500-sequence file: 8
threads took 6 min, 3 threads 7 min (runner log, minute resolution; a
3-thread two-turn job ran beside both). So a one-turn gauntlet job doesn't
scale past ~3 threads (per-floor batches are small: one fight per live
sequence, plus the chooser's 8-fight batches). One-turn jobs stay at 3
threads; throughput comes from running two jobs at once, not wider jobs.

## Mixed depth: floors 1-3 one turn deep is level and 43% cheaper (R4; b45; read 12:20 2026-11-02, manager 158afb00)

The burst8hp2 champion `@hpe0.01` two turns deep on the cell gauntlet,
sequences 0-249, with `--one-turn-floors 3` (floors 1-3 one turn deep)
against the same player at full depth (`champion-hpe0.01-two-a.json`):
clears 0.648 vs 0.648 (paired diff 0.000), end-HP 25.02 vs 25.04 (diff
-0.02, se 0.05), HP at the boss 65.6 / 65.6, deaths by floor within one
sequence everywhere. 70 of 250 sequences differ in some row (first
difference always on floors 1-3, as it must be), but the differences wash
out before the boss. Wall time 81 min (09:25-10:46) against 142 min for
the full-depth half a7 (22:59-01:22, same fast-tables code), both beside
one other job; peak memory 4.74 vs 4.19 GB (no saving: memory is per
two-turn thread, and floors 4+ still search). So the easy hallways need
no depth, and mixed depth gives the same run for 57% of the time.
Decisions "Mixed depth for screens": two-turn screening jobs on the cell
gauntlet use `--one-turn-floors 3` from now; the headline setting (starter
deck + rewards) has not been checked and keeps full depth until it is.

## Card removal: a removal is worth ~1.8 HP, the sim chooser gives it back (Q3; b2z3; read 12:20 2026-11-02, manager 158afb00)

Headline setting (10-29 net one turn `@hpb0.01`, starter deck, rewards
sim + sim-boss), one removal after the first elite's reward
(`docs/specs/card-removal.md`), early-stop protocol d1 1.5.

| arm (vs control) | n | end-HP diff (se) | clears | protocol |
|---|---|---|---|---|
| `strike` vs none | 500 | +1.78 (0.83), z 2.2 | 0.718 vs 0.680, +0.038 (0.020) | open at 500 |
| `sim` vs `strike` | 250 | -1.41 (1.00) | 0.660 vs 0.708, -0.048 (0.028) | fail at 222 |
| `sim` vs none | 250 | -0.11 (0.96) | -0.028 (0.025) | - |

Removing a Strike helps on both halves alike (end-HP +1.78 train, +1.78
held-out); the clears gain is at the boss (boss deaths 88 vs 107 of 500,
elite deaths level), and HP at the boss is +1.6. The SPRT stayed open at
n 500 (z 2.2 sits between its boundaries), so the fixed-n read is the
verdict: a removal is worth about +1.8 HP end-HP, above the spec's ~1 HP
bar, so removal and shops stay on the run-layer list.

The sim chooser (option decks scored by 8 one-turn fights against the
next floor's pool plus 8 against the boss pool, like the reward chooser;
mean 7.9 distinct cards + keep = ~9 options) loses the whole gain. What
it removed in 250 sequences, with paired clears against the `strike` and
none arms on the same sequences:

| removed | n | clears sim | clears strike | clears none |
|---|---|---|---|---|
| Defend | 64 | 0.734 | 0.734 | 0.750 |
| a reward card | 59 | 0.525 | 0.644 | 0.576 |
| keep | 58 | 0.672 | 0.724 | 0.672 |
| Strike | 52 | 0.712 | 0.712 | 0.788 |
| Bash | 17 | 0.647 | 0.765 | 0.588 |

Removing a Defend does exactly as well as removing a Strike on those
sequences, so choosing among starter cards has nothing to win; the loss
comes from removing an earned reward card (24% of sequences, -0.12 clears
vs strike: Carnage 8, Wild Strike, Perfected Strike, Hemokinesis 5 each,
Heavy Blade, Pummel 4, Brutality, Body Slam, Pommel Strike, Shrug It Off,
Dropkick 3, Demon Form, Combust, Inflame once) and from keeping (23%,
-0.05). Like the rest-site chooser, this is selection noise: ~9 options
on 16 shared-seed fights each pick the lucky one, and the lucky one is
often a reward card the chooser took two floors earlier. A rule
("remove the first Strike") beats the chooser; decisions "Card removal
read". Deaths by floor otherwise match (elite deaths 3-4 / 14 on floors
5 and 8 in every arm).

## Effects vs ids on the generated bench, one turn deep (Q6, first half; b39aa; read 14:20 2026-11-02, manager 837a5e68)

`gen_powers12c3` (the 3-copy generated-power bench: 326 cells per set,
`original` = the official power card, `generated` = its generated twin
swapped in), the ids5k and data5k r1 twins of seeds s1 / s101 / s201 (ids
nets see generated cards and powers as "unknown"), one-turn search, win
rate. Effects (data5k) minus ids (ids5k), per-cell means paired by seed,
se over the 3 seed differences.

| slice | cells | effects | ids | effects - ids (se) | per seed |
|---|---|---|---|---|---|
| original, elite + boss | 86 | 0.471 | 0.317 | +0.154 (0.030) | +0.17 +0.20 +0.10 |
| generated, elite + boss | 86 | 0.321 | 0.273 | +0.048 (0.015) | +0.06 +0.07 +0.02 |
| original elite | 63 | 0.528 | 0.344 | +0.184 (0.023) | |
| generated elite | 63 | 0.361 | 0.299 | +0.062 (0.012) | |
| original boss | 23 | 0.313 | 0.240 | +0.072 (0.086) | |
| generated boss | 23 | 0.214 | 0.204 | +0.010 (0.046) | |
| original hallway | 240 | 0.462 | 0.446 | +0.016 (0.015) | |
| generated hallway | 240 | 0.412 | 0.402 | +0.009 (0.015) | |

Reading. One turn deep the effects encoding's edge over ids is mostly on
the *known* card: +0.154 on the original elite and boss cells, +0.048 on
the generated twins. The swap costs the effects nets 0.150 of their win
rate and the ids nets 0.044 (they had less to lose); hallways are level
for both. So an effects net keeps about a third of its edge on an unseen
power card at one turn; by trigger class on the generated cards, the edge
is largest where the power pays at the owner's turn start combined with
HP loss (+0.06 to +0.10, 3-10 cells each) and about zero on plain
HP-loss (-0.002, 34 cells) and card-played triggers (+0.017, 57 cells),
in line with the horizon finding (turn-start powers are what a one-turn
leaf can't see). The two-turn half of Q6 (b39c1 / b39c2, s1 twins on the
elite and boss cells) reads against this: the review's rule is "effects
minus ids within 0.01 at two turns" (s1 one turn: +0.059 on the generated
elite + boss cells) means the simulator, not the encoding, does the
generalising. Script: per-cell paired means over the six
`results/gen_powers/arms/gen_powers12c3/2026-10-31-{ids5k,data5k}-s*-r1-*.json`
files (the `arms` subcommand expects r2 run names, so this read is by
hand; the two-turn files come from `gen_powers_read.py depth`).

## Run value along HP: step 0 of the fitted run value (approach review A3; offline, 14:15 2026-11-02, manager 837a5e68)

The approach review's gate for building a fitted run value
V_run(HP, floor) as the choosers' unit: at floors 5-8 the slope of
P(clear | HP at the floor's start) at 45 HP must be at least 3x its slope
at 75 HP, on the deck-adjusted logistic fit and on raw 10-HP bands alike
(`run_value.py`'s loader and fit; the earlier Q4 read looked along floors,
where the price is flat, not along HP).

| pool | floor | logit slope ratio 45/75, raw | adjusted | raw bands (40s vs 50s) / (70s vs 80s) |
|---|---|---|---|---|
| headline file (one turn, starter + sim + sim-boss, 500) | 5 (elite) | 1.00 | 1.00 | - (no 40s band) |
| | 6 | 4.78 | 4.79 | - (no 80s band) |
| | 7 | 5.56 | 5.57 | - |
| | 8 (elite) | 8.36 | 8.40 | 4.46 |
| | 9 | 23.6 | 23.9 | - |
| starter + rewards, 3 files (random / sim / sim-boss) | 5 | 0.55 | 0.58 | 1.44 |
| | 6 | 2.52 | 2.50 | 1.16 |
| | 7 | 2.62 | 2.58 | 4.01 |
| | 8 | 2.88 | 2.81 | 4.85 |
| two-turn cell @hpe, 4 files | 6-8 | 2.8-3.0 | 2.8-3.2 | 3.3-4.0 |

Reading. The sigmoid is there once HP has spread: on the product's own
headline file, floors 6-8 pass the gate clearly (P(clear) runs 0.2 in the
20s band to 0.9+ above 70 HP; at 75 HP the curve is already in its flat
top), and floor 9 is steeper still. Floor 5 fails everywhere: the median
HP there is ~73 and P(clear) ~0.5-0.7, so the steep part sits near 70 HP,
not 45. The 3-file pool lands at 2.5-2.9 because it mixes three chooser
settings with different clear rates (the fit then spreads). Verdict:
half a pass. A flat HP price mis-prices HP from floor 6 on, which is
where 34% of reward offers are made under 55 HP, so the fitted V_run is
worth building as the chooser's unit (approach 3, use 1), fitted per
player and setting (not pooled) and reported with floor 5 excluded from
the gate. Script in the manager's scratchpad (hp_slope.py); it reuses
`run_value.load`, `floor_data` and `logit_fit`.

## Two-turn product on the headline setting: 0.804 clears (Q2; b39a / b39b; read 14:30 2026-11-02, manager 837a5e68)

Goal 2's headline number. `gauntlet.py play
runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01 --two-turn
--start starter --rewards sim --sim-boss`, sequences 0-249 and 250-499 (2
threads and 3 GB each, 128 min per half), merged into
`results/gauntlet/net1029-hpe0.01-two-starter-simboss.json` (settings
identical, seed 20261101). Paired by sequence against the one-turn product
on the same setting and the heuristic anchor; protocol d1 1.5, min n 50.

| player (starter deck, sim + sim-boss rewards) | clears | two-turn minus it: clears (se) | end-HP (se, z) | protocol | train / held-out clears |
|---|---|---|---|---|---|
| two-turn 10-29 net `@hpe0.01` | **0.804** | | | | 0.752 / 0.856 |
| one-turn 10-29 net `@hpb0.01` | 0.680 | +0.124 (0.022) | +5.73 HP (0.87, z 6.6) | pass at n 141 | +0.092 / +0.156 |
| heuristic, one turn | 0.534 | +0.270 (0.026) | +12.44 HP (0.97, z 12.8) | pass at n 79 | +0.292 / +0.248 |

Where it comes from (two-turn / one-turn / heuristic):

| | reach boss (of 500) | boss win per arrival | HP at boss | mean end-HP (0 if dead) | floor-8 elite won | HP lost per elite (floors 5 / 8) |
|---|---|---|---|---|---|---|
| two-turn | 474 | 0.848 | 63.7 | 28.2 | 0.976 | 17.4 / 13.8 |
| one-turn | 447 | 0.761 | 59.4 | 22.5 | 0.937 | 18.9 / 14.1 |
| heuristic | 401 | 0.666 | 53.9 | 15.8 | 0.879 | 21.0 / 16.4 |

Deaths by floor, two-turn vs one-turn: first elite 1 / 4, floors 7-8
2 / 3, second elite 12 / 31, floor 10 11 / 15, boss 72 / 107. Boss win
per arrival by boss: Hexaghost 0.82 vs 0.71, Slime Boss 0.95 vs 0.89, the
Guardian 0.76 vs 0.66; by entry-HP band (30s / 45s / 60s / 75+) 0.37 /
0.78 / 0.96 / 0.98 vs 0.33 / 0.76 / 0.90 / 0.98. On the 178 paired
sequences where both players entered the boss within 5 HP of each other
the two-turn player won 0.882 vs 0.837. Card picks are the same (the
chooser's sims are one-turn in both: Anger 325 / 330, Inflame 313 / 309,
Spot Weakness 309 / 307, Combust 264 / 233, ~8.5 cards per sequence).

Reading, sceptically. The gain is twice depth's gain on the cell gauntlet
(+0.060, se 0.016, same net, `@hpe` both) and the mechanism differs: on
cells the boss was won at the same rate per arrival (0.760 vs 0.757) and
depth's gain was HP kept; here the boss is won more often per arrival
(+0.087; +0.045 at matched entry HP) on every boss, and elite deaths fall
as before. The difference between the settings is the deck: reward decks
hold scaling powers and setup cards (Inflame, Spot Weakness, Combust,
Anger), whose value sits past the one-turn leaf like Poison's and the
generated turn-start powers' (results "Silent zero-shot number",
"Novelty cost sits past the one-turn horizon"), so depth pays more with a
reward deck than with the fixed close-fight cell decks. Not training
noise: the two files use the same net and differ only in search, paired
on the same sequences; the halves (0-249 / 250-499) agree in sign (+0.092
/ +0.156, 1.4 se apart; they share the starter deck and differ only in
the encounter book). This does not change the product player (the
two-turn `@hpe` player already was it); it is its number on the headline
setting, and it strengthens the approach review's A2: play-time search is
the strongest lever and its cost (2 x 128 min at 2 threads vs 16 min one
turn for 500 sequences) is the throughput limit. The mixed-depth check on
this setting (0059l7r3b39b2) and the committed-line read (b39b1) are
queued. The heuristic anchor at two turns on this setting is not played
(the review's cheap read 1 asks for it on cells; here it would cost
~2 x 128 min x 1.1 and tell how much of 0.804 is the net).

## Where a turn's two-turn cost goes by decision index (line-seed.md step 2, `line_probe.py`; 14:35 2026-11-02, manager 837a5e68)

20 held-out elite and boss tight2 cells (5 each of Gremlin Nob, Lagavulin,
Three Sentries, Slime Boss), the 10-29 net, the product's two-turn
settings (turns 2, sample_k 4, 400k nodes), fallback rule, per-decision
seeds, one thread: 502 two-turn searches over 139 turns, 3.61 decisions
per turn, 87 s in all (`results/depth/line-probe.json`).

| index within the turn | n | nodes | leaves | ms | cut share |
|---|---|---|---|---|---|
| 0 (the turn's first decision) | 139 | 22,801 | 4,101 | 345 | 0.01 |
| 1 | 134 | 9,859 | 2,077 | 169 | 0.01 |
| 2 | 122 | 4,271 | 802 | 73 | 0.00 |
| 3 | 85 | 1,435 | 253 | 20 | 0.00 |
| 4+ | 22 | ~1,400 | ~280 | ~18 | 0.00 |

Index-0 share of a turn's cost: nodes 0.61, leaves 0.59, ms 0.59. So the
first tree already holds about 60% of a turn's two-turn work and the
later searches shrink fast (fewer cards left), which puts the saving from
committing to the first tree's line at ~1.7x on the two-turn part, the
low end of the approach review's 1.5-1.9x guess (the review marked that
number as not re-derived). Caveat: tight2 cells start at low HP with
short fights; a run-HP gauntlet turn holds more cards, so its split may
differ (`--fights 80` on other cells costs ~6 min). The strength question
(does committing cost anything?) is the queued read b39b1.

## Elite skip: the path ceiling is large, a plain HP rule takes about a tenth of it (Q3; b39ab / b39ac; read 14:35 2026-11-02, manager 837a5e68)

`docs/specs/elite-skip.md` (folded): on the headline setting, one turn
deep (`@hpb0.01`, starter deck, sim + sim-boss rewards), `--elites skip`
fights a hard hallway instead of every elite and `--elites hp --elite-hp
40` does so only when the HP entering the floor is under 40. Both read
with `--against` the one-turn headline file (protocol d1 1.5), so they
stopped early.

| arm vs fighting every elite | n | end-HP (se) | clears | HP at boss | protocol |
|---|---|---|---|---|---|
| `skip` (the ceiling: no elite payoff on this gauntlet) | 50 | +14.0 (2.3) | 0.920 vs 0.720 | 78.4 vs 59.6 | pass at 50 |
| `hp` 40 (the plain rule) | 100 | +1.53 (0.61) | 0.770 vs 0.730, +0.040 (0.024) | 62.9 vs 61.1 | pass at 83 |

The rule fires on 22 of 200 elite floors (2 at the first elite, 20 at
the second; mean HP at the skip 30). On the 20 sequences where it fired
the run cleared 0.65 vs 0.45 when the elite was fought (ceiling arm
0.86) and ended with 18.3 vs 10.6 HP; elsewhere the rows are the
control's. In the control file, 136 of 993 elite floors are entered
under 40 HP; the elite is still won there 75% of the time, but only 33%
of those runs clear.

Reading. With no elite payoff, skipping is pure gain and the ceiling
(+14 HP end-HP, +0.20 clears at n 50) is an upper bound on what any path
choice could be worth on this yardstick, not a product number. The one
plain rule recovers about a tenth of it over all sequences (+1.5 HP) and
about half of it on the sequences it touches, with a threshold picked
once (40). So path choice is a real run-layer lever here, of the same
order as a card removal (+1.8 HP), and most of its value needs an elite
payoff to be measured honestly: a map with relics and better rewards is
the owner's simulator decision. The headline setting stays without a
path rule (a rule that avoids elites on a gauntlet where elites pay
nothing would bias the yardstick toward never fighting them). The flags
stay for the full-run number.

## Effects vs ids, the solve step and threshold rows at run level (approach review cheap reads 2, 3, 5; b39abb; read 16:20 2026-11-02, manager 3a78b41d)

Ten one-turn cell gauntlets `@hpb0.01`, sequences 0-499, paired by
sequence against the 10-29 recipe twin of the same seed
(`net1029[-s101|-s201]-hpb0.01.json`): the ids5k and data5k r1 twins
(seeds s1 / s101 / s201; data5k is the effects encoding on the same 5k
round-0 games) and the lean and lean-thr r2 nets (lean = the 10-29 recipe
without the solve step; lean-thr = lean plus threshold rows). End-HP is 0
for a death.

| net (r1 at 5k games, or r2) | clears s1 / s101 / s201 | end-HP s1 / s101 / s201 |
|---|---|---|
| 10-29 recipe (control twins) | 0.634 / 0.634 / 0.620 | 24.5 / 24.0 / 24.2 |
| data5k (effects) | 0.584 / 0.608 / 0.562 | 20.9 / 22.5 / 21.2 |
| ids5k | 0.530 / 0.526 / 0.570 | 19.2 / 18.7 / 19.4 |
| lean | 0.636 / 0.632 / 0.622 | 24.0 / 24.3 / 23.7 |
| lean-thr | 0.592 / 0.644 / 0.630 | 22.6 / 25.1 / 23.9 |

Paired differences, mean over the 3 seeds (seed sd), with the per-seed
values; the train / held-out split is by card half (held-out = cards the
nets never trained on):

| contrast | clears | end-HP | per seed clears | per seed end-HP | held-out clears per seed | train clears per seed |
|---|---|---|---|---|---|---|
| ids minus data (ids vs effects, same games) | -0.043 (0.046) | -2.47 (1.21) | -0.054 / -0.082 / +0.008 | -1.79 / -3.87 / -1.75 | -0.140 / -0.116 / +0.016 | +0.032 / -0.048 / 0.000 |
| data5k minus 10-29 (5k r1 vs 20k r2) | -0.045 (0.017) | -2.68 (1.11) | -0.050 / -0.026 / -0.058 | -3.60 / -1.45 / -3.00 | | |
| lean minus 10-29 (no solve step) | +0.001 (0.002) | -0.22 (0.48) | +0.002 / -0.002 / +0.002 | -0.51 / +0.33 / -0.48 | +0.016 / 0.000 / 0.000 | -0.012 / -0.004 / +0.004 |
| lean-thr minus lean (threshold rows) | -0.008 (0.031) | -0.14 (1.19) | -0.044 / +0.012 / +0.008 | -1.47 / +0.81 / +0.24 | -0.036 / +0.028 / +0.008 | -0.052 / -0.004 / +0.008 |

Per-pair se over 500 sequences is ~0.015 clears and ~0.5 HP. Boss
arrivals (3 seeds pooled): ids reach 0.801, win per arrival 0.677, HP at
the boss 63.2; data 0.824 / 0.710 / 64.3; lean 0.869 / 0.725 / 65.7;
lean-thr 0.875 / 0.711 / 64.9; 10-29 0.869 / 0.724 / 65.3. Deaths: ids
dies more on Lagavulin (75 vs 63) and the Guardian (142 vs 117) than
data; ids and data both die more on every elite than the 10-29 nets.

Reading. (1) **The effects encoding's edge holds at run level, and sits
on unseen cards**: ids loses 2.5 HP of end-HP per sequence and ~0.04
clears to the effects twin trained on the same games; on the held-out
half it is -0.14 / -0.12 / +0.02 clears, on the train half about zero
(+0.03 / -0.05 / 0.00). The s201 pair is the odd one (ids s201 is the
strongest ids seed and data s201 the weakest data seed), so the seed sd
of this contrast (0.046 clears) is large and the clears figure is ~1.6 se
from zero; the end-HP figure (all three seeds -1.8 to -3.9) is firmer.
This matches tight2 (effects beats ids by 0.075 on held-out elites, 0.034
on train) and the generated-bench one-turn read (+0.154 on the original
cards, +0.048 on generated twins): the encoding earns its keep where the
cards are new to the net, which is the goal-1 case; on cards the net
trained on, ids do as well. (2) **The solve step is worth nothing at run
level**: lean is level with the 10-29 recipe on all three seeds (+0.001
clears, seed sd 0.002; -0.22 HP, seed sd 0.48; held-out and train alike).
The ladder's ~0.01 tight2 gap did not reach the gauntlet. This is evidence
for the approach review's decision 7 (drop the solved DB and solver from
the training path), which stays the owner's call. (3) **Threshold rows:
no run-level effect** (-0.008 clears, -0.14 HP, seeds split -1.5 / +0.8 /
+0.2 HP), same as their tight2 null; the layout stays as it is. (4)
**From-scratch seed noise at run level**: the 5k r1 twins spread ~0.02
clears and ~0.8 HP across seeds (ids 0.530 / 0.526 / 0.570, data 0.584 /
0.608 / 0.562), about twice the 10-29 recipe twins' 0.01 / 0.4 HP (results
"Run-level seed noise (twins)"), as the fresh-round-0 tight2 figure
predicted. A 5k r1 arm at 3 seeds detects ~1.6 HP end-HP (MDE 2.8 x 0.8 x
sqrt(2/3)), so the ids contrast is detectable at this size and the
threshold-row one was not expected to be.
Script: the manager's scratchpad `twins_read.py` (pairs by sequence via
`gauntlet_protocol.end_hp`).

## Effects vs ids on the generated bench, two turns deep (Q6, second half; b39c1 / b39c2; read 18:20 2026-11-02, manager 2b40a321)

The s1 twins (ids5k s1, data5k s1 = effects on the same 5k games) on the
elite and boss cells of `gen_powers12c3` (86 cells x 2 sets x 12 fights),
one turn deep (`one`, the same fights as b39aa) and under the fallback
two-turn player (`gen_powers_read.py depth`, 2 threads, ~2.5 h each).
Per-cell win rates, effects minus ids paired by cell, se over cells.

| slice | cells | depth | effects | ids | effects - ids (se) |
|---|---|---|---|---|---|
| original, elite + boss | 86 | one | 0.430 | 0.265 | +0.166 (0.031) |
| | | two | 0.605 | 0.529 | +0.076 (0.018) |
| generated, elite + boss | 86 | one | 0.317 | 0.258 | +0.059 (0.018) |
| | | two | 0.406 | 0.389 | +0.017 (0.012) |
| original elite | 63 | one / two | 0.512 / 0.627 | 0.287 / 0.526 | +0.225 (0.039) / +0.101 (0.021) |
| generated elite | 63 | one / two | 0.362 / 0.442 | 0.278 / 0.421 | +0.085 (0.021) / +0.021 (0.013) |
| original boss | 23 | one / two | 0.207 / 0.543 | 0.203 / 0.536 | +0.004 (0.029) / +0.007 (0.030) |
| generated boss | 23 | one / two | 0.192 / 0.308 | 0.203 / 0.301 | -0.011 (0.029) / +0.007 (0.031) |

Depth's own gain (two minus one, per cell): ids +0.265 (se 0.031) on the
originals and +0.131 (0.020) on the generated twins; effects +0.174
(0.021) and +0.089 (0.015). Overrides: ids 9,032 of 45,100 decisions,
effects 7,093 of 44,137; cuts ~2,700 each.

Reading. (1) **Two turns deep the simulator does most of the
generalising.** On unseen generated power cards the effects encoding's
edge over ids falls from +0.059 to +0.017 (se 0.012; the review's rule was
"within 0.01 = the simulator generalises", and this is within one se of
it), on the same cells and seed. The ids net sees a generated card as
"unknown" and still wins 0.389 of the generated elite and boss fights
under two-turn search, against the effects net's 0.406: search reads the
card by playing it out. (2) **The edge shrinks on known cards too** (+0.166
to +0.076): depth lifts the ids net by 0.265 and the effects net by 0.174
on the originals, i.e. most of what the effects columns gave at one turn
is also what a two-turn tree finds. What remains at two turns (+0.08 on
known elites, +0.02 on unseen) is the encoding's real play-time worth
under the product. (3) **On bosses the encoding never mattered** (one turn
+0.004 / -0.011, two turns +0.007 at both sets): boss fights at these
cells are decided by things neither column set prices, and depth lifts
both nets by the same +0.34 on the original boss cells. (4) One seed; the
one-turn per-seed spread on the generated slice was +0.06 / +0.07 / +0.02,
so the two-turn level carries about +-0.02 of seed noise, but the shrink
is paired on the same seed and cells and is the firm part. What it
changes: the effects encoding stays (it carries one-turn screens and the
sim choosers, which play one turn deep, and +0.08 on known elites under
the product), but goal-1 numbers are read under the product's two-turn
search, where a net's encoding of a new card matters ~3x less than one
turn deep; and the review's A1 reading (fidelity of the simulator plus
search over encodings) gains a second data point beside the Silent and
turn-start-power reads. Script: per-cell means over the `one` / `two`
lists of `results/gen_powers/depth/2026-10-31-{ids5k,data5k}-s1-r1-*-elite_boss.json`
by the bench's `cell` / `set` (in this run's scratchpad).

## Mixed depth on the headline setting: the protocol stopped at n 50, a fixed-n read is queued (R4 left; b39b2; 18:20 2026-11-02, manager 2b40a321)

`--one-turn-floors 3` on the headline setting (starter + sim + sim-boss,
two turns from floor 4), `--against` the two-turn headline file, stopped
by the protocol at its first look: "fail" at n 50 = not 1.5 HP better,
which is the expected verdict for a cost-saving candidate (the review's
note: read a fail as "not 1.5 HP better", not as "worse"). At n 50 it is
level: clears 0.900 vs 0.920 (-0.020, se 0.020; the 5 vs 4 deaths all at
the boss), HP at the boss 62.6 vs 62.9, end-HP 26.1 vs 26.7 (-0.66, se 0.72).
Too few sequences to call it level at the +-1 HP the cell read used (n
250, se ~1 HP). The run continues to 250 sequences without `--against`
(job 0059l8c, behind the survival arms so the landing isn't delayed);
read it with `gauntlet.py read` against the headline file: level within
1 HP and 0.02 clears -> mixed depth becomes the screening default on the
headline setting too (43% cheaper). Rule for later cost-saving reads:
fixed n, not `--against` (decisions "Cost-saving candidates are read at
fixed n").

## Boss replays: the boss curve is causal, and it is a different curve per boss (L2 a; b39d1; read 18:30 2026-11-02, manager 2b40a321)

`boss_replay.py` (docs/specs/boss-replay.md, folded) rebuilt the boss
fight of every headline sequence that reached the boss (474 of 500; the
deck it brought = starter + every `took`, its boss, its seed) and played
it one turn deep with the product net `@hpb0.01` at entry HP 30, 40, ...,
80 on 4 common seeds (the boss floor's own seed and three more in the
sequence's block): 11,376 fights, 7 min at 3 threads. Only HP varies, so
the curve is causal for these decks.

| boss | decks | P(win) at 30 | 40 | 50 | 60 | 70 | 80 | HP at 0.5 / 0.9 |
|---|---|---|---|---|---|---|---|---|
| all | 474 | 0.35 | 0.52 | 0.68 | 0.80 | 0.91 | 0.95 | 39 / 69 |
| hexaghost | 161 | 0.33 | 0.45 | 0.59 | 0.72 | 0.86 | 0.90 | 43 / never |
| slime_boss | 165 | 0.62 | 0.83 | 0.92 | 0.97 | 0.98 | 0.99 | <30 / 47 |
| the_guardian | 148 | 0.07 | 0.25 | 0.49 | 0.71 | 0.88 | 0.95 | 50 / 73 |

(se over decks 0.01-0.03.) Beside it the observational curve from the
same file (two-turn play, win by arrival-HP band): pooled 0.38 / 0.63 /
0.76 / 0.95 / 0.98 / 0.98 for the 30s ... 80s bands (n 37 / 51 / 88 / 103
/ 91 / 104).

| | observed slope 40s -> 60s | causal slope 40 -> 60 | causal share | corr(arrival HP, causal win at 60) |
|---|---|---|---|---|
| all | +0.32 | +0.28 | 0.87 | +0.13 |
| hexaghost | +0.25 | +0.26 | 1.04 | +0.12 |
| slime_boss | +0.11 | +0.14 | 1.24 | +0.17 |
| the_guardian | +0.59 | +0.47 | 0.78 | +0.15 |

Per deck: the HP where a deck's own win rate crosses 0.5 has quartiles
30 / 37 / 50 over all decks (Guardian 40 / 50 / 57, Hexaghost 30 / 40 /
55, Slime Boss at or under 30 for three quarters), 6 decks never reach
0.5; the width from 0.25 to 0.75 has quartiles 5 / 10 / 20 HP. 449 of
474 decks win >= 3 of 4 at 80 HP; 267 win <= 1 of 4 at 30.

Reading. (1) **The confound is small: the boss curve is causal.** The
observational slope between the 40s and the 60s is 87% reproduced when
only HP changes (Hexaghost and Slime Boss fully, the Guardian 78%), and a
deck's arrival HP barely predicts how well it does at a fixed 60 HP
(corr +0.13). Weak decks arriving low explains little; low HP itself
loses the boss. So the run value along HP keeps its full size for L2
(b)-(d): there is nothing to shrink. (2) **It is a different curve per
boss, and the boss is known from the map.** Slime Boss is nearly sure
from 40 HP (0.83) and 0.97 at 60; the Guardian is a cliff (0.25 at 40,
0.49 at 50, 0.71 at 60, 0.95 at 80: 10 HP near 50 is worth ~0.2 of a
win); Hexaghost climbs slowly and tops out at 0.90 at 80 (a deck-dependent
ceiling: 19 decks never reach 0.5). A pooled curve mis-prices HP for two
of three bosses, so the choosers' unit is per boss. (3) **Per deck the
step is sharp** (median width 10 HP): a deck mostly has an HP it needs,
and a chooser that knows the deck's own step (the sim-boss fights give
one point of it at the post-rest HP) prices HP better than any pooled
curve; that is L2 (b)'s design room. (4) Caveats: the replays are one
turn deep while the headline file is two-turn play, so the causal curve
sits lower at the top (0.80 vs 0.95 at 60; depth wins boss fights the
one-turn player loses) and the slope comparison, not the level, is the
read; a two-turn confirmation on a slice (the Guardian's 40-60 band) is
cheap if (b) hinges on the level. Decks that died before the boss (26)
are not in the curve. Output: `net1029-hpe0.01-two-starter-simboss-2026-10-29-seed-check-r2-s1-1a789b2-hpb0.01-12a77a-55cb.json`; read with
`boss_replay.py read`.

## Crossed chooser arms: the chooser holds most of the one-turn headline lead, and nearly all of it on held-out cards (approach review cheap read 10; b39d3; read 19:20 2026-11-02, manager 2b40a321)

Headline setting one turn deep (starter deck, sim rewards, sim-boss),
sequences 0-249, `--chooser` (docs/specs/chooser-player.md, folded): the
fight player and the player whose one-turn sims score the reward options
crossed. Controls: net/net (`net1029-hpb0.01-starter-simboss.json`,
0.688 on 0-249) and heuristic/heuristic (0.532). Paired by sequence;
end-HP = boss HP left if cleared, else 0.

| fighter / chooser | clears | train / held-out | vs net/net (clears, end-HP) | vs heur/heur (clears, end-HP) |
|---|---|---|---|---|
| net / net | 0.688 | 0.680 / 0.696 | - | +0.156 |
| net / heuristic | 0.568 | 0.624 / 0.512 | -0.120 (0.031), -3.6 HP (1.4); protocol fail at 236 | +0.036 (0.034), +3.6 HP (1.1); pass at 153 |
| heuristic / net | 0.596 | 0.520 / 0.672 | -0.092 (0.033), -5.8 HP (1.1); fail at 65 | +0.064 (0.037), +1.5 HP (1.2); open at 250 |
| heuristic / heuristic | 0.532 | 0.456 / 0.608 | -0.156 | - |

Reading. (1) **Swapping the chooser moves clears more than swapping the
fighter.** With the net fighting, the heuristic's choices cost -0.120;
with the heuristic fighting, the net's choices gain +0.064. Swapping the
fighter: +0.036 with the heuristic choosing, +0.092 with the net choosing.
Average chooser effect ~0.09 of the 0.156 lead, fighter ~0.06, and they
interact: the net's chooser is worth most when the net also fights (its
sims are played by the player that will play the deck), which is the
self-consistency the sim chooser was built on. (2) **By half the split
is stark.** On held-out cards the heuristic chooser loses -0.184 against
the net chooser (net fighting) while the fighter swap is -0.024 (heuristic
chooser) / -0.096 (net chooser): the heuristic can't price the cards it
doesn't know, so its picks are poor there, and the one-turn net's own
fighting edge on held-out decks is small. On the train half the fighter
swap is +0.160 / +0.168 and the chooser swap +0.056 / +0.064. So the
one-turn net's play-time lead sits on training cards; on unseen cards
the lead comes from choosing with the net's sims. (3) What it changes:
chooser work (L2 b, a learned or better-simulated chooser) and fighter
work (depth) are both live, with the chooser the larger one-turn lever
and the one where the heuristic is weakest on new cards; for goal 1 the
chooser is a second place where an unseen card's price matters, and the
yardstick should include the chooser (the headline setting), not only
cell fights. Caveat: one turn deep; two turns deep the fighter's share
grows (depth gave +0.124 on this setting), so the two-turn split is a
later read if a decision needs it.

## Run-value chooser: fails its first check on both halves (L2 b; b39d4; read 19:40 2026-11-02, manager 2b40a321)

`--rewards vrun` (docs/specs/run-value-chooser.md, folded): each reward
option scored by P(reach the boss at h | fit-half neighbours) x P(win the
sequence's own boss | h, deck), the per-boss causal curve shifted to the
deck's 8 boss fights, instead of the sim chooser's `1 + 0.01 x end HP`
plus pool-boss fights. One turn deep on the starter setting, the 10-29
net `@hpb0.01`, fit on one half of the one-turn headline file and played
on the other, against that file on the played half.

| played / fitted | clears vrun vs sim | train / held-out | end-HP (se) | protocol at 250 | picks changed | skips vrun / sim |
|---|---|---|---|---|---|---|
| 0-249 / 250-499 | 0.644 vs 0.688 (-0.044, se 0.037) | -0.104 / +0.016 | -1.5 HP (1.4) | open | 22.5% | 21.4% / 15.6% |
| 250-499 / 0-249 | 0.628 vs 0.672 (-0.044, se 0.038) | -0.064 / -0.024 | -1.4 HP (1.5) | open | 23.9% | 21.3% / 14.4% |

Pooled: -0.044 clears (se 0.026), -1.45 HP (se 1.0). Pick change by
floor rises from 10-16% at floors 1-3 to 27-34% at floors 7-9 and 46-49%
at floor 10 (the last reward, where the score is the mean of 8 fights
against the actual boss); decks arrive at the boss with 7.9 taken cards
against the sim chooser's ~8.5.

Reading. (1) **Fail.** The rule asked for a protocol pass or > 1.5 HP on
both halves with >= 10% of picks changed; the picks change (22-24%) and
the result is worse by about one se per half, the same size on both
halves. (2) Where the harm sits is visible but not proven: the new unit
skips a quarter more often, and most of its changed picks are late
(floors 7-10), where its boss term is the deck's own 8 boss fights (se
~0.17 of a win) pushed through a logit shift, so option ranks there are
noisy; early (HP ~80, the causal curve flat) a card that wins the next
fight at 76 HP and one at 80 HP score nearly equal, where the old score
kept the HP tiebreak. (3) What it says about L2: the run value is causal
and steep per boss (boss replays), but using it as the chooser's unit
with the deck level from 8 fights does not beat the flat score with the
sim-boss term, which already carries the deck's boss strength as a mean
over 8 fights. The owner's use (b) for card picks closes as built; two
cheap variants are recorded as ideas, not run: the curve's level from the
pooled per-boss curve (no deck shift, deck strength only through the
next-floor sims) and the old score as a tiebreak inside the flat top.
Uses (c) (a combat price by floor) and (d) (the survival leaf) are
unchanged in standing: (c) waits for the landing, (d) for the survival
arms. Output: `results/gauntlet/net1029-hpb0.01-vrun-fit{250,0}-starter.json`.

## Mutated monsters, stage A, one turn deep: stat changes cost the net little, an unseen power on a new enemy costs it a lot (L4; b39l8b3; read 19:55 2026-11-02, manager 2b40a321)

`mutate_monsters.py` (docs/specs/mutated-monsters-a.md): 200 elite and
boss starts the product reached on the headline file (134 elite, 66
boss; cell decks at the product's entry HP), each advanced to its first
decision and patched: every living monster's HP and max HP scaled, or a
power added; one-sided modifiers, the owner's boon + bane pairs and one
stack; 8 common seeds per start; played to the end by the heuristic and
by the product net one turn deep (`@hpb0.01`). 9 min at 3 threads. The
two-turn subset (40 starts x 4 seeds) is queued (0059l8b4) and fills the
"repair" column later. Win change from the parent, paired by start (se):

| modifier | heuristic | one-turn net | difficulty | novelty cost (net - heuristic) | HP lost, heur / net |
|---|---|---|---|---|---|
| hp0.8 | +0.081 (0.014) | +0.064 (0.012) | easier | -0.018 (0.010) | -7.9 / -8.1 |
| hp1.25 | -0.087 (0.013) | -0.101 (0.015) | harder | -0.013 (0.011) | +8.3 / +9.0 |
| str1 | -0.039 (0.008) | -0.051 (0.009) | harder | -0.012 (0.008) | +2.7 / +3.0 |
| str2 | -0.076 (0.014) | -0.097 (0.016) | harder | -0.021 (0.009) | +5.1 / +5.7 |
| metal3 | -0.033 (0.007) | -0.044 (0.009) | harder | -0.012 (0.009) | +3.2 / +4.0 |
| ritual2 | -0.136 (0.021) | -0.174 (0.022) | harder | -0.038 (0.011) | +9.0 / +10.9 |
| sharp2 (SharpHide 2) | -0.160 (0.020) | -0.208 (0.022) | harder | -0.048 (0.015) | +14.1 / +17.4 |
| metal4-hp0.85 (pair) | +0.016 (0.006) | -0.003 (0.008) | easier | -0.019 (0.008) | -1.9 / -0.8 |
| ritual2-hp0.7 (pair) | -0.051 (0.016) | -0.070 (0.018) | harder | -0.019 (0.010) | -2.8 / -3.6 |
| sharp2-hp0.9 (pair) | -0.097 (0.017) | -0.159 (0.020) | harder | -0.062 (0.015) | +10.0 / +13.3 |
| stack (both pairs) | -0.102 (0.019) | -0.193 (0.024) | harder | -0.091 (0.016) | +8.8 / +13.7 |

Stack: the heuristic's -0.102 against the sum of its parts -0.081; the
net's novelty cost -0.091 against -0.019 + -0.062 = -0.081: about
additive. By encounter, novelty cost of sharp2 / sharp2-hp0.9 / stack:
Three Sentries -0.215 / -0.203 / -0.235 (se 0.04; the heuristic itself
loses -0.26 / -0.19 / -0.27 there); Gremlin Nob -0.047 / -0.039 / -0.102;
Lagavulin +0.012 / -0.020 / -0.038; Hexaghost +0.022 / ~0 / ~0; Slime
Boss +0.017 / +0.040 / +0.034; the Guardian +0.025 / -0.025 / -0.033.
Ritual 2: Sentries -0.038, Lagavulin -0.038, Hexaghost -0.065, Guardian
-0.083 (se 0.02-0.06). HP x0.8 on bosses -0.057 (se 0.027): the net gains
less than the heuristic from an easier boss (Hexaghost -0.086, Guardian
-0.083). Strength on the Guardian: -0.117 / -0.125 (n 15, se 0.06).

Reading. (1) **Balance is measured, and two of the owner's three pairs
are off.** Metallicize 4 with HP x0.85 comes out *easier* (+0.016 for the
heuristic, +0.05 on bosses: the HP bane outweighs the boon), Ritual 2
with HP x0.7 harder (-0.051), SharpHide 2 with HP x0.9 clearly harder
(-0.097; SharpHide is a strong boon on multi-hit decks). As labelled
one-sided changes they still serve; as "near the parent" they need
retuning (HP x0.75 for Metallicize 4 looks closer; SharpHide 2 wants a
bigger bane or SharpHide 1). The stack's difficulty is about the sum of
its parts (-0.102 vs -0.081), so stacking as the distance axis is usable
with a measured, not assumed, sum. (2) **Stat changes: the net is nearly
as robust as the heuristic.** HP x0.8 / x1.25, Strength +1 / +2 and
Metallicize 3 cost the net -0.012 to -0.021 beyond the heuristic (each
~1-2 se; HP x1.25 -0.013). The review's HP-class rule (a regret rise on
HP alone = normalise or drop max_hp) is not met: the drop is small and no
larger than the Strength class. (3) **An unseen power on a new enemy is
where the cost is.** SharpHide costs the net -0.048 to -0.091 beyond the
heuristic, all of it on Three Sentries (-0.20 to -0.24) and Gremlin Nob
(-0.05 to -0.10), and nothing on the Guardian, the one enemy whose
training fights hold that power: the net learned SharpHide as "a Guardian
thing" and attacks into it on three Sentries with Strike-heavy decks. The
heuristic reads the power from the rules and loses only the difficulty.
Ritual 2 (seen on the Cultist) costs -0.038, spread over four enemies.
This is the novelty cost the owner's yardstick asks for, in the goal's
unit: ~0.05-0.09 of a win on an unseen power, ~0.01-0.02 on a stat
change. (4) Per the review's first check the next step is the two-turn
subset (queued 0059l8b4): a drop of >= 0.05 at one turn that depth
halves = a horizon problem (the fix is depth or an accrual term, no
training); a drop depth does not halve = the burst is admitted. Also
open: whether a power-feature row that reads SharpHide the same way on
any enemy (the effects encoding already keys powers by name; this says
the net's *use* of it is enemy-bound) is the cheaper fix. Output:
`results/mutate/a.json`; read with `mutate_monsters.py read`.

## Line seed: a two-turn player that commits to its first tree's line plays level or better (line-seed.md step 3; b39b1; read 20:00 2026-11-02, manager 2b40a321)

`--two-turn --line-seed` (every two-turn search of a combat turn gets the
turn's first sample seed, so later decisions follow the first tree's
line; docs/specs/line-seed.md) with the product net `@hpe0.01` on the
cell gauntlet, sequences 0-249, against the plain two-turn file on the
same sequences (`net1029-hpe0.01-two-a.json`). Fixed n 250 (the protocol
stayed open to the end, as a level candidate should: decisions
"Cost-saving candidates are read at fixed n").

| | line seed | plain two-turn | diff (se) |
|---|---|---|---|
| clears | 0.696 | 0.672 | +0.024 (0.019) |
| end-HP (0 on a death) | 28.0 | 27.4 | +0.60 (0.52) |
| HP at the boss | 69.0 | 69.0 | 0.0 |
| boss deaths / elite deaths | 48 / 28 | 60 / 22 | |
| train / held-out clears | 0.624 / 0.768 | 0.600 / 0.744 | +0.024 / +0.024 |

Reading. The rule (end-HP within +-1.0 HP, clears within +-0.012 of the
plain player) is met on end-HP and exceeded on clears in the favourable
direction (+0.024, 1.3 se): committing to the first tree's line loses
nothing we can see, and the bosses go slightly better (48 vs 60 deaths)
while elites go slightly worse (28 vs 22), both inside noise. So the
first tree's line is as good as re-searching each decision with fresh
samples, and the ~40% of a turn's two-turn cost that sits in the later
trees (line probe: the first tree holds ~60%) can be saved by exporting
the principal line from the first search and stepping it until a cut or
a chance event (stage 2, Rust, `search.rs`): ~1.7x cheaper two-turn play
at level strength. Stage 2 waits for the engine-next landing (no Rust
change to `search.rs` on main before it). Caveat: one book of 250
sequences on the cell setting; the headline setting (rewards) is not
read, and a confirmation on 250-499 is the usual next step once stage 2
exists and is cheap to run. Output: `results/gauntlet/net1029-hpe0.01-two-line-a.json`.

## Standing players re-ranked on the headline setting: none comes near the 10-29 net (approach review cheap read 4; b39d2; read 20:15 2026-11-02, manager 2b40a321)

One turn deep `@hpb0.01` on starter + sim rewards + sim-boss, sequences
0-249, fixed n, paired against the 10-29 net's file on the same
sequences (0.688); end-HP = boss HP left if cleared, else 0.

| player | clears | vs 10-29 (se) | end-HP (se) | protocol | train / held-out | tight2-era standing |
|---|---|---|---|---|---|---|
| 10-29 net (`seed-check-r2-s1`) | 0.688 | - | - | - | 0.680 / 0.696 | the night recipe |
| data40k s1 r1 | 0.632 | -0.056 (0.033) | -0.6 (1.3) | open at 250 | 0.648 / 0.616 | +0.009 held-out over 20k |
| cover21 s1 r1 | 0.592 | -0.096 (0.034) | -3.8 (1.4) | fail at 204 | 0.624 / 0.560 | -0.063 on the ladder |
| data80k s1 r1 | 0.584 | -0.104 (0.034) | -4.5 (1.3) | fail at 131 | 0.560 / 0.608 | best on tight2 held-out |
| lean-thr s1 r2 | 0.580 | -0.108 (0.034) | -3.9 (1.3) | fail at 213 | 0.584 / 0.576 | -0.017 on the ladder |
| burst8hp2 s1 (ex-champion) | 0.540 | -0.148 (0.037) | -5.6 (1.3) | fail at 129 | 0.456 / 0.624 | champion 11-01 to 11-02 |
| heuristic | 0.532 | -0.156 | | | 0.456 / 0.608 | |

Reading. (1) **The 10-29 net is the product net by a wide margin once
rewards are in the loop.** Every newer or bigger-data net is 0.06-0.15
clears worse on the headline setting, and the former champion burst8hp2
plays no better than the heuristic (0.540 vs 0.532; train half 0.456,
the heuristic's figure). (2) **The rulers disagree, in the direction the
review warned about (A7).** data80k was the best net on tight2 held-out
and is fourth here; data40k, ~0.01 below it on tight2, is the closest
here; the ladder's champion loses 0.15. On the cell gauntlet (no
rewards) these gaps were -0.02 to -0.03; with rewards they are 3-5x
larger, because each net also chooses its deck with its own sims
(crossed arms: the chooser holds most of the one-turn lead), so a net's
weaknesses compound through its picks. (3) What it changes: no newer
net is a candidate for the product until it beats the 10-29 net on this
setting; a training rule (decisions "Training: when it runs and when it
stops") that judges on the gauntlet protocol should use the headline
setting with rewards, not the cell gauntlet, as the final ruler; and the
tight2 / ladder numbers of 10-29 to 11-02 should not be used to rank nets
for the product. Why the 10-29 net is so much better here is open: it is
the only net trained with the solve step on the night recipe at 20k
games (lean = no solve step was level with it on the cell gauntlet), so
the recipe, not the data size, is the suspect, and a solve-step twin at
run level (lean s1 is level on cells; its headline file is the cheap
check) would say.

## Mutated monsters, stage A, two turns deep: depth removes the net's SharpHide cost, so the enemies rung is a horizon problem, not a training gap (L4; 0059l8b4; read 22:30 2026-11-02, manager 19428521)

The two-turn subset of the stage A run (`mutate_monsters.py play --players
two --two-starts 40 --two-seeds 4` into `results/mutate/a.json`; 83 min
at 3 threads, peak 3.89 GB): the first 40 of the 200 starts (27 elite:
Three Sentries 9, Gremlin Nob 10, Lagavulin 8; 13 boss: Hexaghost 6,
Slime Boss 4, the Guardian 3), each variant played by the product net two
turns deep (`play_on(turns=2)`, `@hpe0.01`) on the first 4 of the 8
common seeds. Below, every column is computed on those 40 starts and 4
seeds for all three players (the script's own "repair" column uses the
one-turn player's 8 seeds and agrees within 0.01). Win change from the
parent paired by start (se); novelty = the player's change minus the
heuristic's; repair = two minus one. Parent win on the subset: heuristic
0.844, one turn 0.863, two turns 0.881.

| modifier | heuristic | one turn | two turns | novelty, one turn | novelty, two turns | repair |
|---|---|---|---|---|---|---|
| hp0.8 | +0.100 (0.038) | +0.087 (0.035) | +0.075 (0.034) | -0.013 (0.028) | -0.025 (0.023) | -0.013 (0.018) |
| hp1.25 | -0.069 (0.030) | -0.056 (0.029) | -0.050 (0.020) | +0.013 (0.025) | +0.019 (0.030) | +0.006 (0.026) |
| str1 | -0.044 (0.023) | -0.056 (0.030) | -0.037 (0.023) | -0.013 (0.030) | +0.006 (0.017) | +0.019 (0.026) |
| str2 | -0.081 (0.036) | -0.100 (0.044) | -0.081 (0.036) | -0.019 (0.036) | +0.000 (0.022) | +0.019 (0.029) |
| metal3 | -0.019 (0.021) | -0.025 (0.027) | -0.025 (0.012) | -0.006 (0.026) | -0.006 (0.017) | +0.000 (0.025) |
| ritual2 | -0.156 (0.053) | -0.181 (0.059) | -0.144 (0.048) | -0.025 (0.033) | +0.013 (0.028) | +0.037 (0.033) |
| sharp2 | -0.156 (0.051) | -0.188 (0.056) | -0.150 (0.045) | -0.031 (0.043) | +0.006 (0.032) | +0.037 (0.026) |
| metal4-hp0.85 | +0.025 (0.017) | +0.013 (0.028) | +0.037 (0.017) | -0.013 (0.025) | +0.013 (0.012) | +0.025 (0.022) |
| ritual2-hp0.7 | -0.019 (0.045) | -0.056 (0.052) | -0.019 (0.038) | -0.037 (0.035) | +0.000 (0.028) | +0.037 (0.025) |
| sharp2-hp0.9 | -0.125 (0.051) | -0.144 (0.054) | -0.081 (0.042) | -0.019 (0.037) | +0.044 (0.028) | +0.062 (0.031) |
| stack (both pairs) | -0.144 (0.060) | -0.188 (0.068) | -0.131 (0.048) | -0.044 (0.048) | +0.013 (0.040) | +0.056 (0.046) |

Where the one-turn cost sits, the two-turn cost is gone. Elites (27
starts): sharp2 novelty -0.056 (0.047) one turn, 0.000 (0.027) two
turns, repair +0.056 (0.028); sharp2-hp0.9 -0.046 / +0.009 / +0.056
(0.039); the stack -0.093 (0.048) / -0.028 (0.024) / +0.065 (0.037).
Three Sentries (9 starts, the one-turn read's worst case): sharp2 -0.194
(0.116) / -0.056 (0.056) / +0.139 (0.073); the stack -0.194 / -0.028 /
+0.167 (0.093). Gremlin Nob (10): every two-turn change is 0 (the
two-turn player wins all its Nob variants). Bosses (13): one-turn novelty
is within noise already (+0.02 to -0.08, se 0.08-0.11) and two-turn the
same. Ritual 2: -0.025 / +0.013 / +0.037.

Reading. (1) **Depth more than halves the drop, so by the spec's rule
this is a horizon problem, and no training burst is admitted.** The
one-turn leaf has not met SharpHide on Sentries or Nob and attacks into
it; one more turn of search sees the damage come back and stops. With
depth, the product's cost beyond the heuristic on every modifier is
within +-0.025 (se 0.02-0.04): on these state-patch mutations the product
generalises as well as the rules-reading heuristic, and the net alone
does not. (2) **Precision.** 40 starts x 4 seeds: each repair is 1.2-2
se on its own; the four power modifiers (sharp2, sharp2-hp0.9, the
stack, ritual2) all repair by +0.04 to +0.06 and the stat modifiers by
~0, which is the pattern the horizon reading predicts and the burst
reading does not. The one-turn novelty cost on this subset (-0.031 for
sharp2) is smaller than on all 200 starts (-0.048) because of the start
mix and 4 seeds instead of 8; the elite and Sentries rows carry the
signal. (3) **What it changes.** The goal-1 enemies rung should be read
on the product player (two turns), not the one-turn net: the net's leaf
mispricing of an unseen power is real (~0.05-0.09 one turn deep on new
enemies) but search repairs it, as it did for turn-start powers on cards
(horizon replication) and for unseen cards (Q6 two turns). A training
burst on mutated monsters is not justified by this rung; the open
power-feature idea (a row that reads SharpHide the same on any enemy)
would fix the one-turn net only and is not needed for the product. Stage
B (pattern mutations: damage per hit, split hits, Weak on hit) after the
landing is where the two-turn product may still fail, because the leaf
and the heuristic both read moves from the engine's intents. (4) Balance:
the two-turn product agrees with the heuristic's verdicts (every pair's
verdict is `harder` / `easier` / `level` the same way on the 200-start
table with the two-turn column in); two retuned pairs (Metallicize 4 +
HP x0.75, SharpHide 1 + HP x0.9) are queued one turn deep (light, ~5
min) so the owner's pairs come out near the parent. Spec
`mutated-monsters-a.md` folded here and into decisions "Mutated monsters
stage A, two-turn read".

Retuned pairs (0062, `--mods metal4-hp0.75,sharp1-hp0.9`, 200 starts x 8
seeds, one turn deep, 3 min; `results/mutate/a-retune.json`): SharpHide 1 +
HP x0.9 is near the parent (heuristic -0.021, se 0.008; bosses -0.030,
elites -0.016) and the net's novelty cost on it is small (-0.006 all,
Sentries -0.032 vs -0.203 for SharpHide 2 + HP x0.9: the leaf's SharpHide
cost grows steeply with the power's size). Metallicize 4 + HP x0.75 is still
easier (+0.054; bosses +0.155, elites +0.005): on bosses the HP cut outweighs
Metallicize at any cut tried, on elites x0.75 is level, so no single HP
factor balances that pair for both groups. Stage B's pairs: `sharp1-hp0.9`
as is; Metallicize 4 with HP x0.75 on elites and ~x0.9 on bosses, or report
it by group.

## Mixed depth on the headline setting, fixed n 250: level by its bar, a small real cost on floors 1-3, less saving than on the cell gauntlet (R4 left; 0059l8c + 0059l8e; read 22:25 2026-11-02, manager 19428521)

`--one-turn-floors 3` on the headline setting (starter deck, sim rewards,
sim-boss, the product player two turns deep from floor 4), sequences
0-249, against the headline file (`net1029-hpe0.01-two-starter-simboss.json`,
same sequences), paired by sequence (`gauntlet.py read`): clears 0.840 vs
0.852 (-0.012, se 0.007; train -0.008 (0.008), held-out -0.016 (0.011));
end-HP 28.73 vs 29.00 (-0.27, se 0.34); HP at the boss 64.7 vs 64.9 (240
sequences reach it in both); floors won 10.76 vs 10.78. Deaths: 30 vs 27
at the boss (Guardian 17 vs 16, Hexaghost 11 vs 9), identical counts
everywhere else. 229 of 250 sequences pick the same cards; 160 are
identical in every row; the 90 that differ first differ on floors 1 / 2 /
3 (41 / 28 / 21), and the HP after floor 3 is -0.25 (se 0.10) for the
one-turn floors: a small, real cost of playing the first three hallways
without depth, which then washes out to within noise at the boss. Wall
time: ~91 min at 3 threads (16 min as 0059l8c before it was killed for
the survival arm, rows kept; 75 min as 0059l8e) against 128 and 127 min
at 2 threads for the two full-depth halves of 250: with the thread
difference, roughly 30% saved, not the cell gauntlet's 43%, because on
the headline more of a run's search time sits on floors 4+ (reward decks,
longer fights). Peak memory 3.9 GB (two-turn threads from floor 4; no
saving).

Verdict by the pre-set rule (level within 1 HP and 0.02 clears): level,
so `--one-turn-floors 3` is the screening default on the headline setting
too. The -0.012 clears is 1.7 se and the floor-3 HP cost is 2.5 se, so a
cost of about a hundredth of a clear is likely rather than excluded:
headline *reads* of product candidates (anything that may change the
headline number or the product string) keep full depth, and a paired
read never mixes the two settings between its arms. Decisions "Mixed
depth on the headline: screening default, headline reads keep full depth".

## Lean s1 on the headline: the solve step may carry about 0.05 of the 10-29 net's lead, at 1.5-2 se (headline re-rank's cheap check; 0061; read 22:35 2026-11-02, manager 19428521)

The 10-29 recipe without the solve step (`runs/2026-10-30-lean-s1-r2-9952dd3`,
same seed as the product net; level with it on the cell gauntlet on all
three seeds, results doc "Effects vs ids, the solve step and threshold rows
at run level") played one turn deep (`@hpb0.01`) on the headline setting,
sequences 0-249, against the 10-29 net's one-turn headline file (15 min at
3 threads): clears 0.636 vs 0.688 (-0.052, se 0.035; train -0.072, held-out
-0.032), end-HP 19.73 vs 22.21 (-2.48, se 1.28), HP at the boss 58.5 vs
59.8 (209 reach it in both). Deaths at the boss 65 vs 52 (the Guardian 31
vs 26, Hexaghost 28 vs 18), elsewhere alike: the whole gap is boss deaths. Against lean-thr s1's re-rank
file it is +0.056 (se 0.036): lean s1 sits between the 10-29 net and the
newer nets. Only 2 of 250 sequences pick the same cards (each net chooses
its deck with its own sims), so pairing by sequence buys little and the se
is ~2.5x a cell read's.

Reading. The solve step, worth nothing on the cell gauntlet (+0.001 clears,
-0.2 HP, 3 seeds), looks worth ~0.05 clears / ~2.5 HP once rewards are in
the loop, in the direction the headline re-rank suspected, but at 1.5-2 se
on one seed it is a lead, not a result. The mechanism would be the chooser:
its sims are played by the same net, so a net that mis-prices some card a
little picks differently 248 times out of 250 and the small per-fight
difference compounds through the deck. The three seed twins (lean s101 /
s201 vs the 10-29 recipe s101 / s201, 0063, light, ~1 h) pool to a 3-pair
estimate (se ~0.02 clears): -0.04 or more at >= 2.5 se = the solve step
carries part of the headline lead, which is evidence against the approach
review's decision 7 (drop the solver from training) as it stands and would
move "a solve-step-on twin of a newer recipe" up; within +-0.02 = not the
solve step, and the re-rank's gaps are the other recipe changes plus deck
noise. Either way the headline's deck noise (~0.035 clears per 250-sequence
pair) is now a measured number: run-level recipe reads need 3 seeds x 250
sequences to see 0.04.

## Survival-score arms: fail (owner's design; 0059l8a / 0059l8b; read 00:30 2026-11-03, manager caf615f4)

The two `lean-surv` arms (`docs/specs/survival-score.md` "The experiment",
folded 2026-11-03: the net predicts HP lost from now as a histogram, search
scores a win as c + w x end HP / 100, c = 1.0, w = 2.0; `lean-thr-s*` plus
`hp_loss`, `no_death: false`) trained two rounds each (s1
`runs/2026-11-02-lean-surv-s1-r2-aa67556`, s101
`runs/2026-11-02-lean-surv-s101-r2-694def8`) and played run-HP one turn
deep, 2000 pairs against the heuristic (`results/ladder/runhp/0039.json`,
`0040.json`). Against the pre-registered bars:

| | s1 | s101 | bar |
|---|---|---|---|
| run-HP vs heuristic (bare) | +0.03 [-0.48, +0.55] | -0.28 [-0.77, +0.20] | |
| saved vs `lean-hpw2` bare (0006 -2.89, 0007 -2.54) | +2.93 | +2.26 | >= 1.0 mean, each > 0: **pass** |
| saved vs `lean-hpw2@hpb0.01` (0026 +0.79, 0027 +0.81) | -0.75 | -1.09 | manager's added bar, beat the bonus: **fail** |
| deaths per 2000 vs the bare control | +18 | +9 | <= +20: pass (s1 close) |
| tight2 held-out | 0.452 (control 0.518) | 0.447 (control 0.509) | within 0.02: **fail** (-0.065 / -0.062) |

Where the HP goes (0039 / 0040 slices): hallways -0.37 / -0.37 (s101 train
hallways -0.76), elites +0.78 / +1.3, bosses -2.6 / -4.1 (wide). The arm's
win rate on run-HP fights is 0.976-0.979 against the heuristic's 0.984; the
bare `lean-hpw2` nets win 0.983-0.985.

A play-time c sweep (`@sc2`, `@sc4`; run-HP 2000 pairs, by hand, 1 min
each; files kept out of the ladder index): s1 +0.07 / +0.16, s101 -0.11 /
+0.08 HP vs the heuristic, wins 0.976-0.981. The c knob moves nothing: no c
gets within 0.6 HP of the bonus controls, and the win rate stays below
them.

Reading. The learned HP price does what the constant search bonus does,
less well: it saves ~2.6 HP per fight over a bare net (the bonus saves
~3.5), and it buys that HP with wins: the arm loses 0.06 of a win on tight2
held-out and ~1 death per 200 run-HP fights, where the bonus costs no
wins. The histogram head trains (val MSE 1.84-1.85 in HP units against
2.05 at epoch 1), so the net sees HP lost; the loss is in what the rule
does with it: a per-state price from a net that is wrong by ~1.4 HP rms
is noisier than a flat 0.01 per HP, and search follows the noise. By the
spec's rule the arms fail; the survival score is a null as an HP lever,
and use (d) of the run-value plan (the survival leaf) closes with it (it
needs a survive net that at least matches the bonus). Not fed Nob: elites
are the arm's best slice (+0.8 / +1.3 HP). What the result changes: the HP
price stays the constant end-HP bonus (`@hpe0.01`) in the product; a
state-dependent price, if one comes, comes from the fitted run value, not
from a trained head. The engine-next landing this gated went ahead.

## Seed twins of the solve step on the headline: not shown on three seeds (headline re-rank's cheap check; 0063; read 00:20 2026-11-03, manager caf615f4)

The 10-29 recipe without the solve step against the 10-29 recipe with it,
same seed, one turn deep (`@hpb0.01`) on the headline setting, sequences
0-249 per pair: s1 from 0061 (`rerank-lean-s1-r2-...` against the one-turn
control), s101 and s201 from 0063
(`results/gauntlet/rerank-{lean-s101-r2,net1029-s101,lean-s201-r2,net1029-s201}-hpb0.01-starter-simboss.json`,
62 min at 3 threads for the four). Paired by sequence (end-HP 0 on a
death, as the protocol):

| pair | clears lean - with | end-HP | boss deaths lean / with |
|---|---|---|---|
| s1 | -0.052 (se 0.035) | -2.48 (se 1.28) | 65 / 52 |
| s101 | +0.028 (se 0.037) | +1.18 (se 1.48) | 58 / 67 |
| s201 | -0.072 (se 0.035) | -3.44 (se 1.32) | 53 / 49 |
| pooled (3 pairs) | **-0.032 (se 0.021, z -1.5)** | **-1.58 (se 0.79, z -2.0)** | |

The pre-registered rule asked for -0.04 or more at >= 2.5 se to say the
solve step carries part of the headline lead, or within +-0.02 to say it
doesn't; the pooled estimate sits between. Two seeds lose without the
solve step and one gains, so the s1 lead was partly that pair's deck
noise (1-2 of 250 sequences pick the same cards per pair, as before). What
can be said: at run level the solve step is worth at most ~0.07 clears and
~3 HP (2 se), most likely ~0.03 / 1.6 HP, and on cell decks nothing.

Reading. This neither rescues nor sinks the approach review's decision 7
(drop the solver from training): a ~0.03 effect at run level would be the
solver's whole worth, and 3 more pairs (~3 h light) would halve the se to
~0.015 and settle the +-0.02 question. Not queued: the decision is the
owner's, and the training rule gives training CPU only to something new to
learn. The rules version (over the golden games) did not change at the
landing, so the solved DB still replays; the solvedb fingerprint over the
engine sources did, so its cached states are not reused by the new
module (docs/engine-next.md). Listed For the owner with the cost. The
headline re-rank's gaps (data40k -0.056 and the rest) are therefore mostly
other recipe changes plus the deck noise now measured twice (~0.035
clears per 250-sequence pair).

## Line step: the stepped player makes the committed-line player's decisions exactly, at 0.70 of its search cost (line-step.md step 3; probe 01:40 2026-11-03, manager caf615f4)

`scripts/analysis/line_probe.py --compare` played 20 held-out elite and boss
fights (5 each of Gremlin Nob, Lagavulin, Slime Boss, Three Sentries,
`depth_paired.fights`) twice with the product net at the product's two-turn
settings and the per-turn seed: once searching every decision (stage 1,
`--line-seed`), once stepping each uncut tree's principal line
(`--step-line`); single-threaded, 110 s in all
(`results/depth/line-step-compare.json`).

| | |
|---|---|
| fights with identical action sequences | 20 / 20 |
| agreement off cut decisions | 1.0000 (526 of 526 compared) |
| decisions | 527 both; 163 searched when stepping (31%) |
| cost ratio stepping / stage 1 | nodes 0.704, leaves 0.681, wall 0.693 |
| the spec's bars | agreement >= 0.99: **pass**; nodes + leaves <= 0.65: **missed** (0.69-0.70) |

Reading. The identity claim holds exactly: with one sample seed per turn,
re-searching the chosen child rebuilds the first tree's subtree, so
stepping the line changes no decision (526 of 526, outcomes equal in all
20 fights). The saving is smaller than the first-tree share (59% of a
turn's time in the earlier probe) suggested: the line stops at every
chance node, and Ironclad turns draw mid-turn often (Shrug It Off, Pommel
Strike, Battle Trance and the like), so 163 searches serve 527 decisions
instead of one per turn (~146 turns): about one re-search per turn plus
one more every eight turns. Continuing the line through a listed chance
node into the realised outcome (the spec's non-goal) would take some of
the remaining 0.70 -> 0.60; sampled draws (large events) can't be
continued. What the result changes: the bar of 0.65 came from the review's
estimate, not from correctness; a 30% cut of every two-turn read at zero
change in play is taken (decisions "Line-step probe: identity exact, cost
0.70"), and the reads of step 4 decide the play mode.

## Line step on the headline setting, fixed n 250: level with plain two-turn play at about half the wall time; the stepped player is the two-turn play mode from now (line-step.md step 4; 0064 + 0065; read 07:45 2026-11-03, manager 691c5c04)

Step 4a (0064, cells 0-49, 3 threads, 38 min): `--line-seed --step-line`
reproduces the stage-1 committed-line file (`net1029-hpe0.01-two-line-a.json`)
row for row: 544 floors, 0 differences in encounter, won or hp_end; clears
0.66 in both. (Both files were played from 7adb302, before the margin-0 tie
fix 9780a94; that fix changes a tie case which did not occur in these rows.)

Step 4b (0065): the stepped product player on the headline setting (starter
deck, sim rewards, sim-boss), sequences 0-249, paired by sequence against
the headline control (`net1029-hpe0.01-two-starter-simboss.json`, same
sequences): clears 0.836 vs 0.852 (-0.016, se 0.020; train 0.000 (0.028),
held-out -0.032 (0.030)); end-HP 29.05 vs 29.00 (+0.04, se 0.80); HP at the
boss 64.7 vs 65.2 (238 reach it in both); floors won 10.76 vs 10.78. HP lost
per floor is within noise on every floor (largest: the first elite, +0.40,
se 0.31). Reward picks 2495 of 2725 identical; 31 of 250 sequences identical
in every row (mixed depth: 160), as expected, since a shared sample seed
per turn changes which draws follow. Deaths: boss 33 vs 27 (Hexaghost 14 vs
9: won 0.831 vs 0.892 per arrival, 83 arrivals each; the Guardian 17 vs 16;
Slime Boss 2 vs 2), elites 6 vs 7, hallways 2 vs 3. Wall time 69.5 min at 3
threads (peak 3.95 GB) against 127-128 min at 2 threads for each full-depth
half of the control and 75 min at 3 threads for mixed depth on the same
sequences (read there as ~30% saved): the probe's 0.70 holds or better. The
hand-over's 142-178 min estimate was the cell gauntlet's pace (155-171 min
per 250 at 3 threads), not the headline's.

Verdict by the cost-saver rule (level = end-HP within +-1 HP and clears
within +-0.02): level, pass. Sceptical notes: the clears difference sits at
0.8 of its bar and all of it is Hexaghost deaths on the held-out half (5
deaths, about 1 se of a per-arrival rate); the stage-1 cell read of the same
decisions went the other way (+0.024 clears, +0.60 HP), so the two reads
together say "level", not "a Hexaghost cost". Nothing in the mechanism
singles out Hexaghost: the stepped player makes the committed-line player's
decisions exactly (step 4a), and the committed line differs from plain
two-turn only in sharing one sample seed across a turn's searches. If the
500-sequence file shows Hexaghost deaths again, re-read by boss.

Consequences (decisions "Line step is the two-turn play mode"):
`--line-seed --step-line` is the play mode for two-turn reads and the
product's play flags (facts how/two-turn-search, yardstick/cost-savers,
product/net; `configs/product.json`). A control played without the flags
needs `--vary line_seed --vary step_line` under `--against`. The 0.804
headline number stays until the stepped file holds sequences 250-499 too
(job 0066 adds them, ~70 min) and becomes the control. The two-turn
self-play round (L6) uses the stepped player as its game generator.

## Line step on the headline setting, all 500 sequences: level; the stepped file is the headline control, 0.834 clears (cheap-depth lane; 0066; read 13:05 2026-11-03, lanes f1fb0f59)

0066 added sequences 250-499 to the stepped file
(`net1029-hpe0.01-two-line-step-starter-simboss-a.json`, now 500
sequences, clear 0.834). Paired by sequence against the plain two-turn
control (`net1029-hpe0.01-two-starter-simboss.json`, 0.804), same setting
and seed 20261101:

| sequences | clears stepped | clears plain | clears diff (se) | end-HP diff (se) |
|---|---|---|---|---|
| 0-249 | 0.836 | 0.852 | -0.016 (0.020) | +0.04 (0.80) |
| 250-499 | 0.832 | 0.756 | +0.076 (0.026) | +0.77 (0.84) |
| 0-499 | 0.834 | 0.804 | +0.030 (0.017) | +0.41 (0.58) |

HP at the boss 64.1 vs 64.3 (464 reach it in both); floors won 10.75 vs
10.71. Deaths by boss over 500: Hexaghost 29 vs 29 (the 0-249 half's
14 vs 9 reversed on 250-499: 15 vs 20), the Guardian 28 vs 35, Slime Boss
5 vs 8. The earlier read's Hexaghost worry does not repeat.

Verdict by the cost-saver rule (end-HP within +-1 HP, clears within
+-0.02): end-HP level; clears +0.030 sits above the band on the good side
at 1.8 se, so level, not a gain. By the job's note the 500-sequence
stepped file is the headline control (`configs/product.json`
`headline_control`, fact yardstick/headline-control) and the product's
headline number is 0.834.

Sceptical notes. The two halves disagree by 2.8 se (-0.016 vs +0.076), and
the swing is in the plain control, not the stepped player: stepped clears
0.836 and 0.832 by half, plain 0.852 and 0.756. Other players are flat
across the halves (one turn 0.688 / 0.672, heuristic 0.532 / 0.536), so
250-499 is not a harder set of decks. Both control halves were played by
the same unpinned code at the same time (0059l7r3b39a / b39b, 2 threads,
2026-11-02 12:11-14:23), so no code change lines up with the split;
discordant sequences on 250-499 are 32 stepped-only clears against 13
plain-only (on 0-249, 11 against 15). Read as chance in the control's
second half until a mechanism shows up: the old 0.804 headline number was
probably about 0.03 low, which also shrinks the two-turn lead over one
turn less than it seems (+0.154 clears over 0.680 with the new control,
not +0.124). Nothing built on 0.804 changes direction. Wall time: 0066
took 150 min for 250 sequences at 3 threads, twice the 0-249 half's 69.5
min, because 0067 (two-turn games, 3 threads) ran beside it from 08:14;
the cost ratio stays the 0-249 measurement's.

## Sampled-draw leaf screen: fails both bars, no regret gain at 3-4x the cost; the leaf stops here (cheap-depth lane; draw-leaf.md step 3; run 14:20 2026-11-03, lanes f1fb0f59)

One-turn search with the product net @hpb0.01 at the 448 exact puzzles of
horizon 1 or more (`data/bench/puzzles.json`), plain and with the draw
leaf `@dl<k>` (end-of-turn leaves scored at the next decision after k
sampled draws, common random numbers; docs/specs/draw-leaf.md), one
thread (`scripts/analysis/draw_leaf_screen.py`,
`results/probes/draw_leaf_screen.json`):

| arm | regret | horizon 1 | horizon 2+ | gain vs plain (se) | time vs plain |
|---|---|---|---|---|---|
| plain | 0.0174 | 0.0149 | 0.0233 | | 1.0 (0.23 ms) |
| @dl1 | 0.0173 | 0.0142 | 0.0244 | +0.0002 (0.0017) | 3.2x |
| @dl2 | 0.0185 | 0.0159 | 0.0244 | -0.0010 (0.0012) | 3.6x |
| @dl4 | 0.0182 | 0.0158 | 0.0238 | -0.0008 (0.0011) | 4.3x |

Bars (spec and review step A): regret down at least 0.01 at no more than
1.5x plain's time. Fails both: no k moves regret (every gain within one
se of zero, against a bar six to ten se away), and every k costs over 3x.
By the review's pre-registered gate the leaf stops: no cell read, no CPU
spent on it.

Why, as far as this read goes. The leaf is active (time triples, picks
change on some puzzles), so this is not a wiring fault. Two-turn search
cut regret on the same puzzle set to about a third (0.0189 -> 0.0061 for
the then-champion, results doc "Two first checks from the review"), so the
puzzles do reward depth; seeing the next hand alone recovers none of it,
even at horizon 1, where the next hand decides the fight. So two-turn's
gain comes from searching the second turn's play (what to do with that
hand), not from the net valuing a drawn hand better than a paused one;
the review's "net fits post-draw states better" (MSE 0.011 vs 0.092) does
not turn into better choices between this turn's options. Caveat: puzzles
are small endgames (0.23 ms per search), so the cost ratio may differ
mid-fight, but no cost would rescue a zero gain. The code stays (off by
default, `@dl<k>`), for a "draw plus one monster step" variant if a later
lane wants the missing-hit half of the question.

## Two-turn self-play round: both arms fail the protocol; the outcome-label family closes (two-turn-round lane; 0067-0071; read 15:10 2026-11-03, lanes 42d5e5e2)

The one two-turn self-play round (decisions "Two-turn round spec
confirmed"): the 10-29 net burst-fine-tuned on 3000 elite and boss games
played by the stepped two-turn product (0067, 5.5 h at 3 threads; 0068
the 300 validation games), seeds 1 and 101, and a control arm fine-tuned
the same way on the same specs played one turn deep (0071). Each read one
turn deep @hpb0.01 on the cell gauntlet `--against
results/gauntlet/net1029-hpb0.01.json` (protocol, H1 +1.5 HP). Files
`results/gauntlet/{twoturn-s1,twoturn-s101,oneturn-ctl-s1}-hpb0.01.json`.

| arm | verdict | end-HP diff at stop (se) | at all played (se) | clears arm / ctl (paired z) | held-out / train half |
|---|---|---|---|---|---|
| twoturn-s1 | fail n 120 | -0.72 (0.86) | -1.37 (0.83), n 150 | 0.675 / 0.617 (+1.94) | -2.57 / -0.17 |
| twoturn-s101 | fail n 119 | -0.45 (0.77) | -1.02 (0.70), n 150 | 0.613 / 0.613 (0.0) | -1.80 / -0.24 |
| oneturn-ctl-s1 | fail n 179 | -0.07 (0.64) | -0.05 (0.58), n 200 | 0.609 / 0.598 (+0.50) | -0.65 / +0.55 |

Pairing corr 0.92-0.95. The +1.5 HP the round was looking for is outside
every arm's interval (s1's upper 95% bound +0.97 at n 120); both teacher
arms point below zero and below the one-turn control arm. The fails are
not early-stop luck: playing on to n 150 moves both two-turn arms further
down.

Why, as far as this read goes:
- **The fine-tune learned little.** Validation MSE is at its best by
  epoch 1-2 (s1 0.153 -> best 0.151; s101 0.153 -> 0.151; control 0.147
  -> 0.144) and early stopping ends after 5-9 epochs: the outcome labels
  of a stronger player carry little the net can fit beyond what it
  already predicts, so the weights move a little and mostly in noise.
- **Where it hurts is the boss.** At matched starting HP the two-turn arms
  lose +1.33 and +1.41 HP more than the control on the boss floor (n
  49-51), the control arm +0.89; elites are mixed (-0.65 / +0.39), other
  floors level (+0.04 / +0.03, n ~810). Bosses are where a net-valued
  leaf matters most one turn deep. A plausible mechanism, not tested: the
  labels value states under the two-turn player's continuation, which is
  better than what a one-turn player gets from them, so the fine-tuned
  net is optimistic about states it cannot exploit at one turn. Testing
  it would need the two-turn read the stop rule skips.
- **s1's extra clears are not a gain.** s1 clears 10 sequences the
  control loses and loses 3 (z +1.94, under 2, and s101 shows 6 / 6), but
  where both clear it ends 2.1 HP lower: the same boss HP leak.
- **Held-out halves are worse** (-2.6, -1.8 against -0.2 on the train
  half), each half's se about 1.2, so a weak sign of fitting the training
  decks rather than play.

What it changes: the stop rule fires (a null on both seeds; no two-turn
confirmation, no second round). The outcome-label training family closes
on this dev machine (decision/two-turn-self-play), and with it the "untried
exit" in cause/teacher-equals-student: a stronger teacher's outcome labels
do not lift the net either; the gains stay with search and the run layer.
Cost about 20 thread-hours (0067 16.6, 0068 2.0, arms 0.6). The runs are
kept under `runs/2026-11-03-{twoturn-s1,twoturn-s101,oneturn-ctl-s1}-*`.

## Rest probe with 64 fights and a 2-se margin: null, the rest probe closes on this setting (run-decisions lane; 0081; read 23:30 2026-11-03, lanes 90dc0150)

`--rest sim --rest-fights 64 --rest-margin 2` against the one-turn
headline control (10-29 net `@hpb0.01`, starter + rewards sim + sim-boss,
`--vary rest_choice`), early-stopped by the protocol at n 50: fail (the
test accepted "no +1.5 HP gain"). Paired end-HP -0.10 (sd 0.7 per
sequence, se 0.10), clears 0.720 vs 0.720, HP at the boss 58.8 vs 59.6.
Train and held-out halves alike (0.640 / 0.800 each, level in both).
The run took 11 minutes against a 60-minute estimate because of the stop
at n 50, not a fault.

Why: the margin did what it was for and removed the winner's curse (the
11-02 read at 16 fights and no margin upgraded in 10 of 50 and lost 2
clears, -1.22 HP); now the upgrade beats heal by 2 se in only 2 of 50
sequences, both Uppercut+ before Hexaghost. Sequence 1 upgraded at 68 HP
instead of healing to 80 and ended the boss at the same 34 HP, so that
upgrade was worth its 12 HP; sequence 35 upgraded at 53 instead of
healing to 77 and ended 5 HP lower (32 vs 37), both cleared. 47 healed
(rows match the control exactly) and one died at Lagavulin first. So on
this setting, with its only rest right before the boss, heal is the right
call nearly always and the rest decision is worth about 0 HP; even at 500
sequences the ~4% that upgrade bound any gain far below +1.5 HP, so no
fixed-n replay is worth its CPU. A rest decision can only pay where rest
sites sit earlier, before fights the upgrade helps more than the HP: that
needs the mini-run headline (a map with rest sites mid-act), which is the
lane's next step. If rest sites come back there, use 64 fights and the
2-se margin; the plain rule over-picks.

## Mini-run control: 0.900 clears, the mid-act heal carries most of it (run-decisions lane; 0087; read 13:10 2026-11-04, lanes 3edeb150)

The 10-29 net `@hpb0.01` one turn deep on the headline setting plus
`--elite-offers 2 --mid-rest 5` (spec `docs/specs/mini-run.md`), sequences
0-499, against the one-turn headline control
(`results/gauntlet/net1029-hpb0.01-starter-simboss.json`): clears 0.900
vs 0.680 (+0.220, se 0.020), HP at the boss 73.7 vs 59.4 (447 reach
both). Train 0.884 vs 0.660, held-out 0.916 vs 0.700: the same shift in
both halves. 116 sequences clear only on the mini-run, 6 only on the
headline. Deaths by floor move from 31 / 15 / 107 at floors 8 (second
elite), 9 and the boss to 4 / 2 / 40; Guardian and Hexaghost still take
36 of the 50 deaths.

The clear rate sits beyond the note's +-0.08 band, so before reading the
probes I checked where it comes from. It is the setting, not a fault:
- The mid-act heal fires on 496 sequences (all that win floor 5) and adds
  20.7 HP on average (0.4% at full HP already). Floor 6 starts at 73.2 vs
  52.5 HP, floor 8 at 68.0 vs 49.0; the boss rest's cap narrows it to
  71.8 vs 59.4 at the boss.
- Every won elite pays its second offer (988 extra offers); the sim
  chooser takes 62% of them against 86% of first offers, so it already
  declines cards that don't help a fuller deck. Picks per run 9.8 vs 8.5.
Which of the two carries the +0.22 isn't separated (no heal-only run);
the HP gap at floors 6-9 suggests the heal does most of it.

What it changes: the mini-run is an easy setting (0.90 clears), so clears
have little room and the elite probes lean on paired end-HP, which still
varies (the boss leaves a wide HP spread). An elite now pays a card and
the first elite sits right before a heal, so skipping is two-sided here,
as the spec meant. 0088 (elite skip) and 0089 (skip under 40 HP) read
against this file by the protocol.

## Elite skip on the mini-run: open at n 500 on end-HP (+0.99, se 0.86), but +0.054 clears at about 4 se; the elite's card doesn't pay its HP (run-decisions lane; 0088; read 13:55 2026-11-04, lanes 3edeb150)

`--elites skip --against` the mini-run control (0087,
`results/gauntlet/net1029-hpb0.01-starter-simboss-mini.json`, `--vary
elites`), 10-29 net `@hpb0.01` one turn, sequences 0-499. The protocol
stayed open through all 500 sequences: paired end-HP +0.99 (se 0.86;
train +0.89, held-out +1.10), short of the +1.5 HP bar and not rejected
either, so by the charter it is no go. Clears 0.954 vs 0.900 (+0.054, se
0.014), the same in both halves (train +0.052, held-out +0.056); 40
sequences clear only when skipping, 13 only when fighting. HP at the boss
78.8 vs 71.8 (490 reach both), boss deaths 22 vs 40, and the elite floors'
own deaths (4 + 4) are gone. The run took 44 minutes (estimate 40).

Why the two units disagree: end-HP counts a death as 0, so it is the
clear gain diluted by what the extra cards buy in the runs both clear.
Where both clear (437), skipping ends 0.41 HP lower: the second elite
offer (8.7 vs 9.8 picks per run) is worth a little at the boss, but far
less than the 7 HP that skipping both elites carries into it. The +14.0
HP ceiling on the headline (`measurement/elite-skip@headline`) shrank to
+1.0 because the mid-act heal refills most of the first elite's cost and
the card offsets part of the second, not because fighting became right:
on clears, the headline's unit (`decision/headline-unit`), skipping still
wins by about 4 se.

What it changes: on the mini-run an elite is still a net loss, so it has
not yet become the two-sided choice the spec aimed at; a single extra card
is too small a payoff against the second elite's ~15 HP three floors
before the boss. A path rule that skips under some HP can't beat "skip
always" here by much, which 0089 (skip under 40 HP) tests. A setting where
an elite pays more (a relic, max HP, a rare card) is the navigator's call
(the spec's alternatives); the lane's own probes stop at their one read.

## Skip under 40 HP on the mini-run: fail at n 50, the rule never fires there; the elite and path probes close, all three run-decision probes are no go (run-decisions lane; 0089; read 14:05 2026-11-04, lanes 3edeb150)

`--elites hp --elite-hp 40 --against` the mini-run control (`--vary
elites --vary elite_hp`), one turn, sequences 0-49: the protocol failed
at its first look, n 50, on rows identical to the control (paired end-HP
0.00, clears 0.980 each). The rule skipped none of the 100 elite floors:
no sequence among the first 50 reaches an elite under 40 HP on the
mini-run. Over the control's 500 sequences only 20 of 996 elite arrivals
are under 40 HP (6 at floor 5, 14 at floor 8), against 136 on the
headline (130 at floor 8, where the rule took its +1.53 HP,
`measurement/elite-skip@headline`). The mid-act heal after the first
elite is what lifts floor 8's arrivals (68.0 vs 49.0 HP on average).

The fail is not an artefact of the early stop: with 20 firing floors in
500 sequences, even a +20 HP swing on each would add under +1 HP on
average, below the +1.5 bar, so no fixed-n replay is worth its CPU.

What it closes: the charter's three probes are all no go. The rest probe
had nothing to win where the only rest sits before the boss (11-03 read,
`measurement/rest-probe@headline`); on the mini-run, skipping every elite
is open at +0.99 HP (se 0.86) but wins clears by +0.054 (about 4 se,
`measurement/elite-skip@mini-run`), and the HP rule doesn't fire. The
lane's stop rule is reached. The finding worth carrying: on both settings
an elite costs more than it pays, so run-level choices stay one-sided
until the run layer has a bigger elite payoff (relics or max HP, the
mini-run spec's alternatives, both engine work) and rest sites with a
choice before hard fights. Total lane CPU about 10 thread-hours (0081 and 0087-0089).

## Deck-matched reads one turn deep: paired end-HP sd 20.6 -> 13.4 and 10.1, the mean kept; go (cheaper-reads lane; 0099-0100; read 14:45 2026-11-04, lanes bc9c6ab7)

`gauntlet.py play --match` (docs/specs/deck-matched-reads.md) replays the
one-turn control's recorded card picks (`results/gauntlet/net1029-hpb0.01-starter-simboss.json`)
into another net's run, so only the fighter differs. Two known nets, one
turn deep, sequences 0-249, fixed n, paired with the control by sequence,
beside the same nets' unmatched files (`rerank-*-hpb0.01-starter-simboss.json`):

| net | read | end-HP mean | paired sd | corr | clears diff | clears sd | HP@boss sd (both reach) |
|---|---|---|---|---|---|---|---|
| burst8hp2-s1 | unmatched | -5.64 | 20.6 | 0.52 | -0.148 | 0.59 | 17.9 (n 177) |
| burst8hp2-s1 | matched | -5.36 | 13.4 | 0.79 | -0.128 | 0.41 | 12.3 (n 197) |
| net1029-s101 | unmatched | -1.42 | 20.6 | 0.54 | -0.056 | 0.56 | 16.8 (n 208) |
| net1029-s101 | matched | -0.17 | 10.1 | 0.89 | -0.012 | 0.34 | 8.1 (n 217) |

Matched picks: 2374 of 2402 and 2425 of 2455 card floors; the rest come
after the control's own death, where the run's chooser decides. The
charter's bar (go if the sd falls toward 12, fail above ~18) is passed on
both nets: variance falls 2.4x and 4.2x, so a +1.5 HP effect decides at
roughly a third of the sequences. The larger gain on the same-recipe net
is expected: the closer the fighters, the more of the leftover variance
was the picks. The means agree within 1 se of the unmatched reads
(-5.6 vs -5.4; -1.4 vs -0.2), so on these nets the chooser divergence was
noise, not effect. Deaths by type: the matched burst8hp2 loses fewer
elites (24 vs 40) and more bosses (68 vs 56), since it now carries the
control's (better) decks into them.

Cost: each matched 250-sequence read took 1.5-2.5 minutes at 2 threads;
one turn deep the unmatched read's time is mostly the sim chooser's option
fights, which a matched floor skips. Two turns deep the fights dominate.

What it changes: a fighter-only read (search flags, a new net's play)
can be matched to the control; a chooser or run-decision read can't (it
holds the control's picks), and a new net's read matched measures only its
fighting, not its picking. The two-turn confirm (0107, the heuristic
fighting with the product's picks on 500-749, beside 0090's unmatched
anchor) decides whether matched reads become the default.

## Boss-replay score: 1.17-1.28x on end-HP sd, 1.25-1.52x on clears; not adopted (cheaper-reads lane; 0101-0105; read 14:50 2026-11-04, lanes bc9c6ab7)

`boss_replay.py play --hp arrival --seeds 8` (docs/specs/boss-replay-score.md)
replays each boss-reaching sequence's boss 8 times at its arrival state,
one turn deep by the file's own player; `pair` scores each sequence by the
mean replay result (0 if it died earlier). Replay seed 0 reproduced the
real boss win and end HP in every row (447, 191, 225 rows), so the
rebuild is exact. Against the one-turn control, sequences 0-249:

| pair | sd clears | sd replay win | ratio | sd end-HP | sd replay HP | ratio |
|---|---|---|---|---|---|---|
| burst8hp2 unmatched | 0.586 | 0.470 | 1.25 | 20.6 | 17.6 | 1.17 |
| net1029-s101 unmatched | 0.557 | 0.426 | 1.31 | 20.6 | 17.4 | 1.18 |
| burst8hp2 matched | 0.410 | 0.321 | 1.28 | 13.4 | 11.4 | 1.18 |
| net1029-s101 matched | 0.341 | 0.225 | 1.52 | 10.1 | 7.9 | 1.28 |

The bar (adopt at a 1.4x cut) is met only by the matched same-recipe pair
on clears; on end-HP, the protocol's quantity, no pair reaches it. Means
stay put (-5.6 vs -5.6, -1.4 vs -1.2 HP), so the score is unbiased, just
not much tighter: most of the paired variance is in which sequences reach
the boss and with what HP, not in the one boss fight's luck. A 1.18x sd
cut is 1.4x less variance, while 8 boss replays two turns deep would cost
more than the sequences they save. Not adopted; the protocol keeps real
end-HP and clears. If clears ever become the tested quantity of a matched
read, the 1.52x is worth a second look.

## Depth-headroom anchor: the heuristic two turns deep with the product's picks is 9.3 HP and 0.200 clears behind the product, and 5.4 HP behind the net one turn deep (depth-headroom lane; 0090; read 15:20 2026-11-04, lanes c4b0f7e7)

`gauntlet.py play heuristic --two-turn --line-seed --step-line --chooser
<10-29 net @hpe0.01>` on the headline setting, sequences 500-749 (decision
"depth-headroom anchor: the heuristic fights, the product chooses, 250
sequences"), read at fixed n 250 against the product's own file on the same
sequences (`net1029-hpe0.01-two-line-step-starter-simboss-500.json`). Only
the leaf differs; depth, play mode and chooser are equal. Floor-1 picks
agree on 245 of 250 sequences (the 5 others: the chooser's sim fights
follow the fighter); all picks agree on 54, since decks drift once HP does.

| 500-749, n 250 | clears | end-HP |
|---|---|---|
| heuristic two turns, product's chooser | 0.548 | 16.5 |
| product (net two turns) | 0.748 | 25.9 |
| net one turn (@hpb0.01) | 0.676 | 21.9 |

- Product minus anchor: +9.32 end-HP (se 1.09), +0.200 clears (se 0.031);
  train +9.22 (se 1.38), held-out +9.42 (se 1.70): the leaf's worth doesn't
  depend on the content half.
- Anchor minus the one-turn net: -5.41 end-HP (se 1.15), -0.128 clears
  (se 0.034). The net's leaf one turn deep beats the heuristic's two turns
  deep. The second turn adds +3.92 end-HP (se 1.20) with the net leaf on
  these sequences (+6.14 on 0-499, `measurement/headline@two-turn`); the
  500-749 product clears 0.748 against 0.834 on 0-499, so these sequences
  are harder or that half was lucky.
- By fight type (paired floors both reached; HP lost heuristic / product):
  easy 0.43 / 0.22, hard 2.69 / 1.81, elite 20.4 / 16.1 (+4.35, se 0.37;
  wins 0.950 / 0.982), boss 34.0 / 35.5 with wins 0.663 / 0.851. The boss
  HP figure is censored (the anchor arrives 11.5 HP lower, 54.2 / 65.7, and
  dies more): the boss gap is in wins, and arrival HP comes from the
  elites and hallways.
- Cost: 54 minutes at 3 threads against a 150-minute estimate; the
  heuristic leaf is cheap beside the net's, so a two-turn heuristic read
  costs about a third of the product's.

Why: two turns deep, the leaf still carries most of the edge; depth over
the heuristic leaf recovers less than the net's leaf adds at one turn. So
depth's gain rests on the leaf: a deeper search over the same net leaf has
room only where the leaf misjudges what the next turns decide, which is
what the elite replay probe (0093 rollouts, 0094 three turns) measures. It
also says a better leaf (a leaf-improvement lane) keeps a lever beside
depth. What it changes now: nothing alone (the note's rule); it frames the
elite-probe read, which stays the lane's checkpoint.

## Rollout leaf on the 237 decisive elites: -1.54 HP lost (se 0.46), at the 1.5 bar, but the gain grows with the control's own loss: selection on the outcome, not yet a read (depth-headroom lane; 0093; read 17:20 2026-11-04, lanes fc5c2804)

`depth_probe.py play --kind elite --arm rollout` (n 16 rollouts per legal
action, the product net as policy) on every floor-9 elite of the headline
control where the two-turn product lost 15+ HP (237 of 498), read with
`depth_probe.py read results/depth_probe/rollout-elite.json` against the
control's own columns.

| decisive elites | n | HP lost, control | HP lost, rollout | rollout - control (se) | wins control / rollout |
|---|---|---|---|---|---|
| all | 237 | 20.5 | 19.0 | -1.54 (0.46) | 0.954 / 0.954 |
| Lagavulin | 110 | 20.8 | 17.8 | -2.93 (0.65) | 0.955 / 0.991 |
| Three Sentries | 76 | 20.1 | 20.4 | +0.30 (0.75) | 0.974 / 0.934 |
| Gremlin Nob | 51 | 20.5 | 19.2 | -1.31 (1.07) | 0.922 / 0.902 |

- By the control's loss: 15-19 HP (n 118) -0.56 (se 0.53); 20-29 (n 105)
  -1.88 (0.70); 30+ (n 14) -7.36 (3.28). The rollout plays the same fight
  as the control on 24% of fights (same HP); the paired differences run
  from -12 to +10 HP (5th-95th percentile).
- Cost: 0.75 h wall at 3 threads (estimate 40 min), peak 0.99 GB.

Why it isn't a read yet: the fights were picked because the control did
badly on them (lost 15+ HP). Any other player that plays them differently
draws other luck and, on average, does better on exactly those fights,
whether or not it is stronger (regression to the mean). The gain rising
with the control's loss is that pattern, and it biases the decisive-fight
measure of the charter toward "go" for any arm that diverges (rollouts
here, three turns in 0094). The check is outcome-blind: play the rollout
on the other 261 floor-9 elites too (`--kind elite-rest`) and read all 498
(`read rollout-elite.json+rollout-elite-rest.json`), which no selection
biases; the decisive-elite figure stays a description. Three turns move to
the first 48 of all floor-9 elites (`--kind elite-all`, 22 of them
decisive) for the same reason (decision "depth-headroom: outcome-blind
elite reads"). Lagavulin's -2.93 at 4.5 se is the strongest lead; a real
gain there would show on the rest file's Lagavulins too.

## Mutated monsters, stage A, two turns deep at 200 x 4: the SharpHide repair holds, every verdict holds, and one stack is harder than its parts (goal1-yardstick; 0083; read 17:45 2026-11-04, lanes 15483a05)

Job 0083 widened the two-turn column of `results/mutate/a.json` from the
first 40 starts x 4 seeds to all 200 starts (134 elite, 66 boss) x 4 seeds
(`mutate_monsters.py play --players two --two-starts 200 --two-seeds 4
--threads 3`; 836 min wall at 3 threads, peak 4.16 GB; the 40 x 4 file is
kept as `results/mutate/a-40x4-backup.json`). Read with `mutate_monsters.py
read results/mutate/a.json`. Win change from the parent, paired by start
(se); heuristic and one turn on 8 seeds, two turns on 4; novelty two turns
= (two - heuristic) under the modifier minus the same on the parent,
computed from the same rows. Parent win: heuristic 0.995 / one 0.993 /
two 0.996 on elites, 0.621 / 0.667 / 0.716 on bosses.

| modifier | heuristic | one turn | two turns | verdict | novelty, one turn | novelty, two turns | repair (two - one) |
|---|---|---|---|---|---|---|---|
| hp0.8 | +0.081 (0.014) | +0.064 (0.012) | +0.051 (0.011) | easier | -0.018 (0.010) | -0.030 (0.010) | -0.013 (0.008) |
| hp1.25 | -0.087 (0.013) | -0.101 (0.015) | -0.085 (0.013) | harder | -0.013 (0.011) | +0.003 (0.013) | +0.016 (0.012) |
| str1 | -0.039 (0.008) | -0.051 (0.009) | -0.043 (0.010) | harder | -0.012 (0.008) | -0.004 (0.010) | +0.008 (0.007) |
| str2 | -0.076 (0.014) | -0.097 (0.016) | -0.087 (0.016) | harder | -0.021 (0.009) | -0.011 (0.010) | +0.009 (0.009) |
| metal3 | -0.033 (0.007) | -0.044 (0.009) | -0.043 (0.010) | harder | -0.012 (0.009) | -0.010 (0.009) | +0.002 (0.009) |
| ritual2 | -0.136 (0.021) | -0.174 (0.022) | -0.172 (0.023) | harder | -0.038 (0.011) | -0.036 (0.012) | +0.002 (0.012) |
| sharp2 | -0.160 (0.020) | -0.208 (0.022) | -0.155 (0.020) | harder | -0.048 (0.015) | +0.005 (0.014) | +0.053 (0.015) |
| metal4-hp0.85 | +0.016 (0.006) | -0.003 (0.008) | +0.009 (0.007) | easier | -0.019 (0.008) | -0.007 (0.008) | +0.011 (0.010) |
| ritual2-hp0.7 | -0.051 (0.016) | -0.070 (0.018) | -0.061 (0.017) | harder | -0.019 (0.010) | -0.011 (0.010) | +0.009 (0.011) |
| sharp2-hp0.9 | -0.097 (0.017) | -0.159 (0.020) | -0.091 (0.017) | harder | -0.062 (0.015) | +0.006 (0.012) | +0.068 (0.014) |
| metal4-hp0.75 | - | - | +0.029 (0.009) | easier | - | - | - |
| sharp1-hp0.9 | - | - | -0.022 (0.010) | harder | - | - | - |
| stack metal4-hp0.85 + sharp2-hp0.9 | -0.102 (0.019) | -0.193 (0.024) | -0.116 (0.019) | harder | -0.091 (0.016) | -0.014 (0.014) | +0.077 (0.016) |

Reading. (1) **Precision: the checkpoint's bar (two-turn se <= 0.02 on
every modifier) is met by 12 of 13 rows; ritual2 is at 0.023.** Its
effect is 7 se from zero and no verdict hangs on it, so the widening is
accepted as done (decision "goal1-yardstick: stage A two-turn table
accepted at ritual2 se 0.023"). (2) **No verdict flipped** against the
40 x 4 table: every modifier keeps its easier / harder sign, and the
two retuned pairs read as decision/mutated-pairs-retuned says
(sharp1-hp0.9 -0.022 near its parent; metal4-hp0.75 easier on bosses,
+0.098 (0.023), level on elites). (3) **The SharpHide repair is now
firm:** two turns deep the product's novelty cost on sharp2, its pair
and the stack is +0.005 to -0.014 (se 0.012-0.014), repair +0.053 to
+0.077 at 3.5-5 se; the 40 x 4 table had it at 1.2-2 se. It sits on
elites (sharp2 repair +0.085 (0.017)), where the one-turn net attacks
into the hide. (4) **Two exceptions to "within +-0.025 two turns
deep", both from bosses:** ritual2 -0.036 (0.012) and hp0.8 -0.030
(0.010); on bosses -0.081 (0.028) and -0.089 (0.028), on elites
-0.014 (0.011) and -0.001. Ritual's repair is ~0 (+0.002), so unlike
SharpHide it is not a horizon miss one more turn fixes. But the boss
rows are confounded by scale: the two-turn player's edge over the
heuristic on boss parents (0.716 vs 0.621, +0.095) shrinks whenever the
win rate moves away from the middle (hp0.8: 0.867 vs 0.862; ritual2:
0.326 vs 0.312; str2 0.462 vs 0.428, two-turn novelty -0.061 (0.027)),
easier and harder alike. A win-rate difference can't separate a novelty
cost from that compression; the HP-lost change agrees in direction
(ritual2 on bosses +7.9 heuristic, +9.6 two turns) but is ~1 se. So
ritual2's boss cost is a lead, not a result. (5) **Stacking:** the one
stack is harder than the sum of its parts, interaction -0.022 (0.009)
for the heuristic and -0.034 (0.015) two turns deep (2.3-2.4 se), mostly
elite (-0.032 (0.018) two turns). A first sign that stacks are not
additive; job 0092 (five stacks, two turns) is the stacking check that
decides it. (6) **What it changes:** the stage A part of the lane's stop
rule is met; the measurement fact is re-set from this table. Goal 1's
enemies rung reads on the product (two turns), as before, with Ritual on
bosses as the one modifier depth doesn't help.

## Rollout leaf on all 498 floor-9 elites: +0.67 HP lost (se 0.31), worse than two turns; the decisive-elite gain was regression to the mean; no go for rollouts (depth-headroom lane; 0108 with 0093; read 18:10 2026-11-04, lanes ed05eb9c)

`depth_probe.py play --kind elite-rest --arm rollout` (n 16 rollouts per
legal action, the product net as policy) on the 261 floor-9 elites of the
headline control the two-turn product lost under 15 HP on, read with the
237 decisive ones from 0093: `depth_probe.py read
results/depth_probe/rollout-elite.json+results/depth_probe/rollout-elite-rest.json`
(rollout minus the control's own columns, paired per fight). No selection
on the outcome biases the 498 together (decision "depth-headroom:
outcome-blind elite reads").

| floor-9 elites | n | HP lost, control | HP lost, rollout | rollout - control (se) | wins control / rollout |
|---|---|---|---|---|---|
| all 498 | 498 | 14.0 | 14.6 | +0.67 (0.31) | 0.974 / 0.966 |
| Lagavulin | 174 | 16.2 | 15.4 | -0.75 (0.55) | 0.966 / 0.983 |
| Gremlin Nob | 166 | 11.3 | 12.9 | +1.56 (0.57) | 0.970 / 0.946 |
| Three Sentries | 158 | 14.3 | 15.6 | +1.32 (0.47) | 0.987 / 0.968 |
| the 261 non-decisive | 261 | 8.0 | 10.7 | +2.69 (0.38) | 0.992 / 0.977 |
| of which Lagavulin | 64 | 8.3 | 11.2 | +2.98 (0.82) | 0.984 / 0.969 |

- Go rule (1.5 HP or more recovered per elite at 2 se): not met; the
  rollout leaf loses 0.67 HP more than two turns at 2.2 se, and wins
  drop 0.008 (se 0.009).
- On the non-decisive file the rollout is worse by a flat ~2.4-2.8 HP in
  every band of the control's loss (0-5 HP n 36: +2.83; 5-10 n 102:
  +2.71; 10-15 n 110: +2.35), as the decisive file was better by a
  rising amount: both halves are the same player drifting toward its own
  mean. The note's prediction (a rest-file loss near +1.5 HP beside the
  decisive -1.54) came true at +2.69: the decisive read was regression to
  the mean.
- Lagavulin, the strongest lead of 0093 (-2.93 at 4.5 se), shrinks to
  -0.75 (se 0.55) over all 174 and is +2.98 on its 64 non-decisive fights:
  no real gain there either.
- The rollout plays the same fight as the control (same HP and outcome) on
  31% of all elites (38% of the non-decisive).
- Cost: 42 min wall at 3 threads (estimate 50), peak 1.0 GB; lane total
  about 7.0 cpu-h of 12 before 0109.

What it changes: the rollout leaf (n 16, the product net as policy) is no
better than two-turn search on elites, so it doesn't get a boss probe or a
headline candidate; the charter's other arm, three turns on the first 48
of all floor-9 elites (0109, queued), decides the elite-probe checkpoint
alone. A likely why (not measured here): the play-outs follow the net (one
decision at a time), a weaker player than the two-turn search, so 16 of them
estimate the value of a weaker continuation, and with n 16 per action the
estimate is noisy enough to override good two-turn choices.

## Thread check: 8 threads take 0.599x the 3-thread wall time, at the bar; adopted only for a read that has the machine alone (cheaper-reads lane; 0095-0096; read 20:30 2026-11-04, lanes 40c7fd32)

The product two turns deep on the headline setting, sequences 0-99, once at
3 threads (0095) and once at 8 (0096), same pinned build:

| arm | wall | thread-min per sequence | peak | beside it |
|---|---|---|---|---|
| 0095, 3 threads | 74.9 min | 2.25 | 3.31 GB | 0083 (mutate, 3 threads) throughout |
| 0096, 8 threads | 44.9 min | 3.59 | 7.76 GB | 0092 (mutate, 3 threads) throughout |

Both files are identical row for row (100 of 100, clears 0.900), and equal
the headline control's first 100, so per-floor parallel play doesn't change
play. Each arm had one 3-thread job beside it the whole time, so the load
was comparable; other projects' load isn't recorded.

The ratio is 0.599 against a bar of 0.6: a pass at exactly its bar from
one timing each, inside any plausible timing noise, so it reads as "about
0.6", not as a clear pass. What it does show: 2.67x the threads buy 1.67x
the speed (63% parallel efficiency). Each
sequence costs 1.6x the thread-minutes and the job needs 2.3x the memory,
the binding limit (8.8 GB free to admit it, against the usual 3-5 GB). Two
3-thread reads side by side therefore finish more work per hour than one
8-thread read; 8 threads only win when a single read has the machine to
itself and its wall time gates the next decision. That is the charter's
"reads that have the machine" case, and it is how the result is adopted
(decision "Thread count for headline reads"): 3 threads stays the default,
8 threads (mem_gb 8) for a lone urgent read. The lane's goal, the CPU a
verdict costs, is not cut by threads; it moves only through deck-matched
reads (0107 pending).

## Three turns on the first 48 floor-9 elites: -0.75 HP lost (se 0.81), under the 1.5 bar; the decisive half's gain is again regression to the mean; no go, the depth family closes on this dev machine (depth-headroom lane; 0109; read 21:15 2026-11-04, lanes 096341b9)

`depth_probe.py play --kind elite-all --arm three --limit 48 --max-nodes
1600000 --threads 3` (the product, guarded, three turns deep) on the first
48 floor-9 elites of the headline control (sequences 0-47, outcome-blind:
22 decisive, 26 not), read with `depth_probe.py read
results/depth_probe/three-elite-all.json` (three turns minus the control's
own two-turn columns, paired per fight).

| floor-9 elites | n | HP lost, control | HP lost, three turns | three - control (se) |
|---|---|---|---|---|
| all 48 | 48 | 13.1 | 12.4 | -0.75 (0.81) |
| Lagavulin | 19 | 13.8 | 12.6 | -1.21 (1.47) |
| Gremlin Nob | 14 | 11.6 | 9.4 | -2.14 (1.56) |
| Three Sentries | 15 | 13.7 | 14.8 | +1.13 (1.03) |
| decisive (control lost 15+) | 22 | 19.3 | 16.5 | -2.82 (1.42) |
| non-decisive | 26 | 7.9 | 8.9 | +1.00 (0.77) |

- Go rule (1.5 HP or more recovered per elite at 2 se): not met. The
  point gain is half the bar at 0.9 se; the 2-se interval (-2.4 to +0.9)
  doesn't exclude the bar, but the charter's stop rule reads the point
  and the se, and a fight's worth of n more would not move a 0.75 mean
  past 1.5 at 2 se without a larger true effect than the decisive half
  suggests.
- The split repeats the rollout read's pattern: better by 2.8 on the
  decisive half, worse by 1.0 on the rest. Both halves drift toward the
  player's own mean, so the decisive gain is mostly regression to the
  mean; three turns are less bad than rollouts off the decisive half
  (+1.0 against +2.69), the one sign of a small real gain.
- Wins 48 of 48 for both; three turns play the identical fight (same HP)
  on 17 of 48.
- Search cut by the 1.6M node cap on 12.7% of decisions, so this is three
  turns mostly, not fully.
- Cost: 36 min wall at 3 threads (estimate 85; the pilot's ~5 thread-min
  per fight held at ~2.2), peak 8.2 GB for the job (mem_gb 5 was low:
  three threads of three-turn trees, about 2.7 GB each); lane total about
  10.6 cpu-h of 12.

What it changes: neither the rollout leaf nor three-turn search recovers
1.5 HP per elite over the two-turn product, so the lane ends at its stop
rule: the paused depth family (three-turn search, rollout leaves) stays
closed on this dev machine. Gains on goal 2 should come from the leaf
(the net two turns deep is +9.3 HP over the heuristic, 0090) and from the
run layer, not from more depth. A three-turn read would only reopen with a
cheaper search (fewer nodes per turn) or a much larger machine.

## Deck-matched reads two turns deep: paired end-HP sd 17.3 -> 13.5 (1.27x), under the 1.4x bar; matched reads stay a one-turn screen tool, but the read took 0.48x the wall time (cheaper-reads lane; 0107 with 0090; read 21:30 2026-11-04, lanes 1aba741f)

`gauntlet.py play heuristic --two-turn --line-seed --step-line --match
<the product's 500-749 file>` on the headline setting, sequences 500-749,
fixed n 250, paired by sequence with the product's file
(`net1029-hpe0.01-two-line-step-starter-simboss-500.json`), beside 0090's
unmatched read (the same heuristic fighter with the product as its
chooser, so decks diverge only where the chooser's sim fights follow the
fighter's HP):

| 500-749, n 250, against the product | end-HP diff (se) | paired sd | corr | clears diff (se) | clears sd | wall time, 3 threads |
|---|---|---|---|---|---|---|
| unmatched (0090, product's chooser) | -9.32 (1.09) | 17.25 | 0.69 | -0.200 (0.031) | 0.48 | 54 min |
| matched (0107, product's picks) | -8.99 (0.86) | 13.53 | 0.81 | -0.152 (0.026) | 0.41 | 26 min |

- Matched picks: 2422 of 2429 card floors (the rest after the product's
  own death); identical pick lists on 216 of 250 sequences, against 54
  unmatched.
- The bar (sd at least 1.4x lower, means within 2 se) misses: 1.27x on the
  sd (1.63x on the variance). Means agree: -8.99 against -9.32 end-HP;
  clears -0.152 against -0.200 (1.5 se of the unmatched read).
- By fight type: the matched heuristic dies less to bosses (floor-11
  deaths 60 against 72; guardian 26 against 34, hexaghost 27 against 33)
  and the same at the elites (floor 9: 24 and 24); it carries the
  product's better decks into the boss, as one turn deep. Train -0.160
  clears (se 0.037), held-out -0.144 (0.037): no content-half split.
- Wall time 0.48x: both reads ran at 3 threads beside one 3-thread
  mutate job (0083 for 0090, 0092 for 0107), and they differ only in the
  chooser, so the saving is the chooser's sim option fights, which a
  matched floor skips.

Why the sd gain is smaller than one turn deep (2.4-4.2x on variance
there): 0090's "unmatched" read already shares the product's chooser, so
its decks diverge only through HP, and the two fighters here are far
apart (9 HP), so more of the leftover variance is the fights themselves.
The one-turn reads compared nets that each picked for themselves. So the
1.27x is the gain for a search-flag read (same chooser net); for a new
net, whose unmatched read picks with its own net, the gain should be
nearer the one-turn 1.5-2x, unmeasured two turns deep.

What it changes: by the rule written before the run (0107's note),
matched reads don't become the default for two-turn fighter reads; they
stay a one-turn screen tool. A lead the rule didn't weigh: per verdict at
equal precision the matched read costs 0.48 / 1.63 = 0.29x the CPU on this
pair, which is the lane's own measure ("halve the CPU a headline
verdict costs"). Adopting that needs a decision written before a read,
not after this one: the navigator's to weigh. For depth-headroom (closed):
with the chooser's picks held exactly equal the heuristic two turns deep
is 8.99 HP (se 0.86) behind the product, the same as 0090's 9.32.

## Adaptation burst at 1602 games: SharpHide's novelty cost is more than repaired on elites, retention holds; go for 399 and 99 games (adaptation-curve lane; 0114, 0115, 0116; read 22:20 2026-11-04, lanes 7d67038d)

The 10-29 net fine-tuned on 1602 games against sharp2, sharp2-hp0.9 and
ritual2 patched elite and boss fights (fights 200-733 of each modifier;
`configs/adapt-sharp-s1.json`, one training seed: a lead). Val MSE ran
0.182, 0.174, 0.172, 0.177, 0.173, 0.179 over 6 epochs; the last epoch's
net is the one read (finetune keeps the last, not the best).

Read 1 (novelty, 0115: `mutate_monsters.py compare results/mutate/a.json
results/adapt/burst534-s1.json`; 200 starts x 8 seeds, fights 0-199, so
no overlap with training). Win rate, paired by start:

| modifier | base cost | burst gain | cut | parent change |
|---|---|---|---|---|
| sharp2 | -0.048 (0.015) | +0.079 (0.015) | 1.65 | +0.007 (0.006) |
| sharp2-hp0.9 | -0.062 (0.015) | +0.084 (0.014) | 1.34 | +0.007 (0.006) |
| ritual2 (reported only) | -0.038 (0.011) | +0.014 (0.008) | 0.38 | +0.007 (0.006) |

Both judged rows pass (gain >= half the cost and >= 2 se), by 5 se.
By fight type the gain is an elite effect: elites (134 starts) sharp2
+0.110 (0.019) against a cost of -0.082, sharp2-hp0.9 +0.104 (0.018)
against -0.086; bosses (66) +0.017 (0.023) and +0.042 (0.019), where
the base cost was small or positive anyway. Three Sentries carries it:
cost -0.215, gain +0.262 (0.047) on sharp2 (-0.203 / +0.247 on the
pair); Gremlin Nob +0.049 and +0.036 against costs near -0.04. A cut
above 1 means the burst net now beats the heuristic by more on the
patched fights than on the parents: plausibly the heuristic itself plays
badly into thorns on a three-enemy fight (it attacks every sentry), so
the room the net can take there is larger than the "novelty cost"
contrast measured. Ritual 2's cost sits on bosses (-0.066) and the
burst barely moves it (+0.004 on bosses, +0.020 on elites): with a third
of the games on bosses, 534 per modifier don't teach a growing enemy
Strength, or the one-turn search can't use it (Ritual pays off past the
turn horizon: fact `cause/novelty-is-horizon`).

Read 2 (retention, 0116: `gauntlet.py read results/gauntlet/net1029-hpb0.01.json
results/gauntlet/adapt534-s1-hpb0.01.json`, one-turn cell gauntlet
0-499 at fixed n): clears 0.634 control, 0.644 burst (A-B -0.010, se
0.016); paired end-HP burst minus control -0.13 (se 0.49), train half
-0.51 (0.68), held-out +0.26 (0.70). Well above the -1.5 bar; the
official parents' rows in read 1 agree (+0.007, 0.006). Deaths by
encounter barely move (Guardian 46 -> 39, Nob 18 -> 13, small rises on
hallway fights).

What it changes: the pre-registered rule says go, so the curve gets
filled at the charter's 400 and 100 fights (`games` 133 and 33 per
modifier, 399 and 99 fights; the spec's "games 100 / 400" read as fights
in total, the charter's unit). If 399 games already keep most of the
elite gain, goal 1's first games-to-adapt number is a few hundred games
for an unseen damage-reflecting power; ritual2 says the number depends on
whether the mechanic pays off inside the search horizon.

## Adaptation curve filled: 99 games repair SharpHide's one-turn cost on elites, 399 reach the plateau; Ritual 2 stays unrepaired at every size; retention holds (adaptation-curve lane; 0119-0124; read 22:45 2026-11-04, lanes 7d67038d)

The 10-29 net fine-tuned at three nested sizes (same game seed and first
fights per modifier; one training seed each: a curve of leads). Novelty
gain in win rate against the base costs of `results/mutate/a.json`
(sharp2 -0.048, sharp2-hp0.9 -0.062, ritual2 -0.038; 200 starts x 8
seeds), and retention on the one-turn cell gauntlet 0-499 (paired end-HP
burst minus `results/gauntlet/net1029-hpb0.01.json`, fixed n):

| games (per modifier) | sharp2 gain (cut) | sharp2-hp0.9 gain (cut) | ritual2 gain (cut) | elite sharp2 / pair | parents | cells end-HP |
|---|---|---|---|---|---|---|
| 99 (33) | +0.056 (0.013) 1.17 | +0.066 (0.012) 1.06 | +0.006 (0.007) 0.15 | +0.086 / +0.088 | +0.006 (0.005) | -0.27 (0.37) |
| 399 (133) | +0.080 (0.015) 1.66 | +0.079 (0.014) 1.27 | +0.018 (0.008) 0.46 | +0.112 / +0.107 | +0.008 (0.005) | -0.07 (0.42) |
| 1602 (534) | +0.079 (0.015) 1.65 | +0.084 (0.014) 1.34 | +0.014 (0.008) 0.38 | +0.110 / +0.104 | +0.007 (0.006) | -0.13 (0.49) |

Files: `results/adapt/burst{33,133,534}-s1.json`,
`results/gauntlet/adapt{33,133,534}-s1-hpb0.01.json`; jobs 0119-0124
(0117 and 0118 failed in seconds: pinned to a commit without their
configs, re-queued as 0119 and 0120).

Why: the whole effect is on elites, and inside them on Three Sentries
(gain +0.21, +0.28, +0.26 by size on sharp2 against a cost of -0.215):
a three-enemy fight where SharpHide punishes every attack, so learning
"don't spread attacks into thorns" pays at once. Bosses move within
noise at every size (sharp2 boss cost was +0.021 to begin with). Ritual
2 costs most on bosses (-0.066) and no size repairs it: its payoff
(growing Strength) lies past the one-turn horizon, which training on
outcomes can't put inside the search (fact `cause/novelty-is-horizon`).
Retention never moves beyond 0.6 se, and the parents' rows agree, so
the burst recipe adapts without forgetting at these sizes. Val MSE
falls with size (best 0.191, 0.177, 0.172), the curve's other face.

What it changes: goal 1's first games-to-adapt number is **about 100
games** (33 per modifier) to remove the one-turn cost of an unseen
damage-reflecting power, saturating by about 400, for a mechanic whose
payoff falls within the search horizon; for one past it (Ritual) the
answer is depth, not games. Leads, not results: one training seed per
size, nested data, one family of powers, one-turn reads. What would
make it a result: a second seed at 99 games and the paired-modifier
bench (several unseen powers, each fine-tuned and read the same way) —
a backlog entry for the navigator.

## Transfer: a SharpHide burst repairs Thorns 2 too, 0.86x of its own SharpHide gain; adaptation carries across the damage-back-on-attack family (adaptation lane step 1; 0125, 0126; read 23:40 2026-11-04, lanes 4ccb3148)

The stage A burst nets (fine-tuned on SharpHide 2, its hp pair and Ritual 2) played one turn deep on two modifiers they never trained on: thorns2 (Thorns 2 on the enemy, a sibling mechanic) and the stack metal4-hp0.85+sharp2-hp0.9. 200 starts x 8 seeds, read with `mutate_monsters.py compare results/mutate/a.json <file>` (gain = the burst's change in novelty cost against the 10-29 net, paired by start; win rate, se).

| net | modifier | base cost | burst gain | cut |
|---|---|---|---|---|
| 1602 games | thorns2 | -0.053 (0.014) | +0.068 (0.013) | 1.28 |
| 1602 games | metal4-hp0.85+sharp2-hp0.9 | -0.091 (0.016) | +0.125 (0.017) | 1.38 |
| 99 games | thorns2 | -0.053 (0.014) | +0.051 (0.011) | 0.96 |
| 99 games | metal4-hp0.85+sharp2-hp0.9 | -0.091 (0.016) | +0.089 (0.015) | 0.98 |
| 1602 games (trained, for scale) | sharp2 | -0.048 (0.015) | +0.079 (0.015) | 1.65 |

Parents moved +0.006 to +0.007 (se 0.005-0.006), so the gains are specific to the modified fights.

**Verdict: go.** The charter's bar was a thorns2 gain of at least half the sharp2 gain (about +0.04) at 2 se; the 1602-game net gains +0.068, 0.86x its sharp2 gain, at 5 se. Even 99 games get 0.96x of the thorns2 cost back.

**By fight type.** On thorns2 the 1602-game net gains +0.091 (0.016) on elites, spread evenly (Gremlin Nob +0.094, Lagavulin +0.090, Three Sentries +0.090, se 0.03 each), and +0.021 (0.020) on bosses. Its gain on sharp2, the trained mechanic, sits mostly on Three Sentries (+0.262 of the elite +0.110). On the stack the elite gain is +0.154 (Three Sentries +0.328), bosses +0.066 (0.025, Hexaghost +0.164).

**Why it transfers (a reading, not tested).** In the effects encoder the two powers are hook rows with the same effect (plain damage to the player) and different triggers: SharpHide fires when the player plays an attack, Thorns on each hit taken. The net learns the shared effect atom, "attacking this enemy costs HP", rather than the power's id. Not ruled out: the burst taught attack restraint in general against elites with any hook power. A control on a hook power with a different effect would separate these (weakhit1, stage B, is a candidate for step 3).

**What it changes.** Goal 1's games-to-adapt number holds per mechanic family, not per mechanic: a new power that shares effect atoms with a trained one gets most of the repair at no extra games. Single training seed: a lead. Step 2 (0127, second seed at 99 games) and step 4 (0128-0129, rate-column twins on Ritual 2, seed s1) are queued; step 3 waits for 0112.

## Rate columns on Ritual 2, seed s1: the rates net's novelty cost is 0.014 smaller (se 0.010), all on elites; on bosses, where Ritual 2 costs most, no gain; SharpHide gains more (adaptation lane step 4; 0128, 0129; read 00:15 2026-11-05, lanes 4ccb3148)

Step 4 asks whether an input the net can read, the encoder's rate columns (docs/specs/rate-features.md: per entity, Strength per turn and Strength x rounds left), repairs Ritual 2's payoff, which lies past the search horizon. The rates net runs/2026-10-31-lean-rates-s1-r2-93e9721 and its twin trained without the columns (runs/2026-10-31-lean-thr-s1-r2-a81ecde) each played one turn deep on ritual2, ritual2-hp0.7 and sharp2 with their parents, 200 starts x 8 seeds. Novelty cost here is each net's win change on the modified fight beyond its parent, minus the heuristic's change in results/mutate/a.json, paired by start (win rate, se).

| modifier | fights | twin (no columns) | rates net | rates minus twin |
|---|---|---|---|---|
| ritual2 | all 200 | -0.044 (0.012) | -0.030 (0.009) | +0.014 (0.010) |
| ritual2 | elites 134 | -0.041 (0.012) | -0.016 (0.009) | +0.025 (0.013) |
| ritual2 | bosses 66 | -0.049 (0.026) | -0.059 (0.020) | -0.009 (0.018) |
| ritual2-hp0.7 | all 200 | -0.014 (0.010) | -0.013 (0.008) | +0.001 (0.008) |
| sharp2 | all 200 | -0.091 (0.020) | -0.058 (0.015) | +0.033 (0.013) |
| sharp2 | elites 134 | -0.151 (0.025) | -0.099 (0.019) | +0.052 (0.017) |
| sharp2 | bosses 66 | +0.032 (0.028) | +0.027 (0.022) | -0.006 (0.020) |

`mutate_monsters.py compare results/mutate/thr-s1.json results/mutate/rates-s1.json` gives the same column (parents' change +0.010, se 0.008).

**Stop rule:** the rates net's ritual2 cost is smaller (+0.014), so step 4 goes on to s101 and s201 (0132-0135 queued). s201's rates net is runs/2026-10-31-lean-rates-s201-r2-3a08d8b; the other s201 rates folder (f31767f) holds no model.

**Sceptical read.** The hypothesis predicts a gain where Ritual's payoff lands, on bosses (long fights, Strength stacking every turn). There the rates net is no better (-0.009, 0.018). Its ritual2 gain sits on elites, and its gain on sharp2 (a payoff inside the horizon, which the rate columns don't describe) is larger and also on elites. Read together: at s1 the rates net plays elites with an unseen hook power better in general; it doesn't read Ritual's growth. The go rule's second clause (sharp2 within 2 se of equal) fails at s1 (+0.033 at 2.5 se). One seed: a lead; the three-seed read decides.

## Second training seed at 99 games: SharpHide's cost cut 1.12x (seed 1 1.17x), retention -0.31 HP; the 99-game point is a result (adaptation lane step 2; 0127, 0130, 0131; read 00:35 2026-11-05, lanes 4ccb3148)

The 99-game burst (33 games per modifier on sharp2, sharp2-hp0.9, ritual2) trained again with training seed 2 (configs/adapt-sharp-g33-s2.json: same content, game seed 41 and games as seed 1; run runs/2026-11-04-adapt-sharp-g33-s2-984a3f4). One turn deep, 200 starts x 8 seeds, `mutate_monsters.py compare results/mutate/a.json results/adapt/burst33-s2.json` (win rate, se):

| modifier | base cost | seed 1 gain (cut) | seed 2 gain (cut) |
|---|---|---|---|
| sharp2 | -0.048 (0.015) | +0.056 (0.013) (1.17x) | +0.054 (0.013) (1.12x) |
| sharp2-hp0.9 | -0.062 (0.015) | +0.066 (0.012) (1.06x) | +0.062 (0.013) (1.00x) |
| ritual2 | -0.038 (0.011) | +0.006 (0.007) (0.15x) | +0.012 (0.008) (0.31x) |

Parents +0.004 (0.006). By fight type the seeds agree too: sharp2 elites +0.086 / +0.083 (Three Sentries +0.212 / +0.195), bosses -0.004 / -0.006.

Retention (0131, one-turn cell gauntlet 0-499 at fixed n, against results/gauntlet/net1029-hpb0.01.json): clears 0.634 both; paired end-HP (last floor's HP, 0 on a death; the method reproduces the 1602-game read's -0.13) -0.31 (se 0.39), train half -0.02 (0.53), held-out -0.60 (0.58). Well above the -1.5 bar.

**Verdict: checkpoint seed-2 passed.** Both training seeds cut sharp2's cost at 2 se or more (4 se each) with retention, so the 99-game point is a result, not a lead: about 100 games (33 against the new power) repair the one-turn cost of an unseen power whose payoff is inside the horizon. The two seeds differ by 0.002 on sharp2, well under the se; training-seed luck at this size is small next to the effect. Ritual 2 stays unrepaired on both.

## Rate columns over three seeds: no repair of Ritual 2 (rates minus twin -0.005, se 0.008; bosses -0.006); the s1 lead was training-seed luck; Guardian guard passes (adaptation lane step 4; 0128, 0129, 0132-0135; read 00:50 2026-11-05, lanes 4ccb3148)

Step 4 finished: the rate-column nets (runs/2026-10-31-lean-rates-s{1,101,201}-r2-*, s201 = 3a08d8b) and their twins without the columns (lean-thr-s{1,101,201}-r2-*) one turn deep on ritual2, ritual2-hp0.7, sharp2 and parents, 200 starts x 8 seeds each. Value: the rates net's novelty cost (its change on the modified fight beyond its parent, minus the heuristic's in results/mutate/a.json) minus its twin's, paired by start (win rate, se).

| seed | ritual2 | ritual2 bosses | ritual2-hp0.7 | sharp2 | sharp2 elites |
|---|---|---|---|---|---|
| s1 | +0.014 (0.010) | -0.009 (0.018) | +0.001 (0.008) | +0.033 (0.013) | +0.052 (0.017) |
| s101 | -0.010 (0.010) | -0.013 (0.016) | -0.010 (0.009) | -0.028 (0.012) | -0.031 (0.015) |
| s201 | -0.018 (0.012) | +0.006 (0.026) | +0.000 (0.009) | -0.016 (0.013) | -0.032 (0.017) |
| pooled (per-start mean over seeds) | -0.005 (0.008) | -0.006 (0.015) | -0.003 (0.006) | -0.004 (0.009) | -0.003 (0.012) |

**Verdict: no go.** The go rule asked for a ritual2 gain of at least 0.02 at 2 se over the three seeds, with sharp2 within 2 se of equal. Ritual2 is -0.005 (0.008); sharp2 is -0.004 (0.009), equal. The columns don't carry Ritual 2's payoff on this bench, one turn deep: not on bosses (where Ritual's Strength growth lands, -0.006), not on elites.

**Guardian guard** (charter, rev 4): on the 15 Guardian starts among the parents, rates net minus twin win rate, paired by start: s1 +0.000 (0.017), s101 +0.050 (0.024), s201 +0.033 (0.046); pooled +0.028 (0.018). Passes (above -0.05). The Guardian cost seen on official gauntlet decks (cause/novelty-is-horizon) does not show on this bench's Guardian starts. All parents: +0.010, +0.008, -0.003 (se 0.007-0.010).

**Why the s1 lead faded.** At s1 the rates net was better on elites against both unseen powers, and that sign flipped at s101 and s201. The per-seed spread of the twin difference (sharp2: +0.033 to -0.028, sd about 0.031) is about 2.5x the per-seed se (0.012-0.013). A twin pair from one training seed mostly measures that seed's luck in how the net handles unfamiliar hook powers on elites; on this bench a twin comparison needs three seeds before it reads anything.

**Why the columns don't help here (a reading).** The rate columns give Strength per turn and Strength x rounds left, and Ritual 2's payoff is exactly that. The nets were trained on official content, where such rates come from Demon Form on the player's side, and the bench puts the rate on a new enemy. The net has inputs that describe the growth but learned no use for them on an enemy: an input without games that use it. That is the backlog's columns-plus-games follow-up: a burst on Ritual 2 with the columns on.

## Stacking check: 2 of 7 stacks are harder than the sum of their parts beyond 2 se (heuristic), 1 of 6 two turns deep; the sum is close but not the distance axis; the two owner pairs both read harder (goal1-yardstick; 0092; read 04:45 2026-11-05, lanes cf60f1ff)

Job `jobs/done/0092-mutate-monsters.json` (two-turn product 200 x 4, appended to `results/mutate/a.json`; heuristic and one-turn 200 x 8 from 0091). Read with `mutate_monsters.py read results/mutate/a.json`. All 200 parent starts, win change from the parent, paired by start.

**Stacks** (interaction = stack's win change minus the sum of its parts' changes; rule: every stack within 2 se of 0 on heuristic and two-turn):

| stack | heuristic | two turns |
|---|---|---|
| metal4-hp0.85+sharp2-hp0.9 (from 0083) | -0.022 (0.009), 2.4 se | -0.034 (0.015), 2.3 se |
| metal4-hp0.75+sharp1-hp0.9 | +0.001 (0.008) | +0.019 (0.011) |
| metal4-hp0.75+ritual2-hp0.7 | -0.018 (0.010) | -0.001 (0.010) |
| ritual2-hp0.7+hp1.3-str-1 | +0.023 (0.016) | -0.007 (0.014) |
| thorns2-hp0.9+hp1.3-str-1 | -0.038 (0.014), 2.7 se | -0.009 (0.015) |
| metal4-hp0.75+thorns2-hp0.9+hp1.3-str-1 | -0.024 (0.016) | +0.000 (0.016) |
| weakhit1-dmg0.8+thorns2-hp0.9 (stage B, 0112) | +0.013 (0.008) | in 0113 |
| weakhit1-dmg0.8+split (stage B, 0112) | -0.002 (0.007) | in 0113 |

**Verdict: fail by the rule.** Three of 14 tests exceed 2 se (about 0.7 expected by chance), all negative. The old stack's two-turn row is the same 0083 data, not a replication. Sizes: the interactions are 0.02-0.04 in win rate, about a fifth to a third of the stack's own change. So the sum of parts is a fair first guess at a stack's difficulty but not exact. As the job note's fail branch says, stacks are measured directly: stage B (0112 and 0113) already plays its stacks as their own rows.

**Where it comes from.** Both failures sit on elites, mostly Three Sentries: metal4+sharp2 -0.076 (0.034) heuristic and -0.099 (0.043) two turns there; thorns2+hp1.3 -0.058 (0.023) on Sentries, -0.078 (0.032) on Lagavulin and -0.042 on Nob (heuristic). A reading (not tested): one part makes the fight longer (Metallicize's block, +30% HP) and the other charges a price per attack (SharpHide, Thorns), so the price is paid on more turns and the costs multiply instead of adding. Sentries make this worse because they are three targets. The one positive interaction (Hexaghost, thorns2+hp1.3, +0.07 (0.044)) is near the floor, where the sum of parts predicts a drop below what win rates can fall to. That points to win rate as a poor scale for adding effects, not to a real easing. Two turns deep, the product absorbs most of the thorns+hp interaction (elites -0.059 heuristic, -0.022 two turns), so the multiplying is partly a weakness of the heuristic's planning.

**New owner pairs** (two turns, all starts): thorns2-hp0.9 -0.110 (0.016), hp1.3-str-1 -0.058 (0.011); both harder: the boon does not cancel the bane. Thorns 2 alone -0.141 (0.019).

**Thorns against SharpHide** (one-turn novelty, net minus heuristic): thorns2 -0.053 (0.014), sharp2 -0.048 (0.015); two-turn repair +0.053 (0.015) for both. Thorns behaves like SharpHide: a cost inside the search horizon that depth repairs (cause/novelty-is-horizon).

**Reader quirk.** The `all` table already lists stage B rows with a two-turn column of +0.000 (0.000), pooled from 0113's first 2 starts. Ignore it until 0113 ends; the per-fight tables show `-` there.

**What it changes.** The stacking part of the stop rule is recorded (the stop rule asks for a first check, not a pass). The lane's last checkpoint is stage-b-table (0113). On the yardstick, a stack's difficulty is its own measured row; the sum of parts is a prior that misses by up to about 0.04 on elites.

## Stage B bursts: nothing to repair one turn deep, and no burst cuts its modifier at 2 se; the SharpHide control gains on WeakOnHit (4.8 se in HP), so transfer is wider than one effect atom (adaptation lane step 3; 0138, 0139, 0141 with 0112; read 05:10 2026-11-05, lanes 2cca9f24)

Three nets played one turn deep on stage B's weakhit1 (WeakOnHit 1), dmg0.8 (DamageDown 1) and split, 200 starts x 8 seeds, read with `mutate_monsters.py compare results/mutate/a.json <file>` against 0112's base rows (gain = change in novelty cost against the 10-29 net, paired by start, net of the parents' change). The bursts trained on all three modifiers together: 99 games (33 per modifier) and 399 (133 per modifier). The control is the 1602-game SharpHide net from stage A, which never saw them.

| net | modifier | base cost (win) | gain (win) | gain (HP lost) | parents (win) |
|---|---|---|---|---|---|
| 99-game stage B burst | weakhit1 | -0.016 (0.011) | +0.006 (0.008) | -0.16 (0.26) | -0.002 (0.006) |
| | dmg0.8 | -0.006 (0.009) | +0.004 (0.007) | -0.12 (0.18) | |
| | split | -0.016 (0.007) | +0.013 (0.007) | -0.23 (0.28) | |
| 399-game stage B burst | weakhit1 | | -0.001 (0.011) | +0.07 (0.30) | -0.009 (0.007) |
| | dmg0.8 | | +0.007 (0.007) | -0.00 (0.26) | |
| | split | | +0.008 (0.007) | -0.23 (0.28) | |
| 1602-game SharpHide net (control) | weakhit1 | | **+0.024 (0.008)** | **-1.36 (0.29)** | +0.007 (0.006) |
| | dmg0.8 | | +0.001 (0.006) | +0.35 (0.23) | |
| | split | | +0.013 (0.006) | +0.65 (0.27) | |

HP lost: negative is better.

**The base costs are small.** One turn deep, the 10-29 net's novelty cost against the heuristic on these modifiers is -0.016, -0.006 and -0.016 in win rate (1.5, 0.7 and 2.3 se). In HP lost only weakhit1 has a clear cost: +1.74 (0.34) HP, mostly on elites (+2.27). DamageDown makes the net *better* than the heuristic (-1.0 HP). So stage B's one-turn bench has little to cut; a burst's "cut" on it is mostly noise (the 1.10x on dmg0.8 is 0.007 of a 0.006 cost).

**Checkpoint stage-b-bursts: failed.** No burst cuts any modifier's cost at 2 se, in win rate or in HP. The 399-game burst does no better than the 99-game one; on Three Sentries under weakhit1 it is worse (+1.98 (0.67) HP lost). Stage B gives no games-to-adapt point: with costs this small, the curve can't be read here. This is not a failure of adaptation; stage A's 99-game point (`measurement/adaptation-curve`) stands.

**The control is the surprise.** The SharpHide net, trained on a different power, cuts weakhit1's HP cost by 1.36 (0.29) HP (78% of the 1.74 cost) and gains +0.024 (0.008) in win rate, on elites: Gremlin Nob -2.24 HP, Three Sentries -2.45, Lagavulin -1.35 (se 0.6-0.7 each); bosses mixed (Hexaghost -1.04, Guardian +1.76 (1.04), Slime Boss +0.11). On dmg0.8 and split it gains nothing (HP slightly worse, +0.35 and +0.65). So by the charter's rule (control nothing at 2 se = transfer per effect atom) transfer is *not* per effect atom: WeakOnHit's effect (Weak on the attacker) differs from SharpHide's (damage to the attacker), yet the repair carries.

**Why (a reading, not tested).** What SharpHide, Thorns and WeakOnHit share is the trigger side: each punishes the player for attacking this enemy. The 1602-game burst seems to have learned "attacks into this kind of hook power cost something" (restraint, or ordering attacks after block and debuffs), which pays against all three, and does nothing for DamageDown (no trigger on the player's attacks) or split. The stage B bursts at 133 games per modifier did not learn the same about WeakOnHit, perhaps because its cost per game is small (1.7 HP) so 133 games carry little signal, against SharpHide's larger, steadier cost. Not ruled out: the 1602-game net is simply more cautious on elites in general; its parents moved +0.007 (0.006), which the gain already nets out, so that would have to be caution that pays only under hook powers.

**What it changes.** Goal 1's games-to-adapt number is per *family of punishments for attacking* in the widest reading: one burst on a power whose cost is large teaches play that repairs smaller siblings it never saw. For goal 1 this suggests training bursts on content with a strong, clear cost rather than many weak modifiers at once. One training seed and one net: a lead. All four steps of the lane are read; the lane is done.

## Wide read: at 325 boss starts x 32 seeds the one-turn net has no boss edge over the heuristic (+0.01, se 0.12) and no boss cost on any stat change; stage A's boss cost was seed luck in its parent edge. On elites stat changes cost nothing by odds ratio, Ritual 2 and SharpHide do (difficulty-shift lane step 1; 0143; read 07:40 2026-11-05, lanes cd29f3fd)

`results/mutate/wide.json` (job 0143, 110 min at 3 threads against an
estimate of 220): 1000 starts (325 boss, 675 elite) x 32 seeds, the
heuristic and the 10-29 net one turn deep, parent and str1, str2, ritual2,
hp0.8, hp1.25, sharp2, dmg0.8. Read by `yardstick/novelty-read` with the
new `mutate_monsters.py odds` (Mantel-Haenszel log odds ratio of the net
against the heuristic, modified minus parent, bootstrap se over starts,
2000 resamples). On `results/mutate/a.json` it reproduces stage A's
published column (parent +0.42 (0.28), str2 -0.65 (0.25), ritual2 -0.84
(0.32)).

| log odds ratio, net vs heuristic | bosses (325) | elites (675) |
|---|---|---|
| parent (the edge itself) | +0.01 (0.12) | -0.25 (0.19) |
| str1 | -0.10 (0.06) | +0.22 (0.13) |
| str2 | -0.17 (0.09) | +0.29 (0.14) |
| ritual2 | -0.07 (0.13) | -0.65 (0.21) |
| hp0.8 | -0.15 (0.11) | -0.20 (0.25) |
| hp1.25 | +0.01 (0.09) | +0.03 (0.17) |
| sharp2 | +0.09 (0.10) | -1.18 (0.20) |
| dmg0.8 | +0.14 (0.11) | +0.19 (0.25) |

HP lost beyond the heuristic, modified minus parent (se over starts):
elites str1 +0.01 (0.05), str2 +0.16 (0.07), hp1.25 +1.18 (0.15),
ritual2 +2.25 (0.21), sharp2 +6.29 (0.31), hp0.8 +0.35 (0.16), dmg0.8
-1.01 (0.08); bosses all within 0.6 HP (str2 +0.39 (0.24), ritual2 +0.40
(0.38)). Win-rate novelty on bosses: str2 -0.016 (0.009), ritual2 -0.005
(0.011), hp0.8 -0.009 (0.009), against stage A's -0.064 and -0.066.

**Checkpoint wide-read: failed.** Neither str2 (-0.17, 1.9 se) nor
ritual2 (-0.07, 0.5 se) is below the parent by 2 se on bosses.

**Why stage A read a cost.** The wide file plays the same seeds first:
its seeds 0-7 on stage A's 66 boss starts repeat stage A's games exactly
(all 200 starts' heuristic results match) and give stage A's numbers. On
the fresh seeds 8-31 of the same 66 starts the parent edge is +0.18
(0.23), str2 -0.12 (0.19), ritual2 -0.05 (0.26); on the other 259 boss
starts the edge is -0.06 (0.15), str2 -0.13 (0.11), ritual2 -0.01 (0.15).
So stage A's boss cost was its parent edge (+0.42 at 8 seeds) being high
by seed luck, and every modifier's "modified minus parent" inherited it;
with 30 modifiers read against one parent, a 2.6 se outlier was likely.
Only hp0.8 on those 66 starts stays low on fresh seeds (-0.60 (0.28)),
while it is -0.03 (0.12) on the other 259: a start-specific quirk, not a
cost. Each se was right for one comparison, but all 30 modifiers share
one parent term, so a lucky parent moves every "modified minus parent"
the same way at once: the costs looked consistent across str2, ritual2
and hp0.8 because they were one draw, not three.

**What it changes.**
- The boss half of `cause/novelty-is-horizon` (a cost of shifted boss
  numbers) has no support left: at 5x the starts and 4x the seeds there is
  no boss cost on str1, str2, ritual2, hp0.8 or hp1.25. The one-turn net
  also has no boss edge over the heuristic to lose (+0.01 (0.12)), so the
  boss column can't show a novelty cost one turn deep at all; any boss
  read of novelty belongs two turns deep, where the product has an edge.
- On elites the odds ratio separates mechanic from danger better than
  stage A could: plain Strength makes elites more contested (116
  informative starts for str2) and the net does better there than on the
  parent (+0.29 (0.14)); +25% HP costs nothing by odds ratio (+0.03
  (0.17)) and 1.2 HP by HP lost; Ritual 2 costs -0.65 (0.21) and 2.3 HP,
  SharpHide -1.18 (0.20) and 6.3 HP. Per HP of extra difficulty for the
  heuristic, the net loses 0.03 HP on str2, 0.16 on hp1.25, 0.22 on
  ritual2 and 0.40 on sharp2. The elite cost grows with the mechanic, not
  with danger alone; step 2 (the stat burst) tests the same from the
  training side.
- Step 2's boss check has nothing to repair; 0148 plays it as a check
  that the burst keeps the (null) boss edge.

## Stat burst: 400 games on plain stat shifts repair neither SharpHide (-0.023, se 0.013) nor Thorns (+0.018 against the SharpHide burst's +0.066); the unit of novelty is the mechanic, not danger; retention holds on HP (difficulty-shift lane step 2; 0144-0147; read 07:55 2026-11-05, lanes cd29f3fd)

The burst (0144, `runs/2026-11-05-adapt-stat-g100-s1-cf53685`, config
`configs/adapt-stat-g100-s1.json`): the adapt-stageb-g133 recipe from the
10-29 net on hp0.8, hp1.25, str2 and hp1.3-str-1, 100 training fights
each (400 games), the size of the 399-game SharpHide burst. Read one turn
deep at 200 x 8 with `mutate_monsters.py compare results/mutate/a.json`
(gain in novelty cost, win rate, paired by start; the parents' change
is subtracted):

| modifier (never trained on) | base cost | stat burst gain (0145) | SharpHide burst gain, 399 games (0146; `burst133-s1.json`) |
|---|---|---|---|
| sharp2 | -0.048 (0.015) | -0.023 (0.013) | +0.080 (0.015) |
| thorns2 | -0.053 (0.014) | +0.018 (0.016) | +0.066 (0.014) |
| weakhit1 | -0.016 (0.011) | +0.011 (0.010) | +0.013 (0.007) |
| ritual2 | -0.038 (0.011) | +0.019 (0.011) | +0.018 (0.008) |
| parents' change | | -0.019 (0.009) | +0.008 (0.005) |

**Checkpoint stat-burst: failed (stop).** The go bar is half the
SharpHide burst's gain on both sharp2 (0.040) and thorns2 (0.033); the
stat burst reaches neither, and on thorns2 it is 0.048 (about 2.3 se)
below the SharpHide burst. On ritual2 and weakhit1 both bursts gain the
same small amount, so what they share there is general, not specific to
either training set. Its parents fall 0.019 (0.009) (bosses -0.042
(0.024), elites -0.007 (0.007)), so part of every "gain" above is the
parent term moving down: the raw change on sharp2 is -0.042.

Retention (0147, one-turn cell gauntlet 0-499 against
`yardstick/one-turn-controls`): paired end-HP -0.85 (0.49) (train half
-1.19 (0.64), held-out -0.51 (0.75)), above the -1.5 bar; clears 0.602
against 0.634 (-0.032 (0.016)), with 11 more Hexaghost deaths. The
stage B burst at the same size read +1.14 (0.53) on the same files, so
this burst costs a little where the SharpHide and stage B bursts didn't.

The odds-ratio column on the burst's elite parents (-2.92 (0.50)) is not
a collapse: elite parents are won 0.99 by every player, the parent
win change is -0.007 (0.007), and a handful of informative starts set the
ratio. The odds ratio is unusable on near-ceiling parents.

0148 (the burst on the wide bench's bosses) was stopped at its start:
step 1 found no boss cost on the base net to repair, so it could change
nothing.

**What it changes.** With step 1 (stat changes cost the net nothing on
elites by odds ratio and little by HP; `measurement/wide-bench@one-turn`),
both sides agree: the net's cost on changed enemies is a cost of the
mechanic, not of a fight made more dangerous, and practice on harder
numbers doesn't teach the answer to a power that punishes attacking.
Training with jittered numbers (`jitter-training`) loses its premise as a
zero-shot lever for new mechanics; the transfer result
(`measurement/adaptation-transfer`) stands as a family of mechanics.
One training seed: a lead in size, but the gap to the SharpHide burst
is 2.3 se and points the same way as step 1's independent read.

## Stage B two turns deep, at 141 of 200 starts: the pattern modifiers cost the product nothing beyond the heuristic (all within 1.6 se), every two-turn se at or under 0.020; WeakOnHit is the hard one, DamageDown the easy one, split level; reactive-power stacks on elites cost about 0.03 (goal1-yardstick; 0113 partial, with 0112; read 10:30 2026-11-05, lanes 90f55716)

Job 0113 (two-turn product 200 x 4 on stage B's modifiers, appending to `results/mutate/a.json`) was read at 141 of its 200 starts: the lane reached its 90 cpu-h cap with the job at 334 of its 330 estimated minutes, and a snapshot of `a.json` (written after every start) already met the checkpoint's bar. Read with `mutate_monsters.py read` on the snapshot. The heuristic and one-turn columns are 0112's 200 x 8. The two-turn-minus-heuristic contrast (paired by start, the parent's contrast taken out) was computed with `mutate_monsters.outcome` over the same rows, because the reader prints only one-heur and two-one.

**All fights (two turns: 141 starts; win change from the parent, se):**

| modifier | heuristic | one turn | two turns | verdict | novelty one-heur | repair two-one | two-heur |
|---|---|---|---|---|---|---|---|
| weakhit1 (WeakOnHit 1) | -0.072 (0.013) | -0.088 (0.013) | -0.082 (0.016) | harder | -0.016 (0.011) | +0.004 (0.011) | -0.006 (0.014) |
| dmg0.8 (DamageDown) | +0.064 (0.013) | +0.058 (0.011) | +0.044 (0.014) | easier | -0.006 (0.009) | -0.011 (0.010) | -0.020 (0.012) |
| split | -0.003 (0.006) | -0.019 (0.007) | -0.016 (0.008) | level | -0.016 (0.007) | +0.000 (0.007) | -0.004 (0.008) |
| weakhit1-dmg0.8 (the pair) | -0.004 (0.006) | -0.003 (0.007) | -0.021 (0.009) | harder | +0.001 (0.008) | -0.013 (0.009) | -0.012 (0.010) |
| weakhit1-dmg0.8+split | -0.008 (0.010) | -0.016 (0.010) | -0.011 (0.010) | level | -0.007 (0.010) | +0.004 (0.009) | +0.011 (0.013) |
| weakhit1-dmg0.8+thorns2-hp0.9 | -0.084 (0.016) | -0.154 (0.019) | -0.113 (0.020) | harder | -0.071 (0.014) | +0.046 (0.014) | -0.017 (0.014) |

**By fight type, two-heur:** elites (94 starts) all within 1 se except the Thorns stack, -0.031 (0.013), 2.4 se; bosses (47 starts) all within 1.3 se except dmg0.8, -0.072 (0.035), 2.1 se. Stacks' interactions two turns deep: weakhit1-dmg0.8+thorns2-hp0.9 +0.012 (0.015), weakhit1-dmg0.8+split +0.027 (0.009), 3.0 se, the latter all on bosses (+0.074 (0.024)).

**Checkpoint stage-b-table: passed.** Every stage B modifier's two-turn win change has se <= 0.020 (the Thorns stack sits exactly at the bar; at 200 starts it would be about 0.017), and each verdict is recorded above.

**Why, and how far to trust it.**
- *The pair is level where it should be, except two turns deep on bosses.* WeakOnHit and DamageDown were tuned to cancel, and they do for the heuristic (-0.004) and one turn deep (-0.003). Two turns deep the pair reads -0.021 (2.3 se), carried by bosses (-0.059 (0.024)); on elites it is -0.003 (0.003). Every stage B two-turn boss row leans the same way against the heuristic (dmg0.8 +0.122 against +0.188, split -0.043 against +0.002), and so does the positive split-stack interaction on bosses: the parent's contrast enters every row once, and the stack minus its two parts counts it once more. That is the signature of one lucky two-turn parent draw on the boss starts (4 seeds; `yardstick/novelty-read` rule a), the question lane boss-cost-two-turn is reading with fresh seeds (job 0151). So the boss two-turn rows here are not evidence of a product cost until that lane reads.
- *DamageDown's -0.072 on bosses* has a second confound, in the job note: the heuristic's and the lookahead's damage rates don't see DamageDown, so the heuristic column overstates how much easier the fight got. One test in twelve at 2.1 se is about what chance gives.
- *No pattern modifier costs the product.* Beyond the heuristic, the product's change is within 1.6 se on every stage B modifier over all fights. By the job note's rule: no goal-1 failure of the product on patterns; the enemies rung holds for pattern mutations too. One turn deep the net's novelty cost is small (split -0.016, 2.3 se; WeakOnHit -0.016, 1.5 se), as the bursts' read found (`measurement/adaptation-stage-b`).
- *The one lead: stacks holding a reactive power cost the product about 0.03 on elites.* The Thorns stack here (-0.031 (0.013)) and stage A's metal4-hp0.85+sharp2-hp0.9 (-0.030 (0.012), same contrast on 134 elite starts) both sit at about 2.5 se, while their single reactive parts read -0.017 (thorns2-hp0.9) and -0.006 (sharp2-hp0.9). Two of about 24 elite and boss tests beyond 2 se is a little above chance; it is a lead, not a result, and it is the direction a two-turn horizon would predict (more to track per fight).

**What it changes.** The lane's stop rule is met: stage A's widened two-turn table, stage B's paired-modifier table and a first stacking check are recorded. The lane closes at its cap. The goal-1 number on the monsters rung stands: one turn deep the net pays for new mechanics (reactive powers, growth) and two turns deep the product pays nothing measurable per single modifier on patterns or stats, with the boss rows waiting on boss-cost-two-turn and a possible small cost on reactive stacks on elites. The next rung is cards (backlog candidate 1). Job 0113 runs out its last 59 starts because no lane had other CPU work ready (decisions "Lane goal1-yardstick closed"); re-running `mutate_monsters.py read results/mutate/a.json` afterwards only tightens these rows.

## Boss cost two turns deep, on 259 fresh boss starts: no product cost on Ritual 2 or HP x0.8 by the charter's bar; the parent edge is real (+0.075, 5.8 se); hp0.8's -0.038 on the win column (2.4 se) is a ceiling squeeze the odds column does not confirm (-0.38, 1.5 se) (boss-cost-two-turn lane; 0151 with 0143's heuristic games; read 14:10 2026-11-05, lanes d9cd3df1)

Job 0151 (`jobs/done/0151-mutate-monsters.json`) played the two-turn product on the 259 boss starts at positions 200-999 of the wide bench (`results/mutate/wide-two.json`), parent, ritual2 and hp0.8 at 2 seeds; the heuristic's games are the wide file's 32 seeds of the same starts (`results/mutate/wide.json`). The win column is paired by start (the two-turn player's change from the parent minus the heuristic's, se over starts); the odds column is `mutate_monsters.py odds results/mutate/wide-two.json --player two --base results/mutate/wide.json`.

| | two-turn change | heuristic change | beyond the heuristic (win) | log odds ratio vs parent |
|---|---|---|---|---|
| parent edge (two - heuristic) | 0.751 | 0.676 | +0.075 (0.013) | +1.07 (0.20) |
| ritual2 | -0.357 (0.026) | -0.340 (0.023) | -0.017 (0.016) | -0.15 (0.24), 101 informative |
| hp0.8 | +0.118 (0.017) | +0.156 (0.014) | -0.038 (0.016) | -0.38 (0.26), 106 informative |

By boss (win beyond the heuristic; two-turn / heuristic parent win): hexaghost 81 starts (0.65 / 0.59) ritual2 -0.039, hp0.8 -0.001; slime_boss 88 (0.87 / 0.78) ritual2 -0.017, hp0.8 -0.074; the_guardian 90 (0.73 / 0.65) ritual2 +0.003, hp0.8 -0.036.

**Read by the charter** (`lane/boss-cost-two-turn`): go needs ritual2 or hp0.8 below the parent by 2 se on both columns or by 3 se on one, with the parent edge above 2 se. The parent edge is 5.8 se (win) and 5.3 se (odds), so the bench can show a boss cost at this size. Ritual2 is under 1.1 se on both columns; hp0.8 is 2.4 se on the win column and 1.5 se on odds. Neither meets the bar: **stop**.

**Why hp0.8 reads lower on the win column and not on odds.** HP x0.8 makes bosses easier for both players (+0.118 and +0.156): it pushes the starts the product already wins toward 1, where the stronger player has less room to gain than the heuristic. That is the shrinkage `yardstick/novelty-read` (2) names, and the per-boss split shows it: the cost sits on slime_boss, where the product's parent win rate is already 0.87 (-0.074), and is nil on hexaghost (0.65, -0.001). The odds column, which removes that squeeze, leaves -0.38 at 1.5 se. Stage A's hp0.8 row (-0.030 (0.010) on 66 starts) had the same direction and the same ceiling, so the two agree on a win-column squeeze, not on a product weakness. Ritual2's stage A row (-0.036) shrank to -0.017 on fresh starts: one parent draw, as `yardstick/novelty-read` rule (a) expected.

**Cost.** The job ran 5.96 h at 3 threads, about 17.9 thread-h against an estimate of 9 and a cap of 14 (the lane's own count reached 14.4 at 12:32 with the job 93% done): two-turn boss games ran at about 41 thread-s each, twice the 20 thread-s taken from job 0113's pace (0113 mixed elite games, which are shorter). The read finished; the overrun is recorded rather than read as the charter's fail branch, which is for a read that cannot finish.

**What it changes.** The monsters rung costs the two-turn product nothing measurable on any stage A modifier: `decision/no-mutated-monster-burst` stands without its open boss rows, `novelty-gated-leaf`, `future-inputs` and a Ritual 2 burst read two turns deep stay closed by this route, and goal 1's CPU moves to the cards rung (lane yardstick-cards) and generated enemies. For estimates: price two-turn boss games at about 40 thread-s, not 20.

## Stage B two turns deep, final at 200 of 200 starts: nothing beyond the heuristic at 2 se on any pattern modifier; the Thorns stack on elites is now -0.034 (0.011); the heuristic is an unadapted reference (job 0113 complete, with 0112; read 14:40 2026-11-05, navigator 7341b88a)

Job 0113 ended at 14:35 (600 min at 3 threads; its last three starts were boss starts and took 33 min). Read with `mutate_monsters.py read results/mutate/a.json`; the two-turn-minus-heuristic contrast was computed as in the 141-start read (paired by start, the parent's contrast taken out; `mutate_monsters.outcome`'s win rate over the same rows).

| modifier | two turns, change from parent | verdict | two-heur, all (200) | elites (134) | bosses (66) |
|---|---|---|---|---|---|
| weakhit1 | -0.084 (0.014) | harder | -0.012 (0.012) | +0.000 (0.010) | -0.036 (0.031) |
| dmg0.8 | +0.046 (0.012) | easier | -0.018 (0.010) | +0.000 (0.005) | -0.055 (0.029) |
| split | -0.016 (0.008) | harder (2.0 se; level at 141) | -0.014 (0.008) | -0.005 (0.006) | -0.032 (0.020) |
| weakhit1-dmg0.8 (the pair) | -0.016 (0.008) | harder (2.0 se) | -0.013 (0.009) | -0.002 (0.003) | -0.034 (0.025) |
| weakhit1-dmg0.8+split | -0.009 (0.009) | level | -0.001 (0.012) | +0.001 (0.009) | -0.004 (0.032) |
| weakhit1-dmg0.8+thorns2-hp0.9 | -0.110 (0.017) | harder | -0.026 (0.012) | -0.034 (0.011) | -0.011 (0.028) |

- *Against the 141-start read:* no two-turn change moved by more than 1 se; every two-turn se is at or under 0.017. Beyond the heuristic every modifier is within 1.8 se over all fights (it was 1.6). split's verdict moves from level to harder at exactly 2.0 se, and its two-heur from -0.004 to -0.014 (1.75 se).
- *Bosses still lean one way* (-0.032 to -0.055 on four single modifiers, each under 2 se): all are read against the same parent draw of 4 seeds on 66 starts, the signature the fresh-start boss read did not confirm for stage A (`measurement/boss-cost@two-turn`). Not a finding.
- *The reactive-stack lead on elites* is -0.034 (0.011) for the Thorns stack (3.1 se; -0.031 at 141 starts) beside stage A's metal4-hp0.85+sharp2-hp0.9 at -0.030 (0.012). Lane adapted-two-turn's step 1 (job 0152) re-reads both on 272 elite starts they were not found on.
- *HP lost beyond the heuristic on elites is not a clean column when wins fall.* It reads +1.98 (0.58) on sharp2, +2.17 (0.52) on thorns2 and +3.2 to +3.4 on the two reactive stacks, but a loss is counted as the whole entry HP, so a player that loses less HP on the parent (the product) is charged more per new loss than the heuristic is. With wins down 0.14-0.16 for both players, part or all of it can follow from that accounting (not separated here), so it is not read as a cost.
- *The reference.* On Three Sentries (43 starts) SharpHide 2 costs the heuristic -0.262, the one-turn net -0.477 and the product -0.279: "nothing beyond the heuristic" there means level with a player that has no term for the power either. What an adapted player wins on the same fights is lane adapted-two-turn's step 2 (job 0154; decisions "After boss-cost-two-turn").

**What it changes.** `measurement/mutated-monsters@stage-b` is re-set to these rows; the stage A, stacking and stage B burst facts read from the same file are unchanged (their rows were complete before 0113) and confirmed against this read.

## Adapted two turns deep: the 399-game SharpHide burst beats the product on reactive powers (HP lost -1.46 (0.64) on sharp2, -1.61 (0.64) on thorns2, never trained; parent +0.29 (0.38)); the go bar is met as a lead, confirmed on fresh starts next (adapted-two-turn lane step 2; 0154 against a.json; read 17:00 2026-11-05, lanes 19324dbf)

Job 0154 played the SharpHide burst net (`runs/2026-11-04-adapt-sharp-g133-s1-5ad1c9c/model.pt`,
trained on fights 200-332, so these starts were never trained on) two turns deep
(`--two-net`) on the 134 elite starts of positions 0-199 at 4 seeds, the same
starts and seeds as the product's games in `results/mutate/a.json`; out
`results/mutate/adapted-two.json`. Read paired by start, se over starts
(an ad hoc pairing of the two files' `two` rows; `compare` reads only `one`).

| content | product win / HP lost | adapted win / HP lost | adapted minus product, win | HP lost |
|---|---|---|---|---|
| parent | 0.996 / 14.2 | 0.991 / 14.5 | -0.006 (0.007) | +0.29 (0.38) |
| sharp2 | 0.881 / 32.9 | 0.907 / 31.4 | +0.026 (0.013) | -1.46 (0.64), 2.3 se |
| thorns2 | 0.931 / 31.2 | 0.944 / 29.5 | +0.013 (0.010) | -1.61 (0.64), 2.5 se |
| metal4-hp0.85+sharp2-hp0.9 | 0.871 / 29.0 | 0.918 / 26.4 | +0.047 (0.015) | -2.54 (0.63), 4.0 se |

Charter go: the adapted player beats the product by 2 se on HP lost on
sharp2 and on thorns2, with the parent within 1 se (0.8 se on both
columns). Win rate on sharp2 sits at exactly 2.0 se, so the go stands on
the HP column.

Beyond the heuristic (`yardstick/novelty-read` column 3; mod minus parent,
player minus heuristic, a.json's heuristic games at 8 seeds), HP lost:
the product pays +1.98 (0.58) on sharp2, +2.17 (0.52) on thorns2 and
+3.24 (0.57) on the stack; the adapted net pays +0.22 (0.50), +0.26
(0.52) and +0.41 (0.54). On wins the product is level with the heuristic
on the singles and -0.030 (0.012) on the stack; the adapted net is
+0.02 to +0.035 above it. So two-turn search alone leaves an HP cost of
about 2 HP per elite fight on powers that punish attacking. The
heuristic column shows this cost in HP but not in wins, and a.json's
read missed it because it looked at wins. About 400 games remove
almost all of it.

By encounter (HP lost, adapted minus product): Lagavulin carries the
gain (-4.1 sharp2, -4.8 thorns2, -5.1 stack, 43 starts), Nob is smaller
(-1.3, -2.5, -2.5, 48 starts), and Three Sentries goes the other way
(+0.9, +2.6, -0.0, 43 starts). One turn deep, the burst gained most on
Sentries (`measurement/adaptation-curve`). Two turns deep, the search
already handles Sentries, and the net helps against the big single
punisher, where planning around the reflected damage takes longer than
the horizon.

Doubts: one training seed of the burst; 134 starts; the two singles
pass at 2.3 and 2.5 se and share one parent draw (`yardstick/novelty-read`
rule a). So this is a lead. What it changes: `decision/no-mutated-monster-burst`
("the reactive powers cost the product nothing") rested on the heuristic
as zero, and now looks wrong in HP. A burst is a candidate product lever
for new mechanics. Next: the charter's step 3, the same adapted player on
the 272 fresh elite starts at positions 400-799 at 2 seeds, against job
0152's product games, pooled with this read (decisions "Adapted two turns
deep: confirm the go on fresh starts before the close").

## Fresh elite starts: the product pays about 2 HP per fight beyond the heuristic on every reactive modifier (+1.75 to +2.66, each 3.5-5 se), but not in wins; the reactive-stack win lead holds for the Thorns stack only (-0.025 (0.009)) and not for the SharpHide stack (-0.000 (0.010)) (adapted-two-turn lane step 1; 0152; read 18:40 2026-11-05, lanes 1461c7f0)

Job 0152 played the product (two) at 2 seeds and the heuristic at 8 seeds
on the 272 elite starts at positions 400-799 (87 Nob, 95 Lagavulin, 90
Three Sentries; no burst net trained on them), parent plus sharp2,
thorns2 and the two reactive stacks; out `results/mutate/fresh-elites.json`.
Read paired by start (key `i`, `floor`), se over starts, with the same ad hoc
pairing as step 2 (it reproduces step 2's numbers on `a.json` exactly).
Column: two minus heuristic of (modifier minus parent), the
`yardstick/novelty-read` column 3.

| content | product win / HP lost | beyond the heuristic, win | HP lost | step 2's starts 0-399, HP lost |
|---|---|---|---|---|
| parent | 0.983 / 13.4 | (raw +0.006 (0.004)) | (raw -2.02 (0.31)) | (raw -1.53 (0.38)) |
| sharp2 | 0.868 / 30.8 | -0.002 (0.009) | +1.75 (0.49), 3.6 se | +1.98 (0.58) |
| thorns2 | 0.910 / 29.0 | -0.009 (0.009) | +2.16 (0.50), 4.3 se | +2.17 (0.52) |
| metal4-hp0.85+sharp2-hp0.9 | 0.892 / 26.4 | -0.000 (0.010) | +2.45 (0.55), 4.5 se | +3.24 (0.57) |
| weakhit1-dmg0.8+thorns2-hp0.9 | 0.932 / 22.8 | -0.025 (0.009), 2.8 se | +2.66 (0.51), 5.2 se | - |

Why: on the parent the product loses 2.0 HP less than the heuristic per
elite fight; on every reactive modifier that edge is gone (raw two minus
heuristic -0.27 to +0.65 HP). Two-turn search does not keep its HP edge
when an enemy punishes attacking; it still wins as often as the
heuristic. The HP finding of step 2 replicates on new starts at about the
same size, so it is no longer a draw of one parent: the zero-shot cost of
reactive powers to the product is about 2 HP per elite fight. By
encounter (HP, beyond the heuristic): Nob +0.65 to +1.63 (all under 2 se),
Lagavulin +1.82 to +4.41 (Thorns and the Thorns stack largest), Three
Sentries +1.25 to +2.83. On wins only the Thorns stack shows a cost, and
it sits on Lagavulin (-0.054 (0.023)).

The reactive-stack lead (`measurement/mutated-monsters@stage-b`: stacks
holding a reactive power cost the product about 0.03 wins beyond the
heuristic on elites) holds only if both stacks are at 2 se on fresh
starts (job note). The Thorns stack repeats (-0.025 (0.009) against
-0.034 (0.011)); the SharpHide stack does not (-0.000 (0.010) against
-0.030 (0.012)). So the lead fails as stated: it was half a draw of the
0-399 starts. What is real is the HP column, on singles and stacks alike.

Doubts: the product's two seeds against the heuristic's eight; HP lost
counts a loss's whole entry HP, but the win columns here are level, so
the HP column is not a loss artefact except on the Thorns stack.

What it changes: the yardstick for "beyond the heuristic" on reactive
powers should read HP, not wins (a.json's win read missed it twice).
These product games are step 3's control. An interim look at job 0156
(167 of 272 starts, adapted minus product): sharp2 HP -0.36 (0.69),
thorns2 -0.53 (0.75) raw, but the adapted net loses +0.96 (0.36) HP more
on the parent (step 2: +0.29 (0.38)), so its gain beyond the parent is
-1.3 to -1.5 (about 0.7) while retention may fail the charter's
"parent within 1 se". Step 3's final read at 272 starts decides.

## Adapted two turns deep, confirmed on fresh starts: pooled over 406 elite starts the 399-game SharpHide burst beats the product on wins on sharp2 +0.025 (0.008) and thorns2 +0.013 (0.006), parent wins level; it gains about 1.1 HP on the reactive powers and loses 0.60 (0.23) HP on unchanged fights (adapted-two-turn lane step 3; 0156 with 0152, pooled with 0154 and a.json; read 19:15 2026-11-05, lanes 1461c7f0)

Job 0156 played the burst net (`--two-net`) on the 272 fresh elite starts
at positions 400-799 at 2 seeds, the same starts and seeds as job 0152's
product games (`results/mutate/fresh-elites.json`, `two` rows); out
`results/mutate/adapted-two-fresh.json`. Paired by start (`i`, `floor`), se
over starts; pooled with step 2 (0154 against `a.json`, 134 starts at 4
seeds) as one list of 406 per-start differences (the two sets of starts
are disjoint). Adapted minus product:

| content | fresh 272: win | fresh 272: HP lost | pooled 406: win | pooled 406: HP lost |
|---|---|---|---|---|
| parent | +0.004 (0.003) | +0.75 (0.28) | +0.001 (0.003), 0.2 se | +0.60 (0.23), 2.6 se |
| sharp2 | +0.024 (0.011), 2.2 se | -0.97 (0.53) | +0.025 (0.008), 2.9 se | -1.13 (0.41), 2.8 se |
| thorns2 | +0.013 (0.008) | -0.77 (0.57) | +0.013 (0.006), 2.1 se | -1.05 (0.44), 2.4 se |
| metal4-hp0.85+sharp2-hp0.9 | +0.022 (0.011) | -1.29 (0.56) | +0.030 (0.009), 3.4 se | -1.70 (0.43), 4.0 se |

The bar (decisions "Adapted two turns deep: confirm the go on fresh
starts before the close"): the fresh starts alone keep both singles' HP
gain above zero (yes: -0.97 and -0.77), and the pooled read stays at 2 se
on either single with the parent within 1 se. On wins it does: sharp2 at
2.9 se, thorns2 at 2.1 se, the parent at 0.2 se. On HP the singles pass
2 se but the parent does not stay within 1 se: the burst loses 0.60 HP
per unchanged elite fight (2.6 se; step 2 alone +0.29 (0.38), fresh
alone +0.75 (0.28)). So the go stands on the win column, and the HP
column carries a retention cost of about a third of the gain.

By encounter (pooled, HP lost): Lagavulin carries the gain (-3.9 sharp2,
-4.3 thorns2, -4.3 stack, all at 5 se and more; wins +0.025 to +0.040),
Nob gains smaller (-1.2, -1.6, -1.5), and Three Sentries goes the other
way (+1.7, +2.9, +0.8 HP; the parent there +0.83 (0.36)). The burst
trained on all three elites; against Sentries, where the product's
two-turn search already plays the reflected damage, the burst's net is a
worse leaf. Against Lagavulin, a single big punisher, it is better.

Why the go holds at fixed n and not as luck: the HP cost the product pays
beyond the heuristic replicated on the fresh starts at the same size
(`measurement/reactive-cost@fresh-elites`), and the burst's gain on
fresh starts has the same sign and about 0.7x the size of step 2's on
both singles and the stack. Doubts: one burst training seed; the parent
cost is real, so a burst as a product lever needs mixed-in parent games
or a guard that keeps retention.

What it changes: `decision/no-mutated-monster-burst` ("the reactive powers
cost the product nothing") is wrong in wins and HP against an adapted
player: two-turn search alone leaves a zero-shot cost of about 0.02 wins
and 1-2 HP per elite fight on powers that punish attacking, which about
400 games remove at a 0.6 HP parent cost. `cause/novelty-is-horizon`'s
exit "lane adapted-two-turn's go" is reached. Both are the navigator's to
re-set; the lane closes with a wake.

## Burst nets on the headline decks' boss fights, one turn deep: a fine-tune of 400-1600 games moves wins on the two bosses the net never trained on by -0.054 to +0.034 (the 1602-game SharpHide burst +0.034 (0.008) Guardian, +0.031 (0.010) Hexaghost; the stat burst -0.054 (0.012) Hexaghost) and on Slime Boss by at most +0.012; one training seed each, so a lead (navigator probe; 0157-0160; read 19:25 2026-11-05, navigator 2ef20aae)

Why it was run: every mutated-monster burst trains on the bench's elite and
boss fights (`finetune.py`, fights [200, 200 + games) of the product file's
1471 elite and boss fights), so each burst net has already played patched
games against Hexaghost and the Guardian, the two bosses the 10-29 net
never trained on and where 127 of the product's 140 boss deaths are
(`cause/boss-deaths`). The replay costs minutes and needs no code: each
burst net as `boss_replay.py play --player <net>@hpb0.01 --seeds 4` on the
474 boss fights of the headline file (the decks the product built) at HP
30-80, the same seeds as the product net's replay
(`results/boss_replay/net1029-hpe0.01-two-starter-simboss-2026-10-29-seed-check-r2-s1-1a789b2-hpb0.01-12a77a-55cb.json`).
Win rate, burst net minus the 10-29 net, mean over the six HP levels and
four seeds, paired by deck, se over decks:

| burst net (games against patched Guardian / Hexaghost / Slime Boss) | Guardian (148 decks, control 0.558) | Hexaghost (161, 0.642) | Slime Boss (165, 0.886) | all 474 |
|---|---|---|---|---|
| SharpHide 1602 games (177 / 159 / 180) | +0.034 (0.008), 4.5 se | +0.031 (0.010), 3.2 se | +0.012 (0.005) | +0.025 (0.004) |
| SharpHide 399 games (45 / 36 / 51) | -0.006 (0.008) | +0.005 (0.007) | +0.005 (0.004) | +0.001 (0.004) |
| stage B 399 games (weakhit1, dmg0.8, split; 45 / 36 / 51) | +0.032 (0.009), 3.7 se | +0.009 (0.011) | +0.004 (0.005) | +0.014 (0.005) |
| stat 400 games (hp0.8, hp1.25, str2, hp1.3-str-1; 48 / 36 / 48) | -0.003 (0.009) | -0.054 (0.012), -4.4 se | +0.009 (0.005) | -0.016 (0.006) |

Checks. The 1602-game net trained on the boss fights of sequences 66-248
(patched monsters, the cell deck, not the built deck): on the 196 Guardian
and Hexaghost decks of sequences outside that range it gains +0.033
(0.007), on the 112 inside +0.030 (0.011), so the gain is not memory of
those fights. The one-turn cell gauntlet (0-499, `results/gauntlet/adapt*`)
shows the same signs at a quarter of the precision: Guardian +0.044
(0.036) for the 1602-game net, +0.065 (0.037) for stage B 399; Hexaghost
-0.069 (0.032) for the stat burst.

What it says, and what it does not. The se here is over decks: it says
each net's difference from its parent is real play, not replay luck. It
does not say the difference comes from what the burst trained on: each row
is one training seed, and the training-seed sd of a boss win rate on
bosses the net never trained on is 0.02-0.04 (the three seed-check nets'
leads over the heuristic: Hexaghost +0.084, +0.077, +0.047; the Guardian
+0.036, +0.057, +0.111; Slime Boss, trained on, +0.139, +0.145, +0.128,
"Boss lead per boss" above). Read with that sd, the table has one robust
statement: the leaf's play on Hexaghost and the Guardian is loosely held.
A fine-tune of a few hundred games on other content moves it by three to
five hundredths either way, four times as far as it moves Slime Boss,
which the net trained on. The direction of each row is a lead: stat
shifts (Strength +2 on Hexaghost among them) cost Hexaghost wins; games
against patched bosses with a mechanic gain on the Guardian.

What it changes. (1) A burst's retention needs this read beside the cell
gauntlet: the stat burst's -0.032 clears were Hexaghost wins, and the
replay shows it at 4.4 se in five minutes. (2) The backlog's Hexaghost
burst becomes a burst of official Guardian and Hexaghost games
(`unseen-boss-burst`): the two bosses are where the leaf is least pinned
down and where the product dies; the replay is its one-turn screen, read
on two training seeds. Whether a one-turn gain reaches the two-turn
product is open: on reactive powers about a third of the one-turn win gain
did (`measurement/adapted-two@elites`).

Added 19:35 the same run (jobs 0161, 0162): the two seed twins of the
10-29 net (`seed-check-r2-s101`, `-s201`, same recipe, other training
seeds) on the same replay at `@hpb0.01`, minus the 10-29 net (s1):

| seed twin | Guardian | Hexaghost | Slime Boss | all 474 |
|---|---|---|---|---|
| s101 | +0.011 (0.007) | -0.033 (0.009) | -0.006 (0.004) | -0.010 (0.004) |
| s201 | +0.020 (0.006) | -0.009 (0.006) | -0.015 (0.005) | -0.002 (0.003) |

So on the headline decks the training-seed sd of a boss win rate is about
0.010 on the Guardian, 0.017 on Hexaghost and 0.008 on Slime Boss (three
seeds each), smaller than on the tight cells quoted above (0.02-0.04).
Against that spread the burst rows are more than seed luck: the 1602-game
SharpHide net's +0.034 on the Guardian is over three seed sd and its
+0.031 on Hexaghost sits on top of the best of the three seeds there; the
stat burst's -0.054 on Hexaghost is three seed sd down. A fine-tune's
seed spread may differ from a full training's, so the directions stay
leads, but the "loosely held" reading is now measured: fine-tunes on
other content move unseen-boss play by two to three times what a change
of training seed does. The product's net (s1) is the worst of the three
seeds on the Guardian and the best on Hexaghost.

Added 19:50 the same run (jobs 0163-0166): the mean of the three seed
nets as one evaluator against each member alone, without an HP price (an
ensemble spec takes no `@hpb` today), same replay. Ensemble minus the mean
of its members: Guardian +0.007 (0.004), Hexaghost +0.009 (0.004), Slime
Boss -0.000 (0.002), all +0.005 (0.002). Averaging helps only on the two
bosses the nets never trained on, as a seed spread twice Slime Boss's
predicts, but by under a hundredth; a third of that two turns deep
(`cause/leaf-gain-third`) is nothing a read could see. The 11-01
no-change on the ensemble stands, now with the unseen bosses read.

## Unseen-boss bursts, one turn deep: training on Guardian and Hexaghost games lifts the Guardian (+0.030 to +0.055 on all four nets) but not Hexaghost (-0.003 to +0.015); Guardian plus Hexaghost +0.016 to +0.034, under the 0.03 fail bar on one seed of each size, so the lane fails; retention holds (unseen-boss-burst lane step 2; 0170-0181; read 20:45 2026-11-05, lanes 25f7f4c2)

Four fine-tunes of the 10-29 net (`product/net`'s net) on one-turn games
by that net @hpb0.01 against official Guardian and Hexaghost (varied
decks, entry HP 40-100% of max, game_seed 41, none a bench start; about
half the games won, 8.3 turns each), 400 and 1600 games, training seeds
1 and 2 (0170-0173, val MSE 0.227/0.226 and 0.209/0.207). Each read one
turn deep @hpb0.01 on the 474 boss fights of the headline file (HP
30-80 x 4 seeds, the 10-29 net's seeds), win rate minus the 10-29 net
paired by deck, se over decks (0174, 0176, 0178, 0180), and on the
one-turn cell gauntlet 0-499 against `results/gauntlet/net1029-hpb0.01.json`
at fixed n 500 (0175, 0177, 0179, 0181).

| net | Guardian (148) | Hexaghost (161) | G+H | Slime Boss (165) | cells dHP | cells clears |
|---|---|---|---|---|---|---|
| 400 s1 | +0.030 (0.007) | +0.013 (0.010) | +0.021 (0.006) | +0.012 (0.005) | +1.59 (0.46) | +0.030, z +2.1 |
| 400 s2 | +0.035 (0.007) | -0.002 (0.009) | +0.016 (0.006) | +0.008 (0.004) | +1.18 (0.49) | +0.012, z +0.8 |
| 1600 s1 | +0.055 (0.008) | +0.015 (0.011) | +0.034 (0.007) | +0.007 (0.005) | +0.78 (0.50) | +0.014, z +0.9 |
| 1600 s2 | +0.039 (0.007) | -0.003 (0.009) | +0.017 (0.006) | +0.005 (0.004) | +0.42 (0.46) | +0.010, z +0.7 |

**Verdict by the charter.** Fail: one seed of each size gains under 0.03
on Guardian plus Hexaghost (400 s2 +0.016, 1600 s2 +0.017; 400 s1 +0.021
too). No size reaches the go bar (+0.05 on both seeds), and the two-seed
means (+0.019 and +0.026) are far under the 0.07 a two-turn read needs.
Retention holds on every net: cells +0.4 to +1.6 HP, clears z > 0, Slime
Boss +0.005 to +0.012 (the 400 s1 cell pass at +1.59 HP is one seed, and
its twin and the larger bursts are smaller: a lead at most).

**Why.**
- *The Guardian gain is mostly a generic burst effect.* Bursts on other
  content moved the Guardian by about as much (the 1602-game SharpHide
  burst +0.034, the 399-game stage B burst +0.032;
  `measurement/burst-bosses@replay`). Here 400 games give +0.030/+0.035
  and 1600 games +0.055/+0.039: training on the boss itself adds perhaps
  a hundredth or two over any burst, and quadrupling the games adds
  +0.015 on the mean. The gain sits at entry HP 40-60 (+0.04 to +0.09
  per level, where the 10-29 net wins 0.25-0.71), next to nothing at 30
  (0.07 base) or 80 (0.95): it is a better margin where the fight is
  open, not a new way to win from low HP.
- *Hexaghost does not move at all.* -0.003 to +0.015 on 800 or 3200
  training fights of its own, inside the 10-29 seed twins' spread (sd
  0.017), and smaller than the SharpHide burst's +0.031, a burst on other
  content. The training games were informative (Hexaghost won
  about 0.52, so the labels split), so the net fails to use them: a
  one-turn leaf with real-outcome labels does not learn what decides
  Hexaghost. Candidates, unchecked: the net's inputs do not show the
  state that decides the fight (Hexaghost's move cycle position and
  Divider's dependence on the player's HP; Burn's row kind was never
  checked, backlog `unseen-boss-burst`), or Hexaghost's deck ceiling
  (19 of 161 headline decks win 2 of 4 or fewer at 80 HP) leaves little
  that play can change.
- *More games barely help.* 1600 over 400: +0.007 Guardian plus
  Hexaghost on the seed mean, while cells lose about 0.8 HP of the small
  cell gain: the leaf saturates on this source within a few hundred
  games, as one-turn labels did on trained content
  (`cause/teacher-equals-student`).

**What it changes.** Goal 1's games-to-adapt number on a whole unseen
enemy is not reached with this recipe: a few hundred to 1600 one-turn
games do not teach the 10-29 layout a boss it cannot already read
(Hexaghost), and what they do teach (the Guardian) any burst teaches. A
boss burst is no product candidate (two-turn read not run, below its
detectable effect). Reopen if the net gains inputs for the boss state
(move-cycle position, HP-scaled attacks, Burn rows), the source becomes
two-turn games (a stronger teacher), or a probe shows Hexaghost decks
have headroom that play can reach (backlog `hexaghost-headroom`).

## Boss replays re-read by boss: on the same decks at the same entry HP the second turn of search wins +0.083 (0.024) more Hexaghost fights, +0.054 (0.026) Guardian, +0.017 (0.016) Slime Boss; decks differ by 0.2-0.3 in win rate at fixed HP on both unseen bosses; Guardian games add about +0.026 over bursts on other content (navigator re-read, 0 CPU; 20:50 2026-11-05, navigator e63fdaaa)

A re-read of files already on disk, after `lane/unseen-boss-burst` failed
(the section above). No job ran.

**Depth by boss.** The boss replay file of the 10-29 net
(`results/boss_replay/net1029-hpe0.01-two-starter-simboss-2026-10-29-seed-check-r2-s1-1a789b2-hpb0.01-12a77a-55cb.json`)
holds, for each of the 474 decks the plain two-turn product built on the
headline (`results/gauntlet/net1029-hpe0.01-two-starter-simboss.json`,
0.804 clears), the product's own boss result at its arrival HP (`hp_obs`,
`won_obs`: one game, two turns deep, @hpe0.01) and the one-turn replay of
the same deck at HP 30-80 x 4 seeds (@hpb0.01). Two turns minus one turn
per deck: `won_obs` minus the replay's win rate interpolated between the
two nearest HP levels; se over decks. Every deck is used, so nothing is
selected on the outcome; the seeds are not shared and the HP price differs
(@hpe against @hpb), so this is a lead on the size, not a paired read.

| boss | decks | two turns | one turn, same deck and HP | difference |
|---|---|---|---|---|
| Hexaghost | 161 | 0.820 | 0.737 | +0.083 (0.024) |
| the Guardian | 148 | 0.764 | 0.709 | +0.054 (0.026) |
| Slime Boss | 165 | 0.952 | 0.935 | +0.017 (0.016) |

Hexaghost by arrival HP: under 40 +0.031 (0.112, n 13), 40-49 +0.164
(0.098, n 14), 50-59 +0.142 (0.057, n 36), 60-69 +0.043 (0.046, n 39),
70 and over +0.066 (0.031, n 59). The Guardian: 40-49 +0.132 (0.088),
50-59 +0.011 (0.109), 60-69 +0.109 (0.040), 70 and over +0.038 (0.021).

**Decks at a fixed HP (one turn deep).** Between-deck spread of the win
rate with the sampling noise of 4 seeds taken out (sd over decks):
Hexaghost 0.21 / 0.24 / 0.29 / 0.26 / 0.19 / 0.16 at HP 30 / 40 / 50 / 60
/ 70 / 80 (win 0.33 to 0.90); the Guardian 0.06 / 0.18 / 0.24 / 0.21 /
0.13 / 0.09 (win 0.07 to 0.95); Slime Boss 0.19 / 0.14 / 0.13 / 0.07 /
0.03 / 0.03. At 50 HP 21 of 161 Hexaghost decks win 0 of 4 and 46 win 4
of 4; the Guardian 25 and 22 of 148.

**Bursts on the Guardian, all ten nets beside each other** (win rate
minus the 10-29 net, paired by deck; recomputed from the replay files,
matching `measurement/burst-bosses@replay` and
`measurement/unseen-boss-burst@replay`): bursts on other content +0.034
(SharpHide 1602), -0.006 (SharpHide 399), +0.032 (stage B 399), -0.003
(stat 400), mean +0.014; bursts on Guardian and Hexaghost games +0.030,
+0.035, +0.055, +0.039, mean +0.040; the 10-29 net's seed twins +0.011 and
+0.020 (the product's net is the lowest of the three seeds on the
Guardian). Hexaghost: other bursts +0.031, +0.005, +0.009, -0.054; boss
bursts +0.013, -0.002, +0.015, -0.003; twins -0.033, -0.009.

**What it says.**
- *Play matters most at Hexaghost.* The second turn of search wins more
  there than at either other boss, most of it between 40 and 60 HP. So
  the Hexaghost bursts did not fail for want of anything to learn: the
  one-turn leaf with outcome labels does not pick up what one more turn
  of search finds. Whether a third turn finds more is the open half
  (backlog `hexaghost-headroom`).
- *The deck is as large a lever as the fighter on both unseen bosses.*
  At the HP where each boss is open, decks differ by 0.2-0.3 in win rate,
  two to three times what the second turn of search adds. That lever is
  the card chooser, which waits for Act 1's cards (direction "Avoid";
  backlog `own-boss-chooser`).
- *Guardian games do teach the Guardian a little.* Two of four bursts on
  other content lift the Guardian as much as the weakest boss burst and
  two do not move it; the four boss bursts all lift it, by about +0.026
  more on the mean, and part of any fine-tune's Guardian gain can be the
  product's net coming back from its low seed draw (twins +0.011,
  +0.020). The lane's fail stands: about +0.03 one turn deep is under
  +0.01 two turns deep (`cause/leaf-gain-third`).
- *The three-turn boss probe needs no code but more fights.*
  `scripts/analysis/depth_probe.py play --kind boss --arm three` already
  plays the headline control's bosses entered at 50-69 HP: 203 fights on
  sequences 0-499 (Hexaghost 77, 61 won; the Guardian 63, 51 won; Slime
  Boss 63, 62 won). On 77 Hexaghost fights a paired win difference has an
  se near 0.04, so the smallest effect the owner's rule lets a run look
  for is about 0.11, and half of the first-to-second-turn gain in that
  band (about +0.09) is +0.045: the probe does not pass the rule on one
  book. It needs both books' Hexaghost arrivals and a per-boss filter (a
  few lines), about 30 thread-h three turns deep.

## Sequential bursts, one turn deep: two 399-game bursts in a row keep the first's gain (SharpHide then stage B keeps 0.74 of the sharp2 gain, +0.059 (0.013); stage B then SharpHide keeps all of it, +0.080 (0.014)), and both nets play official content as well as or better than the parent; one training seed per order, so a lead (sequential-bursts lane step 1; 0184-0191; read 21:40 2026-11-05, lanes 1b8f9222)

Question (`lane/sequential-bursts`): goal 1 adds content one pack at a
time. If the second burst undoes the first, every pack needs its own
net. Two orders were trained, each from an existing 399-game burst with
the other burst's existing config (no code; configs
`seq-sharp-then-stageb-g133-s1` and `seq-stageb-then-sharp-g133-s1`,
copies renamed): A = the SharpHide burst
(`runs/2026-11-04-adapt-sharp-g133-s1-5ad1c9c`) fine-tuned on stage B's
games (`runs/2026-11-05-seq-sharp-then-stageb-g133-s1-edf6d3f`); B =
the stage B burst (`runs/2026-11-05-adapt-stageb-g133-s1-ea0de42`)
fine-tuned on SharpHide's games
(`runs/2026-11-05-seq-stageb-then-sharp-g133-s1-ea5fcbd`). Each burst
took 90 seconds (the games datasets were cached). All reads were one
turn deep, @hpb0.01 where the reader takes it.

**Measure: gain on the modified elites** (`mutate_monsters.py play
--starts 200 --seeds 8 --players one`, `compare` against the 10-29 net
in `results/mutate/a.json`; win rate, se):

| net | sharp2 | thorns2 | weakhit1 |
|---|---|---|---|
| SharpHide burst alone (`burst133-s1.json`, `-transfer.json`) | +0.080 (0.015) | +0.066 (0.014) | +0.013 (0.007) |
| stage B burst alone (`stageb133-s1.json`) | - | - | -0.001 (0.011) |
| A: SharpHide, then stage B | +0.059 (0.013) | +0.073 (0.012) | +0.022 (0.007) |
| B: stage B, then SharpHide | +0.080 (0.014) | +0.067 (0.012) | +0.019 (0.009) |

Paired against the SharpHide burst itself on sharp2: A -0.021 (0.011),
B +0.000 (0.009). A keeps 0.74 of the sharp2 gain, which is over the
two-thirds bar (+0.053) but loses a quarter of it at 1.9 se. Thorns2 is
kept in full by both. The second burst forgets something only when it
comes second and is not SharpHide. B, whose last burst was SharpHide, is
the plain SharpHide burst on every row. WeakOnHit, the one stage B
modifier that punishes attacking, gains +0.02 in both orders against
the single bursts' +0.013 and -0.001. That is the only hint of the two
bursts adding up, and it is within 1 se of the single SharpHide burst.

**Retention: one-turn cell gauntlet 0-499** against the 10-29 net
@hpb0.01 (paired end-HP and clears, by half):

| net | end-HP all | train | held-out | clears (z) | protocol |
|---|---|---|---|---|---|
| SharpHide alone (`adapt133-s1`) | -0.07 (0.42) | +0.00 | -0.14 | +0.012 (+0.75) | - |
| stage B alone (`adapt-stageb133-s1`) | +1.14 (0.53) | +0.74 | +1.55 | +0.030 (+1.87) | - |
| A | +2.36 (0.46) | +2.45 | +2.27 | +0.028 (+1.91) | pass at 500 |
| B | +0.38 (0.55) | +0.34 | +0.41 | +0.010 (+0.60) | open at 500 |

Neither order costs anything on the cell decks, so the fail branch
(paired end-HP below -1.5) is far away. A's +2.36 HP (5 se, train and
held-out alike) is the largest one-turn cell gain any burst has shown
here and needs a second look before anyone builds on it. It is one
training seed; the stage B burst alone already gave +1.14. Bursts on
patched elites carry the official replay pool, so 800 games of burst
are also 800 games' worth of extra rehearsal steps on official states.
Treat it as a lead for a seed twin, not a gain.

**Retention: boss replay** of the 474 headline boss fights (HP 30-80 x
4 seeds), wins minus the 10-29 net paired by deck (my pairing of
`results/boss_replay/<file>` rows by index, the same as
`measurement/burst-bosses@replay`; it reproduces that fact's single-burst
values):

| net | Guardian | Hexaghost | Slime Boss | all |
|---|---|---|---|---|
| SharpHide alone (`hp-sweep-sharp399`) | -0.006 (0.008) | +0.005 (0.007) | +0.005 (0.004) | +0.001 (0.004) |
| stage B alone (`hp-sweep-stageb399`) | +0.032 (0.009) | +0.009 (0.011) | +0.004 (0.005) | +0.014 (0.005) |
| A | +0.024 (0.007) | +0.006 (0.010) | +0.013 (0.004) | +0.014 (0.004) |
| B | +0.043 (0.008) | +0.044 (0.011) | +0.010 (0.006) | +0.032 (0.005) |

No boss gets worse. B's Hexaghost +0.044 is four times its se and two
and a half times the seed sd there (0.017). That fits the earlier
reading that a few hundred games of fine-tuning move unseen-boss play by
0.03-0.05 in either direction, so it is not a gain on its own.

**Verdict by the charter's stop rule: go (bursts compose).** Both orders
keep at least two thirds of the sharp2 gain (0.74 and 1.00 of +0.080;
each order's gain is over 4 se from zero), and retention is inside the
protocol on the cell gauntlet and on the boss replay. I read "at 2 se"
as "the kept gain is significant at 2 se". The stricter reading, a lower
bound of 2 se above two thirds, no single burst could pass either
(+0.080 - 2 x 0.015 = +0.050 < +0.053). It is one training seed per
order (operating.md: a lead, not a result).

**What it changes.** Goal 1's content workflow can add packs one burst
at a time on the same net. One open cost: the order matters. A second
burst that does not rehearse the first's mechanic gives back about a
quarter of it (A, -0.021 at 1.9 se), so a pack chain should replay the
previous packs' games in each burst (the same rehearsal idea as
`burst-recipe`). Two leads for a seed twin, neither enough to act on:
A's +2.36 HP on the cell decks and B's +0.044 on Hexaghost.

## Seed-2 burst, two turns deep: the win gain replicates (sharp2 +0.018 (0.009), thorns2 +0.015 (0.008)) but the HP gain does not (+0.32 and +0.46 HP lost, against seed 1's -0.97 and -0.77), and the parent cost doubles (+1.67 (0.39)); one burst seed is a lead, adapted columns need three (yardstick-cards step 0; 0168, 0169 with 0152 and 0156; read 22:45 2026-11-05, lanes d896a630)

Job 0168 trained the seed-2 twin of the 399-game SharpHide burst
(`configs/adapt-sharp-g133-s2.json`, best val MSE 0.178 against seed 1's
0.177); job 0169 played it two turns deep (`--two-net`) on the 272 fresh
elite starts at positions 400-799, 2 seeds, the same starts and seeds as
job 0152's product games (`results/mutate/fresh-elites.json`, `two` rows)
and seed 1's job 0156 (`results/mutate/adapted-two-fresh.json`); out
`results/mutate/adapted-two-fresh-s2.json`. Burst minus product, paired
by start (`i`, `floor`), se over the 272 starts; HP lost per elite fight
(a loss costs the entry HP):

| content | s1 win | s1 HP lost | s2 win | s2 HP lost | mean win | mean HP lost | s2 - s1 HP |
|---|---|---|---|---|---|---|---|
| parent | +0.004 (0.003) | +0.75 (0.28) | +0.004 (0.003) | +1.67 (0.39) | +0.004 (0.002) | +1.21 (0.30) | +0.92 (0.32) |
| sharp2 | +0.024 (0.011) | -0.97 (0.53) | +0.018 (0.009) | +0.32 (0.60) | +0.021 (0.009), 2.3 se | -0.33 (0.54) | +1.29 (0.34) |
| thorns2 | +0.013 (0.008) | -0.77 (0.57) | +0.015 (0.008) | +0.46 (0.60) | +0.014 (0.008), 1.8 se | -0.15 (0.55) | +1.23 (0.39) |

The bar (job 0169's note): seed 2 gains HP on sharp2 and thorns2, and the
two-seed mean stays at 2 se on sharp2 wins or HP. The second half holds
(sharp2 wins 2.3 se); the first fails: seed 2 loses HP on both singles.
So it fails: adapted columns need three burst seeds (`yardstick/twin-reads`).

Why: the seeds differ by encounter, not across the board. Seed 2 by
encounter (HP lost, burst minus product): Lagavulin still gains (sharp2
-2.39 (0.94), thorns2 -2.91 (1.11); wins +0.021, +0.042), Nob gains a
little (-1.04, -1.29), and Three Sentries costs much more than seed 1's
(+4.49 (1.21), +5.71 (1.06); the parent there +2.56 (0.75)). Seed 1 had
the same shape at a smaller Sentries cost (+1.7, +2.9 pooled). Wins move
by 0.006 or less between seeds; HP moves by 0.9-1.3, at 2.9-3.7 se of the
seed difference. Against Sentries the product's second turn already
plays the reflected damage, so the burst only changes the leaf, and how
much worse a leaf it is there is a training-seed draw. The HP column of
a burst is mostly that draw; the win column is steadier.

What it changes: `measurement/adapted-two@elites` keeps its win result
(two seeds, +0.021 sharp2 at 2.3 se on the fresh starts) and loses its HP
gain (the mean is -0.33 (0.54), not -1.1), with a parent cost of about
1.2 HP. Under the owner's one-turn rule (`decision/one-turn-comparisons`)
the adapted column is read one turn deep from now on, so no third
two-turn seed is queued; the cards rung's adapted columns train three
burst seeds when they come.

## Burst nets on the held-out cell book: the SharpHide-then-stage-B net keeps its gain on sequences 500-999 (+2.27 (0.47) paired end-HP, against +2.36 (0.46) on 0-499) and carries it to the headline setting with matched decks (+2.47 (0.53), clears +0.040 (0.016)); the seed-2 SharpHide burst loses -1.56 (0.48) there (burst-official steps 1-2; 0192-0198; read 23:15 2026-11-05, lanes 4e7486ad)

Question (lane `burst-official`): do the burst nets' retention reads on
cell sequences 0-499 flatter them, since their training fights come from
those sequences? All reads are one turn deep, on existing nets, @hpb0.01,
paired end-HP and clears at fixed n 500 by the protocol.

Step 1: the 10-29 net on sequences 500-999 as the control (0192,
`results/gauntlet/net1029-hpb0.01-b500.json`, clears 0.686, end-HP 26.9;
on 0-499 it clears 0.634, end-HP 24.5, so the second book is a little
easier), then five burst nets --against it (0193-0197). Paired end-HP
(se) and clears (se), burst minus control:

| net | 0-499 HP | 500-999 HP | 0-499 clears | 500-999 clears | protocol 500-999 |
|---|---|---|---|---|---|
| SharpHide then stage B, s1 | +2.36 (0.46) | +2.27 (0.47) | +0.028 (0.015) | +0.018 (0.013) | pass |
| stage B then SharpHide, s1 | +0.38 (0.55) | +0.49 (0.57) | +0.010 (0.017) | +0.004 (0.014) | open |
| SharpHide 399, s1 | -0.07 (0.42) | +0.11 (0.48) | +0.012 (0.016) | -0.002 (0.012) | fail |
| SharpHide 399, s2 | no read | -1.56 (0.48) | | -0.024 (0.013) | fail |
| stage B 399, s1 | +1.14 (0.53) | +0.75 (0.54) | +0.030 (0.016) | -0.006 (0.014) | open |

(0-499 files: `seq-sharp-then-stageb-s1-hpb0.01.json`,
`seq-stageb-then-sharp-s1-hpb0.01.json`, `adapt133-s1-hpb0.01.json`,
`adapt-stageb133-s1-hpb0.01.json` against `net1029-hpb0.01.json`.)

No flattery: across the four nets read on both books the 500-999 gain is
within 0.4 HP (under one se) of the 0-499 gain, in both directions. Burst
retention reads on 0-499 stand; they don't need to move to the held-out
book. The gauntlet's own train/held-out cell halves agree (the SharpHide
then stage B net gains +2.19 on train cells and +2.34 on held-out cells
on 500-999).

One net passes the +1.0 HP bar at 2 se: SharpHide then stage B. Its gain
is HP rather than deaths on the cells: deaths by encounter are level
(Hexaghost 55 and 55, Guardian 29 and 26), HP at the boss is +1.3.

The seed-2 SharpHide burst costs official play: -1.56 (0.48) HP, clears
-0.024 (0.013); it dies more to Three Sentries (13 against 7), the same
encounter where its two-turn read lost the most HP (previous section).
Seed 1 of the same recipe is level (+0.11). So a single 399-game burst's
effect on official content is a training-seed draw of about +-1.5 HP,
and the SharpHide-then-stage-B gain is one training seed: a lead.

Step 2: that net on the headline setting with the control's deck choices
(`--match`, 0198, `match-seq-sharp-then-stageb-s1-hpb0.01-starter-simboss.json`
against `net1029-hpb0.01-starter-simboss.json`): +2.47 (0.53) paired
end-HP, clears 0.720 against 0.680, +0.040 (0.016); protocol pass at
n 500. Train cells +2.21 (0.77), held-out +2.73 (0.72). Boss deaths fall
from 107 to 89 (Guardian 47 to 39, Slime Boss 18 to 10, Hexaghost 42 to
40); elite deaths are level. So the gain carries from the cell decks to
the run's own decks and is mostly boss fights. Step 3 (own picks, 0199)
follows.

## Burst net with its own picks on the headline setting: +2.00 (0.98) paired end-HP, clears +0.034 (0.023), protocol open at n 500; boss deaths 107 to 78, early-floor deaths up; steps 4-5 queued (burst-official step 3; 0199; read 23:45 2026-11-05, lanes 4e7486ad)

The SharpHide-then-stage-B net (`runs/2026-11-05-seq-sharp-then-stageb-g133-s1-edf6d3f`)
@hpb0.01 with its own card picks on the headline setting one turn deep,
sequences 0-499, against the one-turn headline control
(`results/gauntlet/net1029-hpb0.01-starter-simboss.json`), job 0199,
`results/gauntlet/seq-sharp-then-stageb-s1-hpb0.01-starter-simboss.json`:

- paired end-HP +2.00 (0.98), clears 0.714 against 0.680, +0.034
  (0.023); train cells +1.84 (1.30), held-out cells +2.16 (1.47);
- protocol (SPRT H1 +1.5) open at n 500: z is 2.04, at the bar, so on
  its own this read is a lead, not a pass;
- deaths by floor: bosses 107 to 78 (Guardian 47 to 36, Hexaghost 42 to
  31, Slime Boss 18 to 11), floors 6-10 deaths 53 to 65 (Thugs 5 to 10,
  Looter 0 to 3, Large Slime 2 to 5); HP at the boss +2.0 (406 reach
  both).

Why: the matched read (step 2, same net, the control's decks) gained
+2.47 (0.53); with its own picks the mean is about the same and the se
twice as large, because different picks make different decks and the
pairing weakens (`cause/headline-pairing-weak`). The gain is at the
bosses, as on the matched read. The extra early deaths are new with own
picks (the matched read had elite and hallway deaths level), so the
burst net's card picks may be a little worse than the control's while
its fighting is better; 12 extra deaths in 500 is at about 1.6 se, a
thing to watch on step 4, not a result.

What it changes: by the extended charter (decisions "Lane burst-official
extended", rev 2 of `lane/burst-official`) step 3 is above zero, so
steps 4 (the confirm book 500-999, own picks, 0200) and 5 (the net two
turns deep as the product plays it, matched decks, against the headline
control, 0201) are queued together. Go needs the pooled steps 3-4 read
at +1.5 at 2 se with clears not below, and step 5 not below the control.

## Burst net with its own picks on the confirm book: +0.18 (0.96) paired end-HP, clears -0.022 (0.025); pooled with step 3 over 1000 sequences +1.09 (0.69), z 1.59, under 2 se, so the lane's go fails; step 5 (two turns deep) runs for the depth question (burst-official step 4; 0200; read 00:30 2026-11-06, lanes 4e7486ad)

The same net with its own picks on headline sequences 500-999 one turn
deep, against `results/gauntlet/net1029-hpb0.01-starter-simboss-500.json`
(job 0200, `results/gauntlet/seq-sharp-then-stageb-s1-hpb0.01-starter-simboss-500.json`):

| read | n | paired end-HP | paired clears |
|---|---|---|---|
| step 3, 0-499 | 500 | +2.00 (0.98) | +0.034 (0.023) |
| step 4, 500-999 | 500 | +0.18 (0.96) | -0.022 (0.025) |
| pooled | 1000 | +1.09 (0.69) | +0.006 (0.017) |

Step 4 by cell half: train cells +1.39 (1.24), held-out cells -1.04
(1.46). Deaths by floor: bosses 100 to 113 (Hexaghost 37 to 45, Guardian
53 to 56), elites and hallways level (Sentries 10 to 14, Nob 14 to 10).

The two books differ by 1.82 (1.37), 1.3 se: consistent with one effect
of about +1 HP read twice with own-pick noise, and not with the +2.47 of
the matched read (step 2) carrying over whole. The step-3 boss gain (107
to 78 deaths) does not repeat on 500-999 (100 to 113).

Why: with the control's decks (step 2) and on the cell decks (steps 1
and the 0-499 read) this net fights better by about 2.3-2.5 HP at 4-5 se,
on both cell books. With its own picks it gains about half that, pooled.
Two readings, not separated by these files (the gauntlet files keep no
deck lists): its picks are a little worse than the control's and give
back part of the fighting gain (the step-3 rise in floor 6-10 deaths
points this way, step 4 does not show it), or the matched read's +2.47 on
0-499 was itself on the high side of a smaller fighting gain. Either way
the own-pick gain the product would see one turn deep is about +1 HP,
under the go bar of +1.5 at 2 se, and the burst net is a lead at most.

What it changes: by the charter (`lane/burst-official` rev 2) the pooled
own-pick gain under 2 se fails the go, whatever step 5 shows. Step 5
(0201: the net two turns deep as the product plays it, the product's
decks) was queued before step 4 ended and is left to run, since the
machine has no other work queued: it reads whether a confirmed one-turn
fighting gain of about 2.4 HP reaches two turns deep
(`cause/leaf-gain-third` predicts about a third), which the navigator
needs for any later fighting-only change. Picks from the control with
fights from a burst net is not a mode the product has.

## Crossed player, one turn deep: the burst net fighting with the 10-29 net's picks gains +1.60 (0.48) paired end-HP pooled over 1000 sequences (z 3.36; +1.66 (0.68) on 0-499, +1.54 (0.67) on 500-999), clears +0.012 (0.014), so step 1 goes; crossed minus own picks +0.51 (0.69) (crossed-player step 1; 0202, 0203; read 01:50 2026-11-06, lanes 91af75fb)

The SharpHide-then-stage-B net @hpb0.01 fights and
`runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpb0.01` picks the
cards (`--chooser`), headline setting one turn deep, against the one-turn
controls of each book at fixed n 500 (jobs 0202 and 0203,
`results/gauntlet/crossed-sharp-stageb-ch-net1029-hpb0.01-starter-simboss.json`
and `...-500.json`):

| read | n | paired end-HP | paired clears |
|---|---|---|---|
| crossed - control, 0-499 | 500 | +1.66 (0.68) | +0.018 (0.020) |
| crossed - control, 500-999 | 500 | +1.54 (0.67) | +0.006 (0.018) |
| crossed - control, pooled | 1000 | +1.60 (0.48), z 3.36 | +0.012 (0.014) |
| pooled, train cells | 500 | +1.58 (0.67) | -0.008 (0.020) |
| pooled, held-out cells | 500 | +1.61 (0.67) | +0.032 (0.019) |
| crossed - own picks (0199, 0200), 0-499 | 500 | -0.35 (0.97) | -0.016 (0.023) |
| crossed - own picks, 500-999 | 500 | +1.36 (0.97) | +0.028 (0.025) |
| crossed - own picks, pooled | 1000 | +0.51 (0.69) | +0.006 (0.017) |

The same pairing script reproduces the own-pick pool of
`measurement/burst-official@own-picks` (+1.09 (0.69)), so the numbers
pair as the protocol does. Book 0-499's SPRT passed at n 500, book
500-999's stayed open; the read is the fixed-n one.

Deaths by floor (control to crossed): bosses 107 to 95 and 100 to 100;
by boss, pooled, Guardian 100 to 86 and Slime Boss 28 to 19, Hexaghost
79 to 90; elites (floor 9) 31 to 37 and 30 to 27; hallways level. The
crossed run's picks agree with the control's on 85% of offers (8249 of
9685): same chooser, but the HP and the deck it sees differ.

Why: the gain is steady, both books and both cell halves at +1.4 to
+1.8, and its se (0.48) is lower than the own-pick read's (0.69) because
the chooser is shared with the control, so the arms pair more tightly.
It sits between the own-pick gain (+1.09) and the matched read (+2.47 on
0-499): a matched read replays the control's decks exactly (a slight lean
toward the fighter under test, `how/gauntlet-read`), while here the
chooser picks for the state the burst net leaves. That resolves the last
section's two readings in part: the burst net's own picks cost about
+0.5 HP (0.69, not separated from zero), and the fighting gain the
product's own chooser would see is about +1.6 HP, not +2.4. The boss gain
is on the Guardian and Slime Boss; Hexaghost deaths rise on both books
(42 to 47, 37 to 43), as the burst net's own-pick run showed on 500-999.
One training seed: a lead for the navigator, not a promotion.

What it changes: the charter's step-1 go holds (pooled at least +1.5 at
2 se, clears not below the control on either book; +1.60 is near the
bar, but both books clear z 2 on their own). Step 2 (job 0201's command:
the net @hpe0.01 two turns deep as the product plays it, on the
product's decks, against `yardstick/headline-control`) is queued at 2
threads; it decides the lane: not below the control (paired end-HP above
-1.0, clears z above -2) is a go, below at 2 se a fail. The product is
the navigator's call either way; the product has no chooser-split mode
today.

## Crossed player, two turns deep: the burst net as the product plays it, on the product's decks, gains +1.08 (0.47) paired end-HP over 500 headline sequences (z 2.28), clears -0.006 (0.014), so step 2 passes and the lane ends on go; depth takes about half of the one-turn matched gain (+2.47) (crossed-player step 2; 0204; read 08:20 2026-11-06, lanes 51ea5bcd)

`runs/2026-11-05-seq-sharp-then-stageb-g133-s1-edf6d3f/model.pt@hpe0.01
--two-turn --line-seed --step-line` on the headline setting, sequences
0-499, replaying the headline control's card picks (`--match`), paired
against `yardstick/headline-control` at fixed n 500 (job 0204,
`results/gauntlet/match-seq-sharp-then-stageb-s1-hpe0.01-two-line-step-starter-simboss.json`;
4937 of 5458 floors matched, the rest after the arms' runs part):

| read | n | paired end-HP | paired clears |
|---|---|---|---|
| burst - control, all | 500 | +1.08 (0.47), z 2.28 | -0.006 (0.014) |
| train cells | 250 | +0.54 (0.62) | -0.004 (0.021) |
| held-out cells | 250 | +1.62 (0.72) | -0.008 (0.020) |

Clears 0.834 (control) and 0.828. HP lost per fight type, burst minus
control: hallways +0.10 (0.19), elites -1.39 (0.33), boss -0.15 (0.46);
HP at the boss 64.0 to 65.3 (466 reach both). The protocol's SPRT stayed
open at n 500; the read is the fixed-n one.

Deaths by floor (control to burst): elites (floors 6 and 9) 2+13 to 1+6,
the hallway after the second elite 6 to 15, boss 62 to 61 (Hexaghost 29
and 29, Guardian 28 and 26, Slime Boss 5 and 6). Every death on floors
8-10 in both arms entered the fight at 30 HP or less.

Why: two turns deep the burst net still loses less HP than the 10-29 net,
and nearly all of the gain is at the elites (-1.39 HP lost, 4 se), while
one turn deep most of it was at the bosses. The product's two-turn search
already plays the bosses about as well as the burst net adds, so depth
takes the boss share of the gain (the pattern of `cause/depth-saturated`
and `measurement/adapted-two@elites`). The elite saves don't become
clears: the runs the burst net carries through the second elite at low HP
die in the next hallway instead (15 against 6), so deaths move a floor
later and the clear rate stays level. The held-out half carries more of
the gain than the train half (+1.62 against +0.54, not separated at
these se). One training seed and a matched read (a slight lean toward
the fighter under test, `how/gauntlet-read`): a lead, not a promotion.

What it changes: the charter's stop rule goes (step 1 pooled +1.60 (0.48)
with clears not below on either book; step 2 above -1.0 HP and clears z
-0.42). The navigator decides the product (wake at the close). What a
product change would buy at the headline is about +1 HP of end-HP and no
clears; the second elite's low-HP survivors are where the next gain sits.

## Pattern-row bursts trained: all four fine-tunes train on the rows; validation MSE is 0.0007-0.0018 under each plain twin, inside epoch-to-epoch noise (pattern-rows-burst checkpoint "trained"; 0244-0247; read 09:00 2026-11-06, lanes f66c70a3)

The four boss bursts of unseen-boss-burst ran again with `"row_kinds": ["pattern"]`
(same source games, top, game_seed and seed). Each saved net's meta lists
`row_kinds` `triggered, threshold, held, pattern` (the plain twin's lacks
`pattern`), so the rows reached the net. No refusal or error: the charter's
"cannot train" fail branch is off.

| arm | val MSE min (epoch) | plain twin min | difference | epochs | wall |
|---|---|---|---|---|---|
| g400-s1 | 0.2217 (9) | 0.2235 | -0.0018 | 12 | 3 min |
| g400-s2 | 0.2209 (4) | 0.2218 | -0.0009 | 7 | 1 min |
| g1600-s1 | 0.2046 (7) | 0.2058 | -0.0012 | 10 | 2 min |
| g1600-s2 | 0.2051 (3) | 0.2058 | -0.0007 | 6 | 1 min |

Why it says little yet: all four are lower, but by about 0.5% of the MSE,
while one arm's val MSE moves 0.005-0.008 between neighbouring epochs; the
validation set is mixed content, of which Hexaghost's cycle is a small part,
so a small aggregate gain is what a real Hexaghost signal would also look
like. The plays decide. Epochs take about twice as long (4 s against 2 s
on g400), so the rows widen the input as expected; the first job's peak was
7.4 GB (the twin's 6.22 GB), the other three 4.1-4.2 GB (twins 3.8-3.9 GB). The jobs' 20-40
minute estimates were 10-20x too high: these bursts take 1-3 minutes.

Next: boss replays 0248, 0250, 0252, 0254 (paired by deck against each
plain twin's replay file) and cell gauntlets 0249, 0251, 0253, 0255
(`--against` each plain twin's file), the charter's one read.

### First boss replay of the four (g400-s1, 0248): Hexaghost -0.002 (0.004) against its plain twin (read 09:15 2026-11-06, lanes, partial)

The jobs' notes say to read with `boss_replay.py pair`, but that command
takes only `--hp arrival` replays; these files and their twins are HP
sweeps (30-80 x 4 seeds), like the twins' own read. The read used here:
per deck, the mean win over the six HP levels and four seeds; pattern
minus plain twin paired by deck index (decks checked identical); se over
decks.

| boss | decks | pattern - twin | train half | held-out half |
|---|---|---|---|---|
| Hexaghost | 161 | -0.002 (0.004) | +0.001 (0.005) | -0.005 (0.006) |
| Guardian | 148 | +0.005 (0.004) | +0.010 (0.006) | -0.000 (0.004) |
| Slime Boss | 165 | -0.003 (0.003) | -0.003 (0.004) | -0.003 (0.005) |

One pair of four, so no verdict. Pattern rows did not move Hexaghost on
this net: the pooled gain would need about +0.02 on each of the other
three pairs to reach the fail bar (+0.015). Paired se is about half the
twins' se against the product (0.004 against 0.010), since twin and
pattern net share source, games and seed.

## Pattern-row bursts read: pooled over the four twin pairs Hexaghost gains +0.004 (0.002) wins against the plain twins, under the +0.015 fail bar, so the lane fails; Guardian +0.000 (0.002), Slime Boss +0.000 (0.001); cells -0.42 (0.19) HP against the twins (pattern-rows-burst stop read; 0248-0255; read 09:45 2026-11-06, lanes)

Boss replays (0248, 0250, 0252, 0254) on the 474 boss fights of the
headline file at HP 30-80 x 4 seeds @hpb0.01, read as in the subsection
above: per deck the mean win over HP levels and seeds, pattern minus plain
twin paired by deck (decks and bosses checked identical), se over decks;
pooled = the mean of the four pairs' per-deck differences.

| boss | g400-s1 | g400-s2 | g1600-s1 | g1600-s2 | pooled (4 pairs) |
|---|---|---|---|---|---|
| Hexaghost (161 decks) | -0.002 (0.004) | +0.003 (0.003) | +0.008 (0.005) | +0.008 (0.003) | **+0.004 (0.002)** |
| Guardian (148) | +0.005 (0.004) | +0.003 (0.003) | -0.005 (0.004) | -0.001 (0.003) | +0.000 (0.002) |
| Slime Boss (165) | -0.003 (0.003) | -0.001 (0.003) | +0.002 (0.003) | +0.003 (0.003) | +0.000 (0.001) |

By deck half, Hexaghost: train half -0.002 to +0.010, held-out half -0.005
to +0.012 per pair; no half stands out.

Cell gauntlet 0-499 one turn deep (0249, 0251, 0253, 0255), paired end-HP
(gauntlet_protocol.end_hp) and clears at n 500:

| arm | pattern - twin HP | clears | pattern - control HP | twin - control HP |
|---|---|---|---|---|
| g400-s1 | -1.83 (0.41) | -0.022 (0.011) | -0.24 (0.53) | +1.59 (0.46) |
| g400-s2 | -0.19 (0.31) | -0.002 (0.009) | +0.99 (0.46) | +1.18 (0.49) |
| g1600-s1 | +0.38 (0.37) | +0.014 (0.011) | +1.15 (0.47) | +0.78 (0.50) |
| g1600-s2 | -0.05 (0.31) | +0.014 (0.010) | +0.37 (0.45) | +0.42 (0.46) |
| pooled | -0.42 (0.19) | +0.001 | +0.57 | +0.99 |

(control: results/gauntlet/net1029-hpb0.01.json.) The protocol's own
verdict against each twin is fail on all four, which only says no +1.5 HP
gain; the cells are not below the twins by 1 HP pooled, so retention does
not block anything. The one large cell loss (g400-s1, -1.83) is a twin
that sat +1.59 over the control; the pattern net is level with the
control there, so it reads as that twin's luck as much as a cost of the
rows.

**Verdict: fail** by the charter (pooled Hexaghost gain under +0.015;
every fine-tune trained on the rows, so the fail is the play, not a
refusal). CPU: 2.37 cpu-h of the 5 cap (12 jobs).

Why, as far as the files show:
- The rows show one move past the intent on show
  (`py/src/features.rs` `pattern_rows`: one row per possible next move,
  its probability and effects). For Hexaghost's fixed cycle that is a
  single certain move, so Inferno becomes visible one turn earlier than
  through the intent, and nothing past that. Planning a seven-move cycle
  (when to spend HP, when to block for Inferno) needs more than the next
  move.
- The labels are still the student's own one-turn outcomes
  (`cause/teacher-equals-student`): a row that shows the next move helps
  only if the games' outcomes reward acting on it, and the plain twins
  already learned nothing on Hexaghost from the same games.
- The 1600-game pairs are both +0.008 (one at 2.7 se); 400 games give
  +0.000. That fits a small real signal that grows with games, at about a
  tenth of the second turn of search's +0.083 on the same decks
  (`measurement/depth-by-boss@replay`). At that rate the fail bar would
  need several times 1600 boss games: not a probe this lane can run.
- Validation MSE fell 0.0007-0.0018 on every arm (section "Pattern-row
  bursts trained"); the fight results are that small too.

What it changes: a burst of this size does not learn Hexaghost from its
next move, so the question goes back to decks and depth
(`hexaghost-headroom`), and a pattern row is no cheap substitute for the
second turn of search. For goal 1, pack monsters' pattern rows train
without error from a widened vocabulary (the input path works); whether
they pay is a question for content whose next move matters inside the
horizon.

## Cards by half, partial: 20k-game nets lift both halves but keep the same gap as 5k (+1.99 (0.44) HP against +1.94 (0.15)); one 20k seed (s201) shows no gap at all (yardstick-cards step 1, partial; 0213-0224; read 09:55 2026-11-06, lanes 8c646f98)

`scripts/analysis/cards_by_half.py --root <main>`: per net the mean over its two cell books (0-499, --first 500) of the paired edge over the heuristic by half; per size mean (se over seeds).

| nets | seeds | train HP | held-out HP | gap HP | train clears | held-out clears | gap clears |
|---|---|---|---|---|---|---|---|
| effects 5k | 5 | +0.56 (0.32) | -1.38 (0.39) | +1.94 (0.15) | +0.018 (0.012) | -0.037 (0.007) | +0.055 (0.009) |
| effects 20k | 3 | +2.34 (0.38) | +0.35 (0.71) | +1.99 (0.44) | +0.054 (0.008) | -0.012 (0.012) | +0.065 (0.007) |
| product recipe (10-29 s1) | 1 | +3.69 | +2.09 | +1.60 | +0.090 | +0.002 | +0.088 |

Per 20k net and book (train, held-out HP): s1 +1.46 / -1.08 and +3.05 / -0.00; s101 +1.77 / -0.05 and +1.67 / -0.29; s201 +2.95 / +1.38 and +2.88 / +2.89.

**Why.** Four times the data moves the train half by +1.8 HP and the held-out half by +1.7 HP: more games teach play that carries to unseen cards about as well as to seen ones, so the gap (what unseen cards cost) holds at about 2 HP and does not shrink with size between 5k and 20k. The held-out se at 20k (0.71) is twice the train se: seed s201 generalises to the unseen half on both books (gap ~0.8 and ~0), the other two do not. With three seeds that is one draw from the seed spread, not a mechanism; 40k (0233-0234 and the b500 jobs), the ids floor and the 10-29 twins are still queued, so the gap's trend over size is open. Nothing here changes step 2's design: the gap a held-out-card burst must close is about 2 HP and 0.06 clears at every size read so far.

## Cards by half, 20k complete: with all five 20k seeds the gap is +2.60 (0.58) HP against 5k's +1.94 (0.15); more data lifts both halves and does not shrink what unseen cards cost (yardstick-cards step 1, partial; 0225-0229; read 10:10 2026-11-06, lanes 5d302627)

Same table (`scripts/analysis/cards_by_half.py --root <main>`), five seeds per size now at 5k and 20k:

| nets | seeds | train HP | held-out HP | gap HP | train clears | held-out clears | gap clears |
|---|---|---|---|---|---|---|---|
| effects 5k | 5 | +0.56 (0.32) | -1.38 (0.39) | +1.94 (0.15) | +0.018 (0.012) | -0.037 (0.007) | +0.055 (0.009) |
| effects 20k | 5 | +2.74 (0.33) | +0.14 (0.52) | +2.60 (0.58) | +0.057 (0.005) | -0.017 (0.009) | +0.074 (0.008) |
| effects 40k | 1 | +1.51 | +0.21 | +1.30 | +0.068 | +0.014 | +0.054 |

New per net and book (train / held-out HP): 20k s301 +2.58 / -0.44 and +3.72 / +0.49; s401 +3.32 / -1.02 and +3.82 / -0.49; 40k s1 +3.88 / -0.39 and +1.01 / +0.40. The s201 b500 row reads +3.08 / +2.90 now; the partial section's +2.88 came from 0225's file before that job ended (09:51:50, read at 09:52), so it was a part-written file, not a different measurement.

**Why.** From 5k to 20k games the train half gains +2.18 HP and the held-out half +1.52 HP (about 2.3 se): more data does carry to unseen cards, but less than to seen ones, so the gap grows by +0.66 (se about 0.60, not significant) rather than shrinking. s301 and s401 show the full gap (about 3 and 4.3 HP); s201, the one seed that generalised, is now the exception among five. The 40k row is one net whose two books disagree by 3.7 HP on the gap (4.27 and 0.61), so a single net's book-to-book spread is about as large as the whole effect: nothing reads from one 40k net, and the step-1 table needs the three 40k seeds (0230-0234) before 40k gets a row. What this changes: none of the plan. Training size alone does not buy the unseen half, so the gap of about 2 to 2.6 HP and 0.06 to 0.07 clears stays the target for step 2's held-out-card bursts.

## Cards by half, 40k two seeds: gap +2.13 (1.11) HP, between 5k and 20k; the earlier 40k row and its 3.7 HP book spread came from a part-written file (yardstick-cards step 1, partial; 0230-0233; read 10:25 2026-11-06, lanes 5d302627)

| nets | seeds | train HP | held-out HP | gap HP | train clears | held-out clears | gap clears |
|---|---|---|---|---|---|---|---|
| effects 5k | 5 | +0.56 (0.32) | -1.38 (0.39) | +1.94 (0.15) | +0.018 (0.012) | -0.037 (0.007) | +0.055 (0.009) |
| effects 20k | 5 | +2.74 (0.33) | +0.14 (0.52) | +2.60 (0.58) | +0.057 (0.005) | -0.017 (0.009) | +0.074 (0.008) |
| effects 40k | 2 | +3.23 (0.20) | +1.10 (0.91) | +2.13 (1.11) | +0.074 (0.008) | -0.012 (0.012) | +0.086 (0.020) |

Per 40k net and book (train / held-out HP): s1 +3.88 / -0.39 and +2.97 / +0.76; s101 +2.50 / +0.57 and +3.57 / +3.45. s201's b500 book (0234) was running at the read and is left out.

**Correction.** The previous section's 40k row (one net, +1.30 HP gap, books disagreeing by 3.7 HP) read s1's b500 file while 0230 was still writing it; the finished file gives that book +2.97 / +0.76 (gap +2.21, not +0.61), so the two books disagree by 2.1 HP, not 3.7. This is the second part-written read in a row (the first was 0225's s201 file), so `scripts/analysis/cards_by_half.py` now counts a file with fewer than 500 sequences as missing.

**Why.** From 20k to 40k the train half gains another +0.5 HP and the held-out half +1.0 HP, but with two seeds the held-out se is 0.91: s101 generalises (gap about 1 HP, like 20k's s201) and s1 does not (about 3.2 HP). Over 5k, 20k and 40k the gap sits between 1.9 and 2.6 HP with no trend beyond its se, while both halves rise: training size buys general play, not the unseen cards. Each size has one or two seeds out of five whose gap nearly closes, so whether a net generalises to unseen cards looks like a seed draw; that spread (sd about 1.3 HP at 20k) is what step 2's bursts must beat, which needs three burst seeds as planned.

## Cards by half, 40k complete and the ids floor: ids-only nets lose +5.17 (0.67) HP to unseen cards, effects nets about 2 at every size (40k +2.01 (0.65)); the effects inputs carry about 60% of the card knowledge to unseen cards (yardstick-cards step 1, partial; 0234-0238; read 10:40 2026-11-06, lanes 5d302627)

| nets | seeds | train HP | held-out HP | gap HP | train clears | held-out clears | gap clears |
|---|---|---|---|---|---|---|---|
| effects 5k | 5 | +0.56 (0.32) | -1.38 (0.39) | +1.94 (0.15) | +0.018 (0.012) | -0.037 (0.007) | +0.055 (0.009) |
| effects 20k | 5 | +2.74 (0.33) | +0.14 (0.52) | +2.60 (0.58) | +0.057 (0.005) | -0.017 (0.009) | +0.074 (0.008) |
| effects 40k | 3 | +3.74 (0.52) | +1.73 (0.82) | +2.01 (0.65) | +0.074 (0.005) | +0.004 (0.017) | +0.070 (0.020) |
| ids 5k | 3 | -0.08 (0.22) | -5.26 (0.61) | +5.17 (0.67) | +0.019 (0.007) | -0.099 (0.024) | +0.117 (0.023) |
| product recipe | 2 | +3.32 (0.36) | +2.01 (0.07) | +1.31 (0.29) | +0.080 (0.010) | +0.010 (0.008) | +0.070 (0.018) |

Per net and book (train / held-out HP): 40k s201 +4.31 / +2.90 and +5.18 / +3.07; ids s1 +0.89 / -6.56 and -0.32 / -5.54; ids s101 -0.48 / -6.20 and -0.50 / -5.10; ids s201 -1.11 / -4.01 and +1.02 / -4.12. Product recipe: 10-29 s1 +3.27 / +1.82 and +4.11 / +2.36, s101 +2.71 / +1.23 and +3.21 / +2.65; s201's b500 book (0239) was running (250 of 500 sequences) and the script left it out, as built.

**Why.** At 5k games the ids nets and the effects nets play the train half alike (-0.08 against +0.56 HP, about 1.6 se apart), but on the held-out half the ids nets lose 5.3 HP to the heuristic and the effects nets 1.4: a net that sees cards only by id has learned nothing about a card it never met, and the effects inputs recover about 3.2 of those 5.2 HP. So the zero-shot cost splits into the part the effects encoding already transfers (about 60%) and a remainder of about 2 HP and 0.07 clears that neither more data (5k to 40k) nor the product recipe's second round (1.31 (0.29)) removes. The held-out clears say the same: ids nets clear 0.10 fewer held-out fights than the heuristic, effects nets about as many. The ids5k s301 and s401 controls (0240-0243) complete the floor at five seeds but cannot move a 5.2 HP gap with se 0.67 to the effects nets' 2; the step-1 table is effectively decided. What it changes: step 2's held-out-card bursts aim at the remaining 2 HP (about 0.07 clears) per size; their headroom is that number, not the 5 HP an id-only net would show.

## Cards by half, step 1 complete: unseen cards cost effects nets about 2 HP and 0.06-0.07 clears at every training size (5k +1.94 (0.15), 20k +2.60 (0.58), 40k +2.01 (0.65), product recipe +1.48 (0.24)) and ids-only nets +4.47 (0.56); paired over five seed twins the effects inputs save +2.54 (0.52) HP (yardstick-cards step-1 checkpoint; 0211-0243; read 10:55 2026-11-06, lanes 5d302627)

The step-1 table, all reads in (`scripts/analysis/cards_by_half.py --root <main>`; per net the mean of its two cell books, 0-499 and --first 500, paired against the heuristic by half; mean (se over seeds)):

| nets | seeds | train HP | held-out HP | gap HP | train clears | held-out clears | gap clears |
|---|---|---|---|---|---|---|---|
| effects 5k | 5 | +0.56 (0.32) | -1.38 (0.39) | +1.94 (0.15) | +0.018 (0.012) | -0.037 (0.007) | +0.055 (0.009) |
| effects 20k | 5 | +2.74 (0.33) | +0.14 (0.52) | +2.60 (0.58) | +0.057 (0.005) | -0.017 (0.009) | +0.074 (0.008) |
| effects 40k | 3 | +3.74 (0.52) | +1.73 (0.82) | +2.01 (0.65) | +0.074 (0.005) | +0.004 (0.017) | +0.070 (0.020) |
| ids 5k (floor) | 5 | -0.68 (0.41) | -5.15 (0.39) | +4.47 (0.56) | +0.001 (0.012) | -0.097 (0.015) | +0.098 (0.017) |
| product recipe (10-29 s1, s101, s201) | 3 | +3.44 (0.24) | +1.96 (0.07) | +1.48 (0.24) | +0.080 (0.006) | +0.010 (0.005) | +0.070 (0.010) |

The two new ids controls (0211 and 0212, configs/ids5k-s301.json and -s401.json; first peaks 1.18 and 1.62 GB) read train / held-out HP: s301 -2.30 / -5.75 and -1.80 / -5.49; s401 -0.66 / -4.63 and -1.48 / -4.10. Product s201's second book: +4.39 / +2.29. Paired by seed twin (same seed and games, ids minus effects gap): s1 +4.01, s101 +3.58, s201 +1.93, s301 +1.46, s401 +1.70; mean +2.54 (0.52) HP.

**Why.** Three things are now measured. (1) Zero-shot, a net that sees cards only by id loses about 4.5 HP and 0.10 clears on decks with unseen cards against the same net's play on seen ones; the effects inputs cut that to about 2 HP and 0.06 (paired over five twins, a saving of 2.5 (0.5) HP, about 57%). (2) The remaining 2 HP does not fall with training size: from 5k to 40k games both halves gain about 3 HP, the gap stays within 1.9-2.6, so more of the same data teaches general play, not the unseen cards. (3) The product recipe's extra round narrows it to 1.48 (0.24), about 0.5 HP below 5k at 1.8 se: a lead, not a result. The s301 and s401 ids twins lose on the train half too (-2.0 and -1.1 HP), so with five seeds the ids train edge is -0.68, not the three-seed -0.08; their gap is smaller for that reason, not because they transfer better. For the navigator: cause/unseen-cards-half-edge quotes three pairs (ids minus effects -4.1 HP held-out, -0.8 train); the five-pair values are -3.77 held-out and -1.24 train (the held-out minus train difference, 2.5 HP, is the saving above). What it changes: step 2's held-out-card bursts have about 2 HP and 0.07 clears of headroom on the held-out half, and the seed spread between nets (one or two seeds per size nearly close the gap on their own) means a burst needs three seeds against the 10-29 net to be told from luck, as planned.

## Cards by card and by stratum (step 1b): the script reproduces the navigator's strata to the digit; Demon Form costs every net group 6-9 HP against the heuristic per copy, its Strength lands after the one-turn leaf, and its row is a combination no training game held (yardstick-cards step 1b; no jobs; read 14:30 2026-11-06, lanes d6ed878a)

`scripts/analysis/cards_by_half.py --step1b` (run in the main checkout) prints four tables from existing files: the cell gauntlet by three strata (train decks 500 sequences, held-out decks without Demon Form 326, held-out decks with it 174; both books), the by-card regression, the two-turn cell files by the same strata, and the generated-power bench by trigger.

**By stratum against the heuristic** (end-HP, se over sequences / over nets; clears):

| nets | n | train | held-out without DF | held-out with DF |
|---|---|---|---|---|
| effects 5k | 5 | +0.56 (0.50 / 0.32), +0.018 | +1.74 (0.67 / 0.30), +0.029 | -7.23 (1.19 / 0.80), -0.162 |
| effects 20k | 5 | +2.74 (0.51 / 0.33), +0.057 | +3.64 (0.69 / 0.41), +0.055 | -6.41 (1.24 / 0.78), -0.152 |
| effects 40k | 3 | +3.74 (0.52 / 0.52), +0.074 | +4.30 (0.72 / 0.76), +0.057 | -3.08 (1.24 / 1.04), -0.096 |
| ids 5k | 5 | -0.68 (0.50 / 0.41), +0.001 | -1.28 (0.72 / 0.35), -0.013 | -12.40 (1.28 / 0.62), -0.254 |
| product recipe | 3 | +3.44 (0.55 / 0.24), +0.080 | +5.28 (0.74 / 0.17), +0.078 | -4.26 (1.32 / 0.38), -0.117 |

Every number matches cause/unseen-cards-half-edge. Without Demon Form the held-out decks are no worse than the train decks for any effects net (held-out minus train: +1.2, +0.9, +0.6, +1.8 HP); the ids nets lose 0.6 HP there. More data (5k to 40k) closes the Demon Form stratum from -7.2 to -3.1 HP, faster than it lifts the other strata. So more of the same games do teach the card a little, a lead for step 2's size arms.

**By card** (end-HP on the copies of each non-starter card, product-recipe nets, both books, covariates book and upgrade count, HC1 se): Demon Form +2.35 (1.45) for the heuristic, -5.19 (1.44) for the nets, nets minus heuristic -7.54 (1.23); per net group the Demon Form row is -7.48 (1.12) at 5k, -7.91 (1.18) at 20k, -6.16 (1.18) at 40k, -9.20 (1.22) for ids 5k, -7.54 (1.23) for the product recipe. Every other card's difference is within 2 se of zero, except four cards where the nets beat the heuristic: FTL +3.49 (1.33), Brutality +2.38 (0.81), Inflame +1.94 (0.63) and Clash +1.96 (0.92). **Mismatch with the cause fact:** it says no card other than Demon Form differs by more than 2.4 HP; FTL differs by 3.49, in the nets' favour, so the claim about the cost (no other card costs the nets) still stands. Metallicize, the other held-out power, costs -0.91 (1.31) on the cells: nothing.

**Two turns deep** (each file on its own 250 sequences, se over sequences): the 10-29 net two turns deep gains +10.35 (2.98) and +6.40 (2.11) HP over its own one-turn play on Demon Form decks (sequences 0-249, 500-749; pooled +8.4) against +0.8 to +3.7 elsewhere; the champion (burst8hp2 s1) two turns deep gains +9.9, +10.0, +6.8 over the one-turn 10-29 net there. Against the heuristic, two turns deep, the Demon Form stratum sits 2-5 HP below the other held-out stratum for the 10-29 net (+6.81 and +3.96 against +8.92 and +8.90) and level for the champion (+6.33, +4.73, +4.38 against +5.32, +3.42, +3.83). This matches the cause fact.

**Generated-power bench** (elite and boss fights, three copies, 10-29 net minus heuristic wins, one turn deep, se over cells): turn start -0.292 (0.049, 12 cells); turn start with an HP-loss trigger -0.250 (0.083, 3); turn end -0.061 (0.054, 15); on a card played +0.005 (0.047, 18); on HP lost -0.02 to +0.01; original Demon Form decks -0.140 (0.033, 44 cells), original Metallicize decks -0.083 (0.030, 42). **Mismatch with the cause fact:** the means match, but its se (0.024, 0.044, 0.034, 0.030) are smaller than these. The fact's se treat each fight as independent; the twelve fights of a cell share its deck, so the se over cells used here is the honest one. No conclusion changes: turn start is still about 6 se below zero. The fact also leaves out the original Metallicize decks, at -0.083 (0.030): on elite and boss fights with three copies, the turn-end power costs too, about 60% of Demon Form's cost.

**Code read: how the 10-29 net sees Demon Form** (effects mode, rates off; `py/src/features.rs`, `engine/src/hooks.rs`, `engine/src/search.rs`, `engine/src/state.rs`):
- *Not blind.* Demon Form is a hook power (`DEMON_FORM`: on `OwnerTurnStart`, apply Strength 1 to me). In hand, the card's rows hold that hook granted to "me", scaled by the amount. Once played, the player's entity holds an `own` triggered row: trigger `OwnerTurnStart`, the apply-Strength-to-me scalar times the stacks.
- *Seen in parts, never as a whole.* In the training pool (Ironclad train cards and the monsters), the `OwnerTurnStart` trigger appears only as Brutality (lose 1 HP, draw 1) on the player and Poison on monsters. Apply-Strength-to-me appears as Rupture (on HP lost from a card) and Flex's LoseStrength (negative, at turn end) on the player, and as Ritual (at turn end) and Enrage on monsters. No training game held the row "turn start, gain Strength" on the player's side. The net would have to compose it from parts it learned separately.
- *Outside the leaf.* One turn deep, the search scores the state right after `EndTurn` (`Tree::child`, draw leaf off). `end_turn` runs the player's turn-end hooks and the monsters' turn, then `StartTurn` resets block and energy and asks for the draw. A random draw stops the run there as a chance node, and that is the leaf. The turn-start hooks run only at `TurnStarted`, after the draw resolves. So a turn-end power (Metallicize, Combust) has its first tick inside the leaf; Demon Form's first Strength never does, whether it was played this turn or turns ago. Its whole worth must come from the net's value of the row.
- Verdict: **seen and not learned, with the payoff outside the leaf.** It is not blindness: the inputs carry the row, and a burst that taught other turn-start powers lifted these decks on one seed and one book (step 1c reads three). The 40k nets close half the cost with more of the same games. Both say the row can be learned from games.

**What this changes.** Step 2's arms stay as written. The 5k-to-40k trend (-7.2 to -3.1 HP on the Demon Form stratum at constant train-half play) is a prior that the adapted column will show a games-to-learn slope. The Metallicize row on the bench says a recurring power whose first tick lands inside the leaf still costs something with three copies on long fights. Step 3's predicted plain control (a pair that lands inside the turn) is unaffected, but Metallicize amount modifiers may cost more than zero there. Facts: measurement/cards-by-card@cells.

## Transfer column (step 1c): nets fine-tuned on eight generated power cards, never on Demon Form, gain +6.10 (1.16) HP and +0.149 (0.030) clears on Demon Form decks over the 10-29 net, alike on three seeds; elsewhere they lose about 1 HP and 0.02-0.04 clears (yardstick-cards steps 1b+1c checkpoint; 0256-0260; read 14:30 2026-11-06, lanes d6ed878a)

The three burst8 nets (runs/2026-11-01-burst8-s1-d4b65b6, -s101-d414c13, -s201-5c7bb5c) play one turn deep on both cell books. They are read by stratum against the one-turn 10-29 net (`cards_by_half.py --step1b`, the "burst8 (transfer)" row; se over sequences / over nets):

| stratum | sequences | end-HP | clears |
|---|---|---|---|
| train decks | 500 | -0.88 (0.37 / 0.59) | -0.041 (0.012 / 0.012) |
| held-out without Demon Form | 326 | -1.12 (0.46 / 0.07) | -0.021 (0.012 / 0.005) |
| held-out with Demon Form | 174 | **+6.10 (1.16 / 0.16)** | **+0.149 (0.030 / 0.006)** |

Per net and book, the Demon Form stratum reads +6.13, +6.74 (s1), +6.07, +5.94 (s101), +5.88, +5.89 (s201). The tight se over nets is real: each of the six files lands within 0.9 HP of the others. Against the heuristic, the Demon Form stratum goes from the 10-29 net's -4.26 to +1.99 (1.02). That is about two thirds of the 9.5 HP headroom up to the two-turn product's level on those decks. By card (nets minus heuristic), a copy of Demon Form costs -1.83 (1.00) against the product nets' -7.54.

**Retention.** The train decks lose -0.88 HP and -0.041 clears, about 3.4 se on clears. Seed s101 loses about 2 HP on both books' train decks; s1 and s201 lose 0.3-0.8. The other held-out decks lose about 1 HP on every seed. So the charter's "within 1.5 HP" holds pooled and fails on one seed (s101, train). The clears loss is the larger price: the burst's eight generated powers pull some play away from the train cards.

**Why it transfers.** Step 1b's code read: Demon Form's row (`OwnerTurnStart`, apply Strength to me) is a combination no training game of the 10-29 net held, and its payoff lands after the one-turn leaf. The burst8 games hold generated powers on turn-start and turn-end triggers. Learning to value those rows carries over to the Demon Form row without one game on it. That fits the generated bench, where turn-start powers cost most (-0.292 wins): the net learned the trigger rather than the card.

**What it changes.** Step 1c passes: the transfer column is recorded on three seeds, and learning other recurring powers transfers. Step 2's adapted column (bursts on held-out decks, 0276-0290) must now beat +6.1 HP on these decks to show that games on the card itself add anything. It must also beat burst8's retention: train clears within -0.04, train HP within -0.9. The headroom left to the two-turn product's level is about 3.4 HP. A pass of 2 se there needs about 2.3 HP over three seeds (se about 1.16 over sequences), so a step-2 arm that ties burst8 is the likely outcome unless games on Demon Form itself teach more than the trigger. Facts: measurement/cards-transfer@cells.

## Value chooser: level on the headline at a sixth of the time, as two opposite halves (value-chooser; 0291, 0292; read 15:00 2026-11-06, lanes 7cab620c)

`gauntlet.py play <10-29 net>@hpb0.01 --start starter --rewards value`
(docs/specs/value-chooser.md: each option scored by the net's static value
of fight start states, the next floor's sim draw, each elite while one lies
ahead, the own boss post-rest; no fights), sequences 0-499 at fixed n,
paired against the one-turn control
`results/gauntlet/net1029-hpb0.01-starter-simboss.json` (sim chooser with
the boss horizon). Read with `scripts/analysis/value_chooser_read.py` and
`gauntlet.py read`.

| arm | end-HP (se) | clears (se) | clears A / ctl | without Demon Form: end-HP, clears | train half end-HP | held-out end-HP | wall |
|---|---|---|---|---|---|---|---|
| one hand (0291) | +0.51 (1.04) | +0.006 (0.026) | 0.686 / 0.680 | -0.60 (1.09), -0.024 (0.026), n 453 | +5.07 (1.38) | -4.06 (1.51) | 2.5 min |
| four hands (0292) | +0.08 (0.98) | +0.024 (0.025) | 0.704 / 0.680 | -0.99 (1.00), +0.000 (0.026), n 453 | +4.08 (1.30) | -3.92 (1.43) | 4.6 min |

Sim chooser wall time on the same setting: 16.0 min at 3 threads
(0059l7r3b37c, the fastest of record; 0202/0203 took ~50 min under load),
so the value chooser costs a sixth to a third of it or less. Pick
agreement with the sim chooser's `took` 42% of floors (49% on the first
pick); it takes about one card more per sequence (9.5-9.7 against 8.5) and
Demon Form far less (1.4-1.6% of sequences against 8.4%).

**Why level:** the level total is two opposite halves. Clears on train
decks +0.060 (0.033) and +0.068 (0.034), on held-out decks -0.048 (0.039)
and -0.020 (0.037). The net values cards it trained on better than 16
sampled one-turn fights do (no fight noise, every state at once), and
cards it never saw worse: the zero-shot gap of `cause/unseen-cards-half-edge`
moves from the fights into the picks. Deaths move from the Guardian and
Slime Boss (47 and 18 in the control) to Hexaghost (59 and 45 against 42):
the net's boss values sit near 0 for many decks against Hexaghost (pre-build
check: 146 of 447 boss starts under 0.25, half of them won), so that part
gives little signal there. Four hands buy little: a dealt hand is not the
noise that matters.

**What it changes:** by the charter's go rule (level by
`yardstick/cost-savers` on all and without Demon Form, at a third of the
wall time or less) the four-hand arm passes at its bar (-0.99 HP) and the
one-hand arm misses by 0.004 clears; both inside one se of level. As a
cost saver it is a go for train-half or official-card reads; on the
held-out book it is biased against unseen cards, so a goal-1 own-pick read
of unseen cards cannot use it as is. The train-half gain (+4 to +5 HP at
3-3.7 se, two arms, one seed of fights) is a lead for a better chooser,
not a result.

## Step 2b's card lists, fixed before any read: parts (turn-start triggers and owner Strength, never paired) and neither (yardstick-cards step 2b; configs only; 2026-11-07, lanes 5f492a5f)

Does the net compose a trigger and an effect it learned apart? burst8 (`configs/burst8-s1.json`) held Demon Form's own row, `OwnerTurnStart` with `Apply:Strength`, through three of its eight cards (gc1_019, gc1_082, gc1_095) and gained +6.10 (1.16) HP on Demon Form decks. Two more arms by the same recipe (4,000 games per group, pool 10,000, player net, game seed 31; training seeds 1, 101, 201), each on eight cards of `data/bench/gen_powers_pack.json` chosen by their powers' `keys` with these rules:

- **parts** (`configs/burst8parts-s*.json`): no card holds the pair. The four test-split cards with an `OwnerTurnStart` key and no `Apply:Strength` key (all there are): gc1_020 (turn start: GainEnergy, Apply:Vulnerable), gc1_062 (turn start: Apply:Vulnerable), gc1_086 (turn start: GainEnergy), gc1_123 (turn start: GainEnergy, Apply:Vulnerable). The test split holds no Strength card off the pair, so the four Strength cards come from the train split: the first four by id whose Strength goes to the owner (`target: Me`) on a trigger that does not recur each turn (not `OwnerTurnStart` or `OwnerTurnEnd`, which would put Strength on the next turn as Demon Form does and blur the test): gc1_003 (owner loses HP to an attack: Apply:Strength, Apply:Dexterity), gc1_014 (the same trigger: Apply:Strength, Block), gc1_023 (owner loses HP from any source: Block, Apply:Strength), gc1_040 (owner plays a card: Apply:Dexterity, Apply:Strength).
- **neither** (`configs/burst8neither-s*.json`): the first eight test-split cards by id with no `OwnerTurnStart` and no `Apply:Strength` key: gc1_000 (owner plays a card: LoseHp), gc1_011 (turn end: Damage; owner loses HP: Apply:Weak), gc1_013 (owner loses HP: Apply:Weak), gc1_017 (owner loses HP to an attack: Apply:Weak), gc1_018 (turn end: Apply:Dexterity, Damage), gc1_024 (owner plays a card: LoseHp), gc1_025 (turn end: Apply:Dexterity, Damage), gc1_026 (owner loses HP to a card: PlainDamage).

Read (the charter): both cell books one turn deep by the three strata against the 10-29 net, three seeds pooled, beside burst8. parts at least +3 HP on Demon Form decks and 2 se above neither is a lead that the net composes, on one pair; parts level with neither says its knowledge is per pair. neither is also the control for what any eight-card burst does to Demon Form decks without either part.

## The ledger: no recipe trained since 10-29 beats the 10-29 net one turn deep on the cell books; the best are level (burst8 +0.26, seed twins -0.28, effects 40k -0.16), and none has a two-turn cell read (session-free-reads step 3; no jobs; 2026-11-07, lanes ea911692)

`scripts/analysis/ledger.py --md` (review 2026-11-06 direction 3): per
recipe, the paired end-HP and clears edge over the one-turn 10-29 net
(@hpb0.01) on the same cell book, mean over the recipe's (net, book) files.
It reproduces the three numbers the spec fixed in advance: effects 5k
-3.30 (10 files), 20k -1.45 (10), 40k -0.16 (6) (`test_ledger.py`).

How to read it:

- **The 10-29 net is the ceiling of every recipe tried.** Nothing sits
  above it by more than its own seed noise: the two seed twins of its own
  recipe read -0.44 and -0.12 (sd 0.22), so a recipe has to clear about
  +1 HP before it means anything, and none does.
- **Data helps up to 40k and then stops:** 5k -3.30, 20k -1.45, 40k -0.16,
  80k -0.95 (two nets, three files; one net has only the first book). The
  between-seed sd (0.7-1.0) is larger than the se over sequences (about
  0.5): seed luck, not the book, limits these reads.
- **ids 5k -5.80** against effects 5k -3.30: the effects inputs are worth
  about 2.5 HP at 5k, as in the cards-by-half read.
- **burst8 +0.26 overall** hides its two halves (the transfer section
  above: +6.10 on Demon Form decks, about -1 elsewhere); the ledger is a
  ranking of recipes, the strata table is where a recipe's why lives.
- **Two-turn column: none for every recipe.** Only the 10-29 net and the
  champion have two-turn cell files. The review's "each case with both a
  one-turn and a two-turn read" has no case yet; any recipe that reaches
  the product needs that read first.
- **Thread-hours are the reads' cost** (the gauntlet jobs whose `--out`
  wrote the files), not training; 0.0 means the files predate the job
  records (10-30 and 10-31 runs).

### Ledger: paired edge over the one-turn 10-29 net (@hpb0.01, cell books 0-499 and 500-999)

| recipe | seeds | (net, book) files | end-HP edge | se over sequences (mean) | sd between seeds | clears edge | thread-h | two-turn HP, clears (files) |
|---|---|---|---|---|---|---|---|---|
| effects 5k | 5 | 10 | -3.30 | 0.53 | 0.78 | -0.056 | 2.6 | none |
| effects 20k | 5 | 10 | -1.45 | 0.49 | 0.72 | -0.026 | 1.5 | none |
| effects 40k | 3 | 6 | -0.16 | 0.49 | 1.04 | -0.007 | 1.8 | none |
| ids 5k | 5 | 10 | -5.80 | 0.58 | 0.64 | -0.094 | 0.8 | none |
| burst8 (transfer) | 3 | 6 | +0.26 | 0.53 | 0.57 | -0.002 | 1.4 | none |
| 1029 seed twins | 2 | 4 | -0.28 | 0.43 | 0.22 | -0.002 | 0.7 | none |
| 2026-10-30-cover21 | 1 | 1 | -2.70 | 0.48 | nan | -0.020 | 0.0 | none |
| 2026-10-30-lean | 3 | 3 | -0.53 | 0.44 | 0.30 | -0.004 | 0.0 | none |
| 2026-10-31-lean-thr | 3 | 3 | -0.67 | 0.46 | 1.27 | -0.012 | 0.0 | none |
| 2026-11-01-data80k | 2 | 3 | -0.95 | 0.48 | 0.97 | -0.021 | 0.3 | none |

Per net (mean over its books; se over sequences per book):

| recipe | net | books | end-HP edge | se | clears edge | thread-h | two-turn |
|---|---|---|---|---|---|---|---|
| effects 5k | rerank-2026-10-31-data5k-s1-r1-965c6cc-hpb0.01 | 0-499 + 500-999 | -4.04 | 0.53 / 0.51 | -0.065 | 1.5 | none |
| effects 5k | rerank-2026-10-31-data5k-s101-r1-8cae3c0-hpb0.01 | 0-499 + 500-999 | -2.25 | 0.50 / 0.51 | -0.033 | 0.2 | none |
| effects 5k | rerank-2026-10-31-data5k-s201-r1-fc4b056-hpb0.01 | 0-499 + 500-999 | -3.86 | 0.53 / 0.57 | -0.075 | 0.2 | none |
| effects 5k | rerank-2026-10-31-data5k-s301-r1-a23411c-hpb0.01 | 0-499 + 500-999 | -2.70 | 0.54 / 0.56 | -0.035 | 0.4 | none |
| effects 5k | rerank-2026-10-31-data5k-s401-r1-3e724fc-hpb0.01 | 0-499 + 500-999 | -3.66 | 0.52 / 0.55 | -0.070 | 0.4 | none |
| effects 20k | rerank-2026-10-31-data20k-s1-r1-b2f3f4e-hpb0.01 | 0-499 + 500-999 | -2.03 | 0.48 / 0.49 | -0.038 | 0.3 | none |
| effects 20k | rerank-2026-10-31-data20k-s101-r1-025ea41-hpb0.01 | 0-499 + 500-999 | -2.12 | 0.49 / 0.51 | -0.031 | 0.3 | none |
| effects 20k | rerank-2026-10-31-data20k-s201-r1-95c5a40-hpb0.01 | 0-499 + 500-999 | -0.31 | 0.47 / 0.50 | -0.007 | 0.3 | none |
| effects 20k | rerank-2026-10-31-data20k-s301-r1-97e6f0f-hpb0.01 | 0-499 + 500-999 | -1.30 | 0.45 / 0.45 | -0.016 | 0.3 | none |
| effects 20k | rerank-2026-10-31-data20k-s401-r1-03e381a-hpb0.01 | 0-499 + 500-999 | -1.48 | 0.57 / 0.54 | -0.037 | 0.4 | none |
| effects 40k | rerank-2026-10-31-data40k-s1-r1-72d8ced-hpb0.01 | 0-499 + 500-999 | -1.08 | 0.49 / 0.54 | -0.017 | 1.1 | none |
| effects 40k | rerank-2026-10-31-data40k-s101-r1-606ebe3-hpb0.01 | 0-499 + 500-999 | -0.37 | 0.50 / 0.50 | -0.013 | 0.4 | none |
| effects 40k | rerank-2026-10-31-data40k-s201-r1-1b3f46e-hpb0.01 | 0-499 + 500-999 | +0.98 | 0.43 / 0.49 | +0.009 | 0.4 | none |
| ids 5k | rerank-2026-10-31-ids5k-s1-r1-22d423c-hpb0.01 | 0-499 + 500-999 | -5.77 | 0.58 / 0.62 | -0.104 | 0.1 | none |
| ids 5k | rerank-2026-10-31-ids5k-s101-r1-4ec523a-hpb0.01 | 0-499 + 500-999 | -5.96 | 0.63 / 0.56 | -0.095 | 0.1 | none |
| ids 5k | rerank-2026-10-31-ids5k-s201-r1-4096442-hpb0.01 | 0-499 + 500-999 | -4.94 | 0.59 / 0.53 | -0.059 | 0.1 | none |
| ids 5k | rerank-2026-11-06-ids5k-s301-r1-7ac4b06-hpb0.01 | 0-499 + 500-999 | -6.72 | 0.63 / 0.59 | -0.123 | 0.2 | none |
| ids 5k | rerank-2026-11-06-ids5k-s401-r1-77150bf-hpb0.01 | 0-499 + 500-999 | -5.61 | 0.53 / 0.55 | -0.089 | 0.2 | none |
| burst8 (transfer) | rerank-2026-11-01-burst8-s1-d4b65b6-hpb0.01 | 0-499 + 500-999 | +0.68 | 0.55 / 0.53 | -0.001 | 0.3 | none |
| burst8 (transfer) | rerank-2026-11-01-burst8-s101-d414c13-hpb0.01 | 0-499 + 500-999 | -0.39 | 0.56 / 0.49 | -0.012 | 0.5 | none |
| burst8 (transfer) | rerank-2026-11-01-burst8-s201-5c7bb5c-hpb0.01 | 0-499 + 500-999 | +0.48 | 0.53 / 0.49 | +0.008 | 0.6 | none |
| 1029 seed twins | net1029s101-hpb0.01 | 0-499 + 500-999 | -0.44 | 0.41 / 0.46 | -0.002 | 0.4 | none |
| 1029 seed twins | net1029s201-hpb0.01 | 0-499 + 500-999 | -0.12 | 0.41 / 0.44 | -0.001 | 0.3 | none |
| 2026-10-30-cover21 | rerank-2026-10-30-cover21-s1-r1-88ebd63-hpb0.01 | 0-499 | -2.70 | 0.48 | -0.020 | 0.0 | none |
| 2026-10-30-lean | rerank-2026-10-30-lean-s1-r2-9952dd3-hpb0.01 | 0-499 | -0.51 | 0.42 | +0.002 | 0.0 | none |
| 2026-10-30-lean | rerank-2026-10-30-lean-s101-r2-47f68ad-hpb0.01 | 0-499 | -0.24 | 0.42 | -0.002 | 0.0 | none |
| 2026-10-30-lean | rerank-2026-10-30-lean-s201-r2-24b88f9-hpb0.01 | 0-499 | -0.84 | 0.48 | -0.012 | 0.0 | none |
| 2026-10-31-lean-thr | rerank-2026-10-31-lean-thr-s1-r2-a81ecde-hpb0.01 | 0-499 | -1.98 | 0.47 | -0.042 | 0.0 | none |
| 2026-10-31-lean-thr | rerank-2026-10-31-lean-thr-s101-r2-d16ae2b-hpb0.01 | 0-499 | +0.57 | 0.44 | +0.010 | 0.0 | none |
| 2026-10-31-lean-thr | rerank-2026-10-31-lean-thr-s201-r2-72da355-hpb0.01 | 0-499 | -0.60 | 0.47 | -0.004 | 0.0 | none |
| 2026-11-01-data80k | rerank-2026-11-01-data80k-s1-r1-65e76eb-hpb0.01 | 0-499 | -1.86 | 0.52 | -0.022 | 0.0 | none |
| 2026-11-01-data80k | rerank-2026-11-01-data80k-s101-r1-f0865b6-hpb0.01 | 0-499 + 500-999 | -0.50 | 0.44 / 0.49 | -0.021 | 0.3 | none |

## Burst memory (step 2a read): the mapped pool cuts a burst's peak from 3.81 to 0.70 GB at 4 threads; the curve check's 0.00219 gap is the wider input layout, not the pool, so the check is passed by hand and the bursts run (yardstick-cards step 2a; 0304 against 0276; read 05:50 2026-11-07, lanes)

- **Peak.** Job 0304 reran burst 0276's config (`configs/ycards-heur-g400-s1-memcheck.json`) on the step-2a code (60cc028): peak 0.70 GB against 0276's 3.81 GB, in 3 minutes. The goal was under 2.5 GB. The pending bursts (0305-0322) reserve 2.5-3.0 GB, so the runner admits them.
- **Curves.** `curves_equal.py` failed at tolerance 1e-6: validation MSE equal to 5 digits for epochs 1-3, then apart by up to 0.00219 (epoch 9: 0.1548 against 0.1526); train MSE apart by at most 0.0005. The last epoch's val MSE is equal (0.1615 both).
- **Why.** The two runs did not use the same net shape. Between 0276's pin (ba5f802) and 0304's (60cc028), act1-content's exhaust cards added six effects (`pick_exhaust`, `pick_return_exhaust`, `exhaust_hand`, `exhaust_random`, `block_per_card`, `expr_q_hand`), so the widened net's inputs grew (player 28 to 31 columns, cards 82 to 88, monsters 83 to 89, rows 135 to 141). The pool's cache key includes the layout, so 0304 encoded the pool again instead of converting 0276's `.npz` (`warm-962fe63bc832-10000-e18550cf5b026987`). Checked against that `.npz`: the new player array with its three added columns (all zero) removed equals the old one exactly (`np.array_equal`), targets and groups are equal, and the row and card structure (`row_card`, `row_start`, `row_len`) is identical. So the same examples went in; the wider matrices change the float summation order, and that drift grows from epoch 4. The pool's draw itself is covered by `test_net` (per-epoch batches equal the whole-pool batches).
- **What it changes.** Nothing in the plan: the check's fail is passed by hand (`jobs.py verdict 0304-finetune pass`) and 0305-0322 are unparked. The s1 nets (0276-0278) trained in the narrow layout and s2/s3 in the wide one; the gap between the two code bases on one config (at most 0.002 val MSE, equal at the last epoch) is far inside seed-to-seed spread, so the three seeds pool as planned. The reads go through session-free-reads' family (`configs/families/ycards-step2.json`), not by hand.

## Card modifiers, first table (step 3): Inflame-as-a-tick and the dearer, stronger Metallicize cost the net beyond the heuristic on both leaves; cheaper, weaker Demon Form reads as a gain on the plain leaf (its parent's blind spot); the plain control and Combust are level (yardstick-cards step 3; 0407; read 07:20 2026-11-07, lanes bd39556c)

Job 0407 (`mutate_cards.py play --starts 200 --seeds 16 --players
heuristic,one,tsl`, pin 9d1bf9e; 0334 before it failed on a pin older than the
script) wrote `results/mutate/cards-a.json`; read with `mutate_cards.py read`.
Each modifier is a pack variant of an official card, read against a pack copy
of the same card on the same starts (product-file elite and boss fights whose
deck holds the parent, cell decks at entry HP) and seeds. Novelty = the net's
win change from the parent copy minus the heuristic's, paired by start.

All fights, win change from the parent copy (se) / HP lost change:

| modifier | n | heuristic | one-turn net | tsl net | novelty one | novelty tsl |
|---|---|---|---|---|---|---|
| bash-c1-d5 (plain control) | 200 | +0.029 (0.006) / -2.3 | +0.030 (0.007) / -2.3 | +0.028 (0.007) / -2.2 | +0.001 (0.006) / +0.1 | -0.001 (0.006) / +0.2 |
| inflame-turn1 | 200 | +0.038 (0.008) / -0.7 | -0.004 (0.007) / +2.1 | +0.020 (0.007) / +0.1 | **-0.043 (0.008)** / +2.8 | **-0.018 (0.005)** / +0.9 |
| df-c2-s1 | 155 | -0.016 (0.005) / +1.2 | +0.023 (0.006) / -0.9 | -0.007 (0.004) / +1.5 | +0.039 (0.009) / -2.1 | +0.009 (0.004) / +0.3 |
| metal-c0-a2 | 157 | +0.002 (0.003) / -0.0 | -0.007 (0.004) / +0.0 | -0.004 (0.003) / -0.1 | -0.009 (0.004) / +0.1 | -0.006 (0.004) / -0.1 |
| metal-c2-a5 | 157 | +0.017 (0.005) / -1.7 | -0.004 (0.004) / -0.5 | -0.004 (0.004) / -0.4 | **-0.021 (0.007)** / +1.2 | **-0.021 (0.006)** / +1.3 |
| combust-d8-l2 | 198 | +0.005 (0.004) / -0.3 | +0.001 (0.004) / -0.2 | +0.000 (0.004) / -0.1 | -0.004 (0.004) / +0.2 | -0.005 (0.004) / +0.2 |
| combust-c0-d3 | 198 | -0.015 (0.004) / +0.4 | -0.010 (0.004) / +0.6 | -0.011 (0.004) / +0.6 | +0.006 (0.004) / +0.3 | +0.005 (0.004) / +0.2 |

Pooled over the six power pairs (se over pairs, the charter's unit): one
-0.005 (0.011) wins, +0.39 (0.65) HP lost; tsl -0.006 (0.005) wins, +0.45
(0.22) HP lost; plain control +0.001 (0.006) / -0.001 (0.006). Every
modifier's novelty se on wins is at most 0.009, inside the stop rule's 0.02.

By fight type the effects are bosses' (elites are nearly always won):
inflame-turn1 one -0.108 (0.022), tsl -0.050 (0.015); df-c2-s1 one +0.114
(0.024), tsl +0.027 (0.013); metal-c2-a5 one -0.059 (0.019), tsl -0.058
(0.015). On elites the costs show as HP: inflame-turn1 +2.5 HP lost (one),
+0.6 (tsl); the rest within 0.7 HP.

Checks: copy minus official is near zero for all three players (largest
-0.007 (0.004) wins for the heuristic on Bash, -0.006 (0.002) on Metallicize;
bosses -0.020 (0.012) on Bash), well under the effects read. The plain
control is level on both leaves, as predicted.

Against the prediction written before the run:

- **inflame-turn1: as predicted.** Turning Inflame's +2 Strength now into +1
  Strength per turn helps the heuristic (+0.038) and not the plain-leaf net
  (-0.004): the per-turn Strength lands after its leaf. The turn-start leaf
  cuts the cost by about three fifths (-0.043 to -0.018) but not to zero: it
  shows the first tick, and the value of the later ticks is still unseen.
- **df-c2-s1: wrong in sign on the plain leaf, level-ish with tsl.** The
  prediction (the plain net loses) forgot that the parent is itself in the
  blind spot: on official Demon Form the plain-leaf net never sees the
  Strength (measurement/cards-by-card@cells, -7.54 HP per copy), so the
  modifier's Strength cut (2 to 1) is invisible to it while the cheaper cost
  (3 to 2) is visible. The net sees only the gain, the heuristic sees the
  loss, and the contrast reads +0.039. This is not a novelty gain: the
  novelty contrast against a parent the net already misjudges measures the
  change in that misjudgement. With tsl, which sees the first tick, it is
  +0.009 (0.004), near level as predicted. Rule for later tables: a parent
  with a known zero-shot cost on a leaf is not a clean baseline on that leaf.
- **metal-c2-a5: wrong; it costs on both leaves (-0.021, 3 se).** The
  prediction said Metallicize's block lands at the player's turn end, inside
  the leaf, so no cost. The leaf shows the block once; what the pricier,
  stronger card buys is the rate (5 instead of 3 every turn of a long boss
  fight), which a one-turn leaf shows at most once either way. The heuristic
  takes the trade (+0.050 boss wins); the net weighs one tick of +2 block
  against an energy and does not. The charter had flagged this column as
  open ("Metallicize may cost more than nothing"); the cost lives in later
  ticks, not at turn start. metal-c0-a2 (cheaper, weaker) is -0.009 (0.004)
  plain, -0.006 (0.004) tsl: the same direction, under 2 se on tsl.
- **Combust pairs: level, as predicted** (both under 1.5 se; their damage
  lands every enemy turn but a few HP of damage per turn moves few boss fights
  either way).

What it changes: the zero-shot cost on the cards rung is not "turn-start
powers" but **value that recurs past the leaf** (a rate the leaf shows once):
per-turn Strength (inflame-turn1, even with tsl) and a dearer, stronger
per-turn block (metal-c2-a5). The turn-start leaf repairs the first tick and
nothing beyond. Under decision/turn-start-leaf-reads (tsl is the leaf for
goal-1 card reads) two modifiers pass 2 se and get adapted columns
(decision/burst-adapted-column, three burst seeds): inflame-turn1 (-0.018
(0.005)) and metal-c2-a5 (-0.021 (0.006)). A burst must see the pack card
(how/burst-inputs): the adapted column needs bursts on pack-variant decks,
a spec of its own (next step).

## Step 2, first two arms on the cell books: the heuristic's games teach Demon Form (+4.98 (0.67 over nets) HP on its decks, all three seeds +4.0 to +6.2) but cost the rest (train -1.39 HP, -0.053 clears, outside the keep bar); the net's own 100 games per group teach nothing (-0.42 (0.32)) (yardstick-cards step 2, partial; 0276, 0305-0309, 0339-0357; read 09:50 2026-11-07, lanes a627bc69)

`family.py table configs/families/ycards-step2.json` (not written; five arms
still missing). Paired edge over the one-turn 10-29 net (@hpb0.01) on both cell
books, HP then clears, se over sequences / over the three nets:

| arm | train | held-out | held-out DF |
|---|---|---|---|
| heur-g400 | -1.39 (0.41 / 0.74), -0.053 (0.014 / 0.011) | -1.59 (0.49 / 0.98), -0.042 | +4.98 (1.14 / 0.67), +0.117 (0.029 / 0.008) |
| net-g100 | -0.58 (0.35 / 0.24), -0.030 (0.012 / 0.003) | -0.59 (0.45 / 0.48), -0.022 | -0.42 (0.71 / 0.32), +0.015 (0.018 / 0.012) |

Per seed (train HP, clears; DF HP): heur-g400 s1 -2.84, -0.076; +3.97 / s2
-0.43, -0.040; +4.75 / s3 -0.90, -0.044; +6.24. net-g100 s1 -1.06, -0.036;
-0.86 / s2 -0.30, -0.026; +0.19 / s3 -0.38, -0.028; -0.59.

Why, as far as two arms show it: 400 heuristic games per group carry Demon
Form's payoff in their outcomes (the heuristic plays the card and wins the
later turns), so the value head learns it, about as much as burst8's
transfer column (+6.10 (1.16)); but they are another player's games, and the
net drifts toward them elsewhere (every seed loses clears, s1 3 HP on train).
100 of the net's own games per group are too few to move anything, gain or
loss. The family rule (DF +2 se with train HP >= -0.9 and clears >= -0.04)
fails heur-g400 on the keep bar alone; net-g400 and net-g1600 say whether the
net's own games teach the card at more data without the drift. Not yet a
verdict: the checkpoint waits for all seven arms.

## Step 2, all arms but neither's last two seeds: the net's own games teach Demon Form at 1,600 per group (+3.77 (0.90) HP, all seeds +2.4 to +5.5) and the two-turn product's at 400 (+4.48 (0.60)); both pass the family rule, two-g400 at its clears bar; 2b's parts arm teaches nothing on Demon Form decks (-0.13 (0.66)), so far level with neither's one seed (-1.53) (yardstick-cards steps 2 and 2b, partial; 0310-0322, 0359-0393; read 11:35 2026-11-07, lanes 8d03fc2f)

`family.py table configs/families/ycards-step2.json` (not written: neither
s101 and s201 still reading, 0398-0403). Paired edge over the one-turn 10-29
net (@hpb0.01) on both cell books, HP then clears, se over sequences / over the
three nets:

| arm | train | held-out | held-out DF | pass | thread-h |
|---|---|---|---|---|---|
| heur-g400 | -1.39 (0.41 / 0.74), -0.053 | -1.59 (0.49 / 0.98), -0.042 | +4.98 (1.14 / 0.67), +0.117 | no (keep) | 2.0 |
| net-g100 | -0.58 (0.35 / 0.24), -0.030 | -0.59 (0.45 / 0.48), -0.022 | -0.42 (0.71 / 0.32), +0.015 | no | 2.4 |
| net-g400 | -0.77 (0.40 / 0.51), -0.049 | -0.43 (0.46 / 0.31), -0.032 | +0.79 (0.87 / 0.66), +0.040 | no | 1.6 |
| net-g1600 | -0.45 (0.35 / 0.26), -0.025 (0.012) | -0.37 (0.45 / 0.56), -0.026 | +3.77 (0.87 / 0.90), +0.094 | yes | 1.8 |
| two-g400 | -0.76 (0.38 / 0.17), -0.038 (0.012) | -0.82 (0.47 / 0.25), -0.035 | +4.48 (1.10 / 0.60), +0.109 | yes, best | 13.8 |
| parts | -2.35 (0.43 / 0.53), -0.059 | -2.51 (0.53 / 0.56), -0.034 | -0.13 (0.86 / 0.66), +0.000 | no | 2.8 |
| neither (1 net) | -2.81 (0.52), -0.046 | -2.20 (0.61), -0.034 | -1.53 (0.93), +0.011 | no | 1.7 |

Per seed (train HP, clears; DF HP): net-g400 s1 -0.16, -0.048; +2.05 / s2
-1.80, -0.064; -0.17 / s3 -0.37, -0.036; +0.51. net-g1600 s1 -0.08, -0.008;
+3.41 / s2 -0.31, -0.032; +2.41 / s3 -0.96, -0.034; +5.47. two-g400 s1 -0.67,
-0.038; +5.58 / s2 -1.09, -0.046; +4.36 / s3 -0.53, -0.030; +3.51. parts s1
-1.51, -0.042; +1.17 / s101 -2.23, -0.048; -0.60 / s201 -3.32, -0.088; -0.97.

Why, and what to doubt:
- **A games curve on the net's own play:** 100, 400 and 1,600 games per
  group give -0.42, +0.79 and +3.77 HP on Demon Form decks; only 1,600 moves
  every seed. That is the goal-1 number on this card at this one-turn leaf:
  about 1,600 own games per group to recover 3.8 of the ~9.5 HP the card costs
  zero-shot (cause/unseen-cards-half-edge).
- **A stronger teacher is worth about four times the games:** the two-turn
  product's 400 games per group match the net's 1,600 (+4.48 against +3.77,
  inside one se over nets) but cost 13.8 thread-hours against 1.8, so per CPU
  hour the net's own games are the cheaper repair.
- **Retention is the same small cost in every arm that learns:** train clears
  -0.025 to -0.049 for the net and product arms (z about -2 to -3.2 over
  sequences); two-g400's -0.038 sits right at the rule's -0.04 bar and its s2
  seed (-0.046) is outside it. Under the protocol's clears guard (paired clears
  z <= -2 fails a pass) neither passing arm would be clean; the family rule is
  the lane's, so the verdict stands, with this caveat on promotion.
- **The doubt that matters: is the gain only Demon Form's first tick?**
  burst8's +6.10 fell to +0.48 under the turn-start leaf
  (measurement/burst8-tsl1@cells): what it learned is the first Strength,
  which the turn-start leaf prices with no games. These arms trained on
  Demon Form's own decks rather than on generated cards, so they may have
  learned the later ticks too, but nothing here says so. The charter's gate
  reads the best arm's three nets `@hpb0.01@tsl1` against the 10-29 net's
  `@tsl1` files; queued for two-g400 and for net-g1600 (the cheap arm; same
  question, 1.4 thread-hours), see the decisions entry of this read.
- **2b: parts does not compose.** Turn-start triggers and owner Strength
  learned apart give -0.13 (0.66) HP on Demon Form decks against burst8's
  +6.10 on the pair itself; far below the +3 HP lead bar. neither's one net
  reads -1.53, so parts is within about 1.4 HP of it; the verdict (per pair, or
  level) waits for neither's other two seeds. Both eight-card arms lose 2-3 HP
  on train, more than burst8 (-0.9): cards off the decks' own content cost
  retention without teaching the decks anything.

## Step 2's turn-start-leaf gate and neither complete: both passing arms learned Demon Form's first tick and nothing after it (two-g400 -0.42 (0.94) HP on its decks @tsl1, net-g1600 +1.19 (0.75)); parts and neither are level, so the net does not compose the pair (yardstick-cards steps 2 and 2b checkpoint; 0398-0402, 0439-0450; read 12:10 2026-11-07, lanes 34ade50d)

The gate (decisions "yardstick-cards step 2: the turn-start-leaf gate read for
net-g1600 as well as two-g400"): each arm's three nets `@hpb0.01@tsl1` on both
cell books, paired by sequence against the 10-29 net's `@tsl1` files
(`results/gauntlet/net1029-hpb0.01-tsl1.json`, `-tsl1-b500.json`), by stratum,
three seeds pooled (se over sequences / over nets). Read with
`cards_by_half.complete_nets` and `strata_row` over the files
`results/gauntlet/rerank-2026-11-07-ycards-{net-g1600,two-g400}-s*-hpb0.01-tsl1*.json`.

| arm @tsl1 | train: HP, clears | held-out: HP, clears | held-out DF: HP, clears | plain-leaf DF (step 2) |
|---|---|---|---|---|
| net-g1600 | -0.31 (0.36 / 0.21), -0.025 (0.012) | -0.31 (0.45 / 0.56), -0.030 (0.011) | +1.19 (0.75 / 0.26), +0.019 (0.021) | +3.77 (0.87 / 0.90) |
| two-g400 | -0.71 (0.40 / 0.26), -0.036 (0.012) | -0.70 (0.48 / 0.16), -0.035 (0.011) | -0.42 (0.94 / 0.07), -0.027 (0.022) | +4.48 (1.10 / 0.60) |

Per seed (train HP, clears; DF HP): net-g1600 s1 -0.01, -0.010; +1.59 / s2
-0.20, -0.034; +1.29 / s3 -0.72, -0.032; +0.70. two-g400 s1 -0.63, -0.038;
-0.43 / s2 -1.19, -0.044; -0.53 / s3 -0.30, -0.026; -0.30.

Step 2b complete (`family.py table configs/families/ycards-step2.json`, all
seven arms on three nets): neither -2.08 (0.39 / 0.62) HP train, -1.46 other
held-out, -0.78 (0.77 / 0.59) on Demon Form decks; parts -0.13 (0.66 over
nets) there, so parts minus neither is about +0.65 HP, under one se.

Verdict: **gate failed for both arms**, by the charter's rule (level or better
on all three strata @tsl1): the Demon Form gain is gone or within 1.6 se of
zero, and every stratum loses 0.025-0.036 clears at z of 2 to 3. No step-2 net
goes toward the chooser or the product. The checkpoint "steps 2 and 2b read"
is reached; the stop rule's pass branch (an arm raises the Demon Form decks
by 2 se with the other strata kept) holds on the plain leaf only.

Why, and what to doubt:
- **The games taught the first tick, as burst8's did.** On the plain leaf the
  10-29 net cannot see the Strength Demon Form gives at the next turn start;
  bursts on its decks teach the value net that first Strength (+3.8 to +4.5
  HP). The turn-start leaf shows that tick exactly with no games (+7.54 HP,
  measurement/turn-start-leaf@cells), and on top of it the bursts add nothing
  and keep their retention cost. The later ticks, which neither leaf shows,
  were not learned at 1,600 own games or 400 product games per group.
- **two-g400 is cleaner zero than net-g1600** (se over nets 0.07): the
  stronger teacher's games teach exactly the tick, nothing more. net-g1600's
  +1.19 is positive on all three seeds (+0.70 to +1.59) but 1.6 se over
  sequences; at best a small lead on later ticks, not a read.
- **Retention:** clears fall about 0.03 on every stratum @tsl1, the same as on
  the plain leaf; a burst on one card's decks costs the rest of the content
  about 0.03 clears whatever leaf reads it.
- **2b: per pair.** Trigger and effect learned on different cards give
  nothing on the pair (parts level with neither), and both eight-card arms
  cost 1.5-2.5 HP elsewhere. With the step-2 gate, what one-turn games teach
  about a recurring power is its first occurrence on the pair itself.
- What this changes: goal 1's number for a recurring power at the one-turn
  leaf is "no games repair the later ticks at these sizes"; the repair that
  works is search-side (the turn-start leaf, a deeper horizon), which matches
  step 3's table (inflame-turn1 and metal-c2-a5 still cost under @tsl1, both
  value in later ticks). The boss replays (0352-0403, every third) and the
  best net's headline read (0405) were designed for a net on the product
  path; the gate takes it off.

## Cards adapted column (step 3, second table): no burst closes a cost on the turn-start leaf; on the plain leaf inflame-turn1's bursts win back 56% of its win cost and metal-c2-a5's nothing on all fights; all six bursts cost the parent copy and the official card 0.4-2.4 HP per elite fight (yardstick-cards step 3, leftover; 0409-0421; read 13:50 2026-11-07, navigator c2b85df5)

Six 400-game bursts from the 10-29 net (`configs/cadapt-<mod>-s<1|2|3>.json`,
the net's own games on decks holding the variant, replay share 0.5), each
read on `results/mutate/cards-a.json`'s starts and seeds, one turn deep on
both leaves; `mutate_cards.py adapted` (log `logs/jobs/0421-mutate-cards.log`)
pools the three bursts per start. Gain = bursts minus the zero-shot net,
paired by start, wins (se) / HP lost (se; negative is better). Zero-shot cost
= the net's change from the parent minus the heuristic's (the novelty cost,
sign as in the first table).

| mod, leaf | variant gain | parent copy | official card | zero-shot cost | repair (wins) |
|---|---|---|---|---|---|
| inflame-turn1, one | +0.024 (0.006) / -1.23 (0.23) | +0.001 / +0.53 (0.15) | -0.003 / +0.49 (0.16) | -0.043 (0.008) / +2.79 | 56%, 4 se |
| inflame-turn1, tsl | +0.001 (0.003) / +0.25 (0.16) | -0.001 / +0.62 (0.13) | -0.002 / +0.65 (0.15) | -0.018 (0.005) / +0.86 | none |
| metal-c2-a5, one | +0.009 (0.005) / +0.08 (0.30) | -0.004 / +1.07 (0.28) | -0.008 / +1.19 (0.30) | -0.021 (0.007) / +1.18 | 43%, 1.8 se |
| metal-c2-a5, tsl | +0.002 (0.005) / +0.27 (0.34) | -0.009 / +1.24 (0.30) | -0.012 / +1.39 (0.35) | -0.021 (0.006) / +1.31 | none |

By fight type: the variant gains sit at the bosses (inflame one +0.058 (0.016)
wins against a -0.108 cost; metal one +0.036 (0.011) and tsl +0.021 (0.012)
with -1.74 (0.45) HP against -0.058 and +2.87), and the retention cost sits at
the elites (parent copy, one leaf: inflame +0.76 (0.17), metal +1.79 (0.35)
HP per elite fight; bosses level or better). Per burst seed (adapted on one
file each, no CPU), parent copy HP per elite fight one leaf: inflame +0.65,
+1.26, +0.36; metal +1.43, +2.38, +1.58. Every seed of both mods pays it.

Verdict by the spec's read rule: **no modifier is repaired on the turn-start
leaf**; on the plain leaf inflame-turn1's wins are repaired (+0.024, 4 se,
parent wins level) but its parent copy loses 0.53 (0.15) HP; metal-c2-a5 is
repaired on neither leaf on all fights. The prediction held: games at 400 per
group teach the first tick (inflame's plain-leaf repair, about what the
turn-start leaf shows with no games) and no rate past it.

What it says beyond its question:
- **The cards rung's adapted column is zero at `@tsl1`.** With the step-2
  gate (Demon Form) that makes three recurring powers where bursts teach the
  first tick only. Later ticks are search-side (`projected-leaf`).
- **Metallicize at the bosses is the one exception in sign**: on both leaves
  the bursts lose 1.7-1.9 HP less there with the dearer, stronger variant
  (block every turn over a long fight), though wins stay under 2 se on the
  turn-start leaf and one seed carries little of it (+0.009). Block is not a
  lasting power, so `projected-leaf` will not show it; a lead only.
- **Card bursts cost unchanged play one turn deep.** All six bursts lose HP
  on the parent copy and the official card at the elites, while the replay
  share (0.5 of each batch from the varied Ironclad pool) was in every one.
  Monster bursts were level on their parents one turn deep
  (`measurement/adaptation-transfer`); these change the player's own deck.
  So the reason `burst-recipe` was withdrawn on 2026-11-05 ("one turn deep
  there is no parent cost") no longer holds for card content, as the burst8
  nets' -0.041 clears had already shown on train decks.

## Copy-rehearsal probe: putting the parent copy in the burst's decks doubles the parent cost instead of removing it (metal +2.61 (0.63) HP per elite fight against the plain seed-1 burst's +1.43; inflame +1.54 (0.32) against +0.65); stop (navigator probe sheet; 0456-0460; read 14:25 2026-11-07, navigator c2b85df5)

One burst per modifier, seed 1, the plain seed-1 burst's recipe with the
parent copy added to the burst's card list (`configs/cadapt-<mod>-copy-s1.json`:
decks hold the variant, the copy or both), read on cards-a.json's starts and
seeds (log `logs/jobs/0460-mutate-cards.log`; gain against the zero-shot net
as in the section above).

| mod, plain leaf | variant wins | parent copy, elite HP | parent copy, all: wins / HP | plain seed-1 burst, elite HP |
|---|---|---|---|---|
| inflame-turn1 + copy | +0.023 (0.006) | +1.54 (0.32) | +0.002 / +1.00 (0.25) | +0.65 (0.22) |
| metal-c2-a5 + copy | -0.006 (0.008) | +2.61 (0.63) | -0.022 (0.008) / +1.79 (0.46) | +1.43 (0.29) |

By the rule in 0460's note: **stop** (metal's +2.61 is above +1.43). Both mods
lose more on the parent copy and the official card with copy games than
without, at the elites on both leaves (metal elite @tsl1 +2.11, inflame
+1.64), and metal's copy burst now also loses wins on its parent (-0.022,
2.8 se) and gives up its variant gain. inflame's variant wins are kept
(+0.023, the plain seed's +0.024).

What it says: the elite cost is not missing rehearsal. More of the burst's own
games on decks holding the card cost more, even games on a card the net
already plays well (the copy plays as official Inflame and Metallicize). The
labels are not the difference either: burst games score a win as 2 - HP lost /
100, the parent's targets the same scale. What card bursts do differently from
the monster bursts, which were level on their parents one turn deep, is where
their games come from: varied decks at varied HP (`selfplay.varied_deck`,
`varied_hp`) instead of the read's own product-file fights. Not followed: a
card burst repairs nothing on the turn-start leaf, so keeping its retention
would make a burst that gains nothing cost nothing.

## All-content net's twin on the boss replay: data40k seed 1 (round 1) sits inside the 10-29 net's seed spread on all three bosses (Guardian -0.012 (0.008), Hexaghost -0.033 (0.011), Slime Boss -0.006 (0.005) wins against the 10-29 net), so it is a sound control for allcontent40k-s1 (all-content-net step 2, the twin; 0476; read 00:30 2026-11-08, lanes)

The twin is `runs/2026-10-31-data40k-s1-r1-72d8ced/model.pt@hpb0.01`, replayed one turn deep on the 474 boss fights of the headline file (HP 30-80 x 4 seeds, the 10-29 net's seeds), `results/boss_replay/data40k-s1-r1-hpb0.01.json`, 6.5 minutes, peak 0.69 GB. Win rate, and minus the 10-29 net paired by deck (se over decks):

| net | Guardian (148) | Hexaghost (161) | Slime Boss (165) | all (474) |
|---|---|---|---|---|
| data40k s1 r1 (twin) | 0.546, -0.012 (0.008) | 0.608, -0.033 (0.011) | 0.880, -0.006 (0.005) | 0.683, -0.017 (0.005) |
| 10-29 recipe s101 | 0.570, +0.011 (0.007) | 0.609, -0.033 (0.009) | 0.880, -0.006 (0.004) | 0.691, -0.010 (0.004) |
| 10-29 recipe s201 | 0.578, +0.020 (0.006) | 0.632, -0.009 (0.006) | 0.871, -0.015 (0.005) | 0.699, -0.002 (0.003) |

The s101 and s201 rows reproduce `measurement/burst-bosses@replay` to the third decimal, so the pairing is the same one. The twin is the weakest of the four nets on the Guardian (by 0.023-0.032 against the two seed twins, about two to three seed sds of 0.010) and level with s101 on Hexaghost; it is a round-1 net of a different recipe (data40k) where the others are round 2 of the 10-29 recipe, which may explain a hundredth or two. Nothing here is out of line with the seed spread, so the twin stands as the control. What it changes: allcontent40k-s1's step-2 read is against these per-boss numbers (the +0.03 bar on the Guardian or Hexaghost), not against the 10-29 net; a net that only reaches the 10-29 net's level on the Guardian would show +0.012 against the twin, under the bar.

## All-content net seed 1 on the boss replay: Guardian +0.048 (0.011), Hexaghost +0.093 (0.015) wins against its twin, so checkpoint seed1-bosses passes; the gain sits almost all on held-out-card decks (Guardian +0.004 on train decks, +0.085 on held-out), and Slime Boss loses 0.027 (0.008) on train decks (all-content-net step 2; 0574; read 15:45 2026-11-08, lanes)

The player is `runs/2026-11-08-allcontent40k-s1-r1-887ca04/model.pt@hpb0.01` (0569: data40k seed 1 with the Guardian and Hexaghost in its boss group and the held-out cards in its decks, today's inputs), replayed one turn deep on the 474 boss fights of the headline file at HP 30-80 x 4 seeds, the same file, seeds and threads as the twin (`results/boss_replay/data40k-s1-r1-hpb0.01.json`, 0476): `results/boss_replay/allcontent40k-s1-hpb0.01.json`, 6.6 minutes, peak 0.96 GB. Win rate over the six HPs, minus the twin's paired by deck (se over decks), split by the sequence's half (train decks hold only training-pool cards; held-out decks hold held-out cards):

| boss | all decks | train decks | held-out decks | win rate (twin) |
|---|---|---|---|---|
| Guardian (148) | +0.048 (0.011), 86 decks up, 45 down | +0.004 (0.014), n 69 | +0.085 (0.015), n 79 | 0.595 (0.546) |
| Hexaghost (161) | +0.093 (0.015), 91 up, 42 down | +0.030 (0.012), n 74 | +0.146 (0.025), n 87 | 0.698 (0.607) |
| Slime Boss (165) | -0.004 (0.008) | -0.027 (0.008), n 92 | +0.026 (0.015), n 73 | 0.875 (0.880) |

By HP the gain peaks at 40-50 HP (Guardian +0.09, Hexaghost +0.12) and fades by 80, where both nets win nearly every fight. Against the 10-29 net (the twin sits 0.012 and 0.033 under it, section above) the seed is still +0.036 on the Guardian and +0.060 on Hexaghost, so the pass is not the weak twin's doing.

Why, and what it changes. By the charter's letter the checkpoint passes (Guardian or Hexaghost +0.03), and the lane goes to step 3. But the split says what was learned: on decks of training-pool cards the two unseen bosses gain +0.004 and +0.030, around the bar or under it, while on decks holding held-out cards they gain +0.085 and +0.146. So the bulk of the gain is the held-out cards entering training (and today's wider inputs, which the twin lacks: spec "Decisions"), not the bosses; the cards matter most at the two hard bosses, where a deck's plan is tested longest. Slime Boss, a training boss, slips 0.027 on train decks: the net's share of boss games per boss fell from all to a third, a retention cost to watch at seeds 2-3. One seed is a lead (training-seed sd about 0.010 on these numbers): seeds 101 and 201 (twins data40k-s101-r1 and data40k-s201-r1, which have no boss replay yet) and the one-turn headline decide it. For goal 2 the product's decks are reward picks that include held-out cards, so the card gain is the part the headline can see; for goal 1 the net is never a held-out reader (charter).

## All-content net seed 101 on the boss replay repeats seed 1: Guardian +0.050 (0.009), Hexaghost +0.054 (0.012) wins against its twin; pooled over seeds 1 and 101, outside Demon Form decks against the 10-29 net, the Guardian gains +0.035 (0.007) and Hexaghost +0.017 (0.008); the lane closed at its cap before seed 201 and the one-turn headline (all-content-net close; 0581, 0583, 0601; read 21:20 2026-11-08, lanes)

The player is `runs/2026-11-08-allcontent40k-s101-r1-ce824da/model.pt@hpb0.01` (0583, `configs/allcontent40k-s101.json`, 205 minutes, peak 6.03 GB against its `mem_gb` 3), replayed by 0601 one turn deep on the same 474 boss fights, HP 30-80 x 4 seeds, against its twin data40k-s101 r1 (0581, `results/boss_replay/data40k-s101-r1-hpb0.01.json`): `results/boss_replay/allcontent40k-s101-hpb0.01.json`, 7.4 minutes, peak 0.68 GB. The twins sit in data40k-s1 r1's spread (Guardian 0.546 / 0.569 / 0.558 for seeds 1, 101, 201; Hexaghost 0.608 / 0.637 / 0.591; Slime Boss 0.880 / 0.891 / 0.889), as 0581's and 0582's notes asked. Wins per deck over the HP x seed grid, paired by deck, se over decks; strata as the navigator's split (decisions "After seed1-bosses"): train decks, held-out with Demon Form (DF), held-out with Metallicize and no Demon Form (Met), other held-out. The pairing script reproduces seed 1's filed numbers and the navigator's table to the third decimal.

| | Guardian | Hexaghost | Slime Boss | G+H train | G+H other held-out | G+H Met | G+H DF | G+H outside DF |
|---|---|---|---|---|---|---|---|---|
| s101 minus its twin | +0.050 (0.009) | +0.054 (0.012) | +0.003 (0.005) | +0.025 (0.009) | +0.012 (0.011) | +0.105 (0.018) | +0.238 (0.034) | +0.036 (0.007) |
| s101 minus the 10-29 net | | | | +0.032 (0.009) | +0.005 (0.011) | +0.058 (0.014) | +0.359 (0.045) | +0.029 (0.006) |
| s1 + s101 minus their twins | +0.049 (0.008) | +0.073 (0.012) | -0.000 (0.005) | +0.021 (0.007) | +0.008 (0.008) | +0.162 (0.017) | +0.276 (0.039) | +0.043 (0.006) |
| s1 + s101 minus the 10-29 net | +0.048 (0.008) | +0.054 (0.013) | -0.001 (0.007) | +0.028 (0.008) | +0.001 (0.009) | +0.061 (0.013) | +0.352 (0.044) | +0.026 (0.006) |

Outside Demon Form decks against the 10-29 net, per boss: seed 101 Guardian +0.048 (0.008), Hexaghost +0.010 (0.009); pooled Guardian +0.035 (0.007), Hexaghost +0.017 (0.008), Slime Boss -0.016 (0.004).

Why, and what it changes. Seed 101 repeats seed 1's shape: no gain on other held-out decks, the bulk on Demon Form decks (Demon Form's first tick, which bursts and the turn-start leaf also buy: `cause/unseen-cards-half-edge`), a Metallicize part that against the 10-29 net is about +0.06 (the rest is the twins' weakness there, as the navigator found for seed 1, and seed 101's twin shares it: +0.105 against the twin, +0.058 against the 10-29 net). What is new at seed 101 is a train-deck gain at the Guardian (+0.023 against its twin, +0.03 against the 10-29 net) beside Hexaghost's +0.028, so over two seeds the unseen bosses gain about +0.02-0.03 wins on train decks: a small boss effect, where seed 1 alone said none. Seed 1's Slime Boss loss on train decks (-0.027) does not repeat (+0.003), so the retention cost was seed luck or small. By the charter's letter both seeds pass the per-boss bar against their twins (Guardian +0.048 and +0.050, Hexaghost +0.093 and +0.054); the go also needed seed 201 and the one-turn headline (0585), which the cap stopped (0584 and 0585 cancelled at the close, decisions "Lane all-content-net closed"). The navigator's two-turn condition (outside Demon Form, against the 10-29 net, +0.03 at the Guardian or Hexaghost) is met at the Guardian on two seeds (+0.035 (0.007); the seeds differ, +0.023 and +0.048) and not at Hexaghost. Seed 201's learn peaks near 6 GB, not the 3 GB queued.

## Card-burst-share probe (0702-0714): the two card modifiers' bursts at 33 games and share 0.9

Navigator probe sheet, candidate `card-burst-share` (backlog 45). The
bursts of `yardstick-cards` (inflame-turn1, metal-c2-a5) again at 33 games
and replay share 0.9 (`decision/burst-share`), three seeds each (configs
`cs9-*`), read on `results/mutate/cards-a.json`'s starts and seeds (200
starts per parent x 16 seeds), pooled per start, against the zero-shot
10-29 net and beside the 400-game share-0.5 bursts
(`measurement/cards-adapted@stage-a`). Gain = bursts minus zero-shot,
wins / HP lost per fight.

- **Parent cost mostly gone.** Parent copy per elite fight, plain leaf:
  inflame-turn1 +0.52 (0.15) HP (400 games at 0.5: +0.76), metal-c2-a5
  -0.33 (0.18) (was +1.79), so the Metallicize burst now plays its parent
  better; the official card +0.44 (0.16) and -0.44 (0.20). Over all fights
  inflame's parent +0.24 (0.13), metal's -0.48 (0.15).
- **Inflame's variant gain is smaller.** Plain leaf, all fights:
  inflame-turn1 +0.010 (0.004) wins, -0.43 (0.18) HP, against a zero-shot
  cost of -0.043 (the 400-game bursts: +0.024, 56% of it); the bosses carry
  it (+0.028 (0.010)). metal-c2-a5 +0.012 (0.004), -0.75 (0.15) HP (400
  games: +0.009), bosses +0.031 (0.011).
- **The turn-start leaf: nothing closed again.** @tsl1 all fights:
  inflame +0.004 (0.003) against -0.018, metal +0.004 (0.002) against
  -0.021.
- Verdict by the read rule: not a go (inflame's parent +0.52 against a
  0.5 bar and its plain-leaf win gain +0.010 against +0.012, both missed
  narrowly), not a stop (both parent costs fell below the share-0.5
  bursts'). Interpretation: as on the pack (`measurement/pack-dose-33@gen-b1`),
  share 0.9 keeps the net near its parent and the target gain follows the
  variant's own games; on Metallicize 33 games suffice, on Inflame's tick
  (value that recurs past the leaf) they reach under half the 400-game
  gain.
- Not followed: a larger dose on cards. With the turn-start leaf the
  zero-shot cost is -0.018 (inflame) and -0.021 (metal) wins, and no burst
  of any size has closed any of it; on the plain leaf the best burst so
  far (+0.024) only matches what @tsl1 gives with no games (-0.043 to
  -0.018), so a bigger plain-leaf burst cannot gain over the leaf the
  cards are read with.
