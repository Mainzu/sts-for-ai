# Stochastic MCTS and expectimax with learned values: cards

Angle: MCTS and expectimax with chance nodes and a learned value; Stochastic
MuZero; AlphaZero variants for stochastic games; chance-node sampling
(sparse sampling, progressive widening); how many chance samples are enough.

Cited-by counts were not checked for these papers (no per-paper lookup was run).

### Planning in Stochastic Environments with a Learned Model (2022)
- **Link:** https://openreview.net/forum?id=X6D9bAHhBQ1 · **Venue:** ICLR 2022 (spotlight) · **Cited by:** not checked · **Read:** abstract
- **Problem:** Plan with a learned model when the environment is stochastic, which MuZero's deterministic model cannot do.
- **Method:** Learns afterstate dynamics and a chance-outcome distribution (a VQ-VAE variant with a fixed codebook of one-hot vectors), then runs a stochastic tree search with chance nodes over the learned model.
- **Assumes:** Discrete chance outcomes learned from experience; the chance encoder is trained, not read from the simulator. Abstract does not state the outcome count.
- **Claims:** "matched or exceeded the state of the art" on 2048 and backgammon, and kept MuZero's Go performance. No numbers in the abstract.
- **Evaluation:** 2048, backgammon, Go (per abstract). Full text was not reachable as PDF from the scout.
- **Code:** none found (OpenReview page lists no repository).
- **Fit:** partial. Chance nodes plus a learned value is the right shape, but it learns the chance model, which a perfect simulator makes unnecessary, and it gives no sample-count result.

### Learning and Planning in Complex Action Spaces (2021)
- **Link:** https://arxiv.org/abs/2104.06303 (full text read at https://arxiv.org/html/2104.06303) · **Venue:** ICML 2021 (PMLR 139) · **Cited by:** not checked · **Read:** full text
- **Problem:** MuZero's search enumerates every action, which does not scale to large or continuous action sets.
- **Method:** At each expansion, draw K actions from a proposal β (π with optional noise); PUCT uses (β̂/β)·π in place of π; the policy is trained by KL to the sample-based improved policy.
- **Assumes:** Discrete, continuous or structured actions; a proposal with wide support; an action-independent improvement operator. The paper uses deterministic transition models and notes stochastic transitions could be sampled too. Its theory is asymptotic (K → ∞, central-limit approximation).
- **Claims:** Go (362 actions): K ∈ {15, 25, 50, 100}; "K = 50 closely" approaches the MuZero baseline, trained at 400 sims vs 800. Ms. Pacman (18 actions): K = 2 insufficient, K = 3 "rapidly approaches" baseline. DM Control humanoid.run (21-D): K = 3 sufficient, no gain beyond K = 10. Pixel DMC Table 2: finger.spin 986.38 vs Dreamer 498.88. Real-World RL: Sampled MuZero is lower on Hard Quadruped (348.09 vs 351.56) and Hard Humanoid (1.19 vs 1.40).
- **Evaluation:** Go 19×19, Ms. Pacman, DeepMind Control (state and pixels), CMU Humanoid, Real-World RL suite.
- **Code:** none found.
- **Fit:** partial. The only sample-count data here is for actions, not chance outcomes, and transitions are deterministic. It is still the clearest evidence that a few sampled options can match a full enumeration.

### Monte Carlo *-Minimax Search (2013)
- **Link:** https://arxiv.org/abs/1304.6057 (full text read at https://arxiv.org/html/1304.6057) · **Venue:** arXiv (2013) · **Cited by:** not checked · **Read:** full text
- **Problem:** How to handle chance nodes in MCTS and *-minimax for turn-based, stochastic, zero-sum games with perfect information. The authors target densely stochastic games.
- **Method:** At a chance node, sample c outcomes with replacement and average them equally. Variants add Star1/Star2 pruning (star1ss, star2ss); with pruning off this is expectimax with sparse sampling (expss). Also uses double progressive widening, with outcome limit k = ⌈C·v^α⌉.
- **Assumes:** Two-player zero-sum, bounded utilities, perfect information; a simulator that can sample chance outcomes. Leaf values come from an evaluation function (no learned value in the paper).
- **Claims:** Theorem 1: P(|V̂_d(s) − V_d(s)| ≤ λd) ≥ 1 − (2c|A|)^d · exp{−λ²c / (2v_max²)}, for sampling with replacement only; the bound grows exponentially in depth d. Pig MSE: mcts 78.7, expss 95.3, Star2 87.9. Budget 200 ms per move. star2ss beat Star2 85.0% in Can't Stop. Sample widths used for expss: Pig 20, EWN 1, Can't Stop 25, Ra 5.
- **Evaluation:** Pig, EinStein Würfelt Nicht!, Can't Stop, Ra; 5000 matches each for Pig and EWN, 2000 each for Can't Stop and Ra, seats swapped.
- **Code:** none found.
- **Fit:** good for the sampling theory and the sample-count question, partial overall. It is two-player, the bound is loose at our depths, and it has no learned leaves. Its Pig and Can't Stop results are the closest chance-heavy benchmarks here.

