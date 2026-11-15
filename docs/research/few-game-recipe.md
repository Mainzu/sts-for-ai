# few-game-recipe: a fine-tune recipe under which 33 games adapt

Lane `few-game-recipe` (charter: `kb get lane/few-game-recipe`; opened in
docs/decisions.md "Lane few-game-recipe opened").

## How it moves goal 1, and how we'll know

Goal 1's number is how few games a net needs to adapt to new content
(`measurement/adaptation-curve`, about 100 games today). At 33 games every
burst of gac-alw33 (docs/research/gen-adapted-column.md, "Step 3 read:
family gac-alw33") kept its epoch-1 net: validation MSE rose from the
second epoch on (job 0500's log: 0.1701, 0.1759, 0.1823, 0.1865, stopped
at patience 3), so the default step overshoots the 236 new states. If a
smaller step (lr at a third) or a larger share of new states per batch
(0.8) lets 33 games cut AttackLoss-Weak's cost by half, the games-to-adapt
number drops about threefold. We'll know from the family table against
gac-alw33's default arms on the same starts.

## Step 1 plan (family gfr-33, 2026-11-08)

`configs/families/gfr-33.json`: gac-alw33's configs (same games, game seed
61, training seeds 1-3) with one key changed each:
- `lr3`: `lr` 3.33e-4 (train.LR / 3), share 0.5;
- `sh8`: `share` 0.8, lr 1e-3;
for the net (`@hpb0.01@tsl1`) and heuristic teachers: 4 arms x 3 seeds,
12 bursts and 12 bench reads (gac-alw33's read: 1000 starts x 4 seeds,
elites, GE-AttackLoss-Weak against c-hp1.25-str1), then the table.

Burst `mem_gb` 1.5 instead of gac-alw33's 3.0: its bursts ran 30 seconds
with no recorded peak, and its reads peaked at 0.98-1.58 GB; 1.5 lets them
start in the free memory (2.5 GB). Expected cost about 3.2
thread-hours (gac-alw33: 0.8 per arm), under the cap of 4.

