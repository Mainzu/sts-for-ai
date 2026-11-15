# Slay the Spire and deckbuilder AI: academic prior art (cards)

Scouted 2026-11-15. Angle: academic papers, theses and course projects on StS or StS-like deckbuilders, plus adjacent CCG/deckbuilding work (MCTS, RL, card valuation, automated playtesting, procedural cards). Breadth via web search and OpenAlex keyword search; depth via a few reference chains. 13 papers opened (7 full text, 6 abstract only). Cards below are for those 13 papers. A code artifact (MiniStS repo) and a list of unopened leads follow the cards.

---

### Dominion: A New Frontier for AI Research (2024)
- **Link:** https://arxiv.org/html/2405.06846v1 · **Venue:** arXiv (cs.AI) · **Cited by:** not checked · **Read:** full text
- **Problem:** Make Dominion a benchmark: each game uses a different card set, and the authors release a large human game dataset.
- **Method:** DQN-bot: Rainbow DQN buyer, self-play, two 256-unit hidden layers, takes state and action mask, picks which card to gain; action-card decisions come from Provincial's heuristics. Baseline Provincial is a buy-menu bot evolved by competitive coevolution (Fisher, 2014).
- **Assumes:** Dominion (real card game, 2nd edition base set), ranked 2-player games; 10 kingdom cards from a pool of over 350 per game. Kingdom sampling for the training and evaluation runs is not stated.
- **Claims:** DQN-bot compute: 1,000 steps (about 7,000 games) in roughly 45 minutes on an NVIDIA 1080 Ti. Table 2 (1,000 games per matchup, heuristic bot moves first): Provincial W/T/L vs Big Money 972/4/24; DQN-bot vs Big Money 912/27/61; DQN-bot vs Village/Smithy Engine 418/24/558 (Provincial vs it 994/2/4). "DQN-bot beats or ties Provincial about 64% of the time (637 of 1,000)." Authors attribute the Village/Smithy weakness to that strategy being absent from training. Dataset: over 2,000,000 games from Dominion Online.
- **Evaluation:** Buy-menu matchups among heuristic bots, Provincial and DQN-bot on fixed kingdom sets; no unseen card-set test.
- **Code:** not checked.
- **Fit:** partial. Documents the per-card-set generalisation gap as the main weakness of a learned buyer (the Village/Smithy result). It is a gain-only decision problem, not combat, and it does not test unseen cards.

### Learning With Generalised Card Representations for "Magic: The Gathering" (2024)
- **Link:** https://arxiv.org/html/2407.05879v1 · **Venue:** IEEE Conference on Games (CoG) 2024 · **Cited by:** 7 (OpenAlex) · **Read:** full text
- **Problem:** Predict human draft picks for cards the model has never seen, so the model does not need retraining per card set.
- **Method:** Contextual preference ranking with a Siamese network (triplet loss, margin 1). Card encoder of 4 FC layers (1024 units), deck encoder of 6 conv layers, 512-d tanh embedding. Input variants: one-hot IDs, random vectors, autoencoded card images, hand-coded features (numerical, categorical, and a sentence-transformer text embedding; 1306 inputs), and 16 17Lands meta statistics.
- **Assumes:** Discrete draft picks in MTG; cards described by text and numeric features; 17Lands usage/win-rate stats available for trained sets (the paper notes these are unavailable for brand-new sets). Target is the human pick (top-1), not play strength.
- **Claims:** NEO-trained model, average over unseen sets: one-hot n/a, Random (1024) 23.79%, Features 33.57%, Features + Meta + Image (1024) 42.87%. Pre-training on all sets except BRO (about 75M picks, 2,990 cards), BRO unseen: 55.44% top-1 (abstract: "predict 55% of human choices on completely unseen cards"). Random guessing is about 22% in this setup. Compute not reported.
- **Evaluation:** 14 MTG sets (LTR to M19), about 100M picks, 80/20 train/test split; held-out BRO set for the unseen-card test.
- **Code:** none found (the paper links only a third-party mtg repo as context).
- **Fit:** partial. Directly tests generalisation to unseen cards through text and feature encodings, which is close to reading cards by effect text. It is a draft-imitation metric, not play strength, and the best unseen-card signal relies on meta stats that generated cards would not have.

