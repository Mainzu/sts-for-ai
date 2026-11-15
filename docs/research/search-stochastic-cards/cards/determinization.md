# Determinization and hidden information: scout cards

Angle: PIMC, ISMCTS, strategy fusion and non-locality, how many
determinizations, when PIMC works, open-loop vs closed-loop planning.

Opened 8 papers. Full text: 6. Abstract only: 2 (Bitan and Kraus; Long et al.).

### Perfect Information Monte Carlo with Postponing Reasoning (2024)
- **Link:** https://arxiv.org/html/2408.02380 (read via https://ar5iv.labs.arxiv.org/html/2408.02380) · **Venue:** arXiv (authors also list a CoG 2024 version; OpenAlex W4401943497) · **Cited by:** not checked · **Read:** full text
- **Problem:** PIMC gives each sampled world its own perfect-information strategy, which causes strategy fusion; the paper says this hurts most in games with private observations.
- **Method:** EPIMC postpones the perfect-information leaf evaluator to a depth Dpt (PIMC is Dpt=1). Samples play down the tree and build a subgame; after the budget, the subgame is solved with Information Set Search or CFR+. Deeper depth lowers strategy fusion but costs more sampling.
- **Assumes:** Two-player imperfect-information games from OpenSpiel with discrete actions and tree search; leaf evaluator is a perfect-information evaluator (minimax or random rollouts). Single CPU (Intel Xeon Gold 5218). Default depth 3, Information Set Search, random rollouts.
- **Claims:** Against PIMC with a 1 s budget, Dark Chess at 100 s gives about 80% / 65% / 45% winning rate at depths 3 / 2 / 1. Dark Hex and Dark Chess at 1000 s: depth 3 wins close to 100%. Dark Hex 3x3 leaf evaluator comparison: Minimax close to 70%, Random Rollout close to 50%. Three propositions on the count of strategy-fusion infostates (depth never increases it in the worst case; some depth removes it in finite-horizon games). These cover strategy fusion only, not performance or convergence.
- **Evaluation:** OpenSpiel Card Game, Battleship 3x3, Dark Chess 4x4, Phantom Tic-Tac-Toe, Dark Hex 4x4 (3x3 tests too). Budgets 0.1 to 100 s (or 1000 s for Dark games). 500 games per experiment, seats split evenly. Opponent PIMC at 1 s. Number of worlds not reported (sampling runs until the budget ends).
- **Code:** none found (games come from OpenSpiel, which the paper cites)
- **Fit:** partial. It targets strategy fusion, which is the defect a net-at-leaves search would carry. But its games are small boards or a tiny card game, and it reports no determinization counts. Its finding that games with mostly public observations gain little from depth is a direct warning for a game where draws are the only hidden part.

