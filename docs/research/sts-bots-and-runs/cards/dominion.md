# Dominion and deckbuilding-game AIs: paper cards

Angle: how buy and deck decisions are learned or searched in Dominion and
similar deckbuilding or CCG games, and how bot strength is compared.
Scout date: 2026-11-01. Eight papers opened, all eight read as full text
(arXiv HTML or ar5iv).

---

### Dominion: A New Frontier for AI Research (2024)
- **Link:** https://arxiv.org/html/2405.06846v1 · **Venue:** arXiv preprint (cs.AI) · **Cited by:** 0 (OpenAlex) · **Read:** full text
- **Problem:** Dominion as an RL benchmark, where each game uses a different kingdom of 10 cards from over 350.
- **Method:** Rainbow DQN trained by self-play. A small MLP with two hidden layers of 256 takes the state and an action mask and outputs which card to gain (buy). Action-card choices come from the Provincial heuristics, so only buys are learned.
- **Assumes:** Ranked 2-player games with 2nd-edition base-game cards only. The state encoding is not described in the paper and is deferred to the authors' code. Training used a GPU.
- **Claims:** Training of 1000 steps, about 7,000 games, 45 minutes on an "NVIDIA 1080 Ti". Table 2, 1,000 games per matchup, given as Provincial / DQN-bot Win-Tie-Lose: Big Money 972/44/24 vs 912/27/61; Double Witch 596/69/335 vs 561/63/376; Big Smithy 930/7/63 vs 851/38/111; Big Militia 946/9/45 vs 850/31/119; Village/Smithy Engine 994/2/4 vs 418/24/558; Provincial buy menu 550/53/397 vs 575/62/363. The paper says the DQN-bot "beats or ties Provincial almost two thirds of the time". Provincial vs Provincial: first player won 55%, second 40%. Heuristic baselines always take the first turn.
- **Evaluation:** Round of 1,000 games per matchup against buy-menu bots (Big Money, Double Witch, Big Smithy, Big Militia, Village/Smithy Engine, Provincial). The Dominion Online Dataset holds 30,000 processed rated base-game records, drawn from up to 2,000,000 games.
- **Code:** The paper mentions "our code" and says the dataset is "made easily available online", with no URL or license given. None found.
- **Fit:** partial. It is the clearest example of a learned buy policy compared head-to-head with buy-menu bots over 1,000-game matchups. It breaks the CPU-only constraint as trained (GPU), though a 2x256 MLP is small. Card-play is not learned here.

---

