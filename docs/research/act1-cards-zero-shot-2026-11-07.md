# Act 1 cards zero-shot (lane act1-cards-zero-shot)

Spec: `docs/specs/act1-cards-zero-shot.md`. Script:
`scripts/analysis/pack_cards_read.py`. Files: `results/pack_cards/act1/`.

## Predictions (written 2026-11-07, before any fight)

The read: tight2 held-out elite and boss cells (167: 126 elite, 41 boss),
three fights each, three copies of the card in place of three Strikes (then
Defends), paired by cell with the same fights without it. Per card: (10-29
net @hpb0.01 minus the heuristic) with the card minus the same without it,
in wins and end HP, se over cells; the plain leaf and `@tsl1`.

| class | cards | prediction | why |
|---|---|---|---|
| in-turn | Disarm, Ghostly Armor, Intimidate, Searing Blow, Seeing Red, Shockwave, Bludgeon, Feed, Impervious, Offering | level | the search plays the card in the engine and the net reads the state after (nine of ten unseen official cards, `cause/unseen-cards-half-edge`) |
| turn-start | Berserk | costs on the plain leaf; open under `@tsl1` | its energy lands at the next turn start, after the plain leaf; under `@tsl1` the tick is in the leaf state |
| status later | Power Through, Reckless Charge, Immolate | open | they pay now and charge later through a status card in a pile; the net may overplay them |
| unreadable trigger | Double Tap, Flame Barrier | open | built on triggers the net cannot read (`OwnerPlaysCard`, `OwnerAttacked`), though their effects land before the leaf |
| new atoms (C1) | True Grit, Burning Pact, Second Wind, Sever Soul, Fiend Fire, Exhume | level | new pick kinds, `ScaledBlock`, `HandCards` the net drops, but the effects land inside the turn |

Mismatch with the charter: it counts eleven in-turn cards; its five classes
cover the 22 pack cards with ten (10 + 1 + 3 + 2 + 6 = 22). The table above
follows the pack.

Smoke (6 cells, one fight, not a read): the heuristic plays Berserk on 0.21
of the turns it holds it, Fiend Fire on 0.57. A card the heuristic rarely
plays reads mostly the net's choice against an idle card.

