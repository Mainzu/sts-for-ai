# Text and program representations of game content: paper cards

Angle: language- and program-grounded representations of game content (card text encoders, language-conditioned policies, programs/DSLs as representations) for zero-shot new content.
Scouted 2026-10-24. 14 papers opened (5 with full text, 9 abstract only). Abstract-only cards say so; numbers are as the paper states them, with conditions.

---

### Learning With Generalised Card Representations for "Magic: The Gathering" (2024)
- **Link:** https://arxiv.org/abs/2407.05879 (HTML used: https://arxiv.org/html/2407.05879v1) · **Venue:** IEEE CoG 2024 (per copyright line; arXiv July 2024) · **Cited by:** not retrieved · **Read:** full text (arXiv HTML v1). Caveat: the fetch first reported only a copyright notice, then returned Table II and III. Re-check the tables before quoting.
- **Problem:** Predict MtG draft picks for cards from sets not seen in training.
- **Method:** Siamese contextual-preference network, triplet loss (margin 1). Card encoder: 4 FC layers (1024 units) over features (numerical/categorical, Sentence-BERT text embedding, conv-autoencoder image latent, 16 17Lands usage stats). Deck encoder: conv + FC to 512-d.
- **Assumes:** Discrete picks, supervised on human picks (not game outcomes). About 100M picks over 14 sets; 80/20 split per set.
- **Claims:** Table II (trained on NEO; top-1 pick accuracy, NEO test / average over unseen sets): Features 67.76% / 33.57%; Meta 64.73% / 42.14%; Features+Meta+Image1024 68.00% / 42.87%. Chance on unseen sets estimated at about 22%. Transfer (Table III): pre-trained on all sets except BRO, BRO = 55.44%. The abstract's "55%" is this number. The paper does not test text-only features.
- **Evaluation:** 17Lands picks (plus DraftSim for M19). Unseen-set test on held-out expansions (NEO average, BRO).
- **Code:** none found (no link on the fetched page).
- **Fit:** partial. Shows a frozen text embedding plus features generalises to unseen cards at a modest level. The best unseen result relies on usage statistics, which StS does not have. The target is human picks, not play outcomes.

---

### Integrating Large Language Models with Reinforcement Learning for Generalization in Strategic Card Games (2025)
- **Link:** https://aamas.csc.liv.ac.uk/Proceedings/aamas2025/pdfs/p2795.pdf · **Venue:** AAMAS 2025, extended abstract (3 pages) · **Cited by:** not retrieved · **Read:** full text (PDF)
- **Problem:** Hearthstone agents must keep playing well when new cards with new effect text arrive.
- **Method:** Fine-tuned T5-base encoder, mean-pooled and L2-normalised, gives per-card embeddings (fine-tuned on card text to description, and on GPT-4-written deck summaries). Transformer policy over observation and deck; self-play Monte Carlo returns with MSE loss; auxiliary latent world-model loss (cross-entropy on next-state embedding) weighted by beta.
- **Assumes:** Hearthstone, discrete turns, self-play. T5 fine-tuning and GPT-4 summaries are offline costs. Compute and training length are not given.
- **Claims:** Table 1, win rate vs tree-search AI at levels 0/1/2: Our agent 96% / 76% / 68%; GPT-4o 60% / 24% / 12%; Cardsformer 82% / 68% / 48%. Test decks have up to 50% unseen cards. Number of games per cell and variance are not given.
- **Evaluation:** Hearthstone, five test decks with varying unseen-card proportions, against tree-search AI at three levels.
- **Code:** https://github.com/WannianXia/GeneralizableHS, Apache-2.0 (per the GitHub page; not run). The README title is "Language-Guided Value with Latent Dynamics for Textual Card Game Agent", the IJCNN 2026 title (see leads).
- **Fit:** good for the core idea (frozen text encoder gives per-card vectors, so unseen cards need no retraining). Weak on evidence: a 3-page abstract with no game counts or variance. Needs self-play Monte Carlo returns.

---

