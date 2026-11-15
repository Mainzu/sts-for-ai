# Strength priced by the hits it will still land: reads

Lane `strength-by-hits-left` (charter `lane/strength-by-hits-left`; spec
docs/specs/strength-hits-price.md). The player is the 10-29 net
`@shl<k>@tsl1@hpb0.01`, one turn deep, on gen batch 1, elites, the first
1000 starts (675 elite) x 4 seeds, the command of probe 0472. Every cell
is paired by start and seed with the first 4 of
`results/mutate/gen-enemies-b1.json`'s 16 seeds (zero-shot) and with 0472
(`@esp0.04`); the heuristic's parent results are identical in all three
files (0 of 675 rows differ), and the script reproduces 0472's published
cells exactly. Cost = (net - heuristic)(mechanic) - (same)(ladder control),
HP lost per elite fight, mean (se over starts). Read with
`scripts/analysis/shl_pair.py` (charter cells) and `mutate_monsters.py
read-gen` (all cells).

## Step 2, scale 0.005 (job 0554, 2026-11-08)

`jobs/done/0554-mutate-monsters.json`, `results/mutate/gen-b1-shl0.005.json`;
30 min at 3 threads (0472: 45 min), peak 1.6 GB.

| cell | zero-shot | `@esp0.04` | `@shl0.005` | shl - zero | bar | net wins zero / shl |
|---|---|---|---|---|---|---|
| AttackLoss-Damage x Nob (229) | +13.29 (0.90) | -0.06 (0.38) | +3.80 (0.58) | -9.49 (0.78) | halve at 2 se: pass | 0.698 / 0.890 |
| AttackLoss-Strength x Nob (229) | +2.29 (0.52) | +21.81 (1.06) | +4.65 (0.54) | +2.37 (0.57) | within 1.5: **fail** | 0.879 / 0.892 |
| AttackLoss-Strength x Lagavulin (231) | +1.89 (0.55) | +17.76 (0.96) | +2.94 (0.56) | +1.05 (0.45) | within 1.5: pass | 0.912 / 0.909 |
| AttackLoss-Strength x Sentries (215) | -2.82 (0.56) | +13.40 (0.93) | -2.97 (0.53) | -0.15 (0.27) | within 1.5: pass | 0.962 / 0.966 |
| Nob parent, net HP lost | | +1.74 (0.24) | | -0.36 (0.18) | within 0.5: pass | |
| Lagavulin, Sentries parents | | 0 | | 0 | pass | |

**Verdict at 0.005: fail, narrowly**, on one cell: AttackLoss-Strength x
Nob costs 2.37 HP more than zero-shot (bar 1.5; the bar's lower 2-se edge
is 1.23). Everything else passes: the price keeps 71% of the flat price's
Nob cut, and where the flat price cost +13 to +22 HP on AttackLoss-Strength
it costs +1.05 and -0.15 on Lagavulin and Sentries.

**Why (a reading of the numbers, not traced in games).** On Lagavulin and
Sentries all the monster's Strength comes from being hit, and the price
falls as attacking shortens the fight, so it no longer stops the net
attacking: that was the missing term, and the read confirms it. On
Nob under AttackLoss-Strength both kinds of play feed Strength (Skills feed
Enrage, attacks feed the mechanic), and a Nob fight is long (about 10
rounds at the start), so the price is high whichever card is played; the
net then trades HP for safety: its wins rise (0.879 -> 0.892) while HP lost
rises 2.4. The same trade shows on AttackLoss-Damage x Nob, where wins rise
to 0.890 but stay under `@esp0.04`'s 0.942. On the unmodified Nob the price
helps a little (-0.36 HP, 0.18), a goal-2 lead for step 3 if a scale passes.

**What it changes.** The lane's go needs one scale; 0.01 (job 0555,
queued, waiting for memory) is the stronger price and is expected to cut
Nob's AttackLoss-Damage cost further and cost more on AttackLoss-Strength x
Nob, so a pass at 0.01 is less likely than at 0.005. Both scales failing
closes the lane by its stop rule.

