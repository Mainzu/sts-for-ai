# Selective search: where to spend computation (cards)

Angle: metareasoning and value of computation, learned or adaptive stop gates
for search, anytime search, and ranking-and-selection (OCBA) for picking among
noisy options. 8 papers opened, all from full text.

### Learning to select computations (2017, rev. 2018)
- **Link:** https://arxiv.org/html/1711.06892 · **Venue:** arXiv (layout in UAI style; venue not named on page) · **Cited by:** not checked · **Read:** full text
- **Problem:** Choosing which computations to run is central to limited-resource decisions, but rational metareasoning is intractable and no accurate, scalable method existed for general metalevel MDPs.
- **Method:** Bayesian metalevel policy search (BMPS). The value of a computation is a weighted mix of three features (myopic VOI, value of perfect information, subset VPI) minus the computation cost. The policy runs the highest-value computation and stops when no computation has positive estimated value. Weights are tuned by Bayesian optimization.
- **Assumes:** The agent has an exact model of its metalevel MDP, including its own computing architecture (flagged by the authors as a limitation). Stochastic Bernoulli outcomes with Beta beliefs, plus a deterministic tree variant. Fixed cost λ per computation. Inputs are the belief state (Beta parameters) and the candidate computation.
- **Claims:** "BMPS was at most 5.19% below the optimal policy" on stopping (largest gap at λ = 0.001, t(2999) = 3.75, p = 0.0002; not significant for costs above 0.0025). "BMPS was 20.3% better than meta-greedy on average." Bernoulli metalevel probability model: BMPS 0.6535 vs optimal 0.6596 (99.1%), DQN 0.58, meta-greedy 0.60. Bernoulli tree, heights 2 and 3: BMPS 0.367 vs optimal 0.373 (98.4%). Trained on under 20% as many episodes as the DQN.
- **Evaluation:** (1) stop-or-continue on a binary prediction task, horizon 30; (2) Bernoulli probability model, 2 to 5 options, horizon 25, costs 10⁻⁴ to 10⁻¹; (3) Bernoulli metalevel tree, heights 2 to 6, costs 2⁻⁷ to 2⁰; (4) tornado evacuation, T = 24 h, k ∈ {10, 30} cities.
- **Code:** none found
- **Fit:** partial. It gives a learned, cheap stop-or-continue rule with a tuned cost weight, which fits the gate idea. But it needs an exact model of the computation's effect on the decision (the belief over values), and its tests are bandit and tree toys, not card games.

### Search as Computation Allocation (2026, arXiv 2607.27871)
- **Link:** https://arxiv.org/html/2607.27871 · **Venue:** arXiv preprint (Tuisov, Technion); no peer review listed · **Cited by:** 0 · **Read:** full text
- **Problem:** Search procedures like MCTS are "terminally evaluated": internal computations have no direct payoff and matter only through the final decision. Which computation to run next is the question.
- **Method:** A metalevel MDP with actions (computations, plus stop) and Bellman equations for three objectives: fixed budget, priced cost (E[L + λK]), and exact certificate. Derives myopic and dynamic value of computation, and gets UCT by localizing the root decision and applying a Hoeffding optimism approximation (score Q̂ + √(κ log N(s) / (2N(s,a)))). Also gives a weighted A* ordering f_w = g + w·h.
- **Assumes:** Finite horizon, finite computation and observation spaces; a posterior or predictive model for unperformed computations is needed. Discrete loss for the entropy equivalence; bounded loss for the information bound.
- **Claims:** Theoretical only. Log loss: VOC₁(c | ℋ) = I(Z; Y_c | ℋ). Information bound: VOC₁ ≤ L_max · √(I/2). Divergence example: ratio of information-selected value to maximum is ε/(2q). No experiments.
- **Evaluation:** None. Instantiations (pure-exploration bandits, MCTS, heuristic graph search) are analytic only.
- **Code:** none found
- **Fit:** partial. It gives the theory for why a one-step (myopic) value can pick the wrong computation, and that matters for the 2-turn vs 1-turn gate. It has no experiments and its assumptions (a predictive model of unperformed computations) are not met by a learned value net without a model of its errors.

