# Cards: value targets and their noise

Angle: Monte Carlo outcome targets vs TD(lambda) vs search-bootstrapped targets (TreeStrap, TDLeaf, AlphaZero/MuZero z vs q), off-policy value learning from a fixed behaviour policy, policy improvement from approximate values, action gap.

Scouted 2026-10-24. 13 papers opened: 6 full text (Bellemare 2016, TDLeaf, Giraffe, MuZero, Retrace, Kakade & Langford), 7 abstract or landing page only (Veness 2009, Stochastic MuZero, Bertsekas 2021, Kearns & Singh 2000, AVI 2026, UCT-Aux 2012, MMTO 2014).

---

### Bootstrapping from Game Tree Search (2009)
- **Link:** https://papers.nips.cc/paper/3722-bootstrapping-from-game-tree-search (PDF: https://proceedings.nips.cc/paper_files/paper/2009/file/389bc7bb1e1c2a5e7e147703232a88f6-Paper.pdf) · **Venue:** NeurIPS 2009 (NIPS 22), pp. 1937-1945 · **Cited by:** 52 (OpenAlex) · **Read:** abstract (the PDF body did not come through the fetch tool)
- **Problem:** Move a heuristic evaluation toward the value of a deep alpha-beta search, instead of toward a later search (TD-Leaf) or a game outcome.
- **Method:** TreeStrap. Per the abstract it updates every node of the search tree, not a single node, using the deep search value as the training signal. The exact update rule and target node were not readable.
- **Assumes:** Deterministic two-player chess (Meep), linear evaluation, self-play from small random weights. No chance nodes mentioned.
- **Claims:** Abstract: Meep "played at a master level" in online games against humans, "the best performance of any chess program with a heuristic learned entirely from self-play." No numbers in what I could read.
- **Evaluation:** Chess (Meep), self-play training, then online play against humans.
- **Code:** not checked.
- **Fit:** partial. It is the named method for search-bootstrapped targets on every node, which is the angle exactly. It breaks the stochastic constraint (no chance nodes) and says nothing on generalisation to unseen items.

---

### TDLeaf(lambda): Combining Temporal Difference Learning with Game-Tree Search (1998 / arXiv 1999)
- **Link:** https://arxiv.org/abs/cs/9901001 (full text: https://ar5iv.labs.arxiv.org/html/cs/9901001) · **Venue:** ACNN'98 and Australian J. Intelligent Information Processing Systems 1998; companion KnightCap paper ICML'98 (cs/9901002) · **Cited by:** not checked · **Read:** full text (ar5iv)
- **Problem:** Train an evaluation with TD(lambda) when the value that matters is the minimax result at the root, not the static value of the game's own positions.
- **Method:** TD(lambda) applied to the leaves of the principal variation. The root value is the leaf value of the principal variation. Update: w := w + alpha * sum_t grad J(x_t, w) * [sum_j lambda^(j-t) d_t], with d_t = J(x_{t+1}) - J(x_t) computed on leaves. KnightCap used lambda = 0.7, alpha = 1.0.
- **Assumes:** Deterministic perfect-information games. Chess used 5-10 ply search; backgammon used 2-ply. Linear material-based evaluation at start. Training against human opponents on FICS.
- **Claims:** "After only 308 games, KnightCap's rating climbed to 2110±50" (ar5iv text; the abstract says 2100). Start 1650±50. TD-directed rose about 200 points over about 300 games, which is slower. Backgammon (the one stochastic test): TDLeaf and TD-directed each trained 50,000 games, then played 1,600 games at two-ply, with "no statistically significant change in performance being observed." Two-ply beat one-ply by 0.25 points per game.
- **Evaluation:** FICS blitz games against humans (chess). FIBS-initialised weights, 1,600-game match (backgammon).
- **Code:** not checked.
- **Fit:** partial. It targets search values on the search's leaves, which matches our search-bootstrapped idea. Its one stochastic test (backgammon) gave no measurable gain, which is directly relevant to chance nodes. Deterministic chess is the main evidence.

---

