# Random-world bench (lane `random-world-bench`)

Charter: fact `lane/random-world-bench`. A world is k novel items in one
fight; the question is whether their costs to the net (HP lost per elite
fight beyond the heuristic, against the unmodified fight on the same
starts) add up or compound.

## Step 1: sizing from the generated-enemies table (no CPU, 2026-11-09)

Script: `scripts/analysis/rwb_sizing.py` (reads
`results/mutate/gen-enemies-b1.json`: 24 generated pack mechanics on the
675 official Act 1 elite starts x 16 seeds, heuristic and the 10-29 net
@hpb0.01@tsl1 one turn deep, every mechanic on every living monster).
Novelty per start and seed: the net's HP-lost change from the parent minus
the heuristic's. These numbers carry no stat-only ladder control, so they
sit above `measurement/gen-enemies@table24`'s (mean +1.58 here against
+0.32 there); that control is not part of this lane's measure.

**Spread of single-item costs (cost(1)).** Over all 24 mechanics: mean
+1.58 HP, sd between mechanics 2.76. Without the three where the heuristic
collapses (OppCard-Weak, OppCard-Vulnerable, AttackLoss-Vulnerable; -6 to
-11 HP on Lagavulin and Sentries, the heuristic's failure, not the net's):
mean +2.32, sd 1.77 over 21. Within a world, 50 elite starts x 4 seeds
measure one item's cost with an se of about 0.73 HP (median over
mechanics; at most 1.55).

**The charter's literal read can't decide.** Comparing the k-item worlds'
mean cost against 1.5 x k x the k=1 worlds' mean carries the spread
between items twice: at 20-40 worlds per k, the additive expectation sits
only 0.7-2.4 se from the 1.5x line (21-item pool: 1.5-2.4 se; all 24:
0.7-1.1 se). Neither branch of the stop rule could be reached.

