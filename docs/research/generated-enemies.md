# Generated enemies bench (lane `generated-enemies-bench`)

Goal 1's monsters rung on enemies new in kind: the official Act 1 elites
the mutate bench replays (Gremlin Nob, Lagavulin, three Sentries; the
product file's starts at its entry HP, `yardstick/novelty-read` rule c),
each monster carrying one pack power built from atoms, beside a stat-only
control about as hard. Spec `docs/specs/generated-enemies-bench.md`; code
`scripts/analysis/mutate_monsters.py` (`GEN`, `LADDER`, `read-gen`).

## The 24 mechanics and the first batch

Every (trigger, effect) pair over the triggers monster turn start, monster
turn end, the player's card played, attack HP loss, and the effects
Strength (to the monster), Block (to the monster), Damage, PlainDamage,
Weak, Vulnerable, Frail (to the player), minus the four pairs official
training monsters hold (Ritual, Metallicize, Curl Up, Enrage). 1 stack on
the per-card and per-hit triggers, on Strength and the debuffs; Block 4,
Damage 3, PlainDamage 3 on the turn triggers. A probe on a Cultist fight
(lane worker, 2026-11-07) showed each acting as written: damage reaches the
player, block and Strength the monster, debuffs land on the player, and a
card-played debuff lands before the card resolves (Weak cuts that Strike to
4).

Batch 1 (2 per trigger, by sha256 of the name): TurnStart-Strength,
TurnStart-Damage, TurnEnd-Frail, TurnEnd-Damage, OppCard-Vulnerable,
OppCard-PlainDamage, AttackLoss-Strength, AttackLoss-Damage.

## Predictions for batch 1 (written before the read)

One turn deep `@hpb0.01@tsl1`, the novelty cost in HP lost per elite fight
(net minus heuristic on the mechanic, minus the same on its control).
Mechanism: the one-turn search plays out the player's turn, so an effect
that resolves inside it (on a card played, on an attack hit) is in the
leaf state the net scores: Vulnerable or Strength already applied, HP
already lost. An effect that fires in the monster's turn (its turn start
or end) is priced only by the net's value of a power row it never saw on a
monster (`cause/novelty-is-horizon`: costs sit where value lies past the
leaf). So:

| Mechanic | Predicted cost (HP) | Why |
|---|---|---|
| TurnStart-Strength | +0.5 (0 to +1.5) | growth past the leaf; Demon Form's own row on the player cost the plain leaf and `@tsl1` fixed only the first tick |
| TurnStart-Damage | +1.0 (0 to +2) | 3 damage per monster each monster turn, not in the intent column |
| TurnEnd-Frail | 0 (-0.5 to +0.5) | Frail costs block next turn, small |
| TurnEnd-Damage | +1.0 (0 to +2) | as TurnStart-Damage |
| OppCard-Vulnerable | 0 or below | applied inside the turn, and the intent column counts it |
| OppCard-PlainDamage | 0 (-0.5 to +1) | inside the turn |
| AttackLoss-Strength | +0.3 (0 to +1) | the Strength is inside the turn; its use is the next intent |
| AttackLoss-Damage | 0 (-0.5 to +1) | inside the turn |

Table: 2 of 8 beyond 2 se (the two turn-damage mechanics), mean cost about
+0.4 HP. Fail-fast (all 8 within 2 se) is predicted not to hold, narrowly.

Disclosure: the end-to-end check of the build (20 elite starts, 2 seeds,
`target/e2e.json`, not kept) was read before these lines were written; its
costs had se 0.8-3.8 HP and moved no prediction above (its one large value,
AttackLoss-Damage +8.7 (3.8), is against the prediction and is a lead to
check, not a reason to change it).

## Batch 1 read (job 0469, results/mutate/gen-enemies-b1.json)

`mutate_monsters.py read-gen results/mutate/gen-enemies-b1.json`: 675
elite starts of the first 1000 (229 Gremlin Nob, 231 Lagavulin, 215 three
Sentries), 16 seeds, heuristic and the 10-29 net `@hpb0.01@tsl1` one turn
deep. Cost = (net - heuristic) HP lost on the mechanic minus the same on
its ladder control, paired by start; a loss costs the entry HP.

| Mechanic | Predicted | All elites | Nob | Lagavulin | Sentries |
|---|---|---|---|---|---|
| TurnStart-Strength | +0.5 | +0.48 (0.12) | +0.10 | +1.36 | -1.68 |
| TurnStart-Damage | +1.0 | -0.12 (0.24) | +0.64 | +2.02 | -0.45 (outside) |
| TurnEnd-Frail | 0 | +0.71 (0.09) | +0.32 | +1.07 | +1.04 |
| TurnEnd-Damage | +1.0 | +0.03 (0.24) | +0.83 | +2.23 | -0.38 (outside) |
| OppCard-Vulnerable | 0 or below | -9.55 (0.53) | -0.51 | -10.16 (outside) | -13.43 (outside) |
| OppCard-PlainDamage | 0 | +1.76 (0.29) | +0.57 | +2.92 | +4.58 |
| AttackLoss-Strength | +0.3 | +1.20 (0.22) | +1.84 | +2.04 | -2.82 |
| AttackLoss-Damage | 0 | +5.60 (0.35) | +12.80 | +1.64 | +1.97 |

Over the 8 mechanics: mean +0.01 (se 1.51); 6 of 8 beyond 2 se. **Fail-fast
does not hold** (checkpoint batch1 passed): batch 2 (job 0470, the other
16, merged into the same file) goes on.

Why, from the games (deaths out of about 3,500 games per cell; the net
dies 41-74 times on the parents):
- **The costs sit in encounter interactions, not in the mechanic.**
  AttackLoss-Damage costs +12.8 HP on Nob and under 2 elsewhere: the net
  dies 1,077 times against Nob (heuristic 204) and level with the
  heuristic on Lagavulin (169 vs 179) and Sentries (150 vs 125). On Nob,
  attacks now cost HP and skills feed Enrage; the net's games split into
  wins near the heuristic's HP and collapses (deaths or 10-15 HP left), a
  bimodal pattern, not a uniform drift. OppCard-PlainDamage costs most on
  three Sentries (net 1,187 deaths, heuristic 713): three monsters each
  hit on every card played, and Sentries add Dazed. A mechanic's mean over
  elites mixes one bad pairing with level ones, so the per-mechanic se
  understates how much depends on the parent.
- **The negative costs are the heuristic's collapse, not the net's gain.**
  OppCard-Vulnerable: the heuristic dies 1,481 (Lagavulin) and 1,630
  (Sentries) times, the net 530 and 790; its heuristic HP sits outside the
  ladder on both. The heuristic plays every card it can and stays
  Vulnerable; the net plays fewer. Novelty-read rule (e) again: the
  heuristic is not the zero of a cost, and here it inflates the spread of
  the table (that one mechanic makes the se over mechanics 1.5).
- **The prediction's mechanism fails.** It said costs sit past the leaf
  (the monster-turn damage triggers, +1 each) and not inside the player's
  turn. Measured, the turn-trigger damage mechanics are zero (-0.12,
  +0.03) and the costly ones fire inside the player's turn (on a card
  played, on an attack hit), where the one-turn search sees the HP loss
  in its leaf. Seeing the loss is not enough when the alternative is also
  bad (Nob: skill into Enrage), so the cost is in valuing a squeeze, not
  in the horizon. This agrees with novelty-read column (3), the product's
  earlier cost on reactive powers, and adds that the cost is
  parent-specific.

What it changes: batch 2 runs as planned. For step 4 (the adapted
column on the four costliest), rank by the cost on the worst parent
too, not only the mean over elites, and play the burst against that
parent: AttackLoss-Damage x Nob is the first candidate. Reading the
24-mechanic table, report the per-parent column beside the mean; treat
mechanics whose heuristic sits outside the ladder as unread (the
control is not about as hard, rule (b)).

## Batch 2 read: the 24-mechanic table (job 0470, results/mutate/gen-enemies-b1.json)

`mutate_monsters.py read-gen results/mutate/gen-enemies-b1.json`, after
0470 merged the other 16 mechanics into batch 1's file: the same 675 elite
starts, 16 seeds, heuristic and the 10-29 net `@hpb0.01@tsl1` one turn
deep, the ladder controls from 0469. Batch 1's eight rows read exactly as
before. Cost as in batch 1, HP lost per elite fight; "*" marks a parent
where the heuristic sits outside the ladder (no control about as hard,
rule (b)).

