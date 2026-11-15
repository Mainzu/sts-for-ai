# genpack-reach: how far the generated-pack net's zero-shot cut reaches

Navigator probes on lane `main` (decisions "Generated-pack seed 1 go:
genpack-reach probes queued, wider-generators re-scoped and readied"),
pin 33fd633. Two nets, both @tsl1 one turn deep: pack-net-scratch seed 1
(`runs/2026-11-10-packnet40k-s1-r1-64badf9`, "pns s1") and the
generated-pack net seed 1 (`runs/2026-11-10-genpack40k-s1-r1-acf5102`,
"genpack s1"), the 10-29 net's earlier file beside them.

## Stacks (0842-0843): the cut composes, about half of the cost at the death cap

`random_world.py nd-play`, k 4, 40 main worlds of the 21 generated
mechanics, 50 shared official elite starts x 4 seeds, no-death mode,
each net with its own base file (`results/mutate/rw-nd-pns1-k4.json`,
`results/mutate/rw-nd-gp1-k4.json`); the 10-29 net's k-4 worlds from
`results/mutate/rw-nodeath.json` (same starts, same worlds). Cost = the
net's HP lost beyond its parent fight minus the heuristic's, mean over
worlds (se over worlds); S = the same summed over the world's single
mechanics; g = cost - 1.5 S. HP lost is capped per game as in
`measurement/random-world@nodeath` (`scripts/analysis/rwb_nodeath_caps.py`);
the start-HP cap counts a death as the whole start HP, the play-like
measure; uncapped no-death loss is not a play measure.

| cap | pns s1 cost | genpack s1 cost | 10-29 net cost | genpack - pns, paired by world | ratio | S pns / genpack |
|---|---|---|---|---|---|---|
| start HP | +6.16 (0.23) | +3.16 (0.18) | +6.38 (0.20) | -3.01 (0.18) | 0.51 | +15.75 / +6.16 |
| start HP + 30 | +7.28 (0.46) | +1.62 (0.34) | +6.79 (0.36) | -5.66 (0.36) | 0.22 | +17.33 / +4.05 |
| 100 | +7.18 (0.48) | +1.19 (0.35) | +6.30 (0.35) | -6.00 (0.40) | 0.17 | +16.62 / +3.57 |
| 150 | +9.22 (0.94) | -1.07 (0.53) | +6.50 (0.65) | -10.29 (0.88) | -0.12 | +17.39 / +2.42 |
| uncapped | +182.74 (48.60) | +47.43 (18.00) | +125.81 (37.15) | -135.31 (38.38) | 0.26 | +20.55 / +1.91 |

Heuristic raw loss over its parent at the start-HP cap +25.49; deaths
(uncapped file, HP at or below 0) net / heuristic: pns 0.57 / 0.51,
genpack 0.49 / 0.51. g is negative for every net at every cap (less than
additive, as `measurement/random-world@nodeath`).

Against the probe's rule (go if genpack's k-4 cost is under half of pns
s1's at 2 se): under the three looser caps, go by far (0.17-0.22 of pns,
the paired cut 14-16 se); at the start-HP cap the ratio is 0.51, the
rule's line (genpack - 0.5 x pns = +0.08 (0.2)), with the cut itself
-3.01 (0.18), 17 se. On singles the death-capped cut is 61% (S 15.75 to
6.16), on 4-mechanic worlds 49%: a fight with four unseen generated
mechanics keeps about four fifths of the singles' cut. Where deaths
count as the whole start HP, about half of the stack cost is left, most
of it deaths: genpack dies as often as the heuristic (0.49 / 0.51), but
four mechanics at once still kill more than the parent does.

Pack-net-scratch seed 1 stacks no better than the 10-29 net (+6.16
against +6.38 at the death cap) and is worse on singles (15.75 against
13.86): the from-scratch recipe alone does not price generated
mechanics; the generated pack does (as `measurement/pack-net-gen-bench@seed1`).

What it changes: the cut composes, so the pooled generated-pack net
(once 47's seeds pool) is goal 1's base for enemy mechanics with stacks
included. The bench is cheap (12-15 minutes at 3 threads, about 0.7
thread-h per net) and its paired se at the death cap is 0.18 HP, so it
joins `wider-generators` (53)'s step-3 reads as a guard at k 4, read at
the start-HP cap.

## Bosses (0844-0845): the cut reaches the official bosses, on a small base cost

`mutate_monsters.py play --groups boss`, the 24 generated mechanics on the
325 official boss fights of the bench (Slime Boss 110, Hexaghost 110, the
Guardian 105) x 4 seeds, heuristic and each net one turn deep @tsl1
(`results/mutate/gen-pns1-tsl1-boss24.json`,
`results/mutate/gen-gp1-tsl1-boss24.json`). The heuristic's games are
identical in both files. Novelty cost = the net's change from the parent
minus the heuristic's, paired by start (mean over seeds), se over starts;
the cut's se by the delta method. The pack never carried a mechanic on a
boss: a host kind the net never trained on with these mechanics.

| rows | pns s1 cost (HP) | genpack s1 cost | gain | cut | wins gain |
|---|---|---|---|---|---|
| held-out pooled (6) | +1.21 (0.26) | +0.23 (0.26) | +0.98 (0.24) | **0.81 (0.19)** | +0.030 (0.009) |
| training pooled (18) | +1.82 (0.28) | +0.25 (0.26) | +1.57 (0.23) | 0.86 (0.13) | +0.045 (0.008) |
| parent (no mechanic) | net HP lost 38.47 | 38.48 | | | wins 0.724 / 0.713 |

Held-out rows: AttackLoss-Weak +1.66 to -0.74, OppCard-Damage +1.37 to
+0.29, OppCard-PlainDamage +1.27 to +0.56, TurnEnd-Weak +1.36 to +0.74,
TurnEnd-Frail +1.04 to +0.62, AttackLoss-Damage +0.58 to -0.10. By boss,
held-out pooled gain: Slime Boss +0.91 (0.50), Hexaghost +1.05 (0.35),
the Guardian +0.99 (0.36) (its base cost the largest, +2.59). The largest
training-row gains are the Vulnerable and Weak rows on OppCard and
AttackLoss (+3.4 to +5.3 HP, +0.10 to +0.14 wins).

Against the probe's rule (go if the held-out pooled boss cost falls by
0.4+ at 2 se; stop if pns s1's held-out cost is under 1 HP): go, cut 0.81
(0.19), 0.43 at 2 se, with pns s1's base +1.21. The cut is the same share
as on the elites (0.81 there too, `measurement/genpack-transfer@seed1`),
but the base cost on bosses is a quarter of the elites' (+1.21 against
+5.17), so the gain is about 1 HP per boss fight, not the 2 HP the probe
predicted. Bosses' costs are small one turn deep because a boss fight's
cost is mostly its own horizon (`cause/boss-deaths`), which a generated
power adds little to.

What it changes: with stacks (above), both halves of genpack-reach go.
The generated-pack net's value per mechanic moves to hosts the pack
never carried, elites and bosses, and holds when mechanics stack. Bosses
need not join `wider-generators` (53)'s pack before its learn (its step
2's boss reads stay off, as its charter says for this branch).
