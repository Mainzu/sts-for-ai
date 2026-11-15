# Learned play

Status: closed (2026-10-26, built; its record is docs/research/learned-play-results.md and later specs).

## Outcome

Find out which training changes make search with a learned evaluator play
better than search with the hand-written heuristic, on training and unseen
cards, while keeping the effect-feature net's generalisation lead. Each
change is a switch; an overnight sweep measures them on the evaluation
bench.

Builds after `triggers-and-conditions` and `eval-bench`. Framing from
`docs/research/learned-play-and-generalisation.md` (expert iteration lite).

Non-goals:
- Changing the engine, search algorithm, score or the feature format.
- GPU training, full AlphaZero/MuZero, text/LLM card encoders.
- Learned policies (the net still only scores states).

## Behavior

### Step zero: size the teacher

Before any training, bench search + heuristic at several depths (today's
one turn; `sample_k` 2/4/8; two turns) for decision quality and strength
per second of compute. The chosen setting becomes the **deeper teacher**
used by switch 5, recorded in `docs/decisions.md`.

### Switches

One training pipeline, `scripts/learn.py --config <file>`, with these
independent switches (config files under `configs/`):

1. **Search-value targets** (off = today: final outcome only). A state's
   label = λ · final score + (1 − λ) · the search value of that decision.
   Every option's afterstate scored by the search during self-play becomes
   a labelled example too (labels for all searched nodes, not one per
   decision). λ default 0.5.
2. **Heuristic correction** (off = the net predicts the score directly).
   Output = heuristic estimate + a learned correction, so an untrained or
   unsure net plays like the heuristic.
3. **Ranking loss** (off = squared error only). Adds a pairwise term:
   for options of the same decision, the net should order them as their
   labels do. Weight default 1.0.
4. **Self-play rounds** (off = one round from the heuristic teacher). N
   rounds: play with search + the current net (with a little exploration:
   pick options by softmax over their values, temperature default 0.05),
   retrain on the new games plus the previous round's, repeat. N default 3.
5. **Deeper teacher** (off = one-turn search). Data-generating search uses
   the setting chosen in step zero. The *evaluated* agent always plays
   with the same one-turn search, so results compare evaluators, not depth.

6. **No-death HP-loss target** (off = the net predicts the 0–2 score).
   - *Simulation:* self-play for training runs in a **no-death** mode: HP
     starts at its real value and counts down as usual, but reaching 0
     doesn't end the combat (HP goes negative). Combats still end on a win,
     or at a turn limit (default 50) with a fixed penalty. In-combat effects
     that read the player's HP keep working at the right moments.
   - *Net (risk-neutral):* predicts the **spread** of HP lost from this
     state to the end of combat, as 9 quantiles (10th…90th percentile),
     labels capped at 150. It sees the current HP like any other feature.
   - *External formula (fixed, not learned):* from the spread and the real
     current HP, P(win) = share of the spread below current HP; end HP per
     quantile gets end-of-combat healing (Burning Blood, and Meat on the
     Bone-style rules if added) before scoring; score = P(win) × (2 −
     expected HP lost when winning / 100). Search uses this score at its
     leaves, so the agent is cautious at low HP without retraining.
   - With switch 1, labels are the search's HP-lost values mixed with the
     outcome, in HP. With switch 2, the correction is added to the
     heuristic's HP-loss estimate (median), and the net learns the spread
     around it. With switch 3, the ranking term uses the external score.

Everything else (architecture, features, optimiser, data size per round)
is fixed across configs. Data from a teacher that doesn't depend on the
net (rounds = 1) is generated once per teacher setting and reused.

### Registry: keep every dataset, run and model

So old experiments never need redoing when comparing architecture
decisions:

- **Datasets store games, not features.** `datasets/<id>/` holds compressed
  game records: setup (character, encounter, deck, start HP, seed), every
  action, the search's per-option values at each decision, and the outcome.
  A `manifest.json` records the engine git commit, the golden-trajectory
  hash (rules version), the generating config and the parent model if any.
  The id is a hash of the manifest. Datasets are never overwritten or
  deleted by scripts.
- **Feature caches are disposable.** Encoding a dataset for a feature
  format writes `cache/<dataset id>-<format>.npz`; the cache folder has a
  size cap (default 10 GB, oldest evicted first) and is rebuilt on demand
  by replaying the games. Replay checks the rules version and refuses
  (clearly) a dataset recorded under different rules.
