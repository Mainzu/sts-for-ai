# Expert Iteration and search distillation: cards

Angle: policy improvement by search, distillation of search into a net, and when imitating a stronger search fails. 8 papers opened, all 8 from full text.

Citation counts were not checked for these papers (OpenAlex was not queried per paper), so "Cited by" is marked as not checked.

---

### Thinking Fast and Slow with Deep Learning and Tree Search (2017)
- **Link:** https://arxiv.org/abs/1705.08439 (full text read at https://arxiv.org/html/1705.08439) · **Venue:** arXiv v4 (NeurIPS 2017 poster listed in search, not verified) · **Cited by:** not checked · **Read:** full text
- **Problem:** Learn to play 9x9 Hex from nothing, with tree search doing the planning and a net doing the generalising (Expert Iteration, ExIt).
- **Method:** The apprentice net plays self-play, and an MCTS-with-RAVE expert (10,000 simulations per move) labels the states. Two policy target choices are compared: the chosen action (CAT) and the tree's visit distribution (TPT). The value head is trained on the apprentice's own Monte Carlo outcomes, not the expert's. Online variant aggregates data across iterations, like DAgger.
- **Assumes:** 2-player, deterministic, perfect information board game. Uniform default policy in MCTS. 13-layer CNN with hexagonal filters.
- **Claims:**
  - TPT vs CAT: top-1 errors 47.7% vs 47.0%, but TPT is "50 ± 13 Elo stronger".
  - ExIt vs MoHex 1.0: 75.3% vs 10k-iteration MoHex, 59.3% vs 100k-iteration MoHex, 55.6% vs 4 s/move MoHex with parallel solver. Training curves not converged, per the authors.
  - Compute: 0.3 s for 10,000 iterations (ExIt) vs 0.2 s (MoHex), on the authors' hardware.
  - Text says an apprentice can only approach its expert; the gap bounds per-iteration improvement. The authors argue targets should cover the whole move distribution, not only the chosen move.
- **Evaluation:** 9x9 Hex, against MoHex (10k, 100k, and 4 s/move) and vanilla MCTS.
- **Code:** none found (only a MoHex source link in the appendix).
- **Fit:** partial. Gives the original argument for visit-count targets over chosen-action targets, and for expert improvement. Breaks the hidden-order constraint: no chance nodes, perfect information.

---

### Monte-Carlo Tree Search as Regularized Policy Optimization (2020)
- **Link:** https://arxiv.org/abs/2007.12509 (full text read at https://arxiv.org/html/2007.12509) · **Venue:** ICML 2020 (PMLR 119; proceedings page in search, not opened) · **Cited by:** not checked · **Read:** full text
- **Problem:** AlphaZero's search heuristic (and UCT) is treated as an approximate solution to a regularized policy optimization problem; the paper uses that view to change the search and the targets.
- **Method:** Target policy π̄ = argmax over the simplex of [q·y − λ_N KL(π_θ, y)], with closed form π̄ = λ_N·π_θ/(α − q). The "All" variant combines three changes: sample real actions from π̄, select tree actions from π̄ instead of the deterministic rule, and train the prior toward π̄ with a KL loss.
- **Assumes:** Discounted MDP with learned prior and value, MuZero-style. Atari |A| ≤ 18. DM Control discretised with K = 5 bins per dimension. Low budget = N_sim 5, high = N_sim 50.
- **Claims:**
  - Ms Pacman, N_sim = 5 (8 seeds): All "significantly outperforms" MuZero (figures only, no exact scores).
  - Ms Pacman, N_sim = 50: All is marginally better; the two are comparable at N_sim ≥ 24.
  - Ablation: at N_sim = 5 the Learn change gives most of the gain; at N_sim = 50 the Search change does.
  - Table 1, pixel inputs (3 seeds), MuZero vs All: Walker-Walk 925 vs 941; Walker-Stand 959 vs 951; Walker-Run 533 vs 644; Cheetah-Run 887 vs 882.
  - The tracking bound ||π̄ − π̂||∞ ≤ (|A|−1)/(|A|+N) holds only under a constant-π̄ assumption, per the paper.
- **Evaluation:** Six Atari games (Ms Pacman, Alien, Asteroids, Gravitar, Seaquest, Beam Rider), and DM Control with pixel observations.
- **Code:** none found.
- **Fit:** partial. Gives a concrete target formula that mixes search Q-values with the prior, and reports the low-simulation regime. Breaks the hidden-order constraint: deterministic MDP, no chance nodes, no card or option ranking.

