# Cards: search in stochastic / imperfect-information games (learned leaf evaluators, determinization, chance-node search)

Scout date: 2026-10-24. Constraints used for "Fit": (C) CPU only, training runs of hours at most; (H) no peeking at hidden information; (G) generalisation to unseen cards. "Read: abstract" means only the abstract or landing page was opened (PDF fetch returned binary). Cited-by counts come from OpenAlex where the work appeared in a citation query; otherwise "not checked".

---

### Improving Search with Supervised Learning in Trick-Based Card Games (2019)
- **Link:** https://arxiv.org/abs/1903.09604 (full text: https://ar5iv.labs.arxiv.org/html/1903.09604) · **Venue:** AAAI-19, pp. 1158-1165 · **Cited by:** 16 (OpenAlex) · **Read:** full text
- **Problem:** PIMC search in Skat samples hidden card layouts poorly; the sampled worlds should match what the player's history implies.
- **Method:** A network trained on human games predicts, for each of the 32 cards, the probability of each of 4 locations (3 hands or the skat), one network per game type, first 8 tricks only. A state's probability is the product of its cards' location probabilities (independence approximation). Algorithm 1 samples n states and evaluates every move per state with perfect-information play, then averages.
- **Assumes:** Discrete turns, 3 players, imperfect information, Skat rules. Training data: 20 million human games from a Skat server. Adam, lr 1e-4, batch 32, dropout 0.8, ELU, cross-entropy.
- **Claims:** Table 3 (avg tournament points per game, BDCI:NI): suit, 320 samples, 24.0:15.7 (Δ8.3); grand, 320, 39.0:35.0 (Δ4.0); null, 320, 18.2:7.5 (Δ10.8). KI:NI suit 320 is 22.7:18.1 (Δ4.6). Overall soloist win %, suit: BDCI 81.5 vs NI 78.0. Grand gains are not significant. Per-move time at 320 states: 0.286 s (BDCI) vs 0.093 s (KI). Tournaments: 2,500 matches per matchup, two games per match with roles reversed.
- **Evaluation:** Skat cardplay only (bidding taken from human data), PIMC evaluation, four samplers (NI, BDI, KI, BDCI) compared in tournaments. Test-set true-state sampling ratio on 3,000 holdout samples per trick.
- **Code:** none found (no link on paper pages)
- **Fit:** partial. (H) holds: inference uses only public history. (C) PIMC with 320 samples is affordable, but the network needs a 20M-game human dataset that we do not have. (G) not tested: the net predicts card locations for seen game types only.

### Policy Based Inference in Trick-Taking Card Games (2019)
- **Link:** https://arxiv.org/abs/1905.10911 (full text: https://ar5iv.labs.arxiv.org/html/1905.10911) · **Venue:** IEEE CIG 2019 (from DOI) · **Cited by:** 12 (OpenAlex) · **Read:** full text
- **Problem:** Uniform or model-free sampling of hidden states in determinized search gives poor inference; the paper weights sampled worlds by the probability that each opponent's actions would have been taken.
- **Method:** Reach probability of a sampled state = product of action probabilities in its history (chance from the deal; own actions = 1; other players from policy networks trained on human data). Samples card configurations, normalises the distribution, then runs PIMC. Variant PIF samples full states.
- **Assumes:** Skat, 3 players, imperfect information; policy nets trained on human data (separate nets per decision point and per game type). Up to ~2.8 billion states in an information set.
- **Claims:** Cardplay tournaments, 5,000 matches per game type, roles reversed. PI vs CLI (points per game): suit 19.50 vs 17.18 (+2.32); grand 37.87 vs 37.23 (+0.64, not significant); null 18.84 vs 17.27 (+1.57). PI100 vs CLI: suit +2.86, grand +2.10, null +1.03. A "cheating" Kermit that knows the true state: suit −3.25, grand −8.49, null +9.82 vs CLI. PI20 is about five times slower per move than CLI. Authors state exploitability risk from player models.
- **Evaluation:** Skat cardplay tournaments with human bidding; TSSR on human holdout data (4,000 games grand/suit, 3,800 null, 13,000 null ouvert).
- **Code:** none found
- **Fit:** partial. (H) respected: it uses only opponent-action likelihoods from public history. (C) per-move cost is about 5x. The model needs human game data. (G) not tested. Non-locality and exploitability caveats are relevant to any learned sampler.