### The alpha-mu Search Algorithm for the Game of Bridge (2019)
- **Link:** https://arxiv.org/abs/1911.07960 (read via https://ar5iv.arxiv.org/html/1911.07960) · **Venue:** arXiv (Cazenave and Ventos; Bridge search) · **Cited by:** not checked · **Read:** full text
- **Problem:** PIMC plays sub-optimally because of strategy fusion (different cards in different sampled worlds) and non-locality (local choices block the global optimum).
- **Method:** An anytime search that keeps Pareto fronts of 0/1 outcome vectors over the worlds. Max nodes take the union of fronts; Min nodes take per-world minimums over child-front combinations. Depth 1 reduces to PIMC. With full search over all worlds it removes both defects; stopped early it is heuristic. Cuts and a transposition table with iterative deepening speed it up.
- **Assumes:** Perfect information for the opponents within each world. A double-dummy solver (Bo Haglund's DDS) is the leaf evaluator. Bridge with fixed bidding (3NT contract), 52-card or 36-card deals.
- **Claims:** Declarer win rate, 52 cards, 20 worlds: PIMC M=1 60.2%, M=2 63.0%, M=3 62.0%. 52 cards, 40 worlds: 62.4%, 62.4%, 63.2%. 36 cards, 20 worlds: 46.4%, 47.8%, 48.2%. Timing, 52 cards, 20 worlds, average per move: M=1 0.096 s; M=3 18.678 s without optimizations, 1.228 s with transposition table and cuts ("about fifteen times faster while returning the same move").
- **Evaluation:** 500 initial deals, duplicate scoring, keeping deals where PIMC's win rate is 30% to 70%. Declarer alpha-mu plays against two PIMC defenders. 3NT contract, fixed bidding.
- **Code:** none found in the page text
- **Fit:** partial. It is the clearest worked example of fixing strategy fusion by search cost, with numbers. It needs an exact perfect-information solver at every leaf. Our game has a simulator but no double-dummy-style solver, and it has no value net.

### Optimizing alpha-mu (2021)
- **Link:** https://arxiv.org/abs/2101.12639 (read via https://ar5iv.labs.arxiv.org/html/2101.12639) · **Venue:** arXiv (Cazenave, Legras, Ventos; CoG 2021 per the authors' page) · **Cited by:** not checked · **Read:** full text
- **Problem:** alpha-mu is slow; make it faster without changing its output.
- **Method:** Useful-world tracking (drop worlds that can no longer change the result); world cuts (stop when no or one useful world remains); "Empty Entry" (Pareto fronts at shallower depth so cuts happen earlier); alpha cut, including a deep variant, at Min nodes; Cut on Win at Max nodes; parallel double-dummy searches at leaves.
- **Assumes:** Same as alpha-mu: Bridge, double-dummy leaves, 32- or 52-card starts, 20 or 40 worlds per decision. Hardware not stated on the page.
- **Claims:** 52 cards, 20 worlds, 3 Max moves: 3.020 s with no optimizations, 1.032 s with all. 32 cards, 20 worlds, 3 Max moves: 2.016 s to 0.605 s. 32 cards, 40 worlds, 3 Max moves: 4.381 s to 1.297 s. Leaf parallelization, 52 cards, 2 Max moves, 20 worlds: 0.067 s with 1 thread, 0.042 s with 6 threads. Conclusion: "three times faster"; parallelization factor 2.
- **Evaluation:** 100 games per setting (3200 searches at 32 cards, 5200 at 52 cards), 20 or 40 worlds.
- **Code:** none found in the page text
- **Fit:** partial. Useful as a cost reference for world-count versus search cost, and for pruning ideas that keep the output the same (a matter of exact pruning that our net-based search might reuse). Bridge-specific in its leaf solver.

### Open Loop Execution of Tree-Search Algorithms (2018, extended version v2 2019)
- **Link:** https://arxiv.org/abs/1805.01367 (read via https://arxiv.org/html/1805.01367) · **Venue:** arXiv (Lecarpentier, Infantes, Lesire, Rachelson; ONERA and ISAE-SUPAERO) · **Cited by:** not checked · **Read:** full text
- **Problem:** UCT re-plans from scratch at each step. Can a sub-tree be reused as an open-loop action sequence without re-planning, and when is that safe in a stochastic setting?
- **Method:** OLTA builds an open-loop UCT tree (OLUCT). At each step a criterion chooses between reusing the sub-tree of the recommended action and re-planning. Five criteria: plain OLTA (reuse only if the root is fully expanded), SDM (state-distribution modality), SDV (state-distribution variance), SDSD (Mahalanobis distance to the state distribution), RDV (return-distribution variance). Criteria can be combined; the paper says they are problem-dependent with no generic rule.
- **Assumes:** Generative model of a finite-action MDP with stochastic transitions, deterministic rewards, discount gamma, infinite horizon. Actions do not depend on state (open loop). Said to extend to POMDPs. Theory assumes one optimal action per node and a UCT constant chosen so tail inequalities hold.
- **Claims:** Root-action failure probability at depth d is bounded by ceil(rho ln(b(d-1)))^(-(rho/2)(delta^d)^2), which goes to zero as the budget grows (worst case; Figure 2 uses C_p = 0.7, delta^d = 0.27). Discrete 1D track (1000 episodes, n = 20, q in [0, 0.5]): non-plain variants match OLUCT's loss; plain OLTA is weaker; cost drops at low q. No exact numbers given. Physical TSP (continuous, 100 episodes, n = 300): OLUCT, SDSD and RDV comparable loss; plain OLTA highest loss; SDSD and RDV best cost-performance trade-off.
- **Evaluation:** Discrete 1D track; continuous Physical Travelling Salesman Problem; appendix runs on continuous 1D track (n = 100) and discrete PTSP (n = 200, 1000 episodes).
- **Code:** GitHub erwanlecarpentier/1dtrack and erwanlecarpentier/flatland; no license stated on the page (arXiv non-exclusive license for the paper)
- **Fit:** partial. It is the open-loop vs closed-loop question for stochastic planning, which is what a chance draw creates. It is single-agent MDP, not hidden-information, and it gives no numbers we could reproduce without the repos.

### Mixture of Public and Private Distributions in Imperfect Information Games (2024)
- **Link:** https://arxiv.org/abs/2405.14346 (read via https://arxiv.org/html/2405.14346) · **Venue:** arXiv; the authors list 2023 IEEE Conference on Games (CoG) · **Cited by:** not checked · **Read:** full text
- **Problem:** Determinization (PIMC, IS-MCTS) samples hidden states from the acting player's private belief, which can leak private information to opponents and make the player exploitable. Using public information only throws away useful private information.
- **Method:** Belief mixture Delta_lambda(s_i) = (1 - lambda) Delta_i(s_i) + lambda Delta_pub(s_pub). lambda = 0 is private; lambda = 1 is public. Also varies lambda across game stages.
- **Assumes:** Two-player zero-sum imperfect-information games with explicit beliefs over hidden states. Perfect-information evaluator (AlphaBeta for PIMC; random rollouts for IS-MCTS, exploration constant 0.7). 1000 world states per decision. Policies rerun until variation under 1%.
- **Claims:** Expected utility vs best responder (lower is better), PIMC Liar's Dice 2D: 0.300 at lambda 0.0, 0.382 at lambda 1.0, best 0.281 at lambda 0.6. PIMC Leduc Poker: 0.622 at lambda 0.0, 1.611 at lambda 1.0. IS-MCTS Leduc: 0.797 at lambda 0.0, 2.326 at lambda 1.0. Winning rate vs PIMC, Liar's Dice 3D: 48.6 at lambda 0.0, 27.8 at lambda 1.0. Private distribution beat public in every benchmark tested against the best responder. Winning rates over 1000 games, 95% CI +/-3.1%.
- **Evaluation:** Liar's Dice (2, 3 and 5 dice), a 10- or 20-card trick-taking game, Leduc Poker. Built on OpenSpiel.
- **Code:** none linked; authors say their code is based on OpenSpiel
- **Fit:** partial. The leak problem is about hiding one's own belief from opponents, which matters less in our game, where the hidden thing is the shuffle and the opponent's hand is random. Still the only paper here that puts numbers on the belief used to sample worlds.

### Combining Prediction of Human Decisions with ISMCTS in Imperfect Information Games (2017)
- **Link:** https://arxiv.org/abs/1709.09451 · **Venue:** arXiv (Bitan and Kraus) · **Cited by:** not checked · **Read:** abstract only
- **Problem:** ISMCTS on the Cheat Game, where the opponent's hidden actions are deceptive.
- **Method:** Semi-Determinized MCTS (SDMCTS): a predictive model of the opponent's hidden actions, learned from behavioural data; simulations run on game instances where those hidden actions are fixed.
- **Assumes:** A learned model of human opponent choices from historical data.
- **Claims:** 120 human subjects played head-to-head against SDMCTS agents, which performed well; performance improved as predictive accuracy rose. No win rates or accuracy values on the abstract page.
- **Evaluation:** Cheat Game with human subjects.
- **Code:** none found
- **Fit:** poor. Human-opponent modelling, not a scripted or random game; read from the abstract only.

### Understanding the Success of Perfect Information Monte Carlo Sampling in Game Tree Search (2010)
- **Link:** https://ojs.aaai.org/index.php/AAAI/article/view/7562 (landing page read via https://www.cs.du.edu/~sturtevant/papers/long2010understanding.html; PDF at https://cdn.aaai.org/ojs/7562/7562-13-11092-1-2-20201228.pdf was unreadable through WebFetch) · **Venue:** AAAI 2010 (AAAI-10, pp. 133-137 per the PDF footer) · **Cited by:** 81 (OpenAlex, W1646839507) · **Read:** abstract only (the landing page gives a paraphrase, not the verbatim abstract)
- **Problem:** Why PIMC works well in practice despite criticism on theoretical grounds.
- **Method:** Uses synthetic game trees to find properties that make PIMC perform well or poorly against an optimal player; then checks whether those properties can be detected in real games and predict PIMC's strength.
- **Assumes:** Imperfect-information games too large to solve exactly; the properties are measured on the game tree, so the method needs the tree's structure.
- **Claims:** None with numbers in the text I could read. The page says the properties predict PIMC's strength in real games.
- **Evaluation:** Synthetic game trees, then real games (not named in the text I read).
- **Code:** none found
- **Fit:** good for the "when does PIMC work" question, but the full text was not reached. Needs a PDF read before anyone relies on it.

## Leads not opened (fetch failed)

- Cowling, Powley, Whitehouse, "Information Set Monte Carlo Tree Search" (2012). Eprint PDF https://eprints.whiterose.ac.uk/id/eprint/75048/1/CowlingPowleyWhitehouse2012.pdf returned binary through WebFetch. OpenAlex W2113228754, 159 citations. The IEEE TCIAIG paper is the ISMCTS reference.
- Cowling, Powley, Whitehouse, "Ensemble Determinization in MCTS for MTG" (2012). Eprint PDF https://eprints.whiterose.ac.uk/id/eprint/75050/1/EnsDetMagic.pdf returned binary. OpenAlex W2077755260, 77 citations. Snippet says the best number of determinizations was 20 to 100 at a fixed budget; not verified.
- Goodman, "Re-determinizing MCTS in Hanabi" (IEEE CoG 2019). https://ieee-cog.org/2019/papers/paper_17.pdf returned binary.
- Powley, Cowling, Whitehouse, "Information capture and reuse strategies in MCTS" (AI 2014). Falmouth repository PDF https://falmouth-test.eprints-hosting.org/2264/1/info_capture_reuse.pdf not tried. OpenAlex W2112361867, 20 citations. Describes EPIC, a method for hidden information and randomness.
- Frank and Basin, "A theoretical and empirical investigation of search in imperfect information games" (TCS 2001). OpenAlex W1969269538, 34 citations. Snippets say PIMC errors occur regardless of the number of worlds examined. Not opened.
- Dou Di Zhu determinization paper (Cowling et al.) snippet: 40 determinizations with 250 UCT iterations each. Not opened; from a search snippet only.
- Bitan and Kraus, related: none.
