# Expert iteration, AlphaZero/MuZero family, small-budget and stochastic variants: cards

Scout angle: expert iteration and AlphaZero-style self-play at small compute.
13 papers opened: 5 read as full text (ExIt, Gumbel MuZero via a plain-text mirror, KataGo, Sampled MuZero, ExIt-OOS), 8 read as abstract only.
Problem frame for all cards: StS1 one-turn expectimax over afterstates, with chance nodes, a learned value net (Deep Sets, ~185k params), CPU only, no peeking at hidden information, generalisation to unseen cards.

---

### Thinking Fast and Slow with Deep Learning and Tree Search (2017)
- **Link:** https://arxiv.org/abs/1705.08439 · **Venue:** NeurIPS 2017 · **Cited by:** 198 (OpenAlex) · **Read:** full text (ar5iv HTML)
- **Problem:** Use tree search to produce targets for a network that generalises across states, then let the network guide later searches (Expert Iteration, ExIt).
- **Method:** Apprentice network plays; expert (MCTS guided by the apprentice) labels visited states with the tree policy target n(s,a)/n(s), trained with a cross-entropy-style loss. A value head trained on the binary result z of apprentice playouts is added in later experiments, summed into a multitask loss.
- **Assumes:** Discrete turns; two-player zero-sum; perfect information; deterministic transitions. Hex 9x9, 6-channel board encoding, 13 conv layers, Adam, minibatch 250.
- **Claims:** Top-1 error 47.0% (chosen-action target) vs 47.7% (tree-policy target); tree-policy target "50±13 Elo" stronger. DAgger-augmented TPT network gained 120 Elo. Policy-net-guided MCTS won 97% of games vs baseline MCTS. vs MoHex 1.0: 75.3% at 10,000 iterations; 59.3% vs 100,000 iterations (162-game match); 55.6% vs 4 s/move with parallel solver. Compute: tree search "0.3 seconds per 10,000 iterations" on an Intel Xeon E5-1620 with a Titan X; network evaluations "roughly halve search speed". Total training time not reported.
- **Evaluation:** Hex 9x9; REINFORCE baseline (Elo curves over 5 runs, 90% CI); MoHex 1.0 matches.
- **Code:** none found (not checked).
- **Fit:** partial. Search-distilled policy targets are the core idea and the per-search timings are CPU-scale numbers. It breaks on chance (no stochastic nodes), and its value target is outcome-based only in later experiments.

### Policy improvement by planning with Gumbel (Gumbel AlphaZero / Gumbel MuZero) (2022)
- **Link:** https://openreview.net/forum?id=bERaNdoegnO (OpenReview blocked by a verification page; text read from a plain-text mirror: https://object.cloud.sdsc.edu/v1/AUTH_da4962d3368042ac8337e2dfdd3e7bf3/ml-papers-txt/ICLR/2022/policy_improvement_by_planning_with_gumbel__15d5fc26.txt) · **Venue:** ICLR 2022 (Danihelka, Guez, Schrittwieser, Silver) · **Cited by:** not found in OpenAlex (title lookup empty) · **Read:** full text (via mirror)
- **Problem:** AlphaZero's search can fail to improve its policy when not all root actions are visited; the paper targets reliable improvement with few simulations.
- **Method:** Sample root actions without replacement (Gumbel top-k plus Sequential Halving). Improvement target pi' = softmax(logits + sigma(completed Q)), with unvisited actions given value v_pi. Non-root selection matches visit counts to pi' by squared error (no guarantee claimed there).
- **Assumes:** Guarantee proven for an exact-Q deterministic bandit with monotone sigma; with noisy Sequential Halving the paper gives no formal guarantee. Uses a learned deterministic model (MuZero-style). Discrete actions.
- **Claims:** Training-step speedups vs MuZero n=200 on 9x9 Go (assuming not TPU-limited): Gumbel MuZero n=32: 5.9; n=16: 11.3; n=8: 16.2; n=4: 24.3. "MuZero fails to learn from 16 or less simulations" on 9x9 Go; "Gumbel MuZero learns reliably even with 2 simulations". Atari ms_pacman: MuZero fails with 4 or fewer simulations; Gumbel learns with 2. Elo values exist only in figures.
- **Evaluation:** 9x9 Go with n in {2, 4, 16, 32, 200} (2 seeds); 19x19 Go and chess at n=400; Atari (ALE, sticky actions) n in {2, 4, 16, 18, 50}; Go Elo eval at 800 sims/move vs Pachi at 10k sims anchored at 1000 Elo. Hardware: Google Cloud TPU v3.
- **Code:** paper text names github.com/deepmind/mctx (not opened).
- **Fit:** partial. Directly about search quality at tiny simulation budgets, which matters if the agent searches with few simulations per turn. Breaks on two counts: the guarantee is for deterministic transitions, so chance nodes need an extension (see the 2048 lead below), and it does nothing for value generalisation.

