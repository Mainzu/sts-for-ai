# Pile prices: what the net thinks a card left in its piles is worth (2026-11-09)

From an `/approach` discussion with the owner. The owner's observation: on
Strength decks (Rupture above all) the net plays Pummel early and loses it
to the exhaust pile before its Strength is high. The question became
whether the net prices an exhausted card, and then any card in its piles,
correctly.

Player throughout: the 10-29 net one turn deep, `@hpb0.01` (the one-turn
control, `yardstick/one-turn-controls`), on the headline setting's file
`results/gauntlet/net1029-hpb0.01-starter-simboss.json`. "Played out" means
that same player plays the position to the end; 32 futures (RNG seeds
5000-5031 or 1000-1031) per version, paired across versions. HP change
is (value with the change) minus (value without it); the score is
2 - HP lost / 100 on a win and 0 on a loss, so 0.01 = 1 HP. Data and
scripts: `results/probes/pile-prices/` (scripts in its `scripts/`;
`pilecodec.py` moves one card between piles by rewriting the state's
bytes, `engine/src/codec.rs`).

## Pummel timing: early Pummel is not a loss on official Act 1

Replaying all 450 fights with Pummel in the deck (`one_turn.json`): 363
Pummel plays, mean Strength at the play 1.5, fight peak 2.8; 65 plays
(18%) come 3 or more Strength below the fight's later peak, 16 of 43 in
Rupture decks. From each of those 65 plays, play-now against hold
(`hold_rise3.json`: no Pummel until Strength is 3 above where it was,
reached in 79% of futures): hold minus play now -3.01 (0.69) HP,
-0.051 (0.019) wins; Rupture decks -2.83 (1.61) HP, -0.090 (0.058) wins;
elites hold worse in all 14 plays; bosses -3.13 (1.08) HP, Hexaghost
level (+0.44 (0.74), 12 plays). A one-turn hold (`hold32.json`): -2.08
(0.65) HP, the same as on 40 plays where Strength never grew (-2.16
(0.65)). On the 19 plays in the 18 lost Pummel fights (`hold_lost.json`)
holding raises wins in 5 positions (up to +0.19) and lowers them in 10
(down to -0.88), -0.117 (0.058) wins on average. A per-position oracle
choosing hold or play gains at most +0.012 wins per growth position,
about +0.002 headline clears. Why early Pummel pays (interpretation):
fights last about 5 turns and early damage shortens them.

## Exhausting Pummel: the net prices it at a quarter of its worth

200 turn-start positions with Pummel in draw or discard (`exval.json`),
one copy moved to exhaust: the net's HP change -0.6, played out -2.2
(0.7); the gap -1.6 (0.7). The net's change does not grow with Strength
(slope 0.00 HP per Strength point against about -2 played out); bosses
-3.7 against -13.0, Rupture decks -1.0 against -7.2. A Strike moved
instead: net -0.7, played out +0.35 (0.33).

## Eight cards: the net reads card identity but prices it wrong

180 positions, 60 each hallway, elite, boss (`exval2.json`), each card
present moved to exhaust in turn. Net against played-out HP change:
Defend -1.17 / +0.20 (0.41), Strike -0.99 / +0.86 (0.43), Bash -0.78 /
-1.35 (0.74), Hemokinesis -5.25 / +3.04 (1.73), Carnage -1.82 / -0.41
(0.74), Shrug It Off -3.96 / -1.61 (1.22), Inflame -7.38 / -3.73 (2.28),
Heavy Blade -1.11 / -0.14 (0.55). Across cards corr 0.29. Hemokinesis's
positive played-out change here (31 positions) does not hold on the
1,500-position pairs below: 97 Hemokinesis pairs play out -2.81 HP
against the net's -6.00, the right sign and overpriced about twice.

## 1,500 positions: the design fits clean pairs but does not generalise

1,500 turn-start positions (500 per fight kind), up to 3 random cards from
draw or discard each, 4,448 pairs (`pairs.jsonl`); split by sequence,
1,202 train and 298 held out. Split-half agreement of the played-out
changes puts the best reachable held-out correlation at about 0.81. Held
out: the 10-29 net 0.20; a per-card mean from the training pairs 0.17;
the whole net fine-tuned on the pairs (change loss x10 plus level loss,
Adam 1e-4, full batch) 0.20 at 300 positions, 0.30 at 600, 0.29 at 1,202
(best of 300/600/1000 steps); it fits its training pairs at 1.00. By kind,
net against played out: status cards +0.04 / +3.35 HP (54 pairs), starter
cards -1.04 / +0.09 (425), picked cards -2.83 / -2.25 (404). The net's
level error on these positions is 31.9 HP RMS, mostly win chances at
bosses. Architecture read (`scripts/stsnet.py` ValueNet): piles are not
merged; each card's summary is formed from the card's own vector, times
its count, summed per pile, 7 pile slots side by side into the head; the
card's summary does not see the player's Strength (`py/src/features.rs`
card damage is amount x hits as printed).

