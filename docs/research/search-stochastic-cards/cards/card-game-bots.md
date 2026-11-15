# Card-game bots: Slay the Spire, Hearthstone, Dominion, Legends of Code and Magic, Magic drafting

Angle: AI for deckbuilding and collectible card games. Ten sources opened, nine with full text (web pages, READMEs and arXiv HTML) and one abstract only (Vieira et al., 2009.00655). "Cited by" was not checked for any card; the search tools gave no counts.

Fit terms below refer to the project's constraints: CPU only, a perfect simulator exists, content may be new or random, draw order is hidden, and the goal is search over a learned value net with a self-play teacher that beats its student.

---

### AI systems are improving rapidly at Slay the Spire and its sequel (2026)
- **Link:** https://epoch.ai/publications/ai-systems-are-improving-rapidly-at-slay-the-spire-and-its-sequel · **Venue:** Epoch AI publication (non-academic) · **Cited by:** not checked · **Read:** full text (web page)
- **Problem:** How well frontier LLMs play Slay the Spire 1 (StS1) and Slay the Spire 2 (StS2) at high difficulty, against human players.
- **Method:** SpireClimb, a single-agent visual computer-use harness (Inspect ReAct). Models see the screen and take actions through the game interface. They may take notes and consult the StS wiki.
- **Assumes:** Real game through screenshots, not a simulator. StS1 is tested at Ascension 0 and Ascension 20 Heart. StS2 is tested at Ascension 10 on frozen version v0.107.1. Fixed, arbitrarily chosen seeds.
- **Claims:** StS1 Ascension 0: GPT-6 Astra 98%, GPT-6.1 Sol 97%, Claude Opus 5.5 93%, GPT-6 Sol 92%, Claude Sonnet 5.5 83%, Claude Fable 5.1 65%, GPT-6 Luna 25%. StS1 Ascension 20 Heart: GPT-6.1 Sol 20%, GPT-6 Astra 17%, GPT-6 Sol 2%, four others 0%. StS2 Ascension 10: GPT-6 Astra 35%, GPT-6.1 Sol 29%, GPT-6 Sol 13%, Claude Opus 5.5 7%, others lower. Human line: about 80% to 95% on maximum difficulty (XecnaR 80% to 95% on StS1). The page gives 15 attempts per character per game but no per-model total or confidence intervals in the text. The page does not separate combat, route and deck decisions.
- **Code:** none found (no code or dataset link; the harness is described, not released)
- **Fit:** poor. It is a yardstick for an LLM-with-screen agent, not a search or simulator method. Useful only as the outside number for "how strong is a frontier LLM" and to note that the maximum difficulty still lags humans.

---

### bottled_ai (repository README, xaved88)
- **Link:** https://github.com/xaved88/bottled_ai · **Venue:** GitHub repository (non-academic) · **Cited by:** not checked · **Read:** full text (README page; the linked winrates file was not opened)
- **Problem:** A working rule-based Slay the Spire bot that plays through Communication Mod.
- **Method:** Combat: it works out the likely outcome of each way it could play its hand with "a graph traversal and a simulation we constructed," then plays the preferred order, weighing "about 40 different values." Cards, boss relics and upgrades follow a prioritized list. Events have conditions. It cannot see random roll outcomes or upcoming draws. Route choice is not described.
- **Assumes:** Runs inside the real game (Communication Mod, BaseMod, StSLib, ModTheSpire) with a 10s timeout per message. Python, min 3.11.8. It does not use a perfect simulator for the real game; it sees only what the player sees.
- **Claims:** "best win rate of 52% for a watcher strategy." The README does not give the ascension level or number of runs. It points to docs/winrates.md for current numbers, which I did not open.
- **Evaluation:** Tests in /tests that run without the game ("VERY useful for checking bot behavior without needing to run the game"). No benchmark protocol given.
- **Code:** https://github.com/xaved88/bottled_ai · MIT license (LICENSE.md)
- **Fit:** partial. It is a rule-based yardstick, not a search over a value net. Its combat simulation is the closest thing in this set to a hand-written outcome search. Its 52% has no conditions, so it cannot be compared directly with other numbers.

---

