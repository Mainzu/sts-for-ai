# Adapted column on generated enemies (lane gen-adapted-column)

Charter: `lane/gen-adapted-column`. Bench: `measurement/gen-enemies@table24`
(docs/research/generated-enemies.md). Burst source and family table:
docs/specs/gen-adapted-burst.md.

## Step 2's target: probe 0472 read (2026-11-08)

Job 0472 (`jobs/done/0472-mutate-monsters.json`,
`results/mutate/gen-b1-esp0.04.json`): the 10-29 net `@esp0.04@tsl1@hpb0.01`
on gen batch 1, elites, the first 1000 starts (675 elite) x 4 seeds, paired
with the first 4 of `results/mutate/gen-enemies-b1.json`'s 16 seeds (row
check: the heuristic's parent results are identical). Cost = (net -
heuristic)(mechanic) - (same)(ladder control), HP lost per elite fight,
mean (se over starts):

| mechanic x parent | zero-shot | `@esp0.04` | net wins |
|---|---|---|---|
| AttackLoss-Damage x Nob (229) | +13.29 (0.90) | -0.06 (0.38) | 0.698 -> 0.942 |
| AttackLoss-Strength x Nob | +2.29 (0.52) | +21.81 (1.06) | 0.879 -> 0.630 |
| AttackLoss-Strength x Lagavulin (231) | +1.89 (0.55) | +17.76 (0.96) | 0.912 -> 0.742 |
| AttackLoss-Strength x Sentries (215) | -2.82 (0.56) | +13.40 (0.93) | 0.962 -> 0.851 |
| Nob parent, net HP lost | | +1.74 (0.24) | |

Other mechanics move by under 1 HP; on Lagavulin and Sentries most rows are
identical (no enemy Strength, so the price changes nothing).

**Why (a reading of the numbers, not traced in games).** Nob's Enrage
gains Strength from each Skill the player plays; with AttackLoss-Damage
every attack also costs the player HP, so the leaf's HP price pushes the
net toward Skills, which feed Enrage. The Enemy-Strength price counts that
Strength at the leaf, the net stops feeding it, and the cost is gone. So
that cost was the HP price feeding Enrage (the record's one known Nob
loss), not a novelty the net must learn. The flip side: when Strength comes from being
hit (AttackLoss-Strength), the same price makes every attack look costly,
the net stops attacking, and it loses fights (wins down 0.11-0.25 on all
three parents). A flat price on enemy Strength is wrong in both directions;
what matters is Strength's damage over the hits left (backlog
`strength-by-hits-left`, which this read gives evidence for; the
navigator's to rank).

**What it changes.** By the rule in decisions "After generated-enemies
batch 1" (0472 halves AttackLoss-Damage x Nob at 2 se), the column starts
on **AttackLoss-Weak on Lagavulin and Sentries** (zero-shot +6.03 (0.48)
over the 446 starts at 4 seeds; +6.26 Lagavulin, +5.78 Sentries; ladder
control `c-hp1.25-str1` on both), not on Nob. Probes 0473-0474 (the
SharpHide bursts) no longer pick the target; the navigator reads them for
the ranking.

## Step 2: family gac-alw

`configs/families/gac-alw.json`: six 99-game bursts on GE-AttackLoss-Weak
from the 10-29 net, training fights from position 1000 on (54 Lagavulin, 45
Sentries; validation the last 40 of theirs), never the read's starts;
teachers the net at `@hpb0.01@tsl1` (the read player) and the heuristic
(ahead on this mechanic: wins 0.887 against the net's 0.828); three seeds
each. Read per burst: `mutate_monsters.py play --starts 1000 --groups elite
--seeds 4 --players one --net <burst>@tsl1 --mods
GE-AttackLoss-Weak,c-hp1.25-str1`. Table (`family.py` kind `gen`): per
start, the cut (a - b)(mechanic) - (a - b)(control) in the net's HP lost
(the heuristic cancels), mean over nets; pass at a cut of half the
zero-shot cost (3.0) or more and 2 se over nets; the parent rows' change
(retention) is reported beside it, Nob included.

## Step 2 interim: net-g99 seeds 1-2 (jobs 0479-0482, 2026-11-08)

`family.py table configs/families/gac-alw.json` (not written; four bursts
still pending): net-g99 cuts AttackLoss-Weak's cost by **+6.55 (se 0.31
starts / 0.20 nets)**, per net +6.75, +6.35, 1.09 of the zero-shot cost
(+6.03); parent rows' HP lost -0.32 (retention holds, slightly better).

