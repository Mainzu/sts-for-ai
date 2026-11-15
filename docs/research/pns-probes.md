# Navigator probes on the pack net (pack-net-scratch's nets)

Probes the navigator queued in lane `main` beside lane `pack-net-scratch`
(backlog probe sheet; decisions "Probe pns1-gen-bench queued", "Probe
pns-twin and pns-official queued", "Probe pns1-gen-bench read").

## pns1-gen-bench (0762): the pack net loses generated-bench play zero-shot

Job 0762 (`jobs/done/0762-mutate-monsters.json`, pin 48b2bef): pack net
seed 1 (`runs/2026-11-10-packnet40k-s1-r1-64badf9/model.pt@tsl1`) one turn
deep on the generated-enemies bench's eight costliest or edge rows, 675
official Act 1 elite starts x 16 seeds, `results/mutate/gen-pns1-tsl1.json`,
against the 10-29 net with the same player string on the same starts,
seeds and generated pack (f12ea528) in `results/mutate/gen-enemies-b1.json`.
The job's note says `@hpb0.01@tsl1`; both files played `@tsl1` alone, so
they match.

`mutate_monsters.py compare` (win rate; base cost = the 10-29 net's change
from parent, gain = the pack net's change against it):

| row | 10-29 cost (wins) | pack net gain (wins) |
|---|---|---|
| AttackLoss-Damage | -0.083 (0.007) | -0.053 (0.007) |
| OppCard-Weak | +0.052 (0.009) | +0.045 (0.008) |
| AttackLoss-Weak | -0.066 (0.007) | +0.031 (0.006) |
| OppCard-PlainDamage | -0.042 (0.006) | -0.078 (0.008) |
| OppCard-Damage | -0.053 (0.006) | -0.086 (0.008) |
| TurnStart-Weak | -0.011 (0.003) | -0.011 (0.004) |
| TurnEnd-Weak | -0.013 (0.003) | -0.012 (0.004) |
| OppCard-Vulnerable | +0.153 (0.012) | -0.304 (0.014) |

HP lost per elite fight, pack net minus 10-29, raw (paired by start; se
over starts). Parent (unchanged elites) +0.62 (0.16): Nob +0.92, Lagavulin
+0.28, Sentries +0.66. Rows: AttackLoss-Damage +3.22 (0.40; Nob +5.89),
OppCard-PlainDamage +2.15 (0.28; Sentries +4.54), OppCard-Damage +1.92
(0.29; Sentries +4.38), TurnStart-Weak +1.69 (0.26), TurnEnd-Weak +1.63
(0.27), OppCard-Vulnerable +11.67 (0.75; Lagavulin +18.61, Sentries
+12.58), and better on OppCard-Weak -2.24 (0.51; Sentries -8.19, Nob +2.50)
and AttackLoss-Weak -2.06 (0.40; Sentries -4.61).

By the probe's rule: not "breadth carries" (one costly row cut, by
0.48, where three were needed) and not level: five of the seven costly
rows cost more at many se and the OppCard-Vulnerable edge is lost, so the
guard branch holds. The pack net is not a goal-1 base for generated packs.

What it may mean. Two readings, which 0779 and 0780 separate:
- **The pack's few lessons.** The pack net is the first net trained from
  scratch at today's vocabulary with pack monsters in training. Its only
  example of the OwnerLostHp-from-Attack trigger is Angry (Mad Gremlin:
  +1 Strength when hit, `content/packs/act1-monsters.json`), so it may price
  the trigger by a weak hallway gremlin; the 10-29 net reads 8 of 19
  triggers (`how/burst-inputs`) and may not see some generated triggers at
  all. A narrow lesson would cost more than blindness. This fits
  AttackLoss-Damage, not the OppCard rows: neither net saw an OppCard
  trigger beyond Gremlin Nob's Enrage.
- **The recipe.** 40k games, one round, every card (the 10-29 net: 20k,
  ten rounds, the train half). The parent itself costs +0.62 HP, and the
  OppCard rows, which no pack power touches, cost the most, so the
  recipe may be weaker off its training content.
0779 (the all-content twin: the same config minus the packs, seed 1) and
0780 (pack net seed 101) on the same rows: the twin as bad points to the
recipe; the twin near the 10-29 net points to the pack; seed 101 says
whether it is the seed.

For `generated-pack-scratch` (47): its go compared the held-out rows with
pack net seed 1 only, which now sits well below the 10-29 net on them, so
a go could mean no more than catching up. The charter now also needs the
held-out rows not worse than the 10-29 net's at 2 se.

## pns-twin (0770-0773): the all-content recipe carries the pack net's gain; the pack costs official cells

Jobs 0770-0773 (pin 2af5b30, the pack lane's `sts` bytes): the all-content
nets of 2026-11-08 (`runs/2026-11-08-allcontent40k-s1-r1-887ca04`,
`-s101-r1-ce824da`; `configs/allcontent40k-s*.json` is
`configs/packnet40k-s*.json` without `packs`, same seeds) one turn deep
@hpb0.01 on sequences 0-499, fixed n 500, on the official cells and the
31-card pack headline. Paired end HP (`scripts/analysis/paired_go.py`; the
twin-against-pack-net pools average each side over seeds 1 and 101 per
sequence):

| read | seed 1 | seed 101 | pooled (1, 101) |
|---|---|---|---|
| twin vs control, pack headline | +4.40 (1.00), clears +0.090 | +0.78 (1.02), +0.014 | +2.59 (0.89), +0.052 |
| pack net vs control, pack headline | +3.25 (0.94) | +2.69 | +2.97 (0.85), +0.069 |
| pack net minus twin, pack headline | -1.14 (0.99) | +1.91 (0.96) | +0.38 (0.73), +0.017 |
| twin vs 10-29 net, cells | +2.28 (0.60), +0.040 | +2.36 (0.60), +0.026 | +2.32 (0.54), +0.033 |
| pack net minus twin, cells | -0.67 (0.46) | -1.50 (0.60) | -1.09 (0.39), z -2.80, clears -0.029 |
| pack net vs 10-29 net, cells | | | +1.24 (0.55), +0.004 |

Against the rule in the decisions entry "Probe pns-twin and pns-official
queued": training on the pack does not pay. The pack net beats its twin
by +0.38 (0.73) HP pooled on the pack headline (bar: 2 se above zero and
over half of the gain), and the twin carries 2.59 of the 2.97 (87%). The
seeds disagree (seed 1's twin is the best player on the pack, seed 101's
the weakest), so the split is between -1 and +2 HP per seed, inside about
two single-pair se. On the official cells the pack costs -1.09 (0.39) HP
on both seeds: with a fixed 40k games, fights on pack content take games
from official ones (as `pack-pick-split` found for picks: the drop is
dilution).

What it says:
- **Goal 2.** The gain is the recipe: from scratch, 40k games, one round,
  `deck_pool: all`. For the 10-29 net the cells' held-out half is unseen
  content; for these nets it is training content. So "new content", the
  training rule's reason, is what pays, and the all-content net is the
  stronger official fighter (+2.32 HP on cells against the pack net's
  +1.24). The rule's branch: a twin read on the ruler (0782-0783, beside
  pns-official 0774-0776). The cells' held-out half no longer measures
  zero-shot play for these nets.
- **Goal 1, cards.** Zero-shot, the twin plays the 31 pack cards about as
  well as a net trained on them (pack net minus twin +0.38 (0.73)). This
  agrees with `measurement/act1-cards@zero-shot` (19 of 22 level): effect
  inputs carry new cards. What costs goal 1 is new mechanics, not new
  cards, as the owner's yardstick says (`decision/goal1-yardstick`).
- **For 47.** Base unchanged (pack net seed 1: same code, includes the Act
  1 content). The dilution cost is a risk to its cells guard (within -1.5
  HP of the base): the generated pack should take a bounded share of the
  monster fights. 0779 (the twin on the generated bench) still decides
  whether the recipe or the pack made the pack net worse there.

## pns-twin-official (0782-0783): the all-content gain on the ruler is Demon Form; outside it the twin loses 1.5 HP

Jobs 0782-0783 (pin 2af5b30): the all-content twins (`allcontent40k-s1`,
`-s101` r1 @hpb0.01) one turn deep on the ruler
(`yardstick/headline-setting`, own picks) against
`yardstick/one-turn-controls`, sequences 0-499, fixed n 500. Paired end HP
(`scripts/analysis/paired_go.py`, `--gain <candidate> <control>`):

| read | seed 1 | seed 101 | pooled (1, 101) |
|---|---|---|---|
| twin vs control, ruler | +1.11 (0.98), clears +0.032 | +0.41 (1.02), +0.024 | +0.76 (0.87), +0.028 |
| pack net s1 vs control, ruler (0774) | +0.59 (1.05), +0.038 | | |

By the rule written before the read (pooled +1.5 HP at 2 se) this fails,
and candidate 48 (the product's net becomes an all-content net) retires.

Where it goes. Deaths, control / twin s1 / twin s101: hallways 18 / 30 / 31,
elites 35 / 45 / 45, boss 107 / 69 / 72 (Hexaghost 42 / 23 / 26, the Guardian
47 / 36 / 34, Slime Boss 18 / 10 / 12). The extra elite deaths are at the
second elite (floor 8: 27 to 41 and 26 to 40 on sequences both reach).

Split by Demon Form in the deck (the card the 10-29 net never trained on;
the twins pick it 0.62 and 0.69 of the times offered, the control 0.19):

| sequences | n (s1 / s101) | twin minus control, s1 | s101 |
|---|---|---|---|
| both took Demon Form | 41 / 41 | +19.22 (3.24) HP, clears +0.463 | +15.56 (3.71), +0.390 |
| only the twin took it | 102 / 105 | +3.23 (2.20), +0.118 | +0.41 (2.05), +0.086 |
| neither took it | 356 / 353 | -1.54 (1.12), -0.039 | -1.43 (1.19), -0.037 |

Pooled over both seeds on the 347 sequences where no player took Demon
Form: -1.50 (1.00) HP, second-elite deaths 21 to 31 and 29, boss deaths 68
to 59 and 60. By the cells' halves, pooled: ruler train -0.90 (1.08), held-out
+2.42 (1.36); on the fixed-deck cells (0770-0771) train +0.89 (0.57),
held-out +3.76 (0.91), with elite deaths level (35 / 35, 32 / 36) and boss
deaths down (108 / 94, 103 / 92).

What it says:
- **Goal 2.** The all-content recipe's ruler gain is Demon Form, the
  held-out half's one costly card (`cause/unseen-cards-half-edge`). Two
  turns deep the search already plays its first tick (two turns +8.4 HP on
  Demon Form decks), and outside Demon Form the twin is 1.5 HP worse, its
  deaths moved from the boss to the second elite. A product swap is
  predicted level or worse two turns deep: 48 retires.
- **The chooser's horizon (correction).** `cause/chooser-horizon` said a
  fighter that plays Demon Form right makes the sim chooser overpick it at
  a cost (with `@tsl1`: only the flagged arm took it, 78 sequences, -4.55
  (2.27) HP, -0.115 (0.066) clears; 0333). The twins pick it more often
  (0.62-0.69 against `@tsl1`'s 0.49), and where only they took it they
  gain (+3.23 and +0.41 HP, clears +0.118 and +0.086). So the overpick
  cost belongs to the leaf repair, not to the horizon in general: a net
  that learned the card from games carries its extra picks.
- **Learned against leaf.** On the sequences where both players took
  Demon Form, the twins gain +15.6 to +19.2 HP over the plain control,
  where `@tsl1` on the same control gained +9.93 on its 42. Whether 40k
  from-scratch games taught Demon Form more than its first tick is read
  by twin-tsl1 (0793-0796) against the 10-29 net `@tsl1`, as
  `player-growth-exposure` reads heur-g400.
- **Outside Demon Form.** The -1.50 (1.00) HP could be fighting or picks:
  on fixed decks the twin is level or better on the train half (+0.89
  (0.57)) and level at the elites, which points to picks. pns-twin-matched
  (0791-0792: the twins on the control's own picks, `--match`) splits it.

## pns-twin-matched (0791-0792): on the control's decks the twin fights level outside Demon Form

Jobs 0791-0792 (pin 2af5b30): the all-content twins one turn deep on the
ruler on the control's own picks (`--match
results/gauntlet/net1029-hpb0.01-starter-simboss.json`), sequences 0-499,
fixed n 500, against `yardstick/one-turn-controls`:

| read | seed 1 | seed 101 | pooled (1, 101) |
|---|---|---|---|
| matched twin vs control | +1.69 (0.68), clears +0.024 | +0.61 (0.63), +0.012 | +1.15 (0.57), z 2.00, +0.018 |
| control's Demon Form decks (41) | +14.07 (2.24), +0.317 | +12.71 (2.79), +0.268 | |
| the other 457 sequences | +0.58 (0.69) | -0.47 (0.62) | +0.05 (0.56) |
| by half, pooled | | | train -0.90 (0.73), held-out +3.19 (0.87) |

Under the +1.5 HP bar: a fail by the note's rule (48 was already retired).
Deaths control / s1 / s101: hallways 18 / 24 / 35, elites 35 / 41 / 43,
boss 107 / 83 / 76; outside Demon Form decks the second elite 25 / 32 / 33
and the boss 93 / 81 / 73.

What it says:
- **Fighting against picking.** Outside Demon Form the twins fight level
  on the control's decks (+0.05 (0.56)) and lose -1.50 (1.00) on their own
  picks (0782-0783, on the 347 sequences where no player took it). So about
  1.5 HP of the own-pick shortfall is the one-round recipe's picks, at about
  1.4 se: a lead, not a result. For `generated-pack-scratch` (47), whose
  pack net uses this recipe, own-pick pack-headline reads may carry that
  cost; its cell and bench reads (fixed decks) do not.
- **The trade inside the fight.** On the same decks, outside Demon Form,
  the twins die more at the second elite (25 to 32-33) and less at the
  boss (93 to 73-81), at level HP: the from-scratch net trades elite HP for
  boss wins, which the per-fight end-HP score does not price.
- **Learned against leaf, re-read.** On the control's 41 Demon Form decks
  the twins gain +14.07 and +12.71 HP, against `@tsl1`'s +9.93 on the
  control's 42 (own picks, `measurement/turn-start-leaf@headline`). The gap
  is about 3.5 HP at about 1 se, smaller than the 6-9 HP the own-pick split
  showed. twin-tsl1 (0793-0796) is the paired test.

## twin-tsl1 (0793-0796): from-scratch games taught Demon Form more than its first tick

Jobs 0793-0796 (pin 4056504, the pin of `player-growth-exposure`'s
0784-0789): the all-content twins (`allcontent40k-s1`, `-s101` r1)
@hpb0.01@tsl1 on both cell books (sequences 0-999), paired against the
10-29 net @hpb0.01@tsl1 (`results/gauntlet/net1029-hpb0.01-tsl1.json`,
`-tsl1-b500.json`) with `cards_by_half.complete_nets` and `strata_row`,
two nets pooled (se over sequences, then over nets):

| stratum | n | twins minus 10-29, both @tsl1 | clears |
|---|---|---|---|
| train decks | 500 | +0.56 (0.43, 0.09) | -0.009 (0.014) |
| other held-out decks | 326 | -0.04 (0.60, 0.17) | -0.020 (0.013) |
| held-out Demon Form decks | 174 | **+3.30 (0.95, 0.35)** | +0.034 (0.021) |
| seed 101 alone, Demon Form decks | 174 | +2.95 (0.99) | +0.017 |

Beside it, heur-g400 @tsl1 (the lane's step 1, two of three nets in at the
time of this read): train -1.50, other held-out -1.73, Demon Form decks
-1.20 (0.93, 1.66).

By the rule written before the read: go. Demon Form decks are 3.5 se above
zero (the larger se, over sequences), train decks within -0.9 HP, and the
other held-out stratum sits 3.3 HP under Demon Form's (about 3 se on the
difference). With the first tick shown to both players by `@tsl1`, the
twins still play Demon Form decks 3.3 HP better: what they learned about
the card goes past its first tick (later ticks, or when to play it, which
also pays over later turns). Training on held-out cards in general bought
nothing on the other held-out decks, as `cause/unseen-cards-half-edge`
predicts for cards whose effect lands inside the turn.

What it says:
- **Goal 1.** This is the first learned later-tick value on file. Bursts of
  100-1600 games on a trained net learned the first tick only, at every
  exposure share read so far (`measurement/demon-form-games@tsl1`; burst8
  @tsl1 +0.48 (0.81); two-g400 -0.42 (0.94); heur-g400 above, at 52%
  exposure). A from-scratch learn of 40k games with the card in the pool
  learned it. What differs is the game count (40k against at most 1.6k),
  the start (from scratch against a trained net) or both: candidate 49's
  dose read separates them.
- **For `player-growth-exposure`.** Its step 1 tests exposure share; on
  these numbers share is not the variable, the dose or the start is. Its
  close wakes the navigator (decisions "player-growth-exposure on-close:
  wake always"), and 49 is the next exploration slot's first charter.
- **For goal 2.** 0777-0778 (pns-two-turn) are released, by the rule in
  decisions "Probe pns-twin-official read": the content gain behind the
  all-content and pack nets goes past the first tick, which two-turn
  search plays; whether depth also finds the rest is what 0778 measures.

## pns-gen-attribution, twin (0779): the recipe, not the pack, loses the generated bench

Job 0779 (pin 2af5b30): the all-content twin (`allcontent40k-s1` r1 @tsl1,
the pack net's config minus its packs) one turn deep on 0762's eight
generated-bench rows, 675 elite starts x 16 seeds,
`results/mutate/gen-allc40k-s1-tsl1.json`, against the 10-29 net @tsl1
(`results/mutate/gen-enemies-b1.json`). `mutate_monsters.py compare`, win
rate (base cost = the 10-29 net's change from parent; gain = the twin's
change against it), beside pack net seed 1 (0762):

| row | 10-29 cost | twin gain | pack net s1 gain |
|---|---|---|---|
| AttackLoss-Damage | -0.083 (0.007) | -0.029 (0.006) | -0.053 |
| OppCard-Weak | +0.052 (0.009) | -0.020 (0.009) | +0.045 |
| AttackLoss-Weak | -0.066 (0.007) | +0.042 (0.007) | +0.031 |
| OppCard-PlainDamage | -0.042 (0.006) | -0.043 (0.007) | -0.078 |
| OppCard-Damage | -0.053 (0.006) | -0.047 (0.007) | -0.086 |
| TurnStart-Weak | -0.011 (0.003) | -0.027 (0.005) | -0.011 |
| TurnEnd-Weak | -0.013 (0.003) | -0.021 (0.005) | -0.012 |
| OppCard-Vulnerable | +0.153 (0.012) | -0.267 (0.014) | -0.304 |

Parent change -0.005 (0.002). By the probe's rule the cause is the recipe
(40k games, one round, every card; the 10-29 net is 20k games, ten rounds,
the train half): the twin loses the OppCard-Vulnerable edge (-0.267 wins)
and the OppCard damage rows as the pack net does, with no pack. The pack
adds about half again on AttackLoss-Damage and the OppCard damage rows
(-0.025 to -0.039 wins beyond the twin) and gains OppCard-Weak back.
Official fighting outside Demon Form is level for the same twin
(pns-twin-matched), so the deficit sits on mechanics neither net trained
on: the one-round net transfers worse to new mechanics than the ten-round
one.

For `generated-pack-scratch` (47): its cut bar compares with pack net seed
1, the same recipe, so the generated pack's effect is read cleanly; its
second bar (held-out rows not worse than the 10-29 net) now has to recover
a recipe deficit as well. Decisions "pns-gen-attribution read: the recipe
loses the generated bench; 47's step 2 keeps it and gains a round-2 branch".

## pns-official (0774-0776): the pack nets' ruler gain is Demon Form; outside it they lose 2.1 HP

Jobs 0774-0776 (pin 2af5b30): pack nets `packnet40k` s1, s101, s201 r1
@hpb0.01 one turn deep on the ruler (`yardstick/headline-setting`, own
picks) against `yardstick/one-turn-controls`, sequences 0-499, fixed n 500
(`scripts/analysis/paired_go.py`; the split from the result files, read
2026-11-10 14:35, navigator b03f7647):

| read | end HP (se) | clears |
|---|---|---|
| s1 | +0.59 (1.05) | +0.038 |
| s101 | +0.15 (1.06) | -0.028 |
| s201 | +1.61 (1.06) | +0.024 |
| pooled (three seeds per sequence) | +0.78 (0.89) | +0.011 |

By the rule written before the read (pooled +1.5 HP at 2 se) this fails:
the pack recipe is no goal-2 fighter gain on the ruler, and no two-turn
official read follows. It repeats the twins' read (+0.76 (0.87),
pns-twin-official) on three more nets.

Split by Demon Form in the deck (the pack nets pick it 0.60-0.62 of the
times offered, the control 0.19):

| sequences | s1 | s101 | s201 |
|---|---|---|---|
| both took it (39-41) | +17.67 (3.83), clears +0.436 | +20.15 (3.04), +0.390 | +19.98 (4.03), +0.439 |
| only the pack net (101-102) | +4.60 (2.57), +0.118 | +3.33 (2.53), +0.079 | +2.70 (2.54), +0.088 |
| neither (356-357) | -2.56 (1.14), -0.028 | -3.03 (1.18), -0.106 | -0.80 (1.16), -0.042 |

On the 345 sequences where no player took Demon Form, pooled: -2.14
(0.97) HP, beside the twins' -1.50 (1.00). Deaths by floor (index 8 the
second elite, 10 the boss), control / s1 / s101 / s201: floor 8 31 / 38 /
45 / 45, boss 107 / 78 / 91 / 82, floor 7 0 / 6 / 7 / 3.

What it says:
- **Goal 2.** Five one-round from-scratch 40k nets (two twins, three pack
  nets) now read the same on the ruler: the gain is Demon Form, which two
  turns deep the product already plays (`cause/unseen-cards-half-edge`),
  and outside it they lose 1.5-2.1 HP with deaths moving from the boss to
  the second elite. On the control's own decks the twins fight level
  outside Demon Form (pns-twin-matched, +0.05 (0.56)), so that loss is the
  picks: the sim chooser's trial fights use the playing net's values, and
  a one-round net's picks build weaker decks for the second elite. The
  pack adds -0.64 HP to it (dilution, as on cells). Nothing for goal 2
  before Act 1 (`decision/headline-pool-after-act1`); `all-content-r2`
  (a second round) stays checked and not proposed until the pool widens.
- **Goal 1.** Unchanged: the pack nets carry the 31 pack cards on the
  pack headline (+3.33 HP, `measurement/pack-net-scratch@three-seeds`);
  their official cost is picks, not fighting.
- **For 49** (`from-scratch-later-ticks`): its reads are on fixed-deck
  cells, where picks play no part, so this loss does not touch them.

## pns-two-turn (0777-0778): the pack net's gain grows two turns deep

Jobs 0777 (the product, the 10-29 net two turns deep with line-seed and
step-line, on the 31-card pack) and 0778 (pack net seed 1,
`runs/2026-11-10-packnet40k-s1-r1-64badf9` @hpe0.01, the same flags),
sequences 0-249, the headline setting with `--pack
content/packs/act1-ironclad.json` (pack hash dbec2dc1, pin 2af5b30, the
pre-C6 pack all four files below share). Seed 1 was named before seeds
101 and 201 were read. Paired end-HP (`gauntlet_protocol.end_hp`), se
over sequences:

| depth | pack net s1 minus 10-29 net | clears | files |
|---|---|---|---|
| two turns (0778 vs 0777) | +4.67 (1.40) HP | +0.080 (0.033); 0.716 vs 0.636 | `packnet40k-s1-hpe0.01-two-line-step-starter-simboss-pack-act1.json` vs `pns-net1029-hpe0.01-two-line-step-starter-simboss-pack-act1-31.json` |
| one turn, same 250 sequences (0752 vs 0751) | +2.80 (1.37) HP | +0.088; 0.592 vs 0.504 | `packnet40k-s1-hpb0.01-starter-simboss-pack-act1.json` vs `pns-net1029-hpb0.01-starter-simboss-pack-act1-31.json` |

Ratio two-turn / one-turn 1.67 (se 0.86 by the delta method; the two
differences correlate 0.22 per sequence). By halves: train +5.26 (1.92)
against +2.66 (1.84); held-out +4.08 (2.05) against +2.94 (2.04). The
protocol passed at n 250.

By the probe's rule (ratio >= 0.6 with the two-turn gain 2 se above
zero) this is the "content gains survive depth" branch. A cleaner test
of the same question: `cause/leaf-gain-third` predicts at most 0.46 x
the one-turn gain on all 500 sequences (+3.25, `measurement/pack-net-scratch@seed1`),
about +1.5 HP two turns deep; the read is +4.67 (1.40), 2.3 se above
that. One seed, so a lead: seeds 101 and 201 are queued (0819, 0820).

Where it comes from:
- **The bosses.** Deaths at the boss floor 60 to 37 (Hexaghost 31 to 21,
  the Guardian 21 to 12, Slime Boss 8 to 4); on the 196 sequences both
  players reach the boss, HP lost there 34.3 against 38.3, at the elites
  31.9 against 32.5, hallways level. Deaths before the boss 23 against
  25 (Gremlin Nob 7 against 5, Exordium Thugs 5 against 2). The leaf
  rule's corollary ("a one-turn gain that sits at the bosses predicts no
  clears two turns deep", from the SharpHide burst) does not hold here.
- **Not only Demon Form.** On this pack Demon Form picks are 0.18 against
  0.06 (offers are diluted by 31 pack cards; on the ruler 0.60-0.62
  against 0.19). Sequences where only the pack net took it (30) +11.6
  HP, clears +0.20; where neither did (205) +3.10 (1.48) HP two turns
  deep against +1.79 (1.47) one turn deep. Cards the pack net took and
  the product did not, with the largest mean gains, are setup and
  multi-turn cards (Combust +13.0 on 20, Power Through +11.0, Shrug It
  Off +10.3, Flame Barrier +8.2): attribution by pick is confounded with
  the deck, so these are pointers only.

Reading. A gain whose payoff sits past both search horizons (powers that
pay over later turns, which the net learned from 40k games with them in
the pool, `measurement/pack-net-twin@one-turn`'s twin-tsl1 part) is not
something the second turn of search finds, so depth cannot take it; and
a leaf that values the setup right gives the two-turn search lines worth
choosing, so the gain can grow. This is `cause/leaf-gain-third`'s exit.
The SharpHide-type bursts the rule came from learned an in-fight threat
the second turn sees.

Beside it, the level with real content: the product on the 31-card pack
is 0.636 clears on sequences 0-249 against 0.836 on the curated
setting, -8.56 (1.50) HP (0777 against `yardstick/headline-control`,
`--vary pack`; 0.684 with the earlier 27-card pack on 0-499,
`measurement/act1-cards@pack-offers`). The pack net takes back 0.080
of that 0.200.

What it changes: the pack-capable (all-content) recipe is the product's
fighter candidate once the headline pool widens
(`decision/headline-pool-after-act1`), as the probe's rule said; a
two-turn read on the curated ruler is still not earned (one turn deep
there the pack nets are +0.78 (0.89) and the loss outside Demon Form is
picks). Goal 1: a gain from training on new content that pays past the
horizon carries to product depth at least whole on this read, so goal
1's one-turn reads of such content do not overstate the product's gain.

## pns-two-turn-seeds (0819-0820): the gain carries whole two turns deep on three seeds

Jobs 0819 (pack net seed 101, `runs/2026-11-10-packnet40k-s101-r1-0559253`)
and 0820 (seed 201, `runs/2026-11-10-packnet40k-s201-r1-91c8ae0`), each
@hpe0.01 `--two-turn --line-seed --step-line`, sequences 0-249, the
headline setting with the same 31-card pack (dbec2dc1, pin 2af5b30) and
against 0777's file, as seed 1 (0778). One turn deep each seed reads
against `pns-net1029-hpb0.01-starter-simboss-pack-act1-31.json` on the
same 250 sequences. Paired end-HP (`gauntlet_protocol.end_hp`), se over
sequences; ratio se by the delta method with the per-sequence covariance.

| seed | two turns | one turn | ratio | clears two / one |
|---|---|---|---|---|
| 1 (0778, 0752) | +4.67 (1.40) | +2.80 (1.37) | 1.67 (0.86) | +0.080 / +0.088 |
| 101 (0819, 0767) | +4.42 (1.42) | +2.82 (1.46) | 1.57 (0.83) | +0.096 / +0.048 |
| 201 (0820, 0766) | +4.62 (1.49) | +4.53 (1.50) | 1.02 (0.39) | +0.116 / +0.056 |
| pooled 1/101/201 | +4.57 (1.19; seeds 0.08) | +3.38 (1.21; seeds 0.58) | 1.35 (0.50) | +0.097 (0.030) / +0.064 |
| pooled 101/201 | +4.52 (1.25) | +3.67 (1.30) | 1.23 (0.46) | +0.106 (0.032) |

The probe's rule: go. The pooled ratio is 1.35 against the 0.6 bar, the
pooled two-turn gain 3.8 se above zero on the larger se (sequences; the
seeds agree to 0.08 HP because all three pair against one control file),
and seeds 101 and 201 alone pool to 1.23, far from the 0.46 fail line.
Clears: control 0.636, seeds 0.716 / 0.732 / 0.752.

Where it sits, deaths by floor kind on the 250 sequences:

| player | hallway | elite | boss |
|---|---|---|---|
| product, two turns | 13 | 18 | 60 |
| pack nets s1 / s101 / s201, two turns | 17 / 6 / 9 | 17 / 18 / 8 | 37 / 43 / 45 |
| 10-29 net, one turn | 15 | 40 | 69 |
| pack nets, one turn | 12 / 20 / 19 | 35 / 39 / 31 | 55 / 53 / 60 |

The bosses again: 60 boss deaths to a mean of 41.7 two turns deep (-18),
69 to 56 one turn deep (-13). By half, two / one turn: seed 101 train
+7.14 / +5.34, held-out +1.70 / +0.30; seed 201 train +4.06 / +4.58,
held-out +5.17 / +4.49. Demon Form picks 0.16-0.18 of offers for each
seed against the product's 0.06, as seed 1.

Reading. A gain from training on content whose payoff lands past both
search horizons carries to the two-turn product whole (1.35 (0.50), not
the 0.2-0.46 the in-fight-threat bursts showed); whether it grows past
1 is not shown (the pooled ratio is 0.7 se above 1). This re-sets
`cause/leaf-gain-third`: its one-third discount covers gains on
threats the second turn sees, and a one-turn read of past-horizon
content stands for product depth. The pack-capable all-content recipe
gains +4.57 HP and +0.097 clears at product depth on a pool of real
Act 1 cards, on three seeds: the strongest evidence yet for the owner's
plan of retraining the product's net on the widened pool after Act 1
(`decision/headline-pool-after-act1`).

## twin-two-turn-matched (0846): the twin fighter gains two turns deep outside Demon Form; between, extended to 500

Job 0846: the all-content twin seed 1 (`runs/2026-11-08-allcontent40k-s1-r1-887ca04`)
@hpe0.01 `--two-turn --line-seed --step-line` on the headline setting,
on the headline control's decks (`--match`), sequences 0-249, pin
2af5b30, against `yardstick/headline-control`. Paired end-HP
(`gauntlet_protocol.end_hp`), se over sequences. One turn deep the same
sequences come from 0791's matched file against the one-turn control
(`yardstick/one-turn-controls`); the decks there are the one-turn
control's picks, so the two depths share sequences, not decks.

| set | two turns deep | one turn deep |
|---|---|---|
| all 250 | +1.53 (0.64) HP, clears +0.024 (0.020) | +1.08 (0.94), clears -0.008 |
| the control's Demon Form decks | +4.38 (1.65), n 21 | +11.40 (2.34), n 25 |
| neither control took Demon Form | +1.38 (0.69), n 221 | -0.10 (1.00), n 221 |
| train / held-out half | +1.30 (0.79) / +1.24 (1.16) outside Demon Form | |

Deaths by floor kind on the 250 sequences (hallway / elite / boss):
product 2 / 6 / 33, twin two turns deep 5 / 2 / 28; one turn deep the
control 8 / 18 / 52, the twin 12 / 18 / 50. Clears two turns deep 0.860
against 0.836. Boss deaths by encounter, twin / product: the Guardian 14
/ 17, Hexaghost 12 / 14, Slime Boss 2 / 2.

The probe's rule: between. End-HP +1.53 clears the +1.2 go bar, clears
are above -0.01, but boss deaths fall by 5, short of the 8 a go needs and
above the stop line of 4. So the file extends to 500 on this seed only
(job 0854, same pin, same command at `--sequences 500 --min-n 500`).

Reading, a lead on one seed and 250 sequences:
- **Demon Form decks keep about 0.38 (0.17) of their one-turn gain.** The
  product's second turn plays Demon Form's first tick
  (`cause/unseen-cards-half-edge`), so part of what the twin learned about
  the card is inside the product's horizon; the third to a half that
  `cause/leaf-gain-third` gives in-horizon gains fits. Not yet the rule's
  exit (a past-horizon gain under 0.6x): 1.3 se below 0.6, with 21
  decks.
- **Outside Demon Form the gain appears only with depth**: level one turn
  deep (-0.10 (1.00)) and +1.38 (0.69) two turns deep, about 1.2 se apart
  (the decks differ between the depths, so the difference is not
  paired). The second turn removes the twin's one-turn elite and hallway
  deaths and its boss edge stays (boss deaths 29 to 26 there). No fact
  on file predicts this: `cause/leaf-gain-third` covers gains that shrink
  or carry; this one grows, as the base net's edge over the heuristic
  leaf grows with depth (open question 13). If it holds at 500, a
  one-turn screen can miss a fighter's product gain when that fighter's
  one-turn losses are tactical.
- For goal 2: +1.5 HP and +0.02 clears is the size `decision/crossed-player-lead`
  called a fighter swap for about +1 HP and no clears; here clears move
  the right way and boss deaths fall, which is that decision's condition
  for a promotion read, not yet at the probe's bar.

## twin-two-turn-matched at 500 (0854): between; the fighter is worth about 1 HP outside Demon Form

Job 0854 extends 0846's file to sequences 0-499 on the same snapshot
(pin 2af5b30, same command at `--sequences 500 --min-n 500`): the
all-content twin seed 1 @hpe0.01 `--two-turn --line-seed --step-line` on
the headline control's decks (`--match`), against
`yardstick/headline-control`. Paired end-HP (`gauntlet_protocol.end_hp`),
se over sequences; record `jobs/done/0854-gauntlet.json`. The protocol
(H1 +1.5) passes at n 500; the probe's own rule decides.

| set | end-HP | clears |
|---|---|---|
| all 500 | +1.41 (0.45) | +0.014 (0.015), 0.848 against 0.834 |
| sequences 0-249 / 250-499 | +1.53 (0.64) / +1.28 (0.64) | |
| the product's Demon Form decks (39, all held-out) | +6.46 (1.41) | +0.10 (0.05) |
| the other 461 | +0.98 (0.47) | about +0.01 |
| of those: train 250 / held-out 211 | +0.83 (0.60) / +1.16 (0.74) | +0.02 / -0.00 |

Deaths by floor (index 0-10; the elites sit at 5 and 8, the boss at 10),
twin / product: floor 5 0 / 2, floor 7 1 / 0, floor 8 8 / 13, floor 9 13
/ 6, boss 54 / 62. Boss deaths paired: 20 sequences the twin alone lost
at the boss, 28 the product alone (z 1.15). By boss: Hexaghost 23 / 29,
the Guardian 26 / 28, Slime Boss 5 / 5. On the Demon Form decks deaths 3
/ 7, on the others 73 / 76.

The probe's rule (decisions "twin-two-turn-matched read: between;
extended to 500 on seed 1"): **between**. End-HP clears the +1.0 go bar
and clears are above -0.01, but boss deaths fall by 8 against the 10 a go
needs (and above the stop line of 6). No second seed; the twin stays a
lead.

Reading:
- **Outside Demon Form the twin is a +1 HP fighter with level clears**,
  the second independent net to land there two turns deep: the
  SharpHide-then-stage-B burst net gained +1.08 (0.47) HP and no clears
  on the same decks (`measurement/crossed-player@two-turn`). Two
  different recipes, one fine-tuned and one from scratch, both buy about
  1 HP at the product's depth and no runs. The 250-sequence +1.38 there
  shrank to +0.98 at 500, as a between result should.
- **The deaths move, they don't go**: the twin survives the second elite
  more often (floor 8: 8 against 13) and loses more of those runs on the
  next hallway (floor 9: 13 against 6), so the elite saves arrive with too
  little HP to reach the boss. Boss deaths fall by 8, 1.2 se.
- **Demon Form decks carry 70% of the total**: +6.46 (1.41) HP on 39
  decks. Its one-turn gain on these same decks comes from 0857 (the 10-29
  net) against 0855 (the twin) in twin-depth-paired; 0846's 0.38 ratio was
  against another control's decks.
- For goal 2 the result agrees with `decision/crossed-player-lead`: a
  fighter swap on the curated ruler is worth about +1 HP and no clears,
  and the product's clears sit at the boss, where the deck moves wins two
  to three times as far as the second turn (`measurement/depth-by-boss@replay`).
  The all-content recipe's product use stays with the widened pool after
  Act 1 (`decision/headline-pool-after-act1`).

## twin-depth-paired (0855-0857 with 0854): stop at 1.8 se; Demon Form splits by tick as predicted

Jobs 0855 (twin seed 1), 0856 (twin seed 101) and 0857 (the 10-29 net),
each @hpb0.01 one turn deep on the headline setting on the headline
control's decks (`--match`), sequences 0-499, pin 2af5b30; read with
0854's two-turn file. The five files take the same cards on every floor
before a death (checked). Paired end-HP, se over sequences.

| set | two turns (twin s1 - product) | one turn (twin s1 - 10-29) | growth (paired) | one turn, twin s101 |
|---|---|---|---|---|
| outside Demon Form (461) | +0.98 (0.47) | -0.40 (0.62) | +1.38 (0.76) | -0.92 (0.60) |
| of those train 250 / held-out 211 | | -0.30 / -0.51 | +1.13 (0.94) / +1.67 (1.24) | |
| Demon Form decks (39) | +6.46 (1.41) | +11.49 (2.50) | -5.03 (2.76) | +8.31 (2.76) |
| all 500 | +1.41 (0.45) | +0.53 (0.62) | +0.88 (0.74) | -0.20 (0.61) |

One-turn clears: twin s1 0.710, s101 0.686, the 10-29 net 0.698.
Deaths outside Demon Form at the second elite (floor 8) / the hallway
after it / the boss: one turn deep twin s1 33 / 16 / 80, s101 41 / 19 /
75, the 10-29 net 26 / 14 / 80; two turns deep twin 8 / 12 / 52, product
13 / 6 / 56.

The probe's rule (decisions "Probe twin-depth-paired queued"): **stop**.
The growth outside Demon Form is +1.38, over the +1.0 size, but 1.8 se,
short of 2 se. One-turn screens stand.

Reading:
- **A lead that a fighter's gain grows with depth**, with a mechanism in
  the deaths: one turn deep both twin seeds lose more runs at the second
  elite than the 10-29 net (33 and 41 against 26), and two turns deep the
  twin loses fewer there than the product (8 against 13). The second turn
  repairs the twin's elite errors and its boss edge stays. Both seeds are
  level or below one turn deep (-0.40, -0.92), so the one-turn side is not
  one seed's luck.
- **The Demon Form decks split by tick as `cause/leaf-gain-third`
  predicts.** Two turns deep they keep 0.56 of the one-turn gain (about
  0.17 se, unpaired errors). The twins' one-turn Demon Form gain past the
  first tick was +3.30 (0.95) on the cells (twin-tsl1); taking that part as
  carrying whole and the remaining +8.2 (the first tick, inside the
  product's second turn) at a third predicts about +6.0 two turns deep,
  against +6.46 (1.41) measured. So the 0.56 is not the past-horizon exit
  (a past-horizon gain under 0.6x): it is the mix of the two kinds.
- For goal 2 nothing changes: the twin's two-turn gain is measured
  directly (0854), and any net headed for the product is read two turns
  deep anyway. The lead matters for screening fighters one turn deep: a
  fighter whose one-turn losses are elite deaths may be underrated by
  about 1 HP.
