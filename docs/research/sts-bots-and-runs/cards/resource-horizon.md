# Cards: long-horizon planning with a resource carried across stages

Angle: roguelike AI, multi-stage MDPs, a shared resource (HP, budget, water) across stages, shadow prices, per-stage reward shaping.
Date: 2026-11-01. Eight papers opened. Seven were read as full text; Rogue-Gym (card 7) was read through ar5iv but yielded no numbers. Notes on cards 3 and 5 say how much of each text was read.

Search note: OpenAlex keyword search on roguelike terms returned mostly titles with no resource-across-stages theme. The strongest hits were the shadow-price (dual multiplier) literature and SDDP water values. No paper found models HP or potions carried across Slay the Spire fights directly.

---

### Deep Reinforcement Learning for Turn-based Strategy Games (DeepCrawl) (2020)
- **Link:** https://arxiv.org/abs/2012.01914 · **Venue:** arXiv preprint (cs.LG) · **Cited by:** not checked · **Read:** full text
- **Problem:** Train credible, beatable, varied NPC agents for a turn-based roguelike, not superhuman ones.
- **Method:** PPO with an actor-critic baseline; an LSTM over four map/property branches; 17 discrete actions. Reward is terminal and sparse: R(t) = -0.01 + {-0.1 for an impossible move; +10.0 × HP on a win}, where HP is the normalized agent HP left when the opponent dies. No per-stage reward, no reward for losing.
- **Assumes:** Discrete turns on a grid of at most 10×10 tiles; one agent against an opponent that makes random moves in training; discount γ = 0.99; rollouts of 10 episodes up to 100 steps. The curriculum (five phases) changes enemy HP, agent HP range and loot quantity, not the reward.
- **Claims:** The paper reports no win rates. It reports a 10-person playability test (about 60 min each, 15-item SEQ 1–7 scale): "Would you feel able to get to the end of the game?" μ = 5.54; "Is the game enjoyable and fun?" μ = 5.80. Curriculum training gave "significantly higher average reward" than no curriculum (no numbers given). About two days of training on a GTX 1050 Ti.
- **Evaluation:** DeepCrawl, a roguelike won by completing ten dungeon levels; classes Archer, Warrior, Ranger; opponent ATK = 3, DEX = 3, DEF = 3.
- **Code:** none found (the page links only to the Google Play and App Store builds).
- **Fit:** partial. It is the one paper here that pays for HP left at the end of a fight (+10 × HP on a win), which is the per-fight form of HP pricing. It breaks the constraint of cross-fight carry: HP is not carried between fights, and it sets no price for HP beyond the win reward. Its PPO setup has no shadow price.

---

### Model-based Constrained MDP for Budget Allocation in Sequential Incentive Marketing (2023 arXiv; CIKM 2019 per the page)
- **Link:** https://arxiv.org/abs/2303.01049 · **Venue:** page lists CIKM 2019; arXiv v1 posted March 2023 · **Cited by:** not checked · **Read:** full text
- **Problem:** Spread one global incentive budget across repeated interactions with each user, maximizing engagement without exceeding the budget, from logged off-policy data.
- **Method:** Constrained MDP in Lagrangian dual form, L(π,λ) = −J(π) + λ(J_C(π) − b). The multiplier λ is found by bisection, since cost is monotone in λ (Theorem 3.1). For each λ, policy learning is a soft DQN on reward r − λc. Model-based version: learn transition, reward and cost models once, then plan with tree search for each λ without retraining.
- **Assumes:** Discrete time, horizon T, discounted cost. Assumption 1: the cheapest policy is strictly feasible (J_C(π_l) < b). Assumption 2: the most costly policy exceeds b. Assumption 3: when c(s,a0) > c(s,a1) then r(s,a0) > r(s,a1). The logged behaviour policy is stationary. The budget is a single total (b = 2.9295 synthetic, b = 0.532 Alipay).
- **Claims:** Synthetic, b = 2.9295: random 3.8836; constrained bandit 4.4006 (+13.31%); constrained MDP 4.5093 (+16.11%). Alipay, b = 0.532: random 0.687; bandit 0.688 (+0.145%); constrained MDP 0.693 (+0.873%). At fixed reward 0.687 on Alipay: cost 0.503 (−5.46%) bandit, 0.482 (−9.40%) MDP. The text's own real-data gains (8.97%, 13.61%) disagree with Table 2; the table numbers are quoted here. Model-based and bisection give "almost the same rewards"; bisection costs O(n) times more compute, with no timings.
- **Evaluation:** Synthetic two-step contextual bandit (Gaussian reward and cost, cost variance 0.1); real Alipay red-envelope logs (next-day activity as reward, envelope amount as cost), holdout validation.
- **Code:** none found.
- **Fit:** partial. The clearest worked example of a multiplier used as the price of a shared budget and tuned by bisection so the total spend fits. The domain is marketing with logged data, not a game with a headless simulator, and the budget is a spend total, not HP that can be lost and restored.

