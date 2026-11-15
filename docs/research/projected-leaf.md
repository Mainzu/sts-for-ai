# Projected leaf (lane `projected-leaf`)

Spec `docs/specs/projected-leaf.md`. Player setting `@pl<k>`: at each
end-of-turn leaf, after `@tsl1`, once-a-turn hooks (turn start or turn
end, no self-removal) that apply Strength or Dexterity to their owner run k
more times, for the player and each living monster. The two-turn search
reaches the same leaf code at its last turn's end, so `@pl<k>` projects
two-turn leaves too (read from `search.rs` by the spec review; no test).

## Step 2: the cards rung at k = 2 (predictions, written before the read)

Job: `mutate_cards.py play --starts 200 --seeds 16 --players
heuristic,tsl,pl2 --mods inflame-turn1,df-c2-s1,metal-c2-a5,bash-c1-d5`
into `results/mutate/cards-pl.json`; `tsl` replays `cards-a.json`'s tsl
rows on the same seeds (they must match).

Predicted change in the novelty cost, pl2 minus tsl (wins, paired by start):
- inflame-turn1 (a per-turn Strength hook): +0.008 (half of the -0.018
  left), range 0 to +0.018. For: the leaf now sees two more ticks. Against:
  every hand-set price so far moved at most about 1 HP, and two ticks
  credited at once overvalue the power in short fights.
- df-c2-s1 (Demon Form variant): small, +0.005, same reasons.
- metal-c2-a5 (block, not projected): 0.
- bash-c1-d5 (plain control): 0.
Go (charter): some target 2 se toward zero; fail if inflame-turn1 moves
less than 1 se.

## Step 2 read (job 0471, `results/mutate/cards-pl.json`)

Pairing holds: all 712 starts' `tsl` rows (parent, official and modified)
are identical to `results/mutate/cards-a.json`'s, so pl2 minus tsl is
paired game for game.

Change in the novelty cost, pl2 minus tsl (wins / HP lost, se over starts):

| modifier | all | boss | elite |
|---|---|---|---|
| inflame-turn1 | -0.002 (0.002) / -0.61 (0.13) | -0.006 (0.006) / -0.33 (0.26) | +0.000 (0.001) / -0.74 (0.14) |
| df-c2-s1 | -0.004 (0.004) / -0.06 (0.18) | -0.013 (0.011) / +0.57 (0.39) | +0.001 (0.002) / -0.37 (0.18) |
| metal-c2-a5 (control) | +0.000 (0.001) / +0.14 (0.07) | +0.002 (0.003) / +0.13 (0.15) | -0.001 (0.001) / +0.14 (0.08) |
| bash-c1-d5 (control) | -0.000 (0.001) / +0.01 (0.04) | -0.001 (0.004) / -0.00 (0.10) | +0.000 (0.000) / +0.02 (0.03) |

Novelty against the heuristic, inflame-turn1: tsl -0.018 (0.005) wins /
+0.9 HP; pl2 -0.020 (0.005) / +0.2 HP. On bosses tsl -0.050 (0.015), pl2
-0.056 (0.015).

**Checkpoint cards-k2: failed.** The spec and the predictions put the cost
in wins (prediction +0.008, range 0 to +0.018); wins moved -0.002 (0.002),
1 se away from zero, and the boss column, where the wins cost sits, moved
the wrong way too (-0.006). The stop rule's fail branch holds, and the
lane's cap (4 cpu-h, 3.4 used) would not cover step 3 anyway.

Why, and what the HP column says: the projection works where the leaf can
see it. In elite and hallway fights, which every player wins, two credited
Inflame ticks make the net take the line that keeps more HP: the HP cost
of inflame-turn1 against the heuristic falls from +0.9 to +0.2 (paired
-0.61, 4.7 se; elites -0.74, 5 se), and df-c2-s1 elites gain -0.37 (2 se).
That is the turn-start leaf's pattern again (HP repaired with no games)
at a smaller size. Bosses, where the wins cost is, do not move: there the
fight is a race lasting many turns, and two ticks credited now are either
too few (long fights) or overcredited when the enemy is nearly dead, the
risk the backlog named. The block control (metal-c2-a5) costs +0.14
(0.07) HP, 2 se, not beyond: the projection changes Metallicize play
slightly through Strength it credits elsewhere in the deck. A goal-1 gain
in HP on fights already won is real but small (under 1 HP per elite
fight), and the cards rung's remaining cost is a boss-wins cost the
projection does not reach.