### Information Set Monte Carlo Tree Search (2012)
- **Link:** https://eprints.whiterose.ac.uk/id/eprint/75048 (PDF: https://eprints.whiterose.ac.uk/id/eprint/75048/1/CowlingPowleyWhitehouse2012.pdf, fetch returned binary) · **Venue:** IEEE TCIAIG 4(2), pp. 120-143 · **Cited by:** 160 (OpenAlex) · **Read:** abstract
- **Problem:** Determinization (sample a world, search it) causes strategy fusion; ISMCTS searches trees whose nodes are information sets instead.
- **Method:** Three ISMCTS variants. Per the abstract, "Instead of searching minimax trees of game states, the ISMCTS algorithms search trees of information sets." Variant details not read.
- **Assumes:** Not read (abstract only).
- **Claims:** None quoted; the abstract has no numbers I could read.
- **Evaluation:** Not read.
- **Code:** none found
- **Fit:** partial. Conceptually the direct alternative to determinized search, relevant to (H). Details are unverified; the PDF is the next thing to read.

### Understanding the Success of Perfect Information Monte Carlo Sampling in Game Tree Search (2010)
- **Link:** https://ojs.aaai.org/index.php/AAAI/article/view/7562 (PDF: https://ojs.aaai.org/index.php/AAAI/article/download/7562/7423, fetch returned binary) · **Venue:** AAAI-10, pp. 134-140, DOI 10.1609/aaai.v24i1.7562 · **Cited by:** 81 (OpenAlex) · **Read:** abstract
- **Problem:** PIMC is criticised in theory but works in practice; when does it work?
- **Method:** Synthetic game trees to find properties where PIMC does well or badly versus optimal play; then detect the same properties in real games to predict PIMC strength.
- **Assumes:** Two-player imperfect information game trees; not read further.
- **Claims:** No numbers in the abstract page I could read.
- **Evaluation:** Synthetic trees plus real games (not read).
- **Code:** none found
- **Fit:** partial. Useful as a diagnostic for (H)-type sampling; no direct evaluator result.

### Bootstrapping from Game Tree Search (2009)
- **Link:** https://papers.nips.cc/paper/3722-bootstrapping-from-game-tree-search (PDF: https://proceedings.nips.cc/paper_files/paper/2009/file/389bc7bb1e1c2a5e7e147703232a88f6-Paper.pdf, fetch returned binary) · **Venue:** NIPS 2009 (NeurIPS 22), pp. 1937-1945 · **Cited by:** not checked · **Read:** abstract
- **Problem:** How to learn a heuristic evaluation function when the training signal is the outcome of a deep search rather than a later search or the game result.
- **Method:** TreeStrap (update every node of the alpha-beta tree toward the deep-search value) and RootStrap (root only). Contrasted with TD-Leaf, which moves a single leaf toward a later search value.
- **Assumes:** Perfect-information chess; linear evaluation function; alpha-beta search at every move; self-play from small random weights.
- **Claims:** Abstract only: learned "high quality weights from self-play alone"; master-level online play against humans. The abstract gives no numbers.
- **Evaluation:** Chess (Meep). Details not read.
- **Code:** none found
- **Fit:** partial. The idea of training every node in the search tree from search backups is directly relevant to a learned leaf evaluator. It is perfect-information, so (H) is not addressed.

