# Family-transfer probes on generated enemies (0473, 0474)

The navigator's read, 2026-11-08 (probe sheet, decisions "After
generated-enemies batch 1"). Question: does a burst trained on one power
that punishes attacking (SharpHide) repair that family's generated pack
mechanics, and across triggers?

## Setting

Jobs 0473 and 0474 (`jobs/done/0473-mutate-monsters.json`,
`jobs/done/0474-mutate-monsters.json`; `results/mutate/gen-b1-sharp399-s1.json`,
`results/mutate/gen-b1-sharp399-s2.json`): the two 399-game SharpHide
bursts of `adaptation-curve` (trained on patched sharp2, sharp2-hp0.9,
ritual2; `runs/2026-11-04-adapt-sharp-g133-s1-5ad1c9c`,
`runs/2026-11-05-adapt-sharp-g133-s2-a305ff7`) at `@hpb0.01@tsl1`, gen
batch 1 (eight mechanics and the ladder), elites, the first 1000 starts (675
elite fights: Nob 229, Lagavulin 231, Sentries 215) x 4 seeds, heuristic and
net. Zero-shot: the same starts and the first 4 of the 16 seeds of
`results/mutate/gen-enemies-b1.json` (the 10-29 net `@tsl1`); the
heuristic's results are identical row by row, so the files pair. Cost as in
the bench (`mutate_monsters.gen_table`): (net - heuristic)(mechanic) -
(same)(ladder control), HP lost per elite fight, mean (se over starts);
the control is picked by the heuristic's HP lost, so it is the same entry in
all three files.

## Cost per mechanic, zero-shot / seed 1 / seed 2

| mechanic | all elites | the parent it sits on |
|---|---|---|
| AttackLoss-Damage | +6.23 (0.42) / +2.22 (0.22) / +3.14 (0.26) | Nob +13.29 (0.90) / +1.91 (0.40) / +2.02 (0.46) |
| OppCard-PlainDamage | +1.84 (0.36) / -0.15 (0.23) / +0.33 (0.26) | Sentries +5.39 (0.63) / +0.31 (0.45) / +0.74 (0.42) |
| AttackLoss-Strength | +0.74 (0.32) / -2.06 (0.29) / -1.08 (0.32) | Nob +2.29 / -0.31 / +0.36 |
| OppCard-Vulnerable | -9.53 (0.58) / +0.36 (0.56) / -1.72 (0.58) | Sentries -13.29 (1.18) / +0.50 (1.12) / -4.35 (1.15) |
| TurnStart-Damage | +0.96 / +0.83 / +2.88 | Lagavulin +2.03 / +1.17 / +4.56 |
| TurnEnd-Damage | +0.06 / +0.20 / +2.29 | Lagavulin +2.17 / +1.44 / +5.47 |
| TurnEnd-Frail | +0.55 / +0.36 / +0.70 | |
| TurnStart-Strength | -0.09 / -1.49 / -0.29 | |

Net wins, zero-shot / seed 1 / seed 2 (heuristic):
- AttackLoss-Damage x Nob 0.698 / 0.933 / 0.928 (0.944);
- OppCard-PlainDamage x Sentries 0.636 / 0.803 / 0.800 (0.794);
- OppCard-Vulnerable, all elites 0.841 / 0.670 / 0.707 (0.682); x Sentries
  0.765 / 0.417 / 0.522 (0.501); x Lagavulin 0.850 / 0.765 / 0.789 (0.598);
  x Nob 0.903 / 0.810 / 0.799 (0.937).

Unmutated parents, net HP lost per elite fight: 14.55 / 14.85 / 16.61
(Lagavulin 15.62 / 15.98 / 20.00; Sentries 15.48 / 16.63 / 17.56; Nob
12.59 / 12.04 / 12.29); wins 0.987 / 0.986 / 0.987.

## What it says

- **Transfer across triggers, inside the family.** Both seeds cut
  AttackLoss-Damage x Nob by 85% and OppCard-PlainDamage x Sentries by
  86-94%: a burst on one patched power that makes attacking cost HP
  repairs the pack's generated version of it and the version that punishes
  playing any card. By the rule in decisions "After generated-enemies
  batch 1" ("both cut by half"), one burst per family covers the bench's
  punish-an-action damage mechanics. The pack mechanics are built from
  atoms the net reads (the burst keeps the parent's vocabulary,
  `how/burst-inputs`), so this is transfer by effect, not by name.
- **Two ways out of the Nob cost.** Probe 0472 removed it with no games
  (`@esp0.04`, +13.29 to -0.06) and broke AttackLoss-Strength (+13 to +22
  HP on every parent); the SharpHide bursts cut it to about +2 and made
  AttackLoss-Strength cheaper (-1 to -2). The bursts learned to keep
  attacking under the HP price, where the flat price stopped feeding
  Enrage by stopping skills.
