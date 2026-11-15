# Cards: CPU-efficient learned evaluation for search engines

Angle: NNUE and small nets in engines, Texel-style tuning from outcomes, hand-crafted plus learned correction, distilling search into small nets.
Opened: 13 (full text: 4; abstract or landing page: 8; practitioner wiki: 1). The Stockfish nnue-pytorch docs page (`docs/nnue.md`) was truncated on fetch, so it has no card.

---

### Rapfi: Distilling Efficient Neural Network for the Game of Gomoku (2025)
- **Link:** https://arxiv.org/html/2503.13178 (arXiv 2503.13178v1) · **Venue:** arXiv preprint · **Cited by:** not checked · **Read:** full text
- **Problem:** Strong Gomoku play under CPU-only compute, where large CNNs need GPUs.
- **Method:** "Mixnet": per-point directional line patterns (length 11) are mapped through a trained network, exported losslessly into a pattern-indexed codebook, and summed. A stone change updates at most 4×11 directional features through an accumulator of deltas, which is the incremental-update idea behind NNUE. Trained with cross-entropy plus distillation from a ResNet 6b128f teacher (75% distillation labels, 25% true labels).
- **Assumes:** Perfect-information board game; CPU with AVX2 SIMD, no GPU; 16-bit codebook and 8-bit linear layers in the value head; about 30.8M training positions from KataGo self-play with win/loss/draw targets; Adam, lr 0.001, batch 128, 600k iterations.
- **Claims:** Mixnet Small: 47,575 MCTS playouts/s, 428K α-β nodes/s, 51 kFLOPs. Mixnet Large: 18,401 playouts/s, 104K nodes/s, 381 kFLOPs. ResNet 20b256f: 11 playouts/s, 32 nodes/s, 23,631 kFLOPs. Versus ResNet under MCTS with fixed time, MixNet leads by "300–400 ELO, a win rate of 85%–92%". AVX2 gives "about 4x speedup over a non-vectorized build". Validation value/policy loss: Mixnet Large 0.7632 / 1.166; ResNet 20b256f 0.7181 / 0.7969.
- **Evaluation:** Time-controlled games (2 s to 20 s per move), 400 games per pairing, balanced book openings. Ablations of star block, value grouping, and dynamic convolution. Authors say it won GomoCup 2024 and ranked first among 520 agents on Botzone.
- **Code:** none found (the only linked repo is a KataGo fork, not Rapfi itself; license not stated).
- **Fit:** good for CPU-efficient learned eval with incremental updates and distillation from a teacher. Breaks on the generalisation goal: there are no unseen-card or unseen-rule tests, and the input is a fixed board.

---

### Study of the Proper NNUE Dataset (2024)
- **Link:** https://arxiv.org/abs/2412.17948 (full text read at https://arxiv.org/html/2412.17948) · **Venue:** arXiv preprint (cs.AI) · **Cited by:** 0 (OpenAlex) · **Read:** full text
- **Problem:** NNUE training sets are poorly documented; random position/score pairs train poorly.
- **Method:** Xiangqi NNUE. Positions come from about 44,000 grandmaster games (DPXQ and WXF, 2008–2024) plus 30,000 synthetic self-play games. A position is kept only if |static eval − quiescence| ≤ 60 cp and |static eval − negamax| ≤ 70 cp. Labels are the static eval of a hand-crafted piece-square-table function. Game outcomes are not used as labels. Diversity targets: 50/50 positive/negative side-to-move values, at least 50% of values in [-100, 100], at least 40% with |value| > 100.
- **Assumes:** Xiangqi, perfect information. Inputs 1620 per side (3240 total). Net is about 0.6 MB. Text says hidden size 256, but code shows Linear(1620, 128) and Linear(256, 1), so the text and code disagree. CPU/GPU and training hyperparameters not stated.
- **Claims:** "About +100 Elo over the previous handcrafted (piece-square-table) evaluation." Won 65% of games against the previous handcrafted version (game count not stated). No numbers for the Elephant Eye variant.
- **Evaluation:** Head-to-head matches against the earlier handcrafted engine version.
- **Code:** none stated; no license mentioned.
- **Fit:** partial. Useful as evidence that the data-selection rule (keep positions where cheap evaluators agree) matters more than raw volume. Breaks on the generalisation goal and on outcome-based labels: it uses no outcomes at all.

