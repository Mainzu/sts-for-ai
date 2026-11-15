# Search with noisy or biased evaluations: cards

Angle: search pathology, the optimizer's curse / max-bias, error propagation with depth, when deeper search helps or hurts, and corrections (regularized overrides of a prior, uncertainty-aware selection, pessimism over an ensemble).

Opened 10 papers in total; the 8 best-fitting are carded below. Schramm and Boularias (Volume-MCTS, arXiv 2407.05511) and van Hasselt et al. (Double DQN, arXiv 1509.06461, abstract only) were opened past the target and left out for fit.

Not opened (leads only): Smith and Winkler (2006), "The optimizer's curse" (Management Science 52(3)): the PDF on gwern.net came back as unreadable binary. Wilson, Parker and Nau (2009), "Error Minimizing Minimax": the umd.edu PDF failed with a certificate error. Lustrek, Gams and Bratko, the real-valued minimax papers: PDFs on dis.ijs.si, not fetched. Lee and Powell, "Bias-corrected Q-learning" (AAAI 2012): not fetched.

---

### The Surprising Difficulty of Search in Model-Based Reinforcement Learning (2026)
- **Link:** https://arxiv.org/abs/2601.21306 (full text read at https://arxiv.org/html/2601.21306, v2 revised May 2026) · **Venue:** PMLR v306 (2026) · **Cited by:** not checked · **Read:** full text
- **Problem:** Adding model-predictive control (search) to a good learned policy can make it worse, even when the learned model is about as accurate as a model where search helps.
- **Method:** MR.Q with MPC is compared with MR.Q alone. The proposed MRS.Q takes the minimum over an ensemble of 10 value functions, both in value targets and in MPC trajectory scoring, and drops exploration noise.
- **Assumes:** Continuous control with a learned dynamics model. MPPI search with a 3-step horizon, 6 iterations, 512 samples, value bootstrap beyond the horizon. 1M environment steps, 10 seeds.
- **Claims:** Aggregate final scores at 1M steps: Gym MR.Q 1.46 vs MR.Q+MPC 0.67; DMC 0.84 vs 0.65. MRS.Q Gym 1.54 (best), DMC 0.81 (BMPC 0.86), HumanoidBench no hands 0.59 (best), hands 0.58 (best). The paper says the ensemble minimum applied to TD-MPC2 improved it on all four benchmarks. Overestimation was largest where search hurt most (Figure 3, as the paper states it).
- **Evaluation:** MuJoCo Gym (5 tasks), DeepMind Control (28 tasks), HumanoidBench (14 tasks). Evaluated every 5k steps over 10 episodes, with 95% CIs.
- **Code:** none checked
- **Fit:** partial. The diagnosis matches ours: search amplifies value overestimation on actions the data did not cover, and an ensemble minimum fixes it. But the setting is continuous control with a learned model, not a perfect simulator with hidden draw order.

---

