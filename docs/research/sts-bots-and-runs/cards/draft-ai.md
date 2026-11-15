# Draft AI cards (card pick and deck building)

Angle: learned pick models, simulation-based draft evaluation, and synergy
models for card drafting (MTG, Legends of Code and Magic, Sushi Go Party).
Eight papers opened. All eight were read through arxiv HTML (WebFetch), so the
numbers below come from a fetch summary of the paper, not from a direct read
of the page source. Recheck any number before relying on it.

### AI solutions for drafting in Magic: the Gathering (2020)
- **Link:** https://arxiv.org/abs/2009.00655 (also https://arxiv.org/html/2009.00655) · **Venue:** IEEE CoG 2021 (doi 10.1109/cog52621.2021.9619100) · **Cited by:** 15 (OpenAlex, W3082617223) · **Read:** full text
- **Problem:** Build a bot that picks like a human drafter in MTG, plus a public draft dataset.
- **Method:** Four agents: RandomBot, RaredraftBot, DraftsimBot (expert-scored heuristic), BayesBot (co-occurrence Naive Bayes), and NNetBot (3 dense layers, leaky ReLU, batch norm, dropout 0.5). NNetBot takes the pool and outputs a score over the whole set, masked to the current pack.
- **Assumes:** Human pick labels from simulated drafts. Set is M19 (Core Set 2019), 265 unique cards, 45 picks per draft, 24 packs per draft. Metric is top-one agreement with the human pick, so it measures imitation, not win rate.
- **Claims:** Mean test top-one accuracy: RandomBot 22.15%, RaredraftBot 30.53%, DraftsimBot 44.54%, BayesBot 43.35%, NNetBot 48.67%. Test set is 21,590 drafts (80/20 split of 107,949). All pairwise differences reported significant (Tukey, p << 2e-16). Per-pick numbers are only in a figure.
- **Evaluation:** Dataset of 107,949 Draftsim drafts (CC BY 4.0, draftsim.com/draft-data). Evaluation is imitation accuracy on held-out drafts. No win-rate test.
- **Code:** https://github.com/khakhalin/MTG (license not checked)
- **Fit:** partial. It gives a clean baseline and a data-first setup, but the target is human imitation, not run outcome. Whether that transfers to StS depends on whether the sts-for-ai runs can supply the picks.