---

### Residual Policy Learning (2018)
- **Link:** https://arxiv.org/abs/1812.06298 · **Venue:** arXiv preprint (cs.RO, cross-listed cs.LG) · **Cited by:** 113 (OpenAlex) · **Read:** abstract
- **Problem:** Improve imperfect hand-designed or MPC controllers on long-horizon, sparse-reward manipulation, where RL from scratch is "data-inefficient or intractable".
- **Method:** Model-free deep RL learns a residual added to an initial controller. The base controller is hand-designed or model-predictive (known or learned transition model). The page does not say explicitly that the base is frozen.
- **Assumes:** A "good but imperfect" base controller exists. Continuous control. Six MuJoCo tasks with partial observability, sensor noise, model misspecification, and controller miscalibration. The page names no RL algorithm or residual architecture.
- **Claims:** "consistently and substantially improves on the initial controllers" and can solve long-horizon, sparse-reward tasks where RL alone fails. No numbers on the abstract page.
- **Evaluation:** Six MuJoCo manipulation tasks (per abstract).
- **Code:** project page https://k-r-allen.github.io/residual-policy-learning/ ("Video and code"); no code license stated.
- **Fit:** partial. It states the heuristic-plus-learned-residual structure directly, which matches the angle. It breaks on the setting: continuous control, no search, no discrete card effects, and no numbers I could read.

---

### Giraffe: Using Deep Reinforcement Learning to Play Chess (2015)
- **Link:** https://arxiv.org/abs/1509.01549 · **Venue:** arXiv (MSc dissertation, Matthew Lai) · **Cited by:** not checked · **Read:** abstract (PDF fetch returned compressed binary, so no full text)
- **Problem:** Learn the chess evaluation by self-play with feature extraction and pattern recognition, rather than tuning a hand-crafted function.
- **Method:** Not on the abstract page (network size, inputs, TD vs outcome target not visible).
- **Assumes:** Chess, self-play. Hardware not stated on the page.
- **Claims:** Evaluation "performs comparably to the evaluation functions of state-of-the-art chess engines." No numbers.
- **Evaluation:** Not described on the page.
- **Code:** none found on the page.
- **Fit:** partial. Relevant to CPU-scale nets with search-leaf learning, but I could not read the method or numbers. Treat the claim as unverified.

---

### Thinking Fast and Slow with Deep Learning and Tree Search (2017)
- **Link:** https://arxiv.org/html/1705.08439v4 (abstract: https://arxiv.org/abs/1705.08439) · **Venue:** arXiv (Expert Iteration, ExIt) · **Cited by:** 198 (OpenAlex) · **Read:** full text
- **Problem:** Train a network to imitate tree search (planning) and use it to guide later search.
- **Method:** Expert Iteration. The apprentice net plays self-play; the MCTS expert labels the states; a new apprentice is trained on the pairs; the expert is rebuilt with the apprentice guiding search. Policy target is the root visit distribution n(s,a)/n(s) with n(s)=10,000. The value head uses a KL/cross-entropy loss against the binary game result z. The expert's value is approximated by the apprentice's value, because Monte Carlo estimates of the expert were too costly.
- **Assumes:** 9×9 Hex; 13 conv layers with ELU, mostly 64 hexagonal 3×3 filters; Adam, minibatch 250; GPU is used (Intel Xeon E5-1620 with nVidia Titan X); the expert runs 10,000 MCTS iterations per move; total training time not reported.
- **Claims:** Imitation top-1 error CAT 47.0% vs TPT 47.7%, and TPT was "50±13 Elo" stronger. Three DAgger batches of 100,000 moves gave "120 Elo" over the first TPT net. The policy-network N-MCTS won 97% against vanilla MCTS, at about a 2× search slowdown. ExIt (10k iterations) won 75.3% against 10k-iteration MoHex and 55.6% against MoHex at 4 s/move. The authors say they "cannot say whether it exceeds" state of the art on larger boards.
- **Evaluation:** 9×9 Hex vs MoHex 1.0 and REINFORCE (Figure 2, 5 runs, 90% CI).
- **Code:** none stated; only the arXiv license for the paper.
- **Fit:** partial. The value-target choice (apprentice value in place of an expensive expert value) is directly useful for the problem's search-to-net labels. It breaks on the constraints: the paper relies on GPU, and it has no stochastic or chance nodes.