### Analysis of Uncertainty in Procedural Maps in Slay the Spire (2025)
- **Link:** https://arxiv.org/html/2504.03918 · **Venue:** FDG 2025 · **Cited by:** 1 (OpenAlex) · **Read:** full text
- **Problem:** Measure how much route randomness in StS maps relates to run outcomes and player skill.
- **Method:** Shannon entropy over location types along each played path, normalised by the min and max entropy of all possible paths. A map-generation oracle rebuilds each run's full map from its seed. Welch's t-tests (alpha 0.05). No agents or learned policies.
- **Assumes:** Real StS (Ascension Ironclad runs), developer-released logs with seeds; 77M runs released, 20,000 sampled after filtering.
- **Claims:** All acts, victory vs defeat: t = -64.63, p < 0.001. Act 1: t = -1.14, p = 0.25 (not significant). Act 2: t = -39.70; Act 3: t = -87.78. Skill (Ascension <=10 vs >10), all acts: t = 14.12, p < 0.001. Location entropies: Act 1 first three monster encounters = 2.0; shop and rest-site rooms = 0.
- **Evaluation:** Logged human runs from the developers' dataset; no simulated test.
- **Code:** none found.
- **Fit:** partial. Shows that the seed-to-map oracle is a practical way to analyse the run layer from logs. It does not provide a policy for route choice, and its Act 1 result is not significant.

### Introducing Tales of Tribute AI Competition (2023; extended version 2024)
- **Link:** https://arxiv.org/html/2305.08234v4 · **Venue:** IEEE CoG 2024 (extended arXiv v4) · **Cited by:** not checked · **Read:** full text
- **Problem:** A competition framework and sample-agent baselines for a two-player deck-building CCG with randomness and hidden information.
- **Method:** Sample agents: Random, Max Prestige, Patron Favors, Max Agent (static card tier list), Decision Tree, Flat MC, MCTS (guided playouts, max-based UCT), Beam Search. No RL or neural agents among the samples.
- **Assumes:** Tales of Tribute (not StS): 2 players, shuffled draw piles, a shared five-card tavern, hidden opponent hand and draw order. Time limits: 30 s per turn in the tournament, 10 s per turn and 256 MB in the competition.
- **Claims:** Round robin of 400 games per pair. MCTS vs Beam Search 51.5%, MCTS vs Decision Tree 43.8%, MCTS vs Flat MC 15.2%, MCTS vs Max Prestige 26.8% (row = MCTS). The 2023 competition winner (root-parallelised MCTS) beat Beam Search 79.22%, MCTS 81.33%, Decision Tree 93.12%. The extracted average row does not match the pairwise table, so use only the pairwise numbers, with the caveat that the table extraction was garbled. CI about ±3–5 points.
- **Evaluation:** Round-robin tournament among the sample agents plus the competition framework; no unseen-card test.
- **Code:** not checked (competition framework is a separate repo; not verified).
- **Fit:** partial. Good evidence that MCTS and beam search are the strong baselines in a stochastic, hidden-information deckbuilder, with short per-turn time limits. Not StS and not expectimax.

### Improving Hearthstone AI by Combining MCTS and Supervised Learning Algorithms (2018)
- **Link:** https://arxiv.org/abs/1808.04794 · **Venue:** IEEE CIG 2018, pp. 445–452 · **Cited by:** not checked · **Read:** abstract
- **Problem:** Make MCTS under hidden information and randomness stronger and cheaper in Hearthstone.
- **Method:** A custom MCTS for games with hidden information and random effects. Supervised models (including a simple NN) trained to evaluate states; the evaluations guide the search.
- **Assumes:** Hearthstone (real game, card pool fixed); state evaluator learned from game data.
- **Claims (abstract only, qualitative):** using the learned evaluations to guide search "substantially raises the win rate while reducing the computation." No numbers on the abstract page.
- **Evaluation:** Not read; full text needed for opponents, game counts and compute savings.
- **Code:** none found.
- **Fit:** partial. The learned-evaluator-guides-search pattern matches a value net under expectimax, but with no numbers from the abstract alone, it cannot be checked.

### Mastering Strategy Card Game (Hearthstone) with Improved Techniques (2023)
- **Link:** https://ar5iv.labs.arxiv.org/html/2303.05197 (arXiv 2303.05197) · **Venue:** arXiv (ByteDance authors) · **Cited by:** not checked · **Read:** full text
- **Problem:** Learn deck building and battle end-to-end for Hearthstone.
- **Method:** One policy for both deck building and battle, trained with Optimistic Smooth Fictitious Play and a policy-gradient method (V-trace and UPGO, later PPO-style clipping). The authors state the approach does not require look-ahead search in training or inference. No tree search.
- **Assumes:** Custom Hearthstone environment based on Hearthbreaker, April 2015 Blackrock Mountain rules; 3 heroes (Mage, Warrior, Hunter); 350+ cards in a fixed pool.
- **Claims:** Compute for the best non-cheat model b4: 24 V100 GPUs and 5,856 CPU cores. Machine vs machine: b4 beat baseline b0 73.6%; cheat model c5 beat b0 80.2% and b4 55.5%; each matchup 2×3×3×2500 matches. Human: b4-23day won two Best-of-5 Conquest tournaments 3:0 and 3:0 vs one streamer; c5-16day won 3:1 and 3:2 (small sample: one human, four tournaments).
- **Evaluation:** Self-play in a fixed card pool plus one human opponent. The paper does not test unseen cards or decks.
- **Code:** not checked.
- **Fit:** poor. Opposite of the constraints on compute (cluster-scale) and it has no search and no unseen-card test. Useful as a cost and generalisation contrast.

