### Improve Agents without Retraining: Parallel Tree Search with Off-Policy Correction (2021)
- **Link:** https://arxiv.org/abs/2107.01715 (full text read at https://arxiv.org/html/2107.01715) · **Venue:** arXiv preprint, v3 revised 5 Feb 2023 (NeurIPS 2021 named in a search snippet, not on the page) · **Cited by:** not checked · **Read:** full text
- **Problem:** Tree search guided by a pre-trained value function can score below the original agent, even with exact future states and rewards.
- **Method:** BCTS adds a penalty of γ^d(B_e − B_o) to root actions whose first step leaves the original policy's choice, where B_e and B_o come from an Extreme Value analysis of noisy value estimates. The penalty is estimated from Bellman errors at depths 0 and 1 and multiplied by a swept constant. Batch-BFS runs the search breadth-first on a GPU.
- **Assumes:** Deterministic transitions (Atari is near-deterministic). Discrete actions and a forward model. Value noise is normal with σ_o < σ_e. Theorems use A^(d−1) ≫ 1. Rainbow agents pre-trained on 50M frames.
- **Claims:** Vanilla tree search often lowers scores, with the largest drop at d=1 and the most in Frostbite (18 actions). BCTS at d=4 "more than doubles" the score in several games. BeamRider is about 5× better at d=4. Asteroids is the exception, where vanilla search is about as good as BCTS. Bellman error on the original policy's actions is about 1.5× lower in Breakout and 2× lower in Frostbite. BCTS improves monotonically with depth in all tested games except Asteroids. The paper notes the bias gap grows roughly as √(d log A) while the γ^d factor shrinks the correction. The DQN-with-search versus Rainbow table has an ambiguous column order in the extracted text, so check it against the PDF.
- **Evaluation:** Atari (five games, including Asteroids, Breakout, Frostbite, BeamRider) with pre-trained Rainbow, 200 test episodes, depths 1 to 4.
- **Code:** https://github.com/NVlabs/bcts is linked in the abstract. The paper's checklist says the code was not released at submission. Release status not verified.
- **Fit:** partial. It shows depth hurting a learned value function through extreme-value error on the states it reaches. It breaks the fit in three ways: deterministic transitions, a discrete-action setting, and a fix that penalises actions which depart from a trusted policy, not chance-node sampling.

### Empirical Error Bounds for Monte Carlo Search (2021)
- **Link:** https://arxiv.org/abs/2106.04715 (full text read at https://arxiv.org/html/2106.04715) · **Venue:** arXiv preprint, v2 (cs.AI) · **Cited by:** not checked · **Read:** full text
- **Problem:** Theoretical error bounds for Monte Carlo action-value search depend on the true values, which are unknown during search. The paper asks for error bounds from observed simulation values only.
- **Method:** A general finite-sample bound (Hoeffding style, with an empirical Bernstein variance bound). A tighter CLT bound with a Berry-Esseen penalty. Student-t error estimates (estimates, not guaranteed bounds). Both bound types cover over-estimating an action's value by more than ε, and choosing an action worse than another by more than ε.
- **Assumes:** Bounded returns. Search is convergent, so its expected estimate equals the search policy's value. Arithmetic mean estimators. In MDPs, a leaf baseline estimator with bias ζ (zero in bandits). CLT bounds need approximately normal estimates, which the paper says do not hold for non-stationary UCT.
- **Claims:** General bounds held in all tested configurations, and CLT bounds held once enough samples were drawn. Both decay roughly exponentially with sample count and are loose at low counts. CLT bounds were tighter. For UCT on the grid world the bounds were "significantly looser" at high sample counts, which the authors attribute to early shallow searches and non-stationary sampling. No numeric bound values appear in the extracted text.
- **Evaluation:** 10-armed Gaussian bandit (means uniform on [−1, 1], variance 0.5, ε = 0.1, softmax temperature 10). 10×10 grid-world MDP with rewards 10 and 3 at goals, −10 and −5 at penalties, intended-direction probability 0.7, γ = 0.95. Simple MC at depths 5, 10, 25 and UCT with max depth 25, c = 1.0, using MCTS.jl in Julia with POMDPs.jl.
- **Code:** none found. The paper says source code is in supplementary materials; no repository link or licence on the page.
- **Fit:** partial. It gives a way to test whether a max over sampled values is reliably better, which bears on the winner's-curse question. It does not address pathology or chance nodes, and the tooling is Julia.