---

### Large-Scale Optimization for Evaluation Functions with Minimax Search (2014)
- **Link:** https://www.jair.org/index.php/jair/article/view/10871 (DOI 10.1613/jair.4217) · **Venue:** JAIR vol. 49 · **Cited by:** 35 (OpenAlex) · **Read:** abstract (JAIR landing page)
- **Problem:** Tune a heuristic evaluator of an alpha-beta search program at large scale, using game records.
- **Method:** Minimax Tree Optimization (MMTO). Linear or non-linear weighted features are fitted so that the search's move choices match expert game records. The objective is designed to control search results. A numerical iterative method finds local minima; the optimizer is not named.
- **Assumes:** Shogi (Bonanza), with chess only as "preliminary evidence". Human expert game records, not outcomes. More than 40 million parameters, tuned with a few hyperparameters. Hardware not stated.
- **Claims:** Improves playing strength; Bonanza won the 2013 World Computer Shogi Championship. "more than forty million parameters are adjusted by using a small number of hyper parameters." No Elo or win rates on the page.
- **Evaluation:** Shogi game records; tournament results.
- **Code:** none on the page.
- **Fit:** partial. It is the clearest large-scale Texel-style precedent, and it shows a heuristic can be tuned by search-consistency. It breaks on the labels (human moves, not outcomes) and on the generalisation goal: it tunes fixed features, not unseen cards.

---

### Learning Position Evaluation Functions Used in Monte Carlo Softmax Search (2019)
- **Link:** https://arxiv.org/abs/1901.10706 · **Venue:** arXiv preprint (cs.AI, cs.LG cross-list; v2 2020) · **Cited by:** not checked · **Read:** abstract
- **Problem:** Learn the evaluation used inside a selective search (Monte Carlo softmax search), with fewer games.
- **Method:** Separates node-selection from backup policies. Evaluation is learned from Monte Carlo sampling done with the backup policy, drawing on the principal variation and important internal nodes. Combines modified supervised, RL, regression, and search-bootstrapping learning rules.
- **Assumes:** Game(s) and hardware not named on the page.
- **Claims:** Qualitative only. Sampling "reduces the number of games necessary for learning", with no figures. Principal variation "matches that of a minimax search", with no experimental figures.
- **Evaluation:** Not given on the page.
- **Code:** none found on the page.
- **Fit:** poor. The idea (learn leaf evaluation from search-sampled positions) matches the angle, but the page has no numbers, game, or code to check.

---

### Re-determinizing Information Set Monte Carlo Tree Search in Hanabi (2019)
- **Link:** https://arxiv.org/abs/1902.06075 · **Venue:** arXiv preprint (CIG 2018 Hanabi competition entry) · **Cited by:** not checked · **Read:** abstract
- **Problem:** Standard IS-MCTS can leak hidden information into opponent models, "particularly severe in Hanabi". The fix is re-determinization.
- **Method:** Re-determinizing IS-MCTS. A Bayesian opponent model is updated during the game (Mixed track). A learned evaluation function estimates leaf values so full simulations are avoided. The page does not describe how the value net is trained or its architecture.
- **Assumes:** Imperfect information; 40 ms per move (competition limit); hardware not stated.
- **Claims:** "scores higher in Hanabi for 2-4 players than previously published work at the time of the competition". No score values on the page.
- **Evaluation:** CIG 2018 Hanabi competition, Mixed track. No match counts.
- **Code:** none linked; arXiv license only.
- **Fit:** partial. It handles hidden information without peeking, which the problem's constraint needs, but it gives no detail on the learned evaluator.