Choices made for the cap (3 cpu-h): three fights per cell (expected se
about 0.03 wins per card, under the charter's 0.04); `@tsl1` is played only
on decks holding a turn-start power (Demon Form, Brutality, Berserk; 75 of
167 cells, plus Berserk's own decks), since the flag leaves other decks
unchanged (46 of 46 fights equal; `test_tsl_same_on_plain_decks`).

## Read (2026-11-07, jobs 0428-0431)

Jobs: `jobs/done/0428-pack-cards-read.json` (heuristic, 5 min),
`0429` (10-29 net @hpb0.01, 15.5 min), `0430` (@tsl1 on turn-start decks,
10.5 min), `0431` (table); 3 threads each, about 1.6 cpu-h. Table:
`results/pack_cards/act1/table.json`. A second script computed each
player's own change with the card from the same files and reproduced the
table's lead column to the last digit.

Lead d = (net - heuristic) with three copies of the card minus the same
without, per cell, mean (se) over 167 cells; `*` costs at 2 se on `@tsl1`.
"heur d" and "net d" are each player's own change in wins with the card.

| card | prediction | heur plays | heur d wins | net d wins (tsl1) | lead wins plain | lead wins tsl1 | lead HP tsl1 | lead tsl1 elite | lead tsl1 boss |
|---|---|---|---|---|---|---|---|---|---|
| Disarm * | level | 0.66 | +0.020 | -0.098 | -0.100 (0.034) | -0.118 (0.032) | -2.16 (0.48) | -0.138 | -0.057 |
| Impervious * | level | 0.48 | +0.190 | +0.068 | -0.094 (0.034) | -0.122 (0.034) | -1.58 (0.63) | -0.151 | -0.033 |
| Intimidate * | level | 0.91 | +0.094 | +0.032 | -0.054 (0.030) | -0.062 (0.029) | -1.08 (0.40) | -0.048 | -0.106 |
| Seeing Red | level | 0.43 | +0.026 | -0.016 | -0.028 (0.032) | -0.042 (0.032) | -0.36 (0.47) | -0.079 | +0.073 |
| True Grit | level | 0.62 | +0.050 | +0.018 | -0.022 (0.029) | -0.032 (0.029) | -0.49 (0.40) | -0.026 | -0.049 |
| Immolate | open | 0.63 | +0.220 | +0.190 | -0.000 (0.030) | -0.030 (0.028) | +0.23 (0.43) | -0.026 | -0.041 |
| Second Wind | level | 0.59 | +0.088 | +0.058 | -0.006 (0.033) | -0.030 (0.032) | -0.77 (0.50) | -0.029 | -0.033 |
| Exhume | level | 0.48 | -0.140 | -0.168 | -0.020 (0.031) | -0.028 (0.031) | -0.57 (0.40) | -0.034 | -0.008 |
| Feed | level | 0.59 | +0.166 | +0.144 | -0.012 (0.029) | -0.022 (0.028) | +0.23 (0.52) | -0.048 | +0.057 |
| Bludgeon | level | 0.46 | +0.170 | +0.150 | +0.012 (0.029) | -0.020 (0.026) | +0.03 (0.43) | -0.048 | +0.065 |
| Power Through | open | 0.55 | +0.168 | +0.152 | +0.004 (0.029) | -0.016 (0.028) | -0.63 (0.47) | -0.005 | -0.049 |
| Offering | level | 0.51 | +0.052 | +0.044 | +0.024 (0.036) | -0.008 (0.034) | +0.32 (0.45) | -0.040 | +0.089 |
| Shockwave | level | 0.63 | +0.058 | +0.052 | +0.006 (0.031) | -0.006 (0.030) | -0.21 (0.42) | -0.045 | +0.114 |
| Flame Barrier | open | 0.48 | +0.088 | +0.086 | +0.002 (0.033) | -0.002 (0.031) | -0.32 (0.43) | +0.008 | -0.033 |
| Ghostly Armor | level | 0.69 | +0.142 | +0.144 | +0.024 (0.029) | +0.002 (0.027) | -0.10 (0.43) | -0.021 | +0.073 |
| Searing Blow | level | 0.30 | -0.044 | -0.036 | +0.020 (0.028) | +0.008 (0.028) | +0.21 (0.37) | +0.005 | +0.016 |
| Fiend Fire | level | 0.48 | +0.148 | +0.160 | +0.024 (0.032) | +0.012 (0.031) | +1.01 (0.48) | -0.019 | +0.106 |
| Burning Pact | level | 0.76 | -0.226 | -0.212 | +0.018 (0.030) | +0.014 (0.031) | +0.45 (0.45) | -0.011 | +0.089 |
| Double Tap | open | 0.62 | +0.048 | +0.066 | +0.028 (0.032) | +0.018 (0.031) | +0.70 (0.46) | -0.013 | +0.114 |
| Reckless Charge | open | 0.89 | +0.092 | +0.118 | +0.050 (0.031) | +0.026 (0.030) | +0.51 (0.45) | +0.011 | +0.073 |
| Sever Soul | level | 0.46 | +0.042 | +0.074 | +0.042 (0.032) | +0.032 (0.029) | +0.20 (0.42) | +0.011 | +0.098 |
| Berserk | costs plain; open tsl1 | 0.15 | -0.160 | -0.094 | +0.070 (0.032) | +0.066 (0.033) | +1.77 (0.56) | -0.019 | +0.325 |

Every card's se is at most 0.038 wins (the charter's bar is 0.04). Without
the card the heuristic wins 0.493, the net 0.513 plain and 0.561 with
`@tsl1` (the leaf's gain on the 75 Demon Form or Brutality cells).

**Against the predictions.**
- The record's own test ("shown wrong if a plain in-turn card costs at 2
  se") fails: three in-turn cards cost, Disarm (3.7 se on tsl1),
  Impervious (3.6 se) and Intimidate (2.1 se; HP 2.7 se). With 22 cards
  read at 2 se about one false hit is expected; Disarm and Impervious are
  well past that, Intimidate is the marginal one. The cost is in elite
  fights (Disarm -0.138, Impervious -0.151); boss cells are fewer (41) and
  read wider.
- Berserk does not cost on the plain leaf: the net leads the heuristic by
  more with it (+0.070, all of it in boss cells, +0.33). Both players
  lose wins with Berserk in place of Strikes; the heuristic loses more
  (-0.160 against -0.094) and plays it on only 15% of the turns it holds
  it. `@tsl1` changes nothing on Berserk's wins (net d -0.094 against
  -0.090 plain), so the turn-start tick is not what the net was missing:
  base Berserk gives 1 energy a turn for 2 Vulnerable on the player, a
  poor trade in these decks for both players.
- The open classes are level: status-later (Power Through, Reckless
  Charge, Immolate), unreadable triggers (Double Tap, Flame Barrier), and
  the six new-atom C1 cards, as the in-turn rule predicted for the last.
  Burning Pact and Exhume hurt both players about equally (-0.21 and
  -0.17 wins for the net), so they read level as a lead: a lead read says
  nothing about whether a card is worth having.

**Why the three cost (hypothesis, not read).** All three are exhaust
skills whose whole value sits in a number the net must read in the leaf
state, not in damage dealt: negative Strength on an enemy (Disarm, -2 for
the fight), Weak on every enemy (Intimidate), and 30 block (Impervious,
beyond what the training decks make). The net does worse with Disarm than
with the Strike it replaces (-0.098 wins) while the heuristic gains a
little; with Impervious it gains less than half what the heuristic gains
(+0.068 against +0.190). The likely cause is inputs outside the training
range: enemy Strength only rises in the training content, and block that
large is rare. Against it: Shockwave also applies Weak (and Vulnerable)
to its target and reads level, and Ghostly Armor (block 10) is level. A
cheap check reads the net's leaf value on states with and without these
numbers, with no fights.

**What it changes.** Goal 1's standing count on real content: 19 of 22
new cards played at no measured cost with no training (one turn deep,
`@tsl1`), and 3 in-turn cards that cost 0.06-0.12 wins. The in-turn rule
in `cause/unseen-cards-half-edge` ("a card whose effect lands inside the
turn has no zero-shot cost") holds for effects the net reads as damage or
cards played, not for every number in the state. The charter's two-turn
read of the three costing cards does not fit the cap: 2,004 fights (three
cards and `without`) at 7.2 two-turn fights per thread-minute
(`how/two-turn-games`) is about 4.6 cpu-h against the 1.4 left; it goes to
the navigator with the close.