- **Runs are immutable.** `runs/<date>-<config name>-<short hash>/` holds
  the config, the git commit, the dataset ids used, the model file, the
  training curves (loss per epoch, train and validation) and the bench
  results JSON. A rerun makes a new folder.
- **One index.** `runs/index.csv` gets one line per run: id, date, commit,
  config switches, feature format, bench version and the headline bench
  numbers. `bench_compare.py` accepts run ids, so any runs ever made can be
  compared, with a warning when their bench versions differ.
- The existing `data/*.npz` and `models/*.pt` stay where they are; the
  registry starts with learned-play's first run.

### Sweep (ladder + leave-one-out)

`scripts/sweep.py` runs:
- **Ladder:** baseline (all off) → +1 → +1+2 → +1+2+3 → +1+2+3+6 →
  +1+2+3+6+5 → all on (+4). Rounds come last because they cost the most.
- **Leave-one-out:** from all on, turn each switch off in turn (6 configs).
- 12 trainings, each followed by a bench run, 1 training seed, in one night
  (~8 h). Each config's training plus bench must
  fit ≤ 40 min; the sweep sizes data per round to hold that and prints the
  projected total before starting.
- Output: one registry run per config (per round for switch 4), and a
  comparison table (`bench_compare.py`) saved as
  `runs/sweep-<date>.md`.

### Confirm

`scripts/sweep.py --confirm <configs>` retrains the top 2–3 configs with 3
seeds each, plus the best config with id features (the control), in a
second night. Result goes to `docs/research/learned-play-results.md`.

### Gates for the overall goal (on the confirm run)

- **Plays better:** on the bench's tight fights, search + best net beats
  search + heuristic in win rate with non-overlapping 95% intervals, on
  training-card **and** held-out-card halves.
- **Decides better:** lower regret on contested decisions, both halves.
- **Generalisation kept:** the effects version beats the ids version on
  held-out regret and held-out prediction error.
- **Monotone rounds:** each round's search + net is at least as strong
  (win rate interval not lower) as the search that generated its data.
- **Lookahead must not hurt:** search + net ≥ greedy on the net ≥ no
  lookahead, on win rate.

If a gate fails, the run is still kept and reported as an honest negative
result; nothing is tuned on the test sets.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Engine, search, features, score | Unchanged | existing suites, golden trajectories |
| Existing training (`train.py`, `stsnet.py`) | Checks 6, 8, 9 still pass with the current pipeline; `learn.py` with all switches off reproduces today's net within its validation error | `generalise.py`, `transfer.py`, `granting.py`; new test |
| Evaluation bench | Read-only; every result goes through it | bench determinism tests |
| `sts.run` / `sts.search` | Recording option values per decision may add an optional argument only | `py/tests/test_sts.py` |

## When in doubt

Prefer fewer, comparable runs over more runs with changed settings between
them.

## Scope

May change: `scripts/` (learn, sweep, registry, net heads, losses, tests),
`configs/`, `datasets/`, `runs/`, `cache/` (all gitignored except
`runs/index.csv` and `runs/sweep-*.md`), `.gitignore`, `py/src/lib.rs` (only an optional argument to record per-option
search values from `run`), `results/` (gitignored), `docs/`, `README.md`.

Off limits: `engine/` except exposing values search already computes and
the no-death simulation option (switch 6; off by default, normal play
unchanged), the feature format, the score, the bench's sets and reference
values. No new dependencies.

## Decisions taken (provisional, also in docs/decisions.md)

- Ladder + leave-one-out sweep, one seed per config overnight, top configs
  confirmed with 3 seeds the next night.
- The evaluated agent always uses one-turn search; depth only changes the
  teacher.
- The net corrects the heuristic rather than replacing it (switch 2), and
  each switch is tested both ways.

## Verification

Tests to write first:
- Search-value targets: for a hand-made decision with known option values
  and outcome, the labels equal λ-mixes as specified.
- Heuristic correction: a net whose correction outputs 0 scores every state
  exactly as the heuristic.
- Ranking loss is 0 when the net orders options like the labels and > 0
  when one pair is flipped.
- Exploration: temperature 0 picks the top option; the softmax picks follow
  their probabilities over 10k draws.
- Registry: replaying a stored dataset re-encodes features identical to
  encoding at generation time; a dataset whose rules version differs is
  refused with a clear message; writing a run twice makes two folders and
  two index lines; the cache evicts oldest files past its cap.
- No-death mode: a combat whose player reaches 0 HP continues with
  negative HP and ends on a win or at the turn limit; with the option off,
  the golden trajectories still match.
