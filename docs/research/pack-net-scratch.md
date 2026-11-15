# pack-net-scratch: results

Lane `lane/pack-net-scratch` (spec `docs/specs/pack-learn.md`). One section
per read; job records in `jobs/done/<id>.json`.

## Pack control 0745 (29 cards, pin 2d34cd3)

The 10-29 net @hpb0.01, one turn deep, on the pack-offers headline with the
act1-ironclad pack (29 cards since C3), sequences 0-499, `--vary pack`
against the plain one-turn control
(`results/gauntlet/pns-net1029-hpb0.01-starter-simboss-pack-act1-2d34cd3.json`).

- Clears 0.496 (248 of 500); plain control 0.680 (340); the 27-card control
  (`g1-net1029-hpb0.01-starter-simboss-pack-act1.json`) 0.522 (261).
- Against the 27-card file, sequence by sequence: 156 clear both, 105 clear
  with 27 cards only, 92 with 29 only. Net -13 clears, inside one sd of the
  swap count (sqrt(197), about 14): the two new cards change little, as the
  job's note expected (a drop near -0.16 against plain; measured -0.184).
- Where runs end (29 cards / 27 cards / plain): boss 147 / 151 / 107,
  elite 80 / 62 / 35, hard hallway 25 / 26 / 18. The extra deaths sit at
  elites (+18), not at the boss.
- The two new cards are taken often: Fire Breathing 154 of 267 offers,
  Evolve 56 of 246. The 10-29 net was trained before C3's CardDrawn trigger
  column existed, so it sees neither card's trigger; Fire Breathing at 58%
  take rate is a pick the net can't value. A pack-trained net (this lane's
  step 1) sees the column, so this is part of what step 1 can gain.

It is the `--against` control for the seed-1 pack read.

## Seed-1 learn 0746: failed at start (registry full)

0746 (`configs/packnet40k-s1.json`, pin 2d34cd3) played its 3000 val games,
then failed in the first train chunk: `ValueError: registry full (slot
sets)`. Each combat whose deck holds pack cards binds its own slot set (the
deck's pack cards, then the pack monsters' powers, in slot order). The
engine held 4096 slot sets a process, indexed by u16.

Counted with `sts.slot_sets()` on the fixed build (e353b47): 2814 sets after
the 3000 val games; 11645 more over a 12000-game train set (4000 per group),
about 0.89 a game. Round 0 plays 120k games (`n_train` 40000 per group, 3
groups), so it needs about 107k, past any u16 index. The full round-0
dataset on the fixed build (val, then the 120k train games, 18 minutes)
bound 98,859 sets: a u16 index (65,535) would have failed too.

Fix (e353b47): `Binding::slots` is a u32, `SLOT_SETS` a chunked store of up
to 2^20 sets. Golden, codec golden, the engine suites and series_check
(3104 states, heuristic and the product net bit-identical) are unchanged;
speed is the queued check below.

## Seed-1 learn 0749 (pin 693c4cd)

`configs/packnet40k-s1.json` ran 1.9 h at 6 threads (estimate 3.7 h; 0583's
all-content recipe took 3.4 h; the faster train epochs and the early stop
at epoch 10 account for it). Round 0 val MSE 0.1443 (allcontent40k-s1:
0.1284), round 1 0.1521 (round 1 reaches the heuristic on both halves, as
allcontent's did). The val sets differ (this one holds the pack cards and
monsters), so the MSE gap says the pack games are harder to predict, not
that the net is worse; the gauntlet reads decide. Peak working set 5.54 GB
with `mem_gb` 2.0 (the mapped feature cache, expected); the runner logged
no admission wait while it ran (0747 test-full ran beside it), so lane
step 0's runner change is not needed.

**Control mismatch.** At 693c4cd the pack holds 31 cards: C5 (Blood for
Blood, Corruption) landed between 0745's pin 2d34cd3 and the learn's pin.
0745's 29-card file is therefore not a matched control for this net. A new
control (the 10-29 net @hpb0.01 on the 31-card pack, `--vary pack` against
the plain one-turn control) is queued first; the seed-1 read runs against
it. The pack file is identical from 693c4cd to the card-sets landing
(0280a62), so the reads run at the lane's HEAD.