### Improving State Evaluation, Inference, and Search in Trick-Based Card Games (Buro et al., 2009)
- **Link:** https://mlanthology.org/ijcai/2009/buro2009ijcai-improving (PDF: https://ijcai.org/Proceedings/09/Papers/236.pdf, not opened) · **Venue:** IJCAI 2009, pp. 1407-1413 · **Cited by:** not checked · **Read:** abstract
- **Problem:** Learned state evaluations for Skat, used both for search and for inferring opponents' hidden hands.
- **Method:** State evaluations trained on human player data, then used to infer hidden hands in search. Details not read.
- **Assumes:** Skat, 3 players, imperfect information.
- **Claims:** Per the abstract, "the world's first computer skat player that plays at the level of human experts"; "training on data from average human players can result in expert-level playing strength." The abstract has no numbers.
- **Evaluation:** Not read.
- **Code:** none found
- **Fit:** partial. This is the closest prior art for a learned evaluator in a trick-taking game (the angle the user asked about). Its inference and evaluation details are the next thing to read in full.

### Monte Carlo *-Minimax Search (2013)
- **Link:** https://arxiv.org/abs/1304.6057 (full text: https://ar5iv.arxiv.org/html/1304.6057) · **Venue:** IJCAI 2013 · **Cited by:** not checked · **Read:** full text
- **Problem:** Expectimax and *-minimax cost grows exponentially with the branching factor at chance nodes; the search depth reached in a fixed time is small in densely stochastic games.
- **Method:** At each chance node, sample c outcomes with replacement and visit only those subtrees; value = equally weighted average. Apply Star1 (star1ss) or Star2 (star2ss) to the sampled subgame. With pruning off, this is expectimax with sparse sampling (expss).
- **Assumes:** Turn-based, stochastic, two-player zero-sum, perfect information, densely stochastic (outcomes rarely repeat). Sample width c tuned per game for (expss, star1ss, star2ss): Pig (20, 25, 18), EWN (1, 1, 2), Can't Stop (25, 30, 15), Ra (5, 5, 2).
- **Claims:** Can't Stop: star2ss vs Star2, 85.0% win rate. Ra: roughly 60% vs classic *-minimax. Pig and one other game: best MCMS variant "comparable" to best MCTS variant. EWN: MCMS weaker than MCTS, which the authors attribute to lacking a good evaluation function. Statistics table (Pig, 2,470 states): expss MSE 95.3, bias 9.07; exp MSE 91.4. The authors say sampling adds variance and raises MSE.
- **Evaluation:** 200 ms per search; 5,000 matches for Pig and EWN, 2,000 for Can't Stop and Ra (two games per match, seats swapped). Tuning by self-play round robin, 1,000 games per pairing.
- **Code:** none found
- **Fit:** good for (C) and for the chance-node question: it is the direct template for sparse sampling at chance nodes (e.g. card draws), with a stated per-game tuning of c. Its EWN result shows that sampling does not compensate for a weak leaf evaluator.

### Depth-Limited Solving for Imperfect-Information Games (2018)
- **Link:** https://arxiv.org/abs/1805.08195 (full text: https://ar5iv.labs.arxiv.org/html/1805.08195) · **Venue:** NeurIPS 2018 · **Cited by:** not checked · **Read:** full text
- **Problem:** A leaf in an imperfect-information game has no well-defined value, so standard depth-limited search does not apply.
- **Method:** At each leaf infoset the opponent chooses among k alternative strategies for the rest of the game; each gives a leaf value. Alternatives are generated by biasing the blueprint or by iterative best-response. Values are stored in a table, estimated by rollouts, or predicted by a neural net.
- **Assumes:** Heads-up no-limit hold'em (Modicum), 4-core CPU, 16 GB RAM; betting rounds 1-2 solved, later rounds solved to the end.
- **Claims:** Head-to-head, mbb/g with CIs. Blueprint only vs Baby Tartanian8 −57±13; naive depth-limited −10±8; depth-limited solving 6±5. Vs Slumbot: blueprint −11±8; naive −1±15; depth-limited solving 11±9. DNN leaf values lost to Baby Tartanian8 by 11±10 mbb/g (authors: "slightly worse" than rollouts). Modicum used 700 core hours and 16 GB RAM.
- **Evaluation:** Heads-up NLHE; exploitability with 1,000 CFR+ iterations (numbers in a figure only).
- **Code:** not checked
- **Fit:** partial. (C) is met for this paper's CPU budget. The leaf-value side is informative: multi-valued leaves guard against a bad leaf estimate. The DNN leaf was worse than rollouts here.