### Cardsformer: Grounding Language to Learn a Generalizable Policy in Hearthstone (2023)
- **Link:** https://ebooks.iospress.nl/doi/10.3233/FAIA230581 · **Venue:** ECAI 2023, Frontiers in AI and Applications vol. 372, pp. 2720-2727 · **Cited by:** 4 (OpenAlex) · **Read:** abstract only (guest page; PDF link present but no text came back)
- **Problem:** Hearthstone card effects are written in natural language. Policies must generalise through that language.
- **Method:** Prediction model, trained on offline trajectories, predicts state transitions from card descriptions. Policy model meant to generalise to unseen cards. Encoding and training method are not visible.
- **Assumes:** Hearthstone via PyStone (per abstract). Offline trajectories.
- **Claims:** Abstract only: "significantly improves data efficiency" and outperforms SOTA, including when the deck has untrained cards. No numbers on the page.
- **Evaluation:** PyStone Hearthstone; deck and held-out setup not visible.
- **Code:** the abstract says public; no link on the page. Not verified.
- **Fit:** partial. Right pattern (description to transitions and policy), but no method or numbers were readable. Also a baseline in the AAMAS table above.

---

### Learning to Synthesize Programs as Interpretable and Generalizable Policies (LEAPS) (2021)
- **Link:** https://arxiv.org/abs/2108.13643 (full text: https://arxiv.org/html/2108.13643) · **Venue:** NeurIPS 2021 · **Cited by:** not retrieved · **Read:** full text (arXiv HTML; the appendix is not in the fetched text)
- **Problem:** Learn programmatic, interpretable policies that generalise to larger instances, with reward only (no demonstrations or I/O pairs).
- **Method:** Unsupervised beta-VAE over about 50k random Karel programs (RNN encoder/decoder), plus two behaviour losses (trace-matching via REINFORCE; recurrent action prediction). At test time the Cross-Entropy Method searches the latent program space using task return. The embedding is reused across tasks without retraining.
- **Assumes:** Karel gridworld, 5 actions, 5 perceptions. DSL with while/repeat/if/if-else. Deterministic simulator. CPU-scale search.
- **Claims:** Trained on 12x12 StairClimber and 8x8 Maze, evaluated on 100x100 with no further learning, mean return (StairClimber / Maze): LEAPS 1.00 / 1.00; VIPER 0.00 / 0.10; DRL-abs 0.00 / 0.04; DRL 0.00 / 0.00. LEAPS best on 5 of 6 tasks; on Harvester DRL 0.90 and VIPER 0.51 beat LEAPS 0.45.
- **Evaluation:** Karel tasks StairClimber, FourCorner, TopOff, Maze, CleanHouse, Harvester. Zero-shot scaling test on 100x100 grids.
- **Code:** github.com/clvrai/leaps appeared in search results (not opened); project site clvrai.com/leaps. License not checked.
- **Fit:** partial. A program-grounded policy with a learned program embedding and test-time search over rollouts, which fits the no-hidden-info rule. But the generalisation axis is grid size, not new content. The DSL is Karel-specific; cards would need their own effect DSL.

---

### DraftFM: A Foundation Model for Day-Zero Drafting in Magic: The Gathering (2026)
- **Link:** https://arxiv.org/html/2608.19568v1 · **Venue:** arXiv preprint (submitted 20 Aug 2026), no peer review listed · **Cited by:** not retrieved · **Read:** full text (HTML). The fetch covered the first 100,000 of 120,786 characters; conclusion and appendices not read.
- **Problem:** Score cards from a new MtG set before any draft data exists.
- **Method:** Each card is a frozen 775-d vector: 391 structured Scryfall features, plus 384 values from a frozen BAAI/bge-small-en-v1.5 embedding of type line and rules text (card name removed). Shared encoder 775→512→d, pool encoder with four learned queries, softmax over the pack. Model width d=256 (1,637,999 params).
- **Assumes:** Discrete picks. Trained on 149.5M picks from 29 sets (multi-set, features only).
- **Claims:** Zero-shot top-1 agreement at d=256: BRO 50.83%, FDN 60.37%, MSH 56.67%, mean 55.96%. Internal validation (in-distribution) 68.56%, not comparable. Cited: Bertram et al. 2024 features-only single-set unseen sets 33.6-35.6%. Caveat: BRO, FDN and MSH were also used to choose width, so they are development sets.
- **Evaluation:** 17Lands draft logs plus Scryfall records, 32 sets, 169.9M picks. Top-1/top-3, log loss, calibration; 1,000 draft-level cluster bootstraps.
- **Code:** evaluation protocol github.com/brianward92/mtga; forecast artifact github.com/brianward92/draftfm. Weights and training code release not stated. License not checked.
- **Fit:** partial. A frozen text embedding plus structured features scores unseen content with a small net (about 1.6M params), trainable on CPU in principle. But the target is human pick prediction, not play outcomes.