### Giraffe: Using Deep Reinforcement Learning to Play Chess (2015)
- **Link:** https://arxiv.org/abs/1509.01549 · **Venue:** MSc thesis, Imperial College London (arXiv) · **Cited by:** 68 (OpenAlex) · **Read:** full text (ar5iv; first 100,000 of about 125,700 characters)
- **Problem:** Learn a chess evaluation network without hand-made features and without game-outcome labels.
- **Method:** TD-Leaf(lambda) training of a deep network. The target is the network's own search value at later times, not a label. Uses an L1 loss because "TD-Leaf generates errors with many outliers, and they would completely dominate L2 loss." SGD with AdaDelta; lambda = 0.7, alpha = 1.
- **Assumes:** Deterministic chess. Positions taken from computer games with random legal moves: "5 million positions randomly" and "about 175 million positions" in total. Each iteration samples 256 positions. Initialised from a material-only evaluation. Search depth and time per move in training were not in the part I read.
- **Claims:** Strategic Test Suite (15,000-point scale) rose from "about 6,000 with the material-only bootstrap" to "about 9,500", with peaks above 9,700. Table 3 (0.1 s/position): Giraffe (1s) 9641, Giraffe (0.1s) 8526, Stockfish 5 10505 (108,540 nodes on average). Abstract: "approximately the level of an FIDE International Master." Naive probability-limited search was "slightly" stronger by 26±12 Elo (53%-47%).
- **Evaluation:** Strategic Test Suite and timed search comparisons. Playing-strength tests were not read in detail.
- **Code:** not checked.
- **Fit:** partial. A deep net trained only on search-bootstrapped TD-leaf targets, with an explicit choice (L1) for noisy targets. Breaks the CPU-hours constraint at 175M positions as stated, and is chess-only and deterministic.

---

### Planning in Stochastic Environments with a Learned Model (ICLR 2022; Stochastic MuZero)
- **Link:** https://iclr.cc/virtual/2022/poster/6832 · **Venue:** ICLR 2022 (poster) · **Cited by:** not checked · **Read:** abstract (poster page; full paper not read)
- **Problem:** MuZero-style planning when the environment is stochastic. Earlier MuZero variants used only deterministic models.
- **Method:** Learns a stochastic model that incorporates afterstates, and runs a stochastic tree search on it. Value-target details were not readable.
- **Assumes:** A learned latent model; stochastic transitions; neural networks. Discrete or continuous latent details not read.
- **Claims:** "matched or exceeded the state of the art in a set of canonical single and multi-agent environments, including 2048 and backgammon, while maintaining the same performance as standard MuZero in the game of Go." No numbers on the page.
- **Evaluation:** 2048, backgammon, Go (per abstract).
- **Code:** not checked.
- **Fit:** partial. Structurally the closest match to our afterstate-plus-chance-node expectimax, but only the abstract was read, there are no numbers, and it is a large neural model. Note: arXiv:2104.06303 is a different paper (Sampled MuZero), so cite by the ICLR listing.

---

### Lessons from AlphaZero for Optimal, Model Predictive, and Adaptive Control (2021)
- **Link:** https://arxiv.org/abs/2108.10315 · **Venue:** arXiv (v2 withdrawn by author; a book version followed in 2022) · **Cited by:** 37 (OpenAlex) · **Read:** abstract (arXiv abs page)
- **Problem:** Explain why online decision-making on top of offline training improves performance.
- **Method:** Online play with multistep lookahead and a terminal evaluator trained from offline experience, framed as approximation in value space plus rollout. A Newton-step interpretation appears in a secondary mirror, not in the arXiv abstract I read.
- **Assumes:** Finite-horizon optimal control, deterministic and stochastic, discrete and continuous spaces. Analysis "often based on visualization."
- **Claims:** None quantified in the abstract. It aims to explain "the beneficial effects of on-line decision making on top of off-line training."
- **Evaluation:** None in the abstract.
- **Code:** none found in the abstract page (not searched further).
- **Fit:** partial. Gives the policy-improvement logic for one-step or multistep lookahead over a learned value, which is the question "search with the net does no better than the heuristic." No card-game or stochastic experiment.

---