### Deep Surrogate Assisted MAP-Elites for Automated Hearthstone Deckbuilding (2021; GECCO 2022)
- **Link:** https://arxiv.org/abs/2112.03534 · **Venue:** GECCO 2022 · **Cited by:** 30 (OpenAlex, GECCO record) · **Read:** abstract
- **Problem:** Generate diverse, strong Hearthstone decks with fewer expensive evaluations.
- **Method:** MAP-Elites with a deep surrogate model, trained online to predict game outcomes for candidate decks; the surrogate guides MAP-Elites toward promising decks.
- **Assumes:** Hearthstone deck outcomes from simulated games; deck-level surrogate.
- **Claims (abstract only):** outperforms an offline model trained on random decks and a linear surrogate; "new state of the art" for QD deckbuilding. No numbers on the abstract page.
- **Evaluation:** Not read.
- **Code:** none found.
- **Fit:** partial. A surrogate-for-expensive-evaluation pattern that could apply to deck-level scoring; deck-level, not card-level.

### It might be balanced, but is it actually good? An Empirical Evaluation of Game Level Balancing (2024)
- **Link:** https://arxiv.org/html/2407.11396v1 · **Venue:** IEEE (copyright 2024) · **Cited by:** not checked · **Read:** full text
- **Problem:** Does PCGRL-based automated balancing improve perceived balance for humans?
- **Method:** An RL balancer (PCGRL) that swaps tiles to hit a 0.5 win rate, with rewards from simulated heuristic-agent games; compared with a human survey.
- **Assumes:** A 6x6 tile survival game adapted from Neural MMO, not a card game.
- **Claims:** 71 valid responses; per-scenario n = 16, 20, 23, 12; significant gains in some items (e.g., Scenario 2 player movement difficulty median -2 to 0, p = 0.00002). Scenario 4 showed no significant difference. Caveat: scripted agents may not match human play; no multiple-comparison correction.
- **Evaluation:** Human survey on generated levels.
- **Code:** not checked.
- **Fit:** poor. Not cards or StS. Included because it documents the agent-fidelity caveat for automated playtesting, which the constraints do not need to cover.

### Valet: A Standardized Testbed of Traditional Imperfect-Information Card Games (2026)
- **Link:** https://arxiv.org/html/2603.03252 (arXiv 2603.03252) · **Venue:** arXiv preprint · **Cited by:** not checked · **Read:** full text (html, via summariser)
- **Problem:** A standard testbed of imperfect-information traditional card games to compare algorithms across games.
- **Method:** 21 traditional card games encoded in the RECYCLE game description language. Random agents and an MCTS first player (10 determinizations per decision point; budget 100 times the number of choices), run in the CardStock GGP system.
- **Assumes:** Traditional card games (Hearts, Euchre, Rummy, Leduc, etc.), not deckbuilders; all cards are fixed by the game description.
- **Claims:** 200 simulations per game (100 all-random, 100 MCTS first player). MCTS beat random in all games except Cuckoo. Rummy has the largest gap, "with MCTS often scoring zero." Go Fish and Crazy Eights show little separation. Compute not reported.
- **Evaluation:** The 21-game suite with random and MCTS players.
- **Code:** not checked (RECYCLE and CardStock are the referenced systems).
- **Fit:** poor. No deckbuilding, no StS, no unseen content. Its determinization handling of hidden cards is a documented limitation (it does not model information inferred from action history).

