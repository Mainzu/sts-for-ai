# Backgammon and dice-game engines: prior-art cards

Angle: backgammon and other chance-game engines (TD-Gammon, GNU Backgammon, wildbg, eXtreme Gammon / BGBlitz via third-party analysis), plus *-minimax and sampled chance-node search. Eight sources opened, all read in full text.

### Monte Carlo *-Minimax Search (2013)
- **Link:** https://ar5iv.arxiv.org/html/1304.6057 (arXiv:1304.6057) · **Venue:** IJCAI-13 (ijcai.org/proceedings/2013/93) · **Cited by:** not checked · **Read:** full text
- **Problem:** Online move choice in turn-based, stochastic, two-player zero-sum perfect-information games, where full-width expectimax and *-minimax scale with the chance branching factor.
- **Method:** At chance nodes, sample c outcomes with replacement (each weighted 1/c), combined with Star1 or Star2 pruning (variants expss, star1ss, star2ss). Iterative deepening under a 200 ms per-move limit.
- **Assumes:** Finite two-player zero-sum perfect-information game with a generative model; heuristic h bounded in [v_min, v_max] with h = u at terminals; Theorem 1 needs sampling with replacement (the proof does not cover sampling without replacement). Tuned sample widths c: Pig (20, 25, 18), EWN (1, 1, 2), Can't Stop (25, 30, 15), Ra (5, 5, 2), for expss/star1ss/star2ss.
- **Claims:** Theorem 1: P(|V̂_d − V_d| ≤ λd) ≥ 1 − (2c|A|)^d · exp(−λ²c / (2v_max²)), with no dependence on |S|; the bound needs large c for formal guarantees, and the authors say small c works in practice. Pig (2470 states, 50 runs per state) MSE: mcts 78.7, exp 91.4, Star2 87.9, expss 95.3, star2ss 97.5; sampled variants have lower bias but higher variance. Can't Stop: star2ss vs Star2 win rate 85.0%. Ra: mcms about 60% wins against its classic *-minimax counterparts. In EWN, mcms is weaker than MCTS, which the authors attribute to lacking a good evaluation function.
- **Evaluation:** Pig, EinStein Würfelt Nicht!, Can't Stop, Ra. Matches: 5000 (Pig, EWN) or 2000 (Can't Stop, Ra), two games per match with seats swapped, 200 ms per move.
- **Code:** none found (not checked)
- **Fit:** partial. It is the closest published recipe for sampling only the chance nodes with many outcomes while keeping pruning on the rest, which matches the exact-where-feasible constraint. The games are dice games with few outcomes per roll and no learned evaluation, so the numbers do not transfer directly to a 190k-parameter value net.

### TD-Gammon: Temporal Difference Learning and TD-Gammon (1995)
- **Link:** https://bkgm.com/articles/tesauro/tdl.html · **Venue:** Communications of the ACM (Tesauro 1995; the DOI 10.1145/203330.203343 comes from a search snippet, not the page) · **Cited by:** not checked · **Read:** full text
- **Problem:** Learn a backgammon evaluation function by self-play, with and without hand-built features, and compare with supervised training (Neurogammon).
- **Method:** MLP with a four-component output (win/gammon for each side; triple-value not represented). TD(λ) updates with λ-decayed gradient traces; end-of-game error z − Y. Training picks the move with the highest net score, and the article does not describe lookahead during training. Version 2.0 added 2-ply search; the current version runs a heuristic 2-ply search in real time.
- **Assumes:** Raw board encoding (checker counts per point) first; Neurogammon-style features added from v1.0. Best raw-encoding net had 40 hidden units and trained for 200,000 games. The article does not state the input count for feature-augmented nets. Stated: elementary strategies appear in the first few thousand games; sophisticated ones after "several tens of thousands".
- **Claims:** Against humans (exhibition games, no controlled protocol): v1.0 51 games, net loss 13 points (about a quarter point per game); v2.0 38 games, net loss 7 points; v2.1 40-game session, Robertie "actually trailed the entire session" and won the last game by 1 point. Robertie estimated v1.0 would lose 0.2 to 0.25 points per game to world-class players. Absolute equity errors are often a tenth of a point or more, but move rankings stay reliable because errors are correlated. Limitations: endgame technique, cube errors (doubling was not trained), and "technique is less than perfect" when building a board with no contact. The author suggests 3-ply could remove many endgame errors. Bearoff is not discussed.
- **Code:** none found
- **Fit:** partial. It is the origin of the self-play-on-outcomes training loop. It shows that a net-only chooser can reach strong play, while the search-depth benefit is only stated qualitatively and the cube and endgame gaps remain.