### Value Functions for Depth-Limited Solving in Zero-Sum Imperfect-Information Games (2019, rev. 2022)
- **Link:** https://arxiv.org/abs/1906.06412 (full text: https://ar5iv.labs.arxiv.org/html/1906.06412) · **Venue:** arXiv (cs.AI/cs.GT) · **Cited by:** not checked · **Read:** full text (about 200k of 255k characters read)
- **Problem:** Value functions for depth-limited solving in imperfect-information games, with the question of how they should be trained and whether they generalise.
- **Method:** Value function on public states; inputs = public state and range vector. Training targets = counterfactual values from "value solving": a random trunk strategy is fixed and the bottom is solved with 1,000 iterations of CFR+. Trunk strategies: 90% fully mixed uniform, 10% pure random action. Network: fully connected ReLU, 3-6 layers, width 5-10x input; Huber loss; Adam; 1,000 epochs; 90/10 train/validation split.
- **Assumes:** Two-player zero-sum; domains Goofspiel (5 cards), Oshi-Zumo (board 3, budget 8), Leduc hold'em. Depth limit after half the rounds.
- **Claims:** Datapoints: GS 18,000; OZ 34,000; LH 70,644. Constant zero predictor exploitability: 0.5 (GS), 0.7 (OZ), 0.2 (LH). Trained nets: "exploitability below 0.01". Below 10,000 samples was enough for validation Huber loss 0.001 in all three domains. Generalisation to withheld public states: "very poor in goofspiel, reasonable in oshi-zumo, and very strong in Leduc hold'em." Authors: "a strong connection between validation loss and the resulting exploitability."
- **Evaluation:** The three domains above, DL-CFR+NN solver run for 1,000 iterations, 100 training runs per configuration.
- **Code:** none linked
- **Fit:** good for (G): it measures generalisation to unseen public states and ties value-net error to exploitability. Games are small, and the setting is a CFR solver rather than single-agent expectimax. Those limits are on the paper, not on the fit claim.

### DouZero: Mastering DouDizhu with Self-Play Deep Reinforcement Learning (2021)
- **Link:** https://arxiv.org/abs/2106.06135 (full text: https://arxiv.org/html/2106.06135) · **Venue:** ICML 2021 · **Cited by:** not checked · **Read:** full text
- **Problem:** Learn a strong 3-player imperfect-information card game AI without search, from self-play.
- **Method:** Deep Monte-Carlo: a Q-network is regressed toward the discounted return-to-go of each episode (γ=1; reward only at the final step: WP ±1, or ADP). No bootstrapping. ε-greedy with ε=0.01. Input: one-hot card-combination matrices, hand, other hands' union, recent moves (last 15 moves through an LSTM), played cards. Six MLP layers, hidden 512, ReLU. RMSprop, lr 1e-4.
- **Assumes:** DouDizhu, imperfect information, random decks, bidding skipped in training. 45 actors on 3 GPUs plus 1 learner GPU, 48 CPU processors, 4 GTX 1080 Ti.
- **Claims:** 30 days of training. WP vs DeltaDou 0.586, SL 0.659, RHCP 0.764, RLCard 0.889, Random 0.989 (10,000 decks). Botzone: first of 344 agents, Elo 1625.11. The paper has no with-search vs no-search ablation.
- **Evaluation:** Simulated DouDizhu games, 10,000 decks for Table 1 (WP/ADP); bidding phase 100,000 decks.
- **Code:** https://github.com/kwai/DouZero (license not checked)
- **Fit:** partial. Shows regression onto final outcomes works without search, which is the target type we use. (C) fails: 30 days on 4 GPUs against a "hours" budget. (G) not tested for unseen cards.