### Planning in Stochastic Environments with a Learned Model (Stochastic MuZero) (2022)
- **Link:** https://iclr.cc/virtual/2022/poster/6832 (abstract page). PDF is on OpenReview, which is blocked by a verification page. · **Venue:** ICLR 2022 (spotlight) · **Authors:** Antonoglou, Schrittwieser, Ozair, Hubert, Silver · **Cited by:** not found in OpenAlex · **Read:** abstract only
- **Problem:** MuZero's models are deterministic, which limits it in inherently random environments.
- **Method:** Learns a stochastic model that includes afterstates and runs a stochastic tree search over it. Per a search-result summary (unverified against the paper): chance outcomes are encoded with a discrete codebook (VQ-VAE-style, one-hot, no decoder).
- **Assumes:** Stochastic transitions with discrete chance outcomes; learned model; board games, 2048 and backgammon. Hardware and training budget not in the abstract.
- **Claims:** Per the abstract, "matched or beat the state of the art" on canonical single- and multi-agent environments "including 2048 and backgammon", and "kept MuZero's performance in Go". The abstract gives no numbers. A third-party leaderboard shows 2048 averages of 500,000 (Stochastic MuZero) vs 300,000 (MuZero); not from the paper, so unverified.
- **Evaluation:** 2048, backgammon, Go.
- **Code:** none found (not checked).
- **Fit:** good for the structure of this problem: afterstates followed by a chance node is exactly the StS draw after a card play. It breaks on two counts: it learns a model where the engine is known, and the abstract gives no training cost. Full text needed before using any details.

### Accelerating Self-Play Learning in Go (KataGo) (2019)
- **Link:** https://arxiv.org/abs/1902.10565 · **Venue:** AAAI-20 RLG workshop (per arXiv comments) · **Cited by:** 59 (OpenAlex, arXiv record) · **Read:** full text (ar5iv HTML)
- **Problem:** Make AlphaZero-style self-play learning compute-efficient.
- **Method:** Playout cap randomization: full searches on a fraction p=0.25 of turns (600 nodes, rising to 1000 after two days), fast searches (100 rising to 200) on the rest; only full-search turns are stored, and fast searches drop Dirichlet noise. Forced playouts n_forced = (k·P·ΣN)^(1/2), k=2, with policy target pruning. Auxiliary heads: opponent's next-turn reply (weight 0.15), ownership (weight 1.5/b²), score pdf/cdf (0.02 each). Value target mixes win/loss (c_value 1.5) with a score utility (c_score starts 0.5, drops to 0.4).
- **Assumes:** Two-player zero-sum Go; GPU training; discrete actions; deterministic.
- **Claims:** About 1.4 GPU-years (at most 28 V100 GPUs for 19 days) vs ELF OpenGo roughly 74 GPU-years and AlphaZero roughly 41 TPU-years; "about a 50x reduction in compute" (crude metric). Ablation factors at about 2.5G self-play queries (about 2 days): playout cap randomization 1.37x; forced playouts/pruning 1.25x; global pooling 1.60x; auxiliary policy 1.30x; auxiliary ownership/score 1.65x; game-specific features 1.55x; product about 9.1x (author calls it an underestimate).
- **Evaluation:** Go vs ELF OpenGo and Leela Zero.
- **Code:** GitHub repo (not opened; not checked).
- **Fit:** partial. The auxiliary-target and playout-cap ideas are game-agnostic and cheap to test on CPU; the 50x and GPU numbers do not transfer. Its statement that predicting sub-components of desired targets "can greatly improve training" maps onto the generalisation goal, but nothing here tests it on card play.

