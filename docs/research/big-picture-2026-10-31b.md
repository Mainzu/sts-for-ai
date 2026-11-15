# Big-picture review, 2026-10-31 (second, 16:45)

Run by manager run bb961751 after the generated-power arms read (a major
goal-1 result). Workflow `big-picture-review`: six analysts, a synthesis,
skeptics on the six key claims. Read-only. The newest review outranks the
queue's order. (Paths to scratchpad scripts below are from the analysts'
session and won't exist later.)

## Manager's reading (what changes)

- **Skeptics:** one claim holds (the goal-1 thesis is unproven at current
  strength), five are "overstated", two of them partly refuted. The data
  behind each is right; the generalisations are not.
- **Depth is real but narrow.** +0.061 / +0.055 (heuristic / net leaves)
  on held-out elites and bosses checks out, but it covers 4 Ironclad
  encounters on one half, the fallback rule was chosen after looking at
  those fights, and per encounter depth and the net do *not* add (Nob:
  they substitute, -0.10; Lagavulin: they complement, +0.16). "Largest
  lever on general play" is not shown: no hallways, no generated content,
  train half unread. So the next depth runs measure where it hasn't been
  measured (a novelty slice, hallways), not the train half at full size.
- **Seed noise is bigger than this file said.** Pooled training-seed sd
  over 66 runs is 0.010 train / 0.013 held-out on tight2 (skeptic
  reproduced it exactly), not 0.006-0.0075. MDE for 3 paired seeds is
  ~0.02-0.03 unless arms share data (pairing corr 0.8-0.99 for data and
  rates/thr, ~0 for the gen arms). Every queued arm states its MDE.
- **The ladder is cheap and unused, but its payoff was oversold.** se per
  half is ~0.006 at typical stop sizes (not 0.003), and seed picking adds
  only ~0.003 over a champion that is already the best of 3. The real
  value: a cheap cross-recipe check of the product (are data40k / lean-thr
  nets stronger than the 10-29 champion when played paired?). Queued.
- **Goal 1:** content breadth doesn't transfer (this run's read), and the
  effects-vs-ids thesis has never been tested at current strength; the
  only direct evidence (warm-start zero-shot +0.024 / +0.060, check 9) is
  weakly positive. An ids twin of lean-thr is a config change: run it.
  The generated bench has no oracle arm, so "no transfer" can't yet be
  told from "no headroom"; the nets' swap cost is 0.040, twice the MDE.
- **Direction for goal 1** (synthesis, adopted as the working hypothesis):
  signals the simulator can produce for any content (depth; a power's
  effect measured by simulating it over a few turns) instead of
  hand-written per-mechanic tables or more random content. First checks
  cost seconds of CPU (measured-effects vs the 43 test powers' swap cost;
  top-3 root pruning on the puzzles).
- **Owner decision** (not started): re-scope the rules-engine series:
  widen registry-lite to generated attacks, skills and monster patterns,
  retrain after each spec instead of keeping old nets bit-identical, defer
  fidelity-only specs. Listed under "For the owner".

## Diagnosis (synthesis)

Where the project stands. On goal 2 (official content), the strongest player measured is the champion net with two-turn fallback search: 0.591 on held-out elite and boss fights, against 0.498 for the one-turn heuristic (docs/research/depth-pilot-2026-10-30.md, job 0044b). The best one-turn net leads the heuristic by +0.037 overall (results/ladder/log.jsonl, test 0001). On held-out cards it is only level with the heuristic (+0.003 to +0.006 on tight2). On goal 1 (random and custom content), nothing learned has transferred. 128 generated powers gave -0.006 (se 0.010). The one big fix, rate features (+0.10 to +0.20 on Demon Form fights), is a hand-written table of trigger and effect pairs (engine/src/agent.rs hook_rates). Random content covers power cards only. There is no absolute scale and no run-level measure, so "Stockfish-level" cannot even be stated yet.

The underlying pattern, which all six analyses reach from different sides: playing strength moved only when the player got information it did not have before. Lookahead gives it at decision time (+0.055 to +0.061, z about 4). More varied games give it in training (+0.01 per doubling, and round 1 over round 0 gives +0.018). A feature in outcome units gives it about one mechanic (rates). Making the targets on the same states more accurate never moved play: 0 of 7 label, loss, curriculum and solve-step variants cleared noise, even when MSE or regret fell by a third. Every failure on unseen content is a payoff that lands past the one-turn horizon (Demon Form, Guardian Mode Shift, generated scaling powers). So in this design, generalisation comes from the simulator, roughly in proportion to how far it looks ahead. A net learning from primitive syntax has not delivered it, and the encoding thesis has not been tested against an ids twin at current strength.

What has held the project back is the unit of work more than any one bug. The main loop has been "recipe science": train an arm on 3-5 seeds and compare its tight2 lead over the heuristic. That instrument cannot resolve the effects being chased. Training-seed sd is about 0.010 on train and 0.013 on held-out, pooled over 16 groups. Evaluation noise is only about 5% of the variance. A 3-seed read can only detect about 0.02-0.03, yet most arms expected about 0.01. The fight-only gate passes a null recipe about 20% of the time, which matches the night's 4 false passes. About half of the readings above 0.03 that were later rechecked were artifacts. The costliest one, the 10-24 claim that "a deeper teacher doesn't play better", was a node-cap bias. It pointed about five days of work at labels and curriculum. Meanwhile the cheap, well-powered instrument sat almost unused: the SPRT ladder compares fixed nets at se 0.003 in 1-3 minutes, and it has run 3 times.

The fix is to change the unit of progress. The product becomes "net plus search", measured on a ladder, as Stockfish measures itself. The main investment becomes making search cheap and labelling data with search (the GNU Backgammon and NNUE recipe). Goal 1 is pursued through what the simulator can show the evaluator (depth, effects measured by simulation), not through hand-written features for each mechanic or through more random content. Recipe experiments are allowed only when the expected effect is at least the computed MDE, with seeds paired.

## Directions, ranked (synthesis)

### 1. Ladder every finished net, then redefine the champion as net plus search

