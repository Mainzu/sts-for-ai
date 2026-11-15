# Backgammon and dice games: cards (search angle: shallow expectimax, filters, *-minimax)

Opened 8 sources. Full text: 5 (Tesauro article, TDLeaf, Monte Carlo *-minimax, Carcassonne Star2.5, Woolsey rollouts, On-line policy improvement). Abstract only: 2 (Yeh 2016, Pollack & Blair 1996). Some fetches failed; see the end.

### Temporal Difference Learning and TD-Gammon (1995)
- **Link:** https://bkgm.com/articles/tesauro/tdl.html · **Venue:** Tesauro article, mirrored on bkgm.com (CACM 1995 per my memory; not on the fetched page) · **Cited by:** not checked · **Read:** full text
- **Problem:** Learn a backgammon evaluator by self-play and use it to choose moves.
- **Method:** MLP with sigmoid units, trained by TD(lambda) on self-play. Each turn it scores every legal move and picks the best. Version 2.0 and 2.1 play a heuristic 2-ply search in real time.
- **Assumes:** Backgammon, dice rolled each turn, raw board encoding (version 1.0 adds Neurogammon features). Output is four values (win, gammon for each side). No doubling cube in training. Dice come from the true rules, so no hidden order.
- **Claims:** Raw-encoding net with 40 hidden units after 200,000 training games reached "approximately equal to Neurogammon". Version 1.0 lost 13 points in 51 games (about 0.25 per game). Version 2.0 lost 7 points in 38 games. Article says 3-ply "would" remove many endgame errors, but gives no number.
- **Evaluation:** Exhibition games vs. top human players (Robertie, Magriel, Davis, 1991-1992). Not reproducible as a test.
- **Code:** none found
- **Fit:** partial. Confirms the recipe (learned leaves plus 2-ply in real time). It gives no per-ply numbers and assumes a human-scale match setting.

### TDLeaf(lambda): TD learning combined with game-tree search (1998, arXiv 1999)
- **Link:** https://ar5iv.labs.arxiv.org/html/cs/9901001 (arXiv cs/9901001) · **Venue:** arXiv (Baxter, Tridgell, Weaver; title from memory, confirm on the arXiv page) · **Cited by:** not checked · **Read:** full text
- **Problem:** Train an evaluator on search leaves, not on root positions, so the net learns what search needs.
- **Method:** TD(lambda) applied to the leaf node on the principal variation of each depth-d minimax search. Only extra storage is the principal-variation leaves for the game.
- **Assumes:** Two-player alternating game with a fixed search depth; FIBS backgammon weights as the starting net.
- **Claims:** "Two-ply search beat one-ply search by 0.25 points per game, and the two depths recommended different moves in 24% of positions." TD-directed and TDLeaf each trained 50,000 games, then played 1,600 games against the unchanged FIBS weights (both at 2-ply): "fluctuated around parity", with no significant change. Chess (KnightCap): rating 1650 to 2110 in 308 games.
- **Evaluation:** Backgammon vs. FIBS weights, 1,600 games at 2-ply; chess on FICS.
- **Code:** none found in the fetched text
- **Fit:** good for the training loop. It shows a search teacher (2-ply) can train the student net. Its backgammon gain did not show in the head-to-head test.