---

### Beyond Search-Imitation: Prior-Directed Exploration for Searchless Chess (2026)
- **Link:** https://arxiv.org/abs/2608.27757 (full text read at https://arxiv.org/html/2608.27757) · **Venue:** arXiv preprint, submitted 27 Aug 2026 (no peer-reviewed venue stated) · **Cited by:** not checked · **Read:** full text
- **Problem:** A searchless chess net is trained by imitating a search teacher's visit counts. Can self-play RL improve its single-pass strength past that imitation without losing exploration?
- **Method:** Starts from the frozen Chessformer base (Lc0 BT4) and fine-tunes with self-play policy gradient. The entropy bonus is replaced by a forward KL toward the base's own MCTS-distilled policy, plus an entropy-adaptive sampling temperature. Uses one-step TD(0) advantage with an EMA value target.
- **Assumes:** Searchless play at train and test time, one forward pass per position. The forward KL needs the full reference distribution over enumerable legal moves. Strength is pool-dependent, so claims are relative to the base.
- **Claims:**
  - 100k puzzle suite: base 93.85 ± 0.15%; forward-KL with adaptive temperature 94.87 ± 0.14%; entropy bonus 94.90 ± 0.14%.
  - Elo vs base (closed ladder): forward-KL adaptive +11.7 ± 8.3; forward-KL τ=1 +16.6 ± 8.3; reverse-KL +16.2 ± 8.3; entropy bonus −5.8 ± 8.3; puzzle-tuned supervised control −258.0 ± 9.1.
  - Coverage (draws to cover 95% of mass on depth-4 trajectories): about 22,000 base, about 1,400 forward-KL, about 4,100 entropy bonus, 1 unregularized self-play.
  - The authors call the gains modest and selection-inflated. Single run per cell.
- **Evaluation:** Lichess puzzle suites (10k, 100k, and a ≥2400 20k suite), mate-in-1 to 5, a closed round-robin Elo ladder, and 1,000-game head-to-head matches.
- **Code:** https://github.com/szmilosz/prior-directed-exploration (license not checked).
- **Fit:** poor. Chess, searchless, and GPU-scale. Useful only as a warning that visit-count imitation is a noisy target with covariate shift, and that tactic accuracy and playing strength can separate (the −258 Elo puzzle-tuned control).

---

### ExIt-OOS: Towards Learning from Planning in Imperfect Information Games (2018)
- **Link:** https://arxiv.org/abs/1808.10120 (full text read at https://arxiv.org/html/1808.10120) · **Venue:** arXiv v2 (no peer-reviewed venue stated) · **Cited by:** not checked · **Read:** full text
- **Problem:** Extend Expert Iteration to imperfect information, 2-player zero-sum games.
- **Method:** Online Outcome Sampling (OOS) replaces MCTS as the expert. The net is the rollout policy inside OOS. Training targets are (infoset encoding, σ_oos) pairs with a KL loss. Self-play feeds a reservoir of 32,000 games. Adam at 10⁻³.
- **Assumes:** 2-player zero-sum extensive-form games with perfect recall. The game is supplied as a program that defines the tree implicitly. Games: Leduc (288 infosets), Goofspiel 6 and 13 cards, Liar's Dice with 1 and 2 dice.
- **Claims:**
  - Goofspiel(13), iteration 500: win rates 74% (2.4) and 53% (2.6), still rising.
  - Goofspiel(13) Elo at iteration 500: ExIt-OOS 1600 ± 3.5 vs OOS with 10k simulations 1572 ± 3.7.
  - Goofspiel(6) plateaus at iteration 2500 (67% and 25%). Liar's Dice(2), iteration 1000: 66% (2.6) and 54% (2.8).
  - The text extraction does not label the win-rate columns. Check the PDF before quoting these.
- **Evaluation:** Head-to-head against Random and OOS (10k simulations), 5000 games.
- **Code:** none found.
- **Fit:** partial. The only expert-iteration paper here that handles hidden information (via information sets). Breaks the setting: 2-player zero-sum, no scripted or random environment content, and no mention of chance draws beyond the game program.

---