### wildbg-training: rollout-and-train cycles for backgammon nets
- **Link:** https://github.com/carsten-wenderdel/wildbg-training/blob/main/README.md · **Venue:** GitHub repository (companion to the wildbg engine) · **Cited by:** n/a · **Read:** full text
- **Problem:** Train a backgammon network from zero to strong play by repeated rollout-and-train cycles, with the progress tracked per cycle.
- **Method:** Each cycle generates rollouts on positions (from the previous net or random moves), then trains a supervised net on the rollout equities. Changes across cycles: one tanh hidden layer (cycle 3) to three ReLU hidden layers (cycle 8); separate contact and race nets (cycle 9); loss MSELoss to L1Loss to CrossEntropyLoss; SGD to Adam to AdamW; epochs 10 to 20 to 50 to 292 over the cycles.
- **Assumes:** Rollouts as target labels; data sizes and network shapes are not stated for most cycles. Cycle 22: race net trained on "100,000 new positions; 300,000 combined with 0016".
- **Claims:** Strength is reported as equity change against the previous net, not as ELO or match results. Quoted: cycle 7 "a bit worse than the 6th net"; cycle 11 "equity win of roughly 0.02"; cycle 12 "they now only lose 0.7% backgammon"; cycle 18 "equity win of 1.3 millipoints"; cycle 20 "roughly 3 millipoints" over 19; cycle 22 "roughly 1.5 millipoints" over 18.
- **Code:** repository linked above (license not checked); engine is wildbg
- **Fit:** good for the training loop (rollout-labelled supervised fitting, per-cycle regression tracking in millipoints). Partial for measurement: no sample sizes, no ELO, and gains are small per cycle.

### On-line Policy Improvement using Monte-Carlo Search (Tesauro and Galperin, mid-1990s; arXiv 2025 posting)
- **Link:** https://arxiv.org/html/2501.05407 (arXiv:2501.05407) · **Venue:** arXiv posting (9 Jan 2025); the page's references point to NIPS 8 (1996) · **Cited by:** not checked · **Read:** full text
- **Problem:** Improve a base policy in real time, without extensive offline training, by one step of policy improvement with Monte Carlo rollouts.
- **Method:** For each legal action, estimate its value by Monte Carlo trials that play the action then follow the base policy; choose the best. Candidates unlikely to win, or tied with the current best, are pruned early. Truncated rollouts play a few steps, then use the net's equity estimate.
- **Assumes:** Environment can be simulated; the model of nondeterminism is known; base-player decisions are fast enough to run inside rollouts. Tens of thousands of trials per decision with pruning; about a million base decisions per Monte-Carlo decision. Hardware: IBM SP1/SP2 nodes.
- **Claims:** Table 1 (ppg vs TD-Gammon 2.1 1-ply, several thousand games; MC uses 5K trials, 5–10 s/move on 32 SP1 nodes): Lin-1 −0.52 to −0.01; Lin-2 −0.65 to −0.02; Lin-3 −0.32 to +0.04. Table 2 (800 positions, equity loss per move): Lin-1 0.040 to 0.0124 (3.2×). Table 3 (truncated, 800 positions, 32 nodes): 80 hidden units, 7-step thorough 0.0120 to 0.00181 (6.6×, 65 s/move); 10 hidden units, 11-step thorough 0.0152 to 0.00318 (4.8×, 25 s/move). Quoted: "Potentially 80% or more of the base player's equity loss can be eliminated." The 80-unit result may be biased because that net generated the grading data. The authors estimate world-class humans at 0.005–0.006 on this test set.
- **Code:** none found
- **Fit:** good for the sampling-versus-exact question. Monte Carlo over chance outcomes with a value net at truncation gives measured equity-loss reductions at matched search cost, with conditions stated. Hardware is 1990s, so times are not comparable.

