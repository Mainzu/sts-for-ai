# Game-AI rating and benchmark cards (angle: rating systems outside chess)

Scout run 2026-11-01. 8 papers opened, all 8 read as full text (HTML or ar5iv). "Cited by" was not retrieved for any card (the OpenAlex fetch did not return counts for these works), so it is marked as such.

Notes on the fetches:
- Some numbers in the GVGAI card came through garbled (see that card).
- Nothing here is a Slay the Spire paper. Each card says what its method assumes so Opus can check the fit.

### Re-evaluating Evaluation (2018)
- **Link:** https://arxiv.org/abs/1806.02643 (read via https://ar5iv.labs.arxiv.org/html/1806.02643) · **Venue:** NeurIPS 2018 · **Cited by:** not retrieved · **Read:** full text
- **Problem:** Elo gives poor predictions and can be manipulated when agents or tasks are non-transitive or redundant.
- **Method:** Proposes multidimensional Elo (mElo, with a cyclic term) and Nash averaging over a symmetric zero-sum meta-game. Nash averaging is invariant to adding redundant copies of agents or tasks.
- **Assumes:** Two-player games with payoff matrices (win-probability data for every agent pair). Elo assumes skill is transitive. Nash averaging needs a full matrix of agent-vs-agent or agent-vs-task results. Inputs are win/loss outcomes, not scores.
- **Claims:** Go (eight algorithms, Silver et al. extended data): Elo Frobenius error 0.85, logistic loss 1.41; mElo2 0.35 and 1.27. Rock-paper-scissors: Elo predicts 0.5 for every pair. Adding a second copy of agent C shifts Elo to −63 and +63 for A and B. Adding a near-duplicate task changes agent C's average from 84 to 88 and reverses the A/C ranking. Nash averaging invariance (P1), continuity (P2), interpretability (P3) are stated as theorems. On Atari (20 agents, 54 environments, min-max normalised), the paper says "better-than-human performance has not yet been achieved under Nash averaging."
- **Evaluation:** Go algorithm matrix from Silver et al.; rock-paper-scissors toy game; Atari with 20 agents on 54 environments.
- **Code:** none found in the text (pseudocode for mElo2 in Appendix E).
- **Fit:** partial. Good for the "copies of an agent can flip Elo" failure, which matters when our nets share one lineage. It needs a full agent-vs-agent matrix, and the paper gives no uncertainty estimates.

### Deep Reinforcement Learning at the Edge of the Statistical Precipice (2021)
- **Link:** https://arxiv.org/abs/2108.13264 (read via https://arxiv.org/html/2108.13264) · **Venue:** NeurIPS 2021 (outstanding paper award, per search summary) · **Cited by:** not retrieved · **Read:** full text
- **Problem:** Point estimates (mean or median over 3 to 10 runs per task) hide large uncertainty in RL benchmark claims.
- **Method:** Stratified bootstrap confidence intervals, performance profiles, interquartile mean (IQM, the mean of the middle 50% of pooled runs), optimality gap, and probability of improvement. Released as the rliable library.
- **Assumes:** Several independent runs (seeds) per task, and the scores are per run. Stratified bootstrap resamples runs within each task. Works from N = 10 runs up. The paper says the scores need not be normal.
- **Claims:** Atari 100k, 100 runs per algorithm: "about 36%" of SPR's mean improvement over DrQ(ε) (+0.08) came from sample-median bias at 5 runs (+0.03). Sample medians need roughly 50 to 100 runs, "far too many to be computationally feasible for most research projects." Example 5-run CIs: DrQ(ε)-over-DER median improvement within (0.01, 0.21); SPR-over-DrQ within (−0.09, 0.18). IQM bias for SPR between 3 and 100 runs: 0.05 points for median vs 0.006 for IQM. Compute: about 18,200 runs, 2400 to 3600 GPU days.
- **Evaluation:** Atari 100k (26 games), ALE 200M (55 games with sticky actions), Procgen (16 tasks, 10 runs each), DM Control (6 tasks).
- **Code:** https://github.com/google-research/rliable (licence not stated in the fetched text; check LICENSE). Colab notebook linked from the paper.
- **Fit:** good. It gives a method for CIs on a few seeded runs of several agents, and the "few runs" warning applies to our seeded fights. Its target is per-task score distributions, not win/loss, so it needs scores on a comparable scale.