### Approximately Optimal Approximate Reinforcement Learning (ICML 2002)
- **Link:** https://hunch.net/~jl/projects/aoarl/Final.tex_back (LaTeX source copy of the paper; the publisher page was not used) · **Venue:** ICML 2002 · **Cited by:** not checked · **Read:** full text (source)
- **Problem:** Guarantees for policy improvement when the policy is chosen by an approximate greedy chooser.
- **Method:** Conservative Policy Iteration. Each step calls an approximate greedy chooser G_eps(pi, mu) for pi', estimates the advantage A(pi') by sampling restarts from mu, then mixes pi_new = (1-alpha) pi + alpha pi', with alpha = (1-gamma)(A_hat - eps/3)/(4R).
- **Assumes:** Finite states and actions, rewards in [0, R], gamma < 1, a restart distribution mu the learner can sample from, known eps. A regression fit with average l1 advantage error of at most eps/2 is said to suffice for G_eps.
- **Claims:** Each update improves eta_mu by at least eps^2/(72R) (Theorem 2). Terminates after at most 72R^2/eps^2 calls to G_eps. Returned policy has OPT(A_{pi,mu}) < 2 eps, with probability at least 1-delta. Corollary 2: if A >= 0 and alpha = (1-gamma)A/(4R), improvement is at least A^2/(8R). Mismatch bound (Theorem 3): eta_mu~(pi*) - eta_mu~(pi) <= (eps/(1-gamma)^2) * ||d_{pi*,mu~}/mu||_inf.
- **Evaluation:** None (theory only).
- **Code:** none needed for the theory.
- **Fit:** partial. The one card here that bounds improvement in terms of approximation error and distribution mismatch, which is the policy-improvement angle. Bounds are loose, and the method needs restart sampling from a fixed distribution plus per-step advantage estimates.

---