- **Interference: the burst loses the net's best mechanic.** Zero-shot,
  the net beat the heuristic by 9.5 HP on OppCard-Vulnerable (Vulnerable on
  the player for each card played); both burst seeds play it about as the
  heuristic does (wins 0.67-0.71 against the heuristic's 0.68 and the
  zero-shot net's 0.84), Sentries worst (0.77 to 0.42-0.52). A reading, not
  traced in games: the burst learned "a card played costs me", which is
  right against damage and wrong against a debuff whose cost the search
  sees inside the turn. Retention read only on the official parents would
  miss it: the parents' wins held (0.987).
- **Seed 2's retention is worse** (Lagavulin parent +4.4 HP, turn-trigger
  damage mechanics +2-3 HP), as SharpHide's seed twins were already 1.7 HP
  apart on the cells (`decision/burst-adapted-column`).

What it changes: `gen-adapted-column`'s per-mechanic families stay (they
measure games to adapt from the base net, the charter's number); a
burst's retention needs reading on the other generated mechanics, not
only the parents, before a pack ships a net (`pack-adapt-pipeline`);
probes 0546-0547 read the column's own 99-game AttackLoss-Weak bursts on
gen batch 1 for the same interference.

## Bench-retention probes (0546, 0547): a 99-game AttackLoss-Weak burst on the eight other mechanics

The navigator's read, 2026-11-08 (decisions "After the family-transfer
probes", point 2). Jobs 0546 and 0547 (`jobs/done/0546-mutate-monsters.json`,
`jobs/done/0547-mutate-monsters.json`; `results/mutate/gen-b1-gacalw-g99-s1.json`,
`results/mutate/gen-b1-gacalw-g99-s2.json`): `gen-adapted-column`'s
99-game AttackLoss-Weak bursts, net teacher, seeds 1 and 2
(`runs/2026-11-08-gac-alw-net-g99-s1-6e0a1da`,
`runs/2026-11-08-gac-alw-net-g99-s2-d5834b5`) `@tsl1`, gen batch 1 (eight
mechanics, none of them AttackLoss-Weak, and the ladder), elites, the same
675 elite fights x 4 seeds as 0473-0474, player one only; the heuristic's
games come from `results/mutate/gen-enemies-b1.json`'s first 4 seeds, as
`odds --base` does. Delta = the burst's net HP lost minus the zero-shot
net's on the same start and seed, seeds 1 and 2 pooled per start, mean
(se over starts).

| mechanic | delta HP lost, all elites | delta wins | cost zero-shot / s1 / s2 | worst parent |
|---|---|---|---|---|
| parent (unmutated) | -0.47 (0.15) | -0.001 | | |
| OppCard-Vulnerable | **+1.23 (0.31)** | **-0.049** | -9.53 / -5.27 / -6.19 | Sentries **+6.04 (0.70)**, wins 0.765 -> 0.581 / 0.626 (heuristic 0.501) |
| AttackLoss-Damage | -4.56 (0.34) | +0.070 | +6.23 / +3.34 / +3.00 | Nob -9.62 (0.78), wins 0.698 -> 0.877 / 0.898; cost +13.29 -> +6.88 / +4.89 |
| OppCard-PlainDamage | -2.87 (0.24) | +0.040 | +1.84 / +1.30 / +0.93 | Sentries cost +5.39 -> +4.04 / +3.40 |
| AttackLoss-Strength | -2.89 (0.27) | +0.026 | +0.74 / -0.76 / -0.78 | |
| TurnStart-Strength | -1.84 (0.23) | +0.008 | -0.09 / -0.58 / -0.54 | |
| TurnStart-Damage | -1.70 (0.20) | +0.014 | +0.96 / +1.30 / +1.28 | |
| TurnEnd-Damage | -1.71 (0.19) | +0.018 | +0.06 / +0.58 / +0.42 | |
| TurnEnd-Frail | -0.35 (0.14) | +0.001 | +0.55 / +0.91 / +1.03 | Sentries +0.08 (0.26) |

The ladder (official elites with more HP or Strength) gains too: delta
-0.07 (c-hp0.8) to -2.57 (c-hp1.5-str2), -1 to -2 HP on most entries,
growing with the fight's length.

What it says:

- **Go, read at the parent.** On all elites OppCard-Vulnerable sits just
  under both bars (+1.23 HP, wins -0.049; the rule's bars are +2 HP at 2 se
  or -0.05 wins), so the read looked one level down: on Sentries the
  burst loses 6.04 HP (8.6 se) and 0.16 wins, in both seeds (+7.13, +4.95),
  on Lagavulin and Nob it is level or better. The interference is general
  in the sense that matters: a second burst, on a different mechanic with a
  quarter of the games and none of SharpHide's patched content, loses the
  same edge in the same place (SharpHide's 399 games: Sentries wins 0.42 /
  0.52). A pack's net read for retention on the official parents would
  ship it (parents -0.47 HP, wins level).
- **It is one spot, not a spread.** Every other mechanic, the parents and
  the ladder play better after the burst (-0.35 to -4.56 HP). The bench's
  cost column (net minus heuristic, against the ladder control) moves much
  less than HP lost, because the control gains too: outside the
  punish-an-action family the costs stay within about 0.5 HP of zero-shot.
  So most of the gain is a general one on long elite fights (99 more elite
  games), and the column's measure, which subtracts its control, is not
  fooled by it.
- **Transfer by trigger at 99 games.** The AttackLoss-Weak burst halves
  AttackLoss-Damage x Nob's cost (+13.29 to +6.88 / +4.89) and cuts
  OppCard-PlainDamage x Sentries by a third (+5.39 to +4.04 / +3.40),
  where SharpHide's 399 games cut both by 85-94%. The same trigger (the
  monster losing HP to an attack) carries most of the transfer; the other
  trigger (a card played) less.
- **A reading, not traced in games.** Both bursts teach that an action of
  the player's own is punished; OppCard-Vulnerable punishes each card with
  a debuff whose price the search sees inside the turn, and the zero-shot
  net's edge there (+9.5 HP against the heuristic) is that it keeps
  playing cards. The bursts move it toward the heuristic, worst against
  Sentries, the parent with the most cards to play and the most incoming
  damage. Seed 2 is the better seed on both the Nob cut and the Sentries
  loss, so two seeds do not tie the interference to how much the burst
  learned.

## Pack-joint-burst probe (0549-0553): one burst over gen batch 1's eight mechanics

The navigator's read, 2026-11-08 (decisions "After the bench-retention
probes", point 3; backlog candidate 27). Jobs 0549/0551 (bursts:
`configs/pjb-net-g50x8-s1.json`, `-s2.json`; 50 fights per mechanic over
the three elites, 400 games, net teacher `@hpb0.01@tsl1`, replay share
0.5), 0550/0552 (bench reads, `results/mutate/pjb-2026-11-08-pjb-net-g50x8-s1-7fc419b.json`,
`-s2-e28ee47.json`; gen batch 1, elites, the same 675 starts x 4 seeds as
0546-0547), 0553 (the family table, `jobs/done/0553-family.json`).
Delta = the burst's net HP lost minus the zero-shot net's on the same
start and seed, both nets pooled per start, mean (se over starts); cost =
(net - heuristic)(mechanic) - (net - heuristic)(c-hp1.25), the
heuristic's games from `results/mutate/gen-enemies-b1.json`'s first 4
seeds; z = zero-shot.

| mechanic x parent | delta HP lost | wins z -> burst (heuristic) | cost z / s1 / s2 |
|---|---|---|---|
| OppCard-Vulnerable x Sentries | **-2.22 (0.53)** | **0.765 -> 0.787** (0.501) | -12.26 / -12.07 / -14.10 |
| OppCard-Vulnerable, all elites | -0.84 (0.25) | 0.841 -> 0.847 | -7.73 / -7.04 / -7.75 |
| AttackLoss-Damage x Nob | -8.18 (0.78) | 0.698 -> 0.868 (0.944) | +13.29 / +6.73 / +7.37 (cut 0.47; 0553: bar 0.5, **fail**) |
| OppCard-PlainDamage x Sentries | -4.03 (0.44) | 0.636 -> 0.756 (0.794) | +7.36 / +6.15 / +3.29 |
| AttackLoss-Strength x Nob | -4.31 (0.52) | 0.879 -> 0.932 | +2.80 / +0.32 / +0.55 |
| parent x Lagavulin | **+1.67 (0.37)** | 0.989 -> 0.981 | +0.50 / +2.70 / +2.09 |
| TurnEnd-Frail x Lagavulin | **+3.25 (0.42)** | 0.978 -> 0.964 | +1.23 / +5.30 / +4.08 |
| parent, all elites | +0.38 (0.16) | 0.987 -> 0.985 | |

Every other mechanic x parent plays level or better (TurnStart and
TurnEnd damage -0.6 to -2.0 HP; the ladder -0.1 to -4.7 HP, growing with
the fight's length) except the short Lagavulin ladder rows (c-hp0.8
+1.08, c-str1 +1.21, c-str2 +1.04) and c-hp2 x Sentries (+1.77 (0.31)).
The 99-game AttackLoss-Weak bursts (0546-0547, on Lagavulin and Sentries)
left the same Lagavulin rows level: parent -0.18 (0.29), TurnEnd-Frail
-0.72 (0.30).