### Active Evaluation of General Agents: Problem Definition and Comparison of Baseline Algorithms (2026)
- **Link:** https://arxiv.org/abs/2601.07651 (read via https://arxiv.org/html/2601.07651v2) · **Venue:** arXiv, accepted to AAMAS 2026 (per search summary) · **Cited by:** not retrieved · **Read:** full text
- **Problem:** With n tasks and m agents, pick which task and agent pair to run next, so that a ranking is reached with few evaluations.
- **Method:** Compares uniform averaging, UCB, dueling bandits, batch and online voting rules (Elo, Copeland, SCO, Nash averaging, and others) and task-selection strategies. Error metric: Average Generalized Top-k Ranking Error (AGRE).
- **Assumes:** Each game gives a pairwise result (or a per-task score that becomes a ranking), and the ground-truth ranking is known for the test. Atari scores are simulated as normal distributions per agent and game from Agent57's table. Scores normalised to [0, 100] per game.
- **Claims:** Atari AGRE at t = 10^4 (k=3 / k=8): BatchSCO 0.019031 / 0.008095; OnlineSCO 0.025931 / 0.009034; BatchElo 0.032967 / 0.010907; OnlineElo 0.037259 / 0.012504; BasicUCB 0.241976 / 0.074383; UniformAveraging 0.242354 / 0.259529. The paper states Elo is "a consistently reliable choice for efficient reduction of ranking error in practice" despite theoretical failure modes (from search summary). Atari: 15 of 57 tasks have Kendall-tau distance of at least 8 from the ground truth.
- **Evaluation:** 57 Atari games, 8 agents (random, human expert and deep RL agents), simulated from Agent57 Section H.4; synthetic Mallows model (m=8, n=50, φ=0.3); AgentBench (25 LLMs, 8 environments) is mentioned in the companion VasE card, not here.
- **Code:** none found in the fetched text (voting code is in OpenSpiel, see the VasE card).
- **Fit:** good. It maps directly onto choosing which seeded fights and agent pairs to run for a rank with fewer games. Its Atari numbers are simulated normal scores, so they do not show how the methods work on real stochastic game outcomes.

### Evaluating Agents using Social Choice Theory (2023, v4 2025)
- **Link:** https://arxiv.org/abs/2312.03121 (read via https://arxiv.org/html/2312.03121v4) · **Venue:** arXiv (venue not checked) · **Cited by:** not retrieved · **Read:** full text
- **Problem:** Rank general agents across many tasks, where each task has its own incomparable metric, and avoid the known failure modes of Elo.
- **Method:** Voting-as-Evaluation (VasE). Each task (or game) is a voter that ranks agents by its own metric. A voting rule aggregates the votes. Nine rules are tested (approval, Borda, plurality, STV, Copeland, ranked pairs, Kemeny-Young, Schulze, maximal lotteries). Also proposes Iterative Maximal Lotteries (IML).
- **Assumes:** Per-task rankings from each task's own metric. No cross-task normalisation needed. The evaluator sets the task weights. Population consistency and Condorcet consistency cannot both hold for any deterministic voting scheme, so the evaluator must choose.
- **Claims:** Maximal lotteries satisfies Condorcet, population, clone, agenda consistency and IIA, and runs in polynomial time (stated properties). Elo failures shown: with 10 copies of agent B, Elo gives p̂_AC = 0.631 against a true 0.9. On the Atari set (8 agents, 54 games), all nine methods rank Rainbow first. Nash averaging uses only 4 tasks ("7.4%" of tasks). In Diplomacy (31,049 seven-player games, 52,958 players, 50 random splits), Copeland and approval voting have significantly lower error than Elo; Copeland is best.
- **Evaluation:** Atari (8 agents, 54 games); AgentBench (25 LLMs, 8 environments; gpt-4 is the Condorcet winner); Diplomacy human games.
- **Code:** voting code, examples and datasets in OpenSpiel: https://github.com/google-deepmind/open_spiel/tree/master/open_spiel/python/voting (licence not checked).
- **Fit:** partial. The per-task voting idea fits our case of several seeded fight sets as separate "tasks". The method needs many tasks or a full ranking per task. Our case has few agents, so the clone and redundancy failure modes matter more.