### Combining Deep Reinforcement Learning and Search for Imperfect-Information Games (ReBeL, 2020)
- **Link:** https://arxiv.org/abs/2007.13544 (full text: https://ar5iv.labs.arxiv.org/html/2007.13544) · **Venue:** arXiv preprint (cs.GT) · **Cited by:** not checked · **Read:** full text
- **Problem:** Combine deep RL and search for imperfect information, with a learned value at the leaves of a depth-limited subgame.
- **Method:** Depth-limited subgame rooted at a public belief state; CFR-D solver (fictitious play also used). Value net input = public belief state (beliefs over infostates for both players) plus public features; output = values per infostate. Training targets = root values averaged over solver iterations. Leaves sampled with ε=0.25 exploration; the paper states random-belief training "fails to learn anything valuable."
- **Assumes:** Two-player zero-sum. Liar's Dice and heads-up NLHE. Full HUNL data generation used 90 DGX-1 machines (8 GPUs each) per the paper's Section 7 text ("up to 128 machines").
- **Claims:** Liar's Dice exploitability with 1,024 iterations (ReBeL CFR-D): 0.017 (1x4f), 0.015 (1x5f), 0.024 (1x6f), 0.017 (2x3f). Full-game CFR is 0.001-0.002 in the same table. HUNL vs Slumbot 45±5 mbb/g; vs Dong Kim 165±69 (AIVAT). Liar's Dice training: one GPU, 60 CPU threads for data generation, 1,000 epochs, batch 512. The paper says the input grows linearly with the number of infostates.
- **Evaluation:** Liar's Dice (1x4f, 1x5f, 1x6f, 2x3f), HUNL, turn endgame hold'em.
- **Code:** none linked
- **Fit:** partial. Training data comes from search, not from final outcomes (a difference from our setup). The random-belief failure is a useful pitfall for (G). Compute and input size make the full version infeasible under (C).

### Re-determinizing Information Set Monte Carlo Tree Search in Hanabi (2019)
- **Link:** https://arxiv.org/abs/1902.06075 (full text: https://ar5iv.labs.arxiv.org/html/1902.06075) · **Venue:** technical report on the CIG 2018 Hanabi competition · **Cited by:** 9 (OpenAlex) · **Read:** full text
- **Problem:** Standard IS-MCTS leaks hidden information into opponent models in Hanabi; 40 ms per move.
- **Method:** RIS-MCTS resamples the acting player's hidden hand at every node where that player decides. A shallow net (38 input features, DL4J) approximates Q(s,a) and predicts the final score. Target = mean score of the child node, using nodes with at least 50 visits (a "penumbra" around the played trajectory, not only roots). Three iterations: 300 games at 3 s/move (about 258k records); 500 games at 10 s/move; 200 games at 30 s/move (about 704k records).
- **Assumes:** Cooperative multi-player (2-5), hidden hands, 40 ms move budget (30 ms used).
- **Claims:** Table VI, mean score (SE ±0.1 for RIS-MCTS-NR): RIS-MCTS-NR(3): 20.5 (2P), 21.0 (3P), 20.9 (4P), 19.7 (5P). EvalFn(3) alone: 18.8, 20.0, 20.1, 19.2. Author notes 5 players are better handled by a hat-guessing method.
- **Evaluation:** Official Hanabi rules with 2-5 players; games count not stated in Table VI.
- **Code:** https://github.com/hopshackle/fireworks (license not checked)
- **Fit:** good for (C) and for learned leaves trained on search-node values rather than only final results. It is multi-player cooperative, so the game differs from ours.

### Perfect Information Monte Carlo with Postponing Reasoning (2024)
- **Link:** https://arxiv.org/abs/2408.02380 (full text: https://ar5iv.labs.arxiv.org/html/2408.02380) · **Venue:** IEEE CoG 2024 (DOI 10.1109/cog60054.2024.10645574) · **Cited by:** 1 (OpenAlex) · **Read:** full text
- **Problem:** Strategy fusion in PIMC: solving each sampled world separately gives a different strategy per world.
- **Method:** EPIMC evaluates leaves at depth d instead of right after the first action (PIMC = depth 1). Steps: sample a world, play forward to depth d or terminal, evaluate with a perfect-information evaluator, then solve the resulting infostate subgame with Information Set Search or CFR+.
- **Assumes:** Two-player adversarial games; Card Game, Battleship, Dark Chess, Phantom Tic-Tac-Toe, Dark Hex; OpenSpiel; one Intel Xeon Gold 5218 CPU.
- **Claims:** Dark Chess at 100 s: win rates 80%, 65%, 45% at depths 3, 2, 1 vs PIMC (1 s). At 1,000 s, depth 3 wins close to 100% in Dark Hex and Dark Chess. Dark Hex 3x3: minimax leaf close to 70%, random rollout close to 50%. Card Game and Battleship: depth has little effect. Each experiment: 500 games split between seats.
- **Evaluation:** Budgets 0.1-100 s (up to 1,000 s for Dark Hex and Dark Chess) against PIMC with 1 s.
- **Code:** none found (no license stated)
- **Fit:** partial. It gives an explicit depth-vs-leaf trade-off on CPU (C). Gains need large budgets, and the games are adversarial, not stochastic single-agent.