### MCTS Based on Simple Regret (2012)
- **Link:** https://arxiv.org/html/1207.5536 · **Venue:** arXiv preprint (Tolpin, Shimony; BGU); no peer-reviewed venue listed · **Cited by:** not checked · **Read:** full text
- **Problem:** UCT minimizes cumulative regret, but in search only the final move's choice earns reward, so simple regret is the better target.
- **Method:** Two-stage MCTS: at the root's first step of each rollout use a simple-regret rule (ε-greedy with ε = 1/2, or UCB_√·), then UCB inside the rollout (named "Alg+UCT", e.g. ½-greedy+UCT). Also a crude myopic VOI score per action used for sampling (not as a stop test).
- **Assumes:** Stationary bounded rewards (typically [0, 1]); Bernoulli arms in bandit tests; undiscounted MDP rollouts; exploration constant c = 2. The VOI estimate uses a one-more-sample myopic assumption.
- **Claims:** Mostly qualitative (plots). 32-arm bandit: ½-greedy and UCB_√· both beat UCB. Random 2-level trees (root degree 16 and 64): ½-greedy+UCT and UCB_√·+UCT give the lowest regret. Sailing domain: UCT always worse than the SR+CR variants, with the gap wider on the 10×10 lake (plots use 397 and 1,585 rollouts). No exact numbers in text.
- **Evaluation:** Bernoulli bandits (32 arms, 10,000 experiments); random 2-level max-max trees (16 and 64 root arms); sailing 6×6 and 10×10 lakes. No board games; computer Go is listed as future work.
- **Code:** none found
- **Fit:** partial. It shows that a root-only selection rule can beat UCT when the budget is small, which bears on how to spend a fixed search budget. But it is not a stop rule, and it uses a bandit with stationary rewards, not a learned value net.