### Revisiting the Arcade Learning Environment: Evaluation Protocols and Open Problems for General Agents (2018)
- **Link:** https://arxiv.org/abs/1709.06009 (read via https://ar5iv.labs.arxiv.org/html/1709.06009) · **Venue:** JAIR vol. 61, 2018 (IJCAI 2018 extended abstract is a shorter version) · **Cited by:** not retrieved · **Read:** full text
- **Problem:** The deterministic ALE lets agents memorise action sequences. Protocols differ across papers, so results are hard to compare.
- **Method:** Sticky actions: with probability ς = 0.25 the environment repeats the previous executed action instead of the new one. Also recommends a train/test game split, reporting training in frames, and reporting performance at several points in training.
- **Assumes:** Atari 2600 via ALE, one stochastic input rule per frame. Frame skipping works. Only the game-over signal ends an episode. Hyperparameters tuned on training games only.
- **Claims:** Sticky actions change deterministic results a lot: Brute, Asterix 6909 → 308, Freeway 1.1 → 0.0, Seaquest 621 → 81 (Table 2). DQN (5 trials) and Sarsa(λ)+Blob-PROST (24 trials) results at 200M frames: Asterix 2,866.8 (1,354.6) and 4,395.2 (460.7). The authors say DQN's 5-trial sample "may be too small to detect some differences". Sarsa(λ)+Blob-PROST scores highest at 200M in 50 of 60 games; DQN in 35 of 60.
- **Evaluation:** 60 Atari games, 200M frames, ς = 0.25; learning curves at 10M, 100M, 200M frames.
- **Code:** no repository link; learning-curve data at http://www.marcgbellemare.info/static/data/machado17revisiting.zip (plain http link from the paper).
- **Fit:** good. The main lesson for us is that stochasticity added by the environment (not seeds alone) changes the ranking, and that protocol rules must be fixed up front. Its train/test game split maps to a held-out set of seeds or fight types for the nets.