### BRExIt: On Opponent Modelling in Expert Iteration (2022)
- **Link:** https://arxiv.org/abs/2206.00113 (full text read at https://arxiv.org/html/2206.00113) · **Venue:** not stated (v2, April 2023) · **Cited by:** not checked · **Read:** full text
- **Problem:** Speed up approximate best responses in population-based training by putting opponent models into ExIt's search and net.
- **Method:** Net has policy, value, and opponent-model heads. The MCTS expert uses ground-truth opponent priors (BRExIt) or learned opponent models (BRExIt-OMS) at opponent-turn nodes. Visit-count targets are sharpened with temperature (τ = 1 for the first 10 moves, then 0.01). Dirichlet noise is removed because the low budget would randomise the search too much.
- **Assumes:** Two-player, fully observable, sequential zero-sum game (Connect4, 6×7). MCTS budget of 50 iterations. About 27k parameters per net. Fixed test opponents.
- **Claims:**
  - BRExIt vs ExIt: over 97% probability of improvement (PoI). BRExIt-OMS vs ExIt: over 91% PoI.
  - ExIt-OMFS (opponent models only for feature shaping) vs ExIt: 80% PoI for ExIt, so the opponent-model-without-search variant is worse.
  - Full-distribution vs one-hot targets: no significant difference in most cases. Exception: ExIt-OMFS vs the mixed opponent (p = 0.025), where one-hot was worse.
- **Evaluation:** 7 variants, 10 runs each per opponent, 48 wall-clock hours per run, on 64 CPUs, no GPU. 280 runs in total. Results as interquartile means and PoI.
- **Code:** not provided.
- **Fit:** partial. CPU-only budget matches. The points that carry over are low-budget MCTS and target sharpening, and the finding that auxiliary information hurts when it is not used inside the search. Breaks the setting: no hidden draw order, and the opponent model is a player, not a draw.

---

### Policy Learning from Self-Play with Policy Gradients and MCTS Value Estimates (2019)
- **Link:** https://arxiv.org/abs/1905.05809 (full text read at https://arxiv.org/html/1905.05809) · **Venue:** arXiv preprint (no venue stated) · **Cited by:** not checked · **Read:** full text
- **Problem:** A policy trained with cross-entropy on MCTS visit counts (as in ExIt) inherits MCTS's exploration. The authors want a policy learned from MCTS value estimates instead.
- **Method:** Tree-Search Policy Gradient (TSPG): a gradient over all actions, weighted by MCTS value estimates of successor states, not visit counts. Logits = θ_ce + θ_tspg, where θ_ce is a frozen cross-entropy policy and θ_tspg is trained. The policy is linear in state-action features, not a neural net.
- **Assumes:** Deterministic, perfect-information, 2-player board games. Treats MCTS as unaffected by θ, which the authors say is violated in practice. Self-play: 200 games per run, 1600 MCTS iterations per turn (800 for Hex 11×11), 5 seeds.
- **Claims:**
  - Table I, win % of biased MCTS vs UCT, equal budgets, shown as πce (double) vs πtspg: Breakthrough 100.0 vs 100.0; Connect 4 76.0 vs 72.0; Gomoku 28.0 vs 18.0; Hex 7×7 89.5 vs 88.5; Hex 11×11 86.5 vs 71.0 (πtspg CI 50.0–95.0); Knightthrough 76.5 vs 63.0; Othello 69.0 vs 69.0; Teeko 97.0 vs 93.8; Yavalath 100.0 vs 98.5.
  - The text says πtspg "consistently outperforms" πce standalone, but the figure values are not in the text. Table I mostly favours πce (double), which is the control with extra update steps. The two claims do not agree on their face; read the figure before relying on either.
- **Evaluation:** Nine board games (Breakthrough, Connect 4, Gomoku, Hex 7×7 and 11×11, Knightthrough, Othello, Teeko, Yavalath).
- **Code:** none found.
- **Fit:** poor. Linear policies, deterministic board games, and no chance nodes. The idea of learning from value estimates of successors, not from visit counts, is the part that might carry over.

---