### Learning and Planning in Complex Action Spaces (Sampled MuZero) (2021)
- **Link:** https://arxiv.org/abs/2104.06303 · **Venue:** arXiv (Hubert, Schrittwieser, Antonoglou, Barekatain, Schmitt, Silver) · **Cited by:** 31 (OpenAlex) · **Read:** full text (ar5iv HTML)
- **Problem:** Policy evaluation and improvement when enumerating all actions is infeasible.
- **Method:** Sample K actions from a proposal beta (the policy, optionally with noise); run PUCT over a corrected prior pi_beta ∝ (beta_hat/beta)·pi with c1=1.25, c2=19652; the policy target is the normalised root visit counts over the K sampled actions; trained with KL.
- **Assumes:** Discrete (Go, 362 actions; Ms. Pacman, 18) and continuous (control, 56 action dims in CMU Humanoid) action spaces. Simulations: 400 per move for Go training, 800 for Go eval, 50 for control and Atari.
- **Claims:** Go, K in {15, 25, 50, 100}: "with K=50 samples already closely approaching the performance of the baseline" (1 seed). Ms. Pacman: K=2 insufficient, K=3 approaches the full-search baseline. Control: K=20, 50 simulations/move, 3 seeds. CMU Humanoid: "more than an order of magnitude fewer interactions". The paper reports no hardware.
- **Evaluation:** Go 19x19; Atari Ms. Pacman; DeepMind Control hard and manipulator tasks; CMU Humanoid; Real-World RL suite.
- **Code:** none found (not checked).
- **Fit:** partial. Sampling a subset of large action sets is relevant if the number of legal multi-card plays per turn grows large. It models no chance nodes and no hidden information.

### ExIt-OOS: Towards Learning from Planning in Imperfect Information Games (2018)
- **Link:** https://arxiv.org/abs/1808.10120 (full text via https://arxiv.org/html/1808.10120) · **Venue:** arXiv v2 (Kitchen, Benedetti; CliniCloud Labs) · **Cited by:** 0 (OpenAlex) · **Read:** full text (arXiv HTML, read through a summarizer)
- **Problem:** Extend ExIt to imperfect-information games.
- **Method:** Expert is Online Outcome Sampling (OOS) search over information sets; the network is the rollout policy inside OOS. Training pairs are (infoset encoding, OOS action probabilities), trained with a KL loss. Policy only, no value head described. Exponentially weighted reservoir of 32,000 games. Per iteration: 32 episodes, then 128 gradient steps (Leduc, Goofspiel 6) or 512 (Goofspiel 13). Adam, lr 1e-3, 20 concurrent searches, 10k simulation steps per search in Goofspiel.
- **Assumes:** Two-player zero-sum; imperfect information; infoset encoding (no hidden state seen by the net); Leduc 288 infosets, Goofspiel(6) about 1e5, Goofspiel(13) about 1e9. Hardware not stated, but "one process per core" and batched NN evaluation.
- **Claims:** Goofspiel(6): 66% (2.5) at iteration 100, 69% (2.5) at 1000 vs its teacher (win-rate table; the parenthesised value is undefined in the paper). Goofspiel(13) Elo: ExIt-OOS 1531 at iteration 200, 1600 at 500; OOS 10k 1572 (3.7). Leduc exploitability: figure only. Head-to-heads: 5,000 games each.
- **Evaluation:** Leduc poker; Goofspiel(6) and (13); Liar's Dice(1) and (2).
- **Code:** none found (not checked).
- **Fit:** partial. It respects hidden information by construction (the net sees only the infoset), which matches the no-peeking constraint. It is a policy-distillation method with no value target, and its search is OOS, not expectimax over chance nodes.

### Multiagent Gumbel MuZero: Efficient Planning in Combinatorial Action Spaces (2024)
- **Link:** https://ojs.aaai.org/index.php/AAAI/article/view/29121 (abstract page; PDF at https://ojs.aaai.org/index.php/AAAI/article/view/29121/30120 not opened) · **Venue:** AAAI-24, pp. 12304-12312 · **Cited by:** 5 (OpenAlex) · **Read:** abstract only
- **Problem:** Action spaces that grow exponentially with the number of agents; AlphaZero and MuZero "degrade significantly" as the simulation budget shrinks.
- **Method:** MA Gumbel AlphaZero (no model) and MA Gumbel MuZero (learned model) for multiagent MDPs.
- **Assumes:** Cooperative multiagent control; combinatorial joint actions; learned model in the MuZero variant.
- **Claims:** Abstract only: "up to an order of magnitude" fewer environment interactions than model-free approaches; "superior performance" on cooperative multiagent control. No numbers on the abstract page.
- **Evaluation:** Cooperative multiagent control problems (names not on the abstract page).
- **Code:** https://github.com/tjuHaoXiaotian/MA-MuZero (linked from abstract page; not opened).
- **Fit:** partial. A joint action over several units at small budgets is close to choosing an ordered sequence of plays within one StS turn. It is not a card game and models no chance.