- External formula: a spread entirely below current HP gives P(win) = 1; a
  spread entirely above gives 0; for a deterministic case, the formula's
  score equals the engine's score after Burning Blood's heal.
- Quantile loss: predicted quantiles of a known distribution converge to
  its true quantiles within 5% on a toy fit.
- All switches off reproduces today's net's validation error within 5%.
- A 2-round smoke run (tiny data) completes and writes per-round numbers.
- The sweep prints its projected time and refuses to start a plan over
  the night's budget without `--force`.

End-to-end: the overnight sweep finishes and its comparison table shows,
per switch, its effect alone (ladder) and inside the full mix
(leave-one-out); the confirm run reports every gate.

## Don't guard

- Configs mixing feature formats (one format per sweep).
- Resuming a half-finished sweep (rerun it).
- Hyperparameter search beyond the listed defaults.

## Build steps

1. **Teacher sizing.** Bench search + heuristic at the depth settings;
   record the chosen teacher. Check: table in
   `docs/research/learned-play-results.md`, decision recorded.
2. **Registry.** Game-record datasets with manifests, replay into feature
   caches with the size cap, immutable run folders, `runs/index.csv`,
   `bench_compare.py` on run ids; self-play and training write through it.
   Check: registry tests.
3. **Search-value targets.** Record per-option values in self-play, label
   mixing, all-nodes examples. Check: target tests; all-off reproduction
   test.
4. **Correction head and ranking loss.** Check: their tests.
5. **No-death HP-loss target.** Engine no-death option, quantile head and
   loss, external formula, search leaves through it. Check: its tests,
   golden trajectories.
6. **Self-play rounds.** Loop, exploration, monotone check, data reuse.
   Check: exploration test, 2-round smoke run.
7. **Sweep runner.** Configs, ladder + leave-one-out, time projection,
   results folder. Check: dry run on tiny data; then the overnight sweep.
   Stop point: review the sweep table with the owner before confirming.
8. **Confirm run.** 3 seeds for the chosen configs plus the id control;
   gates. Check: gates reported (pass or honest fail).

## Amendment 1 (2026-10-24)

The first sweep showed switch 6 configs ranking below the random floor. Cause:
switch 1 mixed the **heuristic** search's values into training labels, but
those are ranking scores on the wrong scale (mean 0.98 vs real scores 1.71),
so labels were biased. The owner's direction: keep the
heuristic's influence to a minimum and train on ground truth, using the
heuristic only to make the first data cheap.

### Behavior (replaces the conflicting parts above)

- **Round 0 (bootstrap):** search + heuristic plays the games; labels are
  the games' real outcomes only. No heuristic values in any label.
- **Rounds 1–3:** search + the current net plays (exploration: softmax over
  option scores, temperature 0.05 on the 0–2 score scale), the net retrains
  on a sliding window of the last 2 rounds' games. Round 0's games are
  retired after round 2. Self-play rounds are part of every config, not a
  switch.
- **Switch 1, own-search targets** (off = outcome only): from round 1, a
  label mixes the real outcome with the current net's search result at that
  decision (λ = 0.5). With the score target: λ·outcome + (1 − λ)·search
  value. With the HP target: λ·(one-hot of the real HP lost) + (1 − λ)·the
  best option's outcome histograms as predicted by the current net, averaged
  by probability. Round 0 is always outcome only.
- **Switch 2 (heuristic correction): removed.** It keeps the heuristic
  inside every prediction. The spec's claim that an untrained correction
  plays like the heuristic is withdrawn.
- **Switch 3, ranking loss:** sibling order comes from the current net's
  search values, from round 1. Never the heuristic's order.
- **Switch 5 (deeper teacher): no longer a switch.** Self-play search depth
  is one setting: measure the speed of net-guided search, and take the
  deepest setting that keeps one round under ~20 minutes. Record it in
  `docs/decisions.md`.
- **Switch 6, HP target:** the net outputs a **histogram over HP lost**
  (1-HP bins from 0 to 30, wider bins up to 150, one bin for ≥ 150, plus a
  turn-limit bin), trained with cross-entropy, instead of 9 quantiles. The
  external formula reads P(win) as the probability below the current HP,
  applies end-of-combat healing per bin, and returns the expected score.
  No-death simulation as before.
- **Sweep: every combination** of the three remaining switches (target:
  score or HP histogram; own-search targets; ranking loss) = 8 configs, each
  with round 0 + 3 rounds, one training seed, one night. The time
  projection sizes data to fit. Confirm night unchanged (top 2–3 configs ×
  3 seeds, plus the id-feature control of the best).