### sts_lightspeed (repository README, gamerpuppy)
- **Link:** https://github.com/gamerpuppy/sts_lightspeed · **Venue:** GitHub repository (non-academic) · **Cited by:** not checked · **Read:** full text (README page; the fork maxisawesome/sts_lightspeed was seen only in search results)
- **Problem:** A fast C++ simulator of Slay the Spire, for tree search and simulation.
- **Method:** Standalone C++17 with a console mode. It can load saves, but only into combat. Search is "Tree Search (best result, knowing the state of the game's rng)." The planned version does tree search "without knowing the RNG state."
- **Assumes:** The README says it is "Designed to be 100% RNG accurate*". The asterisk has no matching footnote in the captured page, so the qualification is unknown. Ironclad is the only character named. Hardware for the speed claim is not given.
- **Claims:** "Speed: 1M random playouts in 5s with 16 threads." No hardware details, no independent benchmark. Implemented: all enemies, all relics, all Ironclad cards, all colorless cards, and "Everything outside of combat / all acts."
- **Evaluation:** None given in the README beyond the speed line.
- **Code:** https://github.com/gamerpuppy/sts_lightspeed · MIT license per the page (license text not in the captured page)
- **Fit:** good. A CPU-speed reference for a C++ game simulator with a tree-search focus, on the same kind of problem (hidden draw order, scripted monsters). The 16-thread figure is a close match to this machine's 16 threads, but it is the author's claim and not checked. The RNG-accuracy claim is conditional on an unexplained asterisk.

---

### Summarizing Strategy Card Game AI Competition (2023)
- **Link:** https://arxiv.org/pdf/2305.11814 (HTML fetched at https://arxiv.org/html/2305.11814) · **Venue:** arXiv, Kowalski and Miernik, summary of the Legends of Code and Magic (LOCM) competitions · **Cited by:** not checked · **Read:** full text
- **Problem:** What won five years of AI competitions on LOCM, a small collectible card game with a draft phase and a battle phase, and how strength was measured.
- **Method:** Summary and results table across CEC/COG editions (v1.2 for 2019 to 2021, v1.5 for 2022). Winners were search-based for every v1.2 edition, with neural nets dominating v1.5.
- **Assumes:** Two-player battles with random seeds. v1.2: a draft phase plus battle, with random sampled decks. v1.5: one four-second construction turn, then battle.
- **Claims:** CEC 2019 (v1.2): Coac (depth-3 minimax with alpha-beta and heuristic pruning) won with 94.22%; runner-up UJIAgent2 58.93%. COG 2019: Coac 89.88%, ProphetCoac 87.84%. CEC 2020: Coac 86.07%, Chad 79.10%, ReinforcedGreediness (first neural net) 60.20%. COG 2020: Chad 79.99%, Coac 74.68%. COG 2021: DrainPowerAggressive 78.72%, DrainPower 77.96%, Chad 75.51%. COG 2022 (v1.5): ByteRL (deep RL, end-to-end policy) 84.41%, NeteaseOPD 75.00%, Inspirai 67.57%; random baseline 1.29%.
- **Evaluation:** Each agent plays a fixed number of randomly sampled decks (v1.2), ten games per random seed, each match mirrored for first-player advantage. Placement by win rate within each edition. Public CodinGame leaderboards (Sprint had 742 participants, Marathon 2174 submissions). Note: the paper does not spell out the opponent pool behind each table entry. Last year's agents were not re-run, so win rates fell in 2020.
- **Code:** none found in this card (the competition environments are referenced)
- **Fit:** good. It shows the split used in this genre: a separate draft/construction step (often a fixed card order or a heuristic, tuned by Bayesian optimization in Inspirai) and a battle step with search or RL. Its evaluation method (randomized decks, mirrored matches, placement by win rate) is directly reusable for a yardstick. It is a different game, so the numbers do not transfer.

---