### Power Mean Estimation in Stochastic Monte-Carlo Tree Search (2024)
- **Link:** https://arxiv.org/abs/2406.02235 (full text read at https://arxiv.org/html/2406.02235; first ~100k of 140k characters read) · **Venue:** arXiv (2024) · **Cited by:** not checked · **Read:** full text
- **Problem:** The averaging backup in UCT underestimates the optimal value in stochastic settings; max backups overestimate.
- **Method:** Stochastic-Power-UCT: each node's value is a power mean of its action Q-values, V̂ = (Σ_a (T_a/T)·Q_a^p)^(1/p), with p ≥ 1. p = 1 is plain averaging. Selection bonus C·T^(b/β)/T_a^(α/β).
- **Assumes:** Discounted MDP-style single-agent stochastic problems, γ = 0.99; budgets from 2^9 to 2^18 simulations per step; no learned value.
- **Claims:** Theorem 3: |E[V̂_n(s0)] − Ṽ(s0)| ≤ O(n^(−1/2)). FrozenLake 4×4, 16384 sims: UCT 0.27±0.02, p = 2 0.37±0.02; at 262144: UCT 0.44±0.02, p = 2 0.47±0.02. Taxi 16384: UCT 1.66±0.83, p = 2 2.94±0.95. Paper says p = 2 was best in the stochastic tasks.
- **Evaluation:** SyntheticTree (depth 1–4, branching 2–16, Gaussian noise σ = 0.5); FrozenLake 4×4 and 8×8; Taxi. Metric is discounted total reward (1000 runs; 20 for Taxi).
- **Code:** none found.
- **Fit:** partial. It gives a backup rule for stochastic nodes that needs no chance sampling model, but the tests are single-agent grid worlds and reward, not win rate, with no card content.