---

### Language-conditioned world model improves policy generalization by reading environmental descriptions (2025)
- **Link:** https://arxiv.org/html/2511.22904v1 · **Venue:** arXiv (Nov 2025), prepared for the LAW 2025 workshop · **Cited by:** not retrieved · **Read:** full text (HTML). The fetch covered the first 100,000 of 126,230 characters; the checklist tail was not read.
- **Problem:** Agents must read language describing how the environment behaves, and generalise to unseen language and dynamics without test-time MCTS.
- **Method (LED-WM):** Frozen T5 encodes each manual sentence. Each grid entity has a learned symbol embedding, randomly initialised so identity must come from language. Scaled dot-product attention matches entities to sentences; then CNN, plus DreamerV3 RSSM world model. Policy learned in imagination. Optional finetune on 60 synthetic trajectories.
- **Assumes:** MESSENGER 10x10 grid, discrete actions, 5 seeds. DreamerV3-style training (compute not given in the fetched text).
- **Claims:** Policy win rate on MESSENGER, 1000 episodes, mean +/- sd over 5 seeds. S1: LED-WM 100 +/- 0 (CRL 88 +/- 2.5; EMMA w/ curriculum 88 +/- 2.3). S2: 51.6 +/- 2.7 (CRL 76 +/- 5; EMMA w/ curriculum 95 +/- 0.4). S2-dev: 96.6 +/- 1.0 (no baselines shown). S3: 34.97 +/- 1.73 (CRL 32 +/- 1.9; EMMA w/ curriculum 22 +/- 3.8). The authors say LED-WM underperforms CRL on S2.
- **Evaluation:** MESSENGER stages S1, S2, S2-dev, S3. Test games include unseen synonyms and paraphrases, new entity combinations, new role assignments, new movement dynamics. S2 trains on one movement combination only.
- **Code:** none found in the visible text.
- **Fit:** partial. Shows entity-to-text attention generalising to unseen descriptions. But it is grid-world RL with a DreamerV3-class world model. Cost on CPU is unknown, and the held-out axis differs from card pools.

---

### RTFM: Generalising to Novel Environment Dynamics via Reading (2020, ICLR)
- **Link:** https://arxiv.org/abs/1910.08210 · **Venue:** ICLR 2020 (per comments field) · **Cited by:** not retrieved · **Read:** abstract only (the PDF fetch returned an undecodable byte dump)
- **Problem:** Policies must act in new environments with new dynamics by reading a document, not by retraining.
- **Method:** txt2pi model, which captures three-way goal / document / observation interactions. Architecture not visible from the abstract page.
- **Assumes:** Procedurally generated grid world with monsters. Document gives entity-attribute-action dynamics. Discrete actions.
- **Claims:** Abstract only: txt2pi outperforms FiLM and language-conditioned CNN baselines on dynamics not seen in training. No numbers on the page.
- **Evaluation:** Read to Fight Monsters, procedurally generated; held-out dynamics. Split not visible.
- **Code:** none found on the abstract page.
- **Fit:** partial. Clearest statement of "text describes mechanics, policy generalises to new mechanics". Not a card domain, and no numbers visible.

---

### Grounding Language to Entities and Dynamics for Generalization in Reinforcement Learning (EMMA) (2021, ICML)
- **Link:** https://arxiv.org/abs/2101.07393 · **Venue:** ICML 2021 (PMLR 139) · **Cited by:** 15 (OpenAlex) · **Read:** abstract only
- **Problem:** Use manual text to generalise to new games with new dynamics, without a pre-given text-to-observation mapping.
- **Method:** EMMA (Entity Mapper with Multi-modal Attention): entity-conditioned attention over manual sentences. End-to-end, learned from environment reward only.
- **Assumes:** Messenger multi-task environment, free-form manuals.
- **Claims:** Abstract: zero-shot to unseen games with new dynamics, "40% higher win rate than multiple baselines" (comparison and game count not stated in the abstract). Win rate on the hardest Messenger stage is 10%.
- **Evaluation:** Messenger; unseen games.
- **Code:** none found on the abstract page.
- **Fit:** partial. The entity-level grounding idea is relevant. The 40% figure has no conditions visible.