### Improving Hearthstone AI by Combining MCTS and Supervised Learning Algorithms (2018)
- **Link:** https://arxiv.org/abs/1808.04794 (HTML fetched at https://arxiv.org/html/1808.04794) · **Venue:** arXiv, Świechowski, Tajmajer and Janusz · **Cited by:** not checked · **Read:** full text
- **Problem:** Make MCTS for Hearthstone stronger by learning a state-value function and using it to cut search.
- **Method:** Determinized UCT MCTS over information sets (a PIMC and ISMCTS mix). The value net is a dense network (256, 128, 64; tanh; 750-element input; 2-way softmax) trained to predict the winner, with 10-dimensional word2vec card embeddings from card text. It is used for early cutoff after a player's last move in a turn (not before 20 steps). Training data came from a "cheater" MCTS that sees the true state, plus an iterative loop (20,000+ plain-MCTS games, then 3,000 games per iteration, capped at 1M samples).
- **Assumes:** Hearthstone simulator with 483 cards; two fixed decks (ZooWarlock and CubeWarlock). Time budget per move: 0.5 s or 1 s. Random sampling of hidden state for determinization. Deck building is out of scope.
- **Claims:** Plain MCTS vs MCTS: 73.5% P1 at 0.5 s and 70.6% P1 at 1 s. Value net (V) vs MCTS at 0.5 s: 82.0% (410 to 90). Board solver (S) vs MCTS at 0.5 s: 79.0%. Value net plus solver (VS) vs MCTS at 0.5 s: 78.4%. V vs MCTS at 1 s: 76.0%. VS vs random bot: 500 to 0. Value-net accuracy for the winner: 0.76 validation; 0.775 (P1) and 0.794 (P2) for one deck. Paper says heuristics add "up to 9 percentage points" for the first player and "even double the win-rate" for the second. Table totals are inconsistent with the stated 500 games (noted by the reader). Human-match table was hard to parse and is not quoted.
- **Evaluation:** About 500 games per configuration, per the text, against plain MCTS, with first and second player both counted.
- **Code:** none found
- **Fit:** good. It is the closest match in this set to the "search over a learned value net" with a teacher that sees the hidden state. The "cheater" MCTS teacher is an explicit teacher-student setup. It does not cover deck building, and its numbers are for a fixed pair of decks with a non-perfect simulator.

---

### Dominion: A New Frontier for AI Research (2024)
- **Link:** https://arxiv.org/abs/2405.06846 (HTML fetched at https://arxiv.org/html/2405.06846v1) · **Venue:** arXiv, Halawi et al. (Dominion Online dataset paper) · **Cited by:** not checked · **Read:** full text
- **Problem:** Make Dominion a benchmark game for AI, where each game uses a different card set (kingdom).
- **Method:** A Rainbow DQN bot (fully connected, two hidden layers of 256) learned by self-play. It picks which card to gain; action-card decisions come from the same heuristics Provincial uses. Opponents are heuristic buy-menu bots and the evolved Provincial bot (Fisher 2014, competitive coevolution). No tree search for either bot.
- **Assumes:** Ranked 2-player games with 2nd edition base set. State space of 17 to 25 cards and 15 to 40 turns. Kingdom of 10 cards drawn from up to 350. Training: 1000 steps, about 7000 games, about 45 minutes on an NVIDIA 1080 Ti. Dominion Online dataset of about 2,000,000 games, 30,000 processed.
- **Claims:** Table 2 (1000 games per matchup, heuristic goes first), Provincial W-T-L vs DQN-bot W-T-L: Big Money 972-44-24 vs 912-27-61 (Provincial row sums to 1040, a typo); Double Witch 596-69-335 vs 561-63-376; Big Smithy 930-7-63 vs 851-38-111; Big Militia 946-9-45 vs 850-31-119; Village/Smithy Engine 994-2-4 vs 418-24-558; Provincial menu 550-53-397 vs 575-62-363. "DQN-bot beats or ties Provincial almost two thirds of the time." Provincial vs Provincial: first player 55%, second 40%.
- **Evaluation:** Matchups are 1000 games against each heuristic, not a full round-robin. Fig. 1(b) averages 10,000 games among five Provincial strategies. Dominion Online rating (Glicko-2): dataset players average μ = 0.65 and φ = 0.17.
- **Code:** dataset described in the paper; no repository link checked
- **Fit:** partial. Strong for the "random card set per game" framing and for the head-to-head evaluation with a fixed number of games. It has no search, so it does not inform the tree-search side. It is a deck-building-by-buying benchmark, not combat play.

---