What it says:

- **Between, by the read rule** (go needed all three; fail was the
  Sentries wins under 0.70): the Sentries edge holds, the Nob cut lands
  just under its bar (0.47 against 0.5; per net +6.56 and +5.92, se 0.32
  over nets), and one mechanic x parent rises past 2 HP at 2 se
  (TurnEnd-Frail x Lagavulin +3.25, 7.7 se, both seeds).
- **Rehearsal by the pack's own games keeps the edge.** With
  OppCard-Vulnerable's own games in the burst the net plays it better
  than zero-shot on Sentries (wins 0.787, HP -2.22), where two
  single-mechanic bursts lost 0.14-0.18 wins there. The interference
  0546-0547 found was missing rehearsal, not a conflict between
  mechanics in one net.
- **50 games a mechanic repair about half.** Nob's cost falls 0.47 with
  about 17 Nob games per mechanic (all eight mechanics' Nob games count
  through the trigger, as 0546-0547 showed); OppCard-PlainDamage x
  Sentries wins 0.636 to 0.756. Near the about 100 games the adaptation
  curve gave for one mechanic (`measurement/adaptation-curve`).
- **A new, smaller leak, on Lagavulin.** The parent and its short ladder
  rows lose about 1-1.7 HP a fight and TurnEnd-Frail 3.25, wins down
  0.008-0.014, in both seeds, though the burst held TurnEnd-Frail x
  Lagavulin games. A reading, not traced in games: lessons from the
  punish-an-action mechanics (play fewer cards, attack less) reach
  Lagavulin, whose free sleeping turns reward the opposite; the
  AttackLoss-Weak burst carried one such lesson and left Lagavulin level,
  so the leak comes with the mix. A pack's retention guard per mechanic
  per parent (`decision/burst-adapted-column`) catches it; batch 1's
  50-game joint net would not ship under it.

## Gen batch 1 through the pack chain (0556-0564): pack-adapt-pipeline step 2

Lane worker's read, 2026-11-08. `family.py queue configs/packs/gen-b1.json`
queued the whole chain at once (bursts 0556/0558 for arm g99: 99 games per
mechanic, two seeds; 0560/0562 for g99-parents: the same plus the three
parents unmodified; bench reads 0557/0559/0561/0563; table 0564 with its
verdict check). It ran 10:10-14:33 with no session editing or re-queuing
any of it (one session read 0559/0560 midway and left the chain alone).
The table is `results/families/gen-b1.md` (`.json` beside it), 3.8
thread-hours for the lane in total. The setting is the pack-joint-burst
probe's (675 starts x 4 seeds, the three elites).

| | g99 (pooled) | g99-parents (pooled) | pjb 50 games (probe) |
|---|---|---|---|
| AttackLoss-Damage x Nob cut of +13.29 (share cut) | **+11.50** (0.87) | **+9.91** (0.75) | +6.2 (0.47) |
| OppCard-PlainDamage x Sentries cut | +4.51 | +6.66 | |
| OppCard-Vulnerable x Sentries delta HP | -3.47 | -2.53 | -2.22 |
| TurnEnd-Frail x Lagavulin delta HP | **+3.01** (0.39) | **+5.18** (0.43) | +3.25 (0.42) |
| parent x Lagavulin delta HP | +0.87 (0.33) | +2.06 (0.32) | +1.67 (0.37) |
| parent, all elites delta HP | +0.19 (0.16) | +0.82 (0.16) | +0.38 (0.16) |
| nets passing the guard | 1 of 2 | 1 of 2 | 0 of 2 |

The guard per net fails a cell at 2.0 HP (or 0.05 wins) lost and 2 se.
The shipped net (`runs/2026-11-08-pack-gen-b1-g99-parents-s1-6078389`,
the guard-passing net with the largest mean cut, +1.10) has Nob's cut
+9.41 per net and, worst, TurnEnd-Frail x Lagavulin **+1.99** (0.40), parent
x Sentries +1.58 (0.30), TurnEnd-Frail x Sentries +1.51 (0.30). The other
passing net (g99 s1, mean cut +0.85) is the same shape.

- **The chain works, and the target passes cleanly.** Queue to table with
  no session; Nob's cost cut is 0.75-0.87 of the zero-shot cost in both
  arms, against the bar of half at 2 se. Doubling the dose from 50 to 99
  games per mechanic took the cut from 0.47 to 0.87: the adaptation curve's
  "about 100 games" holds inside a joint burst.