### Predicting Human Card Selection in MTG with Contextual Preference Ranking (arXiv version, 2021; COG 2021 original)
- **Link:** https://arxiv.org/abs/2107.04438 (also https://arxiv.org/html/2107.04438) · **Venue:** arXiv 2107.04438 v2 (26 Apr 2022); the COG 2021 original is doi 10.1109/cog52621.2021.9619134 · **Cited by:** 12 for the COG 2021 original (OpenAlex, W3164721414); 0 for the arXiv entry · **Read:** full text
- **Problem:** Pick the card that adds to a set when the set's value is not the sum of its cards. Learn from pairwise preferences in context, not direct set scores.
- **Method:** Contextual Preference Ranking (CPR): a triplet Siamese network. The anchor is the current pool, positive and negative are candidate cards. Triplet loss, Euclidean distance, margin 1. Candidates are ranked by distance to the pool. Baseline is RankNet on set-level evaluations.
- **Assumes:** The same DraftSim M19 data as above (107,949 drafts, 80/20 split). Inputs are card identities (one-hot, 302 cards in the paper's setup) and the pool as a sequence. The paper says it trained for far fewer epochs than the baselines and gives no full training protocol.
- **Claims:** Test MTTA (mean top-one accuracy) and MTPD (mean pick distance, lower is better): RankNetBot 69.09% / 0.80; CPRBot D=2 53.69% / 0.98; CPRBot D=256 83.78% / 0.25. Baselines copied from Ward et al.: NNetBot 48.67% / 1.48. The text says "more than 56%" over prior work, which does not match the table. Section VI-E gives NNetBot about 64.7%, which also conflicts with the 48.67% in Table II. Neither conflict is explained.
- **Evaluation:** DraftSim M19 hold-out, top-one and pick-distance metrics. Imitation only.
- **Code:** none found on the page. Data link https://draftsim.com/draft-data/
- **Fit:** partial. Shows that a learned, context-conditioned pick ranker beats simple heuristics on imitation accuracy. The two numbers conflict, so use the table only and check against the source. The claim of set-context value is the part that matches a deck with synergies.

### Closed Drafting as a Case Study for First-Principle Interpretability, Memory, and Generalizability in Deep RL (2023)
- **Link:** https://arxiv.org/abs/2310.20654 (also https://arxiv.org/html/2310.20654) · **Venue:** arXiv (not checked for a venue) · **Cited by:** 0 (OpenAlex, W4388185037) · **Read:** full text
- **Problem:** Study what a deep RL drafter learns, whether it uses memory, and whether it generalizes to new card sets, using a small pick-and-pass card game.
- **Method:** DQN trained by self-play, 4 hidden layers of 128 units. Reward is points scored, plus 100 on a win. Interpretability uses SkopeRules to recover each agent's card priority ranking. Memory is tested with a t-test and a new MemInfluence metric (KL divergence after perturbing the memory of the previous player's hand).
- **Assumes:** Sushi Go Party, 4 players, 9 of 37 cards per configuration. Experiments use the "My First Meal" configuration plus five interpolated configurations. Human priority lists come from 172,357 Board Game Arena games.
- **Claims:** Explicit memory: mean reward difference 14.08 in favor of memory (p = 1.4×10⁻⁶⁵, second half of rounds, My First Meal). MemInfluence 1.96×10⁻⁴, so the action distribution barely depends on memory content. Largest single-card memory effect about 6% (Tempura vs Soy Sauce, second-to-last round). Win rate falls as set distance grows, but exact values are only in a figure.
- **Evaluation:** Self-play DQN against a "Human-Like Agent" built from average-human priorities. 25 train-test pairs of configurations, 100 batches of 100 rounds each.
- **Code:** none found (links only to scikit-learn-contrib/skope-rules)
- **Fit:** partial. A small DQN on a headless card game is CPU-cheap, and the setup (rule extraction, configuration shift) suits a draft study. The game is not StS, and it is a multiplayer pick-and-pass format.

### Predicting Drafted Deck Strength for "Magic: the Gathering" (2026)
- **Link:** https://arxiv.org/abs/2607.04782 (also https://arxiv.org/html/2607.04782) · **Venue:** arXiv preprint (cs.LG), submitted 6 Jul 2026 · **Cited by:** 0 (OpenAlex, W7167610787) · **Read:** full text
- **Problem:** Predict the win rate of a deck after each pick, given the partial draft so far. This targets outcome, not human imitation.
- **Method:** DraftEncoder, a transformer. Card text goes through a frozen EmbeddingGemma encoder (768-d). Player rank enters through FiLM layers. Set-level encoder, pack and draft-state tokens, and an MLP head giving win probability. Loss is NLL that accounts for the 7-win/3-loss stopping rule, with later picks weighted more.
- **Assumes:** 17Lands draft logs from MTG Arena (12 expansions, 77,374 to 149,475 drafts each). Pack sizes 13 to 15. Target is observed win rate W/(W+L), with a noise ceiling of about 0.23 Spearman from simulated Bernoulli outcomes. Win rates are inflated by self-selection (average about 55%).
- **Claims:** Spearman rho on the FDN test set, no fine-tuning: Heuristic 0.1391; LR 0.0690; LR+Meta 0.0886; DraftEncoder 0.0879; DraftEncoder+Meta 0.1529. With four days of fine-tuning: DraftEncoder 0.1641; DraftEncoder+Meta 0.1809. Experiment 1 gives no exact numbers (figure only). Without fine-tuning the heuristic beats DraftEncoder without meta features.
- **Evaluation:** Chronological split on BLB, FDN, TDM (experiment 1), and held-out FDN last 2 weeks (experiment 2). Metric is Spearman rho, mean ± std over 3 seeds.
- **Code:** https://github.com/akulen/MtGDraftEncoder (license not checked)
- **Fit:** partial. The outcome target (win rate after each pick) is the closest match to a run-level value. The model is large and needs a frozen text encoder and lots of logs, which is poor for CPU-only training. The noisy ceiling (about 0.23) shows how weak draft-outcome signal is in MTG, which is worth knowing before expecting sharp labels from StS runs.

