# Depth pilot (2026-10-30, manager local_10dd1a9a)

Question (big-picture review 2026-10-30, direction 2): does two-turn search
beat one-turn? Before spending 2-3 CPU-hours on the paired test, a pilot on
60 held-out tight2 elite and boss fights (shuffled with seed 0; the
heuristic as evaluator; `bench.LIMIT`; 4 threads; same fights for every
row). Script: `scripts/analysis/depth_pilot.py` (edit the row list to
repeat a row).

| search | won / 60 | s per fight |
|---|---|---|
| one-turn (`sample_k` 0) | 30 | 0.07 |
| one-turn, `sample_k` 4 | 30 | 0.17 |
| two-turn, `sample_k` 4 | 21 | 3.5 |
| two-turn, `sample_k` 1 | 14 | 3.6 |

60 fights is small (a paired difference's SE is roughly 0.06-0.08), but
the order is the point: two-turn search as built *loses* to one-turn, and
loses more with fewer samples.

## Why (from `engine/src/search.rs`)

1. **Each option samples its own draws.** At a chance node too large to
   list, every branch draws its own `sample_k` outcomes from one shared
   RNG stream, so sibling options are scored on different luck. The best
   option is then the max over noisy estimates and favours the lucky one
   (the optimizer's curse). Fewer samples, more noise, worse play: k=1 <
   k=4 < one-turn fits this.
2. **The node cap cuts the tree.** `max_nodes` (50,000, not exposed to
   Python) turns every unexpanded state into a leaf once reached. The tree
   is built depth-first, so options listed later are cut sooner and are
   scored on mid-turn states by the heuristic, which was built for
   end-of-turn states. Two-turn's time per fight is the same for k=1 and
   k=4, which suggests it always runs into the cap.
3. Sampling inside one turn is harmless (one-turn k=4 equals one-turn).

So the review's "depth was ruled out" was likely a measurement of this
noise and truncation, not of depth. The past result can't be read as
"depth doesn't help" either way.

## What it changes

Next item 4 becomes: (a) expose `max_nodes` and a cut counter to Python;
(b) common random numbers: every sibling option sees the same sampled
outcomes (seed each sampled chance node from the turn and the sample
index, not from a shared stream); (c) then the paired two-turn vs
one-turn test on held-out elite and boss cells, reporting cap hits. Cost
note: two-turn is ~50x one-turn per fight at 4 threads, so the paired
test needs a cell subsample (~8 fights per cell over ~200 cells: ~1 h at
6 threads, paired SE ~0.015).

## After the fix (same day, 15:10)

Common random numbers and the cut counter built (`docs/specs/search-crn.md`,
3704a6f, 9564fc0). Rerun on 60 held-out elite and boss fights (the first
spec of each of the first 60 cells, not the shuffled 60 above; heuristic
evaluator, 6 threads; `scripts/analysis/depth_paired.py --per-cell 1
--limit-fights 60`, output `results/depth/pilot-crn.json`):

| search | won / 60 | wall time |
|---|---|---|
| one-turn | 25 | 1 s |
| two-turn, `sample_k` 4, 50,000 nodes | 34 | 80 s |

Paired difference +0.150 (SE 0.066); elite +0.125 (n 56), boss 4/4 vs 2/4.
Cut probe (34 decisions from 6 fights): only 6% of two-turn searches hit the
node cap, mean 7,900 nodes, 0.19 s each. Shared samples make sibling
options reach equal states, which the tree merges, so the tree is far
smaller than with independent samples. That also explains the speed-up
(3.5 s per fight at 4 threads before, ~1.3 s at 6 now).

A pilot, not a result. The full paired test (8 fights per cell, every
elite and boss cell, each half) is queued: jobs 0005 (held-out) and 0006
(train).

## Full paired test (jobs 0007, 0008; read 16:10 by manager run 16:06)

Every held-out and train elite and boss cell, the first 8 specs of each
(1,336 held-out and 1,328 train fights), heuristic evaluator, two-turn
`sample_k` 4 with 50,000 nodes. Outputs `results/depth/paired-held_out.json`
and `paired-train.json`; analysis inline in the manager run (the script's own
summary plus the per-encounter split below).

| half | one-turn | two-turn | paired diff (se) | two-only wins / one-only wins |
|---|---|---|---|---|
| held-out | 0.498 | 0.450 | **-0.048** (0.015) | 170 / 234 |
| train | 0.503 | 0.503 | +0.000 (0.015) | 199 / 199 |

By encounter (diff, se 0.023-0.033 each):

| encounter | held-out | train |
|---|---|---|
| Gremlin Nob | **+0.074** | **+0.077** |
| Lagavulin | -0.051 | +0.045 |
| Slime Boss | -0.049 | -0.025 |
| Three Sentries | **-0.167** | **-0.098** |

**The pilot's +0.150 was its fight mix.** The rerun is deterministic (all 60
pilot fights give the same outcome in the full run, both arms), and 42 of
the pilot's 60 fights were Gremlin Nob, the one encounter where two-turn
really helps. The rest of the field cancels or reverses it.

What the split says:
- **Depth helps where the next turn is decisive and short.** Nob punishes
  Skills (Enrage) and kills fast; seeing his next swing pays, in both halves
  alike (+0.075). Fights one-turn ends in <= 3 turns: +0.08 both halves.
- **It hurts on long fights.** One-turn fights of 7-10 turns: -0.20
  held-out, -0.12 train; over 10 turns -0.26 / -0.11. Three Sentries (the
  longest elite, Dazed piling into the deck) loses in 31 of 42 held-out
  cells, so it is broad, not a few odd cells.
- **Wins look the same.** On fights both arms win, final score and length
  are equal (1.929 vs 1.923 held-out). Two-turn doesn't win "worse"; it
  loses more fights outright.
- The held-out half loses more than train with the same evaluator, so card
  content matters: held-out cards lean harder on the heuristic's blind
  spots at depth. Cut share 13% held-out, 9% train.

Reading: with the heuristic as evaluator, two-turn search doesn't lead by
the plan's 0.02 bar; it fails it in both halves. Two explanations remain
and the queue tests both:
1. **Leaf bias compounds.** The heuristic scores end-of-turn states; two
   turns out its errors (on poison, Dazed, block timing) steer the tree
   more. Test: the same paired runs with a trained net as evaluator (round-2
   retrain, seed 1), jobs 0009 / 0010.
2. **Too few sampled draws on long fights.** `sample_k` 4 over a big,
   Dazed-filled deck may be noise that the max over options amplifies.
   Test: Three Sentries held-out only with `sample_k` 16, job 0011.

If net leaves turn two-turn positive overall (>= 0.02 on either half),
depth is worth an amplifier spec; if only k 16 fixes Sentries, sampling is
the problem; if neither, depth with today's evaluators is out, and the
only measured depth gain is the Nob pattern (worth a per-encounter
selective search later, not now).

## Net leaves, k 16, and the node-cap bias (jobs 0009-0011; read 17:45 by manager run 17:33)

Same fights as the full paired test. Net leaves: seed-check r2 s1
(`results/depth/paired-net-*.json`); k 16: Three Sentries held-out,
heuristic leaves (`paired-sentries-k16.json`).

| run | held-out diff (se) | train diff (se) |
|---|---|---|
| heuristic leaves, k 4 | -0.048 (0.015) | +0.000 (0.015) |
| net leaves, k 4 | -0.010 (0.014) | +0.013 (0.014) |
| Sentries only, heuristic, k 4 | -0.167 (0.030) | -0.098 (0.031) |
| Sentries only, heuristic, **k 16** | **-0.229** (0.031) | - |

By encounter with net leaves (held-out / train): Gremlin Nob +0.030 /
-0.009, Lagavulin +0.119 / +0.074, Three Sentries -0.128 / -0.042, Slime
Boss -0.064 / +0.028. By one-turn fight length (held-out): <= 3 turns
+0.063, 4-6 +0.010, 7-10 -0.098, > 10 -0.260. Net leaves shrink the loss
but don't reach the 0.02 bar on either half.

**More sampled draws made it worse,** which noise can't explain. The
k-16 losses die early: 88 of 234 two-turn Sentries losses end on turn 2,
against 45 of 157 one-turn losses. That pointed at the node cap:
`search.rs` builds the tree depth-first, and once it has 50,000 nodes every
unexpanded state becomes a leaf. The first root options get searched two
turns deep; later ones are cut to **mid-turn-1 states**, scored before the
monsters attack, so they look better than any fully searched option. Search
then picks an option it never finished looking at. A bigger k grows the
tree, so more options are cut: worse with k 16.

Checked on the first decision of the first held-out Sentries cell (k 16):
at cap 50,000 the tree cut 17 states and scored Strike 0.124 (chosen);
the full tree has only 96,502 nodes and scores Strike 0.050 and picks
Defend (0.076). One-turn search almost never reaches the cap (1 cut in
2,202 decisions over all tight2 encounters, both halves; the one was a
Sentries turn), so ordinary play, benchmarks and training are unaffected.

So every two-turn result so far, the pilot included, is measured with a
biased search, and the loss on long fights (bigger decks, more options,
more cuts) is at least partly this bias. Reruns at cap 400,000 are queued
(0016 Sentries k 16; 0017 / 0018 held-out / train elite+boss, heuristic,
k 4). Depth is not dropped until they are read.

A real fix should not depend on the cap being large enough. Candidates:
(a) when a two-turn tree would cut, fall back to one-turn search for that
decision (consistent, cheap, loses depth exactly where trees are big);
(b) expand breadth-first by turn, so the cap only trims turn-2 subtrees and
those leaves are end-of-turn-1 states (still mixes depths across options);
(c) a bigger cap (memory-bound). Pick after the 400k reruns show how often
400k still cuts.

## Cap 400,000 on Sentries (job 0016; read 18:16 by manager run 18:04)

Held-out Sentries cells, heuristic leaves, k 16, 336 paired fights:
one-turn 0.533, two-turn 0.452, **diff -0.080 (se 0.029)**, against -0.229
at cap 50,000 (same fights). The cut probe still cut 9.4% of 64 sampled
decisions (mean 64,648 nodes, ~1 s each). Two-turn took 1,604 s against
one-turn's 27 s (60x).

Reading: the bigger cap removed about two thirds of the Sentries loss, so
the node-cap bias was real and large. Two-turn search still loses here by
~2.8 se, with 9% of decisions still cut; whether the rest is leftover bias
or depth itself with heuristic leaves isn't separable from this run. The
elite+boss reruns (0017 held-out, 0018 train, k 4) decide whether the
fallback fix (option a) is worth building: if they come out near 0 or
positive, build (a) and re-measure; if clearly negative with few cuts,
depth with the heuristic as leaf scorer is out.

## Cap 400,000 on held-out and train elite+boss (jobs 0017, 0018; read 22:10 by manager run 22:08)

Heuristic leaves, k 4, the same 1,336 / 1,328 fights as the 50k runs
(one-turn results identical fight for fight, so only two-turn changed).

| half | cap | all | gremlin_nob | lagavulin | three_sentries | slime_boss | cut share |
|---|---|---|---|---|---|---|---|
| held-out | 50k | -0.048 (0.015) | +0.074 | -0.051 | -0.167 | -0.049 | - |
| held-out | 400k | **+0.016 (0.015)** | +0.101 | -0.060 | -0.062 | +0.088 | 16% |
| train | 50k | +0.000 (0.015) | +0.077 | +0.045 | -0.098 | -0.025 | - |
| train | 400k | **+0.056 (0.014)** | +0.095 | +0.045 | -0.009 | +0.097 | 3% |

(Win-rate diffs two minus one; per-encounter se 0.021-0.033.)

Reading:
- The node-cap bias was most of depth's loss. Every change from 50k to
  400k is where cuts were: Sentries and Slime Boss (many enemies or splits,
  big trees) moved +0.09 to +0.14; Lagavulin and Nob barely moved.
- **Two-turn search with heuristic leaves now beats one-turn by +0.056 on
  train (~4 se)** and is level on held-out (+0.016, ~1 se). It clears the
  0.02 bar on the train half. On bosses it gains +0.09-0.10 on both halves,
  as much as the champion net's held-out boss lead (+0.05) and half its
  train boss lead (learned-play-results "Champion ladder"), so part of the
  nets' boss lead is what one extra turn of lookahead buys.
- What's left negative: held-out Lagavulin (-0.06, ~1.8 se) and held-out
  Sentries (-0.06, ~2 se), where 16% of decisions still cut. Two causes
  remain and aren't separated: leftover cap bias, and max over noisy leaf
  values (prior-art doc `unseen-mechanics.md`).
- Cost: two-turn took 10,677 s / 7,387 s against one-turn's 31 s / 9 s
  (300-800x). Fine as a test-time player or a label source on few states,
  not for self-play at today's speed.

Next (Next 4): play with two Python-side guards, no rebuild needed since
`sts.search` returns `cuts` and option values: (a) fallback, use one-turn's
choice whenever the two-turn tree cut; (b) guarded override, keep one-turn's
choice unless two-turn values another option above it by more than m.

## Fallback and guard players on held-out, cap 400k (jobs 0038, 0039; read 02:20 2026-10-31 by manager run 02:07)

Heuristic leaves, k 4, cap 400k, the same 1,336 held-out elite+boss fights
(one-turn results identical fight for fight in all three runs, checked).
`fallback` plays two-turn's choice except where the tree cut; `guard`
is fallback plus "keep one-turn's choice unless two-turn values another
option more than 0.05 above it".

Two-turn minus one-turn (win rate):

| player | all | gremlin_nob | lagavulin | three_sentries | slime_boss |
|---|---|---|---|---|---|
| plain (0017) | +0.016 (0.015) | +0.101 | -0.060 | -0.062 | +0.088 |
| fallback | **+0.061 (0.014)** | +0.104 | -0.033 | +0.009 | **+0.165** |
| guard m 0.05 | +0.036 (0.009) | +0.086 | +0.006 | +0.030 | +0.021 |

Paired between players on the same fights (se in brackets):

| | all | nob | lagavulin | sentries | slime_boss |
|---|---|---|---|---|---|
| fallback - plain | **+0.044 (0.011)** | +0.003 | +0.027 (0.026) | **+0.071 (0.025)** | **+0.076 (0.022)** |
| guard - fallback | -0.025 (0.012) | -0.018 | +0.039 (0.030) | +0.021 | **-0.143 (0.029)** |

Share of decisions cut / overridden (two-turn's pick differs from
one-turn's): fallback nob 0.8% / 10%, lagavulin 0.6% / 14%, sentries 5.8%
/ 12%, slime boss 8.3% / 11%; guard brings overrides down to 2-5%.

Reading:
- **The node cap was still biasing two-turn search at 400k.** Falling back
  on the 1% of cut decisions gains +0.044 (4 se), all of it where cuts
  are common (Sentries, Slime Boss). With that fixed, two-turn search with
  the *heuristic* as leaf scorer beats one-turn by +0.061 on held-out,
  about as much as plain two-turn did on train (+0.056). Held-out Sentries
  goes from -0.06 to level; the bosses' gain nearly doubles.
- **Noisy max over leaf values is not the main cost.** The margin guard
  trades a little on Lagavulin and Sentries (+0.02-0.04, under 1.5 se) for
  a large loss on Slime Boss (-0.14): there two-turn's better options win
  by small value gaps, and a margin of 0.05 throws them away. A smaller
  margin is not worth a run (expected effect below the ~0.02 bar).
- Lagavulin is the one fight still slightly negative (-0.03, ~1 se);
  not acted on.
- What it changes: the fallback player is *the* two-turn player from now
  on (decisions "Two-turn player: fallback"). It should enter the
  champion ladder, and it is the player the teacher check (Next C)
  compares the nets against. The train half under fallback is unmeasured;
  with 3% cuts on train the expected change is small.

## Net leaves with the fallback player, held-out, cap 400k (job 0044b; read 06:10 2026-10-31 by manager run 02:07)

Champion r2 s1 scores the leaves; two-turn search with the fallback player
(one-turn's choice where the tree was cut) against one-turn search with the
same net, on the same 1336 held-out elite and boss fights as 0038. The
two-turn pass took 7133 s on 6 threads; 4.8% of decisions were cut and
12.7% changed one-turn's choice (overrides).

Two-turn minus one-turn, net leaves: **+0.055 (se 0.013)**; elites +0.048
(0.015), bosses +0.079 (0.028). That is the same size as with heuristic
leaves (+0.061), and the two gains add: on the same fights,

| encounter | heur 1-turn | heur 2-turn | net 1-turn | net 2-turn | net2 - net1 | net2 - heur2 |
|---|---|---|---|---|---|---|
| all | 0.498 | 0.558 | 0.535 | 0.591 | +0.055 (0.013) | +0.032 (0.013) |
| Gremlin Nob | 0.476 | 0.580 | 0.548 | 0.551 | +0.003 (0.018) | -0.030 (0.016) |
| Lagavulin | 0.497 | 0.464 | 0.461 | 0.589 | +0.128 (0.033) | +0.125 (0.032) |
| Slime Boss | 0.485 | 0.649 | 0.576 | 0.655 | +0.079 (0.028) | +0.006 (0.027) |
| Sentries | 0.533 | 0.542 | 0.557 | 0.568 | +0.012 (0.027) | +0.027 (0.027) |

Reading, with care for four encounters read at once:
- Net two-turn is the best player we have on held-out elites and bosses
  (0.591), +0.093 over the heuristic's one-turn play.
- The gains don't split the same way. On Nob, the net's one-turn play
  already gets what depth gives the heuristic, and depth adds nothing more.
  On Lagavulin, depth hurts the heuristic (-0.033) and helps the net
  (+0.128, ~4 se): the net's values seem to see what to do during
  Lagavulin's sleep only when it can look a turn ahead. Slime Boss gains
  from depth with either leaf.
- Compared with the cap-50k net-leaf run (-0.010, 23% cuts), the earlier
  loss was the node-cap bias, not the net.

Read rule (manager.md Running): two-turn net >= +0.02 on a half -> spec
distilling two-turn values into the net. Held-out passes it clearly; the
train half (0057b) is queued and will set how big the gap is in training
fights. Cost note: two-turn play is ~145x one-turn's time here (7133 s vs
49 s), which is why distillation, not two-turn self-play, is the next step.

## Hallways, held-out (job 0057a6h, read 18:10 2026-10-31 by manager run c3a3a6dc)

`depth_paired.py --half held_out --groups hallway --per-cell 2 --policy
fallback --max-nodes 400000`, champion net at the leaves
(`results/depth/paired-net-held_out-hallway-fallback.json`), 886 fights.
Cut probe: 7% of decisions cut, mean 30k nodes.

Two-turn minus one-turn: **+0.025 won (se 0.009)**, score +0.050 (se
0.017). Half the elite/boss gain (+0.055), but hallways are most of a
run's fights. Per encounter (n 74-84 each): three_louse +0.060, looter
+0.053, cultist +0.041, thugs / large_slime +0.036, fungi / lots_of_slimes
+0.024, jaw_worm +0.012, wildlife / small_slimes 0.000, two_louse -0.014
(se 0.024-0.043). Nine of eleven gain or tie; nothing loses beyond 1 se.
Reading: depth's gain isn't confined to the four elite/boss encounters the
review worried about; it is smaller where fights are easy (one-turn already
wins most of what can be won). The train half (0057b) is still queued.

## Where net-leaf depth gains: unseen power cards (read 18:45 2026-10-31 by manager run c3a3a6dc; post hoc)

The held-out elite/boss runs, split by the cards in each fight's deck
(joined back to `tight2.json` by cell and seed). Every held-out deck holds
some held-out-only card, so the split is by card, not novel vs familiar.
Two-turn minus one-turn wins, per-fight se:

| leaves | fights with an unseen power (Demon Form, Metallicize, Rage, +) | without |
|---|---|---|
| champion net (`paired-net-held_out-cap400k-fallback`) | +0.076 (0.017), n 912 | +0.012 (0.023), n 424 |
| heuristic (`paired-held_out-cap400k-fallback-m0`) | +0.050 (0.017) | +0.083 (0.025) |

Per card with net leaves the top gains are Demon Form+ +0.181 (0.041),
Metallicize +0.110, Rage +0.107, Iron Wave+ +0.086, Demon Form / FTL
+0.083; with heuristic leaves Demon Form+ gains only +0.013. Demon Form
fights alone: net +0.125 (0.025) vs +0.024 on the rest; hallways show no
such split (+0.016 vs +0.029).

Reading (a hypothesis, not a result: 20 cards looked at, the split chosen
after seeing them, ~2.2 se): with the net at the leaves, most of depth's
held-out gain comes from fights with an unseen power, which the net is
known to mis-price (Demon Form probe); looking one turn further shows the
payoff the net's values miss. The heuristic prices powers by hand, so its
depth gain doesn't concentrate there. If true, it matters for goal 1:
search is a general repair for mis-priced new mechanics, and distilling
two-turn values would teach exactly the novel cases. Pre-registered check
on fresh fights (job 0057a9a5, held-out `tight_bosses`, Hexaghost and
Guardian, all 1480 fights, 1080 with a power): net-leaf depth gain on
power fights minus no-power fights >= +0.05 holds the hypothesis; <= 0
drops it. MDE for that difference is ~0.08 at this size, so a pass is
strong evidence and a miss between 0 and 0.05 says little.

## Top-3 player vs fallback, held-out, net leaves (job 0057a8z3; read 22:15 2026-10-31 by manager run 5cbfc037)

`depth_paired.py --policy topk --top-k 3`: two-turn search may only pick
among one-turn's top 3 options (fallback on cut trees, as before). Same
args and fights as `paired-net-held_out-cap400k-fallback.json` (one-turn
results are identical fight for fight, so pairing is clean; two-turn's
own sampling still adds noise to both arms).

| slice | n | topk3 - fallback (won) | se | fights that differ |
|---|---|---|---|---|
| all | 1336 | +0.005 | 0.009 | 128 |
| elites | 1008 | +0.015 | 0.010 | 99 |
| Slime Boss | 328 | -0.027 | 0.016 | 29 |
| Nob / Lagavulin / Sentries | 336 each | +0.015 / +0.006 / +0.024 | 0.011 / 0.018 / 0.021 | |

`outside` (two-turn's own best not in one-turn's top 3) is 952 of 28,302
decisions (3.4%), above the 2% floor, so the arms could have differed and
didn't by much. On the 582 fights with any outside decision the diff is
-0.007. Read rule (decisions "Top-3 two-turn player"): within +-0.02 ->
**no change, fallback stays**. The split (elites up, Slime Boss down) is
post hoc and each slice is under 2 se; not acted on. topk vs one-turn:
+0.060 (se 0.012), the same as fallback's +0.055.

## Novelty check on fresh fights: held-out bosses (job 0057a9a5; read 04:20 2026-11-01 by manager run 68e81bce)

The pre-registered check from "Where net-leaf depth gains". `depth_paired.py
--bench tight_bosses --half held_out --groups boss --per-cell 20 --policy
fallback --max-nodes 400000`, champion net at the leaves
(`results/depth/paired-net-held_out-bosses2-fallback.json`), all 1480
fights (74 cells x 20 seeds), none used for the post hoc split. Cut probe
3.9%; 11.1% of decisions overridden; two-turn pass 3512 s at 4 threads.
"Power" = the deck holds Demon Form, Metallicize or Rage (1080 fights, as
pre-registered). The deck is fixed per cell, so se below is clustered by
cell (per-fight se is about 2/3 of it).

| slice | one-turn | two-turn | two - one | power | no power | power - none |
|---|---|---|---|---|---|---|
| all | 0.395 | 0.512 | **+0.118 (0.018)** | +0.144 (0.021), 54 cells | +0.048 (0.033), 20 cells | **+0.096 (0.039)** |
| Hexaghost | 0.447 | 0.520 | +0.073 (0.028) | +0.117 (0.034) | -0.032 (0.032) | +0.149 (0.046) |
| Guardian | 0.342 | 0.504 | +0.162 (0.022) | +0.168 (0.025) | +0.144 (0.046) | +0.023 (0.052) |

Demon Form fights alone: +0.207 (per-fight se 0.024, n 460) vs +0.077 on
the rest.

Rule: power minus no-power >= +0.05 holds the hypothesis. **+0.096 (se
0.039): it holds**, about 2.5 se, on fresh fights. Caveats, read with it:
- It holds on Hexaghost only (+0.149); on the Guardian depth gains about
  as much without a power (+0.144) as with one (+0.168). The pooled pass
  leans on one boss.
- Only 20 no-power cells; "power" decks also differ in other cards
  (Carnage, Uppercut, Wild Strike decks gain more too), so the slice is
  "decks with an unseen power", not the power cards themselves. Demon Form's
  +0.207 is the clearest single signal and matches the probe (the net
  mis-prices it).
- Bigger than the slice: net two-turn beats net one-turn by +0.118 on
  held-out bosses, twice the tight2 elite/boss gain (+0.055). One-turn
  play is weak here (0.395), so there is more to repair.

Reading: depth repairs the net's mis-pricing of unseen powers, at least
Demon Form on Hexaghost, and helps broadly on held-out bosses anyway. For
goal 1 this makes search part of the answer to new mechanics: the
two-turn player is the one to measure new content with.

## Net leaves, train half, elites and bosses (job 0057b; read 04:20 2026-11-01 by manager run 68e81bce)

`depth_paired.py --half train --groups elite,boss --per-cell 4 --policy
fallback --max-nodes 400000`, champion net at the leaves
(`results/depth/paired-net-train-cap400k-fallback-pc4.json`), 664 fights
(166 cells). 12.8% overrides. se clustered by cell.

| encounter | one-turn | two-turn | two - one | held-out (0044b) |
|---|---|---|---|---|
| all | 0.601 | 0.636 | **+0.035 (0.020)** | +0.055 (0.013) |
| Gremlin Nob | 0.512 | 0.530 | +0.018 (0.027) | +0.003 |
| Lagavulin | 0.589 | 0.661 | +0.071 (0.057) | +0.128 |
| Slime Boss | 0.700 | 0.756 | +0.056 (0.032) | +0.079 |
| Sentries | 0.607 | 0.601 | -0.006 (0.039) | +0.012 |

Depth helps the net on train fights too, but by about two thirds of the
held-out gain (+0.035 vs +0.055; difference inside 1 se), with the same
pattern per encounter (Lagavulin and Slime Boss gain, Nob and Sentries
don't). Train decks hold no unseen powers, so there is no novelty slice
here; the smaller train gain fits the reading above (part of the held-out
gain is repair of unseen content) without proving it. Passes the old
distillation bar (+0.02) at ~1.7 se; distillation is closed anyway.
