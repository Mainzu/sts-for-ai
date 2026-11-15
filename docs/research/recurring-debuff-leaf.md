# Recurring debuff leaf (lane `recurring-debuff-leaf`)

Charter: `kb get lane/recurring-debuff-leaf`; spec
`docs/specs/recurring-debuff-leaf.md`.

## Step 1: the `@pd1` flag (built 2026-11-10)

`CombatState::projected_leaf_with(k, debuffs)`; `SearchConfig.projected_debuffs`;
evaluator key `projected_debuffs`; player setting `@pd1`, only with `@pl<k>`.
With the flag, a living monster's once-a-turn hook (OwnerTurnStart or
OwnerTurnEnd, no self-removal) also runs its Apply of Weak, Frail or
Vulnerable to the player k more times at the end-of-turn leaf, through the
engine's `apply_power` (Artifact cancels). Off by default; `@pl<k>` alone
unchanged (`engine/tests/projected_leaf.rs`); golden unchanged.

## Step 2 read

Jobs 0764 (k 2) and 0765 (k 4): two arms, the 10-29 net one turn deep `@tsl1@pl<k>@pd1@hpb0.01`, k = 2 and
4, on GE-TurnStart-Weak, GE-TurnEnd-Weak, GE-TurnStart-Frail,
GE-TurnEnd-Frail and their parents, 675 elite starts x 8 seeds, against
`results/mutate/gen-wf-tsl1.json` (job 0760, the same net `@tsl1`).

Read: `mutate_monsters.py compare results/mutate/gen-wf-tsl1.json
<arm>` (win rate: the base's novelty cost, the arm's gain net of parents,
the cut, the parents' change), plus the same contrast in HP lost per elite
fight. Go (charter): at one k, both Weak rows cut by half or more with the
gain 2 se above zero, and the parents within 0.3 HP.

### Result (read 2026-11-10): fail

Win rate (`mutate_monsters.py compare`, mean (se)):

| row | base cost | k 2 gain | k 2 cut | k 4 gain | k 4 cut |
|---|---|---|---|---|---|
| TurnStart-Weak | -0.011 (0.003) | +0.006 (0.002) | 0.56 | +0.008 (0.003) | 0.71 |
| TurnEnd-Weak | -0.013 (0.003) | +0.005 (0.002) | 0.35 | +0.007 (0.003) | 0.50 |
| TurnStart-Frail | -0.002 (0.002) | +0.001 (0.001) | 0.70 | +0.001 (0.001) | 0.70 |
| TurnEnd-Frail | -0.002 (0.002) | +0.000 (0.001) | 0.20 | -0.001 (0.001) | -0.50 |
| parents | | +0.000 | | -0.001 (0.001) | |

HP lost per elite fight (the novelty cost is one minus heuristic, modified
minus parent; a negative change is fewer HP lost):

| row | base cost | k 2 change | k 2 cut | k 4 change | k 4 cut |
|---|---|---|---|---|---|
| TurnStart-Weak | +2.55 (0.20) | -0.30 (0.10) | 0.12 | -0.48 (0.14) | 0.19 |
| TurnEnd-Weak | +2.95 (0.20) | -0.40 (0.12) | 0.14 | -0.69 (0.15) | 0.23 |
| TurnStart-Frail | +0.44 (0.10) | +0.03 (0.06) | - | +0.28 (0.11) | worse |
| TurnEnd-Frail | +0.67 (0.11) | +0.03 (0.08) | - | +0.32 (0.13) | worse |
| parents | (14.5 lost) | -0.06 (0.05) | | +0.09 (0.08) | |

Verdict: **fail**. The spec's rule asks both measures. In win rate, k 4 just
reaches it (TurnEnd-Weak's cut is 0.50, exactly the bar, at 2.3 se). But the
win-rate cost is only about 1 point of win rate, so its cut has a wide error
(about 0.7 +- 0.3 and 0.5 +- 0.25). HP lost is the precise measure here. In
HP the projection repairs about a fifth of the Weak cost (0.19 and 0.23, se
about 0.05), far from half. Parents stay within 0.1 HP at both k, so
retention holds. At k 4 the Frail rows get 0.3 HP worse (2.5 se).

Why, by encounter (k 4, HP; cost / change):

| encounter | TurnStart-Weak | TurnEnd-Weak | TurnEnd-Frail |
|---|---|---|---|
| gremlin_nob (229) | +2.59 / -0.97 | +3.01 / -1.65 | +0.37 / -0.37 |
| lagavulin (231) | +2.42 / -0.73 | +2.49 / -0.70 | +0.73 / +0.48 |
| three_sentries (215) | +2.65 / +0.30 | +3.37 / +0.35 | +0.92 / +0.89 |

On the one-monster elite the projection works: Gremlin Nob's TurnEnd-Weak
cost is cut by 55%. Lagavulin is cut by about 30%. On Three Sentries it
hurts. The modifier puts the hook on every sentry, so the leaf applies the
debuff k times per living sentry (12 Weak at k 4). The leaf then rates
states with more sentries alive as far worse than they play out, because
Weak's turns don't stack that way in a real fight: they extend its duration,
and the player is Weak either way. The same over-count would explain the
Frail rows getting worse at k 4. So "k more times per monster" is the wrong
count for a debuff whose duration stacks. A projection of the debuff's
*duration* (the player stays Weak for the next k turns, once, however many
monsters apply it) would fit better. That is a different flag; this lane's
one read is spent.
