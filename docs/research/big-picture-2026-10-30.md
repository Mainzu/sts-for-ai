# Big-picture review, 2026-10-30

Written after progress was judged too slow, to get more data analysis and
abstract thinking. Six analysts each read
the project through one lens: results, where strength is lost, goal 1,
prior art, throughput, and measurement. A synthesiser merged them, and two
skeptics re-derived each load-bearing claim from the primary files. Every
claim came back "overstated" in some detail; the versions below are the
skeptics' corrected ones. The workflow is saved as
`.claude/workflows/big-picture-review.js`.

## Where the project stands

**Goal 2 (strength).** On the cards the nets trained on, search with the
net now beats search with the hand-written heuristic, but by a small
average margin: +0.021 win rate on the train half of tight fights v2
(mean of 19 nets, `runs/tight2/rescore.json`). The margin is not spread
evenly. It sits in the fights that decide runs:

| Fight type | Share of tight2 cells | Net lead, train half | Net lead, held-out half |
|---|---|---|---|
| Hallway | 73% | about 0 | small deficit at the HP extremes |
| Elite | 20% | +0.056 | +0.001 (level) |
| Boss | 7% | +0.128 | +0.054 [+0.003, +0.105] |

(Per-group leads averaged over 15-18 nets with per-fight data, from
`runs/seed-check/check.json` and `runs/rung4-nightdb/check.json`, mapped to
`data/bench/tight2.json`.) In hallway cells, 81-83% of fights end the same
way for every player, so the equal-weight average dilutes any real effect
about 3.7x. The gate scored all of this as "fail" because it only looks at
that average on the held-out half.

**Goal 1 (unseen content).** Nothing is shown in play yet. Over 19 nets
the held-out lead is about the train lead minus a fixed 0.017 (slope 0.93,
r 0.81). The skeptics refined what limits it: new cards built from
primitives the net already knows cost nothing (zero-shot on Silent's tier
A cards the net matches the heuristic, +0.001 [-0.039, +0.041]), but a new
mechanic costs a lot (Silent's Poison, -0.069 [-0.094, -0.044]). The net's
inputs for unknown powers and for cards added to the hand carry
essentially zero weight. So goal 1 is limited by **mechanic coverage**,
not by the number of card kinds.

## The pattern underneath

**We measured where measuring was cheap.** The exact solver and the
calibrated tight fights are strongest near the end of a fight and at low
HP. Most of a week went into improving value labels there (curriculum,
rung 4, exact caps, frontier 2). But the decisions where the choice
matters are early: the share of decisions whose pick changes the outcome
climbs from 7% one turn from the end to 51% four turns out (exact
puzzles, `db/solved.sqlite`).

**The loop has only a weak amplifier.** Self-play picks moves with the
same one-turn search (limit 16, temperature 0.05) that the evaluated
player uses (`scripts/learn.py:114`). The only stronger teachers are game
outcomes, play-out averages and the exact solver, and the solver's trusted
zone never got past about one turn from the end. Cleaner labels for the
same policy can lower value error without making a better policy, and
that's what happened. Rounds go flat after round 1 or 2.

**Proxy metrics improved four times while play didn't.** A deeper
teacher (regret -59%), exact-only labels (paused-state MSE 0.092 →
0.017), rung 4 (err² 0.078 → 0.052) and Amendment 3's 400k cap (val MSE
down) all left play flat. Value MSE is not a stand-in for strength.

**Single-seed recipe questions couldn't be answered.** Retraining at
another training seed moves a net's lead by sd 0.006-0.0075. With 3 seeds
per arm a test rules out only effects above ~0.015 on the held-out half;
with one seed, above ~0.025-0.03. Every label change since the 10-28
night measured 0.000-0.006: not shown, but not ruled out either. Four
"passes" later reversed under retraining.

## What we know about cost

- **The exact-solver step is ~70% of a curriculum round's wall time**
  (196.7 of ~283 min in the 10-28 night, `logs/night2.log`) and uses 6 of
  16 threads. Exact labels are ~6% of value labels by count (20% of the
  value loss by weight). Without the step a round runs ~2.5-3.2x faster.
- **Comparing two nets directly is cheap.** On one fixed fight set the
  paired sd per fight is ~0.37-0.39 and fights cluster by cell (design
  effect ~1.4), so ~7-10k fights decide a 0.01 gap: 1-2 minutes at ~118
  fights/s. Rankings agree across halves of a set (0.86-0.94). This tells
  you which net is better *on that set*; generalising needs fresh fights.
- The CPU did heavy work for an estimated 35-40% of the last ~52 hours:
  waiting for the 2-hourly manager wake-ups, duplicate runs, a 4-hour
  hang, and slow test suites (~80 min for the three slowest). Being
  re-measured.

## Stop doing

- Label, curriculum and round variants at one-turn depth. Cap self-play
  at 2-3 rounds.