| Mechanic | Heur win | Net win | All elites | Nob | Lagavulin | Sentries |
|---|---|---|---|---|---|---|
| TurnStart-Strength | 0.940 | 0.933 | +0.48 (0.12) | +0.10 | +1.36 | -1.68 |
| TurnStart-Block | 0.942 | 0.936 | +1.88 (0.15) | +0.70 | +1.05 | +2.08 |
| TurnStart-Damage | 0.899 | 0.888 | -0.12 (0.24) | +0.64 | +2.02 | -0.45* |
| TurnStart-PlainDamage | 0.904 | 0.894 | -0.40 (0.24) | -0.23 | +2.08 | -0.44* |
| TurnStart-Weak | 0.928 | 0.919 | +2.21 (0.16) | +1.11 | +2.53 | +1.29 |
| TurnStart-Vulnerable | 0.899 | 0.903 | -1.76 (0.25) | -0.93 | +1.44 | -2.79* |
| TurnStart-Frail | 0.973 | 0.973 | +0.48 (0.09) | +0.25 | +0.80 | +0.68 |
| TurnEnd-Damage | 0.897 | 0.884 | +0.03 (0.24) | +0.83 | +2.23 | -0.38* |
| TurnEnd-PlainDamage | 0.904 | 0.891 | -0.16 (0.25) | -0.08 | +2.22 | -0.01* |
| TurnEnd-Weak | 0.928 | 0.916 | +2.55 (0.17) | +1.37 | +2.60 | +2.01 |
| TurnEnd-Vulnerable | 0.907 | 0.909 | -0.46 (0.20) | -0.87 | +1.48 | +0.45 |
| TurnEnd-Frail | 0.973 | 0.973 | +0.71 (0.09) | +0.32 | +1.07 | +1.04 |
| OppCard-Block | 0.973 | 0.972 | +0.83 (0.11) | +0.65 | +0.49 | +1.38 |
| OppCard-Damage | 0.891 | 0.838 | +2.12 (0.28) | +1.98 | +2.70 | +4.45 |
| OppCard-PlainDamage | 0.895 | 0.854 | +1.76 (0.29) | +0.57 | +2.92 | +4.58 |
| OppCard-Weak | 0.763 | 0.816 | -2.94 (0.56) | -1.52 | +7.19 | -14.30* |
| OppCard-Vulnerable | 0.691 | 0.845 | -9.55 (0.53) | -0.51 | -10.16* | -13.43* |
| OppCard-Frail | 0.972 | 0.953 | +1.77 (0.15) | +0.48 | +0.87 | +4.26 |
| AttackLoss-Strength | 0.921 | 0.917 | +1.20 (0.22) | +1.84 | +2.04 | -2.82 |
| AttackLoss-Damage | 0.953 | 0.871 | +5.60 (0.35) | +12.80 | +1.64 | +1.97 |
| AttackLoss-PlainDamage | 0.960 | 0.953 | +1.44 (0.18) | +1.06 | +1.69 | +2.15 |
| AttackLoss-Weak | 0.896 | 0.832 | +5.38 (0.32) | +1.44* | +6.29 | +6.00 |
| AttackLoss-Vulnerable | 0.745 | 0.848 | -6.53 (0.43) | +0.21 | -6.08* | -9.10 |
| AttackLoss-Frail | 0.974 | 0.968 | +1.26 (0.12) | +0.56 | +1.02 | +2.56 |

