# Cards: Slay the Spire and deckbuilding roguelikes (angle: sts-deckbuilders)

Scout pass for the learned-play-and-generalisation survey. Papers opened: 13 (9 with full text or full README/HTML, 4 abstract only).

Caveat: numbers below were read through a summarising web fetch, not checked line by line against the raw source. Verify any number against the source before quoting it in a decision.

---

### sts-rl-agent: learned non-combat policy on sts_lightspeed (year not shown)
- **Link:** https://github.com/Jialeiv/sts-rl-agent · **Venue:** GitHub repo (weights on Hugging Face, Jialeiv/sts-rl-agent) · **Cited by:** n/a · **Read:** full text (README and combat_experiments/ file listing; code files not opened)
- **Problem:** Learned non-combat decisions (map, card reward, shop, campfire, events) for Slay the Spire Ironclad. Combat is left to the simulator's MCTS. The README also reports six failed attempts to distil combat into a network.
- **Method:** Non-combat: a 412-dim `NNInterface` observation concatenated with a 368-dim candidate descriptor, scored by an MLP with [128,128] hidden layers, argmax over legal candidates, trained from scratch with REINFORCE. Combat: unchanged ScumSearch MCTS. Negative combat arms: behaviour cloning, DAgger, REINFORCE fine-tune, attention scorer, value net with 1-ply lookahead, policy/value-guided PUCT.
- **Assumes:** Discrete turns. Ironclad, A0 track only (the Defect track is incomplete). Simulator sts_lightspeed at commit 7476a81 with two patches, Python 3.12, CMake and pybind11. Fixed seeds. The search teacher uses the true future draw order (see Claims).
- **Claims:** Headline on the same 50 held-out seeds, same MCTS combat, only the non-combat layer differs. Built-in heuristics with MCTS@2000: avg floor 22.8, win rate 2%. Built-in heuristics with MCTS@50000: 31.2, 6%. Learned policy with MCTS@2000: 38.5, 4%. Learned policy with MCTS@50000: 42.5, 14%. Single runs, no confidence intervals. Negative results: behaviour cloning of MCTS reached imitation accuracy 0.59 and floor ~12. Value net with 1-ply lookahead reached floor ~8, which the README says is worse than no lookahead. PUCT with a learned policy/value scales with simulations but loses to blind MCTS at equal budget. The author's explanation: "the teacher effectively sees the future", since MCTS rollouts use the true future draw order. Conclusion: judgment decisions compress into small nets; planning decisions (combat card sequencing) resist.
- **Evaluation:** 50 fixed held-out seeds (eval/eval_seeds_50.txt). Scripts: eval/armB_blind.py, eval/native_bot_eval.py, eval/death_analysis.py. Combat arms: combat_experiments/armB_value.py, armB_value_train.py, armB_dagger.py, armB_attn.py, armB_rl.py, armB_mcts.py, armB_selfplay.py.
- **Code:** https://github.com/Jialeiv/sts-rl-agent, MIT per README. Simulator sts_lightspeed is MIT.
- **Fit:** good. It is the closest match I found: a value net plus 1-ply lookahead doing worse than no lookahead, on the same kind of simulator. It breaks the no-peeking constraint if its teacher is reproduced as-is, because the teacher uses future draw order.

---