---

### Statistical Feature Combination for the Evaluation of Game Positions (1995)
- **Link:** https://arxiv.org/abs/cs/9512106 (JAIR vol. 3, doi 10.1613/jair.179) · **Venue:** JAIR · **Cited by:** 23 (OpenAlex, JAIR entry) · **Read:** abstract
- **Problem:** Combine evaluation features into one function with weights that carry the same meaning across all game phases (Othello).
- **Method:** Fits feature weights from "a large number of classified Othello positions", comparing logistic regression, Fisher's linear discriminant, and the quadratic discriminant. Logistic regression is described as used "for the first time in the context of game playing". The page does not say how positions were classified.
- **Assumes:** Othello; features roughly normal for the quadratic version; classified positions representative enough.
- **Claims:** Logistic regression "leads to better results than the other approaches" (tournaments against a world-class Othello program). No numbers on the page.
- **Evaluation:** Tournaments between the resulting program versions.
- **Code:** none named; the abstract points to JAIR files.
- **Fit:** good for the concept, since it is the earliest outcome-fitted feature-weight method that matches Texel-style tuning. It is partial on evidence: no numbers were visible, and the page does not say whether outcomes were the labels.

---

### TDLeaf(lambda): Combining Temporal Difference Learning with Game-Tree Search (1999)
- **Link:** https://arxiv.org/abs/cs/9901001 · **Venue:** arXiv (also ACNN'98; Australian J. Intelligent Information Processing Systems 1998) · **Cited by:** 27 (OpenAlex) · **Read:** abstract
- **Problem:** Use TD(lambda) with minimax search, so the learner updates the evaluation from the search result.
- **Method:** TDLeaf(lambda), a variant of TD(lambda) applied to the leaves of the minimax search. The page does not explain the leaf update in detail.
- **Assumes:** Chess (KnightCap) and backgammon. Hardware not stated.
- **Claims:** KnightCap "improved from a 1650 rating to a 2100 rating in 308 games" on FICS. Backgammon results mentioned but no numbers.
- **Evaluation:** Live play on the Free Internet Chess Server; opponents not described.
- **Code:** none linked.
- **Fit:** partial. It learns the eval from game outcomes through search leaves, which fits the angle. It breaks on chance nodes (chess only) and gives no numbers on the setup.

---