Why the cut exceeds the cost (per encounter, HP lost per elite fight, 4
seeds, mean (se); zero-shot -> burst s1 / s2):

| | Lagavulin (231) | Sentries (215) |
|---|---|---|
| net on mechanic | 31.75 (1.21) -> 24.43 / 24.50 | 36.49 (1.15) -> 26.47 / 27.53 |
| net on control `c-hp1.25-str1` | 25.28 -> 24.38 / 24.20 | 30.59 -> 27.66 / 28.17 |
| heuristic on mechanic (zero-shot file) | 26.91 | 30.91 |
| net wins on mechanic | 0.84 -> 0.93 / 0.93 | 0.81 -> 0.94 / 0.93 |
| parent (unmutated) | 15.62 -> 15.49 / 15.40 | 15.48 -> 14.72 / 15.29 |

The burst net plays the mechanic about as well as its control (Lagavulin
24.4 vs 24.3) and now beats the heuristic on it by 2.5-4 HP; the cost is
gone, not halved. The share is over 1 because the cost was measured
against the heuristic and the cut against the zero-shot net: the burst
went past the heuristic. Both encounters and both seeds agree, the control
moved far less than the mechanic (0.9-2.9 against 7.3-10), and the
unmutated parents held, so the gain is the mechanic, not a general elite
gain. It took 99 games (714 states, a one-minute burst). The rule's pass
(half the cost, 2 se over nets, two nets) is met with seed 3 and the
heuristic arm still to read; the checkpoint waits for the written table
(0493).

## Step 3: 33 games on the target, and the next three mechanics

Queued without waiting for the heuristic arm: the charter's measure is per
mechanic **and teacher**, so both teachers run on every family whatever
step 2's heuristic read says, and net-g99 already meets the step-3 gate.
Next three mechanics by worst parent on the bench
(`measurement/gen-enemies@table24`), skipping AttackLoss-Damage x Nob
(0472's `@esp0.04` removed it: the leaf's HP price, not novelty):

| family | mechanic x parent | zero-shot cost (16 seeds) | control | training fights |
|---|---|---|---|---|
| `gac-alw33` | AttackLoss-Weak x Lagavulin+Sentries | +6.03 (4 seeds) | `c-hp1.25-str1` | first 33 of step 2's |
| `gac-ocw` | OppCard-Weak x Lagavulin | +7.19 (0.54) | `c-hp1.25-str1` | 65, cycled to 99 |
| `gac-ocpd` | OppCard-PlainDamage x Sentries | +4.58 (0.54) | `c-hp1.5-str2` | 61, cycled to 99 |
| `gac-ocd` | OppCard-Damage x Sentries | +4.45 (0.54) | `c-hp1.5-str2` | 61, cycled to 99 |

One parent holds only 61-65 training fights from position 1000 before the
last 40 (validation), so the single-parent families set `repeat` (each
cycle a fresh play seed). Each family: net (`@hpb0.01@tsl1`) and heuristic
teachers, three seeds, read and table as step 2 (the cut on the parent
only; the parent rows of all three elites as retention). OppCard-Weak's
heuristic collapses on Sentries (wins 0.49) but not on Lagavulin (0.88),
the parent trained here. With these four the column holds four mechanics:
the lane's stop rule (done), whatever they read; games to adapt is 33 or
99 for the target and 99 or "more than 99" for the others.

## Step 2 read: family gac-alw table (job 0493, 2026-11-08)

`results/families/gac-alw.md` (0493; bursts and reads 0479-0490). Cut in
AttackLoss-Weak's cost on Lagavulin and Sentries, HP lost per elite fight
beyond `c-hp1.25-str1`, mean over nets (se starts / se nets); zero-shot
cost +6.03 (0.48):

| arm | cut | share of cost | per net | parent change | pass |
|---|---|---|---|---|---|
| net-g99 | +6.36 (0.25 / 0.22) | 1.05 | +6.75, +6.35, +5.97 | -0.38 | yes |
| heur-g99 | +3.36 (0.19 / 0.72) | 0.56 | +1.97, +3.72, +4.40 | -0.32 | yes |

