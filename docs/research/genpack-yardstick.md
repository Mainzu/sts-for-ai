# Generated enemy pool on the owner's yardstick (genpack-yardstick)

Navigator probe, lane `main`, jobs 0931 (wide net, widepack40k s1), 0932
(pack-net-scratch s1, the same recipe with no generated pool) and 0933
(the 10-29 net). The owner's yardstick (`decision/goal1-yardstick`): stage
A modifiers on official elites, 675 starts x 2 seeds, @tsl1 one turn deep
against the heuristic. Files `results/mutate/yard-wide-tsl1.json`,
`yard-pns1-tsl1.json`, `yard-n1029-tsl1.json`; the heuristic's games are
identical across the three files (675 of 675 parents checked).

## Read (navigator, 2026-11-12)

Novelty cost = (net - heur)(parent) - (net - heur)(modifier), end HP (0
on a loss), mean over starts (se), paired by start. Positive = the net
loses its edge on the novelty.

| modifier | wide | pns1 | 10-29 | wide - pns1 | wide - 10-29 |
|---|---|---|---|---|---|
| parent edge (net - heur) | -0.72 (0.27) | -0.09 (0.25) | +1.19 (0.23) | -0.63 (0.26) | -1.91 (0.27) |
| sharp2 | -0.28 (0.29) | +6.73 (0.48) | +5.42 (0.42) | -7.01 (0.47) | -5.70 (0.43) |
| thorns2 | +4.20 (0.33) | +8.23 (0.48) | +4.92 (0.38) | -4.02 (0.46) | -0.72 (0.40) |
| ritual2 | -1.07 (0.30) | -0.22 (0.32) | +1.68 (0.35) | -0.84 (0.32) | -2.75 (0.34) |
| weakhit1 | +0.82 (0.25) | +1.40 (0.28) | +1.61 (0.27) | -0.58 (0.28) | -0.78 (0.26) |
| metal3 | -0.32 (0.19) | +1.64 (0.27) | +1.56 (0.24) | -1.96 (0.25) | -1.88 (0.23) |
| str2 | +0.07 (0.21) | +0.20 (0.20) | +0.01 (0.15) | -0.12 (0.26) | +0.07 (0.22) |
| hp1.25 | +0.09 (0.27) | +0.10 (0.31) | +0.73 (0.29) | -0.01 (0.31) | -0.64 (0.30) |
| sharp2-hp0.9 | +0.27 (0.30) | +6.72 (0.49) | +5.14 (0.42) | -6.45 (0.47) | -4.87 (0.40) |
| thorns2-hp0.9 | +4.44 (0.34) | +7.97 (0.47) | +4.26 (0.36) | -3.53 (0.46) | +0.19 (0.37) |
| ritual2-hp0.7 | -1.78 (0.32) | -2.09 (0.35) | +0.03 (0.37) | +0.31 (0.32) | -1.81 (0.33) |
| weakhit1-dmg0.8 | -0.69 (0.24) | +0.20 (0.26) | +0.40 (0.23) | -0.89 (0.27) | -1.10 (0.23) |
| **pooled 4 (sharp2, thorns2, ritual2, weakhit1)** | **+0.92 (0.19)** | **+4.03 (0.28)** | **+3.41 (0.25)** | **-3.11 (0.26)** | **-2.49 (0.25)** |

In wins the pooled cost is +0.003 (0.005) for the wide net, +0.058
(0.007) for pns1 and +0.038 (0.006) for the 10-29 net; sharp2 alone
-0.004 / +0.125 / +0.067.

**Verdict: go** on the probe's rule (the wide net's pooled cost at most
half pns1's at 2 se: 0.92 is 23% of 4.03, the gap 12 se). The generated
enemy pool moves goal 1's standing number with no games on the official
modifiers. One training seed: a lead until `wide-recipe-confirm` (65)
reads seeds 101 and 201 on the same rows.

## Why (per encounter and per grid row)