### Learning and Planning in Complex Action Spaces (Sampled MuZero, 2021)
- **Link:** https://arxiv.org/abs/2104.06303 (full text read at https://arxiv.org/html/2104.06303) · **Venue:** ICML 2021 (PMLR 139; per keywords and search, not opened) · **Cited by:** not checked · **Read:** full text
- **Problem:** MuZero's search enumerates every action, which is infeasible when the action space is huge, continuous, or structured.
- **Method:** Draw K actions from a proposal β (set to the policy π, with optional temperature and Dirichlet noise). Run PUCT over only the sampled actions, with the prior corrected to (β̂/β)·π. The root visit-count distribution is the target, and the net learns it by KL. The paper argues the visit counts already correct for the sampling.
- **Assumes:** Action space size N with K ≪ N. β has wide support. Deterministic transition model. The sample-based operator is justified asymptotically (K → ∞).
- **Claims:**
  - Go (362 actions): K ∈ {15, 25, 50, 100}, 1 seed each. K = 50 "closely approaching" the all-actions baseline. No exact Elo gaps given.
  - Ms. Pacman (18 actions): K = 2 insufficient, K = 3 approaches the baseline (1 seed).
  - DM Control: main runs K = 20 (3 seeds). Humanoid run: K = 3 already enough, no gains beyond K = 10 (6 seeds). Equal or better than Dreamer on 20 pixel tasks (finger.spin 986.38 vs 498.88).
  - RWRL (3 seeds): Easy Humanoid 289.36 vs D4PG 102.92; Hard Cartpole 244.71 vs STACX 135.26. Exceptions: Hard Quadruped 348.09 vs STACX 351.56.
- **Evaluation:** Go (100 games per checkpoint, 800 simulations per move), Atari (50 simulations), DM Control and RWRL (50 simulations, 5-step returns, γ = 0.99).
- **Code:** not in the paper. A search result mentions the opendilab LightZero repo (not opened, not verified).
- **Fit:** partial. The sampling-with-correction idea fits a case where there are more options than the search can afford to visit. Breaks the setting: deterministic transitions, no chance nodes, and the win is measured on single-agent or board tasks.

---

### Policy Improvement by Planning with Gumbel (ICLR 2022)
- **Link:** https://object.cloud.sdsc.edu/v1/AUTH_da4962d3368042ac8337e2dfdd3e7bf3/ml-papers-txt/ICLR/2022/policy_improvement_by_planning_with_gumbel__15d5fc26.txt (text mirror of the ICLR paper; arXiv and OpenReview not reached, OpenReview is ruled out in sources.md) · **Venue:** ICLR 2022 · **Cited by:** not checked · **Read:** full text (from mirror)
- **Problem:** AlphaZero's root search can fail to improve its policy when it cannot visit all actions, which is common when simulations are few relative to actions (362 in 19×19 Go).
- **Method:** Sample m = min(n, 16) root actions without replacement (Gumbel-Top-k). Run Sequential Halving over the n simulations. Pick the action maximising g(a) + logits(a) + σ(q̂(a)). Policy target π' = softmax(logits + σ(completed Q)), where completed Q uses v_π for unvisited actions, trained with KL(π', π). Non-root selection is deterministic, so visit counts track π'.
- **Assumes:** Theory is for a deterministic bandit with a predictor. Simulation budget n small relative to action count k. Guarantee needs correctly evaluated action values (v_π approximated). Stochastic extension uses empirical means. Go c_visit = 50, c_scale = 1.0; Atari c_scale = 0.1 on normalised Q.
- **Claims** (figures only, no exact Elo in the text):
  - 9×9 Go: MuZero fails to learn with 16 or fewer simulations; Gumbel MuZero "learns reliably even with 2 simulations".
  - Atari ms_pacman: MuZero fails at 4 or fewer simulations; Gumbel learns reliably at n = 2.
  - Training speedup on 9×9 Go (Table 1, relative to n = 200, when not limited by training TPUs): n = 32 5.9×; n = 16 11.3×; n = 8 16.2×; n = 4 24.3×.
  - 19×19 Go at n = 400: matches or exceeds MuZero.
  - The paper says the guarantee is about the search's chosen action and the target construction. It does not claim the trained net is guaranteed to improve in practice.
- **Evaluation:** 9×9 Go (2 seeds for the main figure, 10 for beam_rider), 19×19 Go against Pachi (10k simulations, anchored at 1000 Elo), chess, Atari with sticky actions. Google Cloud TPU v3.
- **Code:** https://github.com/deepmind/mctx (JAX; license not checked).
- **Fit:** partial. Directly targets the few-simulations regime, and gives a policy target built from search values rather than raw visit counts. Breaks the hidden-order constraint: deterministic bandit theory, no chance nodes, and the experiments are on perfect-information games and Atari with TPUs.