- **The ship passes at its bar.** The shipped net's worst cell, TurnEnd-Frail
  x Lagavulin, sits 0.01 HP under the guard's 2.0, and it was picked as
  the best of four nets read on the same starts the guard reads; the other
  three lose 3.0-8.4 HP there. The leak is real in every net (5 to 20 se),
  so "a net ships" here says the guard's threshold let one seed through,
  not that the pack's net keeps Lagavulin. By the charter's stop rule this
  is **go**; read sceptically, it is go on the chain and between on
  retention.
- **Parents in the burst make the Lagavulin leak worse, not better.**
  g99-parents loses more on parent x Lagavulin (+2.06 against +0.87) and on
  TurnEnd-Frail x Lagavulin (+5.18 against +3.01) than g99, and more on
  the parents over all elites (+0.82 against +0.19), though it trained on
  the parent Lagavulin's own games. Rehearsal by the parent's games would
  hold the parent level if the teacher played it at least as well as the
  zero-shot net. That it does not points at the teacher (`@hpb0.01@tsl1`)
  on Lagavulin's long sleeping-start fight, not at forgetting: a lead for
  `cause/teacher-equals-student`, untested here (a cheap test: the
  teacher's own HP lost on parent Lagavulin against the zero-shot net's,
  on the same starts).
- **The leak grows with dose.** TurnEnd-Frail x Lagavulin: +3.25 at 50
  games, +3.01 / +5.18 at 99. More pack games buy the target and cost
  Lagavulin; a retention term (or a better teacher on Lagavulin) is the
  open question, for the navigator.

What it changes: the pack chain is goal 1's one-command path from a pack
of generated mechanics to a net and its table, and its guard works (it
refused three of four nets for the leak it is built to catch). The 2.0 HP
threshold at 2 se lets a net with a consistent 2 HP loss through; a
stricter guard (a bar on the upper bound, or on the pooled arm rather than
the best net) would have refused all four. Not changed in this lane: the
guard is the spec's, and the choice is the navigator's with the retention
question.

## Pack-retention step 1, seed 1 (0575, 0576): the heuristic as burst teacher

Lane `pack-retention` step 1: gen-b1's g99 arm, same pack, bench and
zero-shot base, with the heuristic playing the burst games
(`configs/packs/gen-b1-heur.json`). Seed 1 read (0576, 1,000 starts x 4
seeds); seed 2 (0577, 0578) and the table (0579) still queued. Delta HP
lost against zero-shot, se over starts (`family.py table`, seed 1 only):

| cell | net teacher g99 (gen-b1, per net) | heuristic teacher, s1 |
|---|---|---|
| TurnEnd-Frail x Lagavulin | +1.16, +4.86 (pooled +3.01) | +0.95 (0.36) |
| parent x Lagavulin | pooled +0.87 | +0.76 (0.36) |
| AttackLoss-Damage x Nob, cut of +13.29 | +11.50 pooled | -2.51 (the cost grows) |
| mean cut over the pack's cells | | +0.34 |

What it says:
- The heuristic teacher learns almost nothing. The Nob cell, where the
  net costs 13.3 HP more than the heuristic, gets no better (+0.82 HP lost,
  cut -2.51): value labels from the heuristic's own continuations don't
  teach the net's search what to avoid there. Every other cut is within
  about 2 HP of zero.
- The TurnEnd-Frail x Lagavulin leak shrinks to +0.95, but with nothing
  learned that says little about the teacher: a burst that moves the net
  less leaks less. Its summed squared weight drift from the parent is
  12.9, inside the net-teacher bursts' 9.0-20.8, so the weights moved as
  much; they moved without gaining.
- The Lagavulin parent leak stays (+0.76 against +0.87) under either
  teacher: that part is forgetting outside the burst, not the teacher's
  play.
- Checkpoint `heur-teacher` fails at seed 1 whatever seed 2 shows: its go
  needs the Nob cut at 8.0 or more at both seeds. The lane goes to step 2,
  the retention term (`docs/specs/burst-anchor.md`), on the net teacher.

### Seed 2 (0577, 0578) and the pooled table