---

### Read and Reap the Rewards: Learning to Play Atari with the Help of Instruction Manuals (2023)
- **Link:** https://arxiv.org/abs/2302.04449 · **Venue:** arXiv (cs.LG), no peer-reviewed venue listed (v4 July 2024) · **Cited by:** not retrieved · **Read:** abstract only
- **Problem:** Speed up RL on Atari by reading developer manuals.
- **Method:** Read and Reward: a QA-extraction module pulls relevant manual information, and a reasoning module detects object interactions and gives an auxiliary reward to an A2C agent.
- **Assumes:** Atari games with developer manuals. Discrete actions.
- **Claims:** Abstract: "significant improvement" in performance and training speed. No figures.
- **Evaluation:** Atari games; the count is not in the abstract.
- **Code:** none found.
- **Fit:** poor. Manual-derived reward shaping for individual games; no card domain, and zero-shot transfer is not stated. This is probably the "Read and Reap" paper meant in the brief. No card-game paper with that title turned up.

---

### SPELLS: A Representation Learning Approach to Latent Power Prediction for Magic: The Gathering (2025, MSc thesis)
- **Link:** https://norma.ncirl.ie/9752/ · **Venue:** MSc thesis, National College of Ireland (not peer reviewed) · **Cited by:** 0 (OpenAlex) · **Read:** abstract only (NORMA abstract page; PDF listed but not read)
- **Problem:** Estimate latent power levels of MtG cards with under 0.4% human labels.
- **Method:** Sentence-BERT (384-d) on oracle text; ResNet50 art features reduced to 256-d by PCA; structured features. Anchor-graph label propagation gives pseudo-labels, which train a DNN, XGBoost and an SVR. Active learning with human correction.
- **Assumes:** Scryfall data, 26,795 cards. Human power labels on a 1-10 scale. No play simulation.
- **Claims:** On manually labelled anchors, all models MAE below 1.0 (1-10 scale). On cluster representatives: DNN R2 = 0.87, Spearman 0.97; XGBoost R2 0.83, MAE 0.19, Spearman 0.97; SVR unstable (MAE 1.26, R2 -0.28).
- **Evaluation:** Scryfall cards; cluster representatives. No unseen-set protocol visible in the abstract.
- **Code:** none found (a configuration manual is on NORMA).
- **Fit:** partial. Text embedding to value for unseen cards is the pattern. But labels are subjective ratings, not outcomes, and results are self-reported in one thesis.

---

### Conceptual Reinforcement Learning for Language-Conditioned Tasks (2023, AAAI)
- **Link:** https://arxiv.org/abs/2303.05069 · **Venue:** AAAI 2023 · **Cited by:** 4 (OpenAlex) · **Read:** abstract only
- **Problem:** Joint observation-text latents overfit to instances. Invariant concepts should transfer better.
- **Method:** CRL: concept-like joint representation with a multi-level attention encoder and two mutual-information constraints. How concepts reach the policy is not visible in the abstract.
- **Assumes:** RTFM and Messenger, discrete actions.
- **Claims:** Abstract: training efficiency "improved by up to 70%"; generalisation "improved by up to 30% on new environment dynamics". Baselines and conditions not on the page.
- **Evaluation:** RTFM and Messenger.
- **Code:** none found on the abstract page.
- **Fit:** partial. The invariant-concept idea is relevant to text plus state. No mechanism or conditions visible.

---