### Monte Carlo *-Minimax Search (2013, arXiv 1304.6057)
- **Link:** https://ar5iv.labs.arxiv.org/html/1304.6057 · **Venue:** arXiv (IJCAI-style paper; authors not captured in my fetch) · **Cited by:** not checked · **Read:** full text
- **Problem:** Exact expectimax and Star1/Star2 grow too fast with the chance branching factor, so they only reach shallow depths.
- **Method:** Samples c chance outcomes with replacement and averages them (sparse-sampling idea). Keeps Star1/Star2 pruning on the sampled tree. Variants: star1ss, star2ss, expss (no pruning). Proof: estimates approach the depth-d minimax value as c grows, but the bound is exponential in depth.
- **Assumes:** Discrete chance events and a known simulator. Sampling is with replacement (the proof does not cover without-replacement sampling). Tested with a 200 ms per move limit and parameters tuned by self-play.
- **Claims:** "star2ss won 85.0% against Star2 in Can't Stop." In Ra, MCMS "won roughly 60%" against classic *-Minimax. Pig statistics on 2,470 states, 50 runs per state: MCTS MSE 78.7, regret 0.41; expss bias 9.07 vs. Star1/Star2 about 9.4-9.5. Weak in EWN, which the authors blame on the evaluator.
- **Evaluation:** Pig, EinStein Wurfelt Nicht!, Can't Stop, Ra; 200 ms per move.
- **Code:** none found
- **Fit:** good. Directly matches "sample the draws for the next turn" and gives Star1/Star2 pruning on top of the sample. The 200 ms budget and game set are a usable test template.

### Playing Carcassonne with Monte Carlo Tree Search (2020, arXiv 2009.12974)
- **Link:** https://arxiv.org/html/2009.12974 (arXiv 2009.12974) · **Venue:** arXiv · **Cited by:** not checked · **Read:** full text
- **Problem:** Choose moves in Carcassonne, a stochastic tile game, with MCTS and with *-minimax.
- **Method:** Star1 uses bounds U and L on unevaluated chance children. Star2 probes one child to set the bound. Star2.5 probes f > 1 children (f = 0 is Star1, f = 1 is Star2). Star2.5 is compared with MCTS and MCTS-RAVE.
- **Assumes:** Stochastic tile draws; bounds U = 100 and L = -100 set by hand (the paper does not explain how they are derived from an evaluator).
- **Claims:** "A depth of 3 was the maximum that allowed the Star2.5 agent to return an action." Depth 4 never returned a result; depth 2 "performed poorly". Star2.5 used 20.58 min per game vs. random. MCTS beat Star2.5 at 88.57% as first player and 77.14% as second, over 140 games. No node counts or pruning savings reported.
- **Evaluation:** Carcassonne matches, 100 or 140 games with swapped seats and fixed tile sequences.
- **Code:** none found
- **Fit:** partial. A warning: exact *-minimax with a weak bound timed out at depth 4. Its wall-clock cost is what the sts-for-ai problem faces.

### Backgammon rollouts (Woolsey column, bkgm.com, Jan 2000)
- **Link:** https://bkgm.com/articles/GOL/Jan00/roll.htm · **Venue:** bkgm.com column (Woolsey) · **Cited by:** not checked · **Read:** full text
- **Problem:** Judge a play by simulating the rest of the game many times.
- **Method:** Rollouts are normally played at 1-ply. 2-ply rollouts are "stronger but takes too long". Variance reduction may let bots use 2- or 3-ply.
- **Assumes:** Human play by a program at a fixed ply; sample counts matter.
- **Claims:** A 1296-trial rollout suggested a play that a 5000+ trial rollout called "a fluke". "At about 10,000 trials, it is very unlikely" the worse play wins by luck. Two programs' holding-game rollouts "differed by as much as .100 in equity". Gives no numeric equity gain per ply.
- **Evaluation:** Hand analysis of backgammon positions (not a benchmark).
- **Code:** none
- **Fit:** partial. Useful as the yardstick idea: how many samples before a comparison is trustworthy. Not a method.

