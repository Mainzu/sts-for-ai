# Leaf numbers probe: read (lane leaf-blind-numbers)

Spec: `docs/specs/leaf-blind-numbers.md`. Charter: fact `lane/leaf-blind-numbers`.

## Read (2026-11-07, job 0434)

Job `jobs/done/0434-leaf-numbers-probe.json`, output
`results/leaf_numbers/probe.json`, log `logs/jobs/0434-leaf-numbers-probe.log`.
The 10-29 net @hpb0.01, plain leaf, the pack read's 167 tight2 held-out elite
and boss cells x 3 fights = 501 fights per set; 2389-3132 leaves per set. HP =
score x 100; se over fights (a fight's mean over its leaves is one unit). Ran
4 minutes against a 20-minute estimate: the fights are one-turn net play with
recording, 50 s a set in the log, so the speed is plausible.

### Step 1: leaf forms

| set | monster_rolls | draw | block at monster_rolls | Str<0 | Weak>0 |
|---|---|---|---|---|---|
| without | 0.30 | 0.56 | 1.02 (0.14) | 0.00 | 0.07 |
| Disarm | 0.27 | 0.58 | 0.99 (0.13) | 0.27 | 0.09 |
| Impervious | 0.31 | 0.59 | 3.47 (0.21) | 0.00 | 0.07 |
| Intimidate | 0.27 | 0.60 | 1.04 (0.14) | 0.00 | 0.20 |

Predictions: forms right (draw outnumbers monster_rolls, which is 27-31%).
Impervious block wrong: 3.5 mean, not over 10; the monsters' turn eats most
of the 30 block before the leaf, and many Impervious turns end at a draw leaf
(block 0).

### Step 2: prices

| set | block0 | block+10 | block+20 | block+30 | str-2 net / worth | weak+1 net / worth |
|---|---|---|---|---|---|---|
| without | -0.06 (0.09) | -2.61 (0.38) | -5.92 (0.63) | -5.34 (0.84) | +4.92 / +9.89 | +6.02 / +2.67 |
| Disarm | +0.05 (0.17) | -3.14 (0.46) | -6.00 (0.68) | -5.03 (0.81) | +4.92 / +12.51 | +5.97 / +2.50 |
| Impervious | +0.92 (0.20) | +0.97 (0.23) | +0.91 (0.36) | +1.52 (0.44) | +3.24 / +13.07 | +4.20 / +2.45 |
| Intimidate | +0.03 (0.18) | -2.94 (0.47) | -5.51 (0.65) | -4.39 (0.78) | +4.46 / +9.81 | +4.95 / +2.19 |

(block0 is the price of the block actually present: value with it minus
value without it. Heuristic changes: 0 for every block perturbation; str-2
+4.2 to +7.5; weak+1 +10 to +19.)

- **Leftover block is mispriced, the wrong way, where it matters most.** On
  three sets the net pays -0.26 to -0.30 HP per point of worthless leftover
  block up to 20, about -6 HP for 20 (wrong sign, 9 se from 0). The block
  actually present on played lines is small (about 1), so block0 is near 0:
  the bias acts on the lines search compares and rejects, a line that blocks
  more than the monsters hit is marked down. On the Impervious set the sign
  flips: the net pays about +1 HP for the leftover block present and for any
  added block, a bias toward the lines that keep surplus block. A sign that
  depends on the deck says the net reads leftover block as a cue for
  something else (what the deck or the turn looks like), not as a quantity.
  Prediction (about +2 HP for 20 block) wrong in sign on three sets.
- **Strength -2 is priced at about half its upper-side worth** (+4.9 against
  +9.9 to +12.5; flagged on Disarm and Impervious). The worth is an upper
  estimate (block can absorb hits) and the heuristic prices it at the same
  +4-7, so the net's price is not clearly wrong. Identical +4.92 for without
  and Disarm: the net does not price Strength differently on the deck that
  makes it.
- **Weak +1 is overpriced about twice** (+4.2 to +6.0 against +2.2 to
  +2.7; flagged only on Disarm by 2 se); the heuristic overprices it five
  times. Overpricing Weak would make the net play Intimidate more often, not
  lose by it: Intimidate costs 0, so the overprice likely costs only the
  turns where it displaces a better play.

### What it changes

- The stop rule's fail-fast does not apply: not every number is priced
  right, and one mispriced number has an exact search-side fix. At a
  `monster_rolls` leaf the next `StartTurn` sets block to 0 and resets
  energy whenever no block-keeping effect is in play, so the search can clear
  both at the leaf without changing the leaf's true value. Step 3 tests that
  fix (a search option off by default).
- Strength and Weak have no exact search-side fix (a correction would be a
  hand-made price, not the game's rule); they go to all-content-net as
  evidence: the net prices -2 Strength the same on the deck that makes it as
  on one that never does, and Weak about twice its one-turn worth.
- Expected outcome of step 3 against the stop rule: the go needs two of the
  three cards' lead within 2 se of zero, and only Impervious's cost can come
  from leftover block; Disarm's and Intimidate's numbers are Strength and
  Weak. A go is unlikely (about one in five). The fix is still worth its
  small cost because it changes every deck's leaves: the -0.3 HP per block
  point acts on every line that blocks more than it needs, so the retention
  read (cell gauntlet) can show a general gain or loss, and a pass there
  reaches the headline.

## Step 3 read: leaf_clear_block (2026-11-07, jobs 0451-0453)

Spec `docs/specs/leaf-clear-block.md`. Jobs `jobs/done/0451-pack-cards-read.json`,
`0452-pack-cards-read.json` (table `results/pack_cards/act1-lcb/table.json`),
`0453-gauntlet.json` (`results/gauntlet/net1029-hpb0.01-lcb1.json`). The 10-29
net @hpb0.01 with `@lcb1`, against the same fights without it
(`results/pack_cards/act1/table.json`) and the one-turn cell control
(`results/gauntlet/net1029-hpb0.01.json`). The pack read ran in 2.5 minutes
against a 12-minute estimate; the log's per-set times (87 s for 2,004 net
fights, 34 s for the 900 @tsl1 fights, which play only turn-start decks in
both runs) are the usual pace, so the estimate was loose, not the run short.

Each card's lead (card minus without, se over 167 cells):

| card | wins plain before / lcb | wins tsl1 before / lcb | HP tsl1 before / lcb |
|---|---|---|---|
| Disarm | -0.100 (0.034) / -0.110 (0.033) | -0.118 (0.032) / -0.130 (0.032) | -2.16 (0.48) / -2.26 (0.47) |
| Impervious | -0.094 (0.034) / -0.084 (0.035) | -0.122 (0.034) / -0.120 (0.035) | -1.58 (0.63) / -1.56 (0.61) |
| Intimidate | -0.054 (0.030) / -0.062 (0.029) | -0.062 (0.029) / -0.072 (0.028) | -1.08 (0.40) / -1.19 (0.39) |

Cell gauntlet, n 500 fixed: clears 0.636 against 0.634 (+0.002, se 0.003),
paired end HP +0.04 (0.07), protocol fail (no +1.5 HP gain; nothing lost
either); train and held-out alike (+0.000 and +0.004 clears), deaths by
encounter the same within one fight.

- **Checkpoint lcb-read failed.** No card's lead comes within 2 se of zero
  (closest: Intimidate -0.072 against 2 se of 0.056); all three move by
  under a third of an se. The cell gauntlet is level, so the option is
  harmless and useless at once.
- **Why so small: the option rarely changes a decision.** Fight by fight,
  `@lcb1` changes the result of 10 of 501 fights on decks without the
  three cards, 10 Disarm, 13 Intimidate and 24 Impervious (@tsl1: 4-12 of
  225); on the gauntlet 73 of 500 sequences change anywhere, with a net
  sum of zero. The step-2 markdown of about -0.3 HP per point of surplus
  block is real on the leaves, but the lines it marks down are mostly
  ones the search rejects anyway (more block usually means less damage
  dealt, priced right), and the leftover block on played lines is about 1
  point. Impervious, the one card whose cost could come from leftover
  block, moves most (24 fights changed, plain +0.010 wins) and still sits
  at -0.12 @tsl1: its 30 block is eaten by the monsters' turn before the
  leaf (3.5 mean at `monster_rolls`, step 1), so the leaf number was never
  where its cost lives.
- **What it changes.** The three cards' cost is not a leaf-number artefact
  the search can clear: Disarm's is Strength below zero priced the same
  as on decks that never make it, Intimidate's Weak is overpriced about
  twice, and Impervious's is play, not the leaf (its block is gone by the
  leaf). Those are content the net has not learned, the evidence for
  `all-content-net`. The stop rule's fail branch applies; the lane is done.