- The exact-solver step inside training rounds. If exact labels stay, a
  separate background process grows the database.
- Reading a single-seed pass, or the best of N rounds, as a result.
  Recipe questions get ≥5 seeds per arm or aren't asked; questions about
  one net go to a paired test on fresh fights.
- The equal-weight average or value MSE as the only verdict. Report
  hallway / elite / boss separately, and keep the train half (strength)
  apart from the held-out gap (generalisation).
- Treating the warm-start curve's Silent win rates as decisive: Silent's
  training-seed sd looks like ~0.03 from three cells. Read its MSE gate
  and stall counts.
- Starting runs only when a manager wakes up.

## Directions, best value per CPU-hour first

1. **Re-read every stored result by fight type and half** (zero CPU).
   Changes how every past verdict reads; may reveal that rounds 3-10 lost
   elite and boss ground, and whether rung 4's elite gain is real.
2. **Find the ceiling and test depth** (~2-3 CPU-h). Two-turn search
   against one-turn, paired, on elite and boss cells; bounded exact solves
   at the start of the shortest hallway cells for a ceiling. Then share
   sampled draws between sibling options in the two-turn search (common
   random numbers) and repeat. Depth is Stockfish's main lever and was
   ruled out here on a bench 5x less sensitive than today's. If depth
   pays, the amplifier is a deeper teacher distilled into the one-turn net.
3. **A champion ladder with sequential testing** (fishtest's pattern,
   ~0 CPU to build, minutes per test). One champion net; every new net
   plays paired fresh fights against it under an SPRT (H0 ≤ 0, H1 ≥ 0.01),
   reported by fight type; promote on H1. Training-seed luck becomes
   something we keep instead of something we fight. First candidate: an
   ensemble of three seed retrains.
4. **Low-HP training coverage** (~2 CPU-h). Self-play starts at ≥10% of
   max HP (≥8 HP for Ironclad); hallway tight cells start at a median 3-5
   HP. The one regime where the nets trail is one their training never
   starts in.
5. **A lean training loop**: no solve step, 2-3 rounds, seeds instead of
   rounds. ~3x per run; the confirmation run also tells us which of the
   night's three changes produced its +0.04.
6. **Goal 1 by mechanics**: a standing primitive-response probe (does
   value move the right way when a card's damage, block or cost changes?),
   then a pilot on how held-out play scales with training content. If
   coverage pays, move a minimal runtime registry and generated cards,
   *with new mechanics in them*, ahead of the fidelity specs in the queue.
7. **A job queue** so the CPU never waits for a manager: a queue file and
   a runner that starts the next job when a slot frees (at most two heavy
   jobs, capped threads, a stall watchdog). Managers add jobs and read
   results. A test-size profile cuts the slow suites.
8. **An Act-1 gauntlet** as goal 2's metric: hallway fights, elites and
   the boss in sequence with HP carried over, paired against the champion.
   It lets the game weigh hallway attrition against elite and boss
   survival, and it is the first step toward the run layer.

## Open questions

- What does near-perfect play win on tight2, by fight type? If hallway
  cells sit within ~3 points of the heuristic, they leave the gate.
- Does two-turn search with shared draws beat one-turn by ≥0.02 on elite
  and boss cells?
- Does rung 4's held-out elite gain (+0.030, found after looking) hold on
  fresh seeds?
- Is the nets' hallway deficit low-HP coverage, or search already being
  exact in short fights?
- Which of exploration 0, branch rollouts and curriculum labels made the
  night's +0.04?
- Does held-out play scale with mechanic coverage? That decides the queue
  reorder.

## Addendum: the zero-CPU first checks (same day)

Five single-thread analyses, each re-derived by a skeptic with its own
script. Scripts are in `scripts/analysis/` (`regroup.py`,
`sprt_replay.py`, `hp_coverage.py`, `exact_share.py`,
`primitive_probe.py`, `cpu_timeline.py`, and a `check_*.py` beside each);
outputs go to `scripts/analysis/out/` (not committed).

**1. Results by fight type** (`regroup.py`; held up exactly).
- Every net's lead is in elites and bosses; hallways are level or
  slightly negative (-0.013 to +0.006). Train half: elites +0.046 to
  +0.067, bosses +0.109 to +0.138 (five 3-seed arms). Held-out: elites
  -0.019 to +0.017, bosses +0.026 to +0.073.
- **Training-seed sd is 2.5-3.5x larger per fight type than overall**:
  elite 0.017 / 0.019, boss 0.022 / 0.025 (train / held-out), against
  0.0066 / 0.0076 for all cells. A 3-seed vs 3-seed test on elite or boss
  cells detects only 0.035-0.058. Use the per-type sd in MDE lines.
- The best measured arm on train elite+boss is the **round-2 retrain**,
  +0.084 [+0.065, +0.103]. Later rounds are lower (round 10 held-out
  elite+boss -0.035 vs round 2, seed-level [-0.068, -0.003]): suggestive,
  not established, and round 2 also had about twice the outcome labels.
- Rung-4 B vs A on held-out elites: +0.030, every seed agrees, but the
  seed-level interval includes 0 and B loses hallways, so its overall
  effect is about 0. It moves wins between fight types.
- Caution: even the old 10-24 baseline nets beat the heuristic on
  bosses by about +0.10. Much of the boss lead may be a weakness of the
  heuristic on bosses, not something curriculum learning bought.

**2. Sequential testing** (`sprt_replay.py`; numbers reproduce, three
readings corrected).
- A normal-form SPRT (H0 lead <= 0, H1 >= 0.01, alpha = beta = 0.05) is
  calibrated (false-pass 0.03-0.07 on synthetic fights) and stops after a
  median of ~2,900 paired fights (90th percentile ~5.6k); at H1 0.02,
  ~900. Clustering by cell is mild (design effect 1.1-2.3).
- **A pass doesn't cross card pools.** Every net passes against the
  heuristic on train cards; none of those passes is confirmed on
  held-out cards. Silent's two halves disagree in opposite directions.
- Same recipe, different training seed gives **real, reproducible**
  strength differences (sd ~0.0067 per net): selecting and ensembling
  seeds is a legitimate gain, not just noise to average out.
- Ladder parameters (item 3 of Next): fresh spec seeds in the calibrated
  cells, drawn in random order stratified over both halves and the three
  fight types, 5 seeds per cell; H0 <= 0, H1 >= 0.01, alpha = beta =
  0.05; cap 16,000 paired fights, keep the champion if inconclusive; and
  at the stop require the held-out half's lead >= -0.005. A quick screen
  at H1 0.02 with a 4,000 cap is fine but catches a true +0.01 only about
  half the time. Recipe questions still need >= 3 seeds per arm.

**3. Low-HP coverage and the solver's cost** (`hp_coverage.py`,
`exact_share.py`).
- The gate is a low-HP-from-turn-1 test: 61% / 68% of all tight2 fights
  (train / held-out) and 84% / 91% of hallway fights start at 1-8 HP,
  against enemies at full HP. Training has plenty of 1-8 HP states
  (13-19% of value labels) but **94-96% of them come late in fights that
  started at a median 22-26 HP**, and the exact draws are all end-of-fight
  tails. No self-play game starts below 8 HP. The gap is in kind, not
  amount: a low-start-HP slice in self-play is the cheap test.
