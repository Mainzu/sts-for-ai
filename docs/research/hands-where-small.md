# Hands where small: more sampled hands where the two-turn tree is small (lane hands-where-small, 2026-11-07)

Lane charter: kb `lane/hands-where-small`. Goal 2: does searching again with
16 sampled hands, where the 4-hand two-turn tree is small, cut the
product's HP lost at elites?

How this moves goal 2, and how we'll know: the product samples 4 hands at
each chance node of its two-turn tree, and the review of 2026-11-06 traced
most of its exact endgame regret to that sampling. If more hands where the
tree is cheap save HP at elites (77% of pre-boss HP), the product gets
stronger at about the same cost. The elite replay (step 2) gives paired HP
lost per fight; a null closes in-fight search as spent.

## Method

- **Puzzle screen** (`scripts/analysis/hand_screen.py`): the product's
  decision at each deeper exact puzzle (`data/bench/puzzles.json`, horizon
  >= 1, both halves: 448). The decision copies the product's guarded player
  (`depth_paired.guarded_fight`): one-turn search, two-turn search (limit 16,
  400,000-node cap, K sampled hands); the one-turn pick where the two-turn
  tree cut, else the two-turn pick. Five sample seeds per puzzle. Arms: K 4,
  K 16, and adaptive (K 4; where the 4-hand tree is uncut and under 25,000
  nodes, search again with 16 and take that pick unless it cut). Regret is
  exact best minus the exact value of the pick (0.01 is about 1 HP); the
  unit is the puzzle (mean over its seeds). About 35 s on 4 threads.
- **Elite replay** (`depth_probe.py play --arm two --sample-k 16`): the 498
  floor-9 elites of the headline product file, same fights, decks and
  seeds, read paired against the file's own columns. The 4-hand arm
  reproduces the file exactly (pilot: 6 of 6 fights identical), so the
  file's columns stand as the control.

## Step 1: puzzle screen (results/hands/puzzle-screen.json)

| arm | regret | se | minus K 4 | se | nodes (mean) |
|---|---|---|---|---|---|
| K 4 (product) | 0.0063 | 0.0015 | | | 2,522 |
| K 16 | 0.0027 | 0.0009 | -0.0036 | 0.0012 | 4,449 |
| adaptive | 0.0027 | 0.0009 | -0.0036 | 0.0012 | |

- **Passes the charter's step-1 bar** (paired gain at least 2 se): 3.1 se.
- **Smaller than the review's figures.** The review gave 0.0089 at 4 hands,
  0.0030 at 16, paired 0.0059 (0.0016); here 0.0063, 0.0027, 0.0036
  (0.0012). The 16-hand figure agrees; the 4-hand one is a third lower. The
  review's script isn't on disk; the gap fits a different seed set (the
  4-hand regret is mostly sampling luck, so it moves with the seeds).
- **Mostly sampling luck, as the review said:** 74% of the 4-hand regret
  sits on puzzles the search gets exactly right on at least one seed (the
  review said 83%). Only 39 of 448 puzzles have any error at 4 hands, 28 at
  16.
- **By half:** train -0.0042 (0.0016), held-out -0.0029 (0.0017); both
  point the same way.
- **By horizon:** one turn from the end -0.0045 (0.0016, 313 puzzles); two
  or more -0.0016 (0.0012, 135). The gain sits where the two-turn tree
  reaches the end of the fight.
- **On puzzles the adaptive rule is 16 everywhere:** 98% of 4-hand trees
  are under 25,000 nodes (endgames are small), so the screen can't tell the
  two apart; the elite replay and step 3 can.
- **Size:** 0.0036 is about 0.36 HP per deeper endgame decision. A fight
  has a few such decisions near its end, so the charter's 0.3 HP per elite
  is within reach but not assured; most elite HP is lost earlier in the
  fight, where the screen says nothing.

## Step 2: elite replay at 16 hands (results/depth_probe/two16-elite-all.json, job 0342)

| | value | se |
|---|---|---|
| HP lost, 16 minus 4 hands (per elite) | -0.34 | 0.16 |
| wins | 485 of 498 both arms (paired 0.000) | 0.004 |
| fights played differently | 133 of 498 | |
| cut share (decisions where the two-turn tree hit its cap) | 1.9% | |
| seconds, all 498 at 3 threads | 2,030 | |