### Budget-adaptive allocation rule for optimal computing budget allocation (2023, rev. 2025)
- **Link:** https://arxiv.org/html/2304.02377v4 · **Venue:** European Journal of Operational Research (2025), arXiv preprint version · **Cited by:** not checked (OpenAlex shows 1 for the EJOR record) · **Read:** full text
- **Problem:** Fixed-budget ranking and selection: pick the design with the smallest mean, maximizing probability of correct selection (PCS) under a total sample budget. The asymptotic OCBA rule ignores the budget size, which the authors say hurts at small budgets.
- **Method:** Approximates PCS with a Bonferroni lower bound (APCS), concave so the problem is convex. Linearizes the optimality conditions to get a closed-form, budget-dependent allocation. Two sequential forms: FAA (total budget fixed in the rule) and DAA (rule anchored to the next replication, recommended unless only final PCS matters). Each sample goes to the most "starving" design.
- **Assumes:** Normal sampling (non-Gaussian outputs use batches as single samples); independent samples, no common random numbers; unique best design; variances bounded away from 0; mean gaps bounded below by δ̲ > 0; k ≥ 3; sample means and variances plugged in.
- **Claims:** Empirical PCS (Table 3). Example 1 (10 designs): budget 50, OCBA 0.466, AOAP 0.492, FAA 0.474, DAA 0.473; budget 1000, OCBA 0.950, FAA 0.967, DAA 0.969. Example 3 (50 designs): budget 200, OCBA 0.356, AOAP 0.429, FAA 0.383, DAA 0.382; budget 5000, FAA 0.970, DAA 0.974, OCBA 0.947. Example 6 (facility location, 10 alternatives): budget 40, OCBA 0.501, FAA 0.504, DAA 0.502; budget 800, OCBA 0.959, DAA 0.976. Runtime (Ex. 4): AOAP 59.270 s, FAA 3.352 s, DAA 3.436 s. AOAP is stronger at the start in several examples.
- **Evaluation:** Six examples: 10 designs (budgets 50 to 1,000), 10 designs with decreasing variances (50 to 3,000), 50 designs (200 to 5,000), 500 designs (6,000 to 40,000), 10,000 designs (600,000 to 1,200,000), facility location with 10 alternatives (40 to 800). Compared with equal allocation, OCBA, AOAP, FBKT. MATLAB R2022b. 10⁵ macro-replications (Ex. 1 to 3), 10⁴ (Ex. 4 to 6).
- **Code:** https://github.com/Haowei-Wang/Budget-adaptive-rule-for-OCBA (license not checked)
- **Fit:** good for the "pick best of a few noisy options" part. It gives small-budget allocation rules with PCS numbers, and the normal and independence assumptions need checking against sim-noise in a fight. It does not handle a decision that is tree-structured or a learned value with bias (the value net's error is not noise).

### Selecting Computations: Theory and Applications (2012, arXiv 1207.5879)
- **Link:** https://arxiv.org/html/1207.5879 · **Venue:** arXiv preprint (Hay, Russell, Tolpin, Shimony); no venue named · **Cited by:** 51 (per OpenAlex) · **Read:** full text
- **Problem:** Search approximates decisions by simulating action sequences; the metalevel question is which simulations to run. Cast as a Bayesian selection problem, argued to fit better than the bandit framework of UCT.
- **Method:** Metalevel problem as a countable-state MDP with a terminal stop-and-act state. Myopic policy (at most one more computation; "tends to stop too early"), blinkered policy (for independent actions), VOI-based sampling with distribution-free VOI bounds from Hoeffding's inequality, and hybrid tree search: VOI sampling at the root and UCT below. Sampling stops when VOI falls below the sampling cost; unused budget is redistributed to later states.
- **Assumes:** Bounded utilities (WLOG [0,1]); fixed cost c > 0 per computation; Bernoulli sampling with Beta priors; blinkered policy needs independent actions; VOI bounds assume i.i.d. samples and expected selection equals sample mean.
- **Claims:** One-armed Bernoulli: the policy performs at most λ(1−λ)/c − 3 computations, at most 1/(4c) − 3 (Theorem 10). Optimal policy computable in O(1/c²); blinkered in O(D/c²) with D = 129 grid points, independent of the number of arms. Flat selection (25 Bernoulli arms): blinkered "significantly outperforms all others" on regret; no exact values in text. Go 9×9 (Pachi-based UCT, 5,000 to 15,000 samples per ply, 1,000 repeats): at stopping threshold 10⁻⁶, the VOI-aware policy "reaches the winning rate of 64% for 10000 samples per ply". The text has a sample-count typo that the card does not resolve.
- **Evaluation:** Bernoulli selection problems (25 arms, 1,000 and 10,000 trials, budgets 200 to 2,000); 9×9 Go with a modified Pachi engine.
- **Code:** none found (authors modified Pachi, no link in text)
- **Fit:** good. It has a stop rule (VOI below sampling cost) on a game tree with a fixed per-computation cost, and a Go result with a win rate. It assumes a bounded-utility model with Bernoulli beliefs; a value net would need its error modelled, and its tests are not card games.

### Static and Dynamic Values of Computation in MCTS (2020, UAI 2020; arXiv 2002.04335)
- **Link:** https://arxiv.org/html/2002.04335 · **Venue:** UAI 2020, PMLR v124 pp. 31–40 (per search results; page itself does not name it) · **Cited by:** not checked · **Read:** full text
- **Problem:** Which simulations to run in MCTS. UCT is heuristic; existing computation-value methods are myopic (one computation, root actions only).
- **Method:** Static value φn (value of an action if the agent takes n steps with no new computation) and dynamic value ψn (assumes all uncertainty is resolved later). Greedy VOC(φn) and VOC(ψn) policies pick the computation with the highest value and stop when all VOC values are zero. Shows ψn ≥ E[φn] ≥ φn, and that the earlier myopic VOC′ can stop too early.
- **Assumes:** Finite MDP, discount γ in [0,1) (experiments use γ = 1, zero immediate rewards within n steps); known dynamics; Gaussian prior on Q* with known parameters; Normal observation noise with known parameters; UCT rollouts treated as i.i.d. Deterministic-transition approximation via a Normal bound, with the computation chosen by the sensitivity ∂λ/∂n.
- **Claims:** Asymptotic optimality with infinite budget (Prop. 3). Stated only qualitatively: VOC(φn)-greedy is best on correlated bandit trees; VOC(ψn)-greedy matches Thompson sampling at large budgets on peg solitaire. No exact regret numbers in text (they are in figures).
- **Evaluation:** Bandit-trees: complete binary tree of depth 7 (128 arms), stochastic transitions (0.75 to the chosen subtree); correlated arms (RBF kernel scale 1, noise N(0, 0.1), 10k seeds) and uncorrelated arms (means U(0.45, 0.55), noise N(0, 0.01), 5k seeds); budget max 128. Peg solitaire: 4×4 board, 9 random pegs, pegs remaining over 200 seeds. Baselines: UCT, Hay et al. VOI, Bayes UCT, DNG-MCTS.
- **Code:** none found
- **Fit:** partial. It is a principled non-myopic stop-and-choose rule with known-model and Gaussian assumptions. Those do not hold for a learned value net unless its uncertainty is modelled. Its tests are small synthetic trees, not card combat.

### Spending Thinking Time Wisely: Accelerating MCTS with Virtual Expansions (2022, arXiv 2210.12628)
- **Link:** https://arxiv.org/html/2210.12628v1 · **Venue:** arXiv preprint (Ye, Abbeel, Gao); NeurIPS 2022 per search results, not confirmed on page · **Cited by:** not checked · **Read:** full text
- **Problem:** MCTS in MCTS-based RL is expensive, and vanilla MCTS uses the same fixed budget N for easy and hard states.
- **Method:** Virtual MCTS (V-MCTS). After k iterations, the remaining N − k expansions run UCT on the fixed Q values with no network calls, giving a virtual policy π̂_k. Termination rule (VET-Rule): stop once k ≥ rN and ||π̂_k − π̂_{k/2}||₁ < ε, then return π̂_k. The gap between two virtual policies is the difficulty signal.
- **Assumes:** Finite action set; rewards bounded in [0,1]; prior on the best empirical action at least 1/|A|. Built on EfficientZero (MuZero variant), so it uses a learned network per state. Two-player Go with Tromp-Taylor rules and komi 6.5, plus five Atari games.
- **Claims:** Go 9×9 (200 games over 3 runs, vs GnuGo level 10): MCTS (N=150) 75% ±3.0%, average budget 150; DS-MCTS 60% ±4.0%, budget 97 ±12.5; V-MCTS (r=0.2, ε=0.1) 71% ±4.7%, budget 76 ±10.8. Time per move: V-MCTS 0.12 s, GnuGo 0.18 s, MCTS over 0.2 s. Atari (100 seeds, N=50 MCTS): Pong 19.7 ±1.6 vs V-MCTS 18.8 ±2.8 (budget 13.3 ±0.6); Breakout 410.7 ±15.1 vs 372.8 ±18.3 (15.7 ±0.6); Qbert 14495.8 ±683.9 vs 11476.6 ±978.2 (16.3 ±1.2). Paper says under 50% of search on Go, over 60% saving on Atari.
- **Evaluation:** 9×9 Go vs GnuGo level 10 (200 games × 3 runs); five Atari games at the 100k-step setting (100 seeds × 3 runs).
- **Code:** https://github.com/YeWR/V-MCTS.git (license not checked)
- **Fit:** good. It is a learned-net search with a cheap stop test that needs no extra model: stop when the policy stops moving. Win rate drops 4 points for about half the budget on Go. Its tests are Go and Atari, not card combat, and the stop threshold (ε) needs tuning.

### Planning and Acting While the Clock Ticks (2024, arXiv 2403.14796)
- **Link:** https://arxiv.org/html/2403.14796v1 · **Venue:** arXiv preprint (Coles, Karpas, Lavrinenko, Ruml, Shimony, Shperberg); no venue named · **Cited by:** not checked · **Read:** full text
- **Problem:** Temporal planning needs a complete plan before any action runs, which fails under tight deadlines. Concurrent planning and execution lets actions start before planning ends, without dispatching in the past and while meeting wall-clock deadlines.
- **Method:** Extends the situated temporal planner (Shperberg et al. 2021, built on OPTIC's forward search) to dispatch during search. CoPEM is a metareasoning POMDP, intractable in general; the authors solve a one-step-lookahead case. Dispatch rule: dispatch the best explored candidate when its estimated success probability beats the not-dispatch probability by a dispatch threshold (0.25, 0.1, or 0.025 tested); a subtree focus threshold is set at half of that.
- **Assumes:** Heuristic forward search where node expansions are the time unit; CPU speed set by an expansions-per-second parameter; success probability linked to log-probability of failure; runtime and deadline distributions estimated during search; known induced deadlines, independence, perfect-information measurements in theory (relaxed in practice); deterministic action durations; minimum of 10 expansions.
- **Claims:** No exact counts in text. Figure 1 (RCLL, 1 to 3 robots): the dispatch advantage is large on a slow CPU and shrinks as the CPU gets faster; with a fast enough CPU, the no-dispatch baseline may win. Abstract says the approach "outperforms situated temporal planning" under strong time pressure. Turtlebot results are in supplementary material (not read).
- **Evaluation:** Robocup Logistics League planning problems (1, 2, 3 robots, varying expansions per second); Turtlebot office-delivery problems (supplementary). Baseline: the planner with default parameters ("nodisp").
- **Code:** none found
- **Fit:** partial. It shows an act-or-keep-searching rule with a success-probability threshold and a measured time model, which fits the ponder-or-act angle. But it is for temporal planning with deadlines, not for choosing among card plays, and it has no direct value-net or game results.

---

## Not opened (fetch failed or blocked)

- Winands et al., "Time Management for Monte-Carlo Tree Search in Go" (Maastricht PDF): returned unreadable binary through WebFetch. Not carded.
- Deep imagination, Sci Rep 2022 (nature.com, doi 10.1038/s41598-022-13862-2): redirected to a publisher login page. Not carded.
- Gu, Ruml, et al., "When to Commit to an Action in Online Planning and Search" (SoCS 2022, doi 10.1609/socs.v15i1.21755): ojs page blocked by Anubis bot check. Not carded; the arXiv follow-up above cites it.