### Drafting in Collectible Card Games / AI solutions for drafting in Magic: the Gathering (2020)
- **Link:** https://arxiv.org/abs/2009.00655 · **Venue:** arXiv (Magic: The Gathering drafting) · **Cited by:** not checked · **Read:** abstract only (the HTML and PDF were not opened; the search summary also mentioned a 2019 SBGames short paper and a 2020 arXiv version by Vieira and colleagues, which I did not verify)
- **Problem:** Emulate human drafting in Magic, a sub-game where players pick cards from a common pool to build a deck.
- **Method:** Four drafting agents: a primitive heuristic, an expert-tuned heuristic, a Naive Bayes agent and a deep neural network agent. Accuracy is analysed across the draft timeline.
- **Assumes:** Over 100,000 simulated, anonymized human drafts from Draftsim.com. The task is to pick like a human, not to win games.
- **Claims:** Qualitative only in the abstract: "the deep neural network agent outperforms other agents, while the Naive Bayes and expert-tuned agents outperform simple heuristics." No exact numbers in the abstract.
- **Evaluation:** Ability to emulate human drafting on the Draftsim dataset. No game play evaluation in the abstract.
- **Code:** none found
- **Fit:** poor. It evaluates drafting by pick-matching, not by win rate, and does not cover play. Its one useful point is the dataset-plus-accuracy evaluation style, which is a cheap yardstick for a deck picker.

---

### AutoClad (repository README, benmuth)
- **Link:** https://github.com/benmuth/AutoClad · **Venue:** GitHub repository (non-academic) · **Cited by:** not checked · **Read:** full text (README page)
- **Problem:** Train neural network agents to play Slay the Spire by supervised learning.
- **Method:** Forks sts_lightspeed. Generates randomized battle scenarios, runs a baseline agent (SimpleAgent) to collect demonstrations, extracts state-action pairs, trains a network to imitate the baseline, exports TorchScript for C++ inference. Tree search and RL are listed as later plans, not implemented.
- **Assumes:** Simulator is the C++ sts_lightspeed fork. Python for training, C++ for simulation and inference (LibTorch needed to run). Only Jaw Worm encounters work; more encounters are in progress.
- **Claims:** No win-rate, accuracy or dataset-size numbers. The only number is `--count 20` in a command.
- **Evaluation:** `just run-agent neural --scenario=jaw_worm`. The README says it is "benchmarking different approaches" but reports no metrics.
- **Code:** https://github.com/benmuth/AutoClad · license file LICENSE.md present, type not named on the page
- **Fit:** partial. It is an imitation-of-a-scripted-teacher pipeline on the same simulator family, which is relevant to the teacher-student question. It has no results, so it cannot serve as a yardstick.

---

### Slay the Cultist series, part 4 (blog, doronsinger)
- **Link:** https://dev.to/doronsinger/part-4-slay-the-cultist-9n7 · **Venue:** dev.to blog post (non-academic) · **Cited by:** not checked · **Read:** full text (web page)
- **Problem:** Train a PPO agent for combat against the Cultist, the simplest early encounter, and find out why it learns badly.
- **Method:** PPO with a per-card hand scoring head; earlier, mean-pooled hand contents. The author later moved to a search-based architecture, which they still consider "probably correct" (not detailed in the post).
- **Assumes:** Headless environment meant to be "perfectly true to the real game." Cultist is "perfectly predictable," so draw order is the only unknown. PPO settings: learning rate 3e-4, 1,024 steps per batch, minibatch 256, 10 epochs, gamma 0.99, GAE lambda 0.95, clip 0.2, entropy 0.15.
- **Claims:** Mean-pooled baseline: 200,000 training steps (about 14,000 fights), "reached a 70% win-rate." Per-card scoring: "100% win-rate after only 10,000 steps", which the author calls "fallacious" because of an energy-reset bug. Average HP at fight end: about 47, then 55 after reward changes, 63 with a scripted always-block heuristic, which later fell to about 34 before recovering to 55.
- **Evaluation:** Single encounter, Cultist. Metrics are win rate and HP at fight end.
- **Code:** none found in the post
- **Fit:** partial. Combat only, no deck or route. Its main value is a warning: effects silently skipped and an energy bug made the simulator wrong, and a learning "latch" bug stopped learning after about a third of a run. It also shows a scripted heuristic can match a learned policy on one metric while not learning anything.