## Step 2, scale 0.01 (job 0555, 2026-11-08), and the lane's verdict

`jobs/done/0555-mutate-monsters.json`, `results/mutate/gen-b1-shl0.01.json`;
31 min at 3 threads, peak 1.31 GB. Same pairing (0 heuristic rows differ).

| cell | zero-shot | `@shl0.005` | `@shl0.01` | 0.01 - zero | bar | net wins zero / 0.01 |
|---|---|---|---|---|---|---|
| AttackLoss-Damage x Nob | +13.29 (0.90) | +3.80 (0.58) | +0.98 (0.38) | -12.31 (0.84) | halve: pass | 0.698 / 0.941 |
| AttackLoss-Strength x Nob | +2.29 (0.52) | +4.65 (0.54) | +11.67 (0.90) | +9.38 (0.92) | within 1.5: **fail** | 0.879 / 0.847 |
| AttackLoss-Strength x Lagavulin | +1.89 (0.55) | +2.94 (0.56) | +6.66 (0.71) | +4.77 (0.70) | within 1.5: **fail** | 0.912 / 0.873 |
| AttackLoss-Strength x Sentries | -2.82 (0.56) | -2.97 (0.53) | -1.15 (0.56) | +1.67 (0.36) | within 1.5: **fail** | 0.962 / 0.962 |
| Nob parent, net HP lost | | -0.36 (0.18) | +0.30 (0.20) | | within 0.5: pass | |

**Verdict: fail at both scales; the lane stops (checkpoint gen-b1-scales
failed).** The price does what the flat one did on Nob's AttackLoss-Damage
(0.01 matches `@esp0.04`: +0.98 against -0.06, wins 0.941 against 0.942),
and it does cut the flat price's AttackLoss-Strength damage by a half to
nine-tenths (Nob +9.4 against +19.5, Lagavulin +4.8 against +15.9,
Sentries +1.7 against +16.2). But no scale does both: the dose that
removes the Nob cost (0.01) already stops the net attacking where attacks
feed Strength, and the dose that leaves attacking alone (0.005) keeps a
quarter of the Nob cost and still costs 2.4 HP on AttackLoss-Strength x
Nob.

**Why.** The price is a level, not a change: every leaf of a decision pays
for the Strength the monster already holds times the hits left, and the
choice is ranked by the difference. An attack on an AttackLoss-Strength
monster adds Strength (a cost that scales with all the hits left) and
shortens the fight by a few rounds (a credit that scales only with the
Strength already held, small early in the fight). Early on the cost wins,
so a larger k still discourages attacking; the turns-left term softens it
but does not reverse it until Strength is large. The charter's "against"
(the estimate is crude early, where a long fight prices Strength fully)
is what happened. On Nob both actions feed Strength, so there is no cheap
action to switch to, and the net pays in HP.

**What it changes.** A zero-games leaf price does not repair the HP price's
walk into enemy Strength on generated punish-an-action mechanics at
one turn deep without breaking the mechanic that makes Strength from hits;
games do (`measurement/family-transfer@gen-b1`, about 100 games a mechanic,
`gen-adapted-column`). The `@shl` flag stays in the code, off by default.

## Held-out read: @shl0.005 on the 16 mechanics outside batch 1 (job 0566, navigator probe, 2026-11-08)

`jobs/done/0566-mutate-monsters.json`, `results/mutate/gen-rest-shl0.005.json`;
the 10-29 net `@shl0.005@tsl1` (`@hpb0.01` added), 675 elite starts x 4
seeds, 29 min at 3 threads, peak 1.04 GB. Paired by start and seed against
the first 4 seeds of `results/mutate/gen-enemies-b1.json` (zero-shot); the
heuristic rows match on all 10,800 mechanic x start pairs. Change = the
net's HP lost with the price minus without it, on the mechanic's own
fights (se over starts); wins zero-shot > price.