### MiniZero: Comparative Analysis of AlphaZero and MuZero on Go, Othello, and Atari Games (2023)
- **Link:** https://arxiv.org/abs/2310.11305 · **Venue:** IEEE Transactions on Games (accepted) · **Cited by:** 0 (OpenAlex) · **Read:** abstract only
- **Problem:** Which of AlphaZero, MuZero, Gumbel AlphaZero, Gumbel MuZero suits a given task.
- **Method:** Zero-knowledge framework supporting all four; introduces "progressive simulation" (increase the simulation budget during training).
- **Assumes:** Deterministic board games and Atari.
- **Claims:** Abstract only: more simulations generally help in 9x9 Go and 8x8 Othello; progressive simulation "performs significantly better" in the two board games. No numbers on the abstract page.
- **Evaluation:** 9x9 Go, 8x8 Othello, 57 Atari games.
- **Code:** released; abstract says "Our code and data are available" at rlg.iis.sinica.edu.tw/papers/minizero (not opened).
- **Fit:** partial. A usable benchmark for comparing small-budget search variants with released code; no stochastic or card-game content.

### A Gold-Standard Study of What Makes a Lightweight Game-Playing Agent Strong (2026)
- **Link:** https://arxiv.org/abs/2607.06854 · **Venue:** arXiv (Kelidari, Haghi, Salmani; cs.LG, cs.AI, cs.GT) · **Cited by:** 0 (OpenAlex) · **Read:** abstract only
- **Problem:** Self-play agents for imperfect-information card games look strong only against weak yardsticks (random, self).
- **Method:** Fixed rule-based Gin Rummy expert used only for evaluation; over 100 runs; encoders MLP, conv, set-based, attention, recurrent; baselines NFSP and information-set MCTS; Leduc Hold'em as a secondary check.
- **Assumes:** Two-player imperfect-information card game; compute and training budget not in the content read.
- **Claims:** The expert "beats every agent we trained 70 to 99 percent of the time". Agents "beat a random opponent over 99 percent of the time" (weak test). A self-play champion lifted "from about 30 to 36 percent against the expert" by stacking trust-region updates, reward, curriculum, warm start, and best-checkpoint keeping. Extra network capacity "does little to break the ceiling". Imitation learning/DAgger and reward shaping judged unhelpful.
- **Evaluation:** Gin Rummy vs fixed rule-based expert; Leduc.
- **Code:** abstract says a package is released; comments link a repository (not opened).
- **Fit:** partial. Relevant to measurement: it argues for evaluating against a fixed heuristic expert rather than random or self-play, which is our "beats the heuristic" test. It does not cover chance-node search or value nets.

### Policy Gradient Search: Online Planning and Expert Iteration without Search Trees (2019)
- **Link:** https://arxiv.org/abs/1904.03646 · **Venue:** arXiv (Anthony, Nishihara, Moritz, Salimans, Schulman) · **Cited by:** 14 (OpenAlex) · **Read:** abstract only
- **Problem:** MCTS stores a tree that does not scale to very large branching factors.
- **Method:** Updates a neural simulation policy online with policy gradients and uses no search tree; used inside expert iteration.
- **Assumes:** Hex; perfect information.
- **Claims:** Abstract only: "comparable performance" to MCTS in Hex; a PGS-based expert iteration agent "defeated MoHex 2.0" on 9x9 Hex. No win rates or budgets on the abstract page.
- **Evaluation:** 9x9 Hex.
- **Code:** none found (not checked).
- **Fit:** poor. No tree and no chance nodes; Hex only. Mentioned for completeness on tree-free search.