---

### sts-rl-agent (Hugging Face model card, Jialeiv)
- **Link:** https://huggingface.co/Jialeiv/sts-rl-agent · **Venue:** Hugging Face model page (non-academic; a write-up on the page) · **Cited by:** not checked · **Read:** full text (model page)
- **Problem:** Learn the non-combat decisions (map pathing, card rewards, shops, campfires, events) for Slay the Spire, while combat stays with the simulator's built-in MCTS.
- **Method:** Small MLP, about 100k parameters, hidden layers [128,128], trained from scratch with REINFORCE. Headline checkpoint trained on 15k games; an 8k-game checkpoint is also included.
- **Assumes:** Simulator sts_lightspeed (patched version and clean-room code). Ascension 0, Ironclad only, 50 fixed seeds, single run. Combat is MCTS with a fixed budget (2000 or 50000 iterations).
- **Claims:** Table (A0 Ironclad, 50 fixed seeds): stock bot heuristics with random map, MCTS @50000: avg floor 31.2, win rate 6%. This model, MCTS @2000: avg floor 38.5, win rate 4%. This model, MCTS @50000: avg floor 42.5, win rate 14%. Learned non-combat layer is worth "~11 floors" over the stock bot. Negative results on combat: behaviour cloning of MCTS reached floor about 12 vs teacher 23; value net with 1-ply lookahead about 8; attention model about 14; imitation accuracy plateaued at 0.44. Defect A20 track paused and incomplete, no Heart wins kept.
- **Evaluation:** Simulator runs at A0 with fixed seeds. No confidence intervals. Single run.
- **Code:** https://huggingface.co/Jialeiv/sts-rl-agent · MIT (listed on the model page; checkpoints included)
- **Fit:** good. It is the closest match to the split the project asks about: a learned policy for the decisions outside combat, with search for combat. Its failed attempts to distill MCTS combat into feed-forward nets are direct evidence about the teacher-student gap. It is A0 only, with a small sample, and the 50-seed results have no confidence intervals.

---

## Not found or not checked

- **"Conquer the Spire" paper:** a search turned up no paper by that title. Related items were a 2022 Carleton honours project (classical RL on early fights, not opened) and an IPSJ 2025 conference abstract (Cui and Yoshiura, deep Q-learning; not opened).
- **Forge (Magic: The Gathering) AI papers:** none found in one search. Forum threads only.
- **Hearthstone RHEA claim (over 97.5% vs original RHEA):** seen only in a README diff in search results; not opened, not verified.
- **Hearthstone Battlegrounds MCTS assistant (EPiC 2022):** seen only in search results (9.56% vs 26.26% of turns lost, 56% vs 46.91% wins); not opened.
- **Dominion MCTS thesis (Agder, 2014; Jansen and Tollisen 2015; Yan Princeton thesis):** seen in search results only; the Agder thesis claims 87.5% vs moderately experienced humans and 68.5% vs SingleWitch/DoubleWitch; not opened, not verified.
- **Japanese write-up on SpireBench (20 LLMs, Ascension 20 Ironclad):** seen in a search result only (automaton-media.com); not opened.
- **bottled_ai winrates page (docs/winrates.md):** linked from the README; not opened.

## Cross-cutting notes for the strength question

- Known Slay the Spire yardsticks: Epoch's SpireClimb (LLM with screen, no simulator) gives a frontier-model number; bottled_ai's 52% (Watcher, no ascension stated); the HF sts-rl-agent's A0 Ironclad table (14% at MCTS @50000, 50 seeds). None of them is on the same protocol.
- Card-game competitions (LOCM) use a fixed opponent-free protocol: randomized decks, mirrored matches, placement by win rate. That is the most reusable evaluation pattern in this set.
- Split of the game into deck construction and battle, as seen in the sources: LOCM competitions (fixed card order or heuristic for draft, search or PPO for battle); Hearthstone MCTS (fixed decks, deck building out of scope); Dominion (buy-menu and card-gain decisions learned separately from play); the STS RL agent (non-combat learned, combat by MCTS).