**What:** Queue one job that runs ladder.py test on every finished r1/r2 net against the current champion: data40k x3, lean-thr x5, lean-rates x5 (with --no-promote, since rates are off-recipe), cover21, and lean-distil s1 and later seeds. Promote winners that pass the held-out check. Then name the product player as 'champion net + two-turn fallback on elites and bosses, one-turn on hallways'. Screen candidates at one turn (like fishtest's short time control) and confirm passes at two turns on elite and boss cells (the long time control).

**Why:** The ladder resolves 0.005-0.01 between fixed nets in minutes (se about 0.003), while training a candidate takes about 150 minutes. Best of N at seed sd about 0.01 is worth about +0.01, the same as one data doubling, for under an hour of CPU. It also gives every later comparison one fixed reference instead of a lead over the heuristic.

**CPU:** About 2-4 thread-h for about 15-20 nets at one turn. Two-turn confirmations cost a few thread-h each until top-k pruning (rank 2) is built.

**First check:** Ladder the three data40k r1 nets against the champion, under 10 minutes each. If any of them passes, the champion is already out of date.

**Serves:** Goal 2 (product strength and the yardstick); it also gives goal-1 reads a fixed reference.

### 2. Top-k verified depth: make two-turn search 3-5x cheaper

**What:** Run one-turn search, keep its top 3 root options, and search only those two turns deep with the fallback rule. Use it for the product player, the ladder's long time control, depth benches and distillation labels. Once it is cheap, start fishtest-style SPRT [0, 0.005] tests on search settings with the net held fixed (sample_k, the fallback threshold, the cap, top-k).

**Why:** Depth is the only lever with z > 4 on held-out content. Its cost (about 145x one-turn, about 12 thread-h per 1,300 elite and boss fights) is what keeps it out of benches, the ladder, labelling and self-play. The exact best option sits in one-turn's top 3 in 39 of 40 net errors. Leaves already go to a native net in one batch, so tree size is the only cost to cut. A stream of small fixed-net tests is the Stockfish-style way to make progress without seed noise, but it is only worth running at two turns, which is why depth must get cheaper first.

**CPU:** Seconds for the puzzle check. A small engine or Python change. About 2-3 thread-h to confirm on held-out Lagavulin and Slime Boss fights.

**First check:** On the 443 puzzles, with analyst 2's scratchpad pattern (<scratchpad>\puz.py), apply two-turn search to the top-3 children only. Compare regret and node counts with full two-turn. Build it if regret stays within 0.002 and nodes drop at least 3x. Then measure node counts on 50 mid-fight elite states, since the endgame puzzles are small and may understate the saving.

**Serves:** Goal 2 directly. It also enables ranks 4 and 5.

### 3. Ids twin of the current recipe (test the goal-1 thesis)

**What:** Run lean-thr with mode ids, using the same round 0, seeds and data order as lean-thr s1/s101/s201. Read the paired difference on tight2 held-out, tight_bosses and gen_powers12.

**Why:** The whole goal-1 design rests on the effect-primitive encoding, and it has never been compared at current strength. If ids comes within about 0.02 on held-out, the generalisation that exists comes from afterstates and search, and goal-1 effort should move to the simulator side. If effects lead by more than 0.03, the encoding work in the engine series is justified. learn.py already supports it (cfg mode ids), so it is a config change.

**CPU:** About 20 min for a 5k single-seed probe, then about 3-4 thread-h for 3 seeds at 20k.

**First check:** One seed at 5k games, scored on tight2 held-out against lean-thr s1. A gap above about 0.05 already decides it. Otherwise run 3 paired seeds.

**Serves:** Goal 1.

### 4. Depth on novel content, with the full-size train-half job 0057b reshaped

**What:** Replace the 5.5 h train-half job 0057b with three smaller reads, two-turn fallback vs one-turn on the champion net. (a) Train elite and boss cells at every=2. (b) A stratified sample of about 100 hallway cells x 4 fights. (c) A novelty slice: the 53 cells holding 'turn start -> +Strength', the 39 held-out Demon Form boss cells, Guardian cells near Mode Shift, and a gen_powers12 subset. Ask whether depth gains more on novel content than on train content, and whether it removes the rate nets' Guardian hesitation.

**Why:** If depth's gain grows with novelty, then search and its distilled form are the content-agnostic goal-1 tool, and both goals share one investment. Hallways are 73% of tight2, and depth has never been measured there. The train half alone would confirm a result already at z about 4.

**CPU:** About 5-7 thread-h in all, 2-3x less once rank 2 lands.

**First check:** The novelty slice first (about 400 fights, about 1 h on 4 threads). Compare net2 - net1 there with the +0.055 measured on held-out elites and bosses.

**Serves:** Goal 1 and goal 2.

### 5. Search-labelled data at scale (expert iteration), gated on the distillation read

**What:** Finish lean-distil s101/s201 and read them paired with lean-thr. If distillation gives at least +0.01 on elites and bosses, label 10x more positions (about 100k elite and boss decisions) from the champion's games with top-k two-turn net-leaf search. Retrain once. Measure the distilled net both at one turn and under two-turn search, to see whether the gain compounds. Repeat this as the meaning of a 'round': self-play with a search-improved target, which is the step one-turn rounds 2-10 lacked.

**Why:** Stockfish and GNU Backgammon train on positions labelled by a stronger search, at large scale. Here the teacher (net + two-turn) is measured +0.055 stronger than the student, and the data slope has not flattened (+0.01 per doubling). Interim s1 shows elites +0.016 to +0.020 and bosses -0.007 to -0.015, so 3 seeds must decide before scaling up.

**CPU:** About 7 thread-h per 100k labels at today's teacher speed, about 2-3 h with top-k. Plus one learn run per seed.

**First check:** Score the distil s1 net's one-turn regret on the 443 puzzles (seconds): does it move from 0.019 toward 0.006? Then read the 3-seed tight2 and boss lead.

**Serves:** Goal 2. Goal 1 if rank 4 shows that depth carries over to novel content.

### 6. Measured power effects and an oracle arm (content-agnostic goal-1 features, and a bench with headroom)

**What:** (a) For each power, have the engine fire its hooks over k canonical simulated turns on a cloned state, with and without the power. Record the deltas in outcome units and use them as the rate columns and as the generator's price, replacing the hand-written hook_rates table. (b) Train an oracle arm (lean-thr plus the 43 test-split powers) and score it on gen_powers12 to find the bench's ceiling. If the oracle gains under about 0.02, redesign the bench: several generated cards per deck, and a ladder of content at controlled distances from training.

**Why:** Rate features showed that an outcome-unit signal moves play on unseen mechanics (+0.10 to +0.20), but the table only covers fixed trigger and effect pairs, so a modder's power gets nothing. Simulating the effect is the afterstate principle stretched over time and works for any atom the engine implements. Without an oracle, 'no transfer' cannot be told apart from 'nothing to gain'.

**CPU:** (a) A Python first check under 1 minute, then an engine change and 3 lean runs (about 3-4 thread-h). (b) 3 oracle runs, about 3-6 thread-h.

**First check:** In Python with sts.Combat, apply each of the 43 test powers from data/bench/gen_powers_pack.json and step a few EndTurns with a fixed deck. Correlate the crude delta with each card's measured swap cost (9-net mean, sd 0.062 across cards). Build it if the correlation is above about 0.5.

**Serves:** Goal 1.

### 7. Throughput fixes that cost no CPU

**What:** Cache the heuristic's tight2 results on disk, keyed by (TIGHT_SET, rules_version, search, every), at learn.py:1141 and in the read scripts. Evaluate experiments at every=2. Split the feature cache from the label hash. Hold a token so only one job is in torch training at a time. Store cached features as float16 or memory-mapped arrays. Add a fast test tier with per-test timing, and move test_sweep and the full-size smoke runs to a slow tier. Wake the manager on job completion.

**Why:** The heuristic replays are identical every run (10% of learn time). Evaluation noise is about 5% of the variance, so half the fights barely matters. Paging slowed epochs 7-10x. The feature cache re-encodes round 0 in round 1 (3m16s, then 7m08s for the same data). Together these give about 1.3-1.5x on every run, and less waiting during builds.

**CPU:** About 0. One 3-minute heuristic pass to seed the cache.

**First check:** Subsample every other spec in existing round.json tight_results. Confirm the rates-vs-thr and data40k-vs-20k differences and their se change by less than 10%.

**Serves:** Both (more decisions per CPU-hour).

### 8. Seed-paired recipe protocol and a check on training variance

**What:** Every recipe arm shares its control's round 0, data order, init seed and exact draw. Each spec states its MDE before it is queued. Run 3 paired seeds, and extend to at most 8 only while the interim z stays between -0.5 and 2.5. Test whether averaging the last epochs' weights (EMA or SWA) and a frozen-dataset protocol cut the seed sd.

**Why:** The cost of a decision falls with the square of sd(diff)/effect. Pairing gave corr 0.81-0.99 where data was shared. Halving the training variance would cut the seeds needed 4x, which beats any engine speedup.

**CPU:** About 2-3 thread-h for the EMA check. The protocol itself only reorders runs already planned.

**First check:** Retrain lean-thr's round-2 net 4 times on its saved datasets with EMA and 4 times without (training only, tight2 every=2). Adopt EMA if the across-seed sd falls by 30% or more.

**Serves:** Both.

### 9. HP-aware ladder pool, then a full-Act gauntlet as goal 2's headline number

**What:** Add a ladder pool of the same deck x encounter cells at 40-100% of max HP, scored by paired HP lost (a death counts as all remaining HP plus a penalty), next to win/loss. Then build about 200-1,000 fixed Act-1 sequences with HP carried between fights, scored by paired Act-clear rate and HP at the boss. Fit a Bradley-Terry rating over anchors: random, heuristic 1- and 2-turn, champion 1- and 2-turn.

**Why:** Tight cells start at a median of 5-6 HP, with 16-20% at 1 HP. Old data shows nets winning as often as the heuristic while losing 3-8 more HP per won fight. The current yardstick could point the wrong way for whole runs, and it will saturate as the champion improves.

**CPU:** About 1-2 thread-h for the first HP check. About 0.5-1 thread-h per one-turn agent per 1,000 Acts.

**First check:** Replay ladder test 0003's net pairing on about 2,000 pairs from the run-HP pool. If HP lost puts the nets in a different order from win rate, the tight yardstick has been misleading for runs.

**Serves:** Goal 2.

### 10. Random numbers that stay matched after choices diverge (deferred)

**What:** Seed draws, shuffles and monster rolls from (fight seed, turn, reshuffle or event counter) instead of one shared stream, so two-turn product tests need fewer fights.

**Why:** Real, but narrow. Analyst 2 is right that one differing decision changes the outcome in 18% of fights. Analysts 5 and 6 show this noise is about 5% of a recipe comparison's variance, and one-turn product tests already take minutes. It pays only for two-turn ladder tests, and it changes the rules fingerprint.

**CPU:** An engine change, a golden re-pin and about 1 thread-h of tests.

**First check:** Only once two-turn ladder tests are routine: list every RNG consumer in engine/src (state.rs takes a single Rng) and estimate the discordance it would remove.

**Serves:** Goal 2 (cheaper measurement).

## Stop doing (synthesis)

- Stop spending CPU on label, loss, exact-label, curriculum, frontier, rung-4 and solve-step variants, and on self-play rounds past round 1, unless the targets come from a stronger search. The existing Stop list should name 'rounds > 1 at one-turn search' explicitly.
- Stop queuing recipe arms without a computed MDE. Use sd 0.010 (train) and 0.013 (held-out), or the measured sd of the paired difference, not 0.006-0.0075. An arm whose expected effect is below its MDE does not run, or runs only as a seed-paired, frozen-data comparison.
- Stop treating the Amendment 5 fight-only gate, or any single-seed read, as a verdict on a recipe. Keep it, or better an SPRT, only for the question 'is this net better than the champion'.
- Stop using the one-turn tight2 lead over the heuristic as the headline of strength. Report net plus search on the ladder, split elite and boss from hallway, and keep held-out as the goal-1 number.
- Stop putting generated content into the training recipe, and stop planning a hand-written feature for each mechanic as the goal-1 route (manager.md Next E). It contradicts content agnosticism, and gen128 cost about 0.04 on elites.
- Stop the Guardian-cost fix hunt beyond reading the 5-seed result. Instead, test whether two-turn search removes the hesitation before Mode Shift. If it does, the rate cost is a horizon problem, not a feature bug.
- Stop re-auditing the 10-24 teacher sizing as its own job. Job 0044b (net two-turn vs net one-turn with fallback and shared samples) already answers it. Mark the 10-24 result as superseded in the docs, and require an artifact check before any large negative reading kills a direction.
- Stop using regret@decisions and the rankings in bench-baseline.md / exact-puzzles.md, which were measured against the 50k-capped reference, to locate errors.
- Stop running test_sweep (sweep.py, unused since the job queue arrived, about 35 min) and the full-size smoke runs in the default test pass.
- Stop deep FIFO padding with re-planning every 2 h. Order the queue by value of information and wake the manager when a job finishes (jobs.py wait).

## Next 48 hours (synthesis's plan; the manager's re-rank is in docs/manager.md)

Hours 0-2, CPU-light, alongside the running 0057a6c/d. None of this needs more than seconds of CPU.
(1) Compute MDEs for every queued job (0057a7 onward) at sd 0.010 / 0.013, and correct the sd in manager.md "Machine time".
(2) Run the top-3 pruning check on the 443 puzzles (rank 2, seconds).
(3) Run the measured-effects correlation check on the 43 test powers (rank 6, under 1 minute).
(4) Run the every=2 subsample check on existing round.json files, and fit Bradley-Terry ratings to the existing paired files.
(5) Build the heuristic tight2 disk cache and seed it with one 3-minute pass.
(6) Reorder the queue by renaming job files.

The new queue order:
(a) One ladder job (4 threads, about 1 h) covering data40k x3, lean-thr x5, lean-rates x5 (--no-promote), cover21 and distil s1.
(b) 0057a7 distil s101.
(c) 0057a7a/b boss_lead reads (cheap). Read the 5-seed Guardian result and then stop the hunt.
(d) The ids-twin probe at 5k, seed 1 (about 20 min).
(e) 0057a8 distil s201.
(f) The ids twin at 20k, s101/s201, paired, unless (d) already showed a gap above 0.05.
(g) Oracle arm, 3 seeds, on gen_powers12.
(h) The reshaped depth job in place of 0057b. Novelty slice first (about 1 h at 4 threads), then about 100 hallway cells x 4 fights, then train elite and boss cells at every=2.
(i) data80k cut to 2 seeds (s1, s101). Pairing corr is 0.87-0.99, so 2 seeds decide it.
(j) lean-look 0058-0060, read with Lagavulin and Nob pre-registered as the target slices.
(k) score-r0.

Hours 2-24. While the queue runs:
- If the puzzle check passes, build top-k root pruning as a small spec with a program-run check: regret within 0.002 of full two-turn, at least 3x fewer nodes on puzzles and on 50 mid-fight states.
- Build the fast test tier with per-test timing, the feature/label cache split and the torch-phase token.
- Write up this review's decisions in docs/decisions.md: the champion is net plus search; MDE-gated recipes; generated content stays out; goal 1 goes through simulator-side signals.
- Read each job when it finishes, by waking on completion, not on the 2-hour clock.

Hours 24-48.
- Read the distil 3-seed result and the distil s1 puzzle regret. If elites gain at least +0.01, write the scale-up spec: about 100k top-k two-turn labels from the champion's games, with the distilled net measured at one turn and under two turns.
- Read the ids twin and the oracle arm, and decide the goal-1 route.
- If the measured-effects correlation was above 0.5, spec the engine change and queue 3 lean runs paired with lean-thr.
- Read the depth novelty and hallway results. If net2 - net1 is at least +0.03 on train elite and boss cells, promote the two-turn player as the champion definition and run the first two-turn ladder confirmation on elite and boss cells.
- Start the HP-lost ladder pool check on about 2,000 pairs.

Owner decision, since it is expensive to reverse: re-scope the rules-engine series. The recommendation is to widen registry-lite to generated attacks, skills and monster patterns next, retrain after each spec instead of keeping old nets bit-identical, and defer the specs aimed at fidelity alone. Leave a short note for the owner. Do not start building it.

## Open questions

- Does depth's gain grow on novel content (Demon Form, gen powers, Guardian near Mode Shift) compared with train content? If yes, search and distillation are the goal-1 route and both goals share one investment. If no, goal 1 needs simulator-side features such as measured power effects.
- How much of today's held-out lead survives in an ids-mode twin of the same recipe? That decides whether the engine series' encoding work serves goal 1 at all.
- Does the generated-power bench have headroom? An oracle arm trained on the test powers either gains at least 0.02 there or does not.
- Does distillation compound with search? Is the distilled net under two-turn search stronger than the champion under two-turn search, or does distillation only buy one-turn speed?
- How much tree size does top-3 root pruning save on mid-fight elite and boss states, which are larger than the endgame puzzles?
- Is the remaining roughly 41% of held-out elite and boss fights that the two-turn net loses mostly luck, or mid-fight mistakes (setup timing, Lagavulin's sleep window)? Only a stronger mid-fight reference labelling can tell.
- Does the tight-fight lead track HP efficiency at run-realistic HP, or do the nets win as often as the heuristic while losing more HP?
- Which part of the training-seed variance (init, data order, round-0 data) is largest? That decides what arms must share, and whether EMA or more data shrinks it.
- For goal 2 at run level, how much of the win rate comes from combat versus card rewards and pathing? The project has no measurement out of combat, and outside bots such as bottled_ai get most of their win rate there.

## Skeptics' verdicts on the key claims

### Search depth, with the node-cap bias fixed, is the largest and most reliable lever on general play. Its gain adds to the net's, and its remaining errors are concentrated among one-turn's top 2-3 options.

*Evidence given:* depth-pilot-2026-10-30.md: two-turn fallback beats one-turn by +0.061 (se 0.014) with heuristic leaves and +0.055 (se 0.013) with net leaves, on 1,336 held-out elite and boss fights. Net two-turn scores 0.591, heuristic one-turn 0.498. Analyst 2's rerun of the 443 horizon >= 1 exact puzzles (data/bench/puzzles.json) gave mean regret 0.0293 for heuristic one-turn, 0.0191 for net one-turn and 0.0061 for net two-turn. The exact best option was in one-turn's top 3 in 39 of 40 net errors and 40 of 42 heuristic errors. Search scores all leaves in one batched call to a native Rust net (engine/src/search.rs header; NetEval in py/src/lib.rs:737), so depth's cost is tree size, not Python overhead.

- **overstated, refuted.** The win-rate numbers check out against the primary files. The three conclusions drawn from them do not.
  
  CONFIRMED (results/depth/*.json, summary.all.won):
  - paired-held_out-cap400k-fallback-m0.json: 0.4978 -> 0.5584, diff +0.0606, se 0.0140, n 1336.
  - paired-net-held_out-cap400k-fallback.json: 0.5352 -> 0.5906, diff +0.0554, se 0.0135.
  - engine/src/search.rs header: every leaf is scored in one evaluator call.
  - py/src/lib.rs around line 737: NetEval runs natively in chunks of 4096 and never takes Python's lock. So the cost is tree size: two-turn takes ~145x one-turn's time (7133 s vs 49 s, depth-pilot doc).
  
  "MOST RELIABLE": not supported.
  - The same depth comparison changed sign four times as the method changed: pilot +0.150, cap 50k -0.048, cap 400k +0.016, fallback +0.061. Those files are paired-held_out.json, paired-held_out-cap400k.json and the fallback file.
  - The fallback player was picked after seeing the cap-400k run, then scored on the same 1,336 held-out fights. Fallback is a principled fix, so this is a mild forking-paths problem, but it is one.
  - Net two-turn with fallback is measured on the held-out half only. The train half (job 0057b) is unread per docs/manager.md, and heuristic fallback on train is "unmeasured" per the depth doc.
  - Coverage is narrow: 4 Ironclad encounters (Nob, Lagavulin, Sentries, Slime Boss) from tight2, elites and bosses only. There are no hallway fights and no generated content. "General play", the owner's goal 1, has not been tested at depth.
  - Per encounter the effect is uneven. Heuristic leaves: Lagavulin -0.033. Net leaves: Nob +0.003 and Sentries +0.012, both within noise.
  
  "LARGEST": not supported.
  - The net beats the heuristic at one turn by +0.083 on train (0.586 vs 0.503; paired-net-train.json and paired-train.json), which is bigger than any depth gain.
  - docs/research/learned-play-results.md lists levers of the same size: effects features +0.060 on tier B zero-shot, and warm start +0.054. Those come from different benches, so no single ranking holds.
  
  "ADDS TO THE NET'S": holds only as an average over large interactions that cancel out.
  - How I computed it: I paired the heuristic-fallback and net-fallback files fight by fight (all 1,336 matched on cell and seed). For each fight, interaction = (net two-turn win - net one-turn win) - (heur two-turn win - heur one-turn win).
  - Mean over all fights: -0.005 (se 0.019), so it looks additive.
  - Per encounter it is not:
  
  | encounter | interaction (se) |
  |---|---|
  | Gremlin Nob | -0.101 (0.025) |
  | Lagavulin | +0.161 (0.045) |
  | Slime Boss | -0.085 (0.041) |
  | Sentries | +0.003 (0.033) |
  
  - So on Nob, depth and the net buy the same thing (they substitute). On Lagavulin they complement each other. "Adds" is a coincidence of this 4-encounter mix, not a property you can carry to other content.
  
  PUZZLE SUB-CLAIMS: unverifiable.
  - No repo file holds "Analyst 2's rerun": n 443, regret 0.0293 / 0.0191 / 0.0061, top-3 in 39 of 40 and 40 of 42.
  - docs/research/exact-puzzles.md reports 448 puzzles at horizon >= 1, with heuristic regret 0.031 [0.017, 0.048]. Its net-minus-heuristic intervals all include 0.
  - docs/research/big-picture-2026-10-31.md says the earlier two-turn puzzle figures came from a scratchpad deep.py that stops after 85 s, so likely not all 448 puzzles. It also found that big errors carry 96-98% of puzzle regret (22 of 40 net errors are >= 0.05).
  - The same doc says the puzzles are endgame tails (horizon 2+ is only 6-8% of the set). Even if the top-3 figure is right, it speaks to endgames, not general play.
  
  Pattern: one well-measured, real effect, on a narrow slice (4 Ironclad elite and boss encounters, one half), has been promoted to a general ranking of levers.

- **overstated.** What I checked, and what the data shows:
  1) I recomputed the win-rate numbers from the raw per-fight files results/depth/paired-held_out-cap400k-fallback-m0.json and results/depth/paired-net-held_out-cap400k-fallback.json. Both files hold the same 1,336 fights, matched on cell and seed. Mean win rates: heuristic one-turn 0.4978, heuristic two-turn 0.5584, net one-turn 0.5352, net two-turn 0.5906. Paired differences:
  - heuristic two-turn minus one-turn: +0.0606 (se 0.0140)
  - net two-turn minus one-turn: +0.0554 (se 0.0135)
  - net one-turn minus heuristic one-turn: +0.0374 (se 0.0140)
  - net two-turn minus heuristic one-turn: +0.0928
  The fights come from 167 cells. Clustering the se by cell raises it only a little: 0.0148 for the net gain and 0.0164 for the heuristic gain. So the headline numbers are correct and well beyond noise.
  2) "Adds to the net's gain": I computed the interaction per fight as (net two-turn minus net one-turn) minus (heuristic two-turn minus heuristic one-turn). It is -0.005 (se 0.019). That fits additivity, but the 95% interval is about ±0.037, so it can't rule out depth giving half as much on top of a net. Per encounter the gains clearly don't add (table in docs/research/depth-pilot-2026-10-30.md). On Gremlin Nob depth gives the heuristic +0.104 but the net +0.003. On Lagavulin it gives the heuristic -0.033 but the net +0.128. Additive holds for the total only.
  3) "Most reliable" and "general play": the evidence comes from one benchmark slice. It is held-out tight2 elite and boss cells only: no hallway fights, no generated cards, powers or enemies (the owner's goal 1). The tests used one net, r2 s1, and one half. The train half under the fallback player has not been measured; 0057b is still queued (docs/manager.md Next). The fallback rule and the 400k node cap were picked after looking at results on these same 1,336 fights. That is a mild selection effect: fallback minus plain is +0.044 (se 0.011), so it is real, but the reported +0.061 is the best of the variants tried. The sign of depth's effect has flipped three times as the search was fixed (-0.048, then +0.016, then +0.061), and the gain varies a lot by encounter (net leaves: +0.003 to +0.128). "Largest lever" holds against the levers measured here (net over heuristic +0.037; data doubling +0.009 to +0.013 per docs/manager.md Log 14:02). The cost is 145x one-turn's time (7,133 s vs 49 s), so it is a lever for picking test-time moves or making training labels, not a free one.
  4) Puzzle regret figures (0.0293 / 0.0191 / 0.0061) and "39 of 40, 40 of 42 errors in one-turn's top 3": unverifiable. No file in the repo holds Analyst 2's rerun, and I could not rerun two-turn search under the no-heavy-work rule. The repo's own docs/research/exact-puzzles.md gives 448 horizon >= 1 puzzles, not 443, and heuristic regret 0.031, which roughly matches. That doc also says the set measures endgames (horizon 2 or more is only 6-8% of it). On horizon-1 puzzles two-turn search reaches the end of the fight, so its near-zero regret is close to guaranteed by how the set was built. It doesn't measure depth on general play. "Top 3" also means little until the usual number of options per puzzle is known.
  5) Mechanism: the engine/src/search.rs header does say every leaf is scored in one evaluator call. NetEval in py/src/lib.rs (around line 737) is native Rust and splits the leaves into chunks of 4,096. So the claim about cost (tree size, not Python overhead) holds.

### Changing the targets on the same data does not move play. Proxy metrics such as MSE, regret and err2 do not predict play.

*Evidence given:* 0 of 7 label, loss, curriculum and solve-step variants reached |z| >= 2 on held-out (learned-play-results.md: caps +0.009 / -0.011, frontier 2 -0.015, rung 4 +0.002 even though err2 fell from 0.078 to 0.052, lean -0.004). Self-play rounds 2-10 are flat (r10 - r1 +0.001 +- 0.016). Warm and fresh starts had equal MSE (0.057) but warm won by +0.054.

- **overstated.** All numbers checked against docs/research/learned-play-results.md.
  
  The quoted numbers mostly match the source:
  - Caps +0.009 / -0.011 are the held-out tight-fight differences of the cap 150k and cap 400k nets against night s1 r10, on the old 10-seed set (lines 363-370). Both intervals cross 0.
  - Rung 4 averages +0.002 held-out [-0.002, +0.006] (lines 589-590). err² falls from 0.078 to 0.052, but only at seed 1 (line 585).
  - Lean -0.004 is lean's held-out +0.002 minus the seed check's +0.006 (lines 806, 813-819).
  - Warm and fresh reach equal 10k-game MSE (0.057) and warm wins +0.054 (0.038-0.070) (lines 681-683, 693-695).
  - r10 - r1 is +0.001 +- 0.016 (line 99).
  - Frontier 2 "-0.015" is not printed anywhere. It is an unpaired difference I derived from the 100-seed table: frontier 2 held-out -0.024 minus night s1 r10's -0.009 (lines 409, 413). On tight2 the gap is -0.002 (+0.008 vs +0.010, lines 465 and 468).
  
  Where the data contradicts the claim or the claim goes past it:
  
  (1) "0 of 7 reached |z|>=2" depends on which version of each test you count.
  - The first rung-4 check is a pure label change on the same data. It gave B - A held-out +0.016 [+0.010, +0.021], a clear pass (lines 538-540). It was later put down to a weak baseline: arm A stopped training early on the bounds-walked database. So better targets did move play there, when the baseline net was under-trained.
  - Rung-4 seed 201 alone gave held-out +0.006 [+0.001, +0.011] (line 587).
  - The exact-only nets (exact values as the only targets) moved play a lot, downward: -0.17 / -0.11 against the heuristic (lines 233-236, 338-340). Their training rows were also a different subset, so it isn't pure.
  - So targets can move play. What the data shows is that no target variant improved held-out play beyond training noise once seeds were averaged.
  
  (2) The tests had too little power to see the effect size of the lever the claim implicitly favours.
  - One data doubling gives about +0.009-0.011 held-out (lines 1178-1183).
  - The tests above had intervals of about +-0.03 on the 10-seed v1 set (line 196) and an MDE of about 0.016 for lean (line 816).
  - Training-seed sd is 0.006-0.0075 (lines 597-598), about 2x with fresh round 0s (lines 866-869).
  - A data doubling run through the same single-retrain designs would also have "failed |z|>=2". So the null results bound target effects at roughly 0.01-0.02. They don't show targets are inert compared with data.
  
  (3) The self-play evidence doesn't fit the claim's category. Self-play rounds produce new data; they are not new targets on the same data.
  - The r10 - r1 figure covers rounds 1-10 of the 10-26 sweep, not rounds 2-10. Inside that sweep, r5 - r1 was +0.032 +- 0.015, which the doc treats as a post-hoc peak.
  - Round 0 to round 1 does move play: +0.018 held-out, about 2.5 se (lines 888-891).
  - The seed check supports "past round 2 adds nothing" (lines 633-635).
  
  (4) "Proxies do not predict play" holds for small differences between similar nets, not in general.
  - In warm-start, MSE ranks the arms the same way as play at 0 and 500 games: MSE 0.070 / 0.072 / 0.078 against win 0.499 / 0.481 / 0.469 (lines 672-677). Fresh at size 0 has MSE 1.154 and win 0.122.
  - Cases supporting the claim: rung 4 lowers val MSE and err² at every seed while play stays flat (lines 592-595). The 400k cap has the best position regret yet the worst held-out play among the checks (lines 359-360, 467). Exact-only B with bounds has the best h2 regret but plays at -0.12 (lines 312, 338-340).
  
  My interpretation: the pattern is real. Within the regime the project has explored, sharper targets for the same states have not bought measurable held-out play. But the claim states it as a general law, while the evidence supports a bounded one: effects of at most about 0.01-0.02, on nets already trained to convergence. The supporting list is chosen selectively. It leaves out the one significant label pass (the first rung-4 check) and a large negative move (exact-only).

- **overstated.** All primary source is docs/research/learned-play-results.md unless noted.
  
  Numbers that trace:
  - Caps: +0.009 / -0.011 held-out is the 10-seed tight-fight v1 paired diff against s1 r10 (cap 150k +0.009 [-0.018,+0.036], cap 400k -0.011 [-0.041,+0.019]; lines 363-370).
  - Frontier 2 -0.015 is not printed anywhere. It is derivable from the 100-seed table (held-out -0.024 against s1 r10's -0.009; lines 409-413) as the difference of two leads, not as a paired interval.
  - Rung 4: err2 0.078 -> 0.052 and held-out B-A +0.005 [-0.0004,+0.011] at seed 1 (lines 564-567). Averaged over 3 training seeds, held-out B-A is +0.002 [-0.002,+0.006] (line 590). The +0.002 is right.
  - Lean -0.004 is lean minus the seed check on held-out (+0.002 vs +0.006, sd 0.011 / 0.004; line 806).
  - Self-play r10-r1 +0.001 +- 0.016 is at lines 97-99.
  - Warm vs fresh: tier-A MSE 0.057 for both and win +0.054 at lines 681-694.
  - The tally "0 of 7" appears nowhere in the docs. I found 6 arms (cap150k, cap400k, frontier 2, rung 4, lean, lean-lowhp), so the count of 7 is unverifiable.
  
  Problems with how the numbers are compared:
  1. "Does not move play" is a null result read as a zero. The single-retrain comparisons (caps, frontier 2) have intervals of about +-0.03 and cover fight noise only. Training-seed sd alone is 0.006-0.0075 (line 597), and per-cell intervals at 100 seeds are +-0.02-0.03 (lines 418-423). These tests could only have seen effects of roughly 0.015-0.03. The seed-averaged tests are tighter (rung 4 +-0.004; lean MDE about 0.016, line 815) and rule out large effects only. What the data supports is that no variant moved held-out play by more than about 0.01-0.02.
  2. Some variants did move play, in the wrong direction. More exact labels pushed held-out down while pushing train up: 400k at 100 seeds was +0.017 / -0.031 against s1 r10's +0.009 / -0.009 (lines 409-416). On tight2 it read -0.003 against r10's +0.010 (lines 465-467). The doc itself says "more exact labels push both further". That is a targets-to-play effect (more overfitting to the train cards), not no effect, though it comes from single retrains.
  3. The first rung-4 check did pass (+0.016 [+0.010,+0.021], line 538). It was then explained as a database confound (lines 570-573). It is worth naming as a counter-case that the confound accounts for.
  4. Self-play rounds are not "the same data with new targets": each round generates new games. The same sweep also shows r5-r1 +0.032 +- 0.015 (z about 2), which the doc discounts because r5 was picked after looking. The intervals hold bench noise only (lines 101-104). The firmer evidence that rounds are flat comes from tight2 and the seed check: held-out r2 +0.006, r4 +0.003, r7 -0.004, r10 -0.003, train peaking at r2 (lines 613-635). So "flat or slightly declining after r2" holds.
  5. Warm vs fresh is not like-for-like and is weaker than stated. Fresh nets had no Ironclad replay and no pretraining, so the two arms trained on different data. A different MSE does separate them: Ironclad MSE 0.057 vs 0.128 (line 683). Silent tier-B MSE differs too: -0.0033 [-0.0048,-0.0019] in results/warm-start/curve.json comparisons.
  6. The +0.054 [0.038,0.070] interval is fight noise only. Per-seed tier-A wins in curve.json are warm 0.561 / 0.526 / 0.535 and fresh 0.462 / 0.513 / 0.487. I computed this with a short Python read of the cells. The seed-paired diffs are +0.099 / +0.013 / +0.049, so mean 0.054, sd about 0.043, t about 2.2 on 2 degrees of freedom. That is consistent in direction across all three seeds, but not significant over seeds. The doc itself warns that Silent seed sd is about 0.03 (line 701).
  7. Proxies not predicting play is well supported within one setup. Rung 4 lowered val MSE and err2 at all 3 seeds with no change in play (lines 583-592). 400k had the best val MSE (0.1555) but the worst held-out play. Across the rung-4 seeds, A's val MSE ranking does not match its lead ranking. But "do not predict" is stronger than the evidence: the proxies were measured on the net's own-play or validation distribution, not on held-out cards, and the warm/fresh case has a proxy (Ironclad MSE) that does line up with play.
  
  Interpretation (mine): the underlying pattern the data supports is that held-out play is limited by generalisation to unseen cards. Every arm leads on train cards and is level on held-out cards (lines 627-632). Label precision on the training distribution is not the bottleneck. So the direction "polish the targets" looks spent, but the claim should be stated as "no detectable effect, at the 0.01-0.02 scale".

### Recipe comparisons are dominated by training-seed variance. At today's seed sd, 3 seeds cannot detect the 0.01 effects most arms were sized for, and the fight-only gate is not a recipe verdict.

*Evidence given:* Analyst 6, from 66 runs/*/round.json files: pooled seed sd is 0.0100 train and 0.0127 held-out. Fight noise per net is about 0.0024, about 5% of the variance. Analyst 5 independently found sd(diff) 0.010-0.023 and lean-thr's sd 0.011-0.012. The 0.006-0.0075 in docs/manager.md comes from one group that shared its exact draw. MDE = 2.8 x sd x sqrt(2/n), which gives about 0.023-0.029 at n = 3. Pairing seeds helps a lot when the arms share data: corr 0.81-0.99 for data20k/40k and rates/thr, but near 0 or negative for the gen arms. The gate's false-pass rate is P(Z > 0.83), about 0.20.

- **overstated.** How I checked: I parsed every runs/2026-10-3*/round.json that has a gate. I grouped runs by arm and round, read gate.halves.<half>.net[0], and pooled the variance within each group of 3 or more seeds (scratchpad skeptic1_sd.py). I compared the tight_results bitstrings across seeds (skeptic1_bits.py), and read the MDE lines in the specs.
  
  What holds:
  (1) The pooled seed sd is 0.0100 on train and 0.0127 on held-out (47 degrees of freedom), so I reproduce the stated numbers exactly.
  (2) Fight noise is small next to seed noise. On the fixed tight2 set, two lean-thr r2 nets disagree on about 7-10% of fights. That gives an se of the difference of 0.0024-0.0029, so about 0.002 per net, or about 2-5% of the variance. The gate's own per-net interval looks wider (se about 0.0055-0.007), but it treats the fight set as random, so it is not the noise in a comparison between nets.
  (3) The 0.006-0.0075 really comes from one shared-draw source: the rung-4 seed check (docs/decisions.md line 517, Amendment 1). docs/manager.md:65 still quotes it. docs/manager.md:253 and :502 already say the sd is about 2x larger with fresh round 0s.
  (4) The gate (scripts/learn.py:1048-1058) builds a z-interval over cells for one net and passes when both halves are above 0. Seed variance never enters it. Pass results split inside arms: lean r1 1/3, lean-gen128 r1 1/3, lean-lowhp r1 1/3, lean-thr r1 2/5, lean-thr r2 1/5, data40k 1/3. So a single pass is not a verdict on the recipe.
  
  What is overstated:
  (a) The pooled 0.0127 mixes the two kinds of run. Fresh-round-0 groups (cover, data) pool to 0.0116 / 0.0177. Groups that share a round 0 (all lean* arms, the design every feature arm uses) pool to 0.0090 / 0.0091. For shared-round-0 arms the unpaired MDE at n=3 is about 2.8 x 0.009 x 0.816 = 0.021, not 0.023-0.029.
  (b) "Arms sized for 0.01" is not what the specs say. lean-loop.md:62 says MDE about 0.016. gen-training-arms.md:75-77 says about 0.02. data-scaling.md:45-50 says 0.027-0.031. distill-two-turn.md:27 says 0.03. Per-fight-type MDEs are 0.04-0.06. The specs underestimated sd (0.007), but they did not target 0.01.
  (c) "3 seeds cannot detect 0.01" ignores pairing, and the data argue against it. Some paired sd(diff) values: data40k-data20k held-out 0.0055 (n=3, so paired MDE about 0.009), lean-rates minus lean-thr r1 held-out 0.0038 (n=5), lean-gen128 minus lean-thr r1 held-out 0.0062. So arms that share data can detect about 0.01 with 3-5 paired seeds.
  (d) The correlations quoted (0.81-0.99, and near 0 or negative for gen) come from 3-5 points each. lean-gen16 vs lean-thr r2 train gives corr -1.00 at n=3, and gen128 vs thr is 0.99 at r1 but -0.19 at r2. These are not stable estimates.
  (e) The false-pass rate of 0.20 is per half. Because `met` needs both halves, the real rate is lower unless the halves are fully correlated.
  
  My interpretation: the core pattern is right. Seed variance, not fight noise, limits every comparison, and a gate built only on fights can't judge a recipe. But the real fix is paired designs with shared round 0 and shared data, plus a correct sd for each design, not simply more seeds.

- **holds.** I recomputed the figures from the primary files with a single-threaded script (<scratchpad>\sd.py). It reads tight_win[train/held_out][0] from runs/*/round.json where tight_set == "tight2", which gives 67 files, all dated 2026-10-30 or 10-31. It groups them by arm and round, then pools the within-group variance.
  
  What the data shows:
  (1) The pooled seed sd is 0.00996 for train and 0.01267 for held-out, on 47 df. That matches 0.0100 / 0.0127.
  (2) docs/manager.md line 65 says "sd ~0.006-0.0075". Line 253 of the same file already says those figures came from runs that shared one round-0 net, and that the sd is about twice as large with fresh round 0s. So calling the 0.006 figure stale is correct.
  (3) The MDE arithmetic is right. 2.8 x 0.0100 x sqrt(2/3) = 0.023 and 2.8 x 0.0127 x sqrt(2/3) = 0.029. With a t-distribution at df = 4, the multiplier is about 3.7 instead of 2.8, so the true MDE is larger still.
  (4) The paired results by seed, as sd(diff) and corr:
  - data40k vs data20k r1 (n = 3): sd(diff) 0.0068 / 0.0055, corr 0.87 / 0.99.
  - lean-rates vs lean-thr: r1 (n = 5) sd(diff) 0.0062 / 0.0038, corr 0.24 / 0.84; r2 (n = 4) 0.0102 / 0.0097, corr 0.81 / 0.91.
  - gen128 and gen16 vs lean-thr: sd(diff) 0.006-0.024, corr -1.00 to 0.99, varying by round.
  - data20k vs data5k: corr 0.47-0.52.
  (5) The gate (scripts/learn.py gate() at line 1044) passes a half when the lower bound of the per-cell 95% interval on the net's lead over the heuristic is above 0. It requires both halves. Across the 67 tight2 files, the mean lead se is 0.0042 (train) and 0.0046 (held-out); the mean se of the net's own win rate is about 0.0057. If a recipe's true mean equals the heuristic, z = 1.96 x 0.0047 / sqrt(0.0100^2 + 0.0047^2) = 0.83 and P = 0.20. That reproduces the claim. The gate measures fight-level noise only and ignores seed variance, so the core claim holds: one passing net is not a verdict on its recipe. docs/research/learned-play-results.md lines 603-630 support this: none of the 10-28 night's gate passes held up when re-run with more seeds.
  (6) The fight-noise share: tight2 uses a fixed set of fights, and play is deterministic (the heuristic results are byte-identical across runs). That makes a per-net fight noise of about 0.0024-0.0035 plausible, which is roughly 4-8% of the held-out variance. I could not find the exact source of 0.0024.
  
  Where the stated evidence is overstated:
  (a) The pooled sd counts round 1 and round 2 of the same seed as separate draws, so the 47 df overstate the information; it is closer to about 25 independent df. It also mixes heterogeneous groups. Group sds range from 0.002 (data40k, train) to 0.033 (cover10, held-out), and lean-rates sits at only 0.003-0.007.
  (b) The "corr 0.81-0.99 for rates/thr" figure is cherry-picked: rates/thr train r1 is 0.24. Every correlation here rests on 3-5 points, so a single value like -1.00 or 0.99 means almost nothing.
  (c) "3 seeds cannot detect 0.01" is true only when seeds are not paired. With paired seeds and shared data, sd(diff) is 0.0055-0.0068 (data40k/20k), which gives a paired MDE at n = 3 of 2.8 x sd / sqrt(3), about 0.009-0.011. That is borderline, not impossible.
  (d) The false-pass rate of 0.20 is per half and assumes a true lead of exactly 0. The train and held-out seed residuals correlate at 0.85 (n = 65), so the rate for both halves together is a bit under 0.20, perhaps 0.15. With sd = 0.0127 and se = 0.005, a single half is about 0.24.
  
  My interpretation: the direction of the claim is right, and the project's own manager.md line 502 already uses the same MDE formula with the doubled sd.

### Comparing fixed nets (the product) is cheap and well powered, but almost unused. Picking the best of the existing seeds is worth about as much as one data doubling.

*Evidence given:* results/ladder/log.jsonl: 3 tests, all on 10-30, each 69-180 s at 6 threads. The champion is still runs/2026-10-29-seed-check-r2-s1-1a789b2. Net-vs-net se per half is about 0.003. With seed sd about 0.01, the best of about 5 nets is worth about +0.01. More than 30 r1/r2 nets have finished since. In test 0003, hallway pairs differed in only 3.8% of cases, elite pairs in 17.1% and boss pairs in 14.4%.

- **overstated, refuted.** What holds:
  - The ladder is cheap and barely used. results/ladder/log.jsonl has exactly 3 tests, all run 2026-10-30 between 20:35 and 20:40, taking 69, 69 and 180 s.
  - results/ladder/champion.json still names runs/2026-10-29-seed-check-r2-s1-1a789b2 (since test 0001).
  - I counted runs/*/model.pt files with -r1- or -r2- in the path and a file time after 2026-10-30 20:40: 69 nets from 14 arms (cover, lean, data5k/20k/40k, gen, rates, thr, distil). That is well over 30.
  - The discordance rates are right. I recomputed them from pairs_played in results/ladder/tests/0003.json: hallway 3.8% (2979 pairs), elite 17.0% (claim 17.1), boss 14.4%.
  - The ladder test already appears as a recommendation in docs/research/big-picture-2026-10-31.md item 7 and docs/manager.md Next F. So this is a known idea that hasn't been run, not a new finding.
  
  What is wrong or overstated:
  1. The se is about twice what the claim says. I took the sd of cand-champ over the counted pairs, divided by sqrt(n), and ignored clustering. In 0003 (4090 pairs, the largest test) that gives se 0.0059-0.0060 per half and 0.0042 overall. The file's own clustered intervals are wider (held_out lo/hi -0.0098/+0.0137, so se about 0.006). For 0002 the per-half se is 0.010-0.011. Getting se 0.003 per half would take about 16k pairs, the cap, which is roughly 12 minutes. Still cheap, but the claim's precision is off by 2x. Per fight type the test is not well powered: in 0003 the elite se is 0.014 and the boss se is 0.023.
  2. 'Best of ~5 is worth +0.01' measures the gain against the recipe's average seed, not against the champion. The expected best of 5 normals is 1.16 sd. The champion is already the best of 3 seed-check seeds: s101 trails it by 0.013 (0002), s201 by 0.0002 (0003). The expected best of 3 is 0.85 sd. So picking among more seeds of the same recipe adds only about (1.16-0.85)*sd, roughly 0.003 at sd 0.01. That is below what the SPRT can tell apart: it tests 0 against d1=0.01, and 0003 stopped at lead -0.0002. Any bigger gain from the 69 new nets would come from newer recipes (data40k, lean-thr) having better averages. That is a recipe gain, not seed picking. The seed sd figures (docs/decisions.md:517 gives 0.006-0.0075; big-picture-2026-10-31 :108 gives 0.012-0.014; fresh round 0 roughly doubles it, per manager.md:502) also include bench measurement noise. The true spread between seeds is smaller, which shrinks the gain from picking further.
  3. 'Worth one data doubling' compares two different kinds of gain. The data doubling (data40k over 20k: +0.013 train / +0.009 held-out, docs/manager.md:343,524) raises the recipe's average and stacks with seed picking, since you can pick the best of the data40k seeds too. Seed picking is a one-off gain that doesn't compound. The two don't trade off against each other.
  
  My interpretation: running a ladder test as the routine last step of every finished run is a sound, cheap habit. But the numbers here inflate both how precise the ladder is and how much it would gain. The real value is a cheap cross-recipe check of the product (are the newer recipes actually stronger than the 10-29 champion when played paired?), not a +0.01 from seed luck.

- **overstated.** These figures check out against the primary files. results/ladder/log.jsonl has only 3 tests (0001-0003), all run 2026-10-30 between 20:35 and 20:40. They took 69, 69 and 180 s and used 1150, 1305 and 4090 pairs (d1 0.01, cap 16000). The only ladder jobs are jobs/done/0020-0022-ladder.json. results/ladder/champion.json still names runs/2026-10-29-seed-check-r2-s1-1a789b2. 92 run folders under runs/2026-10-3* have a model.pt modified after 2026-10-30 20:40 (checked with stat), so "more than 30 nets since" holds, although some are r0 or probe nets. I recounted 0003's pairs_played by group: hallway pairs ended differently in 3.8% of cases (2979 pairs), elite in 17.0% (840) and boss in 14.4% (271). docs/manager.md Next F has listed "ladder-test the best ... nets" as pending, so "almost unused" holds.
  
  Three numbers fail.
  (1) The se per half is not about 0.003. 0003's held-out half has an interval of [-0.0098, +0.0137] at n=2035, which is se ~0.006. My recomputed paired se is 0.0059 per half and 0.0042 overall at 4090 pairs. For 0002 it is 0.0077 overall. An se of 0.003 per half would need about 8000 pairs per half, which is the cap region. At the SPRT's actual stopping sizes, the per-half se is about 2x the claim. The test is still powered for a +0.01 overall effect, because SPRT d1 = 0.01 with alpha = beta = 0.05 is its design. It is not powered to resolve differences per half or per fight type: boss n of 76-271 gives se 0.02-0.06.
  (2) The sd of 0.01 between training seeds was measured on a different yardstick. It comes from tight2 leads over the heuristic: 0.0066/0.0076 with a shared round 0, 0.014-0.017 with fresh round 0s (docs/research/learned-play-results.md, the rung-4 seed check and coverage pilot sections). The ladder uses a different pool of fights, weighted toward bosses: 0001's ladder lead is +0.037 against +0.027/+0.006 on tight. The only same-recipe differences measured on the ladder itself are -0.013 (se 0.0077) and -0.0002 (se 0.0042). After removing fight noise, that suggests a seed sd on the ladder of only about 0.005. That estimate rests on 2 points.
  (3) The champion is already a best-of-3 pick. r2 s1 beat both of its seed twins on the ladder (0002, 0003), and it was also the best seed on tight in the seed check. E[max of 5] = 1.16 sd, so the +0.0116 arithmetic is right against a random seed. But the gain from moving best-of-3 to best-of-5 is only (1.163 - 0.846) sd, about 0.003 at sd 0.01. Noisy selection (SPRT accepts near-0.005 candidates about half the time) shrinks it further.
  
  The data-doubling comparison: 40k vs 20k is +0.013 train / +0.009 held-out with se 0.004/0.003 over 3 seeds. 20k vs 5k is +0.015/+0.011 over 5 seeds, and that step is two doublings (docs/manager.md around lines 335-345 and 405-412). So one doubling is about +0.01, a figure on the tight2 yardstick. Matching it with a ladder-pool seed-selection gain mixes yardsticks. A data doubling also lifts every future net, while seed selection is a one-off gain over a champion already chosen as the best of 3. Ladder-testing the newer data20k/40k nets would mostly measure recipe gain, not seed selection.
  
  Interpretation: the core point stands. The product comparison is cheap and has barely been used since 10-30. The size of the payoff is inflated.

### The goal-1 thesis (effect primitives let a net read unseen content) is unproven at current strength. The generated-power bench may not have the headroom to show transfer at all.

*Evidence given:* No config in configs/ or runs/*/config.json sets mode ids. The only effects-vs-ids comparison dates from 10-24, and after 500 games of fine-tuning the two encodings are equal (results/warm-start/curve.json). Check 9 fails at 18.3% against a 20% bar. On gen_powers12, the per-card swap cost correlates 0.937 between the thr nets and the gen128 nets, and the between-net sd is the same on generated and original cells (0.055 vs 0.056). No oracle arm exists to show the ceiling.

- **holds.** I checked each piece against the primary files. The conclusion survives, but three pieces of the stated evidence are wrong or misread, and some data points the other way.
  
  What checks out:
  - No config uses ids. Every "mode" key in configs/*.json and runs/*/config.json says "effects" (288 matches, zero ids).
  - Check 9 is in docs/decisions.md line 329. Effects gain MAD is 0.0210 against 0.0257 for ids, 18.3% lower against a 20% bar, recorded as FAIL. Per card, Demon Form is 34.3% better and Go for the Eyes 5.3%.
  - No oracle arm exists. docs/specs/gen-training-arms.md compares lean-gen16 and gen128 only against lean-thr. No reference net knows the 43 test powers, so nothing measures the ceiling.
  
  Corrections:
  (a) Date. results/warm-start/curve.json was written 10-30 (decisions.md line 566). Only the parent nets, value_effects.pt and value_ids.pt, and results/effects.json and ids.json date from 10-24.
  (b) "Equal after 500 games" is right. I averaged the 3 seeds per row. At 500 games, Silent tight a is 0.499 effects vs 0.481 ids, and Silent tight b is 0.481 vs 0.483. But before any fine-tuning (size 0), effects leads by +0.024 and +0.060, and decisions.md says so: features help zero-shot only. Effects also leads ids on Ironclad's tight2 train half at every size: +0.051, +0.018, +0.029, +0.024.
  (c) The 0.937 is per generated card (43 cards, about 7.6 cells each). I recomputed it from results/gen_powers/arms/gen_powers12/*.json and data/bench/gen_powers12.json. Swap cost = original-set cell win minus generated-set cell win, averaged over the 3 seeds of each arm.
    - Per card, thr vs gen128 correlates 0.937. Pairs of thr seeds correlate 0.875.
    - Per cell (326 cells) it is only 0.861.
    - The between-net sd of cell win, averaged over cells across all 9 nets, is 0.060 original vs 0.058 generated. The claim said 0.056 vs 0.055: close.
    - A high correlation doesn't show missing headroom. It is what you'd expect if a card's swap cost is mostly the card's own strength.
  
  Data that bears on headroom (my interpretation):
  - The nets' mean swap cost is 0.040 (original 0.504, generated 0.463), against the spec's MDE of about 0.02 (spec lines 75-77). Transfer would have to recover half the whole gap to show.
  - On the Demon Form cells the swap costs only 0.010. That is because lean-thr nets rarely play Demon Form: 83%/73%/86% of offers never played (learned-play-results.md lines 1079-1095). So the original-card reference is itself crippled.
  - The generator prices only Strength powers, and 84% of the test cards are unpriced (learned-play-results.md first check, around line 970). Many generated cards may be worth little, which shrinks headroom further.
  - Real headroom does exist on an unseen mechanic: a per-mechanic rate feature lifted Demon Form fights by +0.10 to +0.17 per seed. It just isn't measurable on this bench.
  - In the first check, the champion leads the heuristic more on generated cards (+0.021, se 0.011), but the doc puts that down to the heuristic's blind spot.
  
  The underlying pattern: the gen arms tested whether more varied training content helps. They never tested effects against ids, because there is no ids net on that bench. So the only direct tests of the thesis are warm-start zero-shot (positive) and check 9 (positive direction, fails the bar). "Unproven" is fair; "contradicted" would not be.

- **overstated.** I checked each piece of evidence against the files. Analyses were single-thread Python over results/gen_powers/arms/gen_powers12/*.json, joined to data/bench/gen_powers12.json (7,824 fights, 326 cells).
  
  (1) "No config sets mode ids" holds as written. All 55 configs/*.json and 233 runs/*/config.json that have a mode field say "effects". The 10-30 warm_ids runs (runs/2026-10-30-curve-warm_ids-*) have no mode field because they start from models/value_ids.pt.
  
  (2) "The only effects-vs-ids comparison dates from 10-24" is wrong on the date. The warm-start curve ran on 10-30 (run folders dated 2026-10-30; docs/research/learned-play-results.md heading "Warm start on Silent ... (2026-10-30)"). Only its parent nets and check 9 are from 10-24.
  
  (3) "Equal after 500 games" holds: MSE A 0.070 vs 0.072, win B 0.481 vs 0.483, with every interval crossing 0. But the evidence leaves out the row that matters most for goal 1, the zero-shot row (0 Silent games). There, effects beat ids on MSE (0.099/0.294 vs 0.130/0.337) and on win rate (+0.024 tier A; +0.060 tier B, interval 0.041-0.079). That is a small but real zero-shot transfer signal. It is on Silent cards, which reuse known primitives, not on unseen primitives.
  
  (4) Check 9's 18.3% vs the 20% bar holds (docs/decisions.md:329). The same entry says the gate is dominated by net-to-net noise, and the direction favours effects (MAD 0.0210 vs 0.0257). So it is weak evidence either way.
  
  (5) I reproduced the 0.937 correlation. It is per generated card (43 cards), using the mean of the 3 thr seeds against the mean of the 3 gen128 seeds. Per cell it drops to 0.861, and thr against gen16 gives 0.918. A high value is expected anyway, because both nets play the same fight seeds and each card's own strength drives most of the swap cost. The generated cards are cheaper and weaker: the heuristic loses 0.058 from the swap (first-check.json). So the correlation does not measure headroom.
  
  (6) The sd figures 0.055 vs 0.056 match the per-cell sd across all 9 nets, population form (ddof 0): 0.0551 generated vs 0.0563 original. With the 6 thr+gen128 nets it is 0.052 vs 0.054.
  
  (7) No oracle arm exists. A search for "oracle" in docs/specs, docs/manager.md and scripts finds nothing.
  
  (8) Against "may not have headroom at all": the bench has already told two players apart on generated content. results/gen_powers/first-check.json, the 4-fight version of the same cells, has the champion's lead over the heuristic +0.021 (se 0.011) larger on generated than on original. On card-played triggers the lead is +0.083 (se 0.020), and on permanent powers +0.091 (se 0.024). The doc reads this as the heuristic's blind spot (84% of test cards unpriced), not as the net generalising. Either way it shows the bench can resolve differences of about 0.02-0.03 between players. What is unknown is how much room exists above the nets, because there is no oracle or adapted reference.
  
  (9) The core of "unproven" holds. Arms minus control on the generated set: gen128 -0.006 (se 0.010), gen16 -0.004 (se 0.012). Generated minus original within each arm: gen128 +0.006, gen16 +0.002 (learned-play-results.md, results/gen_powers/arms.json).

### The CPU is already busy. The losses are in what gets queued, in delay and in contention, not in idle time.

*Evidence given:* Analyst 5, from jobs/done/*.json: at least one job ran 89% of the time and two jobs 70%. About 45% of thread-hours went to experiments within noise, to runs measured with the biased search, or to failed and hung runs (analyst 1: about 112 of 253.7 thread-h). Every learn run replays the heuristic's tight2 fights, about 10% of learn time, with identical results each time (learn.py:1141). Epochs ran 7-10x slower under paging (logs/jobs/0055-learn.log). Jobs waited 99-790 min between being added and starting.

- **overstated.** How I checked: I wrote a single-thread script (scratchpad u.py) that reads the started, ended, added and threads fields of the 86 started jobs in jobs/done/*.json, plus the one job in jobs/running. It builds a timeline of the job runner's activity. The window runs from 2026-10-30 12:25 to 2026-10-31 16:44, 28.3 hours.
  
  What the data confirms:
  - At least one job was running 88.9% of the window. Two jobs were running 69.6% of it. These match the stated 89% and 70%.
  - The runner reserved 256.1 thread-hours in total (the stated figure is 253.7).
  - Hours by threads reserved: 15.85 h at 12 threads, 5.05 h at 6, 3.11 h at 8, and 3.15 h with no job at all.
  - The 0055-learn epoch times are real. In logs/jobs/0055-learn.log, epochs 1-4 took 236-379 s and epochs 5-10 took 37-67 s, a 6-10x gap.
  - scripts/learn.py around line 1141 runs `heur = heur or tight_results("heuristic", ...)`. That caches the heuristic replay within one run but not across runs, so every learn run re-runs it.
  - Queue waits are real. 0057-learn waited 790 min, and many learn jobs waited 150-720 min.
  
  Where the claim is overstated:
  1. "Not in idle time" is too absolute. The 3.15 h with nothing running is 11% of the window, worth up to about 38 thread-hours at 12 threads. Most of it is two gaps on the first day: 94 min before 0007 and 64 min before 0009, while the runner was being set up. Idle was a real loss early on but small lately.
  2. "Busy" means slots, not cores. Reservations averaged 256.1/28.3 = 9.0 threads, well under the machine's thread count. jobs.py caps the runner at `--heavy-slots 2` and `--thread-budget 14`. The runner's own measurements also show spare CPU: runner.log records 6-10 idle logical threads when most jobs started, usually with another job already running. So the runner's two slots were nearly always full, but the CPU was not saturated. The real limit is the two-heavy-job policy and the machine's memory (hence the paging), not a lack of cores.
  3. Long waits come from queuing jobs hours in advance behind two slots. They show a backlog, not lost CPU. A wait costs time to results, not machine time.
  4. I did not re-check analyst 1's split of 112 of 253.7 thread-hours into wasted categories. It depends on judgement calls ("within noise", "biased search"), so that part is unverifiable from here.
  
  Interpretation: the main point holds. The runner's slots were almost always full, and the bigger losses are in what got queued (repeated heuristic replays, hung or failed runs, experiments that ended within noise) and in memory contention. But "the CPU is busy" really means "the runner's two slots are full". About 3-4 physical cores' worth of capacity stayed unreserved, held back by the memory limit and the slot policy.

- **overstated, refuted.** I recomputed everything from jobs/done/*.json, jobs/running and jobs/runner.log with a small single-thread Python script.
  
  What holds:
  (1) Slot occupancy. Over the 28.3 h span (2026-10-30 12:25 to 2026-10-31 16:44), at least one job ran for 25.16 h (89%) and two jobs ran together for 19.7 h (69.6%). No job ran for 3.15 h (11%). Most of that idle time came on day 1: a 94 min gap after 13:05 and a 64 min gap after 15:11.
  (2) Heuristic replay. Every learn log has one 'tight fights (heuristic)' pass of 24520 fights, taking 1m46s to 5m02s. Over 42 learn jobs that adds up to 117.7 of 1346.8 wall-minutes, or 8.7% (2% to 24% per run; short runs are hit hardest). All 67 heuristic fight records in runs/ and results/ JSON hash to the same value (23c85104), so the replay really does give the same result every time (scripts/learn.py:1141 recomputes it once per run).
  (3) Queue waits. The longest wait is 790 min (0057-learn) and the median is about 141 min.
  (4) The slow epochs are real. In logs/jobs/0055-learn.log, epochs 1-4 took 236-379 s and later epochs took 37-91 s, so 6-10x slower. But only 0055 and 0056 were running then (runner.log: 0054z jobs ended by 12:18; 0055 and 0056 started at 12:19). The log itself shows no paging, so 'paging' as the cause is plausible but not shown. docs/manager.md:375-379 only flags paging as a risk to check, and it records ~2x slower epochs for a different paging episode at 14:00, caused by another project's build.
  
  What fails is the headline 'the CPU is already busy'. The 89%/70% figures count job slots, not CPU use:
  - The declared threads of running jobs average 9.0 across the span. All 12 declared threads were in use only 15.85 h (56%).
  - The runner measures system-wide idle cores at every job start (GetSystemTimes, scripts/jobs.py:160-179, written as 'idle N' in jobs/runner.log). Across 86 starts it ranged 5.0-15.0, median about 9.4 idle. Even when a 6-thread job was already running, the next start often saw 10-12 cores idle (0008: 12.1, 0054: 12.2, 0056: 10.9). These are only snapshots taken at start moments, but they do not show a saturated CPU.
  - The binding limits are the 2-heavy-slot cap and free memory: a job starts only if mem_gb + 1 GB is free. Those limits leave cores unused. That is idle CPU, not a busy one.
  
  The '45% of thread-hours wasted (112 of 253.7)' figure is mostly judgement and I could not verify it. My thread-hour total is 256.1 (it includes jobs still running). Clearly failed or hung runs come to only about 36 thread-h: 0049e 6x3.07 h, 0052a 6x2.38 h ended-unknown, the rest small. The 'within noise' and 'biased search' categories need a per-experiment reading that I did not redo.