### Cardiverse: Harnessing LLMs for Novel Card Game Prototyping (2025, EMNLP)
- **Link:** https://arxiv.org/abs/2502.07128 · **Venue:** EMNLP 2025 (arXiv v1 Feb 2025, v2 Sep 2025) · **Cited by:** not retrieved · **Read:** abstract only
- **Problem:** Prototype novel card games. Human effort goes into ideation and gameplay evaluation.
- **Method:** Graph-based indexing for novel variations. LLM generates game code, validated against gameplay records. Gameplay AI is an ensemble of LLM-generated heuristic functions optimised through self-play.
- **Assumes:** A game engine written in code; design-time LLM calls only. At play time no LLM is needed (per the EMNLP summary, not the abstract).
- **Claims:** None quantitative on the abstract page.
- **Evaluation:** Not on the abstract page.
- **Code:** github.com/danruili/Cardiverse (on the abstract page). License not checked; the paper is CC BY-NC-ND 4.0.
- **Fit:** partial. A program-as-heuristic route to card-game AI from natural-language rules. No evaluation numbers seen.

---

### Latent Predictor Networks for Code Generation (2016)
- **Link:** https://arxiv.org/abs/1603.06744 · **Venue:** arXiv preprint (v2 June 2016) · **Cited by:** 82 (OpenAlex) · **Read:** abstract only
- **Problem:** Generate code from a mix of natural language and structured specification.
- **Method:** Network conditioned on multiple input functions. Marginalises over the conditioning context and generation granularity (characters or tokens).
- **Assumes:** Two new datasets from MtG and Hearthstone card games, plus one existing corpus (per abstract).
- **Claims:** Qualitative only: outperforms strong benchmarks on the three corpora. No numbers in the abstract.
- **Evaluation:** The MtG and Hearthstone card-to-code corpora; sizes not visible.
- **Code:** none found on the page.
- **Fit:** poor for play. Partial as a precedent: card text to program as an encoder-decoder task, on the same two card games.

---

### A Generalist Hanabi Agent (R3D2) (2025, withdrawn)
- **Link:** https://arxiv.org/abs/2503.14555 · **Venue:** arXiv (cs.MA), v2 withdrawn · **Cited by:** not retrieved · **Read:** abstract only (PDF not available)
- **Problem:** One MARL agent for Hanabi across 2-5 players, which also cooperates with unfamiliar partners.
- **Method:** Reformulates observations and actions as text; R3D2 distributed recurrent DQN.
- **Assumes:** Multi-agent, cooperative, cards hidden from the actor's own hand (Hanabi).
- **Claims:** None usable. The authors withdrew v2 after finding "a bug in R3D2 implementation that invalidates some of the key claims".
- **Evaluation:** Hanabi, 2-5 players.
- **Code:** https://github.com/chandar-lab/R3D2-A-Generalist-Hanabi-Agent (on the abstract page).
- **Fit:** poor. Withdrawn; do not rely on its claims.

---

## Leads not carded (not opened, or no readable text)

- **Language-Guided Value with Latent Dynamics for Textual Card Game Agent** (IJCNN 2026), DOI 10.1109/ijcnn69854.2026.11729694. Closed access; OpenAlex has no abstract. Authors Wannian Xia, Shuang Xu, Bo Xu. The GitHub repo GeneralizableHS (Apache-2.0) uses this title in its README. Likely the most on-target follow-up to the AAMAS and Cardsformer papers.
- **Language-Driven Play: LLMs as Game-Playing Agents in Slay the Spire** (FDG 2024), DOI 10.1145/3649921.3650013. DOI page gave only partial abstract text. 11 citers.
- **Reader: Model-based language-instructed reinforcement learning** (EMNLP 2023), aclanthology 2023.emnlp-main.1032. Fetches failed (socket hang-up; 403 at aaltodoc; PDF byte dump).
- **Code Generation for Collectible Card Games with Complex APIs** (FLAIRS), journals.flvc.org/FLAIRS/article/view/133044. 403 on the article page and the PDF.
- **UrzaGPT** (arXiv 2508.08382): LoRA-tuned LLM for MtG card selection (drafting). Not opened.
- **PTCG-Bench** (arXiv 2605.29653): LLM agents that read Pokemon TCG card effect text. Not opened.
- **SpireBench** (OpenAlex W7221518687, 2026): Slay the Spire long-horizon evaluation. Not opened.
- **Performance of Large Language Models as Hearthstone Agents** (FDG 2026, OpenAlex W7171619767): cites Cardsformer. Not opened.
- **Mastering Strategy Card Game (Hearthstone) with Improved Techniques** (CoG 2023, arXiv 2303.05197): learned play, not a language representation. Not opened.