| mechanic x Nob | change | wins |
|---|---|---|
| AttackLoss-Weak | -4.55 (0.52) | 0.838 > 0.902 |
| TurnEnd-Weak | -2.38 (0.34) | 0.921 > 0.933 |
| TurnStart-Weak | -2.25 (0.36) | 0.921 > 0.936 |
| OppCard-Damage | -1.86 (0.32) | 0.896 > 0.927 |
| AttackLoss-PlainDamage | -1.66 (0.30) | 0.954 > 0.966 |
| OppCard-Weak | -1.41 (0.36) | 0.874 > 0.892 |
| TurnEnd-PlainDamage | -1.23 (0.23) | 0.956 > 0.964 |
| TurnStart-Block | -1.15 (0.28) | 0.944 > 0.953 |
| TurnStart-PlainDamage | -1.03 (0.24) | 0.956 > 0.963 |
| OppCard-Block | -0.94 (0.22) | 0.969 > 0.972 |
| AttackLoss-Vulnerable | -0.89 (0.24) | 0.903 > 0.918 |
| TurnStart-Vulnerable | -0.37 (0.15) | 0.936 > 0.940 |
| TurnEnd-Vulnerable | -0.35 (0.16) | 0.933 > 0.940 |
| OppCard-Frail | +0.14 (0.09) | 0.976 > 0.974 |
| AttackLoss-Frail | +0.22 (0.10) | 0.977 > 0.977 |
| TurnStart-Frail | +0.34 (0.12) | 0.978 > 0.978 |

Lagavulin and Sentries: every row identical to zero-shot (change +0.00,
wins equal): no monster there holds Strength, so the price is zero at
every leaf. Mean change over the 16 mechanics and all three parents -0.41
(0.06) HP per elite fight; on Nob -1.21 (0.15).

**Verdict: go** on the probe's rule (no row worse by 1.5 HP at 2 se or
0.03 wins; mean not above 0). The trade the lane found stays on the one
cell where the mechanic itself feeds Strength on attacks
(AttackLoss-Strength x Nob, +2.37); everywhere else the price is inert or
helps. The help is all on Nob, where Enrage grows with every Skill and
the mechanics make fights longer, so the price on Strength x hits left
weighs more; it is largest where the mechanic also weakens the player
(the Weak rows), which lengthens the fight further. The three Frail rows
cost +0.1 to +0.3 HP (1.5-2.9 se), wins level: Frail cuts block, so a
price that leans toward ending Nob sooner trades a little block there.
Next: the one-turn headline with the price against the one-turn control
(job 0572), which reads it on official play, Nob fights included.

## Headline read: @shl0.005 one turn deep is level on the headline (job 0573, navigator probe, 2026-11-08)

The 10-29 net `@hpb0.01@shl0.005` on the headline setting (own picks,
sequences 0-499, `--vary price`) against the one-turn control
`results/gauntlet/net1029-hpb0.01-starter-simboss.json`; file
`results/gauntlet/net1029-hpb0.01-shl0.005-starter-simboss.json`, 60
minutes at 3 threads, peak 0.78 GB. The protocol stays open at n 500
(no pass, no fail).

- Paired end HP +0.95 (0.64), clears 0.692 against 0.680, +0.012
  (0.016), z +0.74; train half +0.008, held-out half +0.016.
- Deaths by encounter (price / control): Hexaghost 51 / 42, the Guardian
  45 / 47, Slime Boss 11 / 18, Gremlin Nob 11 / 13, Lagavulin 9 / 11,
  Sentries 7 / 11.
- HP lost per fight, paired on sequences that met the fight at the same
  entry HP (se over sequences): Gremlin Nob -0.30 (0.40), n 190 (the bench
  predicted -0.36 (0.18) on the unmodified Nob); Lagavulin +0.28 (0.16)
  and Sentries -0.02 (0.17), where no monster gains Strength and the
  price is zero, so these show how far the decks diverge; the bosses
  inside 1.3 se.

Reading: the price costs official play nothing and gains nothing that
the headline can see: the Nob gain is the bench's size and under 1 se
here. By its read rule (decisions "After shl-held-out") a level result
makes `@shl0.005` goal 1's candidate leaf only; the one-turn controls
and the product stay as they are.
