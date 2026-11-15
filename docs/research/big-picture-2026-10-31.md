# Big-picture review, 2026-10-31

Run by the manager after the coverage pilot, the cap-400k depth
reruns and the lean loop: the saved `big-picture-review` workflow (six
lenses, a synthesis, two skeptics per key claim; 19 agents). The raw
lens reports are not copied here; the synthesis and the skeptics' verdicts
are. Numbers carry their source paths. The previous review is
`big-picture-2026-10-30.md`.

## Manager's reading (what changes)

- **The skeptics marked every key claim "overstated"**, none simply wrong
  in its data. What survives: label, loss and curriculum changes under
  one-turn search never moved play (0 of ~9 comparisons beyond noise);
  data (round-0 size, card kinds), the start point (effects features, warm
  start) and depth did. Not surviving: "strength is limited by lookahead"
  (on held-out every net is ~0 and depth doesn't close it), and "much of
  the lead is just the net being non-flat" (the boss lead tracks data).
- **Depth as a player:** the two-turn heuristic at cap 400k is still
  ~0.02 *below* the one-turn r2 net (-0.021 held-out, -0.026 train, se
  ~0.015, skeptic's recomputation). So depth's value is as a teacher or
  with net leaves, both unmeasured. The teacher check (direction 3, step 1)
  is the cheap way to find out.
- **Round 0 has never been scored on tight2.** The cover pilot's r1 nets
  sit below the heuristic, so round-0 quality matters, but nobody knows
  how much r1/r2 add over r0. Scoring the existing r0 nets is cheap and
  decides whether self-play rounds stay in the recipe.
- **Goal 1's held-out gap** sits in power cards, chiefly Demon Form's
  per-turn scaling (39 cells, one card), not in "unseen cards" in general;
  unseen cards built from known parts play near train level. So generated
  content should generate *power mechanics* (trigger x effect x grant), not
  only card kinds; the registry spec's generator follows that.
- **Machine use:** the queue sat empty between manager runs on day one
  (~30-40 thread-h lost); this run queued ~12 h, which fixes most of it.
  Remaining savings (a heuristic tight-results cache) are ~5%.

Re-ranked Next (in `docs/manager.md`): score round-0 nets; data scaling
read paired by seed index; teacher check; Demon Form probe and power-rate
features (with the lookahead build); registry-lite with generated powers;
yardstick fixes and seed selection through the ladder; the heuristic cache.

## Skeptics' verdicts on the key claims

### Strength is limited by lookahead and sibling resolution, not by label accuracy. Every label, loss or curriculum change reads |z| < 2 (0 of 9). Depth and data are the only levers above noise.

- **overstated, refuted.** The negative half of the claim holds up. The positive half (depth is the lever) depends on one favourable cell, and win-rate data in the same files points the other way.
  
    What I checked:
  
    (1) Label accuracy is not the bottleneck: supported. In runs/rung4-nightdb/check.json, rung 4 cuts label error err2 by about a third (A 0.078/0.069/0.088 vs B 0.052/0.045/0.061), yet B_vs_A held-out lead is only +0.0052, CI [-0.0004, 0.0109]. runs/tight2/rescore.json shows held-out leads between -0.012 and +0.007 across caps and frontiers.
  
    (2) Depth: only one of the six paired runs in results/depth/ clears noise. I read the summary.all.won values:
  - heuristic leaves, cap 400k, train: +0.056, se 0.014 (z 4.0). This is the one cited.
  - heuristic leaves, cap 400k, held-out: +0.016, se 0.015 (z 1.1).
  - heuristic leaves, cap 50k: train 0.000; held-out -0.048, se 0.015 (z -3.2, two-turn search loses).
  - net leaves (the champion, r2-s1): train +0.013, se 0.014; held-out -0.010, se 0.014.
  The net-leaf runs used the 50k cap, which docs/manager.md says biases two-turn search, so they don't rule depth out. But they show no depth gain for the learned evaluator either. Held-out, which is goal 1, has no depth result above noise. The guarded and fallback reruns (0038/0039) are still queued.
  
    (3) Evaluator vs depth, in win rate. Compare the one-turn arm 'a' across the same fight sets. The net beats the heuristic by +0.083 on train (0.586 vs 0.503) and +0.037 on held-out (0.535 vs 0.498). Depth adds +0.056 and +0.016. So in actual play, switching evaluator moves win rate more than depth does. That contradicts the puzzle-regret framing ('depth 3x, evaluator only 40%').
  
    (4) The 448-puzzle regret numbers and the '25 of 40 wrong picks within 0.05' figure come from scratchpad scripts (deep.py, classify.py) that are not in the repo. I cannot check them. The '0 of 9' tally is also not in a repo file.
  
    (5) 'Depth and data are the only levers' is contradicted by docs/research/learned-play-results.md around lines 680-690. Effects features vs ids give +0.060 zero-shot win on tier B (interval 0.041-0.079). Warm start vs fresh at 10k games gives +0.054 (0.038-0.070). Neither is depth or data size. The coverage pilot (lines 837-846) does support data and coverage as levers: held-out lead -0.074 with 4 kinds vs -0.025 with 21, and +0.003 for the lean 20k recipe.
  
    Interpretation: the data supports 'better labels alone don't buy play'. It does not support 'strength is limited by lookahead'. On held-out content the measured bottleneck looks like generalisation: every net leads the heuristic by about +0.02 on train and about 0 on held-out, and depth doesn't close that gap.

- **overstated, refuted.** Checked the primary files.
  
    (1) The label/curriculum half holds. In runs/rung4-nightdb/check.json, over_seeds B_vs_A held-out is +0.0019 [-0.0021, +0.0058] and train is +0.0011, while B cut err2 by a third (0.078 to 0.052) and val_mse from 0.171 to 0.151. So better labels bought no play. In runs/tight2/rescore.json the net leads sit inside noise (s0 r7 held-out is -0.012 [-0.021, -0.003], significant but negative).
  
    (2) "Depth is a lever above noise" is true on the train half only. results/depth/paired-train-cap400k.json gives all +0.0565 se 0.0143, n 1328, and 743/668 checks out. But results/depth/paired-held_out-cap400k.json gives all +0.0165 se 0.0147 (z about 1.1), with elite -0.007, Lagavulin -0.060 and Sentries -0.0625. At 50k nodes held-out is -0.048 se 0.015, so depth hurt. With net leaves (paired-net-held_out.json / paired-net-train.json) two-turn gives -0.010 se 0.014 held-out and +0.013 se 0.014 train, both noise. paired-sentries-k16-cap400k.json gives -0.080 se 0.029. The claim's own test (|z|>2 on held-out, the half that matters for generated content) fails for depth just as it does for labels. docs/research/depth-pilot-2026-10-30.md itself calls held-out "level, ~1 se". Like-for-like also breaks: depth is measured as two-turn vs one-turn heuristic, labels as net vs heuristic or arm vs arm. And the train-held-out gap with the same untrained heuristic (+0.056 vs +0.016) shows the variance between fight sets is bigger than the se within one set.
  
    (3) Puzzle regret. One-turn means match the scratchpad pick files: champ_picks.json 0.0189 and heur_picks.json 0.0314, both n=448. Note that docs/research/exact-puzzles.md says the evaluator differences are paired intervals that all hold 0. The two-turn figures (0.010 and 0.0056) come from scratchpad deep.py. That script stops after 85 seconds (`if time.time()-t>85: break`) while two-turn runs 300-800x slower, saves no output, and so most likely covered only the first n puzzles, not the same 448. The "3x on 448" comparison is therefore not shown to be paired and can't be verified.
  
    (4) "25 of 40 wrong picks within 0.05" is wrong. In champ_picks.json, 40 picks are wrong and 18 are under 0.05; the 22 picks at >=0.05 carry 96% of total regret (heuristic: 13 of 43 under 0.05, 98%). The big errors dominate. That fits exact-puzzles.md ("over half give up more than 0.05") and goes against a "close sibling" story.

### Much of the nets' measured lead is the net not being flat where the heuristic is, and self-play past round 1 adds roughly nothing. The round-0 net, which may hold most of the strength, has never been scored on tight2.

- **overstated, refuted.** I checked each part against the primary sources.
  
    (1) "The round-0 net was never scored on tight2." This is literally true for the sweeps' own round-0 nets. tight_results is null in all nine runs/2026-10-30|31-cover*-r0-*/round.json, and the key is absent in runs/2026-10-27-score+branch-s0-r0-bd9a1c3/round.json. But a net trained only on heuristic games was scored on tight2. That net is models/value_effects.pt, the Oct-24 baseline: 30k heuristic games, configs/baseline.json, decisions.md line 356. It was scored as the warm-start curve's size-0 parent. File: results/warm-start/cells/warm_effects-0-sNone-08bf127b7fcb54e4.json, field tight2_train. The test is tight2's train half, every 4th cell: 154 cells, 3,080 fights. It won 0.479.
  - The heuristic's per-fight results on the same specs come from the bit strings in runs/*/round.json tight_results. The heuristic is deterministic: one distinct string across every run. On that subset the heuristic wins 0.509.
  - Paired by fight, with the interval over cells, my computation gives a lead of -0.030 [-0.050, -0.009]. The heuristic-data-only net is clearly below the heuristic.
  - On the same subset the lean r1 nets lead by +0.022, +0.005 and +0.039, mean +0.022. The subset tracks the full train half within about 0.005 for every net.
  - So the closest available proxy for a round-0 net is about 0.05 behind the round-1 nets. That contradicts "the round-0 net may hold most of the strength". Caveat: value_effects.pt is an older recipe (data size, setups, labels), not the lean loop's shared 20k round 0. So the exact claim stays technically open.
  - The cover arms point the same way. Their r1 nets, one round on top of a weak 5k round 0, are all negative: -0.004 to -0.059.
  
    (2) "Round-0 0.818 vs r10 0.810" comes from docs/research/learned-play-results.md lines 107-115, the 2026-10-26 sweep. Those were varied full-HP setups, where the heuristic itself wins 0.797, so win rate there barely separates players. On the same table the round-0 net is worse on the objective being trained: score 1.490 against r10's 1.515 and the heuristic's 1.510, and it loses 17.2 HP when it wins against r10's 12.4. In that sweep every round was below the heuristic on the tight fights. This evidence does not show that round 0 holds the strength.
  
    (3) "Self-play past round 1 adds roughly nothing" holds.
  - Seed check (learned-play-results.md lines 612-617, runs/seed-check/check.json), train lead: r2 +0.027, r4 +0.020, r7 +0.012, r10 +0.017.
  - Lean loop: r1 +0.022 (lines 833-845) against r2 +0.017 (lines 800-803).
  - Night nets (runs/tight2/rescore.json): s1 r1 +0.020, later rounds +0.010 to +0.033, with no trend.
  - Caveat: the seed-check rounds were picked because they passed the gate, so they are not a clean series. What round 1 adds over round 0 is untested with the current recipe.
  
    (4) "The lead is mostly the net not being flat where the heuristic is" is unverifiable, and partly undercut.
  - sat.py is not in the repo, so the 63-67% and 14-22% figures can't be traced.
  - data/bench/decisions.json is set "tight", version 1. Those are the old tight-v1 decisions with the heuristic search agent, not tight2. Reproducing the figures would need the engine.
  - Two observations cut against the mechanism. First, value_effects.pt has outcome labels, so it is not flat where the heuristic is, yet it loses by 0.030. Being non-flat is not enough to produce a lead. Second, the boss lead tracks data, not just a trained net: cover4 / cover10 / cover21 / lean train boss leads are +0.006 / +0.014 / +0.098 / +0.132 (lines 846-847). That suggests learned content rather than the absence of flatness.
  - The ladder's boss +0.132 rests on only 76 pairs (52 cells), with interval [+0.001, +0.262] (results/ladder/tests/0001.json by_type.boss). That is thin support for "bosses carry the biggest lead".

- **overstated, refuted.** I checked each part of the claim against the primary sources.
  
    (1) The flatness mechanism comes from a scale artifact. I re-ran lens 2's sat.py (scratchpad sat.py; my variants sat2.py and sat3.py are in the same scratchpad folder) over data/bench/decisions.json. These are 1000 decisions per half from the tight v1 set (not tight2), sampled along heuristic play with a limit-16 search. The heuristic's max<0.1 share does reproduce: 0.631 train and 0.674 held-out. The r2 s1 net (runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt) gets 0.138 and 0.215. But the two evaluators work on different scales. The median best-option value is 0.029 (train) and 0.013 (held-out) for the heuristic, against 1.463 and 1.186 for the net. So any absolute threshold ("max < 0.1", "spread < 0.02") says the heuristic is flat almost by definition. A scale-free test is whether the best two options tie exactly (gap < 1e-9). On that test the two are alike: heuristic 50.7% train and 59.9% held-out, net 51.0% and 55.6%. With a 0.005 gap the shares are 72%/81% against 56%/62%.
  
    Group pattern: hallway is as flat as boss for the heuristic (spread<0.02 held-out: hallway 0.657, boss 0.674). Yet the nets' lead is about 0 in hallway and large in boss (docs/research/learned-play-results.md lean table: hallway train +0.006, boss train +0.137). So flatness does not track where the lead is.
  
    (2) "Self-play past round 1 adds nothing." The seed check (runs/seed-check/check.json) has no r1 arm. Its train leads, recomputed from the averaged block (r2 +0.0271, r4 +0.0203, r7 +0.0124, r10 +0.0170), support "nothing past r2", not "nothing past r1". The lean r1-vs-r2 figures, recomputed from runs/2026-10-30-lean-s*/round.json minus the heuristic's 0.49724: r1 per seed +0.023, +0.008, +0.036 (mean +0.022); r2 +0.013, +0.030, +0.007 (mean +0.017). Lean-lowhp goes the other way: r1 +0.021, r2 +0.022. The seed sd is about 0.012-0.014, so r1 versus r2 is unresolved either way.
  
    (3) The varied-setups figures (round-0 net 0.818 vs r10 0.810, learned-play-results.md line 111) are 500 games per group. That gap of 0.008 is within noise. On the same rows the round-0 net is worse on score (1.490 vs 1.515) and on HP lost when won (17.2 vs 12.4). The heuristic itself gets 0.797, so this metric saturates and cannot show that round 0 holds most of the strength.
  
    (4) The no-tight-scores check is literally true: every runs/*-r0-*/round.json has tight_win null and tight_results null, including all the cover r0 runs, whose tight_set is 'tight2'. But a heuristic-trained, round-0-type net has been scored on tight2. results/warm-start/curve.json gives the warm_effects size-0 cell (models/value_effects.pt, unchanged) a tight2 train win of 0.479 [0.462, 0.497] on every 4th cell, 3080 games. I aligned the heuristic's per-fight string from runs/seed-check/check.json with data/bench/tight2.json, cell%4==0. On that same subset the heuristic scores 0.509, the r2 retrains 0.531-0.549 and the r10 retrains 0.521-0.530. So that round-0-style net sits about 0.03 below the heuristic, not near the r2 nets. It is not the curriculum's own round 0 (older data and labels), so the claim about that exact net stays unverifiable.
  
    The cover pilot's r1 nets do point the other way. They start from fresh 5k-per-group round 0s and come out below the heuristic on train (cover4 about -0.05 to -0.06, cover10 -0.006 to -0.045, cover21 -0.018 to +0.009). So round-0 quality clearly matters, but nothing shows the round-0 net alone matches the r2 nets.

### Depth is affordable as a teacher on stored states, but not as a self-play or ladder player at cap 400k. Whether it is a stronger teacher than the net (net leaves at 400k) has never been measured.

- **overstated.** The timing numbers check out. logs/jobs/0017-depth-paired.log has "two: 10677s, won 687/1336" and logs/jobs/0018-depth-paired.log has "two: 7387s, won 743/1328". Both jobs ran at 4 threads (jobs/done/0017*, 0018* json), so 10677x4/1336 = 32 thread-s per fight and 7387x4/1328 = 22 thread-s per fight. The one-turn runs took 31 s and 9 s.
  
    The 1.4 s / 76k-node figure is only the held-out cut probe (0017: mean_s 1.435, mean_nodes 76,372, cut_share 16%). The train probe in 0018 shows 0.22 s, 22k nodes and 3% cuts, so the cost per decision varies about 6x. I could not find the "448 endgame states in 10 s / 22 ms" figure anywhere in the repo. docs/research/exact-puzzles.md has the 448 horizon>=1 puzzles but no two-turn timing, so that part is unverifiable.
  
    Net leaves were measured only at cap 50k, and that holds: results/depth/paired-net-{held_out,train}.json args show max_nodes 50000, with cut_share 23% / 12% and diffs -0.010 / +0.013 (logs 0009/0010). "Bias up to 0.15" is -0.229 vs -0.080 (k16, logs 0016 and docs/research/depth-pilot-2026-10-30.md), which is right. But net leaves ran at k4, and at k4 the cap shift was +0.064 / +0.056 overall and at most about 0.14 per encounter (Slime Boss held-out -0.049 to +0.088).
  
    Where it is overstated:
  
    (1) "Not affordable as a ladder player." Ladder tests in results/ladder/log.jsonl ended after 1,150 to 4,090 pairs. At 22-32 thread-s per elite/boss fight (hallway fights are likely cheaper), one entry is roughly 1-5 h at 6 threads. That is the same size as jobs 0038/0039, which estimate 190 min each, and docs/manager.md Next 3 already plans "the two-turn heuristic as a ladder entrant". Depth is unaffordable only as the reigning champion (every later test would play it) or as self-play. Self-play is supported: docs/decisions.md A3 measured net two-turn self-play at 0.20-0.30 games/s against 5-12 games/s for one turn, and the depth-pilot doc says "not for self-play at today's speed".
  
    (2) "Never measured as a teacher." That holds against the net, but a partial teacher measurement exists. docs/research/learned-play-results.md Step 1 (results/teacher_sizing.json) found two-turn k4 heuristic contested regret 0.023 vs 0.056 for one-turn on train, and 0.019 vs 0.037 on held-out. That was at the 50k cap, against a two-turn reference that biases the result upward, and with no gain in wins.
  
    (3) Contradicting data the claim leaves out. I paired the same fights across results/depth/paired-{half}-cap400k.json (heuristic two-turn) and paired-net-{half}.json (net one-turn), matching fights on (cell, seed). Heuristic two-turn at 400k minus net one-turn comes out at -0.021 (se 0.015) held-out and -0.026 (se 0.014) train. So as a player, depth with heuristic leaves is still weaker than the one-turn net it would teach. That weakens the case that depth is a stronger teacher without the net at the leaves. The net-leaf version at 400k is unmeasured, both for strength and for cost: at 50k its trees averaged only 8-16k nodes per decision, so its 400k cost can't be read off the heuristic runs.
  
    What follows is my interpretation. The core gap the claim names is real: no one has compared a depth teacher with the net on ground truth, such as the 448 exact puzzles. But the affordability split is drawn too sharply. A one-off ladder entry is affordable, and labelling stored states at 0.2-1.4 s per decision is affordable only for tens of thousands of states, not for full datasets every round.

- **overstated.** Checked the logs and JSON myself; I ran no new experiments.
  
    What the data shows:
  (1) The timings are copied correctly. logs/jobs/0017-depth-paired.log has "two: 10677s, won 687/1336" at 4 threads (args in results/depth/paired-held_out-cap400k.json); 10677 x 4 / 1336 = 32.0 thread-seconds per fight. logs/jobs/0018 has 7387 s for 1328 fights, which gives 22.3. One-turn took 31 s and 9 s.
  (2) "About 1.4 s and 76k nodes" per mid-fight decision is the held-out probe only: 61 decisions, mean_s 1.435. The train probe in 0018 is 0.223 s and 22k nodes, about 6x less. The probe timing is also noisy. Jobs 0038 and 0039 probe the same 61 decisions (76372 nodes) and measured 1.12 s and 2.15 s. So per-decision cost varies about 2x with machine load and about 6x between halves.
  (3) The figure of about 22 ms per endgame puzzle (448 in 10 s) appears in no file under docs/, results/, runs/ or logs/. teacher_sizing.log has "448.7 games/s", but that is one-turn play speed, not puzzle states. I can't check this number.
  (4) The cap bias is right. Sentries at k 16 went from -0.229 (paired-sentries-k16.json, 50k cap) to -0.080 (cap 400k), a change of 0.149. Note that these are k-16 runs. At k 4 the shifts are: Sentries 0.104, Slime Boss 0.137, all held-out 0.064 (-0.048 to +0.016), all train 0.056 (0.000 to +0.056).
  (5) "Never measured" is true only in the narrow form: net leaves at cap 400k, as a teacher, have never been run. Net leaves exist only at 50k (0009/0010: -0.010 and +0.013, which match the claim), and 0038/0039 run heuristic leaves. But nearby measurements do exist, and the claim leaves them out.
   (a) results/teacher_sizing.log scored the heuristic two-turn search as a teacher on stored contested decisions: regret 0.023 train / 0.019 held-out. The heuristic one-turn search scored 0.056 / 0.037, and docs/research/bench-baseline.md puts the nets' regret at about 0.09 train. Two caveats: the reference those scores are measured against is itself a two-turn sampling search, and the cap was the old 50k.
   (b) There is a like-for-like play comparison on the same fight keys. I matched (encounter, seed) between paired-net-*.json 'one' and paired-*-cap400k.json 'two'. The net's one-turn play beats the heuristic two-turn at 400k by +0.021 held-out (se 0.015, n 1336) and +0.026 train (se 0.014, n 1328). So as a player, depth with heuristic leaves at 400k is already a little weaker than the r2 s1 net with no depth.
  (6) The affordability split is my interpretation, and it is overstated. One 1336-fight paired run took about 3 h of wall time on 4 threads. The ladder tests 0020-0022 used 578 to 2055 fights, so a ladder test of the two-turn search fits in one queued job. docs/manager.md even plans "the two-turn heuristic as a ladder entrant". The claim is right about self-play: at roughly 22-32 thread-seconds per fight, a 30k-game round is days of compute. The teacher side is less certain than stated. At 50k, net leaves cost about 3x more per decision than heuristic leaves (0.168 vs 0.053 s held-out, 0.123 vs 0.058 s train). So a net-leaf teacher at 400k could cost seconds per state, and nobody has measured it.

### The goal-1 held-out gap is a gap in valuing unseen powers. Unseen cards built from known primitives already generalise, so adding card kinds won't close it. Features in outcome units, and generated power mechanics, are what's missing.

- **overstated.** I re-derived every number from primary files with small single-thread scripts. They are in <scratchpad>\skep2.py, skep2b.py, skep3.py, skep4.py and skep5.py.
  
    How I computed it: lead = net win bit minus heuristic win bit, averaged per cell and then across cells, with the se taken over cells. Deck lists came from data/bench/tight2.json and data/bench/tight_bosses.json. Check-6 cards are scripts/selfplay.py HELD_OUT (Twin Strike, Iron Wave, Thunderclap, Pommel Strike, Uppercut). Check-9 cards are the held_out() cards in engine/src/cards.rs:427-445 (Go for the Eyes, FTL, Metallicize, Demon Form, Rage).
  
    WHAT REPRODUCES:
  (a) runs/seed-check/check.json, round 2, averaged over 3 seeds: check-6-only cells +0.029 (se 0.011, 87 cells) and check-9-only cells -0.025 (se 0.013, 106 cells). Train is +0.021 to +0.031 depending on the slice. Exact match.
  (b) c6-minus-c9 is positive in 21/21 runs with tight_results in runs/*/round.json (median +0.057). The claim says 18/18; same direction. The gap is also present in rounds 4, 7 and 10 (c9-only -0.039, -0.034, -0.039).
  (c) results/bosses/lead.json joined to deck lists: Demon Form cells -0.172 (se 0.034, 39 cells) vs +0.043 without (76 cells). Per net: -0.186, -0.167, -0.163. Exact match.
  
    WHAT CONTRADICTS OR WEAKENS THE CLAIM:
  1. The gap belongs to one card, Demon Form, not to unseen powers in general.
  - tight2, round 2, all held-out cells:
    - Metallicize without Demon Form: +0.010 (se 0.009, 122 cells)
    - Rage without Demon Form: -0.002 (se 0.007, 130 cells)
    - Go for the Eyes/FTL with no power card: +0.030 (se 0.008, 106 cells)
    - every cell without Demon Form: +0.017 (406 cells)
    - every cell with Demon Form: -0.016 (204 cells)
  - Bosses (lead.json):
    - Metallicize or Rage without Demon Form: +0.006 (44 cells)
    - Rage cells overall: +0.005, better than cells without Rage (-0.046)
    - Go for the Eyes/FTL without a power card: +0.090 (20 cells)
  - Metallicize is also not an unseen power: it is in known_powers through Lagavulin (docs/decisions.md line 327).
  - So "unseen powers" is one data point: Demon Form, a 3-cost power whose pay-off comes late.
  
    2. The boss Demon Form result is mixed up with boss novelty. learned-play-results.md says the unseen-boss and unseen-card gaps compound. Split by boss (mean of the 3 nets), Demon Form cells vs cells without it:
  - Hexaghost: -0.357 (7 cells) vs +0.032
  - The Guardian: -0.258 (16 cells) vs -0.034
  - Slime Boss: -0.004 (16 cells) vs +0.122
  Only Slime Boss gives a clean, smaller (0.126) Demon Form gap.
  
    3. "py/src/features.rs has no rate features" is misleading. In effects mode (features.rs header; decisions.md line 322), a hook power is encoded as rows: trigger, effect and amount times stacks. Demon Form shows up as "turn start -> +Strength", so the net does see a per-turn rate in primitive units. What it lacks is the summed outcome-unit numbers the heuristic gets from hook_rates (engine/src/heuristic.rs:68). It also never got a training signal for that trigger-effect pairing on the player's side. The training powers cover the parts separately: Brutality has a turn-start trigger and Rupture has a +Strength effect. Nothing tests whether outcome-unit features would fix it; that part is a hypothesis.
  
    4. "Adding card kinds won't close it" is only partly supported, and it pulls against the claim's own fix.
  - The coverage pilot (docs/research/learned-play-results.md, "Coverage pilot" section) says more kinds raised both halves equally (train minus held-out 0.020/0.016/0.015). That fits the claim.
  - Per cover run, c6-minus-c9 stays 0.02 to 0.12 at 4, 10 and 21 kinds.
  - But no cover pool held any card like Demon Form. The one cover10 run with two training powers (s101: Brutality, Rupture) had c9-only -0.023, against about -0.11 for the other cover10 and cover4 runs (n=1, a hint only).
  - "Generated power mechanics" is itself adding card kinds, of one particular sort. The real claim is about which kinds, not that kinds don't help.
  
    5. Card-level "generalises" rests on close neighbours. The check-6 cards are near-copies of training cards, and the Go for the Eyes/FTL evidence is +0.030 on tight2 and +0.090 on 20 boss cells. That part holds, with that caveat.
  
    6. The tight cells are tuned so the heuristic wins about 50%. A negative lead on Demon Form cells can mean the net is bad, or that the heuristic's hand-coded strength-per-turn (hook_rates) is especially good there. This data cannot tell the two apart.
  
    Summary: what the data shows holds (unseen cards made of known parts are near train level, and the deficit sits in the check-9 power cards, all three nets agreeing). The reading is overstated: "unseen powers" is really Demon Form alone, with the bosses entangled. The prescription (outcome-unit features, generated power mechanics) is plausible but untested by this evidence.

- **overstated.** I recomputed the stated numbers from the primary files with per-cell clustering. Scripts are in my scratchpad: c69b.py and df2.py under <scratchpad>\.
  
    WHAT HOLDS
  - The r2 numbers reproduce. I used runs/seed-check/check.json (the mean of seeds 1/101/201 minus heuristic_fights) and data/bench/tight2.json held_out (610 cells).
    - Only-check-6 decks: +0.029 (se 0.011, 87 cells).
    - Only-check-9 decks: -0.025 (se 0.013, 106 cells).
    - Train: +0.027 (the averaged gate value in check.json).
  - The c6-minus-c9 split is positive in every run that stores tight_results in runs/*/round.json (cover4/10/21, lean, lean-lowhp). That is 21 of 21 runs, not 18 of 18. The median is +0.057 and the per-run se is about 0.02.
  - Boss Demon Form reproduces from results/bosses/lead.json joined to data/bench/tight_bosses.json plus tight2's slime_boss cells (the order is asserted equal).
    - Held-out cells with Demon Form: -0.172 (se 0.034, 39 cells). Without: +0.043 (se 0.021, 76 cells).
    - Per net: -0.186, -0.167 and -0.163.
    - The effect holds within each boss. Hexaghost: -0.357 vs +0.032. Guardian: -0.258 vs -0.034. Slime Boss: -0.004 vs +0.122.
    - It also holds in a least-squares fit with start HP, number of unseen cards and boss as controls: Demon Form coefficient -0.197, se 0.039. The Demon Form cells sit at much lower calibrated HP (17-35 vs 34-42), but HP does not explain the effect.
  - Removing power cards closes the r2 held-out gap.
    - All held-out cells: +0.006.
    - Without Demon Form cells: +0.017 (406 cells). Demon Form alone is about half the gap.
    - Without Demon Form, Rage and Metallicize: +0.030 (193 cells), the same as train.
  
    WHAT IS OVERSTATED OR WRONG
  1. "Check-9" does not mean "unseen powers". Two of its five cards, Go for the Eyes and FTL, are attacks. Metallicize's power is a known power: docs/decisions.md line 327 and scripts/selfplay.py line 31 keep it known through Lagavulin. Only-check-9 cells without Demon Form score +0.007 (se 0.014, 50 cells), close to the check-6 cells. By card at r2 (the cells overlap heavily, so these are confounded):
     - Demon Form: -0.016
     - Metallicize: -0.008
     - Rage: +0.001
     - Go for the Eyes: +0.008
     - FTL: +0.014
     - Check-6 cards: +0.010 to +0.024
     The deficit is concentrated in one scaling power (Demon Form), with power cards in general as a smaller, weaker signal. It is not a clean "unseen power" effect.
  2. The proposed split between "built from known primitives" and "unseen powers" is false for these nets. The seed-check nets run in effects mode (runs/2026-10-29-seed-check-r2-s1-1a789b2/config.json, "mode": "effects"). In that mode a hook power's hooks become rows of trigger/effect primitives scaled by stacks (py/src/features.rs header, lines 16-28). So the net sees Demon Form as known primitives too: a turn-start trigger that applies Strength to the player. What it lacks is how much a per-turn effect is worth over the remaining fight. That fits the "no rate / outcome-unit features" part of the claim, not "unseen". hook_rates in engine/src/heuristic.rs (lines 68-110) does turn per-turn hook effects into rates, and I found no rate features in features.rs. That part of the stated evidence holds.
  3. "Adding card kinds won't close it" goes beyond the data. In the coverage arms, the only-check-9 lead improves from about -0.107 (cover4, three seeds averaged) to -0.082 (cover10) to -0.056 (cover21). The c6-minus-c9 difference stays about +0.05 to +0.07. So more kinds raise check-9 cells in absolute terms but do not close the relative gap. No arm tested generated power mechanics, so whether those would close it is untested, not shown.
  4. The 18/18 (actually 21/21) agreement and "all three nets agree" are weaker than they look:
     - Every run is scored on the same fixed 87 and 106 cells (one deck sample), so the runs are not independent replications of the population of decks.
     - The three boss nets share training data and differ only in training seed, so their agreement rules out training-seed noise only.
     - The Demon Form boss result rests on 39 cells and one card.
  
    INTERPRETATION
  The data supports "the held-out gap is mostly in valuing power cards, chiefly Demon Form's per-turn scaling". It does not support "unseen powers" as a category, or the claim that card kinds cannot help. "Rate / outcome-unit features" is a plausible hypothesis that the data is consistent with, but no run has tested it.

### Recipe questions below about 0.02 (shared round 0) or 0.03 (fresh round 0) can't be decided on this machine. Questions about one net against another are cheap. The current yardstick spends most of its fights where they carry no information.

- **overstated, refuted.** Checked against the primary sources. The arithmetic is right, and the cited facts are mostly right. The headline conclusions do not follow from them.
  
    (1) Seeds formula. k = 2(2.8 sd/delta)^2 gives 7.7 seeds per arm at sd 0.007 and 35.3 at sd 0.015 for delta 0.01. The same formula gives 1.9 seeds at delta 0.02 with sd 0.007, 8.8 at delta 0.02 with sd 0.015, and 3.9 at delta 0.03 with sd 0.015. The sd inputs match docs/manager.md:306-307 (shared round 0: 0.0066 / 0.0076) and :367 (fresh round 0: ~0.014-0.017).
  
    The claim says questions below 0.02 or 0.03 "can't be decided on this machine", but the formula says otherwise once you look at what a run costs. In jobs/done/0029-0037-learn.json (coverage pilot, 5k round 0, 6 threads), each run took 11.5-16 min. In jobs/done/0023-0028 (lean loop), each took 30-54 min. The machine runs two heavy slots at once (manager.md). At those costs:
  - delta 0.01 with a shared round 0 needs about 16 runs, roughly 4-7 h.
  - delta 0.01 with a fresh round 0 needs about 70 cheap runs, roughly 9 h.
  - delta 0.02 with a fresh round 0 needs about 18 runs, roughly 2-8 h.
  That is one night, not impossible. The claim's 0.02 and 0.03 floors match the old figure from docs/research/big-picture-2026-10-30.md:66-69 (3 seeds per arm rules out effects above ~0.015; one seed, above ~0.025-0.03). They come from current seed counts, not from machine capacity.
  
    The real limit is per fight type. Seed sd is elite 0.017 / 0.019 and boss 0.022 / 0.025 with a shared round 0 (big-picture doc :173-176), so a boss question at delta 0.02 needs about 24 seeds per arm, more with a fresh round 0. Larger runs (data40k) also cost more. The claim's single overall floor hides both.
  
    (2) "Net vs net is cheap". This holds. results/ladder/log.jsonl shows three tests decided in 69, 69 and 180 s, using 1150, 1305 and 4090 pairs (cap 16000, d1 0.01). One caveat: a ladder test only measures fight noise between two fixed nets. A pass says nothing about a recipe. 0001 passed overall, but its held-out half was +0.010 [-0.017, +0.038] (results/ladder/tests/0001.json).
  
    (3) Hallway concordance. I recomputed this from pairs_played, counted pairs only. Hallway pairs ended the same way for both players 0.922 / 0.953 / 0.962 of the time in tests 1-3; hallways are 893 of 1226 tight2 cells, 72.8% (data/bench/tight2.json). That matches the claim. But elites (0.754 / 0.843 / 0.830) and bosses (0.684 / 0.839 / 0.856) also mostly end the same way, and the whole pool does too (0.872 / 0.923 / 0.928). Hallways hold 73% of fights and 38-45% of the pairs that end differently: hallway / elite / boss counts are 65 / 58 / 24, 45 / 42 / 14 and 113 / 143 / 39.
  
    So hallways are less informative per fight, not uninformative. And "most fights carry no information" is a property of paired win/loss tests in general, not of the hallway share. Pairs that end the same way are also not literally zero information here. The SPRT in scripts/ladder.py (llr at about line 80) tests the mean lead per fight, so those pairs enter n and the variance. Dropping hallways would change what is measured (the pool weights); it would not just remove waste. Whether hallways take most of the time is unverifiable: I found no timing per fight, and hallway fights are probably shorter.
  
    (4) Calibration. This holds: 206 of 1110 cells have hp == 1 (data/bench/calibration2.json). 'tried' is 2305. Of the 963 excluded cells, 836 say "wins at 1 HP" and 3 say "wins at max HP", 839 together, plus 124 dropped as steep. "839 because the heuristic wins at 1 HP" is about right, though 3 of them are the max-HP case. This shows the bench is cut at the heuristic's edge. It does not show the ladder wastes fights.
  
    Interpretation: the claim takes a seeds-per-arm budget and presents it as a machine limit. Runs cost 12-54 min, so delta 0.01 recipe questions on the overall lead cost a night, not "can't". The hard part is per-type questions, especially bosses with a fresh round 0. The yardstick point is half right: nearly every fight in every group ends the same way for both players. Hallways are the low-yield 73% by count, and by time that is unknown.

- **overstated.** The raw numbers check out. The conclusions drawn from them go further than the data does.
  
    Checked and correct:
  (1) The formula k = 2(2.8 sd/δ)^2 gives 7.7, so 8 seeds, at sd 0.007, and 35.3, so 35 seeds, at sd 0.015. Both are right for δ = 0.01. The sd sources are docs/research/learned-play-results.md:866-871: shared round 0 gives 0.0066 / 0.0076, and fresh round 0 gives cover21 0.017 / 0.014 and cover4 0.005 / 0.011.
  (2) results/ladder/log.jsonl: tests 0001 and 0002 took 69 s each (1,150 and 1,305 pairs) and test 0003 took 180 s (4,090 pairs), all at d1 = 0.01.
  (3) data/bench/tight2.json: hallway is 9,000 of 12,320 train fights and 8,860 of 12,200 held-out fights, about 73%.
  (4) In the pairs_played arrays of results/ladder/tests/0001-0003.json, both players ended counted hallway pairs the same way 92.2%, 95.3% and 96.2% of the time (all pairs: 93.1 / 95.2 / 96.2%). I computed this with a short Python count of cand == champ per group.
  (5) data/bench/calibration2.json: 206 of 1,110 cells have hp == 1. 839 excluded entries carry the reason "wins X at 1 HP", plus 124 "steep" entries, for 963 excluded out of 2,305 tried.
  
    Where the claim goes too far:
  (a) The thresholds contradict the claim's own evidence. With shared round 0, δ = 0.01 needs only 8 seeds per arm, about 16 runs. docs/manager.md:400 puts a lean seed at about 50 min (3 x 50 min), so that is roughly 13 h on one lane, which this machine can do. By the same formula, δ = 0.02 with shared round 0 needs only about 2 seeds, and δ = 0.03 with fresh round 0 about 4. Even 35 seeds per arm at δ = 0.01 fresh means about 70 runs: slow, maybe 1-3 days with parallel lanes, but not impossible. "Can't be decided" should read "costs N run-hours".
  (b) The fresh sd of 0.015 comes from 3 seeds per arm, and one of the arms (cover4) shows 0.005. An sd from 3 samples has a 95% interval of roughly 0.5x to 6x, so the 35-seed figure is itself very uncertain.
  (c) Pairs that end the same way are what pairing is for, not waste. A paired difference has variance of about P(discordant), around 0.04-0.08 here, against about 0.5 for unpaired games: roughly 7-10x less noise. Elite and boss pairs also end the same way 75-86% of the time (counted pairs), so about 93% of all pairs end the same way (test 0003). This is the nature of comparing close nets, not something special about hallway.
  (d) What the data does support: per pair, hallway carries about 3-4x less information than elite or boss, since 4-8% of hallway pairs differ against 15-25% for elite and boss. Weighting the pool toward elite and boss, or toward cells that differ more often, would make tests cheaper.
  (e) The 1-HP numbers describe how the pool was built: cells floor at 1 HP, and decks the heuristic wins even at 1 HP were dropped. They are evidence about representativeness, not about information per fight.
  (f) "Net against net is cheap" holds. Note, though, that test 0001 passed on the train half (+0.064) while the held-out half's interval included zero (+0.010, -0.017 to +0.038). So a cheap pass answers a narrower question than the claim implies.

### The machine does useful work only about half the time. Cheap process fixes are worth more CPU than any single experiment.

- **overstated.** I recomputed everything from the primary files using small single-thread Python scripts.
  
    What the data shows:
  1. Thread-hours. I summed threads x overlap from started/ended in jobs/{done,running}/*.json over 10-30 12:25 to 10-31 01:00, counting the still-running 0038/0039 up to 01:00. That gives 94.6 thread-hours against 16 x 12.58 h = 201.3, which matches the claim. Note that 01:00 was later than the clock when I checked (00:45), so the tail is extrapolated.
  2. The denominator is too big. The runner itself caps work at heavy_slots=2 and thread_budget=14 (scripts/jobs.py lines 214 and 357). docs/manager.md "Machine limits" says at most two CPU-heavy jobs at once. Every learn or depth job asks for 6 threads, so the most the runner can ever hold is 12 threads. Measured against 12 threads (151 thread-hours), the jobs held 63%, not 47%. The runner log shows only 6-9 idle cores while a single 6-thread job ran.
  3. The idle time is all on the runner's first afternoon. The 188.6 min with nothing running fall entirely between 12:26 and 17:42: 12:26-12:37, 13:05-14:39 (94 min), 15:11-16:15 (64 min), 17:14-17:23 and 17:32-17:42. After 17:42 idle time is about 1 min. From 17:42 to 00:45, jobs held 70.2 of 84.6 thread-hours at the 12-thread cap (83%). From 20:41 on they held 46.6 of 48.8 (95%). So "half the time" describes the runner's bring-up day, not how it runs now.
  4. The empty-queue cause holds, and is a bit larger than stated. Comparing each job's 'added' time with the gaps, the queue was empty for about 181 min of the 188.6 idle minutes, not 2h38m.
  5. The steady-state loss is a different problem: 17:50-20:41 ran at only 8 threads for 2.7 h. That is because 0017/0018 were 4-thread jobs that filled both heavy slots while 6-thread jobs 0020-0037 waited. That is another process issue, about 11 thread-hours, not mentioned in the claim.
  6. Heuristic tight_results hold. All 15 runs/2026-10-3*-r1-*/round.json files have the same md5 for tight_results.heuristic (23c85104), and tight_set is tight2. The logs logs/jobs/0023-0037-learn.log show 'tight fights (heuristic) done in' times of 106-302 s per job. That totals 2488 s of 23337 s job wall time (10.7%), ranging from 7% to 24% per job. This is a genuinely free fix: caching saves about 4 thread-hours over 15 jobs.
  7. The patience claim reproduces numerically but is not waste. Epochs after the best one total 3000 of 11924 s across 30 training runs. But re-simulating early stopping on the same val-MSE curves: patience 2 would stop before the best epoch in 10 of 30 runs (val MSE worse by 0.003-0.024, against a base of about 0.15), and patience 1 in 21 of 30. Most of those 3000 s are the price early stopping pays to find the best epoch, not a cheap fix.
  8. "More than any single experiment." This is true looking back: the 3.1 h idle at the 12-thread cap is about 38 thread-hours, against about 19 for one 190-min depth job such as 0038. Looking forward it is weak. At 00:20 the manager queued 18 jobs (0040-0057, about 11.7 h of estimates), which already fixes the empty-queue gap. What is left (the heuristic cache, a heavy-slot rule for small jobs) is roughly 10% of learn-job time, plus a one-off 11 thread-hours.
  
    Interpretation: the underlying pattern is real. The CPU sat idle while the queue waited on 2-hourly manager runs, and that fix (keep the queue deep) mattered more than any single experiment that afternoon. But "useful work only half the time" leans on the full-machine thread denominator and a window that is mostly the runner's first day. One of the three named fixes, patience, is not cheap. The biggest one is already applied.

- **overstated.** The raw numbers reproduce exactly. The two conclusions drawn from them go further than the data supports.
  
    How I checked:
  1. Thread-hours. I parsed the start/ok/failed lines in jobs/runner.log and paired each start with its end; the two jobs still running were closed at 10-31 01:00. Jobs held 94.59 thread-hours out of 201.2 available (all logical cores x 12h35m). The longest stretches with nothing running were 13:05-14:39 (94 min) and 15:11-16:15 (64 min). Together that is 2h38m, and the added timestamps in jobs/done/*.json (0005 added 14:36, 0009 added 16:12) confirm the queue was empty then. All gaps together come to 3h08m.
  2. Heuristic results. In all 21 runs/2026-10-3*/round.json files that have tight_results (r1 and r2 rounds alike, all on tight_set tight2), the md5 of tight_results['heuristic'] is the same: 23c85104. The whole tight_results differs per file, because the net half differs.
  3. Recompute time. Across logs/jobs/0023-0037-learn.log, the "tight fights (heuristic) ... done in" time runs from 106 s to 302 s. It sums to 2,488 s, which is 10.7% of the 23,337 s of summed job wall time (from started/ended in jobs/done).
  4. Training after the best epoch. Summing the "epoch N: val MSE (Xs)" lines gives 11,924 s of training, of which 3,000 s came after the best epoch.
  
    Where the claim goes too far:
  (a) "Useful work only about half the time" is wrong as a time statement. At least one job was running for 9h27m of the 12h35m, about 75% of wall time. The 47% figure is a share of thread capacity, and its denominator is 16 threads, which the runner never aims for. scripts/jobs.py defaults to --heavy-slots 2 and --thread-budget 14, and these jobs request 6 threads each, so the practical ceiling is about 12 threads. Measured against 14 threads, the share is 54%; against 12, it is 63%. The runner's own idle readings at job start were 5.6 to 14.9 cores (runner.log), so other processes were already using part of the machine. "Held threads" is also not the same as "useful work": 0017 and 0018 were flagged stalled while still computing.
  (b) "Nothing ran" is true only of the queue. The git log shows other work committed during the gaps: search CRN at 14:10, a depth pilot run outside the queue at 14:37 (two-turn 34/60 against one-turn 25/60), and the Act-1 bosses steps at 14:45-15:04 (builds and tests). So part of the 2h38m was used outside the queue.
  (c) "Worth more CPU than any single experiment" is roughly a tie at best. My estimates multiply wall seconds by the job's 6 threads:
  - Caching the heuristic results would save about 4.1 thread-hours.
  - The post-best epochs cost about 5.0 thread-hours. Only part of that can be recovered, because patience 3 is how the run finds its best epoch.
  - The queue-empty gaps cost at most 2.63 h x 12 = 31.6 thread-hours, and less given the work outside the queue in (b).
  For comparison, single experiments cost: the lean loop 0023-0028 about 26.3 thread-hours (15,795 s x 6); the coverage pilot 0029-0037 about 12.6 (7,542 s x 6); the cap-400k reruns 0017+0018 about 20 (5h04m x 4 threads). The two compute fixes together (about 9 thread-hours, about 5% of held time) are smaller than any of these. Only fixing the gaps between manager runs reaches the size of the largest experiment.
  (d) The claim also misses one loss. From 18:16 to 20:21, nineteen jobs were pending (added by 18:11), but 0017 and 0018 held both heavy slots with only 4 threads each, so the runner held about 8 threads for 2 hours. That is a heavy-slot rule problem, not an empty queue.
  
    What the data supports: the queue sat empty between 2-hourly manager runs, and some heavy-slot blocking added to that. These were the largest avoidable losses, about 30-40 thread-hours on day one, comparable to one large experiment. The heuristic recompute and the patience setting are small savings, about 5% of held time.

## Synthesis

### Diagnosis

Where the project stands. On goal 2 (strong StS combat), a week of learning work moved the one-turn learned player from -0.030 to about +0.027 over the one-turn heuristic on tight2's train half. Nearly all of that gain is in elites and bosses (scripts/analysis/out/regroup.json). One extra turn of search on the plain heuristic buys about as much (+0.056 on train elite+boss, results/depth/paired-train-cap400k.json). No metric has a ceiling or an absolute scale, so "Stockfish-level" can't be stated on any current yardstick. On goal 1 (random and custom content), no random content can exist yet: cards are static Rust tables and powers are a Rust enum. The held-out gap people have been reading is not a card-generalisation gap. It is a gap in valuing unseen powers.

The underlying pattern. All six lenses point the same way once you put them side by side. Playing strength here is decided by sibling resolution: telling apart options whose values are a few percent apart in tight, knife-edge positions. It is not decided by how accurate the value labels are in absolute terms. Three things improve sibling resolution: more lookahead (depth computes the consequence instead of estimating it), more and more varied data (lower-variance estimates in the flat region), and a stronger teacher's ranking. Those are exactly the levers that ever cleared noise: depth (z about 4), data and coverage (+0.03 to +0.05), warm start. Label work (exact solver, caps, frontiers, curriculum rounds, loss switches) improves absolute calibration, mostly in endgames. It lowered MSE four times and moved play 0 of 9 times. The heuristic it is all measured against is flat (it scores every option below 0.1 in 63-67% of tight decisions, per lens 2's sat.py). So much of the "learned" lead is simply "not flat". That would also explain why self-play rounds past 1 add nothing measurable, and why the round-0 net (a supervised fit to heuristic games) may hold most of the strength. Nobody has scored that net on tight2.

What has been holding it back. (1) The project has treated a self-play loop with a one-turn teacher as its strength engine. That teacher is no stronger than the student, which in NNUE terms is lambda = 0. Every strong game AI distils a stronger search into its evaluation; this project never has. (2) It spent its scarcest resource on recipe science at the 0.005-0.01 level. That is undecidable on this machine: training-seed variance needs 8-35 seeds per arm. About 43% of productive CPU in 10-28 to 10-30 went to the flat label line. (3) It reads a narrow yardstick: cells calibrated to the flat heuristic's 50% (median start HP 5-6), where 92-96% of hallway pairs carry no information. It also keeps picking the best of many noisy numbers (4 gate passes that were luck, a +0.15 depth pilot, a +0.017 rung 4). (4) The machine itself does useful work about half the time: the queue ran dry for 25% of a 12.6 h window, and every job recomputes byte-identical heuristic results. (5) On goal 1, nine fidelity specs sit ahead of the one spec (a runtime registry) that would let random content exist at all.

Settled conflicts. Depth: lenses 1, 2 and 4 rank it first, lens 5 says stop. Both are right about different uses. As a player it costs 22-32 thread-seconds per elite or boss fight at cap 400k (0017: 10,677 s x 4 threads / 1,336 fights; 0018: 7,387 s x 4 / 1,328). So lens 4's estimate of 1-1.5 CPU-h for a 3,000-pair ladder test is wrong by about 15-20x; the real figure is about 20-25 thread-h. As a labeller on stored states it costs about 1.4 s per mid-fight decision, and about 22 ms per endgame puzzle state (448 puzzles in 10 s). So depth is affordable as a teacher on a targeted subset of states, and as a boss-only option at test time. It is not affordable as a self-play player. Data volume: lens 1 says push it to 80k/160k, lens 6 says data scaling is underpowered. Read 0045-0057 as a pilot. But the configs share round0_seed 0 and pair train_seed by seed index (data5k-s1 and data20k-s1 both use train_seed 1001), so reading 5k vs 20k paired by seed index probably removes much of the seed noise. Only scale further on a clear slope. The reason to generate content: the manager's 10-31 reorder justifies the registry by "more card kinds". Lens 3's evidence (the c6 vs c9 split in 18/18 runs, the Demon Form boss gap) says it should generate power mechanics (trigger x effect x grant combinations), not card kinds. I side with lens 3. The registry moves forward either way, but the generator's design differs.

What none of the six saw. The data-scaling queue and the coverage pilot both make round-0 nets without scoring them (runs/2026-10-30-cover*-r0-*/round.json: no tight_results). So the single most decisive question in lens 1 can be answered from about ten nets that already exist. The ranking loss already orders options by recorded search values (learn.py docstring), so distillation from depth needs no new loss, only different search values in that term for a subset of states. That is the smallest possible amplifier change. And the yardstick and the baseline are calibrated against each other (tight cells sit where the heuristic is flattest). That inflates exactly the boss and elite leads that the project counts as its learned strength.

### Directions (ranked by value per CPU-hour)

1. **Throughput multipliers: a queue that never runs dry, a heuristic cache, patience 2** (both (capacity); CPU: ~0.3 CPU-h (one small unit test of cached vs fresh results at every=100, plus fast suites))

   What: (a) Keep at least 6 h of pending jobs, plus a filler list the runner starts when nothing else is pending (extra seeds of the current arms, ladder tests of new r2 nets), and wake the manager when pending work drops below a threshold. (b) Cache learn.tight_results('heuristic') on disk, keyed by (tight set, every, search settings, rules fingerprint); depth_paired's one-turn arm reads the same cache. (c) Patience 2 in experiment configs. (d) Log peak memory per job in the runner, then consider a third heavy slot.

   Why: About 25% idle time, 10% duplicated work per learn job and 25% of training time after the best epoch, all at zero risk to results. This raises the effective CPU of every later direction by roughly 30-50%.

   First check: md5 of a cached heuristic tight_results equals 23c85104 (the value shared by all 10-3x r1 runs). Re-run lens 5's gap analysis on jobs/*.json after 24 h; target under 5% of time with nothing running.

2. **Score the existing round-0 nets on tight2** (goal 2 (and the recipe that goal 1 runs inherit); CPU: ~0.6 CPU-h (about 207 s per net x about 10 nets))

   What: One job that rescores, on tight2 by fight type and half and paired against the heuristic: runs/2026-10-27-score+branch-s0-r0-bd9a1c3/model.pt (the night's round 0), the 8+ runs/2026-10-30-cover*-r0-* nets and the lean round 0. Also add r0 scoring to the data-scaling read (0045-0057 run rounds n=1, so r0 and r1 both exist).

   Why: It decides whether self-play rounds have contributed anything. If round 0 is within about 0.01 of r1/r2, the recipe is 'fit a big heuristic-games dataset, then search', and rounds (about 25 min each) leave the recipe. Any amplifier must then beat round 0. The nets already exist.

   First check: The night r0 net's train lead against sc r2's +0.027 and lean r1's +0.022. Within 0.01 means rounds are dead weight.

3. **Teacher check, then distillation through the existing ranking loss** (goal 2; CPU: Step 1 ~0.5-1 thread-h; step 2 ~5-8 thread-h (bosses only); step 3 ~8 thread-h of labels + ~3 h of training)

   What: Step 1: on about 1,000 stored mid-fight elite and boss states (db/train.sqlite), compute root option values with one-turn net search and with two-turn net-leaf search at cap 400k with the fallback guard. Measure how often the top choice differs and the value gap between the two picks. Step 2, if they disagree on 5% or more: a boss-only paired screen of net-leaf two-turn vs one-turn net on both halves. Step 3, if step 2 is at least +0.02: label about 20k contested elite and boss states with two-turn values, feed them as the ranking-loss targets in place of the one-turn search values (lambda in {0.5, 1.0} for the value target), train 3 seeds, ladder-test against the champion.

   Why: This is the one ingredient every strong game AI has and this project lacks: a teacher stronger than the student. Depth is the only search change measured above noise. Labelling stored states costs about 1.4 s each, unlike playing at 22-32 thread-s per fight. Using the ranking term is the smallest change and targets the measured error type (near-ties between sibling options).

   First check: Step 1 alone. If two-turn and one-turn net search pick the same option in more than 95% of contested states, distillation has nothing to teach, and depth stays an optional boss-only search at test time.

4. **Power features in outcome units (goal 1's zero-shot fix)** (goal 1; CPU: Probe <0.5 CPU-h; arm (a) ~15 thread-h)

   What: First, a Demon Form probe: on held-out boss decisions where Demon Form is playable, compare how often and on which turn the r2 nets and the heuristic play it, and the net's gain for playing it. Then arm (a): expose engine hook_rates (block/turn, Strength/turn, self-loss/turn per power on an entity and per power a card grants) as named feature columns. Run 3 seeds against lean-thr, read on the only-c9 and Demon Form boss slices. Later, arm (b): rates measured by simulating a few sandbox turns with and without the power, so the features stay content-agnostic.

   Why: The whole held-out deficit is in unseen powers (18/18 runs; Demon Form -0.172 on bosses). The heuristic copes because it converts any hook row into outcome units; the net sums embeddings and can't form the frequency x magnitude x remaining-turns product. This is the most direct test of whether goal 1's representation is right.

   First check: The probe: under-playing Demon Form points to horizon or rate features; over-playing it into lethal points elsewhere. Set the MDE before running (about 0.04 on only-c9 at fresh-round-0 sd).

5. **Fix the yardstick: novelty slices, paired HP lost, a held-out non-inferiority test, a two-turn anchor** (both (measurement); CPU: (a) 0; (b) ~0.3 CPU-h first check, then 10-30 min per test; (c) 5-15 min extra per passing test; (d) about 0 if specs match; (e) ~35 min per 3,000-pair test once built)

   What: (a) Add only-c6 / only-c9 / both / Demon Form slices to coverage_read, lean_read, boss_lead and the ladder report. (b) Store hp_start and hp_end per pair in ladder.py, and add a pool of the same deck x encounter cells at start HP of 40-100% of max, scored by paired HP lost (a death counts as all remaining HP plus a penalty). (c) Replace the held-out floor of -0.005 with a sequential non-inferiority test (H0 <= -0.01, H1 >= 0). (d) Make the two-turn heuristic an anchor entrant, built from existing per-fight files where the fight specs match. Then (e) an Act-1 gauntlet with HP carried over, as goal 2's main measure.

   Why: The novelty split stops lean-thr and data scaling from being misread (Guardian's gap is mostly Demon Form). HP lost gives signal on the 92-96% of hallway pairs where both players get the same result, and measures what a run spends. The current held-out guard rejects a true-zero net 37% of the time.

   First check: Replay 0001's and 0003's pairings for about 2,000 pairs on the run-HP pool. Compare the effect in sd units per pair with win/loss, and check that it ranks 0001 the same way.

6. **Registry-lite before the fidelity series, then a random-power benchmark** (goal 1; CPU: Build ~1-2 CPU-h of suites; benchmark ~45 thread-h (defer until directions 1-3 have freed CPU))

   What: One spec: a runtime card table plus N reserved generic power slots whose hooks (trigger, condition, effects, lifetime) load from JSON or Python, a register API and a content fingerprint, with golden games bit-identical when no slot is used. Then about 200 generated powers from existing atoms, split by combination. Arms: no generated content vs 16 vs 128 generated powers in training, 3 seeds each, judged on test-power decks, official check-9 cells and Demon Form boss cells.

   Why: Random content is goal 1's training distribution and its only test set large enough to read generalisation by mechanic. Today it is 9 specs away. The build is mostly coding, not CPU.

   First check: Before any training, run the champion against the heuristic on 300 decks holding random power cards. If it already matches the heuristic there, the official-card gap is specific to Demon Form and the benchmark shrinks.

7. **Seed selection through the ladder (cheap product strength)** (goal 2; CPU: ~0.05 CPU-h per test)

   What: Ladder-test the best existing lean r2, cover21 r1 and (later) data20k/data40k r1 nets against the champion with --no-promote off. Promote passes. Adopt this as the routine end step of every finished run.

   Why: Best-of-5 at seed sd 0.015 is worth about +0.017, as big as most recipe effects. Each test takes 1-3 minutes and needs no new training.

   First check: One test: the top lean r2 net by tight2 train lead vs r2 s1.

8. **Let data scaling finish as a pilot, read paired by seed index** (both; CPU: Already queued (~12 h); no new CPU unless the slope holds)

   What: Keep 0045-0057. Read 5k vs 20k paired by seed index (they share round0_seed 0 and train_seed per index), with r0 scored too. Queue 80k only if 20k beats 5k by at least 0.02 and 40k is at least 20k. Check memory before going larger.

   Why: Data volume is one of the few training-side levers above noise, and heuristic games are cheap. But the design has MDE about 0.027-0.031 unpaired, so it is a pilot, not a verdict.

   First check: Paired 5k vs 20k difference per seed index and its spread. If the paired sd is well below 0.015, coupling works and becomes the default for recipe questions.

### Stop doing

- Stop experimenting with label sources, exact-solver caps, frontiers, curriculum rounds, round counts and loss switches under one-turn search. 0 of 9 cleared noise, and they took about 43% of productive CPU. Return to the label side only when the labels come from a stronger search (depth), which makes them different in kind.
- Stop running multi-seed recipe comparisons whose expected effect is below about 0.02 (shared round 0) or 0.03 (fresh round 0). For product strength, train 3-5 seeds and promote whichever net passes the ladder. Leave such science questions alone unless coupled arms make them decidable.
- Stop broad heuristic-leaf depth runs after 0038/0039. Spend no more CPU on two-turn search as a ladder or self-play player at cap 400k (about 20-25 thread-h per 3,000-pair test). The next depth CPU goes to net leaves on bosses and to labelling stored states.
- Stop reading decisions-set regret and ranking as strength: their reference is the flat two-turn heuristic. Stop bucketing depth effects by an arm's own fight length; that split reverses when you bucket by the other arm's length. Report by encounter and start-HP band only.
- Stop acting on any reading above 0.05, or any pass right at its bar, before an artifact hunt: fight mix, cut and cap counts, database or version used, a second seed. Every reading of that size in this project's history was an artifact.
- Stop using the tight2 gate and the monotone check to pick or stop rounds inside learn.py. Picking the best of about 20 rounds produced 4 of 4 lucky passes. Keep tight2 as a regression and sensitivity check only.
- Stop scaling card kinds as the goal-1 lever, and stop counting fidelity specs 2-9 (amount expressions through monster patterns) as goal-1 progress. Generate power mechanics, not card kinds.
- Stop letting the job queue run dry between manager runs, recomputing the heuristic's tight-fight results in every job, and re-reading a 32.5 KB manager.md full of history on every wake-up.

### Next 48 hours (synthesis's plan, before the skeptics)

The CPU now runs 0038/0039 (held-out elite+boss at cap 400k with the fallback and guard players, about 3 h each). Behind them are 0040/0041 (slow suites on merged main), 0042-0044 (lean-thr) and 0045-0057 (data scaling).

Hours 0-3, while 0038/0039 run, CPU-light work only:
(1) Build the heuristic tight-results disk cache and patience 2 for experiment configs (direction 1). Don't run tests until a slot frees.
(2) Add the novelty-class slices (lens 3's ho_cards.py and c69.py logic) and the round-0 scoring hook to the read scripts.
(3) Write a filler list and set a pending-hours floor in the manager protocol. Slim manager.md (move the history out of Next and For-the-owner into an archive file).
(4) Write the artifact-hunt rule and start an effect-size ledger from lens 1's 23-row table.
(5) Draft the registry-lite spec, plus a short spec for hook_rates feature columns.

Hours 3-6: when 0038/0039 end, read them by encounter with cut and override counts (guard > fallback means noisy-max costs). Then insert ahead of 0042, in this order:
- job A: score round-0 nets on tight2 (the night r0 net plus the cover and lean r0 nets; about 0.6 CPU-h);
- job B: the teacher check, step 1 of direction 3 (1,000 stored elite and boss states, one-turn vs two-turn net-leaf root choices; about 1 thread-h);
- jobs C1-C3: ladder seed-selection tests of the top lean r2 and cover21 r1 nets against r2 s1 (minutes each).
Let 0040/0041 run in the other slot. Don't read 0042+ if they fail.

Hours 6-24: 0042-0044 (lean-thr), then data scaling. Read lean-thr split by Demon Form and no Demon Form on held-out Guardian. Credit threshold rows only on the no-Demon-Form cells. In parallel, CPU-light: run the Demon Form probe as a small job (<0.5 CPU-h). Add hp_start/hp_end logging and the run-HP pool to ladder.py, plus the held-out non-inferiority test (code plus test_ladder only).

Hours 24-48: data scaling finishes. Read it paired by seed index, with r0 alongside r1.
- If job B showed 5% or more top-choice disagreement, queue the boss-only net-leaf two-turn paired screen on both halves (about 5-8 thread-h). On +0.02 or more, prepare the two-turn labelling job for about 20k contested states.
- If job A showed round 0 within 0.01 of r1/r2, set rounds to 0-1 in every later config and say so in the decisions log.
- Queue the hook_rates feature arm (3 seeds, about 15 thread-h) as soon as its spec is built and the fast suites pass.
- Run the HP-lost first check (about 0.3 CPU-h) on 0001's and 0003's pairings.

Keep at least 6 h queued at all times, using the filler list (extra data-scaling seeds, ladder tests).

### Open questions

- Is the round-0 net (heuristic games only) as strong on tight2 as r1/r2? This decides whether self-play rounds stay in the recipe at all.
- Does two-turn net-leaf search at cap 400k choose differently from, and better than, one-turn net search on contested mid-fight elite and boss states? Without that, there is nothing to distil.
- How much of the nets' boss and elite lead is 'not flat' rather than learned skill? Splitting the lead by whether the heuristic was saturated at that decision would tell (lens 2's sat.py joined to per-fight outcomes).
- Does the net under-play or over-play Demon Form? The answer picks between horizon features and composition features.
- Do the data-scaling arms really share game streams by seed index (is data5k-s1's game set a prefix of data20k-s1's)? If yes, the paired read has far more power than the planned unpaired MDE of 0.027.
- What is the paired sd of HP lost per fight at run-realistic HP, and does it rank nets the same way win/loss on tight cells does?
- How large is the reachable ceiling on elites and bosses? The union of five players wins 75-80% against 54-60% for the best single player, but part of that is draw luck. A bounded exact or clairvoyant solve of the smallest elite cells would give an upper bound.
- Is a two-turn search with a policy prior (expand only one-turn's top-k first moves) cheap enough, say 5-10x one-turn, to make depth usable in play on bosses? The existing two-turn result files may already show how often its pick is in one-turn's top 3.