### Learning and Improving Backgammon Strategy (Galperin, 1994; arXiv 2025 posting)
- **Link:** https://arxiv.org/html/2504.02221v1 (arXiv:2504.02221) · **Venue:** CBCL Learning Day 1994 (per page; arXiv posting 2025) · **Cited by:** not checked · **Read:** full text
- **Problem:** Learn a backgammon value function from self-play and improve decisions online.
- **Method:** TD(λ) self-play training on a parallel machine; linear representations "performed well". At decision time, for each legal action, play many games to termination in parallel and pick the highest win percentage. No move filtering or pruning is described.
- **Assumes:** Approximation error treated as unbiased white noise, which the author calls "a naive assumption"; the evaluation must not be "coherently flawed".
- **Claims:** The rollout method beats the originally learned function "75% of the time". Decisions take "tens of seconds rather than in hours" on massively parallel hardware. Not reported: number of games, comparison with gnubg or XG, hardware or total compute.
- **Code:** none found
- **Fit:** partial. A rollout-over-learned-linear-eval design with a headline win rate and no sample sizes, so it is a lead rather than a measurement.

### Star2 on a backgammon-like tree: Hauk's sample run (GNU Backgammon list, 2003)
- **Link:** https://lists.gnu.org/archive/html/bug-gnubg/2003-08/msg00428.html (Thomas Hauk's data post, quoted in Joseph Heled's reply) · **Venue:** bug-gnubg mailing list · **Cited by:** n/a · **Read:** full text
- **Problem:** Measure Star2 against expectimax at depth 5 on a tree with backgammon-like branching.
- **Method:** Star2 with probing and cutoffs, with fast move ordering flagged as essential. Synthetic "Dice" game on a 20×20 board, chosen to approximate backgammon's branching (21 rolls, about 20 moves per roll), with an expensive difference-of-pairs evaluation. Tree: Max, chance, Min, chance, Max, chance, Min (about 2.5 ply).
- **Assumes:** Single run; depth 5; evaluation heavy in CPU cost; Star1 not measured. Heled's caveat: duplication of end positions is "much higher" than in backgammon, and the branching factor may be realistic.
- **Claims:** Expectimax: 50,564,968 total nodes, 439 s, 47,979,820 eval_board calls. Star2: 1,982,934 total nodes (including 1,963,357 probe nodes), 17 s, 1,841,987 eval_board calls, average CutBF 4.15. Reductions: node expansions about 25.50×, eval calls about 26.04×, time about 25.82×. Both scored −121. Hauk's claim: the node reduction is "nearly the same" as the evaluation-call reduction, so overhead is small.
- **Code:** none found
- **Fit:** partial. It measures exact chance-node pruning with an expensive eval, which is the CPU-hour concern, but it is one synthetic run without a learned eval, and it is not a strength measurement. The published follow-up (*-Minimax Performance in Backgammon, Hauk/Buro/Schaeffer, LNCS 2006, DOI 10.1007/11674399_4) was found but not opened, and no abstract was retrieved.