### Bootstrapping from Game Tree Search (2009)
- **Link:** https://papers.nips.cc/paper/3722-bootstrapping-from-game-tree-search · **Venue:** NIPS 2009 (NeurIPS 22) · **Cited by:** 52 (OpenAlex) · **Read:** abstract (PDF linked but not read)
- **Problem:** Learn the parameters of a heuristic evaluation for a game program from search results.
- **Method:** Search Bootstrapping. The heuristic is updated "towards the values computed by an alpha-beta search" at all nodes of the tree, using the outcome of a deep search rather than a later search (as Samuel's checkers player and TD-Leaf do). The learner is a linear heuristic (feature set not described).
- **Assumes:** Chess (Meep), self-play only, weights initialised to small random values, alpha-beta search at "deep" depth (exact depth not given on the page).
- **Claims:** The learned heuristic gave "the best performance of any chess program with a heuristic learned entirely from self-play", and Meep "played at a master level" online. No Elo or game counts on the page.
- **Evaluation:** Online play against human opponents (per abstract).
- **Code:** none on the page.
- **Fit:** good for the mechanism: regress a small evaluator onto search values, with the search as teacher. Partial on evidence: no numbers were visible, and it does not cover chance nodes or unseen items.

---

### Mastering 2048 with Delayed Temporal Coherence Learning, Multi-Stage Weight Promotion, Redundant Encoding and Carousel Shaping (2016)
- **Link:** https://arxiv.org/abs/1604.05085 (full text read at https://ar5iv.labs.arxiv.org/html/1604.05085) · **Venue:** arXiv (journal version: IEEE TCIAIG 2017) · **Cited by:** 30 (OpenAlex, TCIAIG version) · **Read:** full text
- **Problem:** Build a strong 2048 player. It is a single-player nondeterministic puzzle framed as an MDP.
- **Method:** TD learning of afterstate values with n-tuple networks (lookup tables over tile patterns). Adds delayed TD(λ), temporal coherence learning for per-weight rates, multi-stage weight promotion, carousel shaping, and redundant encoding. At play time it uses expectimax with iterative deepening and transposition tables, over the learned afterstate value.
- **Assumes:** Java learning code on 2× AMD Opteron 6234 (24 cores, 64 GB RAM), lock-free parallel updates on 24 threads. Eval search single-threaded on an i7-4770K at 3.5 GHz. Budget 10^10 actions, about 10^7 episodes, 1 to 7 days per run, 5 repeats. The 4-tuple/6-tuple baseline has 4×16^6 = 67,108,864 parameters; the 16-stage net has 1,073,741,824.
- **Claims:** Final network, 1-ply: average 324,710 (±11,043); 32768 / 16384 / 8192 tile rates 19% / 68% / 90%; 258,371 moves/s. 3-ply: average 511,759 (±12,021); 50% / 92% / 99%; 1,484 moves/s. 1000 ms per move (100 games): average 609,104 (±38,433); 32768 in 70%. The conclusion says the controller "scores more than 600 000 points on average and achieves the 32 768-tile in 70% of games".
- **Evaluation:** 2048, 1000 games per setting unless noted; fixed depths 1, 2, 3, 5 ply, and per-move time limits from 1 ms to 1000 ms.
- **Code:** https://github.com/wjaskowski/mastering-2048 (Java learning code); https://github.com/aszczepanski/2048 (C++ best player). License not stated in the paper.
- **Fit:** good on structure. It is a CPU-only, stochastic (chance-node) game with expectimax over learned afterstate values, which is the problem's setting. It breaks on generalisation: n-tuple tables are fixed to board patterns and do not transfer to unseen cards.

---

### Stockfish NNUE: Chess Programming Wiki reference (practitioner wiki, 2020s)
- **Link:** https://www.chessprogramming.org/NNUE · **Venue:** Chess Programming Wiki (secondary; cites Nasu 2018 for the shogi original, not opened) · **Cited by:** n/a · **Read:** page (wiki)
- **Problem:** Engine evaluation that stays cheap on CPU during search, with incremental updates.
- **Method:** Input is 768 binary features (6 piece types × 2 colours × 64 squares). Each side has its own accumulator, the first hidden layer, with shared weights and a flipped view for Black. Later layers are small and dense. Activations are ReLU, CReLU, or SCReLU. Weights are trained as floats and quantized to integers, with common 2024 constants SCALE 400, QA 255, QB 64. Incremental updates: a quiet move changes 2 input neurons, a capture 3, and castling 4. Full refresh is needed at king-bucket or mirror crossings.
- **Assumes:** Chess (perfect information), CPU with SIMD, integer arithmetic, incremental make/unmake or copy-make.
- **Claims:** "The only speed figure" is that Stockfish's search speed was "approximately halved" after NNUE, yet it became stronger. The target is a linear interpolation between the game result (0, 0.5, 1) and sigmoid(eval/eval_scale).
- **Evaluation:** None on the page.
- **Code:** none checked (the nnue-pytorch docs were truncated on fetch).
- **Fit:** good as a mechanism reference: sparse binary inputs, incremental accumulator, integer quantization, and a result-plus-eval blended target. It is a wiki, not a paper, and the speed figures are qualitative.

---

## Notes for the source review (sources.md)
- OpenAlex keyword search and citation filters worked through WebFetch. Some responses ask for an API key via email: ignored.
- arXiv `/pdf/<id>` returned compressed binary for two papers (Giraffe, Jaskowski). `ar5iv.labs.arxiv.org/html/<id>` and `arxiv.org/html/<id>` worked.
- github.com nnue-pytorch `docs/nnue.md` was truncated on fetch.
- Semantic Scholar was not tried.