### Learning to Play Stochastic Two-player Perfect-Information Games without Knowledge (2023)
- **Link:** https://arxiv.org/abs/2302.04318 (full text read at https://arxiv.org/html/2302.04318) · **Venue:** arXiv (2023) · **Cited by:** not checked · **Read:** full text
- **Problem:** Zero-knowledge self-play for stochastic two-player perfect-information games, extending Descent.
- **Method:** Two approaches. (1) Determinization: sample one chance realization per self-play match, fix chance outcomes once resolved, and train on chance states with values from the chosen branch. (2) Descent Expectiminimax: best-first end-game simulations where chance nodes sample the next state and values back up as max, min or probability-weighted averages. Planning at play time is Expectiminimax with a value-only network.
- **Assumes:** "Stochastically normalized" games (a chance node's children are not chance nodes); the simulator can control random outcomes (determinization); the learner receives chance probabilities. Convergence to the optimal stochastic strategy is not guaranteed.
- **Claims:** Round-robin win rates: Descent Expectiminimax 53.9% (C.R. 0.7%), Expectiminimax 48.8% (C.R. 0.7%), Descent with Determinization 47.3% (C.R. 0.7%). Descent Expectiminimax vs Polygames: 57.3% with depth heuristic (C.R. 0.1%), 55.6% without.
- **Evaluation:** EinStein würfelt nicht! on a 5×5 board, six pieces per side, six-sided die (Ludii implementation). 30 days training per learning process; evaluation 1.5 s per action.
- **Code:** not stated in the text; none found.
- **Fit:** good for the structure (learned leaf value inside expectiminimax, chance handled by sampling), partial for scale. It is two-player and one game, and it needs a stochastically normalized game, so a card draw followed by a card play must be arranged so chance nodes do not chain.

### Improving Hearthstone AI by Combining MCTS and Supervised Learning Algorithms (2018)
- **Link:** https://arxiv.org/abs/1808.04794 (full text read at https://ar5iv.arxiv.org/html/1808.04794) · **Venue:** arXiv (2018); IEEE CIG 2018 related · **Cited by:** not checked · **Read:** full text
- **Problem:** Hearthstone hides cards in hand and deck order and has random outcomes; can supervised models make MCTS stronger and more efficient?
- **Method:** A value net (256-128-64, tanh; 750-input state; softmax win probabilities) cuts rollouts after at least 20 steps and at turn end; its win probability is backed up in the tree. Hidden information handled with an information-set transposition table and a determinized start each iteration (PIMC/ISMCTS mix). Chance nodes excluded: each move's random outcomes are averaged dynamically.
- **Assumes:** A custom C++ simulator with 483 cards, two fixed decks (ZooWarlock vs CubeWarlock), 0.5 s and 1 s per move. Card embeddings are 10-dim word2vec-style vectors learned from card text, so the net depends on a fixed card set. Labels are game winners from bot self-play.
- **Claims:** At 0.5 s, value net alone beat plain MCTS 82.0% as P1 (500 games); value net plus board solver 78.4%. At 1 s: 72.9%, 76.0%, 71.6% for the same configs. Validation accuracy 0.775 (P1) and 0.794 (P2). Plain MCTS beat MCTS-baseline 73.5% as P1 at 0.5 s. Hardware not given.
- **Evaluation:** 500 games per config, ZooWarlock vs CubeWarlock; human matches small and mixed.
- **Code:** none stated.
- **Fit:** good for the hidden-order, learned-leaf-value setting and for the time-budget effect (value net helps more at 0.5 s). Breaks the "no fixed card list" rule: the net and embeddings are built on a fixed 483-card set, and chance is not searched as chance nodes.

### Policy Improvement by Planning with Gumbel (2022)
- **Link:** https://openreview.net/forum?id=bERaNdoegnO (PDF: https://openreview.net/pdf/4f2c0c813d0fbe127329c69b1ba216fbcd95d52c.pdf, not read) · **Venue:** ICLR 2022 (spotlight) · **Cited by:** not checked · **Read:** abstract
- **Problem:** AlphaZero can fail to improve its policy when not every root action is visited, which happens at small simulation budgets.
- **Method:** Sample actions without replacement (Gumbel) and use the resulting policy-improvement rule in place of AlphaZero's heuristic action selection, at the root and in the tree. Gumbel AlphaZero and Gumbel MuZero.
- **Assumes:** Discrete action sets; deterministic environments in the reported experiments; the abstract gives no chance-node handling.
- **Claims:** Matches the state of the art on Go, chess and Atari, and "significantly improve[s] prior performance when planning with few simulations." No numbers in the abstract.
- **Evaluation:** Go, chess, Atari (per abstract).
- **Code:** none listed on the OpenReview page.
- **Fit:** partial. Its target is the low-simulation regime our CPU budget implies, but it samples actions, not chance outcomes, and the abstract has no sample counts.

### On Reinforcement Learning for the Game of 2048 (2022)
- **Link:** https://arxiv.org/abs/2212.11087 (PDF https://arxiv.org/pdf/2212.11087 not read) · **Venue:** arXiv (PhD dissertation, Hung Guei; v2 Jan 2023) · **Cited by:** not checked · **Read:** abstract
- **Problem:** Reinforcement learning and game-tree search for 2048, a single-player puzzle with random tile spawns.
- **Method:** Optimistic temporal-difference learning with n-tuple networks; also compares MCTS and deep RL.
- **Assumes:** Single-player, stochastic spawns; the agent uses an n-tuple value table on board features.
- **Claims:** The abstract reports an average score of 625,377 and a 72% rate of reaching the 32768 tile for the optimistic-TD program. No conditions on sample counts in the abstract.
- **Evaluation:** 2048 (per abstract).
- **Code:** none linked on the arXiv page.
- **Fit:** partial. A single-player stochastic game with learned values and afterstates, which matches our single-player shape, but no card content and no chance-sample study in the abstract.
