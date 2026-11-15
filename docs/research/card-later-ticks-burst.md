# card-later-ticks-burst

Lane charter: `lane/card-later-ticks-burst`. Steps 1 and 2 run as one
family, `configs/families/clb-step1.json`.

## Plan (2026-11-11)

**How it moves goal 1, and how we'll know.** Goal 1's number is how few
games a net needs to adapt to new content. Two card variants still cost the
10-29 net at the turn-start leaf (`measurement/mutated-cards@stage-a`:
inflame-turn1 -0.018 (0.005), metal-c2-a5 -0.021 (0.006) wins), and
400-game bursts closed neither (`measurement/cards-adapted@stage-a`). A
5000-game-per-group burst taught Demon Form's later ticks where 1.6k did
not (`measurement/later-ticks-count@burst5k`). If the same dose closes
half of a card variant's cost, the dose for a recurring-value card is
known on the owner's card yardstick; if not, the later-ticks result is
specific to held-out decks and the card column needs something other than
more games. The adapted read (`mutate_cards.py adapted` against
`results/mutate/cards-a.json`) decides it by the charter's stop rule.

**Recipe (on the owner's behalf).** The fslt-step3 burst (`source`
one-turn, held-out decks) can't hold a pack variant, so the bursts are the
400-game configs (`configs/cadapt-*`: the variant in every deck, games
played by the parent net, same game and training seeds) with `games` 5000
per group: `configs/clb-<modifier>-s<1..3>.json`. Alternatives: build a
pack option into `two_turn_games` decks (code, and a teacher change at the
same time as the dose change), or match fslt's count of games with the new
card (about 3.5k, so about 1200 per group). Kept the 400-game recipe so
the only change from 0409-0421 is the dose; 5000 per group is about 15k
games with the variant, four times fslt's, so a fail here is a fail of
dose, not of too few games.

Per burst net: the mutated-cards book (200 starts x 16 seeds, plain leaf
and @tsl1, as 0410), and the one-turn cell gauntlet's two books @tsl1
against `results/gauntlet/net1029-hpb0.01-tsl1*.json` (guards; the 5k
Demon Form bursts cost other held-out clears -0.033 (0.012)). The family
table's rule (held-out stratum at 2 se, train within -0.9 HP and -0.04
clears) is only a guard line; the verdict is the adapted read.

Cost: 6 bursts at 4 threads, about 25 min each, and 18 reads at 3
threads, about 8 min each: about 17 thread-hours against the 24 cap.

Clean-up: burst runs under `runs/` and datasets/caches under `cache/`
follow the usual registry rules (caches rebuildable); result files are
kept.

## Step 2 read: fail (2026-11-11)

Verdict read `jobs/done/0884-mutate-cards.json` (log
`logs/jobs/0884-mutate-cards.log`), guard table `jobs/done/0883-family.json`
(`results/families/clb-step1.md`). Gain = the three 5k bursts pooled per
start minus the zero-shot 10-29 net, paired by start, wins (se) / HP lost.

| modifier | leaf | variant gain (all fights) | zero-shot cost | go bar | boss variant gain |
|---|---|---|---|---|---|
| inflame-turn1 | one turn | +0.029 (0.007) / -1.89 HP | -0.043 | | +0.075 (0.017) |
| inflame-turn1 | @tsl1 | **+0.001 (0.004)** / +0.37 HP | -0.018 | +0.009 | +0.013 (0.010) |
| metal-c2-a5 | one turn | -0.002 (0.006) / +0.64 HP | -0.021 | | +0.024 (0.012) |
| metal-c2-a5 | @tsl1 | **+0.003 (0.004)** / -0.03 HP | -0.021 | +0.0105 | +0.020 (0.010) / -1.47 HP |

Neither @tsl1 gain reaches 2 se: **fail** by the stop rule. Retention also
misses for inflame: parent copy per elite fight +1.13 (0.24) HP lost @tsl1,
+0.97 (0.27) one turn, against the 400-game bursts' +0.76; metal's +1.03 /
+1.61 is inside its +1.79. Guards (0883): every arm loses clears, held-out
inflame -0.029, metal -0.021, train metal -0.031 (the table's own rule: fail).

**Why.** The dose is not the lever here. Against the 400-game bursts
(`measurement/cards-adapted@stage-a`) twelve times the games change almost
nothing: inflame one turn +0.029 against +0.024, @tsl1 +0.001 against
+0.001; metal @tsl1 +0.003 against +0.002. The bursts do teach the net
inflame-turn1's value (one turn, at the bosses +0.075 of a -0.108 cost), so
the data reaches the net; what the turn-start leaf player still loses on
these variants is not the net's value of the card. Its zero-shot cost is
already smaller than the one-turn player's (-0.018 against -0.043), which
fits the leaf pricing the first tick by itself and leaving a remainder the
value net doesn't fix. The only @tsl1 lead is at the bosses (metal +0.020
(0.010) wins, -1.47 (0.41) HP; inflame +0.013 (0.010)), as the 400-game
bursts had it: about 2 se on 51 starts, a lead, not a result. Demon Form's
later ticks (`measurement/later-ticks-count@burst5k`) were learned on
held-out decks from the two-turn data; on the mutated-cards book the same
dose does not carry over, so the card column needs something other than
more games (a guess, not tested: what the @tsl1 player misses on a variant is its line choice,
not its leaf value).

Note: val MSE rose after epoch 1 in each burst (0859: 0.156 to 0.173), so
the burst's later epochs fit the variant decks at the cost of the rest,
which may explain the clear losses on the guards (not tested).

Cost: 3.7 thread-hours for bursts and reads (table 0883), lane total
5.3 CPU-h of the 24 cap.