### Heuristic Search as Evidential Reasoning (1989; arXiv 2013)
- **Link:** https://arxiv.org/abs/1304.1509 · **Venue:** UAI 1989, pp. 152–161 (posted to arXiv 27 Mar 2013) · **Cited by:** not checked · **Read:** abstract
- **Problem:** Resource-limited problem solving, where traditional heuristic search spends too many expansions.
- **Method:** BPS, a Bayesian problem solver that uses probabilistic inference and decision-theoretic control.
- **Assumes:** Problem solving with a probabilistic model of the heuristic. The page does not state the error model.
- **Claims:** BPS "makes better decisions" than the best existing algorithm on the Eight Puzzle, after "a few hundred node expansions versus several million." No depth-versus-error result.
- **Evaluation:** Eight Puzzle only.
- **Code:** none found.
- **Fit:** poor. Its topic is inference per expansion, not deeper search hurting. Kept only as a pointer to Bayesian treatments of heuristic error.

### Avoiding game-tree pathology in 2-player adversarial search (2018)
- **Link:** https://cris.iucc.ac.il/en/publications/avoiding-game-tree-pathology-in-2-player-adversarial-search/ (abstract read; the UMD PDF at https://cs.umd.edu/~nau/papers/zuckerman2018avoiding.pdf was rejected on certificate) · **Venue:** Computational Intelligence 34(2):542–561, 2018, DOI 10.1111/coin.12162 · **Cited by:** not checked · **Read:** abstract
- **Problem:** Lookahead pathology, where deeper minimax search gives worse play. The authors argue it is not rare.
- **Method:** An error-minimizing minimax variant. It detects locally pathological sections of a tree and cuts off search there, since shallower search does better in those sections.
- **Assumes:** Deterministic two-player zero-sum games with perfect information. Both players can win in the game.
- **Claims:** The abstract gives no numbers. It says "every game should have some sections that are locally pathological" when both players can win, and that the modified procedure "improves decision accuracy compared with standard minimax."
- **Evaluation:** Kalah, described as a case where pathology is common.
- **Code:** none found.
- **Fit:** partial. The cut-off-where-shallow-is-better idea matches the depth question. It assumes deterministic minimax with no chance nodes and gives no quantitative results on the page.

### Understanding the Success of Perfect Information Monte Carlo Sampling in Game Tree Search (2010)
- **Link:** https://ojs.aaai.org/index.php/AAAI/article/view/7562 (PDF at https://ojs.aaai.org/index.php/AAAI/article/view/7562/7423 not read) · **Venue:** AAAI-10, pp. 134–140 · **Cited by:** not checked · **Read:** abstract
- **Problem:** Why perfect information Monte Carlo (PIMC) search works in imperfect-information games, given the strategy fusion and non-locality criticisms.
- **Method:** Synthetic game trees to find properties (leaf correlation, disambiguation) that make PIMC strong or weak against an optimal player. These properties are then detected in real games.
- **Assumes:** Imperfect-information games where hidden state is sampled and each sample is solved as perfect information.
- **Claims:** No numbers on the page. One finding: with disambiguation in the 0.7–0.9 range, low leaf correlation helps PIMC, because the game becomes perfect information quickly and a win remains available.
- **Evaluation:** Synthetic game trees, then real games (not named on the page).
- **Code:** none found.
- **Fit:** partial. Hidden draw order sampled, then solved to a fixed point, is the same structure as sampled outcomes at a chance node. The paper's strategy-fusion critique is the pathology to check for. Only the abstract was read.