### Two-Step Reinforcement Learning for Multistage Strategy Card Game (2023)
- **Link:** https://arxiv.org/abs/2311.17305 (also https://arxiv.org/html/2311.17305) · **Venue:** arXiv preprint, 29 Nov 2023 (Warsaw University of Technology) · **Cited by:** 0 (OpenAlex, W4389217363) · **Read:** full text
- **Problem:** Training an RL agent directly at full difficulty (20 points) failed. Staged learning is the fix. Draft is not the focus; in-game card decisions are.
- **Method:** Actor-critic RL with state encoders and action decoders (macro-action card ranking, or direct card choice). Learning modes: one-step, two-step (train at difficulty 6, then transfer to 20), and two-step interrupted (stop once a reward threshold is reached). Separate agents for planning and questing; random play in defense.
- **Assumes:** The Lord of the Rings: The Card Game, a cooperative game against scenario difficulty (not an opponent). Results at difficulty 20 across 10,000 random games.
- **Claims:** RL-RL-random at difficulty 20: one-step 71.4%, two-step 78.5%, two-step interrupted 72.2%. Single-agent questing: 48.8% (one-step) and 72.7% (two-step). Hyperparameter tuning at difficulty 8 reached 91.9±0.5%. Paper states about 40% for prior MCTS work.
- **Evaluation:** 10,000 random games of LOTR:LCG at difficulty 20; difficulty 6 for the first stage.
- **Code:** none found on the page
- **Fit:** partial. The curriculum idea (train easy, then move to the real difficulty) matches the gauntlet and the staged-difficulty question. It is not a draft model, and it targets in-game decisions in a cooperative game.

### UrzaGPT: LoRA-Tuned Large Language Models for Card Selection in Collectible Card Games (2025)
- **Link:** https://arxiv.org/abs/2508.08382 (also https://arxiv.org/html/2508.08382) · **Venue:** arXiv preprint, 11 Aug 2025 · **Cited by:** 0 (OpenAlex, W4416855465) · **Read:** full text
- **Problem:** Predict the human pick from a pack given the current pool, framed as next-token prediction.
- **Method:** LoRA supervised fine-tuning (rank 8, alpha 16, dropout 0.05) on Llama-3-8B and Mistral-7B-Instruct. Zero-shot baselines: GPT-4o and other 7-8B models.
- **Assumes:** 17Lands human draft logs for NEO (Kamigawa: Neon Dynasty) only, 5,122,921 pick decisions. Training on 1 million picks, test on a 10,000-sample subset. Mostly Premier Draft.
- **Claims:** Fine-tuned Llama-3-8B peaked at 66.2% after 10,000 steps; Mistral-7B-Instruct 64.3%. Zero-shot GPT-4o 43% with card names only, 38% with full card text (100 samples). Random baseline 0.221. Domain-specific SOTA 68% (prior contrastive model, same author). The paper contradicts itself on the untuned Llama-3-8B (abstract says it "is completely unable to draft"; the discussion cites 13%).
- **Evaluation:** Top-one pick accuracy on NEO 10,000-sample hold-out; color adherence as a second metric.
- **Code:** none. The paper says "All code will be released upon acceptance."
- **Fit:** poor. Fine-tuning 7-8B models needs a GPU, which breaks the CPU-only constraint. The NEO-only setup and imitation target also do not match a headless StS study.