Seed 2 confirms seed 1 (`family.py table configs/packs/gen-b1-heur.json`,
pooled over both nets, se over starts; the written table is 0579's):

| cell | heuristic teacher, pooled s1+s2 | per net |
|---|---|---|
| TurnEnd-Frail x Lagavulin | +1.03 (0.35) | +0.95, about +1.11 |
| parent x Lagavulin | +0.81 (0.34) | +0.76, about +0.86 |
| AttackLoss-Damage x Nob, cut of +13.29 | -1.28 (se over nets 1.24) | -2.51, -0.04 |
| mean cut over the pack's cells | | +0.34, +0.51 |

- Both nets pass the guard; the pooled table's "verdict: pass" is the
  guard's and the shipped-net pick, not the lane's checkpoint: the target
  cut fails at both seeds, so `heur-teacher` stays failed.
- What the heuristic teacher does teach is small and broad: cuts of +1 to
  +4.3 HP on Lagavulin and Sentries cells it was never short on (largest
  OppCard-PlainDamage x Sentries, +4.34), nothing on the Nob cell that
  needs a better line than the heuristic plays. Labels from a weaker
  player can't teach the net's search to beat that player.
- The Lagavulin parent leak (+0.8) is the same under both teachers, so the
  step-2 anchor is aimed at the right part: forgetting outside the burst.

## Pack-retention step 2, first net (0586, 0587): anchor 0.003, seed 1

Lane `pack-retention` step 2: gen-b1's g99 arm with the net teacher and an
L2 anchor toward the parent's weights (`docs/specs/burst-anchor.md`,
`configs/packs/gen-b1-anchor.json`). One net of four so far; a003-s2, a03-s1
and a03-s2 (0588-0593) and the table (0594) still queued. Delta HP lost
against zero-shot, se over starts (`family.py table`, printed, not written):

| cell | net teacher g99 (gen-b1) | heuristic teacher (pooled) | anchor a003, s1 |
|---|---|---|---|
| TurnEnd-Frail x Lagavulin | +1.16, +4.86 | +1.03 (0.35) | +1.36 (0.35) |
| parent x Lagavulin | pooled +0.87 | +0.81 (0.34) | -0.22 (0.29) |
| parent, all encounters | | +0.44 (0.16) | -0.77 (0.14) |
| AttackLoss-Damage x Nob, cut of +13.29 | +11.50 pooled | -1.28 | +10.61 |
| mean cut over the pack's cells | | +0.34, +0.51 | +0.62 |

What it says (one seed, a lead):
- The anchor does what it is for on the parents: the Lagavulin parent leak
  is gone (-0.22), and the parents get better on all three elites
  (Nob -0.95, Sentries -1.17), where both earlier teachers lost HP.
- It keeps the Nob cut (+10.61, over the 8.0 bar), so a weight 0.003 doesn't
  stop the burst from learning.
- It does not touch the TurnEnd-Frail x Lagavulin leak: +1.36, level with the
  unanchored net's +1.16 at the same seed. That leak is not forgetting of the
  parent; it is something the burst teaches that carries badly to that cell.
  If a03 (ten times the weight) doesn't remove it either, the weight anchor
  can't pass the checkpoint, whose go needs this cell within 1 HP at both
  seeds; the charter then allows distillation as a further arm, and it would
  have to target that cell's positions, not the parent's.

### Seed 2 of anchor a003 (0588, 0589)

0589 read a003-s2 (1000 bench starts x 4 seeds, 24 min against an
18-minute estimate). Delta HP lost against zero-shot, se over starts
(`family.py table`, printed; s2's own value is twice the pooled mean minus
s1's, since both nets play the same starts):

| cell | a003 s1 | a003 s2 | a003 pooled | net teacher g99, s1 / s2 |
|---|---|---|---|---|
| TurnEnd-Frail x Lagavulin | +1.36 (0.35) | +2.76 (0.47) | +2.06 (0.38) | +1.16 / +4.86 |
| parent x Lagavulin | -0.22 | about +0.68 | +0.23 (0.28) | pooled +0.87 |
| parent, all encounters | -0.77 | about +0.25 | -0.26 (0.14) | |
| AttackLoss-Damage x Nob, cut of +13.29 | +10.61 | +11.06 | +10.84 (se nets 0.23) | pooled +11.50 |

What it says:
- a003 fails the anchor checkpoint's go: TurnEnd-Frail x Lagavulin is
  +2.76 at seed 2, above the +2 HP fail line, and the guard fails that net
  on the same cell (2.0 HP at 2 se). The arm's fate now rests on a03.
- The leak is seed-noisy (+1.36 / +2.76 here, +1.16 / +4.86 unanchored), so
  one seed per arm says little; but at seed 2 the anchor roughly halves it
  (4.86 to 2.76), so the weight anchor does pull on this cell somewhat,
  unlike seed 1 suggested.
- The parents stay near zero-shot at both seeds (Lagavulin within 1 HP), and
  the Nob cut holds (+10.84, well above 8.0): the anchor costs the burst
  nothing at 0.003.
- `family.py table` printed a03 from 0591's half-written read (366 of 1000
  starts) as if it were whole, and gave a verdict from it; a read written
  in parts should be counted only once finished. The table job (0594) runs
  after every read, so the written table is unaffected.