### Student of Games: A unified learning algorithm for both perfect and imperfect information games (2021, arXiv 2112.03178; Science Advances 2023)
- **Link:** https://arxiv.org/abs/2112.03178 (full text: https://ar5iv.labs.arxiv.org/html/2112.03178) · **Venue:** Science Advances 2023 (per OpenAlex record) · **Cited by:** 21 (OpenAlex) · **Read:** full text (first 100k of 167k characters read)
- **Problem:** One algorithm for perfect and imperfect information games, combining guided search, self-play learning and game-theoretic reasoning.
- **Method:** A counterfactual value-and-policy net (CVPN) takes a public belief state. GT-CFR grows a public tree; leaves are valued by the CVPN. Value targets: game outcome (TD(1)) along the self-play line, plus final counterfactual values from GT-CFR solves of subgames. Recursive queries are added to the buffer with probability 0.1 or 0.2.
- **Assumes:** Chess, Go, heads-up NLHE, Scotland Yard, Leduc. Trained with TPU resources comparable to AlphaZero.
- **Claims:** Chess: SoG(60k, c=10) is +420 Elo vs Stockfish 1 thread (0.1 s = 0 reference), 200 games per pair. Scotland Yard: 55% win rate vs PimBot with 10M simulations (2,000 matches). HUNL vs Slumbot2019: 7 ± 3 mbb/h over 3.1M matches. Training steps: 3M (chess), 1M (Go), 17M (Scotland Yard).
- **Evaluation:** Board games and poker benchmarks in the paper; the supplement was not read.
- **Code:** none stated
- **Fit:** partial. It shows value targets from game outcome and from search subgame solves together. Compute (millions of steps on TPUs) breaks (C). Not a single-agent stochastic setting.

### Combining Tree Search and Action Prediction for State-of-the-Art Performance in DouDiZhu (2021)
- **Link:** https://www.ijcai.org/proceedings/2021/470 (PDF: https://www.ijcai.org/proceedings/2021/0470.pdf, not opened) · **Venue:** IJCAI-21, pp. 3413-3419 · **Cited by:** not checked · **Read:** abstract
- **Problem:** Hidden hands in DouDizhu; sampling hidden states is inefficient and predicting them is hard.
- **Method:** AP-MCTS: the tree is built over public information with a policy-value network, and other players' actions are predicted directly rather than sampling hidden states.
- **Assumes:** 3-player DouDizhu.
- **Claims:** 65.65% win rate vs experienced human players; Elo 50-200 above state-of-the-art DouDizhu AIs; the paper says "accurate action prediction is the key to AP-MCTS winning." No counts or budgets in the abstract.
- **Evaluation:** Not read.
- **Code:** none stated on page
- **Fit:** partial. A determinization-free alternative to (H), but compute and training details are unknown.