Both teachers pass the rule (half the cost, 2 se over nets); checkpoint
**alw-g99 passed**. The net teacher removes the whole cost in 99 games; the
heuristic teacher removes about half, although the heuristic itself plays
the mechanic better than the zero-shot net (26.9 against 31.8 HP lost on
Lagavulin, 30.9 against 36.5 on Sentries). The three seeds of an arm play
the same games (one `game_seed`) and differ only in training, so the
heuristic arm's spread over nets (+1.97 to +4.40, sd about 1.2 HP against
0.4 for the net arm) is training-seed luck on one data set: its games teach
the net less, and less reliably. A reading, not traced: the heuristic's
games label states the heuristic reaches, not the ones the net's own search
reaches, so they correct less of the net's own play (the teacher-equals-
student pattern of `cause/teacher-equals-student`). Retention: the parent
rows held in both arms; on the rest of the bench the navigator's 0546-0547
(`measurement/bench-retention@gen-b1`) found one spot lost by the net-g99
bursts, OppCard-Vulnerable on Sentries (wins 0.765 to 0.58-0.63), and every
other mechanic and the ladder better.

**Games to adapt, first look (gac-alw33 net-g33 seed 1, 0494-0495):** 33
games cut +1.14 (0.26 over starts), 0.19 of the cost (Lagavulin 31.75 to
28.99, Sentries 36.49 to 34.74 on the mechanic; wins 0.84 to 0.89, 0.81
to 0.83). One seed, a lead: the net teacher needs between 33 and 99 games
on this mechanic; the family's table settles it.

## Step 3 read: family gac-alw33 table (job 0506, 2026-11-08)

`results/families/gac-alw33.md` (0506; bursts and reads 0494-0505). Cut in
AttackLoss-Weak's cost on Lagavulin and Sentries after 33 games, same read
and rule as gac-alw; zero-shot cost +6.03 (0.48):

| arm | cut | share of cost | per net | parent change | pass |
|---|---|---|---|---|---|
| net-g33 | +1.20 (0.15 / 0.05) | 0.20 | +1.14, +1.17, +1.29 | -0.24 | no |
| heur-g33 | +1.84 (0.14 / 0.08) | 0.30 | +1.77, +1.99, +1.75 | -0.26 | no |

Neither teacher halves the cost in 33 games: **games to adapt on
AttackLoss-Weak is between 33 and 99 for both teachers** (net: 0.20 at 33,
1.05 at 99; heuristic: 0.30 at 33, 0.56 at 99). The parents held.

Why so little at 33 when 99 removes it all (3x the games, 5x the cut): in
every 33-game burst (all six logs, 0494-0504) validation MSE was best after
the first epoch and rose after it, so early stopping (patience 3) kept the
one-epoch weights: about 240 new states seen once. The net-g99 bursts
improved to epochs 3-6 (0481, 0483, 0489: 6-9 epochs run) on about 710
states, so they took roughly 15-25 times the useful gradient steps on the
mechanic. The curve is therefore not "games" alone: below about 100 games
this finetune overfits the new states after one pass, and the 33-game point
measures one pass over 33 games. A cheaper adaptation at 33 games would need
a different recipe (lower learning rate, more rehearsal, or a fixed small
number of epochs), not more of the same; that is a lead for goal 1's
games-to-adapt number, not something this lane tests.

The teachers swap order at 33 games: the heuristic's games cut more (+1.84
against +1.20, se over nets 0.08 and 0.05, so the gap is about 7 se over
nets, but the three seeds of an arm share one game set, so this is one
draw of games per teacher). At 99 games the net's games cut twice as much.
A reading, not traced: the heuristic's games carry the mechanic's lesson
(it plays AttackLoss-Weak better than the zero-shot net) in fewer states,
while the net's own games only pay off once enough of them correct the
net's own search lines.

## Step 3 interim: gac-ocw net-g99 (jobs 0507-0512, 2026-11-08)

`family.py table configs/families/gac-ocw.json` (not written; the heuristic
arm, 0513-0518, still runs): net-g99 cuts OppCard-Weak's cost on Lagavulin
by **+4.13 (se 0.27 starts / 0.53 nets)**, 0.56 of the zero-shot cost
(+7.36 (0.63)), per net +3.12, +4.88, +4.40: the arm passes the rule (half
the cost, 2 se over nets) with less to spare than AttackLoss-Weak (1.05).

HP lost per elite fight (a loss costs the entry HP, as the table counts
it), wins beside it; zero-shot (`gen-enemies-b1.json`, first 4 seeds, the
same starts and floors) -> bursts s1 / s2 / s3:

| | OppCard-Weak | control `c-hp1.25-str1` | parent |
|---|---|---|---|
| Lagavulin (trained) | 34.23 (0.86) -> 29.91 / 28.00 / 28.62 (0.89-0.90) | 25.28 -> 23.9-24.1 | 15.62 -> 15.70 / 16.41 / 17.24 |
| Sentries (untrained) | 39.82 (0.70) -> 36.61 / 31.83 / 31.27 (0.75-0.85) | 30.59 -> 28.4-29.0 | 15.48 -> 14.6-15.1 |
| Nob (untrained) | 29.29 (0.87) -> 26.79 / 25.79 / 26.18 (0.90-0.91) | 24.37 -> 22.5-23.5 | 12.59 -> 12.2-12.5 |

(Corrected 2026-11-08: the first version of this table and of the
heuristic paragraph below paired rows by start only, so rows that share a
start index across floors overwrote each other; the numbers here pair by
start and floor, as `family.py` does, and reproduce the table's parent
column. The conclusions did not change.)

Two things the pass does not show:
- **The trained parent got worse.** The table's parent change (+0.83) is
  Lagavulin's own unmutated row, which loses 0.1, 0.8 and 1.6 HP more per
  fight over the three seeds (wins flat, 0.98-0.99); the untrained parents
  held or improved (Sentries -0.4 to -0.9, Nob -0.1 to -0.4). In gac-alw
  the parents held (-0.38). A reading, not traced: the burst trains on
  Lagavulin with OppCard-Weak only, and the OppCard card in the deck
  changes what a good Lagavulin line is, so the net partly unlearns plain
  Lagavulin. A lead, one family; the heuristic arm and gac-ocpd/gac-ocd
  (single-parent too) show whether it repeats.
- **The lesson transfers.** Sentries and Nob with OppCard-Weak, never
  trained on, gain about as much as Lagavulin (Sentries -8 HP and wins
  0.70 to 0.85 at seeds 2-3; Nob -2.5 to -3.5), beyond their controls
  (-1.6 to -2.2 and -0.9 to -1.9). The net learned the mechanic, not the
  encounter, which is what goal 1's adapted column should count: games to
  adapt on one parent buy the mechanic on the others.