**A paired read can.** Every single item's cost is already measured on
the same starts and seeds (the bench's seeds are fixed per start; a world
played with seeds 1-4 of a start pairs with the singles' seeds 1-4). So
each world's additive prediction is the sum of its own items' single
costs on its own starts, S_w, and the read is g = mean over worlds of
(cost_w - 1.5 S_w): go if above 0 at 2 se, additive if below. The
spread between items then enters only as 0.25 x k x sd^2. Additive's
expected distance from the line, in se (noise taken as sqrt(1 + k) x
0.73, conservative):

| k | 21-item pool, 20 worlds | 21 items, 40 worlds | all 24, 20 worlds |
|---|---|---|---|
| 2 | 5.3 | 7.5 | 2.7 |
| 4 | 7.9 | 11.1 | 3.9 |
| 8 | 11.5 | 16.2 | 5.7 |

20 worlds per k decide k 2-8 on the 21-item pool. The k=0 column (the
parent) and the k=1 column (the singles) need no new games: both are in
the file for all 675 starts x 16 seeds.

**Saturation.** HP lost caps at the start HP (mean 64.9; the parent fight
costs the net 14.6 and it wins 0.984; with one mechanic it wins 0.83 at worst,
0.92 at the median). Summing the singles' raw costs (net, not beyond the heuristic):
at k 2, 12% of starts are predicted past their start HP; at k 4, 37%; at
k 8, 77%. Where both players die the cost difference is squeezed to the
cap, which reads as additive or less whatever the truth. So the world's
starts are chosen among those the singles predict to survive (parent loss
+ summed raw single costs below the start HP): a choice made from data
measured before the world is played, so it doesn't bias the world's own
cost, but it does tilt k 8 toward easy starts (high HP, low parent loss;
about a quarter of them). Deaths per world are reported beside the cost.

**CPU.** Job 0470 played about 367k games in 8.7 thread-h (about 0.085
thread-s a game). A world at 50 starts x 4 seeds x 2 players is 400 games,
about 35 thread-s; the pilot (k 2, 4, 8, 20 worlds each) about 0.6
thread-h; 40 worlds per k with an ids-only twin about 2.5 thread-h. The
cap (9 cpu-h) holds the grid and the optional adapted column.

**What this changes in the plan** (decisions "random-world-bench: paired
read on the singles"): the pilot plays only stacked worlds (k 2, 4, 8),
read paired against the singles already measured; the enemy pool is the
21 mechanics, the three collapse mechanics a side read; card items join
once their singles are measured on the same starts (the card variants of
`mutate_cards.py` swap a deck card, so a card item exists only on starts
whose deck holds its parent, and `results/mutate/cards-a.json` used other
seeds).

## Step 3: pilot read (jobs 0729-0731, 2026-11-09)

Jobs: 0729 replay check (0 differences on 5 starts x 4 seeds, parent and
GE-TurnStart-Damage, both players: the pairing holds); 0730 play (20 main
worlds of the 21 mechanics + 10 side worlds of 24, k 2/4/8, 50 starts x 4
seeds, `results/mutate/rw-pilot.json`; 8.6 min at 3 threads, a quarter of
its 35-minute estimate: 36k one-turn games at about 0.04 thread-s each,
half the 0.085 thread-s step 1 took from job 0470); 0731 read
(`results/mutate/rw-pilot-table.md`; no `--check` was set on it).

The read job's table (mean over worlds, se in brackets):

| pool | k | worlds | cost | S (sum of singles) | cost - S | g = cost - 1.5 S | deaths net / heur / pred |
|---|---|---|---|---|---|---|---|
| main | 2 | 20 | +4.75 (0.63) | +4.81 (0.56) | -0.06 (0.38) | -2.46 (0.49) | 0.15 / 0.09 / 0.08 |
| main | 4 | 20 | +5.57 (0.62) | +6.10 (0.63) | -0.53 (0.75) | -3.58 (0.97) | 0.33 / 0.22 / 0.14 |
| main | 8 | 20 | +3.44 (0.49) | +4.08 (0.58) | -0.64 (0.55) | -2.68 (0.76) | 0.78 / 0.71 / 0.24 |
| side | 2 | 10 | +4.61 (0.72) | +4.81 (0.55) | -0.20 (0.58) | -2.61 (0.68) | 0.16 / 0.11 / 0.07 |
| side | 4 | 10 | +3.35 (0.85) | +5.26 (1.93) | -1.91 (1.15) | -4.54 (2.10) | 0.29 / 0.27 / 0.15 |
| side | 8 | 10 | +4.14 (1.41) | +2.55 (1.89) | +1.59 (0.88) | +0.31 (1.69) | 0.63 / 0.54 / 0.26 |

Its verdict, **additive** on the main pool, **does not stand**: the HP cap
decides it. The singles-predict-survival filter chose starts, but the
worlds are harder than their singles summed, so at k 8 the net dies in
78% of fights (24% predicted) and only 15% of start-seeds have both
players alive (58% at k 4, 80% at k 2). A dead fight's HP lost is capped
at the start HP, while S, the uncapped sum, isn't: cost falls from k 4 to
k 8 because both players hit the cap. Dig (`scripts/analysis/rwb_pilot_dig.py`,
main pool):

| k | net raw loss: world / summed singles | heuristic: world / summed | cost - capped S | g against capped S (z) | both alive, cost - S |
|---|---|---|---|---|---|
| 2 | +21.3 / +19.5 | +16.6 / +14.7 | +0.37 (0.34) | -1.81 (0.38), -4.7 | +0.44 (0.24) |
| 4 | +35.9 / +30.7 | +30.3 / +24.6 | +1.10 (0.67) | -1.13 (0.80), -1.4 | +1.39 (0.64) |
| 8 | +58.2 / +44.8 | +54.8 / +40.7 | +2.08 (0.54) | +1.40 (0.70), +2.0 | +5.73 (2.19) |

(Capped S: each player's per-seed predicted loss capped at the start HP,
then net minus heuristic. "Both alive": start-seeds where both players
win and neither prediction reaches the cap, a selected subset.)

Why, and what it says:
- **Raw difficulty compounds, for both players.** At k 4 a world costs
  each player about 5-6 HP more than its singles summed, at k 8 about 13-14
  HP (+30%), and deaths run 2-3x the prediction. Mechanics stacked in one
  fight are worse than their sum, for the heuristic as much as for the net.
- **The net's cost beyond the heuristic is undecided at k 4 and 8.** At
  k 2 it adds up (interaction +0.4 at most, g -4.7 se). At k 4 and 8 the
  uncapped read biases toward additive (the cap squeezes cost, not S) and
  the capped read biases toward go (capping a per-seed sum of k noisy
  singles cuts more of the prediction than the world's single game, so
  capped S runs low); the truth lies between. Against capped S, main k 8
  sits at exactly the go bar (z +2.0) and side k 8 at +3.0: a lead toward
  compounding, not a result.
- So the pilot gives **open**, not additive: k 2 additive; at k 4 and 8 the
  measure saturates. Charter step 4 runs (the pilot reads a slope: raw
  costs compound, and the novelty interaction rises 0.4 -> 1.1 -> 2.1 with
  k against the capped null), but not on this design: it needs worlds where
  the cap doesn't bind. Picking starts with more headroom doesn't get
  there (prediction under 0.8 x start HP keeps a median of 60 of 675 starts at
  k 8, minimum 28, and the worlds exceed their prediction by 13 HP).

## Step 4: worlds in no-death mode (jobs 0739-0740, 2026-11-09)

Jobs: 0739 `nd-play` (parent, 24 singles, 40 main worlds of 21 mechanics
and 10 side worlds of 24 at k 2/4/8; 50 shared elite starts x 4 seeds,
both players, no-death mode; `results/mutate/rw-nodeath.json`; 65 min at
3 threads against a 30-minute estimate: hopeless fights run to the
50-turn limit); 0740 `nd-read --check` (`results/mutate/rw-nodeath-table.md`).

The read job printed **go** at huge margins (main k 8: cost +1978 HP
beyond the heuristic, ratio 59), and that **is not the result**. In
no-death mode a fight the player can't win goes on until turn 50 while
the monsters scale, so HP lost has no ceiling: the net's raw loss at k 8
averages 2932 HP (summed singles 101) and 46% of its k 8 games end at the
turn limit. The uncapped mean is a measure of those runaway fights, not
of what a fight costs in play, where HP lost stops at the start HP.

Read with HP lost bounded per game (`scripts/analysis/rwb_nodeath_caps.py`;
main pool; S = summed singles, S cap = each player's parent + summed
singles bounded the same way, then net minus heuristic; z of g = cost -
1.5 x the null):

| bound | k | cost | S | S cap | z (S) | z (S cap) |
|---|---|---|---|---|---|---|
| start HP | 2 | +5.56 (0.33) | +6.98 | +5.79 | -14.3 | -15.1 |
| start HP | 4 | +6.38 (0.20) | +13.86 | +7.42 | -19.6 | -16.1 |
| start HP | 8 | +5.36 (0.17) | +27.40 | +8.14 | -37.2 | -22.5 |
| 150 HP | 2 | +5.50 (0.63) | +6.52 | +6.68 | -10.1 | -9.7 |
| 150 HP | 4 | +6.50 (0.65) | +12.76 | +12.24 | -16.4 | -16.8 |
| 150 HP | 8 | +10.24 (0.74) | +25.53 | +18.55 | -22.8 | -21.1 |

(Bounds start HP + 30 and 100 lie between; the side pool reads the same
way, z -1.4 to -14.) The parent fight costs the net 20.2 HP and the
heuristic 24.2 in no-death mode (start HP mean 63).

Why, and what it says:
- **The net's handicap on novel enemies doesn't compound; it barely
  grows.** Its cost beyond the heuristic is about +5.5 HP at k 2, +6.5 at
  k 4 and +5-10 at k 8, while the singles summed grow with k. Every bound
  and both nulls put g far below zero at every k: by the charter's stop
  rule, **additive** (less than additive). The net loses to novelty about
  once per fight, not once per item: stacked mechanics interfere (the
  fight is lost or hard either way) rather than multiply the net's
  mistakes.
- **Raw difficulty compounds, for both players** (pilot, Step 3): worlds
  are harder than their parts, but equally so for the heuristic, which
  sees every mechanic through the same rules, and the net.
- **One sign worth keeping:** at k 8 the net reaches the turn limit more
  often than the heuristic (0.46 against 0.35; k 4 0.08 against 0.07):
  in hopeless no-death fights it stalls more. The 150-HP bound picks this
  up (k 8 cost +10.2 against +5.4 at the start-HP bound). It concerns
  fights both players lose in real play.
- So goal 1's random-content cost, for generated enemy mechanics on the
  official elites, one turn deep, is at most the sum of the per-mechanic
  costs: the per-mechanic benches and bursts give an upper bound for
  random worlds. Not covered: card items, bosses, two turns deep, an
  adapted net (charter step 5).