Over the 24 mechanics (the mechanic as the unit): mean +0.32 (se 0.65), 20
beyond 2 se. Three mechanics are the heuristic's collapse, not a read of
the net (heuristic wins 0.69-0.76 over elites, below the net's; the
Vulnerable and Weak debuffs applied per card or per hit): OppCard-Weak,
OppCard-Vulnerable, AttackLoss-Vulnerable. Without them, over 21
mechanics: **mean +1.28 (se 0.38), 17 beyond 2 se.** CPU: 0469 6.5 and
0470 8.7 thread-hours, 15.2 against the 10 cap (0470 ran 173 minutes, its
estimate 100, so the decision's 12.3 was low too).

Why, from the table:
- **The trigger orders the cost.** Mean cost by trigger (the 21):
  monster turn start +0.39 (7 mechanics), turn end +0.53 (5), the player's
  card played +1.62 (4), attack HP loss +2.98 (5). The punish-an-action
  triggers cost three to six times the monster-turn ones. This is batch 1's
  finding at three times the sample: the cost is in valuing a squeeze
  inside the player's own turn, not in the horizon (`cause/novelty-is-
  horizon` as re-set after batch 1).
- **Weak is the costly effect; the turn-trigger damage is free.** By
  effect: Weak +3.38 (3), Damage +1.91 (4), Block +1.35, Frail +1.06,
  Strength +0.84, PlainDamage +0.66, Vulnerable -1.11 (2; the heuristic
  half-collapses there too). Weak at the monster's turn start or end costs
  +2.2 to +2.6 on every parent; on attack HP loss +5.4, and on Lagavulin
  OppCard-Weak +7.19 where the heuristic holds (0.882 wins). The damage
  triggers in the monster's turn read zero against their control
  (+2.0 to +2.4 against the parent: they make the fight harder by about
  what the HP ladder does, and the net handles that).
- **TurnStart-X and TurnEnd-X read alike** (within 0.4 HP for each
  effect): in the one-turn search both fire outside the player's turn,
  so they are close to one mechanic each; the table holds about 19
  distinct mechanics, not 24, which widens the se over mechanics a little
  in truth.
- **The costliest by worst parent** (in-ladder, heuristic not collapsed):
  AttackLoss-Damage x Nob +12.80 (0.73), OppCard-Weak x Lagavulin +7.19
  (0.54), AttackLoss-Weak x Lagavulin +6.29 (0.55) and x Sentries +6.00
  (0.59), OppCard-PlainDamage x Sentries +4.58 (0.54), OppCard-Damage x
  Sentries +4.45 (0.54), OppCard-Frail x Sentries +4.26 (0.33).
  AttackLoss-Weak is the one costly mechanic that is not parent-specific
  (+6 on both parents it reads on): a candidate for the adapted column
  beside AttackLoss-Damage x Nob.

What it changes: the charter's measure is recorded (checkpoint table24
passed). Pack enemies built from known atoms do cost the net zero-shot,
about 1.3 HP per elite fight on average and up to 13 on one pairing, and
the cost follows the trigger (the player's own action punished). Step 4
(the adapted column) did not fit the cap and goes to the navigator at the
close, with probes 0472-0474 (lane `main`, running now) still to read:
if `@esp0.04` removes the Nob cost, the column starts on AttackLoss-Weak
(both parents) and OppCard-Damage/PlainDamage x Sentries.

## Fickle enemy (lane `fickle-enemy`): predictions (written before the read)

Three modifiers, the cycle Attack -> Power -> Skill opened on each type
(`docs/specs/fickle-enemy.md`; decisions "Fickle enemy built as three
paired openings"), played on the 675 elite starts x 16 seeds of job 0470
(the file copied, so the ladder control and the parent are the same
rows), heuristic and the 10-29 net one turn deep `@hpb0.01@tsl1`.
Predictions: Power turns are nearly free heals for Ironclad's few Power
cards, so the cost sits in Attack and Skill turns; the Attack opening
punishes turn 1, when Strikes and Bash are the plays, and should cost the
heuristic most (it plays attacks regardless); the net's cost beyond the
heuristic and the stat control, if any, is under the 1.0 HP go bar on
Power and Skill openings and nearest it on Attack (smoke, 40 starts x 2
seeds: FE-Attack +2.14 (1.47), the others about 0). Lagavulin's rows
differ in kind: an Attack or Skill opening wakes it on turn 1.

## Fickle enemy read (job 0781, results/mutate/fickle-enemy.json)

`mutate_monsters.py read-gen results/mutate/fickle-enemy.json`: the three
openings on job 0470's 675 elite starts x 16 seeds, heuristic and the
10-29 net one turn deep `@hpb0.01@tsl1`, cost = (net - heuristic) on the
mechanic minus the same on its ladder control, HP lost per elite fight.
The file's 24 earlier rows read exactly as batch 2 (e.g. OppCard-Weak x
Lagavulin +7.19 (0.54)), so the copy and its controls are intact.

| Opening | Heur win | Net win | All elites | Nob | Lagavulin | Sentries |
|---|---|---|---|---|---|---|
| FE-Attack | 0.963 | 0.961 | +0.32 (0.20) | +0.21 | +1.75 (0.47) | -0.64 |
| FE-Power | 0.972 | 0.972 | +0.16 (0.15) | -0.18 | -0.13 | -0.57 |
| FE-Skill | 0.976 | 0.972 | +0.70 (0.17) | +0.80 (0.22) | -0.09 | +1.57 (0.36) |

**Checkpoint fickle-table: failed.** No opening reaches the 1.0 HP go
bar over all elite fights; FE-Skill is the only one beyond 2 se of zero
(+0.70, 4 se) and still under the bar. The seeded first form (the average
of the three rows) would cost about +0.39.

Why, from the table:
- **The fickle enemy is mild.** The heuristic's HP lost puts the openings
  beside one or two Strength on the ladder (controls c-str1 to c-str2,
  heuristic wins 0.96-0.98): the 5% HP loss on two of three turns gives
  back much of what the Strength costs, and Power turns are nearly free
  heals for Ironclad's few Powers, as predicted.
- **The cost does not follow the punished type in one direction.** The
  prediction (Attack opening costliest, it punishes turn 1's Strikes and
  Bash) held only on Lagavulin (+1.75), where an Attack opening's turn-1
  HP loss wakes it (the known effect in the build decision), so that row
  reads the early wake more than the card type. The Skill opening is the
  costly one elsewhere (Nob +0.80, Sentries +1.57): a Skill turn opening
  on turn 1 punishes Defend, the net's habit, a mild version of
  OppCard-Block's +0.49 and OppCard-Frail's +0.87.
- **Against table24's card-played row (+1.62):** a punishment that moves
  each turn costs the net less than a fixed one with a costly effect;
  table24's costly card-played rows were Damage and Weak, and Strength on
  the enemy is the cheapest effect there (+0.84 by effect). The cycle
  being predictable or not is not what this read prices.

CPU: 0781 ran 76 minutes at 3 threads, 3.8 cpu-h (the lane's queued CPU),
against the lane's 2.5 cap (the build decision estimated 1.5; the
estimate was low, as 0470's was).

What it changes: no new costly row for goal 1's table and no held-out
candidate for 47 from this form. The random form (second form, needs
chance in hooks) would price unpredictability on its own, but this read
says the effect it would carry (Strength, +-5% HP) is the cheap kind; a
fickle enemy worth reading again punishes with Weak or Damage.

## Generated training pack (lane generated-pack-scratch)

`scripts/gen_enemy_pack.py` writes `content/packs/gen-enemies-train.json`
(`--check` exits 1 if the committed file differs): the bench's 18
training-split mechanics (all but GE-AttackLoss-Damage, GE-AttackLoss-Weak,
GE-OppCard-PlainDamage, GE-OppCard-Damage, GE-TurnEnd-Weak, GE-TurnEnd-Frail;
each held-out trigger and effect appears in some training pair) as start
powers on copies of the ten official monsters without native code or a
split (Cultist, Jaw Worm, the S and M slimes, Fungi Beast, Looter, Gremlin
Nob, Sentry): 180 monsters, `<base> <mechanic>`, stacks drawn by a fixed
hash from max(1, k // 2) .. 2k (k the bench's stacks). Powers are the
bench's own (`mutate_monsters.gen_pack`), so both load in one process.
Encounters `GP <id>`: each official hallway or elite encounter holding a
base monster, one `one_of` over the mechanics with every base monster
replaced (louse, Lagavulin and the L slimes stay official): 8 hallway, 2
elite. With the Act 1 pack a learn plays them on 8/22 = 0.36 of hallways and
2/5 = 0.40 of elites (`selfplay.with_pack_encounters`). Pinned by
`scripts/tests/test_gen_enemy_pack.py`. Learn config:
`configs/genpack40k-s1.json` (packnet40k-s1 plus this pack); 0779 found the
40k one-round recipe weaker off its content, so per the charter the
navigator re-sets the recipe before the learn is queued.

### Base read (job 0797, results/mutate/gen-pns1-tsl1-all24.json)

Pack net seed 1 (`runs/2026-11-10-packnet40k-s1-r1-64badf9/model.pt@tsl1`)
and the heuristic on all 24 rows plus parent, 675 official elite starts x
8 seeds, generated pack f12ea528 (pin 0fc3d28; 79 min against an 80-minute
estimate). The check in its note holds: on the 8 rows it shares with
`results/mutate/gen-pns1-tsl1.json` (16 seeds, job 0762) the win-rate
difference is at most 0.004 (0.003), every row within 1.3 se, so the two
files agree.

Novelty cost (`read-gen`: the net's HP lost minus the heuristic's, beyond
the same on parent; mean (se) over starts), elites pooled:
- held-out rows: AttackLoss-Damage +10.25 (0.52), OppCard-Damage +7.33
  (0.43), OppCard-PlainDamage +6.84 (0.40), TurnEnd-Weak +3.49 (0.23),
  AttackLoss-Weak +2.53 (0.31), TurnEnd-Frail +0.57 (0.13); mean +5.17;
- the 18 training rows: mean +1.99, from OppCard-Weak -4.05 (0.58) to
  AttackLoss-Vulnerable +5.65 (0.36); 23 of 24 rows cost beyond 2 se.

So the held-out rows cost the pack net more than the training rows before
any generated content is trained: there is room for a cut of 0.4 (about
2 HP a fight pooled). The largest held-out cost, AttackLoss-Damage, sits
on Gremlin Nob (+20.58 (1.05)), where a net that attacks into a
damage-on-hit power pays most. This file is the base for step 3's
`compare` (same starts, seeds and pack).

Recipe: the navigator kept step 2's recipe (decisions "pns-gen-attribution
read", step 2b added: a second self-play round if seed 1 passes the cut
bar and fails the 10-29 bar), so the learn is queued as configured.

### Learn (job 0803, runs/2026-11-10-genpack40k-s1-r1-acf5102)

`configs/genpack40k-s1.json`, seed 1, pin cdcee38: 145 min at 6 threads
(estimate 135; 0749 ran 112, the generated encounters and C6's pin add
the rest), peak 5.18 GB as counted by the runner. Round 1 reaches the
heuristic on both halves, as 0749's did. Val MSE: round 0 0.1535, round 1
0.1713, against packnet40k-s1's 0.1443 and 0.1521; the val set is drawn
from the same packs (dataset eb05af100c1a, with the generated encounters),
so the two numbers are not on one set and say nothing about strength. The
log does not count the generated encounters played; their share is the
configured 0.36 of hallways and 0.40 of elites. Step 3 is queued at pin
d2cab2b: 0809 (the 24 rows @tsl1, heuristic column included for the
same-play check), 0810 (cells), 0811 (31-card pack headline), each read
against pack-net-scratch seed 1's file.

### Seed-1 read (jobs 0809, 0810; 0811 refused)

**Rows (0809, results/mutate/gen-gp1-tsl1-all24.json; 67 min against
85).** Same play check holds: the heuristic's games equal 0797's in all
16 875 cells (675 starts x 25 contents). Novelty cost in HP lost (net
minus heuristic, beyond the same on the parent; paired by start, mean
(se)), the base pack net (0797) then the generated-pack net, and the
gain:

| mechanic (held out) | base | genpack | gain | cut |
|---|---|---|---|---|
| AttackLoss-Damage | +10.25 (0.52) | +1.40 (0.24) | +8.84 (0.43) | 0.86 |
| OppCard-Damage | +7.33 (0.43) | +1.16 (0.19) | +6.17 (0.41) | 0.84 |
| OppCard-PlainDamage | +6.84 (0.40) | +2.65 (0.20) | +4.19 (0.35) | 0.61 |
| TurnEnd-Weak | +3.49 (0.23) | +1.42 (0.18) | +2.07 (0.22) | 0.59 |
| AttackLoss-Weak | +2.53 (0.31) | -1.27 (0.27) | +3.81 (0.26) | 1.50 |
| TurnEnd-Frail | +0.57 (0.13) | +0.53 (0.11) | +0.03 (0.15) | 0.06 |
| **held-out pooled** | +5.17 (0.21) | +0.98 (0.13) | +4.18 (0.20) | **0.81 (0.02)** |
| training pooled (18) | +1.99 (0.12) | -1.22 (0.13) | +3.22 (0.15) | 1.62 (0.08) |

The cut's se is the delta method over per-start pooled values. Against the
10-29 net (results/mutate/gen-enemies-b1.json, same 675 starts) the
held-out pooled cost is +0.98 (0.13) against +4.21 (0.16): 3.22 (0.16) HP
better, so the 10-29 bar holds and step 2b is not needed. On the official
parents the genpack net loses 0.48 (0.14) HP less than the pack net. The
win-rate view (`compare`) agrees: cuts 0.85-1.52 on the held-out rows
except TurnEnd-Frail, whose base cost is within 1 se of zero.

Why, as far as the rows say: the held-out mechanics are new pairings of a
trigger and an effect that both appear in training pairs, on the same
eight base monsters the pack copies; the net learned the effects (damage
when the player attacks or plays a card, Weak) and carries them to the
unseen pairs at 0.6-0.9 of what the training pairs get. The two Frail
rows (TurnStart-Frail -0.33 (0.14), training; TurnEnd-Frail held out)
are the only ones not cut: Frail barely costs the heuristic either, so
there is little to learn. On three training Vulnerable rows the net now
beats the heuristic by 6-9 HP beyond parent (cuts over 2): what training
gains is not only a repair of the novelty cost. So the zero-shot transfer
this reads is to recombined mechanics, not to an unseen trigger or effect.

**Cells (0810, results/gauntlet/genpack40k-s1-hpb0.01-cells.json).**
Paired end HP against pack-net-scratch seed 1 (0753): +0.40 (0.52), train
half +0.99 (0.72), held-out half -0.19 (0.74); clears 0.682 against 0.648
(+0.034 (0.013)). Within the -1.5 HP side bar.

**Pack headline (0811): refused.** The control (0752) was played on
act1-ironclad.json@dbec2dc1, before the owner's C6 rewrote the pack
(upgrades as data, Armaments); 0811's pin plays d3cdb427, and
`--against` refuses a pack mismatch. Both nets are replayed on the
current pack (sequences 0-499) and read paired; step 4 waits on that.

**Pack headline (0814 control, 0815 genpack, 0816 paired check; both on
the post-C6 pack, sequences 0-499).** Paired end HP, genpack minus
pack-net-scratch seed 1: +0.17 (1.13) over 500 (train half +0.72 (1.60),
held-out half -0.38 (1.60)); clears 0.656 against 0.606, +0.050 (0.028),
train +0.068 (0.043), held-out +0.032 (0.035). Within the -1.5 HP side
bar, so 0816 passed and the seed-1 read is a go. The genpack net dies less
at the Guardian (33 against 48) and Lagavulin (10 against 21) and a little
more at Gremlin Nob (23 against 17); the clears gain is about 1.8 se, a
lead only. C6 itself barely moved the control: pack-net-scratch seed 1
cleared 0.600 on the pre-C6 file (0752) and 0.606 on the post-C6 one.

**Seed-1 verdict: go.** Held-out pooled cut 0.81 (0.02) against a 0.4 bar,
10-29 bar held, cells +0.40 (0.52), pack headline +0.17 (1.13). Step 4
runs: learns 0817 (seed 101) and 0818 (seed 201); their controls
(pack-net-scratch seeds 101 and 201 on the 24 rows and on the post-C6
pack headline) are queued now, as they don't wait on the learns. A
single seed's go is a lead; the lane's result is the three seeds pooled.

### Seed-101 read (jobs 0851, 0852, 0853; controls 0826, 0769, 0827)

Learn 0847 (`configs/genpack40k-s101.json`, runs/2026-11-11-genpack40k-s101-r1-065b3ff):
119 min, peak 6.46 GB (mem_gb 2.5). All three reads at the controls' pin
e54c5ba. Numbers from `scripts/analysis/genpack_cut.py` (new; it
reproduces the seed-1 table above to the last digit).

**Rows (0851, results/mutate/gen-gp101-tsl1-all24.json; 65 min against
85).** Against pack-net-scratch seed 101 (0826), novelty cost beyond parent
in HP, paired by start:

| mechanic (held out) | base | genpack | cut |
|---|---|---|---|
| AttackLoss-Damage | +3.90 (0.31) | +1.91 (0.31) | 0.51 (0.07) |
| OppCard-Damage | +7.78 (0.42) | +1.31 (0.20) | 0.83 (0.02) |
| OppCard-PlainDamage | +7.83 (0.42) | +3.07 (0.21) | 0.61 (0.02) |
| TurnEnd-Weak | +4.40 (0.24) | +2.41 (0.22) | 0.45 (0.05) |
| AttackLoss-Weak | +4.11 (0.35) | -0.45 (0.31) | 1.11 (0.08) |
| TurnEnd-Frail | +1.66 (0.14) | +1.23 (0.11) | 0.26 (0.07) |
| **held-out pooled** | +4.95 (0.20) | +1.58 (0.15) | **0.68 (0.03)** |
| training pooled (18) | +3.05 (0.14) | -0.54 (0.14) | 1.18 (0.05) |

10-29 bar: the 10-29 net's held-out cost +4.21 (0.16) against +1.58 (0.15),
2.62 (0.17) HP better: holds. The cut is smaller than seed 1's (0.81)
mostly because of AttackLoss-Damage: seed 101's base net already pays
only +3.90 there (seed 1's +10.25, Gremlin Nob), so there is less to cut,
and the genpack net keeps a similar +1.9. The base nets differ more
between seeds than the genpack nets do: held-out genpack cost +0.98 and
+1.58, base +5.17 and +4.95, but per row the bases differ by up to 6 HP.
TurnEnd-Frail is cut a little this time (0.26 (0.07); seed 1 0.06 (0.25)).

**Cells (0852, against 0769).** Paired end HP +0.27 (0.54), train half
+1.44 (0.72), held-out half -0.90 (0.80); clears 0.642 against 0.628.
The genpack net dies more at Three Sentries (22 against 13); seed 1 did not
(13), so that is one seed's spike, not a pattern yet.

**Pack headline (0853, against 0827).** Paired end HP +0.15 (1.05), train
-0.56 (1.53), held-out +0.85 (1.45); clears 0.606 against 0.580. Fewer
Guardian (41/47) and Lagavulin (20/27) deaths, the same direction as seed 1.

**Two seeds pooled (1, 101; not the verdict).** Held-out cut 0.75 (starts
se 0.02, seed spread 0.06), training 1.35; 10-29 bar +2.92 (0.15) HP; cells
+0.33 (0.37) (held-out half -0.55 (0.54)); pack headline +0.16 (0.77). Every
bar holds with room; seed 201 (learn 0848 done; reads 0885 rows, 0886 cells,
0887 pack headline, queued at e54c5ba) completes the pooled read.

### Seed-201 read and the pooled verdict (jobs 0885, 0886, 0887; controls 0828, 0768, 0829)

All three reads at the controls' pin e54c5ba; the heuristic columns of
0885 equal 0828's on all 675 starts. Numbers from
`scripts/analysis/genpack_cut.py`.

**Rows (0885, results/mutate/gen-gp201-tsl1-all24.json; 55 min against
90).** Against pack-net-scratch seed 201, novelty cost beyond parent in HP:

| mechanic (held out) | base | genpack | cut |
|---|---|---|---|
| AttackLoss-Damage | +7.94 (0.40) | +1.77 (0.23) | 0.78 (0.02) |
| OppCard-Damage | +7.54 (0.39) | +1.17 (0.16) | 0.84 (0.02) |
| OppCard-PlainDamage | +7.61 (0.39) | +3.26 (0.23) | 0.57 (0.02) |
| TurnEnd-Weak | +4.11 (0.24) | +2.16 (0.19) | 0.47 (0.04) |
| AttackLoss-Weak | +4.82 (0.37) | -1.67 (0.26) | 1.35 (0.07) |
| TurnEnd-Frail | +3.19 (0.23) | +0.90 (0.11) | 0.72 (0.03) |
| **held-out pooled** | +5.87 (0.24) | +1.26 (0.12) | **0.78 (0.02)** |
| training pooled (18) | +3.66 (0.14) | -0.75 (0.12) | 1.21 (0.03) |

Seed 201's base net pays the most of the three (+5.87; seeds 1 and 101
+5.17 and +4.95), and its genpack net lands between the other two
(+1.26; +0.98 and +1.58): again the base nets spread more across seeds
than the genpack nets do. TurnEnd-Frail, cut little by seeds 1 and 101,
is cut 0.72 here because this base pays +3.19 on it (seeds 1 and 101
+0.57 and +1.66); the genpack nets pay +0.5 to +1.2 on it at every seed,
so its cut follows how much the base happens to pay.

**Cells (0886, against 0768's file).** Paired end HP +0.89 (0.50), train
half -0.34 (0.74), held-out half +2.11 (0.66); clears 0.676 against 0.668.
Deaths: Three Sentries 12 against 19 (seed 101's spike, 22 against 13,
does not recur), Gremlin Nob 9 against 15, The Guardian 36 against 25.

**Pack headline (0887, against 0829's file).** Paired end HP +0.91 (1.09), train half +0.52 (1.49), held-out half +1.31 (1.58); clears 0.636 against 0.608 (45 min against 55). Deaths: Gremlin Nob 18 against 25, Slime Boss 21 against 27, Hexaghost 37 against 40, The Guardian 33 against 37; Lagavulin and Three Sentries level. Fewer Guardian deaths again, as at seeds 1 and 101.

**Pooled over seeds 1, 101, 201 (the verdict).** Held-out cut **0.76**
(starts se 0.02, seed spread 0.04; the bar reads 0.04): 0.4 at 2 se holds
by a wide margin. Per held-out mechanic, pooled: AttackLoss-Damage 0.77,
OppCard-Damage 0.84, OppCard-PlainDamage 0.60, TurnEnd-Weak 0.50,
AttackLoss-Weak 1.30, TurnEnd-Frail 0.51. Training rows: cost +2.90
(0.11) for the base, -0.84 (0.10) for the genpack nets (cut 1.29): on the
mechanics it trained on, the genpack net does better on a mutated elite
than on its parent, relative to the heuristic. 10-29 bar: the 10-29 net's
held-out cost +4.21 (0.16) against the genpack nets' pooled +1.28 (0.11),
better by +2.93 (0.14) HP: holds. Cells pooled +0.52 (0.30) HP over 1500
sequences (train +0.70 (0.42), held-out +0.34 (0.43)): within -1.5 HP,
and if anything up. Pack headline pooled +0.41 (0.63) HP over 1500 sequences (train +0.23 (0.89), held-out +0.59 (0.89)). **Go**: every bar of
the stop rule holds.

What it means for goal 1: a net trained from scratch on a space of
generated enemy mechanics (18 training mechanics as start powers with
varied amounts, on at most half the monster fights) plays six mechanics it
never saw at about a quarter of the zero-shot cost of the same recipe
without them, and below the 10-29 net's cost, with no loss on official
cells or the pack headline. The remaining held-out cost (+1.28 HP per
elite fight) sits mostly on OppCard-PlainDamage (+3.0) and TurnEnd-Weak
(+2.0): one punishes playing cards with damage that block does not stop,
the other is a recurring debuff, the kind the closed lane
recurring-debuff-leaf tried to price (it cut the Weak rows by a fifth).
Limits: one turn deep @tsl1, elite starts only, one mechanic per fight,
mechanics from the same 24-cell grid (trigger x effect) as the training
split, so "unseen" means an unseen combination of seen triggers and seen
effects, not a new trigger or effect.

## Wider grid (lane wider-generators)

Spec `docs/specs/wider-generators.md`. `mutate_monsters.py` now holds 100
mechanics: the old 24 unchanged (they replay as job 0885's: 8 elite starts,
3 rows and parent, heuristic, 8 seeds, 32 of 32 identical) and 76 new over
9 triggers (the old four, RoundEnd, Attacked, AttackHit, OppAttack,
OppSkill) and 12 effects (the old seven, StrDown, DexDown, Artifact, Wound
into the discard pile, Dazed into the draw pile), minus pairs an official
power holds. Split of the new 76 (`WIDE_SPLIT`): whole trigger Attacked
(11), whole effect Wound (8), 17 held-out pairs, 40 training. A card added
by a hook doesn't scale with stacks (`Effect::scaled`, both in play and in
the net's rows): one Wound or Dazed per firing. The wide pack
(`content/packs/gen-enemies-wide.json`, `gen_enemy_pack.py --wide`): the
old 18 and the new 40 training mechanics on both elites and one
single-base hallway each, 174 copies (the engine holds at most 236 pack
monsters, so not 58 x 10); generated shares 4/18 of hallways, 2/5 of
elites. Learn config `configs/widepack40k-s1.json` (genpack40k-s1 with the
wide pack). Read: `genpack_cut.py --wide --pair <base> <genpack>`.

Smoke run (20 elite starts x 2 seeds, the seed-1 generated-pack net): the
new held-out pairs cost it +2.9 (0.9) HP beyond parent; too few starts to
read, only that the rows play.

### Predictions for step 2 (written before the read)

- The seed-1 generated-pack net's pooled cost on the new held-out pairs is
  over the 1 HP fail-fast: about +2 to +3 HP (many new atoms act through
  the player's deck or on the player's stats, which its 18 training
  mechanics never did), so the lane goes on to the learn.
- pack-net-scratch seed 1 pays more on every new group than the generated
  pack net (+3 to +5 HP): the old pack's value per mechanic moves some way
  to new atoms on the same columns (cut 0.2-0.4 on new pairs, about 0 on
  the whole trigger and effect).
- The largest single new costs sit on Artifact (it cancels Bash's
  Vulnerable) and the Dazed and Wound rows on the per-card triggers.

### Step 2 read (jobs 0896, 0897, 0898; 2026-11-11)

675 official elite starts x 4 seeds, both nets @tsl1 one turn deep, novelty
cost beyond parent in HP, mean (se) over starts (`genpack_cut.py --wide`,
log `logs/jobs/0898-genpack-cut.log`). The heuristic columns of the two
files are identical (51,975 of 51,975 cells), so the pairing holds.

| group | rows | pack-net-scratch s1 (base) | generated-pack s1 | cut |
|---|---|---|---|---|
| new held-out pairs | 17 | +4.01 (0.16) | +1.59 (0.14) | 0.60 (0.03) |
| whole trigger Attacked | 11 | +5.66 (0.20) | +1.07 (0.18) | 0.81 (0.03) |
| whole effect Wound | 8 | +1.00 (0.16) | +1.10 (0.15) | -0.11 (0.17) |
| new training pairs | 40 | +4.21 (0.15) | +1.05 (0.14) | 0.75 (0.03) |

**Fail-fast: does not fire.** The generated-pack net still pays +1.59 HP
on the new held-out pairs, 4 se above the 1 HP bar, so the learn 0899
(the wide pack, seed 1) runs; checkpoint step2-failfast passed.

Why, as far as the rows show:
- The 18-mechanic grid's value carries out of its own grid, but less of
  it: cut 0.60 on new pairings against 0.76 inside the grid
  (`measurement/genpack-transfer@three-seeds`). What is left, 1.6 HP, is
  the wide learn's room.
- The whole trigger is not novel in behaviour. Attacked fires on every
  attack hit on the monster; the old AttackLoss fires when an attack makes
  it lose HP, and OppAttack (on every attack the player plays) is in the
  new training pairs. The net met the same situations under another
  trigger's name, and Flame Barrier trains the `OwnerAttacked` row; so a
  cut of 0.81 says the effect columns and the situation carry, not that a
  never-seen trigger transfers. Step 2b (zeroing the trigger column) is
  the check on how much rides on the name.
- The whole effect costs little to begin with: one Wound into the discard
  pile per firing costs the scratch net 1.0 HP, and both nets pay the
  same. There is nothing to cut; the row says nothing about transfer.
- The largest costs are the DexDown rows on the attack triggers:
  Attacked-DexDown and OppAttack-DexDown cost the scratch net +26 HP and
  the generated-pack net +4 to +5 (it learnt not to attack into a
  punishing on-attack trigger from the old Damage and Weak rows). The one
  training row neither net handles is OppCard-Artifact (+10 to +11 HP,
  cut -0.09): Artifact on every card played cancels Bash's Vulnerable and
  every debuff, and no old row taught that.

Against the predictions: the generated-pack net's cost (+1.59) is under
the predicted +2 to +3; the base's (+4.0) is inside its range; the whole
trigger's cut (0.81) is far from the predicted 0, for the reason above;
the whole effect's cut is about 0, as predicted; the largest single costs
are DexDown, not Artifact or the card rows, except OppCard-Artifact.

### Step 3 read (jobs 0926, 0914-0921; headline resumed as 0945; 2026-11-12)

The wide net is `runs/2026-11-12-widepack40k-s1-r1-1d2c208` (learn 0926,
60 min at 6 threads); the base is the seed-1 generated-pack net. Both
@tsl1 one turn deep on the rows, @hpb0.01 on the gauntlets.

New rows (0916 against step 2's 0896 file; `genpack_cut.py --wide`, log
`logs/jobs/0921-genpack-cut.log`), 675 elite starts, novelty cost beyond
parent in HP:

| group | rows | generated-pack s1 (base) | wide s1 | cut |
|---|---|---|---|---|
| new held-out pairs | 17 | +1.59 (0.14) | +0.25 (0.15) | 0.84 (0.09) |
| whole trigger Attacked | 11 | +1.07 (0.18) | +0.52 (0.18) | 0.51 (0.16) |
| whole effect Wound | 8 | +1.10 (0.15) | +0.05 (0.17) | 0.95 (0.15) |
| new training pairs | 40 | +1.05 (0.14) | +0.03 (0.15) | 0.97 (0.14) |

Old 24 rows (0917, 4 seeds, against `gen-gp1-tsl1-all24.json` on the
shared starts and seeds; `genpack_cut.py --pair`): held-out 6 rows +0.98
(0.13) to +0.10 (0.15), gain +0.88 (0.16); training 18 rows -1.22 (0.13)
to -0.99 (0.16), worse by 0.23 (0.15), under 2 se. The heuristic games of
the two files are identical (33,900 of 33,900), so the rules did not move.

One-turn cells (0918 against 0914, fixed n 500): clears 0.682 to 0.668
(-0.014, se 0.013), paired end HP -0.25 (0.55) (train +0.22, held-out
-0.71). The protocol's "fail" is the +1.5 HP SPRT (no gain), not the
lane's bar; within -1.5 HP holds.

Post-C6 pack headline (0919 against 0915): the job was lost at 17:35 with
350 of 500 sequences in its file; at 350 paired end HP -1.45 (1.23),
clears 0.654 to 0.646 (held-out 0.731 to 0.680; the Guardian kills 32
against 23). `gauntlet.py play` resumes from its `--out` file, so 0945 (at
0919's pin 45c445b) plays sequences 350-499 into the same file; the bar is
read at fixed n 500.

k-4 random worlds (0920; 40 main worlds of the old 24 mechanics, start-HP
cap, the Stacks section's measure, paired by world): +3.16 (0.18) to
+2.48 (0.15), paired -0.67 (0.14), ratio 0.79. Most of these worlds' items
train both nets; descriptive.

So far against step3-go: the held-out-pair cut (0.84, 9 se) clears 0.4 at
2 se; the old rows are not worse (held-out better by 0.88 HP, training
-0.23 under 2 se); cells within -1.5 HP. The headline decides it.

Why, as far as the rows show:
- The wider grid reaches its own new pairings: a held-out pairing of a
  trained trigger and a trained effect costs 0.25 HP, as the training
  pairs (0.03) nearly. The old grid's six held-out rows gain as much
  (+0.88 HP): more pairings of the same columns teach the columns, not the
  pairs.
- A whole trigger never seen on an enemy keeps half its cost (0.52 HP):
  Attacked-Frail (+0.52 to +1.41), Attacked-Damage (cut 0.23) and
  Attacked-Dazed (0.14) stay; the DexDown and StrDown rows on it are cut.
  The trigger's name (and the situations behind it) is what the wide pack
  adds least to; step 2b's trigger-column zeroing is the check.
- The RoundEnd rows are trained but stay costly: RoundEnd-Damage +2.26 to
  +2.30 (cut 0) and RoundEnd-Weak cut 0.23, the RoundEnd finding of the
  backlog's open question 2 (lane `genpack-burst-base`). OppCard-Artifact,
  the step-2 outlier, is cut to +0.29 (cut 0.97) once trained.
- The price of the wider pack on old training rows (0.23 HP, not
  significant) fits the dilution of 18 mechanics into 58 at the same
  generated shares.

### Step 3 headline and verdict (job 0945; 2026-11-13)

0945 played sequences 350-499 into 0919's file at the same pin, so the
file holds 500 sequences of one player build. Paired against 0915's file
(the seed-1 generated-pack net, same settings, all 500 cells matching),
@hpb0.01 one turn deep on the post-C6 pack headline:

| part | n | paired end HP (wide - base) | clears base -> wide |
|---|---|---|---|
| all | 500 | -0.80 (1.05) | 0.654 -> 0.642 (-0.012 (0.026)) |
| train half | 250 | -0.66 (1.36) | 0.572 -> 0.632 (+0.060 (0.036)) |
| held-out half | 250 | -0.94 (1.60) | 0.736 -> 0.652 (-0.084 (0.036)) |
| sequences 0-349 | 350 | -1.45 (1.23) | |
| sequences 350-499 | 150 | +0.74 (1.99) | |

Within -1.5 HP at fixed n 500, so **step3-go passes**: the held-out-pair
cut 0.84 (0.09), the old 24 rows not worse, cells -0.25 (0.55) and the
headline -0.80 (1.05) all meet the charter. The lane closes on a go.

Sceptical notes, for whoever builds on it:
- The bar is a point bar and the headline's se is 1.05: the read says
  "no large loss", not "level". A true loss of up to about 2.9 HP at 2 se
  is not ruled out.
- The halves move in opposite directions on clears: the train half gains
  6 points, the held-out half loses 8.4 (2.3 se). The held-out half's
  extra deaths are bosses: the Guardian 23 against 13, Slime Boss 11
  against 5 (Hexaghost 19 against 16); the train half loses fewer to
  Hexaghost (23 against 30). End HP at the boss is 2.4-2.7 lower on both
  halves (57.0 against 59.5 over the 387 sequences both reach). With
  boss deaths this lumpy (a boss swings a sequence's end HP by its whole
  HP), the split is as likely one seed's boss luck as a real held-out
  cost; it is a lead for a second seed (candidate 65 trains seeds 101 and
  201 on the wide recipe and reads the headline), not a finding.
- The first 350 and the last 150 sequences differ by 2.2 HP (se about
  2.3): no sign that the resume changed anything.

## Product depth (lane genpack-product-depth)

Spec `docs/specs/genpack-product-depth.md`. The question: does the
generated-pack recipe's one-turn cut (0.76, `measurement/genpack-transfer@three-seeds`)
hold when both nets play as the product, two turns deep? Bench: the 6 old
held-out generated rows and their parents on the first 298 official elite
starts (200 elite) x 2 seeds, novelty cost = (player - heuristic) on the
mechanic minus the same on the parent, in HP lost.

### Step 1, the product's own cost (job 0907, results/mutate/gpd-product.json)

The product (10-29 net, two turns, line seed, stepped line) pays a held-out
pooled novelty cost of **+1.46 (0.33) HP** over 200 elite starts x 2 seeds.
The fail-fast (under 1.0 HP: the second turn already prices these
mechanics) does not fire, though 1.0 is only 1.4 se away.

Why it is this small: one turn deep, the 10-29 net pays about 4.2 HP on
the same 6 mechanics (the generated-pack net's 1.28 plus the 2.93 by which
the 10-29 net is worse, `measurement/genpack-transfer@three-seeds`; other
starts and seeds, so a rough comparison). The second turn of search
removes about two thirds of the cost of an unseen enemy mechanic without
any training on it. What is left is what the genpack net could still cut.

| held-out mechanic | product cost, HP (se) |
|---|---|
| OppCard-Damage | +2.27 (0.47) |
| OppCard-PlainDamage | +2.02 (0.46) |
| AttackLoss-Damage | +1.61 (0.44) |
| TurnEnd-Weak | +1.36 (0.61) |
| AttackLoss-Weak | +0.90 (0.75) |
| TurnEnd-Frail | +0.57 (0.27) |

The damage-on-card-play rows cost most, as one turn deep (there
OppCard-PlainDamage kept the largest residual, +3.00, after genpack
training): damage that lands when the player plays a card is the part
search sees least well, since it scales with how many cards the line
plays. By encounter: Three Sentries +2.52, Gremlin Nob +1.03, Lagavulin
+0.92 (pooled over the 6 rows). On the parents the product loses 2.0
(0.38) HP less than the heuristic (13.9 against 15.9 HP lost a fight).

What it changes: the room for the genpack net two turns deep is at most
+1.46 HP a fight on these rows, +2.05 (0.59) on the first 100 starts
(67 elite), the starts step 2 shares.

### Step 1, seed-1 cut (job 0928, results/mutate/gpd-gp1.json; 0908 killed, see decisions)

The generated-pack seed-1 net as the product, on the 67 shared elite starts
x 2 seeds (`genpack_cut.py --player product`):

- held-out pooled cost: base (the product) +2.05 (0.59), genpack +0.27
  (0.53); gain **+1.77 (0.48) HP**, **cut 0.87 (se 0.23)**; cut - 2 se =
  0.399, at the go bar of 0.4 (the stop rule prints "between");
- parents: genpack ends -0.10 (0.41) HP against the product (bar -1.5);
- per mechanic, cut (se): AttackLoss-Damage 0.70 (0.43), AttackLoss-Weak
  3.71 (3.93) (genpack -3.74 (1.40): it does better on that row than on
  the parent), OppCard-PlainDamage 0.24 (0.22), OppCard-Damage 0.60
  (0.20), TurnEnd-Weak 0.40 (0.27), TurnEnd-Frail 0.76 (0.24);
- without AttackLoss-Weak: cut 0.51 (0.17), gain +1.11 (0.43).

Sceptical read: the pooled cut sits exactly at its bar and leans on the
noisiest row; on the other five the cut (0.51) is below one turn's 0.76
but clearly above 0. OppCard-PlainDamage stays the one mechanic genpack
training barely helps, at both depths. So the recipe's transfer survives
the second turn of search, at a lead's strength: one seed, 67 starts.
Seeds 101 and 201 (0929, 0930) decide; read them pooled, with and
without AttackLoss-Weak.

### Step 2 runs (jobs 0929, 0930; resumed as 0937, 0938)

0929 (seed 101) and 0930 (seed 201) ran at 1 thread from 12:39 and died
with the job runner about 17:35 (records `ended-unknown` and `lost`, no
exit code). Their partial files hold 692 and 694 of 938 fights; neither
gained a line after 16:39, so the last hour was already stuck (paging
beside the 6.8 GB wide learn 0926 is the likely cause, as with 0908). The
partials are kept and 0937/0938 resume from them with the same command
and pin d2e6eb5; the pooled read waits for both.

### Step 2 pooled read and verdict (jobs 0928, 0937, 0938)

`genpack_cut.py --player product` over the three pairs (gpd-product
against gpd-gp1, gpd-gp101, gpd-gp201; 67 shared elite starts x 2 seeds,
both players two turns deep with the product's flags):

| seed | genpack held-out cost, HP (se) | gain over the product | cut (se) | cut without AttackLoss-Weak |
|---|---|---|---|---|
| 1 | +0.27 (0.53) | +1.77 (0.48) | 0.87 (0.23) | 0.51 (0.17) |
| 101 | +1.32 (0.73) | +0.73 (0.62) | 0.36 (0.29) | 0.02 (0.30) |
| 201 | +0.86 (0.69) | +1.19 (0.71) | 0.58 (0.31) | 0.28 (0.31) |
| pooled | +0.82 (0.52) | +1.23 (0.47) | **0.60 (starts se 0.20, seed spread 0.15)** | **0.27 (0.19)** |

The product's own held-out cost on these starts is +2.05 (0.59) HP
(+2.18 (0.52) without AttackLoss-Weak). Parents: the genpack nets end
-0.39 (0.48) HP against the product, inside the -1.5 bar.

Per mechanic, pooled cut (se): AttackLoss-Damage 0.67 (0.36),
AttackLoss-Weak 3.24 (3.40) (genpack -3.09 (1.33): better than on the
parent), OppCard-PlainDamage -0.09 (0.26), OppCard-Damage 0.30 (0.21),
TurnEnd-Weak 0.32 (0.30), TurnEnd-Frail 0.38 (0.19).

**Verdict: between** (the stop rule as `genpack_cut.py` and the step-1
read apply it: go needs cut - 2 se >= 0.4; 0.60 - 0.40 = 0.20; fail
needs a cut under 0.2 or under 2 se; 0.60 is 3 se from 0). The charter
allows one read, so the lane closes on it.

Sceptical read:
- Seed 1 was the lucky seed. The step-1 lead (0.87, at its bar) shrank
  to 0.60 pooled, as a single seed at its bar tends to; seeds 101 and
  201 sit at 0.36 and 0.58.
- The pooled 0.60 leans on AttackLoss-Weak, the noisiest row (se 3.4 on
  its cut), where the genpack nets beat their own parent result. Without
  it the pooled cut is 0.27 (0.19): by the same rule that is a fail (not
  2 se). Robustly, the recipe cuts a quarter to a half of what the
  second turn leaves.
- In HP the room is small. One turn deep the recipe took the held-out
  cost from +5.33 to +1.28 against pack-net-scratch
  (`measurement/genpack-transfer@three-seeds`); two turns deep the
  product (the 10-29 net) already pays only about +2 HP, and the genpack
  nets take about 1.2 of it (0.6 without the noisy row). The second turn
  of search does most of the pricing that training does one turn deep.
- OppCard-PlainDamage stays uncut at both depths (-0.09 (0.26) here): damage
  per card the player plays is the one pairing neither search nor the
  recipe prices; it is the place where a feature or a leaf term could
  still pay.
- 67 elite starts x 2 seeds is thin: starts se 0.20 is larger than the
  seed spread, so more starts, not more seeds, would tighten this read
  (about 13 more CPU-h for all 200 starts, past the cap).
- The k-4 random-world rows (descriptive in the charter) did not run: the
  cap went on two stalls (0908, 0929/0930) and the resumes.

What it changes: the generated-pack recipe still pays two turns deep,
but at about half its one-turn strength, and much of its gain one turn
deep is what the second turn of search gives anyway. Goal-1 changes
judged at product depth should expect costs of about 2 HP to work
against, not 5; OppCard-PlainDamage is the open row.

## Mechanic count (lane mechanic-count-curve; read by the navigator, jobs 0905, 0906)

The lane closed at its cap before its read (decisions "Lane
mechanic-count-curve closed (2026-11-12)"); 0905 (the 6-arm net
`runs/2026-11-12-genpack6-40k-s1-r1-2d5163e/model.pt@tsl1` on the 24 GE
rows, `results/mutate/gen-gp6-1-tsl1-all24.json`) and 0906 (`genpack_cut.py
--trained <SIX>` against `results/mutate/gen-pns1-tsl1-all24.json`) ran on.
675 elite starts, HP beyond parent, mean (se over starts), one seed:

| rows | pns1 | 6-arm | cut | 18-arm s1 (spec) |
|---|---|---|---|---|
| held-out 6 | +5.17 (0.21) | +0.60 (0.12) | 0.88 (0.02) | cut 0.81 (0.02) |
| trained 6 (the six pack) | +1.49 (0.14) | -0.93 (0.14) | 1.62 (0.13) | -1.16 |
| neither 12 (in the 18-pack only) | +2.24 (0.13) | +0.34 (0.12) | 0.85 (0.05) | -1.26 |

Stop rule: **go** (0.88, 0.6 or more at 2 se). A pack of 6 mechanics that
holds every trigger and effect of the held-out pairs cuts their cost as much
as the 18-mechanic pack, on seed 1: the transfer rides on the atoms, not the
count. The 12 pairings neither split trained (their atoms all covered) are
cut 0.85, the same as the held-out 6; training a pairing itself is worth
about 1.6 HP more there (+0.34 against the 18-arm's -1.26). Single seed: a
lead, but it agrees with the wide net (58 mechanics, `gen-wp1-tsl1-all24.json`)
cutting the same 6 rows 0.98 (0.03): count from 6 to 58 moves the held-out
cut by 0.1.

Per held-out row the 6-arm, the 18-arm and the wide net leave the same
rows: OppCard-PlainDamage (6-arm +0.97, wide +1.29) and TurnEnd-Frail
(+0.88, +0.93, where pns1's whole cost is +0.57). Split by parent (a
per-start approximation of the cost, heuristic minus net on the mod minus
the same on the parent), OppCard-PlainDamage's remainder is Three Sentries
(pns1 +15.99, 18-arm +4.71, 6-arm +1.18, wide +2.94; Nob and Lagavulin
+0.5-0.9 on the 6-arm and wide nets), and TurnEnd-Frail is a leak on the
parents' side: every generated-pack net costs +0.4 to +1.6 on Gremlin Nob
and Lagavulin, where pns1 is -0.42 and +0.23 (the TurnEnd-Frail x
Lagavulin leak of `pack-retention`). What is left zero-shot one turn deep
on single-hook enemy pairings is about 0.1-0.6 HP pooled, on these two
spots.

## RoundEnd rows: the power is invisible to the net (navigator, 2026-11-13)

No CPU: a re-split of existing files and a read of the encoder. The
question was open question 2's RoundEnd finding (`docs/backlog.md`):
every RoundEnd row costs about 2 HP beyond parent on every recipe, the
wide pack's trained RoundEnd mechanics included.

Cost beyond parent, HP per elite fight (heuristic minus net on the mod,
minus the same on the parent, per start and seed), mean (se); the
`all24` files for the turn-trigger rows, the `gen-wide` files for RoundEnd:

| row | pns1 (no generated pool) | 18-mechanic s1 | wide s1 |
|---|---|---|---|
| TurnStart-PlainDamage | +2.76 (0.13) | -0.13 (0.11) | -0.22 (0.16) |
| TurnEnd-PlainDamage | +2.79 (0.13) | -0.09 (0.12) | -0.19 (0.16) |
| TurnEnd-Damage | +2.75 (0.13) | +0.29 (0.12) | +0.07 (0.17) |
| RoundEnd-PlainDamage | +2.57 (0.17) | +1.88 (0.15) | +1.90 (0.21) |
| RoundEnd-Damage | +2.48 (0.18) | +2.26 (0.17) | +2.30 (0.22) |

Wins move 0.015-0.019 on the RoundEnd rows: the cost is HP, largest on
Three Sentries (+3.4 to +3.9), where three monsters each hold the power.

Untrained, damage at the monster's turn start, turn end or round end costs
the same (about 2.5-2.8 HP). Training on the turn-trigger mechanics removes
that cost; training on nine RoundEnd mechanics (the wide pack) removes
none of it. In the engine the monsters' `OwnerTurnEnd` hooks and the
`RoundEnd` hooks run back to back after every monster has acted
(`engine/src/state.rs`, the round's end), so the two deal the same damage
at almost the same moment.

The encoder explains it. `py/src/features.rs` writes a power's `RoundEnd`
hooks only as `countdown` rows (`power_rows` filters them out of the
`triggered` rows; `power_kind_rows` writes them as kind `countdown`), and
`countdown` is an opt-in kind (decisions "Series row kinds are opt-in"):
every net here has `meta.row_kinds` = triggered, threshold, held
(the wide net, pns1; the 10-29 net predates the field). `is_hook_power`
also ignores `RoundEnd` hooks. So a generated power whose only hook is
`RoundEnd` gives the net no row at all: the net cannot see it, which is
why training on it cut nothing. Official content uses `RoundEnd` only for
the self-countdowns (Vulnerable, Weak, Frail, Intangible: `ReduceSelf 1`,
`content/powers.json`), so writing every other `RoundEnd` hook as a
`triggered` row changes no official input. The wide spec kept the default
kinds on purpose ("Row kinds of the step-3 learn") without this case in view.

Rows read with the blind encoding: every `RoundEnd` row in
`results/mutate/gen-wide-*.json` (the yardstick rows hold none). The
files stay as records of that encoding; they would not replay after a fix.
What follows: backlog candidate 71 (`roundend-rows`), folded into 65
(`wide-recipe-confirm`) as its step 0; `cause/roundend-blind`.

## Wide recipe confirm (lane wide-recipe-confirm)

### Control seeds (jobs 0960, 0961; 2026-11-13)

pack-net-scratch s101 and s201 @tsl1 on `gen-wide` (old encoding, same
command as 0897), `results/mutate/gen-wide-pns101-tsl1.json` and
`gen-wide-pns201-tsl1.json`. The heuristic columns match pns1's on all
675 starts x 4 seeds and the wide s1 file's on its 2 seeds (51,975 of
51,975 cells), so the pairing holds. `genpack_cut.py --wide`, each
control against the wide s1 net (`gen-wide-wp1-tsl1.json`), novelty cost
beyond parent in HP, mean (se) over starts:

| group | rows | pns1 | pns101 | pns201 | wide s1 | cut vs 1 / 101 / 201 |
|---|---|---|---|---|---|---|
| new held-out pairs | 17 | +4.01 (0.16) | +3.97 (0.17) | +2.88 (0.15) | +0.25 (0.15) | 0.94 / 0.94 / 0.91 |
| whole trigger Attacked | 11 | +5.66 (0.20) | +5.20 (0.19) | +3.78 (0.18) | +0.52 (0.18) | 0.91 / 0.90 / 0.86 |
| whole effect Wound | 8 | +1.00 (0.16) | +2.89 (0.21) | +1.98 (0.18) | +0.05 (0.17) | 0.95 / 0.98 / 0.97 |
| new training pairs | 40 | +4.21 (0.15) | +4.65 (0.16) | +3.09 (0.14) | +0.03 (0.15) | 0.99 / 0.99 / 0.99 |

Pooled over the three controls (per start, averaged): new held-out base
+3.62 (0.14), cut 0.93 (0.04).

What this says:
- The wide s1 net's cut is not an artefact of a lucky control seed: it
  stays at 0.91-0.94 against every control seed. The open question for the
  lane is the other side, whether the wide recipe's own seeds 101 and 201
  reach it (the charter's go bar is a three-seed pooled cut of 0.7).
- The control is far from constant across seeds. The new held-out cost
  runs +2.9 to +4.0 HP; single rows swing much more: Attacked-DexDown
  +26.3 / +19.0 / +4.2 and OppAttack-DexDown +26.8 / +18.6 / +3.5 (s201
  learnt not to attack into it), OppCard-Wound +1.8 / +6.9 / +2.5. A
  per-row cut against one control seed is not a measurement; pooled groups
  are.
- The parents' drift (net minus heuristic HP lost on the unmodified
  fight) is small for the controls (-0.1, -0.3, -0.8 HP) and +0.7 for the
  wide s1 net, almost all on Lagavulin (+4.9), as in the genpack-burst-base
  reads; the cost beyond parent subtracts it per start.
- The RoundEnd rows stay costly on every seed and the wide net cuts
  little of them: RoundEnd-Damage wide +2.30 against +2.48 / +2.93 / +2.85
  (cut 0.07-0.22), RoundEnd-Weak +1.72 against +2.89 / +3.33 / +2.07; only
  RoundEnd-Wound (cheap to begin with) moves. That is
  `cause/roundend-blind` again, now on three control seeds: step 0's room
  is about 2 HP on these rows.

No checkpoint: these files are the controls for the per-seed reads.

### Seed 201 of the wide recipe (jobs 1002-1006; read 2026-11-14)

Learn 1002 (`configs/widepack40k-s201.json`, current encoding, RoundEnd rows
blind) after three out-of-memory deaths; reads 1003-1006 ok. Controls are
pack-net-scratch s201 (`gen-wide-pns201-tsl1.json`, `gen-pns201-tsl1-all24.json`,
`packnet40k-s201-hpb0.01-cells.json`) and, descriptive, the 18-mechanic s201.
Commands: `genpack_cut.py --wide` and `--pair`, `--hp`; the yardstick by the
genpack-yardstick table's computation (it reproduces pns1 +4.03 and gp201 +2.01).

| read | wide s201 | control | verdict |
|---|---|---|---|
| new held-out pairs (17), cost beyond parent | +0.65 (0.17) | pns201 +2.88 (0.15) | cut 0.77 (0.06); s1 was 0.94 against pns1 |
| whole trigger Attacked / whole effect Wound | +0.02 / +0.70 | +3.78 / +1.98 | cut 0.99 / 0.65 |
| new training (40) | +0.80 (0.17) | +3.09 (0.14) | cut 0.74 |
| old 24 rows, held-out | +1.08 (0.16) | 18-mechanic s201 +1.26 (0.12); pns201 +5.87 | not worse |
| old 24 rows, training | -0.69 (0.17) | 18-mechanic s201 -0.75 | level |
| yardstick pooled 4 (sharp2, thorns2, ritual2, weakhit1) | +1.08 (0.23) | pns1 +4.03 (0.28); half is 2.02 | passes (sharp2 +0.97, thorns2 +2.30) |
| one-turn cells, paired against pns201 | -0.56 (0.55) (train -1.92, held-out +0.80) | | within -1.5 |

Why: the cut is lower than seed 1's (0.77 against 0.94), and seed 201's
control is the cheaper one (+2.88 against +4.01), so part of the gap is the
control's luck, not the wide net's. RoundEnd rows stay costly again
(RoundEnd-Damage +1.80, cut 0.37; RoundEnd-Weak +1.74, cut 0.16), as
`cause/roundend-blind` says. The yardstick edge holds on the second seed
(1.08 against seed 1's 0.92), so seed 1 was not luck there; thorns2 is still
the weakest row (+2.30). Two-seed pool (1, 201), new held-out cut against
pns: 0.87 (0.04) on a base of +3.45.

Checkpoint seeds-go: not decidable. Seed 101's learn and reads (1008-1012)
are parked (decision/nov14: nothing queued that ends after 14 Nov 08:00).
Seed 201 clears the per-seed fail line (cut 0.77, over 0.3) and every go bar.


## Burst base (lane genpack-burst-base)

Step 2, 11-game arm: joint bursts on GE-OppCard-Artifact and
GE-Attacked-Wound (11 games each, replay share 0.9, @tsl1), three seeds
per base, each read @tsl1 one turn deep on both rows and the parent
(1000 official elite starts x 4 seeds; 675 starts pair with the
zero-shot files). Cut = the drop in the row's HP lost beyond the parent
fight, against the base's own zero-shot file (`family.py`'s `gen_cut`,
control `parent`).

**Pooled cut, fixed before the pns arm is read:** per net, the sum of its
two rows' cuts over the sum of the base's two zero-shot costs (an HP
weighting, so Artifact counts about four times Wound); mean and se over
the three nets. The checkpoint compares the two bases' pooled shares
(go: gp ahead by 0.2 or more at 2 se, se the two arms' se over nets
combined; fail: within 0.1 or pns ahead) with parents within 1.5 HP.

### Generated-pack base, 11 games (jobs 0946-0952; files results/mutate/gbb-2026-11-13-gbb-gp1-g11-sh9-s{1,2,3}-*.json)

| row | zero-shot cost | cut (se starts / se nets) | share | per net |
|---|---|---|---|---|
| GE-OppCard-Artifact | +10.82 (0.56) | +5.29 (0.22 / 1.55) | 0.49 | +7.66, +2.37, +5.83 |
| GE-Attacked-Wound | +2.44 (0.27) | +2.61 (0.16 / 0.14) | 1.07 | +2.89, +2.51, +2.45 |
| pooled | +13.26 | +7.90 | **0.60 (se nets 0.12)** | 0.80, 0.37, 0.62 |

Parent fight: +0.14 HP lost after the burst (inside the 1.5 bar).
The family table (0952, Artifact only, rule "half the cost at 2 se over
nets") says fail at 0.49; that is the table's own rule, not the lane's
checkpoint, which waits for the pns arm (0953-0959).

Sceptical read:
- Wound is cut by all of its cost and more (1.07), on every net alike;
  Artifact by half, with a wide seed spread (seed 2 at +2.37 against
  +7.66 and +5.83). The pooled share rests on Artifact's noisy nets.
- Per encounter the cuts move with the parent fight's drift, which the
  control subtracts: after the burst the nets lose 1.1-1.6 HP more on
  plain Lagavulin and 0.5-1.2 HP less on plain Sentries. So Lagavulin's
  cuts run past its cost (Artifact +5.82/+1.13/+4.36 against +2.93;
  Wound about +4.6 against +1.75), and Sentries' Wound cut is negative
  (about -0.7 against +1.09). Part of each cut is the parent moving, not
  the row being learnt. The pns arm has the same control, so the
  comparison between bases stays fair; the absolute shares overstate
  what was learnt on Lagavulin.
- Sentries carries Artifact's cost (+21.85) and most of its cut
  (+12.31, +4.98, +11.98): the seed spread is the Sentries row.

### Pack-net-scratch base, 11 games, and the checkpoint (jobs 0953-0959; files results/mutate/gbb-2026-11-13-gbb-pns1-g11-sh9-s{1,2,3}-*.json)

Same recipe and reads from pack-net-scratch seed 1, against its own
zero-shot file (`results/mutate/gen-wide-pns1-tsl1.json`), 675 paired
starts x 4 seeds; `family.py`'s `gen_cut` per row, pooled as fixed above.

| row | zero-shot cost | cut (se nets) | share | per net |
|---|---|---|---|---|
| GE-OppCard-Artifact | +9.92 (0.61) | -1.59 (0.63) | -0.16 | -0.33, -2.10, -2.33 |
| GE-Attacked-Wound | +2.24 | +2.86 (0.08) | 1.28 | +3.02, +2.74, +2.81 |
| pooled | +12.16 | +1.27 | **0.10 (se nets 0.06)** | 0.22, 0.05, 0.04 |

Parent fight: +0.25 HP lost after the burst (per net -0.22, +1.10,
-0.12; inside the 1.5 bar). The family table (0959) says fail, by its own
Artifact-only rule.

**Checkpoint kill-fast 11-game read: passed (go).** Pooled share gp 0.60
(0.12) against pns 0.10 (0.06): gp ahead by 0.49 (se 0.14, z 3.6; 0.49 -
2 se = 0.22, past the 0.2 bar), parents +0.14 and +0.25 HP.

Sceptical read:
- The go is all Artifact. On Wound the two bases are level (cut +2.61
  against +2.86; both cut all of the cost and a little more, the parent
  drift again). So the deck effect on a new trigger is learnt in 11 games
  from either base; the new effect on an old trigger is learnt only from
  the generated-pack base.
- pns's Artifact cut is negative on every net: after 11 games it plays
  the Artifact fights worse than zero-shot, beyond its parent. The bursts
  trained normally (val MSE 0.17-0.18 on both bases, same epochs), so this
  is the games, not a broken run. Per encounter: Gremlin Nob -1.06, -6.10,
  -1.16 (gp +5.16, +1.18, +1.54), Lagavulin -2.9 to -2.2 on a cost of only
  +0.52 (parent drift up to +4.05 on net 2), Sentries +3.20, +2.31, -3.57.
- The bases' costs differ by encounter (Artifact on Nob: gp +8.42, pns
  +4.68), so part of gp's lead could be more room to cut. Sentries is the
  check: both pay about the same there (+21.85, +25.61) and gp cuts +12.31,
  +4.98, +11.98 against pns +3.20, +2.31, -3.57. The lead holds where the
  room is equal.
- One base seed each (gp s1, pns s1), three burst seeds: the comparison
  is between two particular nets. gp's seed 2 (+2.37 on Artifact) is still
  above every pns net.

What it says for goal 1: a net trained across generated enemy mechanics
binds a new effect on a familiar trigger in 11 games where the same
recipe without the pool cannot (it gets worse); for a deck effect on a
new trigger both need about the same few games. Charter stop rule: go;
the 33-game arm is not run (it was for the between case).