### Dominion: A New Frontier for AI Research (2024)
- **Link:** https://arxiv.org/abs/2405.06846 (full text read at https://arxiv.org/html/2405.06846v1) · **Venue:** arXiv preprint (Halawi, Sarmasi, Saltzen, McCoy; UC Berkeley and UC Davis) · **Cited by:** n/a · **Read:** full text
- **Problem:** Dominion as an RL benchmark. The kingdom (10 of up to 350 cards) changes every game. The paper releases a dataset and an RL baseline.
- **Method:** Rainbow DQN trained by self-play. Fully connected net, two hidden layers of 256 units, takes a state encoding and action mask, outputs which card to gain. Only buy decisions are learned; action-card decisions use Provincial's heuristics.
- **Assumes:** 2-player, 2nd-edition base set, buy-only learning, discrete turns. Training is 1,000 steps (about 7,000 games), ~45 min on an NVIDIA 1080 Ti. Single run, no seed variance. State encoding and hyperparameters are deferred to the authors' code, not in the paper.
- **Claims:** Table 2, 1,000 games per matchup, DQN-bot Win/Tie/Lose: Big Money 912/27/61; Double Witch 561/63/376; Big Smithy 851/38/111; Big Militia 850/31/119; Village/Smithy Engine 418/24/558; Provincial 575/62/363. Counting ties, DQN-bot beats or ties Provincial in 637 of 1,000 games. Heuristic opponents always moved first, which the authors call a significant advantage. Generalisation to unseen kingdoms: not tested.
- **Evaluation:** 1,000 games per matchup against heuristic bots and Provincial. Dominion Online logs: over 2,000,000 games, of which 30,000 rated two-player base-game games are released.
- **Code:** none located in the fetched text (the paper refers to the authors' code; not checked).
- **Fit:** partial. A small learned buy policy beats heuristics by self-play. It does not test generalisation to unseen card sets, and its loss to the Village/Smithy Engine (418 vs 558) is attributed by the authors to an unexplored combo.

---

### Playing Various Strategies in Dominion with Deep Reinforcement Learning (2023)
- **Link:** https://ojs.aaai.org/index.php/AIIDE/article/view/27518 · **Venue:** AIIDE 2023 (Research Track Posters), DOI 10.1609/aiide.v19i1.27518 · **Cited by:** 3 (OpenAlex) · **Read:** abstract (PDF not readable through the fetch tool)
- **Problem:** Learn all Dominion decisions with deep RL, with agents that play different strategies.
- **Method:** Multiset-based game representation. Soft Actor-Critic adapted to variable-size action sets. Per the abstract, the first application of Geometric Deep Learning ideas to deckbuilding games.
- **Assumes:** Not checked (no full text read). Deckbuilding with variable card sets.
- **Claims:** Authors' abstract, as summarised: first learning-based agent making all decisions without heuristics; exceeds previous learning-based agents; outperformed by search-based agents only in some configurations. No numbers read.
- **Evaluation:** Not read.
- **Code:** none found.
- **Fit:** partial. The multiset encoding is the closest analogue I found to Deep Sets over cards. Without numbers or the full text, treat its claims as unverified.

---

### Rogue-Gym: A New Challenge for Generalization in Reinforcement Learning (2019)
- **Link:** https://arxiv.org/abs/1904.08129 · **Venue:** arXiv; accepted to IEEE CoG 2019 (per fetch) · **Cited by:** n/a · **Read:** abstract
- **Problem:** A roguelike benchmark for RL generalisation. Dungeons differ in every game.
- **Method:** PPO, with and without generalisation enhancements (the specific enhancements are not named in the abstract).
- **Assumes:** Grid-based roguelike, discrete actions, procedurally different dungeon layouts per episode. No card mechanics.
- **Claims:** Qualitative only: "some enhancements believed to be effective fail to mitigate the overfitting in Rogue-Gym" and "others slightly improve the generalization ability." No numbers read.
- **Evaluation:** Not read (train/test protocol not in the abstract).
- **Code:** none found.
- **Fit:** partial. A clean statement that PPO overfits a roguelike's training layouts. Not about cards, and no numbers read.

---

### Doron, "Part 7: Diminishing Returns" (year not shown)
- **Link:** https://dev.to/doronsinger/part-7-diminishing-returns-38me · **Venue:** DEV Community blog series · **Cited by:** n/a · **Read:** full text (post fetched through a summarising fetch)
- **Problem:** How to set the combat search budget for a Slay the Spire agent, and how much to trust the comparisons.
- **Method:** Breadth-first combat search with dominance pruning. A value model for card picks. Behaviour cloning from bottled_ai for events and pathing. Budgets are wall-clock: 1–3 s normal combat, 3–10 s boss. MCTS compared with BFS.
- **Assumes:** Wall-clock budgets (non-reproducible across machines). JVM-hosted simulator (the post mentions JVM warm-up). A0 goal.
- **Claims:** Agent win rate 6%; bottled_ai 26%; bottled_ai published 40% on A20. MCTS vs BFS (30 episodes, matched budget): MCTS avg floor 27.8, 3/30 wins; BFS 2s/5s avg floor 28.0, 1/30 wins. Budget comparison on five seeds: 3s/10s avg floor 24.0; 2s/5s 28.6; 1s/3s 23.0. A rerun of 3s/10s averaged 20.6. Author: "Five-seed average floor is a poor metric because of high run-to-run variance."
- **Evaluation:** 30 episodes for MCTS vs BFS; five seeds for budgets. Wall-clock budgets.
- **Code:** none found.
- **Fit:** partial. Useful as a warning about evaluation noise: the same configuration moved between 28.6 and 20.6 average floor across five seeds. Any "no better than the heuristic" claim needs far more seeds than that.

---

### Doron, "Part 4: Slay the Cultist" (year not shown)
- **Link:** https://dev.to/doronsinger/part-4-slay-the-cultist-9n7 · **Venue:** DEV Community blog series · **Cited by:** n/a · **Read:** full text (summarising fetch)
- **Problem:** PPO learning to fight the Cultist, the easiest early combat.
- **Method:** Network outputs a probability per play and a value estimate. PPO with lr 3e-4, 1,024 steps per batch, minibatch 256, 10 epochs, gamma 0.99, GAE lambda 0.95, clip 0.2, entropy 0.15. Later added per-card scoring for hand cards.
- **Assumes:** Single enemy, turn-based, custom environment.
- **Claims:** "70% win rate" after 200,000 steps (about 14,000 fights). A later "100% win rate after 10,000 steps" was judged misleading after bugs were found (block logic skipped in a visual function, blocking did nothing after death, energy not reset between turns). A "latch" bug stopped PPO learning about a third of the way through runs. After the fix, intent gap was 42% in the correct direction. The author then pivoted to search.
- **Evaluation:** Cultist fights; win rate and end-of-fight HP.
- **Code:** none found.
- **Fit:** poor for the goal, but a useful cautionary case: the reported 100% was inflated by simulator bugs. Check the simulator before trusting learned-play numbers.

---

### SlayTheSpire_RL: attention PPO combat agent (year not shown)
- **Link:** https://github.com/Armarit78/SlayTheSpire_RL · **Venue:** GitHub repo · **Cited by:** n/a · **Read:** full text (README; code not opened)
- **Problem:** A learned combat agent for Ironclad combat in a custom simulator, with a CommunicationMod adapter for live play.
- **Method:** Slot encoders (192 dims) with positional embeddings. Self-attention over hand, enemy and potion slots, card-to-enemy cross-attention, masked mean and max pooling, a 384-dim fusion MLP, policy and value heads. 126 factorised actions with masking. PPO: gamma 0.995, GAE 0.97, clip 0.2, lr 1.5e-4, entropy 0.016, rollout 8,192, minibatch 1,024, 4 epochs, 8 environments run sequentially.
- **Assumes:** Custom simplified simulator, "not a frame-perfect clone". Combat only. Windows and CUDA 12.8 in requirements.txt.
- **Claims:** None. The README says there is no versioned benchmark result for the current attention model, and no ablation comparing attention with the MLP.
- **Evaluation:** Deterministic evaluation on fixed seed ranges (values not stated). Curriculum over normal, elite and boss encounters. Recommended metrics listed but not reported.
- **Code:** https://github.com/Armarit78/SlayTheSpire_RL. Licence not stated in the fetched text.
- **Fit:** partial. The slot-encoding design is a useful comparison to Deep Sets. It has no results, and no licence.

---

### SpireBench: Evaluating Long-Horizon Strategic Play of Agentic Models with Slay the Spire (2026)
- **Link:** https://arxiv.org/abs/2610.12596 (read at https://arxiv.org/html/2610.12596v1) · **Venue:** arXiv (Lowe, Vector Institute; Keemink, Radboud) · **Cited by:** 0 (OpenAlex) · **Read:** full text, first ~100k of ~278k characters
- **Problem:** A benchmark for LLM agents playing full Slay the Spire runs.
- **Method:** LLM tool calls through CommunicationModPlus. No training during play. Cross-run memory is written in context and does not improve results.
- **Assumes:** Ironclad at Ascension 20, four acts, ten fresh seeds, reskinned game terms.
- **Claims:** From the results table, mean acts cleared and mean floor. BottledAI (symbolic): 0.20 acts, Act 1 win rate 20%, mean floor 11.3. All human players (206,082 runs): 0.73 acts, 47% Act 1 win rate, floor 22.1. Best LLM listed: 1.60 acts, floor 36.2 (model name as stated in the paper). Models "misjudge risk over a run". Cost per run up to about $62.
- **Evaluation:** Ten seeds, A20, scored on acts cleared, per-act win rate, final floor.
- **Code:** not checked.
- **Fit:** poor for learned search (no learning or search in the agents). Useful as an external reference: BottledAI at A20 on ten seeds.

---

### Yoshimura & Yoshizoe: Dominion agent that adapts to various card sets (2024)
- **Link:** https://ipsj.ixsq.nii.ac.jp/records/240729 · **Venue:** Game Programming Workshop 2024 (IPSJ), pp. 72–79 · **Cited by:** n/a · **Read:** abstract (PDF in the record, IPSJ-GPWS2024011.pdf, could not be read by the fetch tool)
- **Problem:** A Dominion agent whose card set changes every game. There are more than several million possible card sets.
- **Method:** LSTM model, trained by self-play with A3C. Only a few training card sets, chosen with domain knowledge so that varied tactics are effective.
- **Assumes:** Dominion, card sets excluded from training at test time.
- **Claims:** Abstract: "by appropriately selecting a small number of card sets, the trained models improve their win rates even on card sets not used during training." No numbers read.
- **Evaluation:** Not read (opponents, games and card sets not on the record page).
- **Code:** none found.
- **Fit:** partial. The only paper I found that explicitly tests unseen card sets in a deckbuilder. The numbers and the protocol are unverified until the PDF is read.

---

### AutoClad: supervised imitation on sts_lightspeed (year not shown)
- **Link:** https://github.com/benmuth/AutoClad · **Venue:** GitHub repo (fork of gamerpuppy/sts_lightspeed) · **Cited by:** n/a · **Read:** full text (README; code not opened)
- **Problem:** Train neural agents by supervised learning on Jaw Worm battles from sts_lightspeed, with the long-term aim of Ascension 20 Ironclad.
- **Method:** Randomise scenarios (HP, deck, RNG seeds) from real game data. Run a "SimpleAgent" to record demonstrations. Extract state-action pairs. Train a network to imitate, export TorchScript, run inference in C++ via LibTorch. README argues tree search should generate data because human data is incomplete.
- **Assumes:** Jaw Worm only. C++ inference. Network architecture not specified.
- **Claims:** None reported. Status: pipeline working on Jaw Worm; RL named as a later step.
- **Evaluation:** None reported.
- **Code:** https://github.com/benmuth/AutoClad. Licence file linked but the type is not stated in the fetched text.
- **Fit:** partial. Same data pipeline as a supervised teacher-student setup, with no numbers yet.

---

### sts_lightspeed: C++ Slay the Spire simulator and tree search (gamerpuppy; year not shown)
- **Link:** https://github.com/gamerpuppy/sts_lightspeed · **Venue:** GitHub repo · **Cited by:** n/a · **Read:** full text (README)
- **Problem:** Fast, RNG-accurate simulation and tree search for Slay the Spire.
- **Method:** C++17 simulator, with tree search that returns "best result, knowing the state of the game's rng". A planned search that does not know the RNG state is listed as not implemented.
- **Assumes:** Deterministic given a seed. The current search uses full RNG knowledge, so it is an oracle in the hidden-information sense. All enemies, relics, Ironclad cards and colourless cards implemented; other characters' cards not.
- **Claims:** "1M random playouts in 5s with 16 threads" (no hardware or conditions given beyond that). No bot performance on the page.
- **Evaluation:** None on the page.
- **Code:** https://github.com/gamerpuppy/sts_lightspeed, MIT per sidebar.
- **Fit:** good for infrastructure on a 16-core CPU, per the playout-throughput figure. Breaks the no-peeking constraint if its RNG-aware search is used as a teacher or planner.

---

### Mastering Strategy Card Game (Hearthstone) with Improved Techniques (2023)
- **Link:** https://arxiv.org/abs/2303.05197 (full text read at https://ar5iv.labs.arxiv.org/html/2303.05197) · **Venue:** IEEE CoG 2023 · **Cited by:** 16 (OpenAlex) · **Read:** full text
- **Problem:** A master-level Hearthstone agent covering both deck building and battle, from RL with no search.
- **Method:** One end-to-end policy shared by a deck-building head and a battle head, with shared card and hero embeddings. Optimistic smooth fictitious play. V-Trace and UPGO, later a PPO-style objective. Battle actions factorised into (type, target), with action masks.
- **Assumes:** Partially observable, two-player. Fixed pool of 350+ cards, three heroes, April 2015 rules. The strongest model used 24 V100 GPUs and 5,856 CPU cores, for about two days of training.
- **Claims:** Machine vs machine, 2,500 games per setting: b4 vs b0 = 73.6%; c5 vs b0 = 80.2%; c5 vs b4 = 55.5%. Machine vs one human (top-10 China league, ranked 60–70 during the test): four Conquest Best-of-5 tournaments, b4-23day 3:0 and 3:0, c5-16day 3:1 and 3:2. The paper does not claim generalisation to unseen cards.
- **Evaluation:** Fixed card pool; machine-vs-machine matchups and one human test.
- **Code:** none checked.
- **Fit:** poor on compute (GPU and cluster scale), no search, and no generalisation claim. The card and hero embedding design is relevant, though.

---

### Two-Step Reinforcement Learning for Multistage Strategy Card Game (2023)
- **Link:** https://arxiv.org/abs/2311.17305 · **Venue:** arXiv (Godlewski, Sawicki; cs.AI) · **Cited by:** 0 (OpenAlex) · **Read:** abstract
- **Problem:** RL for The Lord of the Rings: The Card Game, a multistage strategy card game.
- **Method:** Phased learning: first a simplified game, then the full game. Multi-agent setup with separate RL agents per decision (per the abstract). Architecture and algorithm not stated.
- **Assumes:** Multistage card game; details not read.
- **Claims:** Abstract: "winrate of 78.5% across a set of 10,000 random games." The opponent and what "random" refers to are not stated in the abstract.
- **Evaluation:** Not read beyond the abstract.
- **Code:** none found.
- **Fit:** poor. Not a deckbuilder roguelike, no generalisation claim in the abstract, and the win rate has no stated opponent.