---

### InFlow: entropic stochastic dual dynamic programming with HJB cross-certification for seasonal energy storage (2026)
- **Link:** https://arxiv.org/abs/2609.11339 · **Venue:** arXiv preprint (2026) · **Cited by:** not checked · **Read:** full text, first 100,000 of about 160,600 characters (the rest not read; the results quoted are from the first part)
- **Problem:** Find the marginal value of stored water (water value, seasonal storage value) across weekly stages of a reservoir, i.e. the shadow price of a stock that carries across stages.
- **Method:** Periodic SDDP on a weekly Markov chain of inflow nodes; stage LPs solved with HiGHS; water value = negative storage-balance dual (λW = −μ). An independent state-constrained HJB PDE (finite differences) gives −∂sV as a cross-check. Entropic terms: soft-min Bellman operator and a KL-penalized worst-case expectation with multiplier γ.
- **Assumes:** Inflow is a mean-reverting CIR square-root diffusion (κ = 8, σ₀ = 2, θ̄ = 1, a = 0.8); the Feller condition fails in the five driest weeks (minimum Feller ratio 0.8). 52 weekly stages a year, 11 inflow nodes, 8 piecewise-linear thermal cost segments. Normalized, dimensionless demand, not calibrated to a real basin.
- **Claims:** HJB and HiGHS-dual water values correlate 0.995 (exact-cut replication: 0.996). Mesh refinement 61² to 81²: annual mean SSV 0.5783 to 0.5747 (0.6%). Out of sample, 3,000 trajectories, γ = 5 vs γ = 0: nominal mean cost +4.6%, CVaR90 −11.2%; stressed world (dry-season inflow 40% lower): mean −0.4% (interval includes zero), CVaR90 −11.5%. Two-reservoir cascade: correlations 0.9987 and 0.9986 against the grid. Negative result: the authors withdraw the claim that entropic annealing speeds up exact SDDP in higher dimensions.
- **Evaluation:** Synthetic seasonal storage with CIR inflows; a 41×41 HJB grid refined to 81²; a two-reservoir cascade.
- **Code:** none stated; the paper says scripts are "included in the accompanying reproducibility archive" but gives no URL.
- **Fit:** partial. The best worked example of pricing a resource unit from future-stage outcomes (the dual of the storage balance). It breaks two constraints: it needs stochastic dynamic programming on a state grid (heavy on CPU for a 4-to-6-dimensional HP/deck state), and the state is a continuous stock, not a game with discrete fights.

---