### Rule Synergy Analysis using LLMs: State of the Art and Implications (2025)
- **Link:** https://arxiv.org/abs/2508.19484 · **Venue:** submitted to IEEE Transactions on Games · **Cited by:** not checked · **Read:** abstract
- **Problem:** Can LLMs judge rule interactions between cards (positive, negative, neutral synergy) in StS?
- **Method:** Evaluates LLMs on a dataset of StS card pairs labelled for synergy; categorises errors (timing, state definition, rule following).
- **Assumes:** LLM in the loop as the thing being evaluated.
- **Claims:** LLMs "excel at identifying non-synergistic pairs" but struggle with positive and especially negative synergies. No numbers in the page text.
- **Evaluation:** A labelled set of StS card pairs (dataset size not stated in the text I could read).
- **Code:** not checked.
- **Fit:** poor for the method (LLM in loop, which the constraints forbid). Partial as a source of a synergy-labelled StS card-pair dataset, if the dataset is released.

### Predicting Drafted Deck Strength for "Magic: the Gathering" (2026)
- **Link:** https://arxiv.org/abs/2607.04782 · **Venue:** IEEE CoG 2026 (accepted) · **Cited by:** not checked · **Read:** abstract
- **Problem:** Predict deck strength from MTG draft picks, treating the card pool as changing.
- **Method:** Encoder-based model producing set-contextualised card embeddings that encode the pick sequence; predicts deck outcomes from them.
- **Assumes:** MTG Draft format (39–45 picks, 8 players, 40-card deck), card selection separated from gameplay.
- **Claims (abstract only):** "consistent improvement over linear baselines" on large-scale real data; no numbers on the page.
- **Evaluation:** Real-world draft data; not read.
- **Code:** not checked.
- **Fit:** partial. Deck-level strength from picks, card selection isolated from play; not a play-strength test.

### Improving Collectible Card Game AI with Heuristic Search and Machine Learning Techniques (MSc thesis, 2017)
- **Link:** https://ualberta.scholaris.ca/handle/123456789/89399 (PDF linked there; not readable through WebFetch) · **Venue:** University of Alberta MSc thesis, supervisor Michael Buro · **Cited by:** not checked · **Read:** abstract
- **Problem:** Stronger search for Hearthstone (Silverfish-class AI).
- **Method:** Determinized MCTS with chance node bucketing (CNB): bucket chance outcomes with similar effects and pre-sample per bucket; applied in the in-tree phase. High-level policy networks guide rollouts.
- **Assumes:** Hearthstone, real game rules via the Silverfish engine.
- **Claims (abstract only):** "significant improvements over a state-of-the-art AI system." Win rates are in the thesis body (section "Win Rates of UCT with Different CNB Settings"), not read.
- **Evaluation:** Hearthstone matches vs Silverfish (not read).
- **Code:** none found.
- **Fit:** partial. The CNB idea is the closest prior art for reducing chance-node branching in search, but it is a bucketing approximation, not the exact averaging the constraints ask for. Companion CIG 2017 paper "Improving Hearthstone AI by Learning High-Level Rollout Policies and Bucketing Chance Node Events" (pp. 309–316) was not opened (its PDF did not load).

### Mazocarta: A Seeded Procedural Deckbuilder for Instrumented Game Development (2026)
- **Link:** https://arxiv.org/abs/2605.08319 · **Venue:** arXiv (cs.SE) · **Cited by:** not checked · **Read:** abstract
- **Problem:** A reference artifact for instrumented development of a procedural tactical deckbuilder.
- **Method:** Seeded procedural deckbuilder in Rust, compiled to WebAssembly; one rules engine for play, CLI simulation, automated tests, and save/load fixtures; a lightweight autoplay pipeline for balance probes over fixed seed ranges. The agents are not named in the text I read.
- **Assumes:** Its own procedural tactical deckbuilder (not StS); deterministic seeds.
- **Claims:** 1,000 deterministic seeds: single-player autoplay win rate 36.1%; two-player 34.9%. The author says these are repeatable probes, not balance metrics.
- **Evaluation:** Autoplay over 1,000 seeds; no generated-card or unseen-card test reported in the text read.
- **Code:** the paper describes a repo; not checked.
- **Fit:** partial. Close in engineering shape to a Rust engine plus seeded autoplay probes; says nothing about agent strength or unseen content.

---

## Code artifact (not a paper; opened, not counted)

### MiniStS (repo, Bateni & Whitehead, UC Santa Cruz)
- **Link:** https://github.com/iambb5445/MiniSTS · **License:** GPL-3.0 · **Language:** Python
- **What it has:** Headless, combat-only StS simulator. Cards built from actions, targets and status effects (factory methods in `CardRepo`); upgrade-aware values; status effects define stacking, end-of-turn changes and removal. Agents: human input, random, backtracking bots (with and without save-states), and ChatGPT-based LLM agents. `evaluation/evaluate_bot.py` runs batch sims.
- **Results:** No numbers in the repo; the README says few-shot prompting and showing outcomes to the LLM tended to hurt, and anonymising card names helped.
- **Fit:** partial. Closest small StS-like combat clone with card-as-composition and stacking status effects; subset of cards; no search baseline numbers. The paper that describes it (Bateni & Whitehead, EXAG 2024, CEUR Vol-3926 paper7) was NOT readable (binary PDF).

