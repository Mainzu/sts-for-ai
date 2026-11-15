# Card-game search bots: papers on building and ranking (angle: Hearthstone, LOCM, ToT)

Scout: card-game-search angle. 8 papers opened: 6 with full text (arXiv HTML), 2 abstract only.
Failed to open: Battleground MCTS assistant (EPiC, easychair PDF unreadable); Annals 2021 "Practical Solution to Handling Randomness" (PDF unreadable); Santos 2017 Hearthstone MCTS thesis (LabJogos page had no content).

### Summarizing Strategy Card Game AI Competition (2023)
- **Link:** https://arxiv.org/html/2305.11814 · **Venue:** arXiv preprint (cs.AI); same title is at IEEE CoG 2023 (doi 10.1109/cog57401.2023.10333181) · **Cited by:** 10 (OpenAlex, CoG record) · **Read:** full text
- **Problem:** Five years of competitions on Legends of Code and Magic (LOCM), a small CCG built for fair AI-vs-AI play with imperfect information and randomness.
- **Method:** Retrospective. Lists winners per edition and what each bot did (Coac: depth-3 minimax-like search with alpha-beta and pruning; Chad: MCTS with opponent hand prediction and harmony-search card weights; DrainPower: flat simulation with heuristic evaluation; ByteRL: end-to-end deep RL with optimistic smooth fictitious play and an LSTM).
- **Assumes:** Fixed set of random seeds; each player uses a fixed number of randomly sampled decks, each played ten times on the same seed; both seats mirrored. Memory 256 MB (1024 MB or more disqualifies); UNIX-based runner; doubled turn time in v1.2, four seconds for the construction turn in v1.5.
- **Claims:** Table I win rates. CEC 2019: Coac 94.22% vs UJIAgent2 58.93%. COG 2019: Coac 89.88% vs ProphetCoac 87.84%. CEC 2020: Coac 86.07% vs Chad 79.10%. COG 2020: Chad 79.99% vs Coac 74.68%. COG 2021: DrainPowerAggressive 78.72% vs DrainPower 77.96%. COG 2022 (v1.5): ByteRL 84.41% vs NeteaseOPD 75.00%. No round-robin format, game count per pair, or confidence intervals given on the page.
- **Evaluation:** SCGAI competitions on LOCM v1.2 and v1.5 via CodinGame and CEC/COG.
- **Code:** "SCGAI repository" mentioned with no URL or license on the page. Linked elsewhere as https://github.com/acatai/Strategy-Card-Game-AI-Competition (from the ByteRL paper below; license not stated there).
- **Fit:** good. Directly about how competition bots were ranked and what separated winners; but ranking statistics are thin (no CI, no game counts).

### Improving Hearthstone AI by Combining MCTS and Supervised Learning Algorithms (2018)
- **Link:** https://arxiv.org/html/1808.04794 · **Venue:** IEEE CIG 2018 (doi 10.1109/cig.2018.8490368); the arXiv text is v1, not camera-ready · **Cited by:** 54 (OpenAlex) · **Read:** full text
- **Problem:** Hidden information, random effects and large branching make plain MCTS weak in Hearthstone.
- **Method:** MCTS with a transposition table keyed by information sets (ISMCTS/PIMC-style). A "board solver" proposes attack sequences as one per-turn action. A value network (256-128-64 dense, tanh; 750-element state vector) cuts simulations early after k=20 steps and feeds MCTS statistics. Trained iteratively: about 20,000 initial games, then 3,000 per iteration, 1M-sample FIFO buffer, 64 iterations.
- **Assumes:** Two fixed decks (ZooWarlock for P1, CubeWarlock for P2) with fixed seats; time per move 0.5 s or 1.0 s; custom C++ simulator at about 10K games per second; hardware not stated. Training data came from a "cheater" determinization that sees hidden information.
- **Claims:** Each configuration played 500 games vs plain MCTS. At 0.5 s/move, plain MCTS as P1 won 73.5% (vs MCTS as P2). P1 with value net (V) 82.0%, solver (S) 79.0%, both (VS) 78.4%. At 1.0 s/move: baseline 70.6%; VS 72.9%; V 76.0%; S 71.6%. VS bot won 500 of 500 vs random. Second-player table is garbled in extraction; the text reports about 56% for the best second-player config. No confidence intervals reported.
- **Evaluation:** 500-game matches, fixed decks, vs plain MCTS and random; two human-match sets (regular and Legend-rank players) with unclear counts.
- **Code:** none found (links only to HearthSim and SabberStone as engines).
- **Fit:** partial. Good for determinized-MCTS plus learned value and the 500-game paired design; the setup (two fixed decks, fixed seats) is far from a randomized, hidden-order run, and no CI is reported.