### On Reinforcement Learning for the Game of 2048 (2022 dissertation)
- **Link:** https://arxiv.org/abs/2212.11087 · **Venue:** PhD dissertation, NYCU (Hung Guei) · **Cited by:** 0 (OpenAlex) · **Read:** abstract only
- **Problem:** Learning-based play in 2048, a stochastic single-player puzzle.
- **Method:** Optimistic TD learning; n-tuple network ensembles; MCTS; deep RL (abstract lists these; search details not in the abstract).
- **Assumes:** Single-player stochastic puzzle with tile spawns; learned value tables.
- **Claims:** Abstract only: average score of "625,377 points" and "72%" rate of reaching the 32768 tile. Number of games and search settings are not given in the abstract.
- **Evaluation:** 2048.
- **Code:** none found (not checked).
- **Fit:** partial. A stochastic afterstate-style game with learned value functions, close to our structure, but the abstract gives no evaluation conditions.

### Self-Improvement for Neural Combinatorial Optimization: Sample without Replacement, but Improvement (2024)
- **Link:** https://arxiv.org/abs/2403.15180 · **Venue:** TMLR 06/2024 (Pirnay, Grimm) · **Cited by:** not checked · **Read:** abstract only
- **Problem:** Train constructive policies without expert data or costly policy-gradient runs.
- **Method:** Each epoch, sample multiple solutions per instance; the best becomes an expert trajectory for imitation; round-wise Stochastic Beam Search plus a policy update from a provable improvement result using sequence advantages.
- **Assumes:** Combinatorial optimisation (TSP, CVRP, JSSP); no games or chance.
- **Claims:** Abstract only: "comparable performance and generalization" to models trained on expert data; "outperform existing state-of-the-art methods by a wide margin" (JSSP). No numbers on the abstract page.
- **Evaluation:** TSP, CVRP, JSSP.
- **Code:** not checked.
- **Fit:** poor-partial. The idea of training on the best of a few sampled trajectories under a small sampling budget is transferable; the domain is not games and there are no chance nodes.

### Outer-Learning Framework for Playing Multi-Player Trick-Taking Card Games: A Case Study in Skat (2025)
- **Link:** https://arxiv.org/abs/2512.15435 · **Venue:** arXiv (Edelkamp; cs.AI) · **Cited by:** not checked · **Read:** abstract only
- **Problem:** Early-stage card decisions (bidding, game selection) in multi-player trick-taking games.
- **Method:** Bootstrapping outer-learning framework: expand a human-game database with "millions of self-playing AI games"; merge statistics into perfect-hash tables. No neural network named in the abstract.
- **Assumes:** Multi-player trick-taking card game with hidden hands.
- **Claims:** Abstract gives no numbers; claims "improved prediction accuracy".
- **Evaluation:** Skat.
- **Code:** not checked.
- **Fit:** poor. Table-based statistics, not search with a learned value; kept as a card-game reference.

---

## Leads seen but not opened (no card)

- **Gumbel MuZero for the Game of 2048** (Kao, Guei, Wu, Wu; TAAI 2022; https://doi.org/10.1109/taai57707.2022.00017). The IEEE page returned empty. A search snippet (unverified) says the authors "combine Gumbel MuZero and Stochastic MuZero, the first attempt to apply Gumbel MuZero to a stochastic environment" and report "an average score of 394,645 using only 3 simulations during training" on 2048. This is the closest precedent found for Gumbel-style search with chance nodes.
- **Revisiting Tree Search for LLMs: Gumbel and Sequential Halving** (arXiv 2603.21162). Search snippet only.

## Tool notes (for the next review)

- WebFetch cannot decode arxiv.org/pdf/... PDFs (returns binary). Use ar5iv.labs.arxiv.org/html/<id> or arxiv.org/html/<id> instead. Sources file currently lists arxiv.org/pdf-style links as the full-text route; that line needs the change.
- OpenReview forum and PDF pages return a verification screen, not the paper (Gumbel MuZero, Stochastic MuZero). The mirror above worked for Gumbel MuZero.
- mlanthology.org was blocked for WebFetch; IEEE Xplore returned empty.
- The arXiv export API works (http://export.arxiv.org/api/query): usable for keyword search and as the test in sources.md.
- OpenAlex works for arXiv records via doi:10.48550/arXiv.<id> lookup. Title-filter lookup returned nothing for ICLR-only papers (Gumbel MuZero, Stochastic MuZero), so their cited-by counts are unknown.
- The citation graph was thin: cites: filters for Multiagent Gumbel MuZero returned 4 works; ExIt's citers are mostly noisy without search terms.