- **Passes the charter's step-2 bar on its point estimate** (0.34 against
  0.3; 2.1 se from zero), so the gate (0344) releases step 3 (0345). It
  passes close to its bar, and the shape says to treat it as a lead:
  - of the 133 fights that changed, 71 ended with more HP and 62 with less
    (a sign test can't tell them apart); a changed fight moves by 1.3 HP on
    average with sd 7.0. Once one pick differs, the rest of the fight
    diverges, so the gain rides on a few large swings;
  - trimmed means: 2 fights cut from each end 0.30, 5 cut 0.25, 10 cut 0.19.
    The gain is real only if the big swings lean the right way for a
    reason, which 498 fights can't show;
  - by encounter: Gremlin Nob -0.42 (0.24, 21 changed), Three Sentries -0.40
    (0.32, 58 changed), Lagavulin -0.21 (0.28, 54 changed); all point the
    same way, none alone at 2 se;
  - by HP at the start of the fight: under 40 HP -0.30 (83 fights), 40-59
    +0.05 (219), 60-79 -0.73 (184), 80+ -1.75 (12). No gain in the band that
    holds most fights; the gain sits on healthy starts, where wins aren't
    at stake (no win changed).
- **What it changes:** in-fight search isn't shown to be spent, but the
  ceiling for the adaptive rule is about 0.3 HP per elite with an interval
  of roughly 0.0 to 0.66. Step 3 must save at least 0.3 at 2 se, which
  needs it to match 16-everywhere and get lucky on the se; a pass there
  would still want a confirm on fresh fights before the product changes.
  The 4-hand replay (0343) gives the time base for step 3's 1.6x bar.

## Step 3 time base: elite replay at 4 hands (results/depth_probe/two4-elite-all.json, job 0343)

- **Reproduction holds on every fight:** `depth_probe.py read` gives
  reproduced_b 498 of 498 and HP lost 0.0, so the headline file's columns
  stand as the control for steps 2 and 3.
- **Time per fight:** 1,267 s for the 498 elites at 3 threads (2.5 s a
  fight), against 2,030 s at 16 hands everywhere (0342): 16 everywhere costs
  1.60x, exactly the charter's time bar. Both ran beside one other 3-thread
  job (0333), so the ratio isn't a load artefact; wall-clock seconds still
  carry a few percent of noise. The adaptive rule (0345) therefore has to
  match most of 16-everywhere's 0.34 HP while running fewer 16-hand
  searches; its bar is 1.6 x 1,267 = 2,028 s.

## Step 3: the adaptive rule (results/depth_probe/two-adapt-elite-all.json, job 0345)

4 hands; where the 4-hand tree is uncut and under 25,000 nodes, search
again with 16 hands. Same 498 floor-9 elites and seeds.

| | value | se |
|---|---|---|
| HP lost, adaptive minus 4 hands (per elite) | -0.21 | 0.13 |
| HP lost, adaptive minus 16 everywhere | +0.13 | 0.11 |
| wins | level (paired 0.000) | 0.004 |
| fights played differently (against 4 hands) | 99 of 498 (52 better, 47 worse) | |
| decisions searched again at 16 | 25.7% (2,586 of 10,051) | |
| seconds, all 498 at 3 threads | 1,760 (1.39x the 4-hand 1,267) | |

- **Fails the stop rule:** 0.21 HP saved per elite at 1.6 se, against a
  bar of 0.3 at 2 se; the time (1.39x) is inside its 1.6x bar, so the
  saving is what fails. The rule keeps about 60% of 16-everywhere's 0.34
  for 65% of its extra time; the two gains correlate 0.76 by fight, so
  it is the same effect, cut down.
- **Same shape as step 2:** changed fights split 52 to 47; trimmed means
  fall to 0.18, 0.14 and 0.11 (2, 5 and 10 cut from each end); the gain
  sits on healthy starts (60-79 HP: 0.47, 80+: 1.42 over 12 fights) and is
  nil at 40-59 HP (+0.03 over 219) and under 40 (0.08), where wins could
  move; no win moved. By encounter: Gremlin Nob 0.46 (0.23), Three
  Sentries 0.18 (0.19), Lagavulin 0.01 (0.23).
- **What it means:** more sampled hands buy at most about 0.2-0.35 HP per
  elite two turns deep (95% interval for 16 everywhere roughly 0.0 to 0.66),
  none of it in wins, and the cheap form keeps only part of that. In-fight
  search is spent at about 0.3 HP per elite on this setting, which is the
  charter's fail branch: the lane closes, and the product keeps 4 hands.

## Queue chain (built before step 2's read)

- Step 3's adaptive rule is `depth_probe.py play --arm two --rerun-k 16
  --rerun-below 25000` (`depth_paired.guarded_fight`'s `two["rerun"]`):
  where the 4-hand tree is uncut and under 25,000 nodes, search again with
  16 hands and use that tree unless it cut. Pilot on 6 elites: 18 s against
  19 s at 4 hands and 30 s at 16 everywhere (3 threads, load included).
- A 4-hand replay of all 498 elites gives the product's time per fight and
  checks the reproduction on every fight.
- A gate job (`depth_probe.py read ... --require-save 0.3`, step 2's bar on
  its point estimate) releases the adaptive replay only on step 2's go.