### Lookahead Pathology in Monte-Carlo Tree Search (2022; v2 2024)
- **Link:** https://arxiv.org/abs/2212.05208 (full text read at https://arxiv.org/html/2212.05208) · **Venue:** arXiv v2 (June 2024); shorter version at ICAPS 2024 · **Cited by:** not checked · **Read:** full text
- **Problem:** Whether UCT, the usual MCTS variant, shows lookahead pathology, where more search leads to worse decisions. The authors say this had not been studied.
- **Method:** A synthetic win-loss game family. Nodes are forced or choice nodes, and a choice node flips each non-parent child with critical rate γ. The tree is grown lazily with uniform branching b. Heuristics are a perfect-heuristic theorem plus histograms from Stockfish (chess) and Edax (Othello).
- **Assumes:** Win-loss values of +1 and −1 only (no draws). Uniform branching factor. Node-budget search. Heuristic that is perfect (theorem) or built from engine evaluations.
- **Claims:** Theorem 1: with γ = 1.0, budget N nodes and c ≥ √(N³ / (2 log N)), UCT shows pathology even with a perfect heuristic. With γ = 1.0 pathology appears regardless of c, b or heuristic, and persists at depths 200 and 2000. With γ = 0.9 it is most visible at high b and high c. With γ = 0.5 it is almost absent. UCT works well at about 100 nodes and degrades at about 10k nodes. Alpha-beta is also susceptible, especially for γ ≥ 0.7. UCT shows little pathology in P-games. About 40–50% of sampled chess positions have empirical critical rates above 0.9.
- **Evaluation:** Main runs use depth 50 and 500 games per setting, over 2 values of γ, 3 branching factors, 2 heuristic models and 5 values of c. The pathology index is δ_j / δ_10, where δ_i is decision accuracy after i iterations.
- **Code:** https://github.com/npnkhoi/mcts-lp. The licence is not stated on the page.
- **Fit:** good for the budget question (the node cap effect, and why more nodes can hurt). It breaks the fit in two ways: its outcomes are win-loss, not a score or HP, and it does not cover chance nodes.

### Online Robust Planning under Model Uncertainty: A Sample-Based Approach (2025)
- **Link:** https://arxiv.org/abs/2509.10162 (full text read at https://arxiv.org/html/2509.10162) · **Venue:** arXiv preprint, v2 (posted 19 Sep 2025); no peer-reviewed venue named · **Cited by:** not checked · **Read:** full text
- **Problem:** Sparse Sampling assumes an accurate generative model. When the learned model is off, its sampled tree is wrong.
- **Method:** Robust Sparse Sampling (RSS) keeps the Sparse Sampling tree and replaces each backup with a robust one, from a convex sample-average approximation of the dual. Sparse Sampling uses C next-state samples per action to depth H, with the leaf value set to zero in this work.
- **Assumes:** Finite actions, rewards in [0, 1], an approximate model within total-variation distance ρ of the true kernel, rectangular uncertainty, and an absorbing zero-reward fail state. Known ρ.
- **Claims:** Error recursion α_d = γ(λ + α_{d−1}), so α_H ≤ (λ + γ^H)/(1−γ). Complexity is O((|A|C log C)^H) for RSS against O((|A|C)^H) for Sparse Sampling. The failure-probability union bound grows as (|A|C)^d. FrozenLake 8×8 (H = 3, C = 50, γ = 0.99, 1000 seeds): at ρ = 0.2, RSS 0.171 vs SS 0.123; at ρ = 0.5, RSS 0.127 vs SS 0.080; SS with true dynamics 0.249 ± 0.012. CartPole: RSS is worse than SS at low noise and better at high noise. The exact crossover is not given in the text. The authors note a theorem-statement gap: it drops the 1−δ probability.
- **Evaluation:** FrozenLake 8×8 and CartPole with added model noise, as above.
- **Code:** none found.
- **Fit:** partial. It is about model error in sampled trees rather than evaluator noise, but its bound shows how sampling error compounds with depth. It is a practical fallback for short horizons only; the tree grows exponentially with H.

### Sparse Sampling Algorithm for Near-Optimal Planning in Large Markov Decision Processes (2002)
- **Link:** https://mlanthology.org/mlj/2002/kearns2002mlj-sparse (abstract read; the UPenn PDF at https://www.cis.upenn.edu/~mkearns/teaching/cis620/papers/sparseplan.pdf was rejected on certificate) · **Venue:** Machine Learning 49:193–208, 2002 (IJCAI 1999 preliminary version) · **Cited by:** not checked · **Read:** abstract
- **Problem:** Near-optimal online planning in large MDPs with only a generative model, without a dependence on the number of states.
- **Method:** Sparse sampling: a randomly sampled look-ahead tree, covering a vanishing fraction of the full tree, is enough to choose near-optimal actions.
- **Assumes:** A generative model (simulator) of an arbitrary MDP, a discount factor, and a desired accuracy. Rewards bounded (not stated on the page).
- **Claims:** Per-state running time has "no dependence on the number of states" and is exponential in the horizon. The page gives no explicit sample counts or constants.
- **Evaluation:** None on the page.
- **Code:** none found.
- **Fit:** partial. It is the theory behind sampled chance nodes, and the basis of Monte Carlo *-Minimax, which is already carded. The abstract does not discuss depth hurting, and the full PDF was not read.