**Heuristic arm, seeds 1-2 (0513-0516):** +4.57 (0.35 / 0.64), 0.62 of
the cost, per net +5.21, +3.93: as much as the net teacher here (on
AttackLoss-Weak it took half the net's cut). Lagavulin's unmutated row
again loses HP (15.62 -> 17.05 / 15.82): the trained-parent loss repeats
with the other teacher, so it comes from training on one parent with the
mechanic, not from the net's own games. The transfer is smaller than the
net teacher's: Sentries with OppCard-Weak 39.82 -> 33.25 / 36.48, Nob
29.29 -> 26.32 / 27.32. Seed 3 (0517-0518) and the written table (0519)
settle the family.

## Step 3 read: family gac-ocw table (job 0519, 2026-11-08)

`results/families/gac-ocw.md` (0519; bursts and reads 0507-0518). Cut in
OppCard-Weak's cost on Lagavulin beyond `c-hp1.25-str1`, 99 games;
zero-shot cost +7.36 (0.63):

| arm | cut | share of cost | per net | Lagavulin parent change | pass |
|---|---|---|---|---|---|
| net-g99 | +4.13 (0.27 / 0.53) | 0.56 | +3.12, +4.88, +4.40 | +0.83 | yes |
| heur-g99 | +4.83 (0.29 / 0.45) | 0.66 | +5.21, +3.93, +5.36 | +0.81 | yes |

Both teachers halve the cost in 99 games: **games to adapt on
OppCard-Weak is 99 or fewer for both** (33 untested here). The heuristic
arm's edge (+0.70) is about 1 se of the difference over nets, so the two
teachers are level on this mechanic, unlike AttackLoss-Weak (net 1.05,
heuristic 0.56). Seed 3 of the heuristic (Lagavulin parent 16.44, Sentries
with the mechanic 33.36, Nob 27.06) matches the interim reads above: the
trained parent loses about 0.8 HP per fight in both arms (wins flat), the
untrained Sentries parent holds in both arms, the untrained Nob parent
holds with the net teacher and loses 0.4 HP with the heuristic (13.18 /
12.52 / 13.38 against 12.59), and the mechanic's cut carries to Sentries
and Nob without training on them. Retention on the rest of the bench
(other mechanics) was not read for this family.

## Step 3 interim: gac-ocpd net-g99 (jobs 0520-0525, 2026-11-08)

`family.py table configs/families/gac-ocpd.json` (not written; the
heuristic arm, 0526-0531, still runs): net-g99 cuts OppCard-PlainDamage's
cost on Sentries by **+4.16 (se 0.37 starts / 0.19 nets)**, 0.77 of the
zero-shot cost, per net +3.81, +4.24, +4.44: the arm passes, and its three
seeds agree more closely than on gac-ocw. Heuristic seed 1 alone: +2.78.

HP lost per elite fight (wins), zero-shot -> bursts s1 / s2 / s3:

| | OppCard-PlainDamage | control `c-hp1.5-str2` | parent |
|---|---|---|---|
| Sentries (trained) | 49.17 (0.64) -> 42.79 / 42.74 / 42.49 (0.80-0.81) | 44.04 (0.75) -> 41.5-41.9 (0.78-0.80) | 15.48 -> 17.28 / 16.68 / 15.72 |
| Lagavulin (untrained) | 27.09 (0.94) -> 25.58-25.75 | 33.90 -> 33.4-34.0 | 15.62 -> 15.2-16.1 |
| Nob (untrained) | 21.29 (0.96) -> 19.28-20.16 | 38.27 -> 36.4-38.5 | 12.59 -> 12.0-12.3 |

- **The trained parent loses again:** plain Sentries costs 1.8, 1.2 and
  0.2 HP more per fight (table +1.08, wins flat at 0.99). That is the third
  arm out of three single-parent arms read (gac-ocw both teachers, gac-ocpd
  net) where the elite trained with a mechanic gets worse without it,
  while the parents not trained on hold. The two-parent family gac-alw
  did not show it (-0.38). A pattern now, still untraced.
- **The control moved too** (-2.2 to -2.6 HP on Sentries): part of what
  the burst learned is general Sentries play under a stronger enemy; the
  cut (+4.16) is beyond that.
- **Transfer is small here** because OppCard-PlainDamage costs little on
  Lagavulin and Nob to start with (the mechanic's HP lost there is below
  the control's); it still drops 1.3-2.0 HP on both.
- These bursts trained 12-15 epochs (0520, 0522, 0524) against 4-6 on
  gac-ocw: validation kept improving on this mechanic, so the same 99
  games bought more training steps.

**Heuristic arm, seeds 1-2 (0526-0529):** +2.94 (0.42 / 0.16), 0.54 of
the cost, per net +2.78, +3.09: just over the half-cost line, below the net
teacher's +4.16 (the order of AttackLoss-Weak, not of OppCard-Weak, where
the teachers were level). Sentries with the mechanic 49.17 -> 44.27 /
43.31 (net teacher 42.5-42.8); its control 44.04 -> 41.9 / 41.3, so about
half of the heuristic arm's raw gain on Sentries is general Sentries play.
The trained parent loses less here (plain Sentries 15.48 -> 15.67 / 16.02,
table +0.36). Seed 3 (0531) and the table (0532) settle the family.

## Step 3 read: family gac-ocpd table (job 0532, 2026-11-08)

`results/families/gac-ocpd.md` (0532; bursts and reads 0520-0531). Cut in
OppCard-PlainDamage's cost on Sentries beyond `c-hp1.5-str2`, 99 games;
zero-shot cost +5.39 (0.63) (the read's starts; +4.58 on the bench's 16
seeds):

| arm | cut | share of cost | per net | Sentries parent change | pass |
|---|---|---|---|---|---|
| net-g99 | +4.16 (0.37 / 0.19) | 0.77 | +3.81, +4.24, +4.44 | +1.08 | yes |
| heur-g99 | +2.68 (0.35 / 0.27) | 0.50 | +2.78, +3.09, +2.17 | +0.27 | no |

The net teacher halves the cost in 99 games; the heuristic misses the line
by 0.015 HP (2.68 against 0.5 x 5.39 = 2.695), well inside its se over
starts (0.35). By the rule it fails, so **games to adapt on
OppCard-PlainDamage is 99 or fewer with the net teacher and "about 99" with
the heuristic**: the column records the heuristic as "more than 99 (at the
line)". The order of the teachers is AttackLoss-Weak's (net ahead by about
1.5 HP), not OppCard-Weak's (level).

