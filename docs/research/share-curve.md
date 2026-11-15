# share-curve (lane/share-curve)

Goal 1's games-to-adapt number under the replay-share recipe. Few-game-recipe
found that the default finetune replay share 0.5 under-trains a 33-game burst
(measurement/few-game-recipe@gfr-33: share 0.8 cut 4.77 of GE-AttackLoss-Weak's
6.03 HP cost, the default 1.20). This lane asks whether that holds on a second
mechanic and how far down in games it reaches.

How this moves goal 1: the goal-1 number is how few games a net needs to adapt
to new content; today it is quoted as about 100 games (measurement/adaptation-curve,
at share 0.5). If the share recipe holds on both mechanics, the quote drops to
33 games (or 11). We'll know from the two family tables below against the
charter's stop rule.

## Step 1 plan (no code, 2026-11-08)

Net-teacher bursts from the 10-29 net through `family.py`, three burst seeds
per arm, read one turn deep @hpb0.01@tsl1 on each mechanic's gen-adapted
read setup (1000 starts x 4 seeds, elites, against c-hp1.25-str1):

- `configs/families/sc-alw.json`, GE-AttackLoss-Weak (lagavulin,
  three_sentries; zero-shot cost +6.03): g11 sh0.8, g11 sh0.9, g33 sh0.9.
  On file: g33 sh0.5 (gac-alw33), g33 sh0.8 (gfr-33), g99 sh0.5 (gac-alw).
- `configs/families/sc-ocw.json`, GE-OppCard-Weak x Lagavulin (zero-shot
  cost +7.36; repeat on, as gac-ocw): g33 sh0.5 (the 33-game default),
  g33 sh0.8, g33 sh0.9, g11 sh0.8. On file: g99 sh0.5 (gac-ocw, +4.13).

Each family's table (rule: half the cost at 2 se) is written by its table
job; the charter's comparisons (against the 33-game default and the 99-game
cut, parent change within 0.5 HP) are made by hand from the tables.
Step 2 (after the tables): the best 33-game recipe net, one seed, on the
one-turn cell gauntlet --against the one-turn control (retention).

## Step 1, first half: AttackLoss-Weak table (job 0649, 2026-11-09)

Family `sc-alw` (results/families/sc-alw.md, .json), GE-AttackLoss-Weak on
lagavulin and three_sentries, zero-shot cost +6.03 (0.48), net HP lost per
elite fight beyond c-hp1.25-str1, three burst seeds per arm, mean (se starts
/ se nets); parent change is burst minus zero-shot HP lost on the unmutated
parents, negative better (mean, se):

| arm | cut | share of cost | per net | parent change | half-cost rule |
|---|---|---|---|---|---|
| g11 sh0.8 | +1.63 (0.16 / 0.57) | 0.27 | +0.98, +1.14, +2.76 | -0.29 (0.12) | fail |
| g11 sh0.9 | +3.49 (0.20 / 0.46) | 0.58 | +2.57, +3.94, +3.97 | -0.59 (0.07) | pass |
| g33 sh0.9 | +7.48 (0.27 / 0.23) | 1.24 | +7.27, +7.23, +7.94 | +0.17 (0.31) | pass |
| on file: g33 sh0.5 (default) | +1.20 (0.05) | 0.20 | | -0.24 | fail |
| on file: g33 sh0.8 (gfr-33) | +4.77 (0.68) | 0.79 | | -0.41 | pass |
| on file: g99 sh0.5 (default) | +6.36 (0.22) | 1.05 | | -0.38 | pass |