### Agent57: Outperforming the Atari Human Benchmark (2020)
- **Link:** https://arxiv.org/abs/2003.13350 (read via https://ar5iv.labs.arxiv.org/html/2003.13350) · **Venue:** ICML 2020 · **Cited by:** not retrieved · **Read:** full text
- **Problem:** No single RL algorithm had beaten the human baseline on all 57 Atari games with one set of hyperparameters; hard games (Montezuma's Revenge, Pitfall!) were the failures.
- **Method:** One network covering exploratory to exploitative policies, with an adaptive selector over policies during training.
- **Assumes:** Human-normalised score HNS = (Agent − Random) / (Human − Random), capped at [0, 1] for CHNS. The human and random baselines are from the Atari table (the paper does not say where they come from). The paper says the human baseline "potentially under-estimat[es] human performance."
- **Claims:** Capped mean 100.00 (57 games above human) for Agent57; R2D2 (bandit) 96.93 (54 games); NGU 95.07 (51); MuZero 89.92 (51). Uncapped medians: Agent57 1933.49; R2D2 1935.86 (table as extracted; the text says Agent57's median is higher, so the table value should be checked against the PDF). Agent57 averaged over 6 seeds; other agents over 3 seeds. Scores are the windowed mean over 50 episodes; per-game score is the maximum over training.
- **Evaluation:** 57 Atari games (ALE), undiscounted episode return, human and random baseline per game.
- **Code:** none from Agent57; links only to the Arcade Learning Environment repo.
- **Fit:** partial. The "superhuman on all games" claim comes from a per-game baseline plus capping. We have no human data, so an analogous baseline would have to be a fixed reference (for example a heuristic bot or random play), and the paper shows the capped mean hides the uncapped differences.

### General Video Game AI: a Multi-Track Framework for Evaluating Agents, Games and Content Generation Algorithms (2018)
- **Link:** https://arxiv.org/abs/1802.10363 (read via https://arxiv.org/html/1802.10363) · **Venue:** arXiv (venue not checked) · **Cited by:** not retrieved · **Read:** full text
- **Problem:** Game-playing AI overfits to single games. GVGAI tests agents on unseen games and levels.
- **Method:** Competition ranking per game: sort entries by victory rate, then score, then game length. The top 10 get points (25, 18, 15, 12, 10, 8, 6, 4, 2, 1). The entry with the most points across the test set wins. The text is partly garbled, so the last point value is inferred.
- **Assumes:** Single-player planning has a forward model and fixed per-tick time (1 s init, 40 ms per tick). Learning tracks have no forward model. Controllers run on fixed levels; the 2018 learning track had 3 games with 2 training levels and 3 secret test levels each, and a 100 ms decision time. Hardware: Intel Core i5 at 2.90 GHz, 4 GB RAM (paper footnote).
- **Claims:** Robustness study: changing the reward signal or adding noise to actions or the forward model "can significantly change the rankings". Some controllers "perform well under almost all conditions". Soemers' MCTS: "increased the average win rate of the sample agent in 1717 percentage points" (the 1717 looks like an encoding error; the paper's other numbers suggest 17). Perez-Liebana multi-objective MCTS win rate rose "from 32.24%" to "42.38%". No significance tests reported in the text.
- **Evaluation:** GVGAI framework with 120 single-player and 60 two-player VGDL games; competition sets of 10 games with 5 levels each; private validation and test sets per year.
- **Code:** GVGAI website www.gvgai.net; GVGAI Gym https://github.com/rubenrtorrado/GVGAI_GYM (licence not stated in the text).
- **Fit:** partial. The held-out levels and unseen-game test match our seeded fights (train on some seeds, test on others). The paper reports no statistics, so its rankings are a poor template for the kind of CI we need. Its robustness finding (small reward or action noise re-ranks agents) is directly relevant to a stochastic game.

### On the Limitations of Elo: Real-World Games, are Transitive, not Additive (2022)
- **Link:** https://arxiv.org/abs/2206.12301 (read via https://arxiv.org/html/2206.12301) · **Venue:** arXiv (venue not checked) · **Cited by:** not retrieved · **Read:** full text
- **Problem:** Measure how transitive a two-player zero-sum game is from empirical payoff data, and when Elo fails to recover the transitive part.
- **Method:** Treats the payoff logit matrix as skew-symmetric and decomposes it into "disc" games (at most one component is transitive, Theorem 2). Each player gets a strength u/v and a consistency score v, fit by alternating minimisation with L-BFGS.
- **Assumes:** Pairwise win data for each pair of players. Missing entries are allowed (only observed pairs are summed). Test set: 20% of entries held out. StarCraft II needs a regulariser λ/2 Σ(v_i − 1)², chosen by cross-validation.
- **Claims:** Czarnecki et al. (2020) payoff matrices, test MSE: pure Elo game: Elo 1.6×10⁻¹⁰, disc k=2 1.7×10⁻¹⁰; pure disc game: Elo 7.9×10⁻², disc k=1 2.6×10⁻⁶, disc k=2 4.6×10⁻⁷. Elo "provably fails to extract the transitive component of some elementary transitive games" (Example 3, synthetic). Real chess (Lichess, over 4.7 million games) and StarCraft II (aligulac, over 1.7 million games) results are qualitative. No confidence intervals or significance tests.
- **Evaluation:** Czarnecki et al. payoff matrices (Go, AlphaStar, Blotto, Kuhn poker, Connect Four, Quoridor, and random); Lichess elite games; aligulac StarCraft II.
- **Code:** https://github.com/QB3/discrating (licence not checked).
- **Fit:** partial. It is about how to read a full pairwise matrix; it does not handle our case of a few agents on shared seeds, where the matrix is small and noisy. Its useful point is that a single Elo number can hide a cyclic part, which the authors show only on synthetic and large-sample data.

## What is missing from this angle

- TrueSkill (Herbrich et al.), Glicko and Bradley-Terry in game AI: not opened. Microsoft's TrueSkill page did not give a readable full text in the search results.
- MicroRTS and GVGAI rating studies with Elo or TrueSkill: searches found none. MicroRTS competitions score by round-robin win rate (win 1, draw 0.5, loss 0; from the 2025 competition page).
- NetHack and Procgen papers were checked only at the search-snippet level (Procgen: train on a finite level set, test on the full distribution; 500 training levels by default). Not opened, so no card.

Sources (fetched):
- https://arxiv.org/html/2108.13264
- https://ar5iv.labs.arxiv.org/html/1806.02643
- https://arxiv.org/html/2601.07651v2
- https://arxiv.org/html/2312.03121v4
- https://ar5iv.labs.arxiv.org/html/1709.06009
- https://ar5iv.labs.arxiv.org/html/2003.13350
- https://arxiv.org/html/1802.10363
- https://arxiv.org/html/2206.12301