### AlphaZe**: AlphaZero-like baselines for imperfect information games are surprisingly strong (2023)
- **Link:** https://www.frontiersin.org/articles/10.3389/frai.2023.1014561/full · **Venue:** Frontiers in Artificial Intelligence 6 (DOI 10.3389/frai.2023.1014561) · **Cited by:** 4 (OpenAlex) · **Read:** full text (first 100k of 136k characters read)
- **Problem:** Make AlphaZero-style search work for imperfect information.
- **Method:** Replace MCTS with PC-PIMC (samples possible worlds, runs search on each, averages policies). TrueSight Learning trains on the true world state during early data generation.
- **Assumes:** Barrage Stratego and DarkHex 11x11; GPU training.
- **Claims:** Barrage Stratego average win ratio 36% at 800 nodes per tree and 59.6% at 25,000 nodes per turn (Table 4; over 70% at 25,000 excluding P2SRO). Training: Stratego 40 epochs (~32M samples) ~16 days on 3 V100s; DarkHex 11x11 10 epochs (~4M samples) ~26 hours. The authors cannot prove Nash convergence.
- **Evaluation:** Stratego vs handcrafted bots and P2SRO; DarkHex.
- **Code:** none visible (footnotes truncated)
- **Fit:** poor for (C) (GPU days). Its self-described PIMC issues (strategy fusion, non-locality, "strategy hopping") are relevant to (H).

### On Reinforcement Learning for the Game of 2048 (dissertation, 2022)
- **Link:** https://arxiv.org/abs/2212.11087 · **Venue:** NYCU PhD dissertation (arXiv) · **Cited by:** not checked · **Read:** abstract
- **Problem:** RL for 2048, a single-player stochastic puzzle game.
- **Method:** Optimistic TD learning; n-tuple network ensembles; MCTS and deep RL studied as add-ons. Details not read.
- **Assumes:** Single-player stochastic game; afterstate-style value learning is implied but not confirmed from the abstract.
- **Claims:** Abstract: average 625,377 points and 32768 tile in 72% of games, described as the highest among learning-based programs. Number of games and search budget not in the abstract.
- **Evaluation:** Not read.
- **Code:** not linked (CC BY 4.0 on the paper)
- **Fit:** partial. Stochastic single-agent with learned values, the closest published match to our setting, but no details read on search.

### Knowledge-Based Paranoia Search in Trick-Taking (2021)
- **Link:** https://arxiv.org/abs/2104.05423 (HTML: https://arxiv.org/html/2104.05423v1, not opened) · **Venue:** arXiv preprint · **Cited by:** not checked · **Read:** abstract
- **Problem:** Find forced wins in Skat trick-taking; worst-case analysis after a few tricks.
- **Method:** Partial-information game-tree search plus knowledge representation; variants for declarer and opponents; approximation that seeks a forced win against most worlds.
- **Assumes:** Skat, 3 players.
- **Claims:** "The AIs ... score over 1,000 points under the extended Seeger system." Not comparable without the human baseline (not on the page).
- **Evaluation:** Replay of "thousands" of expert games; count not stated.
- **Code:** none found
- **Fit:** poor for (C) and (G). Logic-based worst-case search, not a learned evaluator.

### Transformer Based Planning in the Observation Space with Applications to Trick Taking Card Games (2024)
- **Link:** https://arxiv.org/abs/2404.13150 (HTML: https://arxiv.org/html/2404.13150v1, not opened) · **Venue:** arXiv preprint · **Cited by:** not checked · **Read:** abstract
- **Problem:** PIMC's limits in trick-taking games with very many underlying states.
- **Method:** GO-MCTS runs MCTS over observation sequences produced by a game-specific transformer generative model; trained by population-based self-play.
- **Assumes:** Hearts, Skat, The Crew.
- **Claims:** "promising results"; the abstract has no numbers.
- **Evaluation:** Not read.
- **Code:** none stated
- **Fit:** partial. Search in observation space avoids sampling hidden states (H), but the model is a generative transformer, which is far from the (C) budget as stated.

---

## Not opened (leads only)

- **Stochastic MuZero** (Antonoglou et al., ICLR 2022, "Planning in Stochastic Environments with a Learned Model"). It learns afterstates and chance outcomes for tree search. OpenReview returned a browser-verification page, so I did not open it. It is not carded above.
- **Frank & Basin 1998 (Bridge strategy fusion)**: the original critique was not reachable; strategy fusion is cited via Edelkamp, Blüml et al., and Arjonilla et al.
- **Ballard 1983 (*-minimax)**: only secondary summaries were found; not opened.
- **Survey of AI for card games and Jass** (arXiv 1906.04439): found, not opened.