### Introducing Tales of Tribute AI Competition (2023, rev. 2024)
- **Link:** https://arxiv.org/html/2305.08234 · **Venue:** arXiv preprint (v4, May 2024); competition at IEEE CoG 2023 and 2024 · **Cited by:** not checked · **Read:** full text
- **Problem:** A CCG/deck-building game (Tales of Tribute) with randomness, hidden information, large branching and long-term planning; the authors note no other AI competition exists for this genre.
- **Method:** Competition framework (Scripts of Tribute, C# engine, JSON-over-pipes adapter for other languages). Round robin between entrants plus sample agents; games continue until the winrate ranking "clearly stabilizes."
- **Assumes:** 10 s per turn and 256 MB memory for competition matches. Each pair plays the same seeds twice with seats switched. Ranking is by winrate.
- **Claims:** Ranking uses win rates with 95% CIs; sample tournament used 400 games per pair (paper notes it used 30 s per turn, not the 10 s in the rules). Sample tournament averages: MCTS 65.7%, Decision Tree 63.9%, Beam Search 63.1%. Top agents form a rock-paper-scissors pattern, no clear winner. TOTAIC 2023 winner (Ciężkowski and Krzyżyński): five MCTS trees, one per game seed, averaged; win rates 79.22% vs Beam Search, 81.33% vs MCTS, 93.12% vs Decision Tree. No formal ranking formula or significance test for the competition.
- **Evaluation:** Round robin, 400 games per pair (sample tournament), same seed twice with switched seats.
- **Code:** https://github.com/ScriptsOfTribute (and archive at https://github.com/ScriptsOfTribute/ScriptsOfTribute-CompetitionsArchive); license not stated on the page.
- **Fit:** good. Most explicit on ranking method (round robin, same seeds with switched seats, CIs, stop rule). Not a Hearthstone or StS paper, but a card game with the same ranking problem.

### Learning to Beat ByteRL: Exploitability of Collectible Card Game Agents (2024)
- **Link:** https://arxiv.org/html/2404.16689 · **Venue:** Adaptive and Learning Agents workshop (ALA 2024), arXiv:2404.16689v1 · **Cited by:** not checked · **Read:** full text
- **Problem:** How exploitable is ByteRL, the LOCM state-of-the-art, which uses no search? Models LOCM as a single-agent POMDP against a fixed opponent.
- **Method:** Behaviour cloning on about 125k ByteRL-vs-ByteRL matches (about 3.5M state-action pairs), then PPO (RLlib) fine-tuning from the BC net on fixed deck pools of 32 to 1024 decks. Draft stage is not learned; ByteRL drafts both sides.
- **Assumes:** LOCM battle phase; fixed deck pools (smaller than the full procedural game); five seeds per RL setting.
- **Claims:** Win rate vs ByteRL, final round averaged over five runs, pool sizes 32/64/128/256/512/1024. BC pretrain: 0.904, 0.822, 0.803, 0.801, 0.734, 0.542. No pretrain: 0.812, 0.780, 0.812, 0.720, 0.533, 0.418. BC alone 42.4% (1000 matches). Evaluation every 20 iterations with 100 matches; 95% CIs given only in plots. No formal exploitability value; the win rate is the measure.
- **Evaluation:** 100-match checkpoint evaluations (greedy actions); 1000-match final check for the BC net.
- **Code:** Links to https://github.com/acatai/Strategy-Card-Game-AI-Competition (game manager, example bots, ByteRL weights said to be there); license not stated.
- **Fit:** partial. Good on how strength is measured against a fixed strong bot and on the number of matches; the setting is LOCM, not StS, and the "exploitability" is only a win rate.

### Evolving Evaluation Functions for Collectible Card Game AI (2021)
- **Link:** https://arxiv.org/html/2105.01115 · **Venue:** arXiv preprint (v1, 3 May 2021); no venue listed · **Cited by:** not checked · **Read:** full text
- **Problem:** Which genome representation and which fitness opponent work best for evolving evaluation functions in a CCG?
- **Method:** Three genomes (Linear: 20 weights; BinaryTree; Tree). Three fitness schemes: Progressive (self-play), Weak-op (fixed weak opponent), Strong-op (fixed stronger opponent). Plus two "From-Linear" seeded variants.
- **Assumes:** LOCM battle phase (deterministic; randomness from card order and unknown opponent deck). 50 generations, population 50, elitism 5, mutation 5%, 10 drafts, 10 rounds.
- **Claims:** Tournament win rates (average ± SD over tournament field): Weak-op 42.9 ± 15.7% (Linear), 33.8 ± 14.2% (BinaryTree), 36.2 ± 15.7% (Tree). Strong-op 48.9 ± 16.6%, 45.1 ± 16.9%, 44.8 ± 15.7%. Progressive 54.8 ± 18.0%, 45.5 ± 16.8%, 45.6 ± 18.7%. Tree-from-Linear 60.2 ± 17.4% vs Linear-from-Linear 58.0 ± 17.1%. Head-to-head BinaryTree-weak-op beat WeakOp 82.9 ± 2.67%. Games per evaluation: 9,800 (Progressive) or 10,000 (fixed opponents). Only standard deviations reported; no CIs or significance tests (paper calls a ~2-point gap "relatively minor but consistent").
- **Evaluation:** LOCM tournament over the full field.
- **Code:** none found in the text; only the arXiv license shown.
- **Fit:** partial. Useful for the fitness-opponent choice (self-play vs fixed) and games-per-evaluation counts. Not search-based; evaluation functions for a single-decision rule player.

### Mastering Strategy Card Game (Hearthstone) with Improved Techniques (2023)
- **Link:** https://arxiv.org/html/2303.05197 · **Venue:** arXiv cs.LG (v2, May 2023); acknowledges CoG 2023 reviewers, acceptance not confirmed on the page; OpenAlex lists the CoG 2023 version (doi 10.1109/cog57401.2023.10333220) with 16 citations · **Cited by:** 16 (OpenAlex, CoG record) · **Read:** full text
- **Problem:** Can an end-to-end agent trained from scratch reach master-level full Hearthstone (deck build and battle) with no search at training or play?
- **Method:** Base is OSFP (the COG2022 LOCM winner's approach) with V-Trace and UPGO; one network for deck and battle. Hero pick excluded from the policy. Then added changes: gamma=1.0; random deck-building start; halved actors; V-Trace/PPO-style clipping; separate model per hero; and a cheat variant seeing part of the opponent's deck.
- **Assumes:** Approximates the April 2015 Blackrock Mountain version (modified Hearthbreaker). Mage, Warrior, Hunter; 350+ cards, about 270 per hero; 30-card decks built by the agent; LSTM (256). No explicit determinization or info-set search. Compute: 24 V100 GPUs, 5,856 CPU cores for the largest model.
- **Claims:** Machine-vs-machine (Table I): b4 vs b0 73.6%; c5 vs b0 80.2%; c5 vs b4 55.5%. Protocol: 2 × 3 × 3 × 2,500 = 45,000 matches per pairing. Stage gains reported: +7% (gamma), +10.0% (halved actors), +15.1% (V-Trace/PPO), +6.5% (per-hero model), +5.5% (cheat). Human test: four Best-of-5 tournaments vs a top-10 China-league streamer (ranked 60–70 during the test); agent won all four (3:0, 3:0, 3:1, 3:2).
- **Evaluation:** Hearthstone environment (modified Hearthbreaker), 45,000-match pairings; 4 Bo5 human matches.
- **Code:** none linked for the authors' code; links only to Hearthbreaker and a hearthstone-ai project; no license stated.
- **Fit:** partial. Strong on the matchup count and the self-play ranking design (all heroes, both seats); it is a no-search policy, so it helps only as a contrast to search bots. The setting (full deck building, 2015 cards) is far from a single-combat engine.

### Enhancing Monte Carlo Tree Search for Playing Hearthstone (2019)
- **Link:** https://pure.korea.ac.kr/en/publications/enhancing-monte-carlo-tree-search-for-playing-hearthstone/ (landing page; DOI https://doi.org/10.1109/CIG.2019.8848034) · **Venue:** IEEE CoG 2019, London (IEEE CIG series, vol. 2019-August) · **Cited by:** 21 (OpenAlex) · **Read:** abstract only
- **Problem:** Hearthstone's hidden hand and deck, and a big branching factor from many atomic actions per turn, make search hard.
- **Method:** MCTS with state abstraction into a DAG and a UCT variant for it; sparse sampling to handle randomness and imperfect information and cut stochastic branching.
- **Assumes:** Hearthstone; hidden information from hand and deck. Abstract gives no setup details.
- **Claims:** The abstract says the approach "works well" and gives no numbers on this page; full text is paywalled (Scopus/DOI only).
- **Evaluation:** Not visible from the landing page.
- **Code:** none listed.
- **Fit:** partial. Method is the sparse-sampling and DAG idea for hidden info; numbers unavailable without the paywalled paper.

### Zhang 2017 MSc thesis: Improving Collectible Card Game AI with Heuristic Search and Machine Learning Techniques (2017)
- **Link:** https://ualberta.scholaris.ca/handle/123456789/89399 (landing page; PDF at https://era.library.ualberta.ca/files/cv979v349b/Zhang_Shuyi_201709_MSc.pdf is 13.6 MB and was not readable) · **Venue:** University of Alberta MSc thesis (supervisor Michael Buro) · **Cited by:** 0 (OpenAlex) · **Read:** abstract only
- **Problem:** Hearthstone's multi-action turns and card draws give very large branching, which challenges heuristic search.
- **Method:** Determinized MCTS. Chance node bucketing (CNB) groups similar chance outcomes into pre-sampled buckets in the in-tree phase. High-level policy networks train rollout policies and can also play alone.
- **Assumes:** Hearthstone (game version and decks not visible from the landing page). The abstract does not describe how hidden information is determinized.
- **Claims:** Abstract says "significant improvements over a state-of-the-art AI system"; no win rates, opponents, game counts or time per move on the landing page.
- **Evaluation:** Not visible from the landing page; the full PDF would be needed.
- **Code:** none linked. Thesis is for non-commercial use per the page's licence note.
- **Fit:** partial. The only determinized-MCTS Hearthstone thesis found, but the numbers and the determinization step are not readable here; a PDF reader would be needed.

## Notes for the caller
- Ranking evidence is the strongest part of this set: Tales of Tribute (round robin, same seeds with switched seats, 95% CIs, 400 games per pair, stop when ranking stabilizes) and the LOCM retrospective (win rates per edition, no CIs). Most others give 500 games per config (2018) or only SDs (2021).
- Top LOCM bots changed by edition: search (Coac minimax, Chad MCTS, DrainPower flat MC) won 2019 to 2021; end-to-end RL (ByteRL) won 2022. Search-based winners include a depth-3 alpha-beta minimax (Coac), which the Summarizing paper says was about 33% stronger than the runner-up in 2019 (table gap about 35 points).
- Not checked, for the caller: Hearthstone competition bots (MetaStone/SabberStone CoG 2018 to 2020) have no open results in this scout; the Annals 2021 paper (https://annals-csis.org/Volume_15/drp/pdf/386.pdf) returned unreadable PDF bytes.