### Evolutionary Approach to Collectible Card Game Arena Deckbuilding using Active Genes (2020)
- **Link:** https://arxiv.org/abs/2001.01326 (also https://arxiv.org/html/2001.01326) · **Venue:** arXiv 2001.01326 v2 (13 May 2020); the paper's own venue is not stated on the page · **Cited by:** 19 (OpenAlex, W3083380196, the venue version); 10 (OpenAlex, W2997739784, the arXiv entry) · **Read:** full text
- **Problem:** Arena draft (pick one card of three each turn for 30 picks) where the fitness of a draft can only be estimated by simulated games.
- **Method:** Evolutionary search over draft strategies. "Active genes" restrict genetic operators to genes whose cards appear in the current draft. Variants: AG, AG_weights (0.75 parent, 0.25 child), AG_all, and a baseline Evo_base.
- **Assumes:** Legends of Code and Magic, two-lane version. Card pool of 160 cards, 30 picks, 3 options per turn. Fitness is simulated win count against precomputed contest strategies and random strategies. Cost is measured in simulated games.
- **Claims:** Table I (random player, 500 drafts, 20 games per pair): AG_weights 51.74 ± 0.04 (best), AG 50.76 ± 0.05, Contest2 51.46 ± 0.09, Evo_base 49.24 ± 0.04, Random 48.26 ± 0.02. Table II (greedy player): AG_weights 57.28 ± 0.06 (best), AG 55.16 ± 0.12, Evo_base 52.16 ± 0.19, Random 46.32 ± 0.02. Budget: 1,000,000 simulated games per run.
- **Evaluation:** LOCM two-lane, 250 to 500 test drafts, fixed playing agents (random and greedy material heuristic). Hardware: 16 GB RAM, 8 vCPUs (DigitalOcean droplet). Authors estimate a random player takes about half a minute on a fast engine.
- **Code:** https://github.com/acatai/Strategy-Card-Game-AI-Competition/tree/master/paper-activegenes (license not checked)
- **Fit:** good. This is the closest match to the constraints: a headless simulator, CPU only, win-rate fitness from simulated games, and a fixed compute budget. The cost is in simulated games, which is what sts-for-ai already spends. The game is LOCM, not StS, and it uses a fixed playing agent, so the result says little about how well the draft matches a strong player.

### Learning With Generalised Card Representations for "Magic: The Gathering" (2024)
- **Link:** https://arxiv.org/abs/2407.05879 (also https://arxiv.org/html/2407.05879v1) · **Venue:** arXiv preprint, 8 Jul 2024 · **Cited by:** not checked · **Read:** full text
- **Problem:** Earlier pick models use fixed card IDs, so they cannot handle new cards without retraining.
- **Method:** Extends CPR to unseen cards. Card encoders for one-hot, random vectors, hand-coded features plus Sentence-BERT text embedding, a card-image autoencoder (32- or 1024-d latent), and 17Lands meta stats (16-d). Cards and decks go into a shared 512-d embedding space; decks are stored as a 45×n array.
- **Assumes:** About 100 million picks across 14 sets (LTR, MOM, SIR, ONE, BRO, DMU, HBG, SNC, NEO, VOW, MID, AFR, STX, M19). M19 from DraftSim, the rest from 17Lands. 80/20 split per set. Metric is top-1 accuracy. Meta features are unavailable for brand-new sets.
- **Claims:** Trained on NEO only (Table II), NEO hold-out vs unseen-set average: One-hot 67.80% (unseen n/a); Features+Meta+Image(1024) 68.00% NEO and 42.87% unseen; Meta(16) 64.73% NEO and 42.14% unseen. Random guessing about 22%. Pre-trained on all sets except BRO (Table III): 55.44% on unseen BRO; the abstract's "55%" claim is this number. Fine-tuning on BRO: 62.27% BRO. The paper says M19 accuracy rose by more than 2 points over earlier CPR work.
- **Evaluation:** Top-1 accuracy on each set's held-out split; unseen-set transfer by leaving out BRO.
- **Code:** none found (links only to 17Lands and DraftSim)
- **Fit:** partial. The idea of encoding cards from text and attributes, so that new cards can be valued without retraining, matches the problem of valuing new StS cards. The data is human MTG picks at about 100 million scale, which StS does not have, and the target is imitation.