---

## Leads seen but not opened (for the next pass)

- Are You Lucky or Skilled? Elements of Randomness in Slay the Spire, Andersson, Trojanowski, Alvarez (CoG 2023, DOI 10.1109/COG57401.2023.10333231). The PDF at https://aeau.github.io/assets/papers/2023/andersson2023-cog03.pdf is binary; the page reads as data mining and clustering on player logs, with three skill groups and "more skilled players embrace randomness". Not opened as text.
- Exploring the Impact of Randomness in Roguelike Deck-Building Games: A Case Study of Slay the Spire (LNCS, 2023; OpenAlex W4388202557).
- Automated playtesting in collectible card games using evolutionary algorithms: A case study in Hearthstone (Knowledge-Based Systems, 2018; cited by 45 in OpenAlex). Metadata only; the OpenAlex record has no abstract.
- Summarizing Strategy Card Game AI Competition (CoG 2023; cited by 12 in OpenAlex).
- Q-DeckRec: A Fast Deck Recommendation System for Collectible Card Games (CIG 2018; cited by 42).
- Evolutionary Approach to CCG Arena Deckbuilding using Active Genes (arXiv 2020; cited by 11).
- Learning to Beat ByteRL: Exploitability of CCG Agents (arXiv 2024).
- The Edinburgh UG4 project "Exploring Different Deck Building Algorithms in Slay the Spire" (Justas Zelnia, 2023; https://project-archive.inf.ed.ac.uk/ug4/20233951/ug4_proj.pdf). PDF exceeded the fetch size limit; not opened.
- Carleton honours project on early StS combats with direct policy search (2022; https://service.scs.carleton.ca/node/6275). Redirects to carleton.ca/scs/node/6275, which returned HTTP 404. Not opened.
- Practitioner posts, not academic (noted only): Tomoki's "12 Hours Running a Slay the Spire 2 AI" blog; Doron Singer's dev.to series on search-based StS combat.
- AscensionAI technical writeup by Justin Chan (PPO on modded StS Ironclad, 585-d observation; 2026-06-02 learned deck-building addendum). https://justinochan.github.io/AscensionAI/AscensionAI_Technical_Writeup.pdf is binary and was not readable.
- Scripts of Tribute imitation MSc thesis (Aalborg, 2026): https://projekter.aau.dk/projekter/files/822057972/MasterThesis_LT_02_2026.pdf is binary; not readable.
- LLM-based StS papers, excluded by the no-LLM constraint but listed for completeness: Language-Driven Play (FDG 2024, OpenAlex W4400361424, cited by 21); Orak (arXiv 2506.03610); LLMs May Not Be Human-Level Players, But They Can Be Testers (arXiv 2410.02829; OpenAlex cited by 14); AgenticSTS (arXiv 2607.02255); SpireBench (OpenAlex W7221518687, 2026). A "Zero-Search RL for StS 2" title appears in OpenAlex (W7225726494, 2026), but no text was found by search, so it is unverified.
- Stack-Aware Enemy AI in a Roguelike Deck-Builder (I3D 2026, OpenAlex W7166585348): no text located by search, so it is unverified. Relevant to the enemy-content question, so worth a direct check.
- Sealed-deck learning-to-rank for CCGs (SJSU, 2026, OpenAlex W7171930611).

## Notes on sources (for the next review of sources.md)

- OpenAlex keyword search works (no key used; one response contained a request to register an API key, which I ignored). Two queries returned the lists above.
- arXiv html fetches worked for 2305.08234v4, 2405.06846v1, 2407.05879v1, 2504.03918, 2407.11396v1, 2603.03252; 2303.05197 via ar5iv.
- Abstract-only: arxiv.org/abs pages for 2112.03534, 2508.19484, 2605.08319, 1808.04794, 2607.04782 (these pages loaded).
- Binary PDFs failed through WebFetch: CEUR Vol-3926 paper7 (MiniStS paper), Edinburgh UG4 (too large), AscensionAI writeup, AAU thesis, CoG 2023 Andersson PDF, and the Hearthstone CIG 2017 PDF (stream aborted). The Zhang thesis PDF redirected to a scholaris landing page, which gave the abstract.
- Carleton node URL returned 404 after redirect.
- Semantic Scholar not tried.