Against the charter's bar, AttackLoss-Weak's half of the go holds: the
33-game sh0.9 arm cuts 1.24 of the cost, beyond the 99-game default's cut
(+1.12 HP, about 3.5 se over the two nets' se), and its parent change sits
0.41 HP from the 33-game default's (bar 0.5). The 11-game sh0.9 arm also
passes the half-cost rule (0.58, 7.6 se nets), so the 11-game quote is open
if OppCard-Weak's g11 sh0.8 arm meets the bar too.

Why, and what to doubt:
- The share is a step-count knob: at 33 games, sh0.5 to 0.8 to 0.9 gives
  cuts 1.20 / 4.77 / 7.48, rising with the gradient steps per pass (0.9 is
  5x the steps of 0.5). The seed spread shrinks with it (se nets 0.68 at
  sh0.8, 0.23 at sh0.9): at 0.8 some seeds under-train, at 0.9 all three
  land within 0.7 HP.
- A cut above the cost (1.24, and the 99-game default 1.05) means the
  adapted net plays the mutated elites better than the zero-shot net plays
  the plain ones: AttackLoss-Weak is exploitable (Weak on the enemy also
  strips its attack), and the bursts learn to apply Weak early. Not a
  measuring error: the 99-game default shows it too, with other seeds.
- Cost of the gain: the g33 sh0.9 parent change is the only positive one
  (+0.17, se 0.31): within the bar but the arm that trains hardest is the
  one closest to it. Retention on the cell gauntlet (step 2) is the real
  check of what extra steps cost.
- g11 at sh0.8 vs 0.9: 1.63 vs 3.49 with the same 11 games, so at 11 games
  sh0.9 is still step-limited; a higher share (or more epochs) is the next
  knob if the 11-game quote matters, not more games.

What it changes: nothing is built on it until OppCard-Weak's table (0674);
if OppCard repeats it, step 2 reads g33 sh0.9 for retention.

## Step 1, second half: OppCard-Weak table (job 0674, 2026-11-09); checkpoint recipe-tables passed

Family `sc-ocw` (results/families/sc-ocw.md, .json), GE-OppCard-Weak on
lagavulin (repeat on), zero-shot cost +7.36 (0.63), same reads and units
as the AttackLoss-Weak table; parent change is on the unmutated Lagavulin
(mean, se), negative better:

| arm | cut | share of cost | per net | parent change | half-cost rule |
|---|---|---|---|---|---|
| g33 sh0.5 (the 33-game default) | +2.97 (0.25 / 0.62) | 0.40 | +1.81, +3.14, +3.95 | +1.53 (0.60) | fail |
| g33 sh0.8 | +4.09 (0.29 / 0.03) | 0.56 | +4.02, +4.14, +4.11 | +0.15 (0.22) | pass |
| g33 sh0.9 | +4.51 (0.28 / 0.42) | 0.61 | +4.52, +5.24, +3.78 | -0.04 (0.25) | pass |
| g11 sh0.8 | +2.54 (0.24 / 0.46) | 0.34 | +3.45, +2.08, +2.09 | +1.15 (0.53) | fail |
| on file: g99 sh0.5 (gac-ocw) | +4.13 (0.53) | 0.56 | | about +0.8 | pass |

Against the charter's stop rule, the go holds on OppCard-Weak too, so on
both mechanics: g33 sh0.9 reaches 0.61 of the cost (sh0.8 0.56), both at
the 99-game default's cut or above it (+4.51 and +4.09 against +4.13), and
both parent changes are better than the 33-game default's (+1.53), not
worse. The bar "within 0.5 HP of its 33-game default's" is read one-sided
(no more than 0.5 HP worse; decisions "share-curve: the parent-change bar
is one-sided"). The fail branch is out: g33 sh0.9 beats g33 sh0.5 by 1.54
HP, 2.0 se over the two arms' net se (0.42, 0.62), sh0.8 by 1.12 (1.8 se).

Why, and what to doubt:
- The share gain is smaller here than on AttackLoss-Weak: 0.40 to 0.61 of
  the cost (AttackLoss-Weak 0.20 to 1.24). OppCard-Weak's 33-game default
  already does better (0.40 against 0.20), and its 99-game default stops
  at 0.56: the mechanic seems to cap near 0.6 of its cost for this net
  and read, so more steps buy less. The go here rests on reaching the
  99-game cut, not on beating it.
- The parent result is the surprise: at share 0.5 the 33-game bursts
  cost the unmutated Lagavulin 1.5 HP per fight (se 0.6; the 99-game
  default about 0.8), at 0.8 and 0.9 nearly nothing. More steps on the
  same 33 games did not over-fit the parent; the under-trained net is the
  one that plays the plain Lagavulin worse, perhaps a half-moved value
  head. Retention on the cell gauntlet (step 2) checks it off this one
  encounter.
- sh0.8's three seeds land within 0.12 HP (se nets 0.03): luck, not a
  property; sh0.9's spread (0.42) is like the other arms'.
- The 11-game quote stays open: g11 sh0.8 fails (0.34), as on
  AttackLoss-Weak (0.27), where sh0.9 passed (0.58). Step 1b reads
  OppCard-Weak g11 sh0.9 (family sc-ocw11, three seeds).

What it changes: games to adapt is quoted as 33 at replay share 0.9 (0.8
also passes both) once step 2's retention holds; queued: step 1b
(sc-ocw11) and step 2, the cell-gauntlet retention reads of each
mechanic's best g33 sh0.9 seed (AttackLoss-Weak s3, OppCard-Weak s2:
the hardest-trained, the likeliest to lose retention) --against
results/gauntlet/net1029-hpb0.01.json.

## Step 1b and step 2: OppCard-Weak at 11 games (table 0694) and retention (0695, 0696), 2026-11-09; checkpoint retention passed; the go holds

**Step 1b**, family `sc-ocw11` (results/families/sc-ocw11.md): GE-OppCard-Weak
x Lagavulin, 11 games at share 0.9, three seeds: cut +3.69 (0.26 / 0.71),
0.50 of the +7.36 cost, per net +4.88, +2.43, +3.76, parent change +0.09.
It passes the half-cost rule, but at its bar (0.501): one seed of three
stays at 0.33 of the cost. Against the 99-game default (+4.13, se 0.53) it
is 0.44 HP short, within 2 se (0.89). So 11 games meet the charter's bar on
both mechanics (AttackLoss-Weak's g11 sh0.9: 0.58), the OppCard half with
no margin.

**Step 2**, one-turn cell gauntlet, paired against
results/gauntlet/net1029-hpb0.01.json (same sequences and cells), each
mechanic's best g33 sh0.9 seed (the hardest-trained):

| net | n | paired end-HP (se) | train / held-out | clears (control) | paired clears z |
|---|---|---|---|---|---|
| AttackLoss-Weak g33 sh0.9 s3 (0695) | 250 | +0.06 (0.55) | +0.29 (0.66) / -0.17 (0.89) | 0.636 (0.612) | +1.34 |
| OppCard-Weak g33 sh0.9 s2 (0696) | 200 | +0.31 (0.48) | +0.20 (0.61) / +0.42 (0.75) | 0.635 (0.600) | +1.82 |

Both runs stopped before 500 sequences: `--against` ends a run when the
protocol decides, and it decided "no 1.5 HP gain" (fail at n 205 and 181),
which is the expected answer for a retention read, not a loss. The charter's
bar (retention within 1.5 HP) is met with room: the 2-se lower bounds are
-1.04 and -0.65 HP. Not re-run at 500: no n changes the side of the bar.
(A retention read should be queued without `--against` and paired after;
the note said fixed n 500 and the command did not deliver it.)

Why: the extra gradient steps of share 0.9 are spent on 33 games of one
mutated elite, yet the cell gauntlet (hallways, elites, a boss, train and
held-out cells) is played as well as by the parent, slightly better on
clears. Like the unmutated-parent changes in the tables, this says the
share recipe does not buy its cut by forgetting at this size; the 99-game
default's retention reads (adaptation curve, -0.07 to -0.31) were no
better.

**Outcome of the lane (go).** On both mechanics a 33-game arm at share 0.9
(0.8 too) reaches half the zero-shot cost or the 99-game default's cut,
with the parent spared and retention held: games to adapt is quoted as
**33 games at replay share 0.9** (from about 100 at share 0.5), and 11
games at share 0.9 meet the same bar, on OppCard-Weak at the edge (0.50,
one seed in three short). Caveats for the quote: two mechanics, both
debuff-on-enemy elites one turn deep, net teacher only; the 11-game
number rests on three seeds per mechanic.