### Monte-Carlo Tree Search as Regularized Policy Optimization (2020)
- **Link:** https://arxiv.org/abs/2007.12509 (full text read at https://arxiv.org/html/2007.12509; the appendix proofs were cut off) · **Venue:** ICML 2020 (PMLR v119) · **Cited by:** not checked · **Read:** full text
- **Problem:** AlphaZero's visit-count search rule, and UCT, lag behind new search values when the simulation budget is low, and the prior policy's weight is not set in a principled way.
- **Method:** The target policy maximises q·y minus λ_N times KL[π_θ, y], where λ_N = c·√(Σn_b)/(|A| + Σn_b) shrinks as visits grow. Its closed form is π̄ = λ_N·π_θ/(α − q), with α found by bisection. The paper's variant "All" uses this for acting, for search, and for training the prior.
- **Assumes:** A learned prior policy π_θ and discrete actions. Search values q enter the formula directly, so their scale matters relative to c. Experiments used MuZero-style learners with 5 or 50 simulations.
- **Claims:** The paper says the largest gains come at low simulation budgets. On Ms Pacman, "All" beats MuZero at 5 simulations per step on learning speed and asymptotic score; at 50 simulations the two are close, with All marginally ahead. At 50 simulations, All consistently outperforms MuZero on Alien, Asteroids, Gravitar and Seaquest (per the paper's figures). DMC image-based Walker-Run: All 644 vs MuZero 533 (3 seeds).
- **Evaluation:** Atari (Ms Pacman, Alien, Asteroids, Gravitar, Seaquest) with 8 seeds; DeepMind Control with 64×64×3 pixels, 5 bins per action dimension, 3 seeds.
- **Code:** none checked
- **Fit:** partial. The formula is the clearest statement of how a prior policy and noisy search values should be mixed, with the prior's weight shrinking as visits grow. It is a training-time rule with learned nets, not a rule for overriding a fixed heuristic.

---

### Uncertainty-sensitive Learning and Planning with Ensembles (2019)
- **Link:** https://arxiv.org/abs/1912.09996 (full text read at https://arxiv.org/html/1912.09996) · **Venue:** arXiv (v3, March 2020) · **Cited by:** not checked · **Read:** full text
- **Problem:** Hard-exploration planning with learned value functions, where the single value estimate misleads the tree search.
- **Method:** An ensemble of K value networks. Each tree node holds one value per member. The tree picks argmax_a of mean + κ·std over the ensemble, and new leaves are scored by the ensemble.
- **Assumes:** Discrete actions and a fixed number of planning passes (10 per decision). Perfect model for Deep-sea and Toy Montezuma's Revenge; learned model for multi-board Sokoban. Sparse rewards. κ is set per environment: 50 (Deep-sea), 3 (Toy MR), 9 (single-board Sokoban). The multi-board Sokoban uses a voting rule instead.
- **Claims:** Toy Montezuma's Revenge, 1.2M steps: no ensemble 0/43 solved (4.7 rooms); ensemble without std 2/40 (5.8 rooms); ensemble with std 30/37 (17.5 rooms). Single-board Sokoban 73% vs 50% without ensembles; 8×8 with 4 boxes 94% vs 64%. Multi-board Sokoban 89.0% vs 84.7% (last 1000 games, 10M steps). The paper says only the κ=50 setup solves large Deep-sea instances (N>20).
- **Evaluation:** Deep-sea (Osband et al.), Toy Montezuma's Revenge (Roderick et al.), Sokoban levels generated as in Racanière et al.; 10 seeds for multi-board Sokoban.
- **Code:** none checked
- **Fit:** good. Shows that a penalised, uncertainty-aware pick inside a tree with a perfect model fixes a case where the plain value makes search fail. Constraint breaks: κ needs tuning per environment, and the paper gives no principled way to set it.

---

### Planning and Learning with Adaptive Lookahead (2022)
- **Link:** https://arxiv.org/abs/2201.12403 (full text read at https://arxiv.org/html/2201.12403, v2 dated 18 January 2023) · **Venue:** arXiv · **Cited by:** not checked · **Read:** full text
- **Problem:** A fixed planning horizon is wasteful for some states and harmful for others. The question is how far to look from each state.
- **Method:** Use the value estimate to pick each state's lookahead depth. TLPI uses a threshold: deepen to h(κ) when |Ṽ*(s) − U(s)| > κ‖Ṽ* − V^π‖∞ − β. QLPI uses quantiles of the distance from Ṽ*, with budgets per depth. QL-DQN deepens level by level and stops when the best leaf's distance falls in the current quantile.
- **Assumes:** Discounted finite MDP with a known model. TLPI needs a sup-norm bound ‖V* − Ṽ*‖∞ ≤ ε and sets β = ε(κ+1). QLPI needs only that Ṽ* be m-order-preserving and adds m/S to the quantile budgets. Ṽ* comes from state aggregation, a warm start, or a DQN trained 1M steps.
- **Claims:** Maze, 30×30 four rooms, γ = 0.98, 10 runs: TLPI and QLPI match the best fixed horizon across tested parameters and sometimes beat it (values in plots only). Atari, 5 seeds, wall-clock: QL-DQN beats fixed-depth DQN (depths 0 to 3) on VideoPinball and Tutankham, and is on par on Solaris and Berzerk.
- **Evaluation:** Maze simulator queries to convergence; Atari wall-clock curves against fixed depths 0 to 3.
- **Code:** none checked
- **Fit:** good. Directly answers "when does deeper search help": deepen only where the value error is smaller than the gain. Constraint breaks: the rules need a value-error bound (sup-norm ε or order-preservation), which our net does not have. A measured error estimate would have to stand in for it.

---

### Look-ahead Search on Top of Policy Networks in Imperfect Information Games (2023, v3 2025)
- **Link:** https://arxiv.org/abs/2312.15220 (full text read at https://arxiv.org/html/2312.15220) · **Venue:** arXiv · **Cited by:** not checked · **Read:** full text
- **Problem:** A blueprint policy network (trained with RNaD) can be improved at test time by search, in two-player zero-sum imperfect-information games.
- **Method:** SePoT trains a critic alongside the policy, with no search during training. At play time, when the public state can be rebuilt and the subgame is small enough, it builds a depth-limited gadget game and solves it with CFR+. Otherwise it plays the policy network directly.
- **Assumes:** Two-player zero-sum games with known rules. Subgame size limit of 25,000 or 100,000 histories. Reach probabilities give the ranges. Hidden information is handled by the gadget game.
- **Claims:** Head-to-head average reward ×100, RNaD+SePoT vs RNaD, for max subgame 25,000 / 100,000 histories: Goofspiel 8 randomized 2.70±0.05 / 3.10±0.19; Goofspiel 13 descending 3.44±0.05 / 3.51±0.1; Goofspiel 13 randomized 1.12±0.05 / 1.43±0.3; Battleships 3×3 6.2±0.06 / 6.5±0.07; 5×5 81.9±0.3 / 83.5±0.5; 7×7 24.1±0.7 / 42.1±0.9. The paper says search beat the network with significance in all tested games. Depth limits 2 and 3 beat depth 1 on exploitability (figures only).
- **Evaluation:** Leduc hold'em, Goofspiel (5, 8, 13 cards), Battleships (3×3, 5×5, 7×7); over 100,000 simulations, three RNaD networks, seats swapped.
- **Code:** none checked
- **Fit:** partial. Good match for the fallback: search replaces the policy only where it can be solved, and the policy plays elsewhere. Constraint breaks: it needs known game rules and exact public-state reconstruction, which our hidden draw order complicates. CPU only is fine.

---

### A Bayesian Approach to Online Planning (2024)
- **Link:** https://arxiv.org/abs/2406.02103 (full text read at https://arxiv.org/html/2406.02103v1; appendix cut off) · **Venue:** ICML 2024 (PMLR v235) · **Cited by:** not checked · **Read:** full text
- **Problem:** Neural leaf values are imperfect, so the tree search should use their uncertainty when it picks a branch.
- **Method:** Thompson Sampling Tree Search, which samples leaves from the posterior probability of lying on the optimal branch, with a max backup. Also Bayes-UCB Tree Search, with quantile level α(s) = 1 − (1 − α0)·e^(−(N(s)−1)/β).
- **Assumes:** Deterministic tree of depth H with finite actions, rewards in [−R_max, R_max]. Each leaf is Gaussian N(μ_θ, σ_θ²), with variance from a maximum-likelihood head or a 5-network ensemble. Independent leaf posteriors (Proposition 1). Hyperparameters: B-UCB β = 0.5; BTS α0 = 0.5, β = 3.
- **Claims:** Theorem 1: E[Regret(T)] ≤ H·R_max·√(½·|Z|·H(z*)·T). With ground-truth uncertainty, the Bayesian methods significantly outperform N-MCTS on ProcGen Maze test mazes. With learned uncertainty (MLE or ensemble) the estimates were not accurate enough to beat N-MCTS. BTS still beats N-MCTS with up to 20% error added to the ground-truth uncertainty. On Leaper, BTS beats N-MCTS without ground truth and exceeds 85% success with it (the paper's wording).
- **Evaluation:** ProcGen Maze (150 train, 500 disjoint test mazes; IMPALA net, N-MCTS annotator); Leaper (100 train, 100 test, k = 25 steps).
- **Code:** https://github.com/nirgreshler/bayesian-online-planning (license not checked)
- **Fit:** partial. The warning is useful: learned uncertainty was too poor to help on Maze. The method assumes deterministic dynamics and independent leaves, and our draw order is hidden, so it would need the random outcomes handled first.

---

### A Cure for Pathological Behavior in Games that Use Minimax (1985; arXiv 2013)
- **Link:** https://arxiv.org/abs/1304.3444 · **Venue:** UAI 1985 (arXiv posting 2013) · **Cited by:** not checked · **Read:** abstract only (the full text is a PDF, which I did not open; the ar5iv route redirected to this page)
- **Problem:** Deeper minimax search can make play worse ("searching deeper decreases the probability of making a correct move", quoted from the abstract).
- **Method:** Abramson's explanation: pathology comes from assuming win and loss nodes sit at uniform depth. The cure is a new evaluation function that recognises increasing densities of forced wins at deeper levels.
- **Assumes:** Two-player game tree with win and loss states and an evaluation function at the leaves. The game is not named on the abstract page.
- **Claims:** As stated on the page: the original evaluation function gets less likely to force wins as depth grows, which the paper says predicts the pathology. The new function shows no pathology, though it recognises fewer mid-game wins than the theoretical minimum predicts. No numbers on the page.
- **Evaluation:** Not on the abstract page.
- **Code:** none found
- **Fit:** partial. The cure fits the case where deep search repairs mechanics the value function gets wrong, since it puts the fix in the evaluation. But the claims are unquantified here and the game is not named.

---

### Avoiding Game-Tree Pathology in 2-Player Adversarial Search (2018)
- **Link:** DOI 10.1111/coin.12162 (page reached at https://cris.iucc.ac.il/en/publications/avoiding-game-tree-pathology-in-2-player-adversarial-search/) · **Venue:** Computational Intelligence 34(2), 542–561 · **Cited by:** not checked · **Read:** abstract only (full text behind the DOI, not opened)
- **Problem:** Lookahead pathology ("deeper game-tree search results in worse play") is more common than previously thought: the page says every game has locally pathological sections when both players can win.
- **Method:** Modify minimax to detect these local pathologies and cut off the search there.
- **Assumes:** Two-player zero-sum games where both players can win. The local-pathology detection is game-specific per the abstract.
- **Claims:** The abstract says it gives better decision accuracy than standard minimax, including on Kalah. No numbers on the page.
- **Evaluation:** Kalah, plus other games per the paper (not on the abstract page).
- **Code:** none found
- **Fit:** partial. The cut-off rule is close to our finding that falling back to the shallow choice where the deep tree is cut gains. But the detection is for minimax and game-specific, and the claims are not quantified on the page.