### GNU Backgammon manual: Rollouts
- **Link:** https://www.gnu.org/software/gnubg/manual/html_node/Rollouts-in-GNU-Backgammon.html · **Venue:** GNU Backgammon manual (GPL software) · **Cited by:** n/a · **Read:** full text
- **Problem:** Estimate the equity of each candidate move by rollouts (trials played out with the net), with controls on error and cost.
- **Method:** Trials play to the end or are truncated after a few plies, then the net's evaluation is used. Variance reduction is "performed automatically when looking ahead at least one ply", using the equity difference from one ply to the next. Quasi-random dice are used, stratified over only the first 2 plies. Once the game reaches the two-sided bearoff database, the win probability is exact (no error).
- **Assumes:** A net whose evaluation is good enough to truncate on; truncation trades systematic error for speed.
- **Claims:** Truncated rollouts are "better for estimating relative equity (comparing plays) than absolute equity". No trial counts, standard errors, or speedups are given on this page.
- **Code:** GNU Backgammon (GPL); source is in the project repository (not checked)
- **Fit:** partial. The design (truncation at a net, one-ply variance reduction, exact terminal databases) maps onto the constraints, but the page gives no numbers.

### Backgammon Galaxy engine analysis (vendor comparison of GNU, XG, BG Blitz)
- **Link:** https://www.backgammongalaxy.com/backgammon-galaxy-engine-analysis · **Venue:** Vendor web analysis (Backgammon Galaxy sells the engine variants it evaluates) · **Cited by:** n/a · **Read:** full text
- **Problem:** Measure how close each engine's checker and cube choices are to target rollouts, on blunder positions.
- **Method:** Mean absolute deviation in equity (millipoints) against two target rollouts. XG target: 3-ply checker play, XGR cube, 1,296 trials, truncated at bearoff, variance reduction, quasi-random dice. Gnu target: 1-ply checker play, 2-ply cube, 1,296 trials, same truncation and variance reduction.
- **Assumes:** 1,721 blunder positions, each evaluated twice (cubeful no-double and double/take), 3,442 data points; dice removed for checker-play positions; scores standardized to 0-0 to 7. Target rollouts themselves are uncertain; the report says "difficult to determine absolute accuracy".
- **Claims:** MAD vs XG target: Gnu 0-ply 84.8, Gnu 1-ply 65.3, Gnu 4-ply 43.0, XG 4-ply 37.5, XG++ 21.6, BG Blitz 5-ply 67.1. Galaxy Gnu Deep Rollout 27.8. Vs Gnu target: Gnu 0-ply 80.3, Gnu 1-ply 61.2, Gnu 4-ply 36.8. The only speed claim: "Increased evaluation speed by more than 7x" for Gnu, with no baseline or conditions.
- **Code:** none (commercial)
- **Fit:** good for the cost-accuracy question: it gives a measured error-versus-ply curve for a net engine on one data set. Partial for reproduction: vendor source, no node or time counts, and the target rollouts differ.

---

## Not opened (leads only)
- Hauk, Buro, Schaeffer, "Rediscovering *-Minimax Search" (CG 2004, pp. 35–50) and "*-Minimax Performance in Backgammon" (LNCS 2006, DOI 10.1007/11674399_4). Metadata only: the OpenAlex record for the second has no abstract. Full text is paywalled or unavailable here.
- Hauk's M.Sc. thesis "Search in Trees with Chance Nodes" (University of Alberta, 2004). The repository link returned a fetch error.
- GNU Backgammon manual, "Evaluation settings" (move filters, plies, reduced evaluations, pruning neural networks). Fetches returned HTTP 429 and then only the table of contents. Move-filter specifics are not verified.
- Matussek, exact bearoff game-winning chances (bkgm.com BearoffGWC.pdf). The PDF returned as binary.
- GNU Backgammon bearoff database (makebearoff): the man page is a lead; a 2002 list post reports a 6-point database compressed from about 6.9 MB to about 1.47 MB (search snippet, not opened).
- eXtreme Gammon primary write-ups: none found.
- Co-Evolution in the Successful Learning of Backgammon Strategy (Pollack and Blair, Machine Learning 1998, 202 citations per OpenAlex) and Programming backgammon using self-teaching neural nets (Artificial Intelligence 2002, 160 citations): metadata only.