### Introducing Tales of Tribute AI Competition (2023, revised 2024)
- **Link:** https://arxiv.org/html/2305.08234v4 · **Venue:** arXiv (cs.AI); a search snippet says the first edition was at IEEE CoG 2023 · **Cited by:** 5 (OpenAlex, IEEE CoG record) · **Read:** full text
- **Problem:** A competition framework for a deckbuilding CCG (Tales of Tribute), where players buy cards from a shared tavern during play.
- **Method:** Framework (Scripts of Tribute, in C#, with a JSON adapter for other languages) plus eight sample agents: Random, Max Prestige, Patron Favors, Max Agent, Decision Tree, Flat Monte Carlo, MCTS, Beam Search. None uses a neural network. MCTS searches only its own turn, with guided playouts and a max-based UCT.
- **Assumes:** Two players, hidden information (opponent hand and draw pile), patron decks chosen before the match. Competition limits are 10 seconds per turn and 256 MB of memory. The paper's tournament used a 30-second turn limit, which differs from the competition.
- **Claims:** Average win rates from Table III: MCTS 65.7%, Decision Tree 63.9%, Beam Search 63.1%, Max Prestige 25.0%, Flat MC 21.6%. Random won less than 0.25% and was left out of the comparison. Engine speed: 1,000 Random-vs-Random matches in about 8.5 s on an i5-9300H. TOTAIC 2023 winner (Ciężkowski and Krzyżyński, MCTS with five trees and an evolved heuristic): 79.22% vs Beam Search, 81.33% vs MCTS, 93.12% vs Decision Tree.
- **Evaluation:** Round robin, 400 games per pair, paired seeds with swapped starting seats (the paper notes Beam Search wins more often as first player, so seats are swapped). Engine: ScriptsOfTribute (.NET).
- **Code:** github.com/ScriptsOfTribute and a competitions archive at github.com/ScriptsOfTribute/ScriptsOfTribute-CompetitionsArchive. No license stated.
- **Fit:** partial. It shows a fair way to compare deckbuilding bots (paired seeds, seat swap, round robin, a fixed time limit). The buying happens inside play, not as a separate deck-build step.

---

### Unsound Search with Policy and Value Networks in Legends of Code and Magic (2026)
- **Link:** https://arxiv.org/html/2609.06816 · **Venue:** arXiv (cs.AI), submitted 6 Sep 2026; no peer review stated · **Cited by:** 0 (OpenAlex) · **Read:** full text
- **Problem:** Whether unsound determinized search (perfect-information Monte Carlo) can strengthen a collectible-card-game agent whose belief space is too large to enumerate (about 2^101 states in LoCM).
- **Method:** Dual-head policy and value network, started by behavior cloning of the runner-up policy and trained by self-play. At decision time it samples opponent worlds (hidden hand and deck) from a prior, runs beam search over turn plans, plays out one opponent reply, scores with the value head, and picks the plan with the highest average over worlds.
- **Assumes:** Battle phase only. Both players use the same deck, which ByteRL drafted. Hidden state is the opponent's hand and deck. 200 ms move clock, with the search budget capped at 185 ms. The paper's "certified" runs used an AWS g5.2xlarge. Peak memory about 0.9 GB with search (about 535 MB without), above the competition's 256 MB cap.
- **Claims:** Strictest configuration: 51.35% win rate vs ByteRL, 95% Wilson CI [50.37, 52.33], over 10,000 pre-registered games. Same network with argmax policy and no search: 26.8%, so search adds 24.6 points. Opponent deck known: 60.4% over 500 certified games. Internal ablation: 50.5% (uniform belief), 56.6% (runner-up prior), 59.6% (exact list). Exploitability (250-iteration PPO best response, averaged over last five evaluations): ByteRL 90.1% (peak 97.0%), search agents 61.9% (W=16) and 69.3% (W=64). Sampling saturates around 32 worlds. Quadrupling training data gave about +8 points.
- **Evaluation:** Official LoCM referee with 200 ms timer, predefined seed blocks, pre-set game counts. Exploitability follows Haluška and Schmid (2024) with a fixed pool of 32 decks. The paper also reports a Rust reimplementation of the LoCM engine, about 443x faster than gym-locm.
- **Code:** None stated in the part I read.
- **Fit:** partial. It is the closest match in this set to "learned value net plus search with hidden information", with numbers and a reproducible protocol. It is about battle play, not buying, and the memory use breaks the 256 MB cap the game used. Single author, very recent, not peer reviewed.

---

### AI solutions for drafting in Magic: the Gathering (2020, v3 2021)
- **Link:** https://arxiv.org/html/2009.00655v3 · **Venue:** IEEE CoG 2021 (per OpenAlex record) · **Cited by:** 15 (OpenAlex) · **Read:** full text
- **Problem:** Build agents that imitate human drafting picks in MTG, with a large search space, hidden information and few public datasets.
- **Method:** Five pick agents: RandomBot, RaredraftBot, DraftsimBot (expert card strengths 0–5 plus a colour bias), BayesBot (Naive Bayes over co-occurrence), and NNetBot (three dense layers that predict one of 265 cards, masked to the pack).
- **Assumes:** Core Set 2019 (M19) only. Drafts were made by humans against seven bots using the same heuristic; packs were randomly generated to match real rarity distributions. Data: 107,949 drafts, split 80/20 into 86,359 training and 21,590 test.
- **Claims:** Mean top-one accuracy in predicting human picks on the M19 test set: RandomBot 22.15%, RaredraftBot 30.53%, DraftsimBot 44.54%, BayesBot 43.35%, NNetBot 48.67%. The text also says NNetBot reached about 64.7% on the test set, which conflicts with Table II. The paper does not measure deck quality or win rate.
- **Evaluation:** Top-one agreement with human picks, 80/20 split, Tukey test (p << 2e-16 between groups).
- **Code:** github.com/khakhalin/MTG. Data: draftsim.com/draft-data, CC BY 4.0 (M19 drafts).
- **Fit:** partial. The pick from a shared pool is an acquisition decision, and the paper shows learning it from logs by imitation. The metric is agreement with humans, not strength, so it does not show that a choice is better.

---

### Mastering Strategy Card Game (Hearthstone) with Improved Techniques (2023)
- **Link:** https://arxiv.org/html/2303.05197v2 · **Venue:** IEEE CoG 2023 (per OpenAlex record) · **Cited by:** 16 (OpenAlex) · **Read:** full text
- **Problem:** Hearthstone, a 2-player, zero-sum, imperfect-information game with deck building and battle stages.
- **Method:** One end-to-end policy network for both deck building and battle, with shared card and hero embeddings. Trained with optimistic smooth fictitious play, V-Trace and UPGO, and PPO-style clipping. Random initialization during deck building encourages diverse decks. No look-ahead search and no expert data. Separate models per hero. A "cheat" variant observes the opponent's first n deck cards.
- **Assumes:** Hearthbreaker-based environment (modified by the authors). Hero picking is sampled uniformly and not learned. Observations match what a human sees.
- **Claims:** Each pairing: 3x3 hero matchups x 2 first-turn conditions x 2,500 matches. b4 beats b0 73.6%; c5 (cheat) beats b0 80.2%; c5 beats b4 55.5%. Versus one human streamer (best rank top 10 in the China official league, rank 60–70 during the test), best-of-5 Conquest: b4-23day won 3:0 and 3:0; c5-16day won 3:1 and 3:2. The paper says "The AI won all four tournaments." Compute and training time are not in the part I read.
- **Evaluation:** Machine vs machine (ladder of checkpoints b0 to b4 and c5), plus four human tournaments against one player.
- **Code:** None for the agent. Links to Hearthbreaker (github.com/danielyule/hearthbreaker), which the authors modified. arXiv license only.
- **Fit:** partial. It is an RL approach that learns deck building together with play and compares checkpoints by head-to-head win rate. It is far too heavy for CPU-only at this scale, and the card pool is much bigger than Dominion's.

---

### Mapping Hearthstone Deck Spaces through MAP-Elites with Sliding Boundaries (2019)
- **Link:** https://ar5iv.arxiv.org/html/1904.10656 (arXiv 1904.10656) · **Venue:** GECCO 2019 (per the search snippet) · **Cited by:** not checked · **Read:** full text (ar5iv)
- **Problem:** Generate many high-performing and behaviourally diverse Hearthstone decks, to find strengths, weaknesses and possible rebalancing changes.
- **Method:** MESB, a MAP-Elites variant whose grid boundaries are set at percentile points of the evolved individuals and recomputed every 100 individuals. Behaviour axes are the mean and variance of the 30 cards' mana costs. Mutation replaces k cards, with P(X=1)=1/2 and P(X=k)=1/2·P(X=k−1). Fitness is the sum of hero-health differences over 200 games.
- **Assumes:** Basic and Classic card pool. SabberStone simulator with a fixed gameplay AI (aggro or control heuristics), so only the deck varies. Results depend on this AI and may not match human play. Each configuration ran 10,000 evaluations with 200 simulated games per evaluation, on a cluster of 500 CPU nodes.
- **Claims:** Sunwalker appears in 99% of control paladin decks (elite adversaries experiment). Earthen Ring Farseer in 96.5% of aggro hunter decks. Explosive Shot in 70% of control hunter decks. After the nerf, Sunwalker in control paladin decks drops to 28.8%. The paper gives no exact win-rate values; the validation experiment's win rates are described only qualitatively.
- **Evaluation:** Three experiments: validation against starter decks, elite adversaries, and a balance test with Apriori analysis.
- **Code:** github.com/tehqin/EvoSabber. License not stated.
- **Fit:** partial. A simulator-based search over decks with a fixed play agent, the same setup the run-level question would need (deck as the variable). Its cost, 200 games per evaluation over 10,000 evaluations, is large for a CPU budget.

---

### Clustering Player Strategies from Variable-Length Game Logs in Dominion (2018)
- **Link:** https://arxiv.org/html/1811.11273 · **Venue:** arXiv (cs.AI), v2; no peer-reviewed venue stated · **Cited by:** 0 (OpenAlex) · **Read:** full text
- **Problem:** Turn variable-length Dominion game logs into numbers so that strategies can be compared.
- **Method:** Four encodings (turn, game state, opening, and a normalized version that uses each card's share of the deck, 510 dimensions). t-SNE embeds them in 2D, and regions are interpreted by hand against known strategies.
- **Assumes:** Logs from dominion.isotropic.org, the most popular 10-card set only, 2+ player games of 10–30 turns, 2,795 traces (each player gets a trace). Encodings show deck composition, not how cards were played.
- **Claims:** Qualitative only. The normalized encoding is not dominated by trace length; regions correspond to Copper-heavy, Mines, Big Money, Village/Smithy and Market decks. At turn 10, Big Money decks had the highest Province concentration (an interpretation, not a tested result). No quantitative clustering metric.
- **Evaluation:** Visual inspection of the t-SNE layout against known strategies.
- **Code:** None found. The source logs are from a fan server that closed in 2013; the paper says about 11 million files remain online. No license stated.
- **Fit:** poor to partial. It is a way to describe and label deck archetypes from logs, which could help a run-level analysis. It does not make or score a decision.

---

### Predicting Drafted Deck Strength for "Magic: the Gathering" (2026)
- **Link:** https://arxiv.org/html/2607.04782v1 · **Venue:** arXiv (cs.LG/AI), submitted July 2026; no peer review stated · **Cited by:** not checked · **Read:** full text
- **Problem:** Predict the expected win rate of the deck a drafter builds from a full or partial draft sequence, not the human pick.
- **Method:** DraftEncoder: card text embedded with frozen EmbeddingGemma, plus meta features. A 10-layer Transformer makes set-contextualized card embeddings; a 5-layer encoder over pack and draft-state tokens outputs a win probability after each pick. Trained with an NLL loss that accounts for the 7-win/3-loss stop.
- **Assumes:** Real 17Lands MTG Arena draft logs from 12 expansions, about 77k to 150k drafts each. Observed win rates are censored estimates and inflated by self-selection (average about 55%). Draft format: up to 8 players, 3 pack rounds, 13–15 card packs.
- **Claims:** Unseen expansion, Spearman rho against observed win rate (mean ± SD, 3 seeds): heuristic 0.1391 ± 0.0203; LR 0.0690 ± 0.0031; LR+Meta 0.0886 ± 0.0074; DraftEncoder 0.0879 ± 0.0131 (0.1641 ± 0.0318 after a four-day fine-tune); DraftEncoder+Meta 0.1529 ± 0.0262 (0.1809 ± 0.0381 after fine-tune). In-expansion, the paper reports nearly twice the baseline rank correlation, approaching a noise ceiling of about 0.23. Training: 100 epochs, 4 RTX A5000 GPUs, about one hour per seed.
- **Evaluation:** Temporal split on real human-played logs; Spearman rho against observed win rates.
- **Code:** github.com/akulen/MtGDraftEncoder. No license stated.
- **Fit:** partial. The target is a strength estimate for a whole deck built from acquisitions, which fits the buy-value question. The data is noisy real human play, and the model is GPU-trained, so it breaks the CPU-only constraint. Correlations are low (about 0.15 to 0.18).

---

## Not opened (checked and dropped)

- **Gerigk and Engels, "Playing Various Strategies in Dominion with Deep Reinforcement Learning" (AIIDE 2023), ojs.aaai.org/index.php/AIIDE/article/view/27518:** the page and its PDF returned an Anubis bot-check block. Only the search snippet was read: Soft Actor-Critic on a multiset encoding, "exceeds the performance of all previous learning-based approaches" and is outperformed only by search-based approaches in some configurations. Not carded.
- **Provincial (Fisher), graphics.stanford.edu/~mdfisher/DominionAI.html:** connection refused twice. Provincial's numbers come only from the DQN paper's Table 2.
- **Fenner thesis (Oklahoma, 2014), ou.edu PDF:** the fetch returned raw PDF binary with no readable text. It covers neural-network-assisted tree search for Dominion, and its contents page has a "bridges and branching" section.
- **Agder thesis (2014, UCT Dominion AI), uia.brage.unit.no:** the host did not resolve. The search snippet reports 87.5% vs moderately experienced humans and 68.5% vs DoubleWitch/SingleWitch. Not carded.
- **Mok, cs229 2016 Dominion GA poster:** certificate rejected, then host not found.
- **Yoshimura and Yoshizoe (2024), Japanese Game Programming Workshop, LSTM and A3C self-play across card sets:** only the search abstract was seen. Not carded.
- **Dominiate (rspeer/narmical/DStu forks), Dominulator, pyminion, boompig/dominion:** found by search only. The code was not opened. Dominiate has a genetic-algorithm fork at github.com/Narmical/dominiate (search summary only).
- **Janusz et al. (2018), Hearthstone evolutionary playtesting (Knowledge-Based Systems):** the OpenAlex index shows 42 citations and no abstract; not opened.
- **Legends of Code and Magic drafting with RL (Vieira, Tavares, Chaimowicz, SBGames 2020, OpenAlex W3117546930, 12 citations):** PDF on sbgames.org, not opened. The OpenAlex abstract says learned drafters "outperform the best existing agents".
- **Deep Surrogate Assisted MAP-Elites for Hearthstone deckbuilding (Hoover group):** named in a search result only, not opened.

## Search notes

- OpenAlex keyword search for deckbuilding and Dominion terms returned mostly off-topic work (tourism, magic-as-folklore). Only a few hits were on topic, so the useful vocabulary came from web search.
- Terms that worked: "Dominion AI buy strategy", "Provincial buy menu", "UCT Dominion", "Legends of Code and Magic drafting", "Hearthstone deckbuilding MAP-Elites", "Scripts of Tribute".
- Known gap: no source here reports a head-to-head benchmark of buy-menu strategies with win rates other than the DQN paper's Table 2. The Provincial and Geronimoo sources could not be opened.
