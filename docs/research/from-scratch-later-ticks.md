# Lane from-scratch-later-ticks

Charter: `lane/from-scratch-later-ticks` (decisions "Lane
from-scratch-later-ticks opened"). Question: what let the all-content twins
learn Demon Form past its first tick (+3.30 (0.95) HP @tsl1 on Demon Form
decks, `measurement/pack-net-twin@one-turn`): Demon Form in the training
pool, the game count, or the start (from scratch against a trained net).

## Step 1b: Demon Form's exposure in the twins' training data (read 2026-11-10 16:40, lanes d39a52bc)

Method: `scripts/analysis/power_exposure.py --power DemonForm --card "Demon
Form"` (hallway fights now counted too) on the first 1000 games per group of
each twin's round-0 dataset (40k per group) and all of its round-1 dataset;
outputs `results/power_exposure/fslt-<dataset>.json` (MAIN). The states are
drawn with `selfplay.sample_states` and the dataset's `sample_seed`, but
without the `curriculum` labels the learn uses, so the shares are close to
the trained rows, not exact (the bursts' count was exact).

| dataset | Demon Form decks (of games) | held, all | hallway | elite | boss | played in DF games |
|---|---|---|---|---|---|---|
| allcontent40k-s1 r0 (7def7a8c9cc6) | 726 / 3000 | 31.8% | 7.7% | 33.9% | 58.6% | 43.5% |
| allcontent40k-s1 r1 (a2a90271c9c6) | 767 / 3144 | 36.3% | 5.3% | 41.8% | 60.1% | 50.1% |
| allcontent40k-s101 r0 (3fb9b7e51fe2) | 672 / 3000 | 32.1% | 7.6% | 34.9% | 54.1% | 44.5% |
| allcontent40k-s101 r1 (2ab8ece2b9d4) | 755 / 3144 | 31.1% | 2.4% | 35.1% | 58.6% | 40.9% |
| data40k-s1 r0 (e4a48fca433d, 200 per group) | 0 / 600 | - | | | | |

Beside the bursts (`measurement/growth-exposure@ycards-step2`, elites and
bosses only, half the rows from the replay pool): net-g1600 8.2%, two-g400
32.5%, heur-g400 51.9%.

What it says: on Demon Form decks the twins held the power about as often
as two-g400 did and less often than heur-g400 (32% against 33% and 52%).
Exposure share is not what differs. What differs is volume: about 24% of
the twins' 120k round-0 games hold Demon Form, about 29k games, against at
most 1.6k in a burst, and from scratch every row is new to the net. The
data40k twins never see the card (deck pool: train half), which step 1
needs.

## Step 1 (0798-0801): the pool, not the recipe; branch pool (read 2026-11-10 17:00, lanes d39a52bc)

Jobs 0798-0801 (pin 679a88c): `data40k` s1 and s101 round 1 (the twins'
configs without `deck_pool: all`; `bosses` differ too) @hpb0.01@tsl1 on
both cell books, sequences 0-999. `scripts/analysis/cards_by_half.py
--later-ticks` (strata from the 10-29 net's file; twins minus data40k
paired seed by seed; se over sequences, se over nets):

| comparison | stratum | n | end-HP | clears |
|---|---|---|---|---|
| data40k minus 10-29 | train | 500 | -0.42 (0.42, 0.33) | -0.016 (0.013) |
| data40k minus 10-29 | other held-out | 326 | -1.70 (0.53, 0.61) | -0.035 (0.013) |
| data40k minus 10-29 | held-out Demon Form | 174 | -1.26 (0.84, 0.51) | +0.003 (0.023) |
| twins minus 10-29 | train | 500 | +0.56 (0.43, 0.09) | -0.009 (0.014) |
| twins minus 10-29 | other held-out | 326 | -0.04 (0.60, 0.17) | -0.020 (0.013) |
| twins minus 10-29 | held-out Demon Form | 174 | +3.30 (0.95, 0.35) | +0.034 (0.021) |
| twins minus data40k | train | 500 | +0.98 (0.40, 0.42) | +0.007 (0.011) |
| twins minus data40k | other held-out | 326 | +1.66 (0.58, 0.44) | +0.015 (0.012) |
| twins minus data40k | held-out Demon Form | 174 | **+4.56 (0.78, 0.86)** | +0.032 (0.014) |

By seed, Demon Form decks: twins minus data40k +5.42 (1.11) / +3.70
(0.97); data40k minus 10-29 -1.77 (0.97) / -0.74 (0.96). The twins' row
reproduces twin-tsl1's (`docs/research/pns-probes.md`) to the digit, a
check that the strata and files line up.

By the charter's rule: **pool**. Twins minus data40k on Demon Form decks is
5.3 se above zero (the larger se, over nets), and data40k's Demon Form
decks sit within 2 se of the 10-29 net (-1.5 se). The one-round from-scratch
recipe without the card bought nothing on Demon Form decks; having the
card in the pool bought +4.6 HP there.

Read sceptically:
- The pool also bought +1.66 (2.9 se over sequences) on the other held-out
  decks and +0.98 on train decks against data40k. The Demon Form part is
  what lies beyond that: about +2.9 HP over the other held-out decks.
  Against the 10-29 net the twins are level outside Demon Form, so the
  general gain mostly makes up the one-round recipe's deficit (data40k
  -1.70 on other held-out).
- The configs also differ in `bosses` (the twins fight Hexaghost and the
  Guardian in the boss group). It is a confound for the general gain more
  than for Demon Form, whose decks lift most where fights last longest
  (boss exposure 54-60%, step 1b).
- Two seeds; their Demon Form gaps agree in sign and size (+5.4, +3.7).

What it changes: step 2 runs as written. The dose curve asks how many of
the 40k games with the card in the pool are needed: allcontent5k-s1 and
allcontent20k-s1 round 1, each paired against data5k-s1 / data20k-s1 round
1 (0805-0808).

## Step 2 in progress (2026-11-10 20:20, lanes a6e31c55)

- 0812 (allcontent5k-s1) finished in 15 min (estimate 25), peak 2.87 GB
  (allcontent40k peaked 5.9 GB): `runs/2026-11-10-allcontent5k-s1-r1-228ae95`.
  Its two cell-book reads are 0823 (sequences 0-499) and 0824 (`--first
  500`), the same commands as the twin reads 0805/0806.
- 0813 (allcontent20k-s1) runs; its reads go in when it ends.

## Step 2, 5k dose (0823-0824 against 0805-0806): go (read 2026-11-10 21:50, lanes 92715df6)

`scripts/analysis/cards_by_half.py --later-ticks-dose` (strata from the
10-29 net @tsl1; arm minus twin paired by sequence; one seed, so se over
sequences only). Cell books, sequences 0-999:

| comparison | stratum | n | end-HP (se) | clears (se) |
|---|---|---|---|---|
| allcontent5k minus data5k | train | 500 | -0.68 (0.51) | -0.008 (0.016) |
| allcontent5k minus data5k | other held-out | 326 | -1.06 (0.76) | -0.061 (0.021) |
| allcontent5k minus data5k | held-out Demon Form | 174 | **+7.34 (1.35)** | +0.086 (0.032) |
| allcontent5k minus 10-29 | train | 500 | -4.20 (0.57) | -0.082 (0.017) |
| allcontent5k minus 10-29 | other held-out | 326 | -4.95 (0.77) | -0.098 (0.019) |
| allcontent5k minus 10-29 | held-out Demon Form | 174 | -3.01 (1.23) | -0.029 (0.031) |
| data5k minus 10-29 | train | 500 | -3.52 (0.49) | -0.074 (0.016) |
| data5k minus 10-29 | other held-out | 326 | -3.89 (0.64) | -0.037 (0.016) |
| data5k minus 10-29 | held-out Demon Form | 174 | -10.36 (1.23) | -0.115 (0.028) |

By the step-2 rule: **go at 5k** (Demon Form decks 5.4 se above the twin;
train -0.68, inside -0.9). The stop rule's go branch: the smallest dose
went, so step 3 runs at 5k whatever the 20k arm (0830-0831) shows; the 20k
read still fills in the curve.

Read sceptically:
- Most of the +7.3 is the twin's collapse, not the arm's lead. Measured
  against each net's own train stratum (both against the 10-29 net), the
  Demon Form decks sit at +1.2 HP for the arm and -6.8 for the twin. At 40k
  (step 1) the same numbers were +2.7 for the twins and -0.8 for data40k.
  So a net that never saw the card misplays Demon Form decks badly when it
  is weak, and less as it gets stronger; a net that saw it plays them a
  little better than its other decks at both doses. The "later ticks
  learned" part is the +1.2 to +2.7, the rest is avoiding the unseen-card
  loss (fact `cause/unseen-cards-half-edge`).
- Other held-out clears are -0.061 (2.9 se) against the twin: the arm loses
  clears on the held-out decks without Demon Form. HP there is -1.06 (1.4
  se). A guard to watch at 20k, not in the rule.
- One seed; step 1's two seeds agreed, but a single-seed pass is a lead.
- Both 5k nets are 3.5-5 HP below the 10-29 net everywhere: the dose
  question is about the gap to the twin, not about a usable player.

What it changes: step 3 (count or start) runs now at 5k: three bursts on
the 10-29 net with the ycards-net-g1600 recipe at 5000 games per group on
held-out decks (`configs/families/fslt-step3.json`). About 35% of held-out
decks hold Demon Form, so about 3.5k of the 10k burst games do, near
allcontent5k's share of its 15k (about 24%, step 1b). Pass rule as the
ycards bursts': Demon Form stratum @tsl1 2 se above the 10-29 net @tsl1
over three seeds, train HP within -0.9 and clears within -0.04. A pass
says the count was what mattered (a warm net learns later ticks from as
many games); a fail says the start (from scratch) did, and shrink-and-
perturb is the next candidate. Note the burst trains half its rows on the
replay pool, so it sees half the new rows per game the from-scratch arm
did; a fail at this dose is read with that in mind.

## Step 2, 20k dose (0830-0831 against 0807-0808): go, curve filled (read 2026-11-10 23:50, lanes 72a6bada)

Same read (`cards_by_half.py --later-ticks-dose`), cell books 0-999, one
seed; allcontent20k-s1 (0813, 32 min against a 60-minute estimate, peak
3.9 GB) against its twin data20k-s1:

| comparison | stratum | n | end-HP (se) | clears (se) |
|---|---|---|---|---|
| allcontent20k minus data20k | train | 500 | +1.08 (0.51) | +0.020 (0.015) |
| allcontent20k minus data20k | other held-out | 326 | +1.29 (0.72) | +0.028 (0.016) |
| allcontent20k minus data20k | held-out Demon Form | 174 | **+2.82 (1.04)** | +0.000 (0.022) |
| allcontent20k minus 10-29 | train | 500 | -0.29 (0.48) | -0.024 (0.015) |
| allcontent20k minus 10-29 | other held-out | 326 | -0.75 (0.62) | -0.012 (0.016) |
| allcontent20k minus 10-29 | held-out Demon Form | 174 | -0.74 (1.14) | -0.034 (0.029) |
| data20k minus 10-29 | train | 500 | -1.38 (0.46) | -0.044 (0.016) |
| data20k minus 10-29 | other held-out | 326 | -2.04 (0.58) | -0.040 (0.015) |
| data20k minus 10-29 | held-out Demon Form | 174 | -3.56 (0.97) | -0.034 (0.028) |

By the step-2 rule: go at 20k too (2.7 se; train +1.08). It changes
nothing queued: step 3 runs at 5k, the smallest dose that went.

The curve on Demon Form decks (HP; 40k is step 1's two seeds):

| dose | arm minus twin | same, minus the train row | twin: Demon Form minus its own train (vs 10-29) | arm: Demon Form minus its own train (vs 10-29) |
|---|---|---|---|---|
| 5k | +7.34 (1.35) | +8.0 | -6.8 | +1.2 |
| 20k | +2.82 (1.04) | +1.7 | -2.2 | -0.5 |
| 40k | +4.56 (0.78) | +3.6 | -0.8 | +2.7 |

Read sceptically:
- The arm-minus-twin gap falls from 5k to 20k mainly because the twin's
  unseen-card loss shrinks (-6.8, -2.2, -0.8) as the net gets stronger;
  that part of the curve is smooth.
- The part that would be "later ticks learned" (the arm's Demon Form decks
  against its own train decks) is +1.2, -0.5, +2.7: not monotone, each
  about 1.2 se wide. Only the 40k value (two seeds) clears 2 se. So the
  data say: seeing the card removes the unseen-card loss at every dose;
  value on Demon Form decks beyond the net's other decks shows at 40k and
  is within noise at 5k and 20k.
- The 20k arm is about 1 HP stronger than its twin everywhere (train
  +1.08, other held-out +1.29), so about 1 HP of the +2.82 is general
  strength (training luck between the two nets), not Demon Form.
- The 5k guard worry (other held-out clears -0.061) does not repeat at
  20k (+0.028).

What it changes for step 3: its pass rule reads the Demon Form stratum
against the 10-29 net, a strong net whose unseen-card loss is small (about
-0.8 at 40k strength). So a step-3 pass needs the burst to add later-ticks
value of about 2 se over three seeds, the part that is noisy here; a step-3
fail is then weak evidence for "start", and the close reads it beside the
40k value.

## Step 3, count or start (family fslt-step3, table 0841): pass, count (read 2026-11-11 12:30, lanes ce7b9068)

Three bursts on the 10-29 net (`ycards-net-g1600` recipe at 5000 games
per group on held-out decks, Demon Form in the pool; 0832, 0835, 0858,
15, 14 and 5 minutes against 25), each read @hpb0.01@tsl1 on both cell
books (0833-0840) against the 10-29 net @tsl1
(`results/gauntlet/net1029-hpb0.01-tsl1.json` and `-b500.json`); table
`results/families/fslt-step3.md`, 3.8 thread-h:

| stratum | n | end-HP (se sequences / nets) | clears (se sequences / nets) |
|---|---|---|---|
| train | 500 | +0.08 (0.45 / 0.33) | -0.017 (0.013 / 0.006) |
| other held-out | 326 | +0.19 (0.53 / 0.36) | -0.033 (0.012 / 0.005) |
| held-out Demon Form | 174 | **+2.69 (0.91 / 0.51)** | +0.029 (0.020 / 0.010) |

Per seed on Demon Form decks: +2.07, +2.28, +3.71 HP. By the rule (2 se
over nets, train HP within -0.9 and clears within -0.04): pass, and it
also clears 2 se by the charter's "the larger of sequences and nets"
(2.9 se). Step 3 says **count**: a trained net's start does not block a
later-ticks value; a burst of 5000 games per group teaches what 1.6k-game
bursts did not.

Read sceptically:
- The gain is specific to Demon Form: the other held-out decks were in
  the same burst's pool and gain +0.19, train +0.08. So it is not the
  unseen-card loss of held-out content in general; it is the power whose
  value comes on later turns.
- Size beside step 2: Demon Form minus the net's own train decks is about
  +2.6 here, against +1.2 (5k from scratch, one seed), -0.5 (20k) and +2.7
  (40k from scratch, two seeds). A 5k burst on a trained net reaches the
  40k-from-scratch value; from scratch at 5k it did not, so the start
  helps rather than hurts at this dose.
- The three seeds agree (spread 1.6 HP, all above +2). The 174 Demon
  Form sequences are shared, so the sequences se (0.91) is the honest one.
- Guard caveat: other held-out clears fall -0.033 (0.012), 2.7 se, though
  their HP is level, and train clears -0.017 (1.3 se). The rule guards
  train only; the burst trades a few clears on the other held-out decks.
  Worth a look if this recipe becomes the goal-1 adaptation route.
- Bursts finished well under their estimates (5-15 against 25 minutes);
  0858 ran alone at 5 minutes. Not a fault: each log shows all 10000 games
  (two groups of 5000) and its model written; 0832/0835 shared the CPU.
- One turn deep only; no two-turn read, no headline read.

What it changes: the lane's question is answered (goal 1: a later-ticks
power needs a dose between 1.6k and 5k games per group, about 3.5k games
with the power, on a trained net; no fresh start needed). The lane
reaches its stop rule (go, then count) and closes; shrink-and-perturb is
not needed. Candidate 56 (player cards built the same way) waited on this
step.