### Reinforcement Learning for the Game of Balatro: A Fast Simulator and Two-Policy Training Approach (2026)
- **Link:** https://arxiv.org/abs/2610.39049 · **Venue:** arXiv preprint (stamped 28 Oct 2026) · **Cited by:** not checked · **Read:** full text
- **Problem:** Learn a Balatro policy: long horizon, sparse reward, about 3,000 discrete actions, stochastic draws and shop.
- **Method:** Two PPO policies that share the full state: a blind policy plays hands; a shop policy buys, sells, opens packs and skips. Per-blind reward: 1 for clearing a blind on a play; otherwise chips ÷ target, capped at 1; −1 if hands run out; 0 otherwise. Dense shaping for the blind agent (six signals, including a "graduated loss penalty" and an "ante-scaled clear bonus"); the shop agent gets an interest-tier penalty. Cross-agent credit: cash and round-won rewards go to the shop agent after a blind is cleared; the run-win bonus goes to both.
- **Assumes:** Eight antes, three blinds each (small, big, boss) in order, a shop between blinds. Money and the deck/joker set persist through the run. Training: 4,000 PPO iterations, about 20.5M environment steps, 5,120 steps per iteration, 4 env-runner processes, one RTX A5000 learner (GPU). The simulator is a Rust core with Python bindings; no throughput numbers.
- **Claims:** Training curves only (no held-out evaluation). First-blind clear rate crosses 0.5 at iteration 151, 0.9 by 160, 0.99 by 173, plateau about 0.998. Mean max ante rises from 1 to about 2.1, then 2.6 to 3.0 on the plateau ("about 3 out of 8" in the abstract). Single-agent baselines oscillated between greedy and hoarding modes. The authors say the agent is "not yet a run-completing policy". No full-run win rate reported.
- **Evaluation:** Live training curves from on-policy batches with exploration on, smoothed over 40 iterations. Deterministic evaluation (32 episodes, explore off) is described but not reported.
- **Code:** none found (the paper's own CC BY 4.0 licence is the only licence stated).
- **Fit:** partial. The closest case so far of a resource (money, deck) carried across stages, with per-stage reward and cross-agent credit for the run outcome. It breaks the CPU-only constraint in its training setup (GPU learner), and it reports no run-level win rate, so it doesn't show whether the per-stage design raises the whole-run clear rate.

---

### Reward Constrained Policy Optimization (RCPO) (2018, ICLR 2019)
- **Link:** https://arxiv.org/abs/1805.11074 · **Venue:** arXiv (cs.LG, cs.AI, stat.ML); ICLR 2019 per the search listing · **Cited by:** not checked · **Read:** full text
- **Problem:** Maximize reward subject to a constraint on a general function of per-step penalty (discounted sum, mean, or probability), J_C ≤ α.
- **Method:** Lagrangian min over λ ≥ 0 of max over θ of [J_R − λ(J_C − α)]. The actor and critic use the penalized reward r̂ = r − λc. λ is updated on the slowest timescale, λ_{k+1} = Γ_λ[λ_k + η₁(k)(J_C − α)], with Monte-Carlo estimates of the true constraint. Three timescales: critic fastest, actor middle, λ slowest.
- **Assumes:** V_R bounded for all policies (Assumption 1); every local minimum of J_C is feasible (2); Robbins–Monro step sizes with η₁/η₂ → 0 (3); Theorem 2 needs local minima of the discounted-penalty objective to be feasible (4); bounded noise and stable iterates. Under these, convergence is almost sure to a local minimum (Theorem 1) or to a feasible point (Theorem 2).
- **Claims:** Mars Rover (stochastic grid, failure-probability constraint δ = 0.05, γ = 0.99, A2C): only qualitative; RCPO converges faster and with lower variance than direct Lagrange optimization for α = 0.01 and 0.5. MuJoCo, torque constraint under 25% (Table 2, torque / reward): RCPO Swimmer 24% / 72.7; Walker2d 25.2% / 591.6; Hopper 26% / 1138.5; Humanoid 24.3% / 606.1; HalfCheetah 26.7% / 1547.1; Ant 15.2% / 1031.5. Fixed-penalty reward shaping (λ = 0.1 or 100) is sometimes feasible but gives lower reward (e.g. Walker2d λ=0.1: 13.6% / 823.5, which is higher reward than RCPO's, the one exception). HalfCheetah RCPO (26.7%) breaks the 25% bound the paper states.
- **Evaluation:** Mars Rover (grid, A2C); six Gym MuJoCo tasks (Swimmer-v2, Walker2d-v2, Hopper-v2, Humanoid-v2, HalfCheetah-v2, Ant-v2) with PPO.
- **Code:** none found in the fetched text.
- **Fit:** partial. It states the mechanism most directly: a multiplier that rises while the constraint is violated and falls otherwise, folded into the reward as a per-step penalty. Its constraint is an expectation over one episode, not a budget carried across episodes, and the domains are robotics and grid worlds.

---

### Crawling in Rogue's dungeons with (partitioned) A3C (2018; journal version IEEE Trans. Games 2020 per search)
- **Link:** https://arxiv.org/abs/1804.08685 · **Venue:** arXiv preprint · **Cited by:** not checked · **Read:** full text
- **Problem:** Partially observable, randomly generated roguelike dungeons. The task is to find and take the stairs on each level.
- **Method:** Partitioned A3C: the state is split into four situations (corridor, stairs visible, next to wall, other), each with its own A3C agent sharing a value function. Network: two conv layers (16 and 32 filters, 3×3), a 256-unit dense layer and a 256-unit LSTM.
- **Assumes:** Rogue with 26 configurable floors, each up to 9 rooms with corridors and small mazes. Monsters and traps disabled: death is impossible, and starvation cannot happen within 500 steps. HP is not mentioned. Episodes are per level: they end at the stairs or after 500 moves. Discount γ = 0.95, t_max = 60, entropy β = 0.001.
- **Reward:** +1 for first use of a door; +1 for each action that reveals new doors; +10 for descending; −0.01 for actions that don't change the state.
- **Claims:** 200 consecutive episodes: random 7%, DQN 23%, this work 98%. Situation s2-c2 gives 98% success, average return 17.97, 111.48 average steps. The text says the stairs-visible situation was essential; four situations did not clearly beat two.
- **Evaluation:** The Rogue (RogueInABox) dungeon with stairs-finding per level, 500-move limit.
- **Code:** https://github.com/Francesco-Sovrano/Partitioned-A3C-for-RogueInABox (licence not stated in the paper).
- **Fit:** poor to partial. Its per-level episodes and reward shaping (a small per-level bonus, a small step penalty) are a clear example of per-stage reward design. It has no resource to carry (no HP, no items), so it gives no price for a carried unit.

---

### Rogue-Gym: A New Challenge for Generalization in Reinforcement Learning (2019)
- **Link:** https://arxiv.org/abs/1904.08129 · **Venue:** IEEE Conference on Games (CIG) 2019 (copyright line) · **Cited by:** not checked · **Read:** full text via ar5iv (the arxiv.org/html URL returned 404). The fetched text gives no experiment numbers.
- **Problem:** RL agents overfit their training environment; a roguelike with seeded dungeons (train seeds vs disjoint test seeds) is a benchmark for generalization.
- **Method:** PPO baseline, with variants: PPO Small (three CNN layers), PPO Large (IMPALA-style, 15 CNN layers with 6 residual connections), PPO BatchNorm, PPO L2 (weight decay 1e-4), VAE PPO and β-VAE PPO.
- **Assumes:** Floors generated from a seed; the goal is the Amulet of Yendor on the deepest floor, by finding the downstairs on each floor (number of floors not stated). Observation: one binary channel per ASCII character, 32×16 screen. 11 discrete actions. Episodes end at 500 steps. Enemies and items disabled in experiments.
- **Reward:** Gold collected during the episode, plus a pseudo-reward of 50 gold per floor reached. Level-up rewards and whether HP or items persist across floors are not stated.
- **Claims:** The fetched text gives only qualitative claims: some methods fail to reduce overfitting; L2 "gives better generalization scores than the baseline but 'not sufficiently effective.'" No numeric results were extracted.
- **Evaluation:** Rogue-Gym (Rust core, Python API `pip install rogue_gym`); experiments repo kngwyu/rogue-gym-agents-cog19.
- **Code:** https://github.com/kngwyu/rogue-gym (Rust, Python API) and https://github.com/kngwyu/rogue-gym-agents-cog19; licence not stated in the fetched text. The aggregator note says the first repo was last updated in 2023 (unverified).
- **Fit:** partial. A headless, seeded roguelike simulator with per-floor reward and a gold pseudo-reward per floor. It has no resource carried across floors (gold carries within an episode), and the paper's numbers were not extracted.

---

### NetHack is Hard to Hack (2023)
- **Link:** https://arxiv.org/abs/2305.19240 · **Venue:** NeurIPS 2023 (per search listing); the fetched text calls it an arXiv preprint · **Cited by:** not checked · **Read:** full text, first 100,000 of about 108,700 characters (the last 8,700 were not read)
- **Problem:** Neural policies fall short on long-horizon, open-ended NetHack play; in the NeurIPS 2021 NetHack Challenge, symbolic agents beat neural ones "by over four times in median game score".
- **Method:** The symbolic AutoAscend agent is extended to log the strategy behind each action (HiHack dataset, hierarchical labels, about 3.2 billion transitions from over 100,000 games). Hierarchical behavioural cloning (high-level strategy decoder plus low-level action decoders) on the CDGPT5 LSTM, with a transformer added (transformer-LSTM). Fine-tuned with APPO + BC (moolib).
- **Assumes:** NLE v0.9.0; text tty components (ego-centric pixel view, in-game message, bottom-line stats); 121 discrete actions; NLE timeout 1000 for dataset generation; 13 starting roles; episodes run until the game ends.
- **Claims:** Offline median NLE score 914 (transformer-LSTM BC) vs 403 (LSTM), reported as +127%. Online median 972 (hierarchical LSTM, APPO + BC) vs 779, +25%. Online best mean 1551 ± 73. AutoAscend mean 8556 ± 187, median 4918. Scale alone does not close the gap.
- **Evaluation:** 1024 withheld games, final NLE score.
- **Code:** https://github.com/upiterbarg/hihack (dataset plus augmented AutoAscend and NLE code); licence not stated in the fetched text.
- **Fit:** poor to partial. Relevant as the long-horizon baseline: it shows a hierarchy of strategy labels helps a neural policy. It does not price a resource (its score is a single episode total), and its compute and dataset size are far beyond CPU-only.

---

## Not opened, noted for later

- Dynamic allocation of limited memory resources in reinforcement learning (arXiv 2011.06387): a resource budget in RL; seen in search only.
- A Survey of Reinforcement Learning For Economics (arXiv 2603.08956): has a Lagrangian Q-learning example where the learned multiplier settles near the analytic shadow price (λ ≈ 1.40 vs 1.20); seen in search only.
- NetHack Learning Environment (arXiv 2006.13760): environment paper; not opened.
- Benchmarking Long-Horizon Agents with Checkpointed Exploration in NetHack (NeurIPS 2026 listing): LLM-agent benchmark; not opened.
- OpenAlex result W7163838394, "Reinforcement learning-based dual-policy adversarial model for dynamic difficulty adjustment in a turn-based roguelike game" (2026): titles only; not opened.