- **Sweep guard:** after each config, if its tight-fight win rate or
  contested ranking is below the random evaluator's (bench baseline),
  stop the sweep and report.

### Gates (replace the gates above)

- **Deciding gate:** on the bench's tight fights, search + best net beats
  search + heuristic in win rate with non-overlapping 95% intervals, on
  training-card and held-out-card halves; HP lost reported beside it.
- **Generalisation kept:** the effects version beats the ids version on
  held-out win rate or HP lost (non-overlapping intervals), and on held-out
  prediction error.
- **Monotone rounds:** from round 2, each round's search + net is at least
  as strong as the previous round's (win-rate interval not lower).
- **Lookahead must not hurt:** unchanged.
- Regret and ranking against the heuristic reference are reported as
  diagnostics, not gates: the reference is itself a heuristic search.

### Verification (added)

- **Targets on the right scale:** for each round, the mean training label
  is within 0.1 (score) or 10 HP (HP target) of the mean real outcome of the
  same games.
- **No heuristic in labels:** with the heuristic teacher (round 0), labels
  equal real outcomes exactly.
- **Histogram:** probabilities sum to 1; P(win) at HP h equals the mass
  below h; averaging two outcome histograms with probabilities p and 1 − p
  gives their mixture; for a deterministic one-bin case the external score
  equals the engine's score.
- **Sweep guard:** a config made deliberately worse than random stops the
  sweep (dry run).
- Existing tests for removed parts (switch 2, quantile head, heuristic-value
  labels) are deleted with them.

### Scope

Unchanged areas. Code for switch 2, the quantile head and heuristic-value
labels may be deleted. Runs already in `runs/` stay (the registry is
append-only); `runs/index.csv` keeps their lines.

### Steps

A1. **Ground-truth targets.** Round 0 outcome-only labels, own-search
    targets and ranking from round 1, sliding window, monotone check from
    round 2, remove switch 2, the scale test. Check: the new tests.
A2. **Histogram head.** Bins, cross-entropy, external formula from the
    histogram, own-search histogram targets, remove quantiles. Check: the
    histogram tests.
A3. **Self-play depth and sweep.** Measure net-guided search speed, pick
    the depth, 8-config factorial, sweep guard, time projection. Check:
    dry run on tiny data, guard dry run. Stop point: start the overnight
    sweep only after the owner says so.
A4. **Overnight sweep,** then review the table with the owner.
A5. **Confirm run.** Gates reported (pass or honest fail).

## Amendment 2 (2026-10-25)

Amendment 1's sweep (`runs/sweep-2026-10-25.md`) showed later rounds getting
weaker: the best nets were rounds 1–2 (f-6 round 1: 0.531 / 0.516 tight-fight
win, f-136 round 2: 0.516 / 0.513), and round 3 finished below them in every
config. Round 0's 30k heuristic games left the window after round 2, so
rounds 2–3 trained on ~6.5k net games instead of ~33k, all from near-greedy
play of one net. One seed gave ±0.04 intervals, so no
switch effect was clear: own-search targets (switch 1) came out neutral, the
ranking loss (switch 3) was the only one with a positive sign, and the HP
histogram (switch 6) tied on the final round but gave two of the three best
single-round nets. The owner's direction: keep round 0 in until the net is
at least as good as the heuristic; drop switch 1, keep switch 3; test switch
6 and branch rollouts.

### Behavior (replaces the conflicting parts of Amendment 1)

- **Round 0 stays in the window until the net catches up.** Round k ≥ 1
  trains on Dk + D(k−1), plus D0 while round 0 is still in.