### Anchor a03, seed 1 (0590, 0591)

0591 read a03-s1 (1000 bench starts x 4 seeds, 23 min against 18). Delta HP
lost against zero-shot, se over starts:

| cell | a003 s1 / s2 | a03 s1 |
|---|---|---|
| TurnEnd-Frail x Lagavulin | +1.36 / +2.76 | +0.32 (0.32) |
| parent x Lagavulin | -0.22 / about +0.68 | -0.19 (0.28) |
| parent, all encounters | -0.77 / about +0.25 | -0.66 (0.14) |
| AttackLoss-Damage x Nob, cut of +13.29 | +10.61 / +11.06 | +6.89 |
| mean cut over the pack's cells | +0.62 / +1.08 | +0.92 |

What it says (one seed):
- Ten times the weight removes the TurnEnd-Frail x Lagavulin leak at this
  seed (+0.32, within 1 HP) and keeps the parents better than zero-shot,
  but the burst learns less of its target: the Nob cut drops from about 11
  to 6.89, under the 8.0 bar. The weight anchor trades the leak against
  the cut; neither weight gets both at seed 1 and seed 2 so far.
- The other cells gain a little more under a03 (mean cut +0.92 against
  +0.62 at the same seed): the stiffer net carries the burst's general
  lessons as well as the looser one, and loses only on the burst's own cell.
- On the half-written-read note above: `family.py table` skips a read
  under `min_starts` (200), so any read past 200 starts counts as whole;
  0591's table at 366 starts showed the Nob cut +6.92, close to the
  finished +6.89.

### Anchor a03, seed 2 (0592, 0593), the table (0594) and the anchor checkpoint

0593 read a03-s2 (26 min against 18); 0594 wrote the table
(`results/packs/gen-b1-anchor.json`). Delta HP lost against zero-shot, se
over starts; per-seed values for s2 are twice the pooled mean minus s1's:

| cell | a003 s1 / s2 (pooled) | a03 s1 / s2 (pooled) |
|---|---|---|
| TurnEnd-Frail x Lagavulin | +1.36 / +2.76 (+2.06) | +0.32 / about +1.22 (+0.77, se 0.31) |
| parent x Lagavulin | -0.22 / about +0.68 (+0.23) | -0.19 / about +0.59 (+0.20, se 0.27) |
| parent, all encounters | pooled -0.26 (0.14) | pooled -0.13 (0.13) |
| AttackLoss-Damage x Nob, cut of +13.29 | +10.61 / +11.06 (+10.84) | +6.89 / +8.28 (+7.59, se nets 0.70) |
| mean cut over the pack's cells | +0.62 / +1.08 | +0.92 / +1.16 |
| guard | s2 fails (TurnEnd-Frail x Lagavulin) | both pass |

**Checkpoint anchor: failed.** The go needs one arm with both Lagavulin
cells within 1 HP at both seeds and the Nob cut 8.0 or more. a003 leaves
TurnEnd-Frail x Lagavulin at +2.76 at seed 2 (over the +2 HP fail line);
a03 keeps +7.59 of the cut pooled (6.89 at seed 1, under 8.0) and is at
+1.22 on the leak at seed 2. Each arm meets one of the charter's fail
conditions, so the lane's stop rule reads fail.

Why, and what it says about the fix:
- The anchor buys the leak back only by buying back the burst: across the
  two weights the leak falls by 1.3 HP pooled and the Nob cut by 3.2 HP.
  Both live in the same value head, as the opening entry feared. A middle
  weight lands between the two on both, so by the trend it would miss the
  1 HP bar or the 8.0 cut; it isn't worth its 2.6 thread-h.
- The parents are no longer the problem at either weight: parent x
  Lagavulin within 1 HP at all four nets, the parents better than
  zero-shot overall. The weight anchor does fix forgetting outside the
  burst. What stays is TurnEnd-Frail x Lagavulin, a cell the burst itself
  plays: the burst's own games teach something wrong there. Seed 1's
  reading (that this leak isn't forgetting) holds.
- The family table's own rule (half the target's cost, 6.65) passes a03
  and ships a03-s2 as the pack's net; the lane's stricter go (0.7 of g99's
  cut, both Lagavulin cells within 1 HP) is what fails. The shipped net is
  safer than gen-b1's (the guard passes both seeds, parents better), at
  about two thirds of gen-b1's Nob cut.
- Distillation toward the parent on the burst's positions (the charter's
  other step-2 term) pulls on the Nob positions as directly as on the
  leaking cell, so it would show the same trade. A fix has to change what
  the burst teaches at TurnEnd-Frail x Lagavulin (its teacher's games
  there, or holding that cell's positions to the parent while leaving the
  target free), which is new design work, not a further weight.