## Shown card numbers: a zero-shot gain where Strength or Weak is up

The owner's proposal (Slay the Spire's applyPowers): card numbers as the
game shows them, damage + Strength x hits (x0.75 under Weak), block +
Dexterity (x0.75 under Frail), written into the existing damage and block
columns after encoding (`scripts/zs.py`, `fit_shown.py`). Attack pairs with
the player's Strength or Weak not zero hold 30% of the pairs and 31% of
the net's squared error; priced perfectly they would lift the
correlation 0.18 to 0.53 (`share.py`). The unchanged 10-29 net given
shown numbers, all 4,448 pairs, bootstrap over positions: those attack
pairs 0.156 to 0.218 (+0.060 (0.025)), other pairs +0.009 (0.012), all
+0.026 (0.013); level error 31.9 to 30.5 HP. Fine-tuned on pairs, held
out (`shown.log`): 600 positions 0.33 shown against 0.30 printed, 1,202
positions 0.25 against 0.29, inside the about 0.05 noise of 298 held-out
positions. A sceptic subagent's case against: the head can already form
Strength x hits, so the binding limit may be the labels
(`cause/teacher-equals-student`); the rate columns, a precomputed
Strength product, read nothing (`measurement/rate-columns@ritual2`);
shown numbers use this turn's modifiers for cards drawn later; status
cards, Hemokinesis and block cards stay untouched.

## Exhaust pile hidden: a second zero-shot gain

Only Exhume reads the exhaust pile's contents, and it is a pack card
(`content/packs/act1-ironclad.json`), not in the official offers; Feel No
Pain, Dark Embrace and Dead Branch act when a card is exhausted, not on
the pile. The unchanged 10-29 net with the exhaust pile's card counts set
to 0 (`scripts/zs_noex.py`), the same 4,448 pairs, bootstrap over
positions: all pairs 0.178 to 0.203 (+0.024 (0.011)), attack pairs with
Strength or Weak +0.030 (0.026), other pairs +0.018 (0.010); with shown
numbers as well, all pairs 0.221 (+0.043 (0.013)). Level error 31.9 to
32.4 HP hidden, 30.9 with both; the mean change moves from -1.74 to -2.38
HP against -0.70 played out. By card, played out / today / hidden:
Pummel -4.38 / -0.65 / -2.01 (14 pairs), Slimed +1.53 / +0.15 / +1.54,
Burn +12.48 / -0.83 / +0.18, Wound +3.07 / -2.02 / -1.08, Strike +0.42 /
-0.97 / -1.28, Defend +0.26 / -1.05 / -1.18. Interpretation: an exhausted
card still counts toward the net's value through the exhaust slot, so
"exhausted" reads as partly "still owned". Burn's cost is an input gap,
not a price: its self-damage is not in the 10-29 vocabulary
(`how/burst-inputs`).

## Recipe check: the 0.3 plateau is not the fitting setup

A sceptic subagent pointed out that the refit above chose its step count
on the test split and fit the whole net with no regularisation, so its
0.29 could be the recipe. `scripts/recipe.py` (log `recipe.log`) splits
the 1,500 positions by sequence into 906 train, 296 validation and the
same 298 test positions, chooses steps and ridge strength on validation,
and bootstraps over positions. Test correlation with the played-out
change: the unchanged net 0.20 (0.10); whole net fine-tuned 0.27 (0.06);
whole net with a pull to its original weights (L2-SP 0.1) 0.22 (0.05);
head only, card summaries frozen, 0.24 (0.06); head only with the pull
0.21 (0.05); ridge on the frozen head input 0.13 (0.05); ridge on the
frozen penultimate layer 0.33 (0.08), which scored 0.18 on validation.
Learning curve of the whole-net fit: 25% of train positions 0.28, 50%
0.21, all 0.27. Every setup stays within about 0.05 of 0.29, far from
the reachable 0.81, so the limit lies in what the net learns from (its
inputs or its teacher, the net's own play-outs), not in the fit; more
pairs under the same teacher is a weak bet.

The two cases of one question: Demon Form's later ticks
(`cause/unseen-cards-half-edge`, `measurement/portfolio-projected-leaf`)
and the pile prices here are both value whose source lies turns before
its payoff. Showing the effect has repaired what lands inside the search
(`@tsl1`'s first tick) and given small zero-shot gains (shown numbers,
exhaust pile hidden); teaching it has not (final-score labels flat,
`cause/teacher-equals-student`; pair labels at about 0.3 whatever the
fit).

## Not covered

The two-turn product; generated content; cards beyond the eight and the
random draws above; whether a net trained from scratch on shown numbers
prices better; any play read of shown numbers.