### Increasing the Action Gap: New Operators for Reinforcement Learning (2016)
- **Link:** https://arxiv.org/abs/1512.04860 · **Venue:** AAAI 2016 · **Cited by:** 39 (OpenAlex) · **Read:** full text (ar5iv and arXiv PDF)
- **Problem:** Make the greedy action more robust to estimation and approximation error in the learned value.
- **Method:** Consistent Bellman operator, T_c Q(x,a) = R(x,a) + gamma E[ 1[x'!=x] max_b Q(x',b) + 1[x'=x] Q(x,a) ]. Equivalent to T Q - gamma P(x|x,a)[V(x) - Q(x,a)]. Theorem 1: an operator T' is optimality-preserving and gap-increasing if T Q - alpha[V - Q] <= T' Q <= T Q for some alpha in [0,1). Holds when Q is represented exactly.
- **Assumes:** Tabular proofs. Atari with DQN-style networks. Discretised continuous control (bicycle, value iteration on a 10x...x10 grid over 6 dimensions, gamma = 0.99).
- **Claims:** Stochastic minimal setting (100M frames): advantage learning (A.L.) and persistent advantage learning (P.A.L.) are statistically better than DQN on 37 and 35 of 60 games. Original DQN setting (200M frames): median improvement over DQN 8.4% (A.L.) and 9.1% (P.A.L.); average 27.0% and 32.5%. Times best: Bellman 12, A.L. 21, P.A.L. 31. The paper gives no numeric success rate for the bicycle task (only in figures).
- **Evaluation:** ALE, 60 games, paired t-tests at 99% over 10 trials per game; alpha tuned on 5 games (Asterix, Beam Rider, Pong, Seaquest, Space Invaders).
- **Code:** not checked.
- **Fit:** partial. The action-gap idea is the angle directly, and its stated purpose (robustness to estimation error) fits a learned net. The guarantee is tabular and the evidence is GPU-scale Atari, so the CPU-hours constraint is not met by the evidence.

---

### Safe and Efficient Off-Policy Reinforcement Learning (2016; Retrace)
- **Link:** https://arxiv.org/abs/1606.02647 (full text: https://ar5iv.labs.arxiv.org/html/1606.02647) · **Venue:** NeurIPS 2016 · **Cited by:** 321 (OpenAlex) · **Read:** full text (ar5iv)
- **Problem:** Multi-step off-policy value targets that are low-variance, safe for any behaviour policy, and efficient for near on-policy data.
- **Method:** Retrace(lambda). Trace coefficient c_s = lambda * min(1, pi/mu). Target: Q + E_mu[ sum_t gamma^t (prod_{s<=t} c_s) (r_t + gamma E_pi Q(x_{t+1}, .) - Q(x_t, a_t)) ].
- **Assumes:** Finite MDP for proofs. Tabular operators. Any behaviour policy mu for evaluation. Control needs Markovian traces and asymptotically commuting operators; GLIE not required.
- **Claims:** Theorem 1: gamma-contraction for policy evaluation for any mu, when 0 <= c_s <= pi/mu. Theorem 3: online control converges a.s. to Q* without GLIE, under Robbins-Munro step sizes. Atari, average scores at lambda = 1.0: DQN 0.6839, TB 0.8158, Retrace 0.8698, Q* 0.04317. Times best over 60 games: TB 16, Retrace 30, DQN 12, Q* 2. Inconsistency: the text says "Retrace always achieve a score higher than TB," but Table 2 at lambda = 0 gives TB 0.5512 vs Retrace 0.4288.
- **Evaluation:** 60 Atari 2600 games, 4 seeds, 3e8 frames, 16 threads with per-thread replay of 62,500 transitions.
- **Code:** a PyTorch port is listed at https://github.com/ALRhub/Retrace-PyTorch (seen in a search result, not opened, licence not checked).
- **Fit:** partial. Directly on off-policy value learning from a fixed behaviour policy (for example a heuristic that generated the data). The variance argument is qualitative, and the evidence is deep Q-learning on Atari, not a CPU-scale setting.

---

### Bias-Variance Error Bounds for Temporal Difference Updates (2000)
- **Link:** https://mlanthology.org/colt/2000/kearns2000colt-bias (the Penn PDF https://www.cis.upenn.edu/~mkearns/papers/tdlambda.pdf was rejected with a certificate error) · **Venue:** COLT 2000, pp. 142-147 · **Cited by:** not checked · **Read:** abstract (mlanthology page)
- **Problem:** How the backup length k (or lambda) trades bias against variance in TD policy evaluation.
- **Method:** Error upper bounds for phased TD variants, as experience grows, with k-step or lambda backups.
- **Assumes:** Fixed-policy evaluation in an unknown MDP. Phased learning rates. Finite setting not confirmed from the page.
- **Claims:** "These upper bounds prove exponentially fast convergence." "both the rate of convergence and the asymptote strongly dependent on the length of the backups k." Schedules for k and the second parameter "predicted to be better than any fixed values." No numbers read.
- **Evaluation:** Preliminary experiment on a random walk.
- **Code:** none found.
- **Fit:** partial. Formal support for the bias-variance intuition, which is the noise question, but for fixed-policy evaluation with no chance nodes or search, and no quantitative results read.

---

### The Surprising Effectiveness of Approximate Value Iteration in Self-Play (2026 preprint)
- **Link:** https://arxiv.org/abs/2609.09094 · **Venue:** arXiv (cs.AI), submitted 8 Sept 2026 · **Cited by:** 0 (OpenAlex) · **Read:** abstract (arXiv abs page; paraphrased by the fetch tool)
- **Problem:** Are simple self-play approximate value iteration (AVI) methods competitive with MCTS-based training?
- **Method:** Minimal self-play AVI. One-step lookahead on the learned value gives the policy (no MCTS). Targets are presumably value-iteration backups, not MCTS search values (inferred, not stated).
- **Assumes:** Two-player zero-sum perfect-information board games.
- **Claims:** AVI "learns more accurate value functions than those learned by AlphaZero," measured against ground-truth oracles (no numbers in the abstract). One-step-lookahead greedy policies "remain competitive with MCTS-based policies" at "substantially lower training and inference costs" (no numbers).
- **Evaluation:** Connect Four, Hex 7x7, synthetic games. Othello and Go 9x9 only "preliminary."
- **Code:** not checked.
- **Fit:** partial. Speaks to one-step lookahead on a learned value versus search-bootstrapped targets. Board games only, no chance nodes, no quantitative claims read, and the preprint is very new.

---

### Bootstrapping Monte Carlo Tree Search with an Imperfect Heuristic (2012)
- **Link:** https://arxiv.org/abs/1206.5940 · **Venue:** ECML'12 (arXiv) · **Cited by:** 0 (OpenAlex) · **Read:** abstract (arXiv abs page)
- **Problem:** Use an imperfect heuristic policy to improve UCT value estimates in MDP-style planning with large state spaces.
- **Method:** UCT-Aux. Each internal node gets an extra "auxiliary" arm whose rollouts use the heuristic policy. Standard UCT elsewhere. The page does not say whether the heuristic is a prior, a leaf value, or trained.
- **Assumes:** Non-adversarial MDP planning, with the heuristic optimal in some regions.
- **Claims:** Only qualitative: UCT-Aux "performs better compared to the original UCT algorithm and its variants" in "two benchmark experiment settings." No numbers read.
- **Evaluation:** Two unnamed benchmark settings.
- **Code:** not checked.
- **Fit:** partial. Treats a hand-written heuristic as a search component and limits how far the search departs from it, which is the baseline in our problem. It is MCTS on MDPs, not expectimax, and gives no numbers.

---

### Large-Scale Optimization for Evaluation Functions with Minimax Search (2014)
- **Link:** https://www.jair.org/index.php/jair/article/view/10871 (DOI 10.1613/jair.4217) · **Venue:** JAIR vol. 49, 2014 · **Cited by:** 35 (OpenAlex) · **Read:** abstract (landing page; paraphrased by the fetch tool)
- **Problem:** Tune an alpha-beta evaluation function from expert game records.
- **Method:** Minimax Tree Optimization (MMTO). An objective that makes minimax search results agree with expert moves in the records, minimised by a numerical iterative method. The objective's exact form was not read.
- **Assumes:** Alpha-beta search program. Linear or nonlinear weighted features. "more than forty million parameters" adjusted with a small number of hyperparameters. Shogi, with preliminary chess evidence.
- **Claims:** Performs "significantly better than other methods" (no figures on the landing page). Bonanza finished first at the 2013 World Computer Shogi Championship (per the abstract).
- **Evaluation:** Shogi expert game records; 2013 WCSC.
- **Code:** not checked.
- **Fit:** partial. The target is expert-move agreement through search, not outcomes, which is a third target type for the angle. It needs records, not self-play, and no numbers were read.

---

## Leads not carded (not opened)

- Silver et al. 2012, "Temporal-difference search in computer Go" (Machine Learning). OpenAlex W2153039919, 93 cited. The Springer page redirected to a login, and OpenAlex has no abstract. Not opened.
- Willemsen, Baier, Kaisers 2021, "Value targets in off-policy AlphaZero: a new greedy backup" (Neural Computing and Applications 34). Directly on value targets (original z target vs soft-Z, A0C, greedy backup). OpenAlex W3170943554, 8 cited. The Springer PDF redirected to a login, and OpenAlex has no abstract. Not opened. High priority to get by another route.
- Nau 1983 and Wilson, Parker, Nau 2009 on minimax pathology with approximate evaluations. The umd.edu PDF was rejected with a certificate error. Not opened.
- Non-paper, informal (search snippets only, not opened): Doron Singer's DEV Community blog series reports that self-play with outcome labels "struggled, because a single played line gave every leaf in the tree the same label." The sts-rl-agent Hugging Face page reports a combat value net with 1-ply lookahead reaching "only about floor 8," and "six attempts to distill MCTS combat into a feed-forward network all failed." Both are on-angle but unverified.

## Source notes for the next sources review

- arxiv.org/abs and ar5iv.labs.arxiv.org/html worked. Full text for Bellemare, TDLeaf, Giraffe, MuZero, Retrace.
- OpenAlex: `filter=cites:` and `filter=doi:` worked through WebFetch. `abstract_inverted_index` came back null for the Springer papers (Willemsen 2021, Silver 2012).
- Springer (link.springer.com) redirects to idp.springer.com (login). Not followed.
- cis.upenn.edu and umd.edu PDFs: "certificate rejected."
- NeurIPS proceedings PDF: body unreadable by the fetch tool, only abstract.
- Semantic Scholar not tried for this angle.