- **D0 is a larger heuristic pool, sampled.** Round 0 plays 60k games per
  target (20k per encounter group; validation unchanged). Round 0's net
  trains on a random half of the pool's examples (drawn across all games,
  not whole games). While round 0 is in, rounds ≥ 1 use a random sixth of
  the pool's examples (about 10k games' worth) instead of D0 whole, drawn
  once per seed and kept for every round of that seed. (The pool has no
  repeated states: 0 duplicate feature vectors in today's 30k-game set.)
- **Round 0's net is trained once per target** and shared by both seeds and
  the branch twins.
- **"At least as good as the heuristic":** after round k trains, its net's
  tight-fight win rate (one-turn search, the monotone check's specs) is at
  or above search + heuristic's on the same specs, by point estimate, on
  both halves (training cards and held-out cards). The heuristic's rate is
  measured once per config, on the same thinned specs.
- **Retirement is permanent, and later rounds then play more games:** once a
  round's net reaches that bar, D0 leaves from the next round on and does
  not come back. The window stays the last 2 rounds (no outdated games), and
  every round after retirement plays `n_late` games per group instead of
  `n_round`, so the window doesn't shrink to two small rounds at once.
  `n_late` is the largest size that fits the night when retirement comes as
  early as possible (after round 1); the projection prints it.
- **Switch 1 (own-search targets): removed.** Labels are real outcomes in
  every round (one-hot of the real HP lost with switch 6).
- **Switch 3 (ranking loss): on in every config,** no longer a switch. Sibling
  order still comes from the playing net's search values, from round 1.
- **New switch 7, branch rollouts** (off = no branches). From round 1, after
  each self-play game, one branch game per main game. The branch must be
  meaningfully different from what exploration would play: its option's
  search value is below the decision's best by more than the exploration
  temperature (so softmax gives it under e^-1 of the best's weight). Pick
  uniformly among the game's decisions that have such an option, force one
  of those options uniformly at random, and play on to the end with the same
  search, net and exploration. A game with no such decision gets no branch. The branch game replays the main game's
  actions up to that decision, so its states up to there are identical. Its
  examples (and ranking decisions) come only from states after the forced
  action, labelled with the branch game's own outcome; the main game's labels
  are untouched. Branch games join their round's dataset and window.
- **Binding:** `sts.run` gets an optional argument giving each game a forced
  list of opening actions (a branch = the main game's actions up to the
  branch point plus the forced option). The binding plays them before handing
  over to the agent; the engine is unchanged.
- **Sweep:** switch 6 (score / HP histogram) × switch 7 (branches off / on) =
  4 configs, each with **2 seeds** (seed changes the training seed of rounds
  ≥ 1, their spec seeds and the round-0 sample; round 0's pool and net are
  shared), round 0 + 3 rounds,
  one night. The time projection takes the worst case of each: D0 in every round's
  training (never retired) and `n_late` from round 2 (retired after round 1),
  plus the branch games' self-play. The random-floor
  guard and the monotone check are unchanged. The table shows both seeds of
  each config.
- Round-0 labels, the histogram head, the external formula, the guard and the
  self-play depth are unchanged.

### Verification (added)

- Window rule (net strength mocked): D0 stays in every round while no net
  reaches the heuristic on both halves; reaching it on only one half keeps
  D0; once a round reaches it on both, the next round has no D0, trains on
  the last 2 rounds and plays `n_late` games per group, and D0 stays out
  after a later round falls below.
- `round.json` holds the heuristic comparison and the window per round.
- Forced openings: a game given the first n actions of a recorded game
  reproduces its first n states exactly; with no forced actions, `sts.run`
  output is unchanged (existing tests).
- Branches: every branch game deviates at its branch point to an option
  whose recorded value is below that decision's best by more than the
  temperature; a game whose options are all within the temperature gets no
  branch; its examples come only from after that point
  and carry its own outcome; the main game's labels equal those without
  branches.
- Seeds: the two seeds of a config share round 0's pool and net and differ
  in training seed, later rounds' games and the round-0 sample.
- Pool sampling: round 0 trains on half of the pool's examples, spread over
  its games; rounds ≥ 1 use a sixth, the same in every round of a seed and
  different between seeds; one round-0 training per target in the sweep.
- Switch 1's code and tests are deleted; switch 3 has no off path in the
  sweep.
- The sweep projection fits the night; tiny dry run of the sweep completes.

### Scope

Areas as before, plus in `py/src/lib.rs` the optional forced-openings
argument of `sts.run` (binding only, default off). `engine/` stays off
limits.

### Steps

B1. **Round-0 window rule.** Window tests first, then the rule (including
    `n_late` after retirement) and the `round.json` fields; remove
    switch 1, make ranking always on. Check: window tests, existing suites.
B2. **Branch rollouts.** Forced-openings argument in the binding, branch
    games in self-play, branch labels. Check: forced-openings and branch
    tests.
B3. **Sweep.** 4 configs × 2 seeds, projection, README and decisions. Check:
    sweep tests, tiny dry run. Stop point: the overnight sweep starts only
    after the owner says go.
B3b. **Heuristic pool and sampling.** Tests first, then the 60k pool, the
    half / sixth samples, one round-0 net per target, the projection
    re-sized. Check: sampling tests, sweep tests, tiny dry run. Stop point
    as B3.
B4. **Overnight sweep,** then review the table with the owner.
Then A5 (confirm run) on the configs chosen at B4's review.

## Amendment 3 (2026-10-25) · built 3e334bd

B4 (`runs/sweep-2026-10-25-b4-colab.md`): no config beats the heuristic
(best mean 0.489 / 0.460 tight-fight win vs 0.528 / 0.496); target and
branching differ by less than the seed spread (up to 0.06 between seeds of
one config), so neither switch earned its cost. Two gaps: every training
game starts at full HP while the tight fights that decide the gate start at
calibrated low HP, so the nets rarely see the positions they're judged on;
and B4's rounds were sized for Python inference (~900 games per group),
before Rust inference (~8x self-play) and `sweep.py --jobs 2`. The owner's
direction: playing strength first; the cheapest config with a large training
investment; more variety by default (not a switch); more rounds.

### Behavior (adds to Amendments 1-2)

- **Varied setups in every training game (default, no switch).** Each
  self-play game (round 0's pool and later rounds) starts at a random HP,
  uniform over 10-100% of max HP (whole HP, at least 1), and uses the
  starter deck plus 3-15 random training-pool cards (uniform), both drawn
  per game from the spec seed. Validation games use the same distribution.
  The bench is unchanged (its decks and calibrated HP stay as they are).
- **Per-game HP in self-play.** `sts.run` accepts specs with a fourth field,
  the starting HP (binding only; three-field specs work as today). Game
  records already store each game's HP; replay uses it.
- **One config: the cheapest.** Score target (switch 6 off), no branch
  rollouts (switch 7 off), ranking loss on as before: fastest self-play (no
  no-death mode, no branch games) and the cheapest training. The switches
  stay in the code, off.
- **Rounds until the net clearly wins: at least 6, at most 10.** After each
  round from round 6 on, a run stops when its net clearly beats the
  heuristic: the spec's deciding gate on the tight fights (the monotone
  check's specs), the net's 95% win-rate interval wholly above search +
  heuristic's on both halves. Otherwise it goes on, up to round 10. Round
  0's data stays in until a net reaches the heuristic, as before. The run's
  final round is benched; `round.json` records the gate check per round.
- **New round-0 pool.** The varied setups change round 0's data, so the
  score pool (60k games) and its validation set are regenerated once,
  before the night; the dataset config records the variety settings, so the
  old pool is never reused by mistake.
- **Sweep:** 2 seeds of that config in parallel on the laptop (`--jobs 2`);
  the projection sizes `n_round` / `n_late` so 6 rounds fit the night, and
  rounds 7-10 run on into the next day when needed (up to ~70% longer). Guard and
  monotone check unchanged. The table shows both seeds and every round's
  tight-fight win rate against the heuristic's.

- **A watcher next to the sweep.** `scripts/sweep_watch.py --root <root>`
  reads the sweep's logs, run folders and the process's memory, and prints
  one line per event; it exits on a problem so the agent running the night
  is woken. Events (owner: "chatty"):
  - progress (doesn't exit): each finished round, with its tight-fight win
    rate next to the heuristic's and whether round 0 is still in;
  - problems (exits with the reason and evidence: log tail, memory,
    timings): a crash or guard stop; no log output for 30 min; a run past
    2x its projected minutes; memory above 90% of the system's limit; a
    label-scale warning.
  The agent passes each event on (progress notes too), and on a problem
  leaves the sweep running and waits for a decision, then restarts the
  watcher; it stops nothing on its own.

### Verification (added)

- Watcher (on a fake registry and logs): a finished round gives one
  progress line and no exit; a crash, a guard stop, a 30-min silence, a run
  past 2x its projection, a label-scale warning and memory above the limit
  each exit with that reason; a normal finish exits cleanly with the table
  path.
- Setups: over 3,000 generated specs, HP lies in [10%, 100%] of max and
  deck sizes in 13-25 (Ironclad starter 10 + 3-15), each value range
  covered; the same seed gives the same specs.
- Per-game HP: a game run with a 4-field spec starts at that HP; 3-field
  specs give today's results unchanged.
- Pool: a round-0 dataset generated with the varied setups has a config
  different from the old pool's, so `registry.find` doesn't return it.
- Stop rule (net strength mocked): a run with the gate met at round 6
  stops after round 6; met first at round 8 stops after 8; never met stops
  after round 10; meeting it before round 6 doesn't stop the run early.
  Only the final round is benched.
- Plan: 1 config x 2 seeds; the projection with `--jobs 2` fits 6 rounds in
  the night and prints the worst case (10 rounds); tiny dry run completes.

### Scope

As before, plus in `py/src/lib.rs` the optional per-spec HP in `sts.run`
specs.

### Steps

C1. **Varied setups.** Spec generation (HP and deck size), per-spec HP in
    the binding, validation sets. Check: setup and per-game HP tests.
C2. **Sweep.** One config, rounds 6-10 with the stop rule, 2 seeds with `--jobs 2`, the score pool
    regenerated before the night, projection. Check: sweep tests, tiny dry
    run, `--plan --jobs 2` output. Stop point: the overnight sweep starts
    only after the owner says go.
C3. **Watcher.** `sweep_watch.py` with its tests. Check: watcher tests.
C4. **Overnight sweep** with the watcher, then review the table with the
    owner.
Then A5 (confirm run) if a net clearly beats the heuristic.

## Amendment 4 (2026-10-26)

Amendment 3's sweep (`runs/sweep-2026-10-26.md`; analysis in
`docs/research/learned-play-results.md`, "why rounds don't improve"): no
round reached the heuristic (final 0.475 / 0.445 vs 0.528 / 0.496). Greedy
self-play strength is flat from round 1 to 10 (score 1.50-1.52, the
heuristic's 1.51), while exploration (softmax at temperature 0.05) costs
every net ~8 points of win rate and ~0.21 score in the games whose outcomes
are the labels. So each net learns the values of its noisy self-play policy
(it undervalues mid- and high-HP states by ~0.08-0.10 on greedy play), and
greedy search over those values improves toward the best noisy policy, then
stalls. The owner's direction: labels from greedy play, variety from branch
rollouts; a higher memory cap; the monitor reports to the session that
started it.

### Behavior (adds to Amendments 1-3)

- **Greedy self-play.** Every round's self-play search plays the best
  option at every decision it searches (temperature 0, no softmax), so every
  label is an outcome of the greedy policy that search + net actually plays.
  Round 0 (search + heuristic) was already greedy.
- **Branch rollouts give the variety (switch 7 on, in the one config).**
  From round 1, each main game gets at most one branch game, as Amendment 2
  defines it, except that the branch threshold no longer comes from the
  exploration temperature: a decision qualifies when one of its options is
  valued below the decision's best by more than `branch_gap` (default 0.05
  on the 0-2 score scale, the old temperature's value), one such decision is
  picked uniformly per game and one such option uniformly. The branch game
  replays the main game to there, plays the forced option and then plays
  greedily. Its examples come only from after the forced action, with its
  own outcome; main games' examples are all their sampled states, as now.
  So every label is a greedy-play outcome from the state it labels.
- **Varied setups, the stop rule (rounds 6-10), the round-0 window rule and
  pool, the guard and the monotone check: unchanged.** The plan is the
  config `score+branch` (score target, branches on, ranking loss on) x 2
  seeds, run side by side with `--jobs 2` after `--round0` (round 0's pool
  and net are reused: round 0 has no branches and no exploration, so it is
  the same as Amendment 3's).
- **Higher memory cap, and the true worst case.** `WORKER_GB` rises from 5
  to 6.5 (two runs ~13 GB of the dev machine's memory). The
  largest training set is counted as `learn.py` builds it: round 0's later
  sample plus two rounds at `n_round` while round 0 is in, and two rounds at
  `n_late` once it is out (never round 0 with `n_late` rounds), with branch
  examples included. `n_round` is the largest that fits the cap with round 0
  in (instead of fixed at Amendment 1's 1,079), `n_late` the largest that
  fits with it out, both still limited by the night and the 20-minute round.
  The 2x peak model is checked once against a real round at the planned
  size; the cap is lowered if the measured peak is above it.
- **The monitor reports to the session that started it.** The night session
  runs `sweep_watch.py` as its own background job; the watcher's exit (a
  problem, or the finish) wakes that session, which decides whether it can
  fix the problem then (and restarts the watcher) or tells the owner. No
  agent relays events elsewhere, and no agent polls; the
  session reads the progress lines from the watcher's output when it wakes.

### Verification (added)

- Greedy: in round >= 1 self-play, every recorded action of a main game is
  the best-valued option of its decision (first best on ties); a branch
  game's actions are greedy everywhere except its replayed prefix and the
  forced option.
- Branch threshold: every forced option is valued below its decision's best
  by more than `branch_gap`, independent of the temperature (with
  temperature 0 branches are still picked); a game whose options are all
  within `branch_gap` of the best gets no branch.
- Labels: a main game's sampled states and a branch game's states after its
  forced action carry their own game's outcome (Amendment 2's branch label
  tests hold at temperature 0).
- Sizing: `train_examples` matches the largest training set `learn.py`
  builds under each window state (mocked retirement after round 1 and
  never), branch examples included; the sizes fit `WORKER_GB` = 6.5, the
  night and the 20-minute round; `n_round` and `n_late` are each the largest
  that fits.
- Memory: one real round at the planned size (one process) has a peak
  working set at or below `WORKER_GB`; the measurement is recorded.
- Branch cost: the self-play time factor and branch examples per main game
  are measured at temperature 0 on varied setups (B2's 1.42x and the assumed
  0.5 were at temperature 0.05, full HP) and replace the constants.
- Plan: `score+branch` x 2 seeds; `--plan --jobs 2` prints the sizes, the
  largest training set and the projection; tiny dry run completes.

### Scope

As before (Amendments 1-3). No binding or engine change: temperature 0 and
forced openings exist.

### Steps

D1. **Greedy self-play and the branch threshold.** `branch_gap` separate
    from the temperature, temperature 0 in the sweep's config, branches on;
    measure the branch cost at temperature 0 on varied setups. Check: greedy
    and threshold tests, existing branch tests.
D2. **Sizing.** `WORKER_GB` 6.5, the true worst case, `n_round` sized too,
    the new branch constants; measure one real round's peak memory. Check:
    sizing tests, the measured peak, `--plan --jobs 2`, tiny dry run.
D3. **Monitor procedure.** README's sweep section and the night steps: the
    watcher runs as the session's background job and reports to it. Check:
    docs read back against this amendment.
D4. **Sweep** (`--jobs 2`, round 0 reused) with the watcher, then review
    the table with the owner. Starts once D1-D3 are verified (the owner's
    go, 2026-10-26). **Superseded, won't run:** the curriculum spec's run
    (`docs/specs/curriculum.md`, step 8) replaces it, with curriculum labels
    and runs sized to free memory instead of `WORKER_GB`.
Then A5 (confirm run) if a net clearly beats the heuristic.

## Amendment 5 (2026-10-28): the deciding gate compares paired results · built c18a379

The curriculum night (`docs/research/learned-play-results.md`, "Curriculum
night"): nets level with the heuristic from round 2, the best a 0.035 lead
on one half, and the gate never met. The gate compares two independent 95%
intervals (each about +-0.042 on ~550-610 fights), so the net needs a lead
of about 0.085. But both players play the same fight specs, and search is
deterministic per spec: most of each interval is which fights are hard,
which is shared. The owner agreed (2026-10-28) to compare the results fight
by fight.

### Behavior (replaces the deciding gate's test)

- **Per-fight results.** The tight-fight check records each spec's result
  (won 1, lost 0) for the net and for search + heuristic, in spec order;
  `round.json` keeps them (`tight_results`: per player, per half, a string
  of 0/1). `tight_win` (the Wilson intervals) is derived from them as now.
- **Paired gate.** Per half, d = net's result - heuristic's on each spec
  (-1, 0 or +1). The lead is mean(d); its 95% interval is mean(d) +-
  Z * sd(d) / sqrt(n) (sd with n-1). The half passes when the interval's
  lower end is above 0. The gate is met when both halves pass; the stop rule
  is unchanged. `round.json`'s `gate` records per half the net's and the
  heuristic's intervals (as before), `lead` [mean, lo, hi], `n` and `above`.
- Unchanged: the round-0 window rule (point estimates, "reaches"), the
  monotone check, the guard. A finished round reused on resume keeps the
  gate it recorded.

### Verification (added)

- `paired_gate`: identical results give lead 0 and fail; a net that wins
  every spec the heuristic wins plus k more gives lead k/n and passes when
  the interval clears 0; equal win rates on different specs give lead 0 and
  fail; one half passing isn't enough. The interval matches a direct
  computation of mean +- Z * sd / sqrt(n).
- Stop rule tests (mocked per-fight results) as Amendment 3's.
- The night's nets: the paired lead per half of s1 r4 and both final nets,
  replayed (results recorded in the results doc).

### Steps

E1. Per-fight results and the paired gate in `learn.py`. Check: gate and
    stop-rule tests, `test_rounds`; replay the night's nets.

**Note (2026-10-29, `docs/specs/tight-fights-v2.md`):** the tight fights are
now `tight2.json`, many calibrated cells (deck x encounter at a start HP)
with 20 seeds each. The paired gate's interval is taken over cells: per
cell, the mean of d over its specs; then mean +- Z * sd / sqrt(cells). A
cell's fights share deck, encounter and HP, so counting fights as
independent understated the interval. `tight_win` takes the per-cell
interval in place of Wilson's.