Retention, as in the interim: the trained parent loses with the net teacher
(+1.08) and barely with the heuristic (+0.27); the heuristic's seed 3
(plain Sentries 15.56, the mechanic 43.96, control 41.00) matches its
seeds 1-2. Across the three single-parent arms read so far that pass, the
trained parent's loss is 0.8-1.1 HP; the heuristic arm here, whose cut is
smallest, loses least, so the loss tracks how far the burst moved the net
on that elite.

## Step 3 read: family gac-ocd table (job 0545, 2026-11-08)

`results/families/gac-ocd.md` (0545; bursts and reads 0533-0544). Cut in
OppCard-Damage's cost on Sentries beyond `c-hp1.5-str2`, 99 games;
zero-shot cost +5.11 (0.61):

| arm | cut | share of cost | per net | Sentries parent change | pass |
|---|---|---|---|---|---|
| net-g99 | +3.01 (0.36 / 0.02) | 0.59 | +3.04, +3.02, +2.97 | +0.62 | yes |
| heur-g99 | +2.86 (0.35 / 0.17) | 0.56 | +2.53, +2.93, +3.11 | -0.03 | yes |

Both teachers halve the cost in 99 games, level (0.15 HP apart). The net
arm's three seeds agree to 0.02 se; checked: three distinct trainings
(validation best at epochs 3 and 5) and three distinct read files, so it
is chance, not a copy. HP lost on Sentries with the mechanic 48.78 (wins
0.65) -> 42.8-43.2 (0.79-0.80) in both arms; the control moved 2.5-3.0 HP
in both, so as on gac-ocpd part of the raw gain is general Sentries play
and the cut is beyond it. The heuristic arm leaves plain Sentries level
(15.48 -> 15.37-15.56); the net arm costs it +0.62.

## The column (lane close, 2026-11-08)

Checkpoint **column4 passed**: four mechanics, both teachers, three seeds
each, one turn deep @hpb0.01@tsl1 against the zero-shot 10-29 net. Share
of the zero-shot cost cut (pass = half the cost, 2 se over nets):

| mechanic x parent | net, 99 games | heuristic, 99 games | 33 games (net / heur) | games to adapt (net / heur) | trained parent (net / heur) |
|---|---|---|---|---|---|
| AttackLoss-Weak x Lagavulin+Sentries | 1.05 | 0.56 | 0.20 / 0.30 | 33-99 / 33-99 | -0.38 / -0.32 |
| OppCard-Weak x Lagavulin | 0.56 | 0.66 | - | <=99 / <=99 | +0.83 / +0.81 |
| OppCard-PlainDamage x Sentries | 0.77 | 0.50 (misses by 0.015 HP) | - | <=99 / >99 at the line | +1.08 / +0.27 |
| OppCard-Damage x Sentries | 0.59 | 0.56 | - | <=99 / <=99 | +0.62 / -0.03 |

What it says:
- **About 100 games adapt the net to a generated enemy mechanic**, with
  either teacher, on all four: the net teacher passes everywhere, the
  heuristic on three and at the line on the fourth. 33 games is not enough
  with this finetune: it overfits after one pass (every 33-game burst kept
  its epoch-1 weights).
- **The teacher matters less than the opening rating feared or hoped:**
  the heuristic never beat the net teacher by 2 se at 99 games (OppCard-Weak
  +0.70, about 1 se); the net led on two (AttackLoss-Weak by 3 HP,
  OppCard-PlainDamage by 1.5), level on two. Only at 33 games did the
  heuristic's games cut more (+1.84 against +1.20 on one game set each).
- **A single-parent burst costs that parent's plain fight 0.3-1.1 HP**
  (wins flat), most where the burst moved the net most; the two-parent
  family did not, and the heuristic's bursts cost less. Retention on the
  rest of the bench was read only for the step-2 bursts
  (`measurement/bench-retention@gen-b1`: one spot lost, OppCard-Vulnerable
  on Sentries).
- **The lesson transfers inside a trigger family:** OppCard-Weak bursts on
  Lagavulin cut the mechanic's cost on Sentries and Nob without training on
  them; and the 399-game SharpHide bursts on a neighbouring mechanic had cut
  OppCard-PlainDamage's cost by about 0.9 (`measurement/family-transfer@gen-b1`),
  more than its own 99-game net burst here (0.77): four times the games on
  a neighbour beat the mechanic's own 99.