Read rule (the charter's stop rule): the zero-shot cost is +6.03 HP; the
default cuts are net-g33 +1.20 (se nets 0.05; per net +1.14, +1.17,
+1.29), heur-g33 +1.84 (0.08; +1.77, +1.99, +1.75), parent change -0.24
and -0.26 (results/families/gac-alw33.json). For each recipe arm, the
difference from its teacher's default arm over the three nets, se =
sqrt(se_a^2 + se_b^2) over nets.
- **go:** a recipe cuts 3.01 HP or more (half the cost) for either teacher,
  beats that teacher's default by 2 se, and its parent change is no more
  than 0.5 HP worse than the default arm's.
- **fail:** no recipe beats its default by 2 se.
- **between** otherwise: report the cuts, no follow-up.
Also read each burst's validation curve (which epoch was kept) and the
thread-hours.

## Step 1 interim: net-lr3 seed 1 (jobs 0602-0603, 2026-11-08)

One net, a lead only. The burst (0602, 30 s, peak 0.33 GB) still kept its
epoch-1 net: validation MSE 0.1740, 0.1754, 0.1788, 0.1826, stopped at
patience 3 (seed 2, 0604: 0.1738, 0.1740, 0.1768, 0.1803). Against the
default at seed 1 (0494: 0.1826, 0.2039, 0.2115, 0.2019) the curve starts
lower and rises more slowly, but early stopping still ends after one pass.
Its read (0603, peak 1.0 GB): AttackLoss-Weak cut +0.44 (se starts 0.18),
against the default net-g33 seed 1's +1.14; parent change -0.12.

Why, as a guess to check on the other seeds: with the stop after one epoch
in both recipes, lr/3 moves the net about a third as far, so it learns less
of the mechanic; the lower validation MSE is closeness to the parent, not
learning. If seeds 2-3 agree, lr3 is a fail for the net teacher, and the
recipe question becomes the stopping rule (more epochs at lr/3 with
patience) rather than the step size.

## Step 1 read: net teacher, both recipes (jobs 0602-0613, 2026-11-08)

`family.py table configs/families/gfr-33.json` (not written; the table job
0626 writes it once the heuristic arms are in), against gac-alw33's default
net-g33 arm, +1.20 (se nets 0.05):

| arm | cut (se starts / se nets) | share of +6.03 | per net | parent change | thread-h |
|---|---|---|---|---|---|
| net-lr3 | +0.41 (0.10 / 0.09) | 0.07 | +0.44, +0.24, +0.54 | -0.13 | 0.8 |
| net-sh8 | +4.77 (0.22 / 0.68) | 0.79 | +4.24, +6.11, +3.95 | -0.41 | 0.8 |

- **lr3 fails for the net teacher:** -0.79 below the default, all three
  seeds below every default seed. All three bursts kept epoch 1 (validation
  MSE rises from epoch 2). The guess from the interim holds: early stopping
  still ends after one pass, and a third of the step size moves the net a
  third as far.
- **sh8 meets go for the net teacher:** +3.57 over the default (se 0.68,
  about 5 se); the cut is about four times the
  default's, over half the zero-shot cost, many se above the default, and
  the parent change is better than the default's (-0.24), not worse.
  Two of its bursts got past epoch 1 (best validation at epoch 2, 0.1724,
  and epoch 4, 0.1712; seed 3 kept epoch 1, 0.1744). Why (corrected
  2026-11-08 from `train.replay_batches`): `share` is the replay share, so
  sh8 batches hold 20% new states, not 50%. An epoch still shows every new
  state once, but in 2.5 times as many gradient steps at the same lr, each
  padded with replay. So the 33-game default was under-trained (too few
  steps), not over-stepped: lr/3, the fix for overshoot, cut less, and
  more steps with replay as the anchor cut four times as much, even in the
  one burst that kept epoch 1 (+3.95). This contradicts the candidate's
  mechanism (the first pass overshoots); the replay-dilution half of it
  holds.
- **Checked against a fake pass:** the cut is mechanic gain minus control
  gain (c-hp1.25-str1, same encounters), so forgetting on the control would
  inflate it. It doesn't: per encounter the sh8 bursts gain on the control
  too (lagavulin +1.0 to +1.5, three_sentries +1.4 to +2.4, against the
  default's +0.9 and +1.1 to +1.5), and the mechanic gain carries the cut
  (lagavulin +6.1 to +7.0, three_sentries +5.0 to +8.6, against the
  default's +2.5 to +2.8 and +1.8 to +2.3). Both encounters agree, and the
  parent rows improve (+0.2 to +0.5 HP less lost per fight than zero-shot).
- **Limits of the read:** one mechanic (AttackLoss-Weak), two elites, the
  burst's own encounters (in-distribution, as in gac-alw33); share 0.8 was
  one point, so the best share is unknown (0.9 gives 5 times the default's
  steps per pass; share 1.0 is no new states at all). The same steps might
  also come from more epochs or smaller batches at share 0.5: the read does
  not separate step count from replay anchoring. The heuristic teacher's arms (0614-0625) are still to
  run; they say whether the effect holds across teachers.

What it changes: the 33-game "one epoch is all a burst can use" finding
(docs/research/gen-adapted-column.md) was a property of share 0.5, not of
33 games. The goal-1 number (games to adapt) is recipe-bound: the
adaptation curve measured at share 0.5 overstates the games needed.

## Step 1 result: both teachers (table 0626, 2026-11-08)

`results/families/gfr-33.json` (job 0626), against gac-alw33's default
33-game arms (net-g33 +1.20, se nets 0.05, parent change -0.24; heur-g33
+1.84, 0.08, -0.26). Parent change is the burst's HP lost on the unchanged
fights minus zero-shot's: negative is better.

| arm | cut (se starts / se nets) | share of +6.03 | per net | vs default (se) | parent change | thread-h |
|---|---|---|---|---|---|---|
| net-lr3 | +0.41 (0.10 / 0.09) | 0.07 | +0.44, +0.24, +0.54 | -0.79 (0.10) | -0.13 | 0.8 |
| net-sh8 | +4.77 (0.22 / 0.68) | 0.79 | +4.24, +6.11, +3.95 | +3.57 (0.68) | -0.41 | 0.8 |
| heur-lr3 | +1.15 (0.11 / 0.03) | 0.19 | +1.18, +1.19, +1.08 | -0.69 (0.09) | -0.23 | 0.8 |
| heur-sh8 | +3.13 (0.21 / 0.10) | 0.52 | +3.00, +3.06, +3.32 | +1.29 (0.13) | +0.31 | 1.1 |

**Verdict: go**, through net-sh8: a cut of 0.79 of the cost (>= 0.5),
+3.57 over its default at about 5 se, parent change 0.17 better than the
default's. heur-sh8 also cuts over half the cost and beats its default by
about 10 se, but its parent change is 0.57 HP worse than the default's,
just over the 0.5 guard: with the heuristic's games, the extra steps cost
some of the parent. Its seed-1 burst ran 18 epochs (best at 15,
validation still falling to 0.1668), the others stopped at epoch 1
(validation rising): the heuristic's games carry less signal for the
net's value targets, so more steps also means more drift.

lr/3 lost for both teachers (all six nets below every default net), so
the step-count reading above holds across teachers: the 33-game default
is under-trained, and replay share is the knob that adds steps while
holding the parent.

Cost: 3.5 thread-hours over 24 jobs (table), cap 4.

What it changes for goal 1: games to adapt (`measurement/adaptation-curve`,
about 100 games at share 0.5) was measured with a recipe that under-trains
small sets. At share 0.8, 33 net-teacher games remove 0.79 of the
mechanic's cost, against 0.20 for the 33-game default and 1.05 for the
99-game default (+6.36, `measurement/gen-adapted@alw-g99`): the recipe
closes about two thirds of the gap ((0.79 - 0.20) / (1.05 - 0.20)) between 33 and 99 games. The
curve should be re-measured at share 0.8 (and 0.9) at 11, 33 and 99 games
before "about 100 games" is quoted again.
