# Luck-corrected labels (lane luck-corrected-labels)

Charter `lane/luck-corrected-labels`; spec `docs/specs/luck-corrected-labels.md`.

## Step 1a read (2026-11-11, job 0894)

Job `jobs/done/0894-luck-share.json` (pin 2b6131f, 4 min against a 25-min
estimate: 3200 one-turn fights take 2 minutes at 4 threads, the replay the
rest; the estimate was loose, the game count in the log is the full 3200).
Result `results/luck/luck-share-g1600.json`: 3200 games of the
ycards-net-g1600 recipe (10-29 net @hpb0.01, held-out decks, seed 51),
22813 labelled rows, luck valued by the unpriced 10-29 net on the
post-event state; label noise measured by replaying 1200 rows 8 times.

| slice | games | noise_share (se) | label_share | label var | noise var |
|---|---|---|---|---|---|
| all | 3200 | 0.128 (0.048) | 0.025 | 0.364 | 0.071 |
| Demon Form decks | 691 | **0.011 (0.102)** | 0.002 | 0.363 | 0.072 |
| other decks | 2509 | 0.162 (0.063) | 0.031 | 0.364 | 0.070 |
| elite | 1600 | 0.115 (0.075) | 0.043 | 0.066 | 0.024 |
| boss | 1600 | 0.132 (0.051) | 0.027 | 0.572 | 0.117 |
| Demon Form, boss | 328 | -0.020 (0.113) | -0.004 | 0.565 | 0.115 |

**Fail at the fail-fast**: on Demon Form decks the correction removes 1%
of the label noise (se 10%; 2 se above is 0.21), against the bar of 0.50.
Step 2 does not run. Over all decks it removes 13% (se 5%).

Why:
- **The net prices little of the luck.** The net's own squared error
  around the labels (`residual_ms` 0.147 overall, 0.165 on Demon Form
  decks) is twice the label noise (0.071): the net's error is as big as
  the luck itself, and its values of a chance event's outcomes barely
  differ, so the term it subtracts is small. On Demon Form decks, the
  states whose worth lies past the horizon, it prices nothing: this is the
  backlog's "against" ("the correction removes only luck the net already
  prices"), confirmed.
- **Luck is a fifth of the label spread, not most of it.** Replayed noise
  (E[Var(label | state)]) is 0.071 of a label variance of 0.364 (19%,
  similar on every deck slice); the rest is the spread of true values
  across states. The backlog entry's mechanism ("most of its spread is
  luck after the decision") disagrees with this measurement. The
  noise-limit reading of the dose record still stands as a noise-to-signal
  question, but the label's luck is smaller than assumed.
- Boss fights carry the most noise (0.117) and the correction does as
  well there as anywhere (0.13); elites carry little (0.024).

## Step 1b: prediction before the build

Under the charter as amended after the 2026-11-11 big-picture review
(decisions "After the big-picture review of 2026-11-11: two charters
amended, ..."), step 1a's fail only stops step 2: the read-sd ratio (1b)
is step 1's main result and the lane's go on its own.

The ratio's bar (at most 0.75) needs about 44% of a paired read's
variance removed. If the correction prices a read's chance as it prices
these labels' (13%, at most about 22% at 2 se), the ratio lands near 0.93
(no lower than about 0.88), a fail. What could make it pass anyway: a
read's spread sits in deaths (two thirds from the tenth of sequences where
one player dies) and bosses, and a lethal draw may be priced better than a
label's average draw; and the opening hand, outside the labels' luck, is
in a read's.

## Step 1b read (2026-11-11, job 0900)

Job `jobs/done/0900-luck-read.json` (pin 407a3a4, 1.5 min against a
15-minute estimate). Result `results/luck/luck-read-cells.json`: the
first 100 one-turn cell sequences, net1029-hpb0.01 against
net1029-hpb0.01-tsl1, luck logged by the unpriced 10-29 net. Every game
equals the players' gauntlet files.

| | raw sd (HP) | corrected sd (HP) |
|---|---|---|
| paired, 100 sequences | 8.53 | 12.05 |
| paired, one player died (40) | 12.10 | 16.01 |
| paired, both cleared (60) | 4.58 | 8.03 |
| unpaired, @hpb0.01 | 25.31 | 37.68 |
| unpaired, @hpb0.01@tsl1 | 25.13 | 37.53 |

**Fail: ratio 1.41 (se 0.50) against the bar of 0.75.** The correction
widens every spread instead of narrowing it. The mean paired difference
moves from -1.83 to -2.67 HP, inside its se (about 1.2). The prediction
(about 0.93) was too kind.

Why: a sequence's summed luck has an sd of about 26 HP for each player
(dozens of chance events over about 9 fights), but it doesn't correlate
with the sequence's end HP (r = -0.08 for @hpb0.01). Each event's term
is the net's value of the outcome drawn minus its mean over outcomes.
Those values swing by several HP per draw and carry almost no information
about how the fight ends. That agrees with step 1a: the net's error
around the labels is twice the label noise. The terms add up to noise
about as large as the read's own spread. In the paired read, the twins'
luck terms differ on 22 of 100 sequences and their end HP on only 14, so
the correction adds noise where the read had none. An unbiased term with a
poor value function costs variance, as the backlog entry's trade-off
allowed.
