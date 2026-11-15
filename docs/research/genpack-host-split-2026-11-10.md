# Generated-pack net seed 1: the bench split by parent (navigator, 2026-11-10)

From the two existing files of `lane/generated-pack-scratch`'s seed-1 read,
no new games: `results/mutate/gen-pns1-tsl1-all24.json` (pack-net-scratch
seed 1 @tsl1, job 0797) and `results/mutate/gen-gp1-tsl1-all24.json` (the
generated-pack net seed 1 @tsl1, job 0809), 675 official elite starts x 8
seeds, the heuristic's games identical in both.

Why split by parent: `scripts/gen_enemy_pack.py` puts the 18 training
mechanics on copies of eight official monsters (Gremlin Nob and Sentry
among them) and leaves Lagavulin official, so no training game ever showed
a generated mechanic on Lagavulin. Lagavulin's rows test whether what the
net learned is a value per mechanic that carries to a new host, or a value
per (host, mechanic) pair.

Measure: per start, the mean over a set of mechanics of (net HP lost minus
the heuristic's) on the mechanic minus the same on the parent; a loss
costs the entry HP; mean (se) over starts; gain = base minus genpack; cut
= gain / base. Pooled over all three parents this gives the lane's numbers
(held-out +5.17 (0.21) to +0.98 (0.13), cut 0.81), so the method matches.

| parent | n | mechanics | base (pns s1) | genpack s1 | gain | cut |
|---|---|---|---|---|---|---|
| Gremlin Nob (host in training) | 229 | held-out 6 | +6.08 (0.36) | +2.06 (0.20) | +4.02 (0.30) | 0.66 |
| Gremlin Nob | 229 | training 18 | +1.93 (0.19) | +0.40 (0.12) | +1.53 (0.17) | 0.79 |
| **Lagavulin (never a host)** | 231 | held-out 6 | +1.40 (0.20) | -0.04 (0.23) | **+1.44 (0.25)** | 1.03 |
| **Lagavulin (never a host)** | 231 | training 18 | +2.02 (0.19) | -1.26 (0.24) | **+3.28 (0.26)** | 1.62 |
| Three Sentries (host in training) | 215 | held-out 6 | +8.24 (0.37) | +0.94 (0.21) | +7.30 (0.37) | 0.89 |
| Three Sentries | 215 | training 18 | +2.03 (0.25) | -2.92 (0.23) | +4.94 (0.28) | 2.44 |

Reading: on the host it never saw with any generated mechanic, the net
removes the whole cost of the held-out mechanics (5.8 se) and of the
training mechanics (12.6 se). So, on seed 1, the learned part is a value
per mechanic that moves to a new host, not a table of (host, mechanic)
pairs. Limits: Lagavulin's base costs are the smallest of the three
parents (held-out +1.40 against +6.08 and +8.24), so the host test has
less to cut; one seed; the host is an elite, and bosses (longer fights,
the horizon) are not covered. Probes 0842-0845 (navigator,
`docs/backlog.md` candidate 56) read the same net on bosses and on
stacked mechanics.