- **Sharp Hide is repaired; Thorns is not.** Per elite, sharp2 costs the
  wide net +0.11 (Nob), -2.60 (Lagavulin), +1.80 (Sentries) against pns1's
  +6.60 / +1.55 / +12.45; thorns2 costs it +4.31 / +4.01 / +4.30, level
  with the 10-29 net on every elite (+5.57 / +3.55 / +5.70). Sharp Hide is
  OppAttack-PlainDamage, an unseen pairing of two atoms the wide pack
  trains; Thorns is Attacked-PlainDamage, and Attacked is the trigger the
  wide pack holds out whole (`docs/specs/wider-generators.md`, "Split of
  the new 76"). On the grid's own rows (0916's file) the damage-back
  effect is the one Attacked row the wide net cuts least: GE-Attacked-Damage
  +2.34 (0.28) HP against GE-OppAttack-Damage +0.77 (0.25) (pns1 +9.34 and
  +8.88). The residual on the yardstick sits on the held-out trigger,
  sharpest where damage comes back per hit; official Thorns 2 doubles the
  grid's stack of 1.
- **Ritual and the stat controls**: ritual2 and its pair cost the wide net
  less than nothing (-1.07, -1.78); str2 and hp1.25 are level for all
  three nets, as the controls should be.
- **Parents**: the wide net's own edge over the heuristic on the official
  parents is -0.72 (0.27) HP, 0.63 (0.26) below pns1 and 1.91 (0.27) below
  the 10-29 net (two self-play rounds). The cut is not a parent drop: on
  sharp2 the wide net's edge is -0.44 HP against pns1's -6.82. But the wide
  recipe plays official elites a little worse one turn deep;
  `wider-generators`' cells and headline reads (0918, 0919 re-run) are the
  guard.

## What it changes

- 65 `wide-recipe-confirm`: the yardstick rows become a measure with a go
  condition (pooled over three seeds at most half pns1's at 2 se).
- 67 `player-genpack-scratch`: retired by its own no-CPU probe, run in the
  same session (`docs/backlog.md`, "Checked and not proposed").
- New candidate 70 `wide-full-triggers`: the wide recipe with the held-out
  whole trigger and effect trained, read on thorns2.

## Candidate 67's no-CPU probe (navigator, 2026-11-12)

From `data/bench/gen_powers12c3.json` (elite and boss fights), each net's
@tsl1 file in `results/gen_powers/arms/gen_powers12c3/` minus the
heuristic's one-turn games (`results/gen_powers/depth/heuristic-elite_boss.json`),
wins, mean over cells (se over cells). On the 52 non-recurring generated
power cells every net is level with or ahead of the heuristic: the 10-29
net +0.037 (0.025), all-content 40k s1/s101 +0.022 / +0.050, the three
generated-pack nets -0.000 / +0.037 / +0.061, the three fslt bursts
+0.053 to +0.063; generated minus original on those cells +0.005 to
+0.088. No net is behind the heuristic there by 0.03 wins at 2 se, the
probe's kill rule: a generated player-card pool has no measured cost to
cut on that ruler. Recurring cells (34) as filed in
`measurement/gen-powers@later-ticks` (generated minus original -0.03 to
-0.08, under 2 se for every net but the 10-29 net).

## The wide net on the generated-power bench (job 0934, navigator, 2026-11-12)

Same read as candidate 67's probe above (each cell's wins minus the
heuristic's one-turn games, mean over cells (se over cells); recurring =
the 34 cells whose triggers hold OwnerTurnStart or OwnerTurnEnd, which
reproduces the 10-29 net's +0.037 on the 52 others). The wide net
(`runs/2026-11-12-widepack40k-s1-r1-1d2c208/model.pt@tsl1`,
`results/gen_powers/arms/gen_powers12c3/2026-11-12-widepack40k-s1-r1-1d2c208-tsl1.json`):
non-recurring generated +0.069 (0.023), original +0.024 (0.020);
recurring generated +0.025 (0.020), original +0.047 (0.019). The 10-29
net: +0.037 (0.025), -0.035 (0.026), -0.069 (0.029), +0.010 (0.024).
Enemy breadth costs player-side powers nothing and the wide net is the
first with no recurring-power gap (generated minus original -0.022 against
the 10-29 net's -0.079); the note's 0.04 bar is moot, 67 being retired.
Descriptive, one seed.

## The 18-mechanic nets on the yardstick (jobs 0939-0941, navigator, 2026-11-12)

The probe sheet's `genpack18-yardstick`: the three 18-mechanic
generated-pack nets (`runs/2026-11-10-genpack40k-s1-r1-acf5102`,
`runs/2026-11-11-genpack40k-s101-r1-065b3ff`,
`runs/2026-11-11-genpack40k-s201-r1-a97ea94`, all @tsl1) on the same rows
and pin as 0931-0933 (`results/mutate/yard-gp1-tsl1.json`,
`yard-gp101-tsl1.json`, `yard-gp201-tsl1.json`; heuristic games identical
to `yard-pns1-tsl1.json`, 675 of 675). Same computation as the table above
(it reproduces the wide column to the digit). Novelty cost, HP, mean (se)
over 675 starts:

| modifier | pns1 | wide s1 | 18 s1 | 18 s101 | 18 s201 | 10-29 |
|---|---|---|---|---|---|---|
| parent edge | -0.09 (0.25) | -0.72 (0.27) | +0.50 (0.24) | -0.91 (0.28) | +0.59 (0.23) | +1.19 (0.23) |
| sharp2 | +6.73 (0.48) | -0.28 (0.29) | +1.14 (0.32) | +2.20 (0.33) | +2.72 (0.33) | +5.42 (0.42) |
| thorns2 | +8.23 (0.48) | +4.20 (0.33) | +2.45 (0.35) | +6.28 (0.41) | +4.62 (0.40) | +4.92 (0.38) |
| ritual2 | -0.22 (0.32) | -1.07 (0.30) | -0.74 (0.33) | -1.02 (0.34) | -0.33 (0.31) | +1.68 (0.35) |
| weakhit1 | +1.40 (0.28) | +0.82 (0.25) | +1.00 (0.26) | +1.63 (0.27) | +1.01 (0.28) | +1.61 (0.27) |
| metal3 | +1.64 (0.27) | -0.32 (0.19) | +0.08 (0.21) | +1.38 (0.28) | +0.53 (0.24) | +1.56 (0.24) |
| str2 | +0.20 (0.20) | +0.07 (0.21) | -0.01 (0.19) | +0.06 (0.18) | +0.42 (0.20) | +0.01 (0.15) |
| hp1.25 | +0.10 (0.31) | +0.09 (0.27) | -0.60 (0.28) | +0.54 (0.30) | -0.43 (0.28) | +0.73 (0.29) |
| **pooled 4** | **+4.03 (0.28)** | **+0.92 (0.19)** | **+0.96 (0.22)** | **+2.27 (0.23)** | **+2.01 (0.23)** | **+3.41 (0.25)** |

Minus pns1, pooled 4: 18 s1 -3.07 (0.26), s101 -1.76 (0.25), s201 -2.03
(0.25); wide s1 -3.11 (0.26).

**Verdict on the probe's rule: between.** Replicated needed every seed at
most half pns1's 4.03 at 2 se: seed 1 is (0.96), seed 201 sits at the bar
(2.01) and seed 101 above it (2.27). The wide grid carries it would need
the 18-mechanic nets within 0.5 HP of pns1: they are 1.8-3.1 HP below. So
the 18-mechanic pool already gives most of the yardstick cut, 1.75 pooled
over three seeds (57% off pns1's single seed), with a seed spread of about
0.7 HP (sd over the three seeds).

What it says beyond its question:
- **Seed 1 is a good seed for both recipes.** The wide net s1 (0.92) and
  the 18-mechanic s1 (0.96) are level; the wide grid's yardstick edge over
  the 18 mechanics is not shown until wide seeds 101 and 201 read. Per row
  the wide net is ahead where its grid adds triggers on attacks: sharp2
  -0.28 against +1.14 to +2.72, metal3 -0.32 against +0.08 to +1.38.
- **Thorns 2 is seed noise at this size.** The 18-mechanic seeds spread
  2.45 / 6.28 / 4.62 HP on thorns2 (sd about 1.9), so the wide net's +4.20
  is inside the 18-mechanic range and one learn cannot show it halved.
  This bears on candidate 70 (its pick rule is one seed against +4.20).
- **Ritual 2 is repaired by every 40k from-scratch net**, generated pool
  or not: pns1 -0.22, the three 18-mechanic seeds -0.33 to -1.02, the wide
  net -1.07, against the 10-29 net's +1.68 (0.35). The cost that bursts
  and rate columns never moved on the 10-29 net (`cause/novelty-is-horizon`)
  is gone in the newer from-scratch recipe; what in the recipe does it
  (40k games, the 31-card pack, the turn-start leaf in its labels) is not
  separated by these files.
- Parent edges spread -0.91 to +0.59 across the 18-mechanic seeds: the
  wide net's -0.72 is inside it.