Queued: the 31-card control, then the seed-1 pack read against it and the
seed-1 cell read against `net1029-hpb0.01.json` (both sequences 0-499,
fixed n 500). The cell read's `--check` is `scripts/analysis/paired_go.py`
(pack: paired end-HP z >= 2; cells: paired end-HP >= -1.5); seeds 101 and
201 (`configs/packnet40k-s101.json`, `-s201.json`) wait on that check and
are cancelled on a fail.

## Speed of the slot-set fix 0750

`series_speed` 25 runs, e353b47 against the C5 build, order swapped every
other run. Per-run ratio medians: random combats -5.4%, clone ns +1.6%,
search 1 thread +2.3%, search 16 threads -6.2%. All inside the -10% bar, so
the fix may go into main's `sts` at the next swap; the -5% to -6% on random
combats and 16-thread search is a real cost of the wider binding, worth a
profile if a later change adds to it. Main's `sts` was not swapped in this
session (every lane job runs pinned).

## Seed-1 reads 0751-0753: checkpoint seed1-pack-read passed

**Control 0751** (the 10-29 net @hpb0.01 on the 31-card pack, `--vary pack`
against the plain one-turn control): `results/gauntlet/pns-net1029-hpb0.01-starter-simboss-pack-act1-31.json`.

**Pack read 0752** (seed-1 r1 @hpb0.01, 31-card pack headline, sequences
0-499, fixed n 500, against 0751): paired end-HP **+3.25 (se 0.94, z
+3.45)**, clears 0.600 against 0.516 (+0.084, se 0.027). By half: train
+0.056 clears (se 0.039), held-out +0.112 (se 0.038). Deaths by floor move
mostly at the boss (floor 16: 106 against 129) and at floor 14 (13 against
20); by encounter: Hexaghost 51/58, Guardian 36/49, Lagavulin 21/34, but
Gremlin Nob 30 against 23 (more Nob deaths; the one place it's worse).
HP at the boss is level (58.1 / 58.9 over the 342 sequences both reach),
so the gain is in fighting the boss and Lagavulin, not in arriving
healthier.

Card picks barely move (the same sim chooser picks; only the fighter
differs): pack cards taken 1939 against 1920 of about 4750 offers. Per
card, taken/offered against the control: Fire Breathing 123/236 vs
135/237, Evolve 52/246 vs 44/248, Blood for Blood 128/253 vs 143/251,
Corruption 15/243 vs 17/240, Disarm 122/236 vs 93/234, Double Tap 47/260
vs 66/258, Feed 34/235 vs 56/234. The differences come from the chooser's
rollouts seeing a different fighter (Disarm up, Feed and Double Tap down).

**Cell read 0753** (retention, one-turn cell gauntlet, sequences 0-499,
against `net1029-hpb0.01.json`): end-HP **+1.61 (se 0.58, z +2.79)**,
clears 0.648 against 0.634 (+0.014). By half: train -0.032 clears (se
0.022), held-out +0.060 (se 0.025). No retention loss: the from-scratch net
is a little better on official cells overall, worse on train cells' clears,
better on held-out cells.

**Check** (`paired_go.py`, z >= 2 on the pack, cells >= -1.5 HP): pass.
Single seed, so a lead: seeds 101 (0754) and 201 (0755) learned on the
check's pass. The held-out halves gaining more than the train halves on
both settings is a hint that all-content training generalises better, worth
watching across the three seeds.

## Seeds 101 and 201: reads queued

0755 (seed 201) ran 2.1 h, round 1 reaching the heuristic on both halves
(as seed 1); 0754 (seed 101) is finishing. Each seed gets the same two
reads as seed 1 (pack against 0751, cells against net1029-hpb0.01,
sequences 0-499, fixed n 500). The last read's `--check` is the stop rule:
`paired_go.py --gain-pooled` (the three seeds' end HP averaged per
sequence, minus the control, z >= 2) and `--keep-pooled` on cells (>= -1.5
HP). The pooled se counts sequence noise only, so the read also reports
each seed's own z; a go where one seed is level is written up as such.

Learns done: 0754 (seed 101) ran 2.5 h (beside other jobs), r1 val MSE
0.1543; 0755 (seed 201) 2.1 h, r1 0.1567; seed 1 was 0.1521. Both reach
the heuristic on both halves at round 1, as seed 1 did. 0766-0769 read them.

## Seed-201 pack read 0766: passes alone

0766 (seed 201 @hpb0.01, one turn deep, pack headline, sequences 0-499,
fixed n 500, against 0751's control): end HP +4.05 (se 1.06, z +3.83),
clears 0.574 vs 0.516 (+0.058). Seeds 1 and 201 pooled per sequence:
+3.65 HP (se 0.87, z +4.18), clears +0.071 (`paired_go.py --gain-pooled`
by hand; the lane's go waits for the three-seed check on 0769).

Why: deaths by encounter (control / seed 1 / seed 201) are Hexaghost
58/51/42, Guardian 49/36/45, Lagavulin 34/21/17, Nob 23/30/19, Sentries
20/21/23, Slime Boss 22/19/20. Seed 201 gains mostly at Hexaghost and
Lagavulin; seed 1's Nob rise doesn't repeat (19 vs 23), so it reads as
seed luck, not a pack-net trait. Clears by half: train 0.480/0.536/0.552,
held-out 0.552/0.664/0.596; both halves gain on both seeds, held-out more
on seed 1 only. Two seeds of three now pass alone at z > 3: the pooled
check looks safe unless seed 101 is well below the control, and the
retention side (cells, 0768/0769) is the open question.

## Three-seed read 0767-0769: checkpoint three-seed-read passed (go)

0769's check (`paired_go.py --gain-pooled` / `--keep-pooled`, re-run by
hand, same numbers), sequences 0-499, fixed n 500, one turn deep @hpb0.01:

| read | seed 1 | seed 101 | seed 201 | pooled (3 seeds) |
|---|---|---|---|---|
| pack headline vs 0751 control, end HP | +3.25 (0.94) | +2.69 (1.00) | +4.05 (1.06) | **+3.33 (0.83), z 3.99** |
| pack clears | +0.084 | +0.054 | +0.058 | +0.065 |
| official cells vs net1029-hpb0.01, end HP | +1.61 (0.58) | +0.86 (0.65) | +2.26 (0.58) | **+1.58 (0.52), z 3.06** |
| cell clears | +0.014 | -0.006 | +0.034 | +0.014 |

Every seed passes alone on the pack (z 2.7-3.8); none loses on cells
(seed 101 level, z 1.3). Stop rule: go (pooled pack z >= 2, cells
>= -1.5 HP; in fact cells gain).

Why, and what to doubt: the control never saw the 31 pack cards, so a
gain on the pack is what the training rule predicts (new content); its
size (+3.3 HP, ~+6.5 points of clears) is the news. Deaths on the pack
(control / s1 / s101 / s201): Hexaghost 58/51/43/42, Guardian
49/36/39/45, Lagavulin 34/21/26/17, Nob 23/30/25/19: the gain sits at the
bosses and Lagavulin on every seed; Nob moves both ways (seed noise).
Cells: the gain is not a pack-only effect; seed 101 dies less at Nob
(10 vs 18) and Guardian (38 vs 46) but more at Slime Boss (29 vs 23), and
its train half clears less (0.532 vs 0.592) while its held-out half
clears more (0.724 vs 0.676): retention holds on average but not
uniformly across halves. The pooled se counts sequence noise only (three
seeds share sequences), so seed-to-seed spread (pack 2.7-4.1, cells
0.9-2.3) is the honest error: still clear of zero on the pack, about
+1.6 +/- 0.7 on cells. Not a product read: this is one turn deep; the
product (two turns) reads are the navigator's probes `pns-two-turn`
(0777-0778, gated on 0769, now released), and the generated bench says
the pack net plays generated content worse zero-shot
(`measurement/pack-net-gen-bench@seed1`; 0779-0780 attribute it).