### On-line Policy Improvement using Monte-Carlo Search (arXiv 2501.05407, posted 2025)
- **Link:** https://arxiv.org/html/2501.05407 · **Venue:** arXiv (authors not captured in my fetch; content looks like an older backgammon study, my guess) · **Cited by:** not checked · **Read:** full text
- **Problem:** Policy improvement by Monte-Carlo is too slow for real-time backgammon play.
- **Method:** For each candidate action, estimate its value by simulation with a fixed base policy after it. Prune candidates unlikely to be best or equivalent to the current best. Truncated rollouts stop early and use the net's equity.
- **Assumes:** Backgammon; base players are a random policy, linear nets (Lin-1 to Lin-3), and 10- and 80-unit nets. Full rollouts take about 25-30 decisions per trial.
- **Claims:** Full-game table vs. TD-Gammon 2.1 1-ply: Lin-1 base -0.52 ppg, Monte-Carlo -0.01; Lin-2 -0.65 vs -0.02; Lin-3 -0.32 vs +0.04. Truncated rollouts, 80-unit net, 7-step thorough: loss 0.00181 (6.6x better), 65 sec/move; optimistic 18 sec/move. Multi-layer nets "at least a factor of 100 slower" than linear ones. Full-rollout cost is about a million base decisions per decision, cut to "several tens of thousands" trials by pruning. Test set of 800 positions.
- **Evaluation:** Backgammon, 800-position test set; 5000 games vs. TD-Gammon 2.1 (about 350 hours on 32 SP1 nodes).
- **Code:** none found
- **Fit:** good for the candidate-filter idea (pruning candidates before costly evaluation). Rollout cost is far above the CPU budget.

### Multi-Stage Temporal Difference Learning for 2048-like Games (2016, arXiv 1606.07374)
- **Link:** https://arxiv.org/abs/1606.07374 · **Venue:** arXiv (Yeh, Wu, Hsueh, Chang, Liang, Chiang) · **Cited by:** not checked · **Read:** abstract only (the arxiv.org/html and ar5iv routes failed: 404 and redirect)
- **Problem:** TD-learned 2048 programs rarely reach large tiles.
- **Method:** Multi-stage TD (MS-TD) learning with n-tuple networks, used as leaf values for expectimax (per the abstract).
- **Assumes:** Stochastic tile spawns (dice-like), a learned value at the leaf.
- **Claims:** "using 3-ply expectimax search, the program with MS-TD learning reached 32768-tiles with a rate of 18.31%, while the one with TD learning did not reach any." After tuning, "31.75% in 10,000 games". Threes: 6144-tile rate 7.83%. No speed figures. (A 1-ply vs. 2-ply reach-rate table seen in a search snippet was not checked.)
- **Evaluation:** 2048 and Threes, 10,000 games.
- **Code:** none found
- **Fit:** partial. A stochastic game with depth-limited expectimax on learned leaves. The depth numbers come from the abstract page only.

### Why did TD-Gammon Work? (NIPS 1996)
- **Link:** https://papers.nips.cc/paper/1292-why-did-td-gammon-work · **Venue:** NeurIPS 1996 (Pollack, Blair) · **Cited by:** not checked · **Read:** abstract only
- **Problem:** Why TD-Gammon worked and whether the result transfers.
- **Method:** Hill-climbing on a 4,000-parameter feed-forward evaluator (no TD, no backprop), in a relative fitness setting.
- **Assumes:** Backgammon; the result depends on co-evolution.
- **Claims:** The authors replicated "part of its success"; they conclude the success came from the co-evolutionary structure of the task and backgammon's dynamics. No numbers on search depth on the abstract page.
- **Evaluation:** Backgammon.
- **Code:** none found
- **Fit:** poor. It does not address search depth or pruning.

## Not read
- Veness and Blair, "Effective Use of Transposition Tables in Stochastic Game Tree Search" (CIG 2007, cgi.cse.unsw.edu.au/~blair/pubs/2007VenessBlairCIG.pdf): the PDF came back as binary; no card. Its only stated claim (from a search snippet): transposition tables cut Star2's search effort by about 37 percent. Unverified.
- GNU Backgammon manual move-filter pages (gnu.org/software/gnubg/manual/...): four different pages returned HTTP 429. No card. From a search snippet only: the "Normal" move filter accepts 0 moves at 0-ply and adds up to 8 within 0.16, and pruning nets act at 1-ply and deeper. Needs a retry.
- Ballard's 1983 *-minimax paper: only a DTIC abstract in search results; not opened.