- Step 3 (the fresh-start confirm read) was not run: it confirms a go.

## Pack-dose-33 probe (0697-0701): the pack chain at 33 games per mechanic and share 0.9

Navigator probe sheet, candidate `pack-dose-33` (backlog 38). Gen batch
1's pack chain (`configs/packs/gen-b1-dose33.json`) with one arm, g33-sh9
(33 games per mechanic, replay share 0.9, `decision/burst-share`), two
burst seeds, read @tsl1 on the bench's elites (675 fights x 4 seeds)
against the zero-shot 10-29 net and beside gen-b1's g99 arm at share 0.5
(`results/families/gen-b1.md`). Table: `results/families/gen-b1-dose33.md`
(4.6 thread-h).

- The Lagavulin leak is gone: TurnEnd-Frail x Lagavulin +0.54 (0.33) HP
  per elite fight against g99's +3.01 (0.39); the parent over all
  encounters -0.16 (0.15) HP (g99 +0.19 (0.16)).
- The target is cut by a third, not half: AttackLoss-Damage x Gremlin Nob
  +4.24 (se over nets 1.92) of +13.29, per net +6.16 and +2.32 (g99
  +11.50). AttackLoss-Strength x Nob is cut +2.08, OppCard-PlainDamage x
  Sentries +1.17 with wins +0.096.
- The neighbour edge is lost as single-mechanic bursts lost it:
  OppCard-Vulnerable x Sentries +7.06 (0.81) HP, wins -0.213, on both nets
  (guard fails on both: +6.68 and +7.44 HP); g99 at share 0.5 improved it
  (-3.47 (0.53), wins +0.105) and the 50-game joint burst kept it
  (`measurement/pack-joint-burst@gen-b1`).
- Verdict by the read rule: not a go (guard fails on both nets, cut under
  half), not a stop (the leak is under +3.01). Interpretation: at share
  0.9 a joint burst's new games are a tenth of each batch shared by eight
  mechanics, so each mechanic's own games are too few to rehearse the
  Sentries edge and to cut Nob far, while the parent hardly moves; the
  leak followed the size of the move off the parent, the edge and the cut
  follow the mechanic's own dose. The single-mechanic quote of 33 games at
  share 0.9 (`decision/burst-share`) does not carry to a pack of eight in
  one burst.
- Next (queued 2026-11-09, jobs 0734-0738,
  `configs/packs/gen-b1-dose99s9.json`): the same chain at 99 games per
  mechanic and share 0.9, read on the same rule.

## Share-quote-widen probe (0715-0728): two damage-trigger mechanics at 33 games and share 0.9

Navigator probe sheet, candidate `share-quote-widen` (backlog 46).
OppCard-Damage and OppCard-PlainDamage x Three Sentries, net-teacher
bursts at 33 games and replay share 0.9, three seeds each, read @tsl1 on
`gen-adapted-column`'s starts (families `sc-ocd33`, `sc-ocpd33`; tables
`results/families/sc-ocd33.md` and `sc-ocpd33.md`, 0.8-0.9 thread-h
each), on that lane's rule (cut at least half the zero-shot cost at 2 se
over nets), beside the 99-game share-0.5 bursts
(`measurement/gen-adapted@ocd`, `@ocpd`).

- OppCard-Damage: cut +3.29 (se starts 0.36, nets 0.27), 0.64 of the
  +5.11 cost (99 games at 0.5: +3.01, 0.59); per net +3.63, +2.76, +3.46;
  trained parent -0.02 (0.50) HP per fight (99 games: +0.62). Pass.
- OppCard-PlainDamage: cut +3.70 (0.36 / 0.12), 0.69 of the +5.39 cost
  (99 games: +4.16, 0.77); per net +3.83, +3.82, +3.46; trained parent
  +1.68 (0.26) HP per fight (99 games: +1.08). Pass on the cut; the parent
  change is worse than the 99-game default's.
- Verdict by the read rule (go if both pass with the parent change no
  worse): between. The cut half of the quote widens: 33 games at share 0.9
  cut half or more of the cost on four generated mechanics, two trigger
  kinds (debuff and damage, all on Lagavulin or Sentries). The parent
  half does not: "parents spared" holds for three of the four, and
  OppCard-PlainDamage's trained parent loses 1.68 HP per fight, 0.6 more
  than at 99 games and share 0.5 (about 1.5 se of the difference).
  Interpretation (a guess): PlainDamage punishes every card the player
  plays, so a burst against it teaches playing fewer cards against
  Sentries, which the plain parent then pays for; share 0.9 does not
  protect a parent from a lesson the burst's own games teach on that
  parent's encounter.