- The solve step is **70% of round wall time** (pooled 13,419 of 19,058
  s over 16 rounds). Exact labels are 5.9% of value labels by count, 20%
  by loss weight (fixed by `exact_share`); self-play states almost never
  hit the database (0.09-0.15%).
- (An analyst reported `db/train.sqlite` missing; it is there, 766 MB.
  False alarm.)

**4. Primitive probe** (`primitive_probe.py`, 18 nets, ~1 s per net).
- Damage and block: nearly every net responds the right way (17/18 and
  18/18 on average). Cost: making a card 1 cheaper lowers its value for 9
  of 18 nets. Self-damage added to a card raises value for 12 of 18, but
  that probe is far outside the training data, so "the nets value the
  Bloodletting / Hemokinesis bundle" is a guess, not a finding.
- The violation count is a stable property of a net but does **not**
  track playing strength (Spearman with held-out lead +0.45, wrong sign,
  n = 13) and doesn't separate recipes. Keep it as a transfer diagnostic,
  never as a gate.
- What it points at for goal 1: primitives the training cards only ever
  vary together (cost with damage) are learned as bundles. Training on
  card variants with one primitive changed (generated cards) is the fix
  to test, judged on Silent transfer, not the Ironclad gate.

**5. Where the CPU time went**, 10-28 00:00 to 10-30 12:00 (60 h,
`cpu_timeline.py`).
- A productive heavy job ran ~58% of the time (experiments alone ~44%).
  Standby 11% (fixed since), hung-only
  processes ~10% (two `test_sweep` hangs of ~9.5 h and ~7 h, one seen by
  a manager that stood down because of the lock rule), compaction-only
  ~4%, idle ~16%. The two job slots were 32% used on average.
- `test_rounds` takes 594 s alone but 2,208 s beside other suites
  (3.7-8x slower): run slow suites alone or in their own slot.
- A queue with a stall watchdog and a pre-filled backlog would have
  raised the busy share toward 75-80%. The 12:00 manager is building it
  (`docs/specs/` job queue spec, 22f749b; steps 1-3 980f736).

**What changes in the plan.** The champion ladder gets the parameters
above and a held-out guard. Champion candidates start from the round-2
retrains (and a seed ensemble of them). MDE lines use per-type seed sd.
The low-HP-start slice joins the lean-loop run. Goal 1's next experiment
is training on generated one-primitive variants, judged on Silent
transfer. The boss lead needs a check against a stronger baseline than
the heuristic (depth-2 search) before it's claimed as learned strength.
